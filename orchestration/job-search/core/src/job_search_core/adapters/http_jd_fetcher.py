"""Fetch job descriptions from company / ATS pages over plain HTTP.

Some sites will never work unattended (LinkedIn requires a signed-in session; some ATS
pages block bots). Those return NeedsHuman instead of raising, so one bad posting never
fails a whole run — the job is parked for a manual JD and everything else continues.
"""

from __future__ import annotations

import time
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from ..domain import Job, NeedsHuman

NEVER_FETCH = ("linkedin.com",)
_RETRYABLE = {429, 500, 502, 503, 504}
_USER_AGENT = "Mozilla/5.0 (job-search-pipeline; personal use)"


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "\n".join(parser.parts)


class HttpJDFetcher:
    def __init__(self, client: httpx.Client | None = None, retries: int = 3, backoff: float = 1.5):
        self.client = client or httpx.Client(
            timeout=20, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
        )
        self.retries = retries
        self.backoff = backoff

    def fetch(self, job: Job) -> str | NeedsHuman:
        if not job.url:
            return NeedsHuman(kind="manual_jd", job_id=job.id, reason="No posting URL on record")
        host = urlparse(job.url).netloc.lower()
        if any(host.endswith(d) for d in NEVER_FETCH):
            return NeedsHuman(
                kind="manual_jd",
                job_id=job.id,
                reason=f"{host} requires a signed-in browser session",
                payload={"url": job.url},
            )

        last_error = ""
        for attempt in range(self.retries):
            try:
                resp = self.client.get(job.url)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if resp.status_code == 200:
                    return html_to_text(resp.text)
                last_error = f"HTTP {resp.status_code}"
                if resp.status_code not in _RETRYABLE:
                    break
            time.sleep(self.backoff * (2**attempt))

        return NeedsHuman(
            kind="manual_jd",
            job_id=job.id,
            reason=f"Could not fetch posting ({last_error})",
            payload={"url": job.url},
        )
