#!/usr/bin/env python3
"""Check a tailored resume's content.json against the full resume before it's delivered.

Usage: check_content.py --inventory Full-Resume.md --content content.json [--today YYYY-MM-DD] [--years 15]
       check_content.py --inventory Full-Resume.md

With --inventory alone, it only reads the full resume's work history and prints what it found,
{"ok": bool, "employers": [{"name", "dates", "roles": [{"title", "dates"}]}], "warnings": [...]},
where ok is false when no headings were found. job-search-profile uses this to check a full
resume the user attaches during setup.


Reads the full resume's work history from its headings, one employer per '### Employer | dates'
and one role per '#### Title | dates' under it, and checks that:
- content.json passes render_resume.py's own rules (no company descriptions; every role has at
  least one line, a summary or a bullet);
- every employer, role title and date range in content.json matches the full resume;
- every role that ended within the last --years years (15 by default) is on the resume. Older
  roles may be left out when they aren't relevant to the job; they're listed in
  "omitted_old_roles" so the leaving out can be reported.

With --content, prints JSON: {"ok": bool, "errors": [...], "warnings": [...], "omitted_old_roles": [...]}.
Exit 0 when ok, 1 when there are errors (or, with --inventory alone, no headings), 2 when an input
can't be read.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from render_resume import content_problems, normalize  # noqa: E402

MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
ONGOING = ("present", "current", "now")
NO_HEADINGS = "the full resume's work history isn't in '### Employer | dates' and '#### Title | dates' headings"


@dataclass
class Role:
    title: str
    dates: str


@dataclass
class Employer:
    name: str
    dates: str
    roles: list[Role] = field(default_factory=list)


def parse_inventory(text: str) -> list[Employer]:
    """Employers and their roles, from '### Employer | dates' and '#### Title | dates' headings."""
    employers: list[Employer] = []
    current = None
    for line in text.splitlines():
        m = re.match(r"(###|####)\s+(.+?)\s*\|\s*(.+?)\s*$", line)
        if m and m.group(1) == "###":
            current = Employer(m.group(2), m.group(3))
            employers.append(current)
        elif m and current:
            current.roles.append(Role(m.group(2), m.group(3)))
        elif re.match(r"#{1,3}\s", line):
            current = None  # any other heading ends that employer's roles
    return employers


def end_month(dates: str, today: dt.date):
    """(year, month) a date range ends in; year-only ends count as December. None if unreadable."""
    end = re.split(r"\s*(?:[-–—]|\bto\b)\s*", dates.strip(), flags=re.I)[-1].strip().lower()
    if end in ONGOING:
        return today.year, today.month
    m = re.fullmatch(r"(?:([a-z]{3})[a-z]*\.?\s+)?(\d{4})", end)
    if not m or (m.group(1) and m.group(1) not in MONTHS):
        return None
    return int(m.group(2)), MONTHS[m.group(1)] if m.group(1) else 12


def is_old(dates: str, today: dt.date, years: int):
    """True when the range ended more than `years` years before today; None if unreadable."""
    end = end_month(dates, today)
    if end is None:
        return None
    return end < (today.year - years, today.month)


def starts(full: str, prefix: str) -> bool:
    return bool(prefix.strip()) and normalize(full).startswith(normalize(prefix))


def check(inventory: str, content: dict, today: dt.date, years: int) -> dict:
    errors = list(content_problems(content))
    warnings: list[str] = []
    omitted: list[dict] = []
    employers = parse_inventory(inventory)
    if not employers:
        warnings.append(f"history checks skipped: {NO_HEADINGS}")
        return dict(ok=not errors, errors=errors, warnings=warnings, omitted_old_roles=omitted)

    shown: set[tuple[int, int]] = set()  # (employer index, role index) on the resume
    for job in content.get("experience", []):
        company = job.get("company", "")
        matches = [i for i, e in enumerate(employers) if starts(e.name, company)]
        if not matches:
            warnings.append(f"{company}: not a '###' employer heading in the full resume, so not checked")
            continue
        exact = [i for i in matches if normalize(employers[i].dates) == normalize(job.get("dates", ""))]
        if not exact:
            errors.append(f"{company}: dates '{job.get('dates')}' don't match the full resume "
                          f"('{employers[matches[0]].dates}')")
        ei = (exact or matches)[0]
        employer = employers[ei]
        if not employer.roles:
            warnings.append(f"{company}: the full resume lists no '####' roles under it, so its roles aren't checked")
            continue
        for role in job.get("roles", []):
            title = role.get("title", "")
            cands = [i for i, r in enumerate(employer.roles) if starts(r.title, title)]
            if not cands:
                errors.append(f"{title} at {company}: no role with that title in the full resume")
                continue
            same_dates = [i for i in cands if normalize(employer.roles[i].dates) == normalize(role.get("dates", ""))]
            if not same_dates:
                errors.append(f"{title} at {company}: dates '{role.get('dates')}' don't match the full resume "
                              f"('{employer.roles[cands[0]].dates}')")
            shown.add((ei, (same_dates or cands)[0]))

    for ei, employer in enumerate(employers):
        for ri, role in enumerate(employer.roles):
            if (ei, ri) in shown:
                continue
            old = is_old(role.dates, today, years)
            where = f"{role.title} at {employer.name} ({role.dates})"
            if old is None:
                errors.append(f"{where}: left out, and its end date can't be read; keep it or check by hand")
            elif old:
                omitted.append(dict(company=employer.name, title=role.title, dates=role.dates))
            else:
                errors.append(f"{where}: left out, but it ended within the last {years} years, so it must stay")
    return dict(ok=not errors, errors=errors, warnings=warnings, omitted_old_roles=omitted)


def outline(inventory: str) -> dict:
    """The work history the headings describe, for checking a full resume on its own."""
    employers = parse_inventory(inventory)
    warnings = [] if employers else [NO_HEADINGS]
    warnings += [f"{e.name} ({e.dates}): no '####' roles under it" for e in employers if not e.roles]
    return dict(ok=bool(employers), warnings=warnings, employers=[
        dict(name=e.name, dates=e.dates, roles=[dict(title=r.title, dates=r.dates) for r in e.roles])
        for e in employers])


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--inventory", required=True)
    a.add_argument("--content")
    a.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    a.add_argument("--years", type=int, default=15)
    a = a.parse_args()
    try:
        inventory = Path(a.inventory).read_text(encoding="utf-8")
        content = json.loads(Path(a.content).read_text(encoding="utf-8")) if a.content else None
    except (OSError, ValueError) as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(2)
    result = outline(inventory) if content is None else check(inventory, content, a.today, a.years)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
