#!/usr/bin/env python3
"""Read one job posting page: its description and whether it's really closed.

A page reader that drops scripts can get a posting badly wrong. Some career platforms put the
whole job description in an embedded JSON block and ship a "this position has been filled"
banner, hidden by their JavaScript, on every job page. Read as plain text, an open job then
looks filled and has no description. This script reads the page's structured data instead.

Usage:
    python3 read_posting.py <url>                    # fetch the page (plain GET, no sign-in)
    python3 read_posting.py --html <file> [<url>]    # parse a saved page instead
Prints one JSON object:
    status           open | closed | unknown | unreachable
    status_evidence  why, in a few words
    source           json-ld | embedded-data | visible-text | ""
    title, location, pay, posted, arrangement, jd_text, final_url
`closed` comes only from hard evidence: HTTP 404/410, a redirect away from the posting, or
structured data whose validThrough date has passed. Banner or boilerplate text never makes a
posting closed. Exit code 0 when the page was read, 3 when it couldn't be fetched.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

USER_AGENT = "Mozilla/5.0 (compatible; job-search-assistant; +https://github.com/esscott1/job-search-assistant)"
TIMEOUT = 20

# Elements that are page templates rather than content: the hidden "job expired" notice.
TEMPLATE_MARKERS = ("job-expire", "job-completion", "job-expired", "jobexpired")
SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

# Banner wording that a closed posting would show. Only reported, never acted on here.
CLOSURE_TEXT = re.compile(
    r"(?:position|job|posting|requisition)\s+(?:has\s+been|is)\s+(?:filled|closed|no longer)"
    r"|no longer (?:accepting applications|available|open)",
    re.I,
)


def html_to_text(fragment: str) -> str:
    """A description's HTML as plain text: one line per paragraph or list item."""
    text = re.sub(r"(?i)<\s*/?\s*br\s*/?\s*>|</\s*(?:p|div|h\d|ul|ol)\s*>", "\n", fragment or "")
    text = re.sub(r"(?i)<\s*li[^>]*>", "\n- ", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    lines = (re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class _VisibleText(HTMLParser):
    """Visible text, leaving out scripts, hidden elements and job-expiry templates."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_parts: list[str] = []
        self._stack: list[tuple[str, bool]] = []  # per open element: (tag, is its content hidden?)

    def _hides(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        if tag in SKIP_TAGS:
            return True
        joined = " ".join(f"{k}={v or ''}" for k, v in attrs).lower()
        if any(marker in joined for marker in TEMPLATE_MARKERS):
            return True
        values = dict(attrs)
        style = (values.get("style") or "").replace(" ", "").lower()
        return "hidden" in values or values.get("aria-hidden") == "true" or "display:none" in style

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        hidden = self._hidden() or self._hides(tag, attrs)
        self._stack.append((tag, hidden))

    def handle_endtag(self, tag):
        # Pop back to the matching open tag, so an unclosed <li> or <p> can't shift the state.
        if any(open_tag == tag for open_tag, _ in self._stack):
            while self._stack.pop()[0] != tag:
                pass

    def _hidden(self) -> bool:
        return bool(self._stack) and self._stack[-1][1]

    def handle_data(self, data):
        text = data.strip()
        if text:
            (self.hidden_parts if self._hidden() else self.parts).append(text)


def _json_ld_postings(page: str) -> list[dict]:
    postings = []
    for block in re.findall(r"(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>", page):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                kind = item.get("@type")
                if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                    postings.append(item)
                stack.extend(v for k, v in item.items() if k == "@graph")
    return postings


def _place(location) -> str:
    places = location if isinstance(location, list) else [location]
    names = []
    for place in places:
        address = place.get("address", {}) if isinstance(place, dict) else {}
        if isinstance(address, dict):
            parts = [address.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
            parts = [p.get("name", "") if isinstance(p, dict) else p for p in parts]
            names.append(", ".join(p for p in parts if p))
    return "; ".join(n for n in names if n)


def _salary(salary) -> str:
    if not isinstance(salary, dict):
        return ""
    value = salary.get("value", {})
    if not isinstance(value, dict):
        return f"{value} {salary.get('currency', '')}".strip()
    low, high = value.get("minValue"), value.get("maxValue")
    amount = f"{low}-{high}" if low and high else str(value.get("value") or low or high or "")
    unit = (value.get("unitText") or "").lower()
    return " ".join(p for p in (amount, salary.get("currency", ""), f"per {unit}" if unit else "") if p)


def _from_json_ld(posting: dict, today: dt.date) -> dict:
    result = {
        "source": "json-ld",
        "title": posting.get("title", ""),
        "location": _place(posting.get("jobLocation")),
        "pay": _salary(posting.get("baseSalary")),
        "posted": str(posting.get("datePosted", ""))[:10],
        "arrangement": "remote" if posting.get("jobLocationType") == "TELECOMMUTE" else "",
        "jd_text": html_to_text(posting.get("description", "")),
    }
    valid_through = str(posting.get("validThrough", ""))[:10]
    try:
        expired = valid_through and dt.date.fromisoformat(valid_through) < today
    except ValueError:
        expired = False
    if expired:
        result.update(status="closed", status_evidence=f"structured data: validThrough {valid_through} has passed")
    elif result["jd_text"]:
        result.update(status="open", status_evidence="structured data: a current JobPosting with a description")
    else:
        result.update(status="unknown", status_evidence="structured data has no description")
    return result


def _embedded_job(page: str) -> dict | None:
    """The job object some career platforms embed in the page as `phApp.ddo = {...}`."""
    match = re.search(r"phApp\.ddo\s*=\s*", page)
    if not match:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(page, match.end())
        return data["jobDetail"]["data"]["job"] or {}
    except (ValueError, KeyError, TypeError):
        return None


def _from_embedded(job: dict) -> dict:
    sections = [html_to_text(job.get("description", ""))]
    for key, heading in (("requiredSkillsEducation", "Required"), ("preferredSkillsEducation", "Preferred")):
        text = html_to_text(job.get(key, ""))
        if text and text[:80] not in sections[0]:
            sections.append(f"{heading}:\n{text}")
    pay = ""
    if job.get("salaryMin") and job.get("salaryMax"):
        low, high = sorted((float(job["salaryMin"]), float(job["salaryMax"])))
        unit = re.search(r"([A-Z]{3})\s+(per \w+)", job.get("payRange", ""))
        pay = f"{low:,.0f}-{high:,.0f}" + (f" {unit.group(1)} {unit.group(2)}" if unit else "")
    jd_text = "\n\n".join(s for s in sections if s)
    result = {
        "source": "embedded-data",
        "title": job.get("title", ""),
        "location": job.get("location") or job.get("cityStateCountry", ""),
        "pay": pay or job.get("payRange", ""),
        "posted": str(job.get("postedDate", ""))[:10],
        "arrangement": job.get("physicalLocation", ""),
        "jd_text": jd_text,
    }
    if jd_text:
        result.update(status="open", status_evidence="the page's embedded job data has the full description")
    else:
        result.update(status="unknown", status_evidence="the page's embedded job data is empty")
    return result


def read_page(page: str, today: dt.date | None = None) -> dict:
    """Everything this script can tell from the page's HTML alone."""
    today = today or dt.date.today()
    postings = _json_ld_postings(page)
    if postings:
        return _from_json_ld(postings[0], today)
    job = _embedded_job(page)
    if job:
        return _from_embedded(job)
    parser = _VisibleText()
    parser.feed(page)
    visible = "\n".join(parser.parts)
    notes = []
    if any(CLOSURE_TEXT.search(t) for t in parser.hidden_parts):
        notes.append("a hidden 'filled' template was ignored")
    if CLOSURE_TEXT.search(visible):
        notes.append("visible text mentions closure; judge it against the description")
    return {
        "source": "visible-text",
        "title": "",
        "location": "",
        "pay": "",
        "posted": "",
        "arrangement": "",
        "jd_text": visible,
        "status": "unknown",
        "status_evidence": "; ".join(notes) or "no structured data on the page",
    }


def _job_tokens(url: str) -> set[str]:
    """Path parts that identify the job: anything with a digit, such as a requisition number."""
    return {t for t in re.split(r"[/_\-.?=&]+", urlsplit(url).path) if len(t) >= 4 and re.search(r"\d", t)}


def fetch(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            final_url = response.geturl()
            charset = response.headers.get_content_charset() or "utf-8"
            page = response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as err:
        if err.code in (404, 410):
            return {"status": "closed", "status_evidence": f"HTTP {err.code}", "source": "", "final_url": url}
        return {"status": "unreachable", "status_evidence": f"HTTP {err.code}", "source": "", "final_url": url}
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        reason = getattr(err, "reason", err)
        return {"status": "unreachable", "status_evidence": str(reason), "source": "", "final_url": url}
    tokens = _job_tokens(url)
    if final_url != url and tokens and not any(t in final_url for t in tokens):
        return {"status": "closed", "status_evidence": f"redirected away from the posting to {final_url}",
                "source": "", "final_url": final_url}
    return {**read_page(page), "final_url": final_url}


def main(argv: list[str]) -> int:
    if argv[:1] == ["--html"] and len(argv) >= 2:
        with open(argv[1], encoding="utf-8", errors="replace") as handle:
            result = {**read_page(handle.read()), "final_url": argv[2] if len(argv) > 2 else ""}
    elif len(argv) == 1:
        result = fetch(argv[0])
    else:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 3 if result["status"] == "unreachable" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
