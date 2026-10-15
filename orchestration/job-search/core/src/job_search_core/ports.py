"""Ports: the interfaces steps depend on. Adapters implement them (real ones and fakes).

Steps never import Gmail, Drive, SQLite or an LLM SDK directly — they receive a port.
That keeps steps testable without credentials and lets any orchestrator wire them up.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, TypeVar

from pydantic import BaseModel

from .domain import Job, NeedsHuman, Status, StatusChange, StatusSource

T = TypeVar("T", bound=BaseModel)


class TrackerPort(Protocol):
    """System of record for jobs and their status history."""

    def add(self, job: Job) -> Job: ...
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


class JDFetcherPort(Protocol):
    def fetch(self, job: Job) -> str | NeedsHuman:
        """Return job-description text, or NeedsHuman if it can't be fetched unattended."""
        ...


class LLMPort(Protocol):
    def structured(self, *, system: str, prompt: str, schema: type[T]) -> T: ...
    def text(self, *, system: str, prompt: str) -> str: ...


class ResumeSourcePort(Protocol):
    def read(self) -> str:
        """The master resume as text."""
        ...

    def content_hash(self) -> str: ...


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
