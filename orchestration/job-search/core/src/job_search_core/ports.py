"""Ports: the interfaces steps depend on. Adapters implement them (real ones and fakes).

Steps never import Gmail, Drive, SQLite or an LLM SDK directly — they receive a port.
That keeps steps testable without credentials and lets any orchestrator wire them up.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, TypeVar

from pydantic import BaseModel

from .domain import Job, KnownJob, NeedsHuman, PluginJob, Status, StatusChange, StatusSource

T = TypeVar("T", bound=BaseModel)


class TrackerPort(Protocol):
    """System of record for jobs and their status history."""

    def add(self, job: Job) -> Job:
        """Add a new job. Raises domain.DuplicateJobId if its ID is taken."""
        ...

    def get(self, job_id: str) -> Job: ...
    def list(self, statuses: set[Status] | None = None) -> list[Job]: ...
    def save(self, job: Job) -> Job:
        """Persist non-status fields. Status only changes via `transition`."""
        ...

    def transition(
        self, job_id: str, to: Status, source: StatusSource, note: str | None = None
    ) -> Job:
        """Change status, enforcing domain.TRANSITIONS and recording history."""
        ...

    def history(self, job_id: str) -> list[StatusChange]: ...

    def next_id(self, prefix: str) -> str:
        """The highest number used with this prefix, plus one, so an ID is never reused.
        Another writer can take it before `add`; usecases.add_new_job retries."""
        ...


class JDFetcherPort(Protocol):
    def fetch(self, job: Job) -> str | NeedsHuman:
        """Return job-description text, or NeedsHuman if it can't be fetched unattended."""
        ...


class LLMPort(Protocol):
    def structured(self, *, system: str, prompt: str, schema: type[T]) -> T: ...
    def text(self, *, system: str, prompt: str) -> str: ...


class ResumeSourcePort(Protocol):
    def read(self) -> str:
        """The full resume as text: the whole career history, not a tailored selection."""
        ...

    def content_hash(self) -> str: ...


class ProfileSourcePort(Protocol):
    def read(self) -> str:
        """The job-search profile as Markdown: the same file the plugin's profile skill writes."""
        ...


class DocumentStorePort(Protocol):
    def save_resume(self, job_id: str, content: str) -> str:
        """Store a tailored resume; return its path or URI."""
        ...


class MailMessage(BaseModel):
    id: str
    thread_id: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str


class MailPort(Protocol):
    def search(self, query: str, max_results: int = 50) -> list[MailMessage]: ...


class KnownJobsPort(Protocol):
    def known_jobs(self) -> list[KnownJob]:
        """Every job intake must not log again: the tracker's rows and, where the tracker has one,
        its archive (except rows a reset archived, which may come back as new leads)."""
        ...


class PluginJobsPort(Protocol):
    def jobs(self) -> list[PluginJob]:
        """The rows of the plugin's Job Log, read-only: what Tier 2 shadow mode mirrors."""
        ...


class JobFilesPort(Protocol):
    def saved_jd(self, job_id: str) -> str | None:
        """The JD the plugin saved for this job (`<ID>_JD.md`), or None if there isn't one."""
        ...

    def fit_report(self, job_id: str, run: int) -> str | None:
        """The plugin's fit report for this run (`<ID>_fit_r<n>_<date>.md`), or None."""
        ...
