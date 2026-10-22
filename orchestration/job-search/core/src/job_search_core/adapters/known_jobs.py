"""Known jobs for intake's dedup, read from a tracker."""

from __future__ import annotations

from ..domain import KnownJob
from ..ports import TrackerPort


class TrackerKnownJobs:
    """The tracker's own rows. The SQLite tracker has no archive, so that's every known job."""

    def __init__(self, tracker: TrackerPort):
        self.tracker = tracker

    def known_jobs(self) -> list[KnownJob]:
        return [
            KnownJob(id=j.id, company=j.company, title=j.title, canonical_url=j.canonical_url)
            for j in self.tracker.list()
        ]
