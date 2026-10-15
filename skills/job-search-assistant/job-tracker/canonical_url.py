#!/usr/bin/env python3
"""Canonical form of a job-posting URL, used as the tracker's dedup key.

The same job arrives in several emails with different tracking parameters, so the
link in the email can't be compared as-is. This script reduces it to one stable URL
per posting, and drops anything that isn't safe to store (LinkedIn email links carry
a one-time sign-in token, `otpToken`, in the query string).

Usage:
    python3 canonical_url.py <url> [<url> ...]      # or one URL per line on stdin
Prints one JSON array of {"input": ..., "canonical": ...}. `canonical` is "" when the
link isn't a posting (a search page, an unsubscribe link) or can't be resolved without
following it (an opaque click-tracker such as MyJobHelper's).
"""

from __future__ import annotations

import html
import json
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Hosts whose links are opaque redirects: the job isn't visible in the URL itself.
CLICK_TRACKERS = ("clicks.alerts.myjobhelper.com",)

# Hosts that are never a posting. A Gmail link's message ID is in the fragment, which
# the generic rule drops, so every email would otherwise share one "canonical" URL.
NOT_POSTINGS = ("mail.google.com",)

# Query parameters that only track the click; everything else is kept.
TRACKING_PARAMS = {
    "eid",
    "fbclid",
    "gclid",
    "lipi",
    "midsig",
    "midtoken",
    "otptoken",
    "ref",
    "refid",
    "source",
    "src",
    "trackingid",
    "trk",
    "trkemail",
}
TRACKING_PREFIXES = ("utm_", "mc_")

LINKEDIN_JOB = re.compile(r"/jobs/view/(?:[^/]*-)?(\d{6,})")
GREENHOUSE_JOB = re.compile(r"^/([^/]+)/jobs/(\d+)")
LEVER_JOB = re.compile(r"^/([^/]+)/([0-9a-f-]{36})")
ASHBY_JOB = re.compile(r"^/([^/]+)/([0-9a-f-]{36})")
# Workday: optional locale, the site name, then job/<location>/<slug>_<req id> or
# details/<slug>_<req id>. Anything after the posting (/apply, /login) is dropped.
WORKDAY_JOB = re.compile(r"^/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/((?:job/[^/]+|details)/[^/]+)")
ICIMS_JOB = re.compile(r"^/jobs/(\d+)")
SMARTRECRUITERS_JOB = re.compile(r"^/([^/]+)/(\d{6,}[^/]*)")


def _is_tracking(key: str) -> bool:
    key = key.lower()
    return key in TRACKING_PARAMS or key.startswith(TRACKING_PREFIXES)


def canonical(url: str) -> str:
    url = html.unescape((url or "").strip())
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return ""
    host = parts.hostname.lower()
    query = parse_qsl(parts.query, keep_blank_values=True)

    if host.endswith(CLICK_TRACKERS) or host in NOT_POSTINGS:
        return ""

    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        match = LINKEDIN_JOB.search(parts.path)
        job_id = match.group(1) if match else dict(query).get("currentJobId", "")
        return f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id.isdigit() else ""

    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
        match = GREENHOUSE_JOB.match(parts.path)
        if match:
            return f"https://job-boards.greenhouse.io/{match.group(1)}/jobs/{match.group(2)}"

    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io") and parts.path.startswith("/embed/"):
        params = dict(query)
        if params.get("for") and params.get("token", "").isdigit():
            return f"https://job-boards.greenhouse.io/{params['for']}/jobs/{params['token']}"

    if host == "jobs.lever.co":
        match = LEVER_JOB.match(parts.path)
        if match:
            return f"https://jobs.lever.co/{match.group(1)}/{match.group(2)}"

    if host == "jobs.ashbyhq.com":
        match = ASHBY_JOB.match(parts.path)
        if match:
            return f"https://jobs.ashbyhq.com/{match.group(1)}/{match.group(2)}"

    if host.endswith(".myworkdayjobs.com"):
        match = WORKDAY_JOB.match(parts.path)
        if match:
            return f"https://{host}/{match.group(1)}/{match.group(2)}"

    if host.endswith(".icims.com"):
        match = ICIMS_JOB.match(parts.path)
        if match:
            return f"https://{host}/jobs/{match.group(1)}/job"

    if host == "jobs.smartrecruiters.com":
        match = SMARTRECRUITERS_JOB.match(parts.path)
        if match:
            return f"https://jobs.smartrecruiters.com/{match.group(1)}/{match.group(2)}"

    kept = sorted((k, v) for k, v in query if not _is_tracking(k))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(kept), ""))


def main() -> int:
    urls = sys.argv[1:] or [line for line in sys.stdin.read().splitlines() if line.strip()]
    print(json.dumps([{"input": u, "canonical": canonical(u)} for u in urls], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
