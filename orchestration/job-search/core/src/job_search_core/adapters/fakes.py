"""Deterministic fakes for tests, demos and running without credentials."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from pydantic import BaseModel

from ..domain import FitResult, Job, NeedsHuman


class FakeJDFetcher:
    """Returns canned JD text per job id; unknown ids need a human."""

    def __init__(self, jds: dict[str, str] | None = None):
        self.jds = jds or {}
        self.calls: list[str] = []

    def fetch(self, job: Job) -> str | NeedsHuman:
        self.calls.append(job.id)
        if job.id in self.jds:
            return self.jds[job.id]
        return NeedsHuman(kind="manual_jd", job_id=job.id, reason="fake: no JD on file")


class FakeLLM:
    """Scores by a caller-supplied rule; tailoring echoes a marker so tests can assert on it."""

    def __init__(self, score_for: Callable[[str], int] | None = None):
        self.score_for = score_for or (lambda jd: 8)
        self.calls: list[str] = []

    def structured(self, *, system: str, prompt: str, schema: type[BaseModel]):
        self.calls.append("structured")
        if schema is not FitResult:
            raise NotImplementedError(schema)
        jd = prompt.split("<job_description>")[-1]
        return FitResult(
            score=self.score_for(jd),
            top_gaps=["gap one", "gap two", "gap three"],
            rationale="fake rationale",
        )

    def text(self, *, system: str, prompt: str) -> str:
        self.calls.append("text")
        return "# Tailored resume (fake)\n"


class InMemoryResumeSource:
    def __init__(self, text: str = "Synthetic master resume"):
        self.text_value = text

    def read(self) -> str:
        return self.text_value

    def content_hash(self) -> str:
        return hashlib.sha256(self.text_value.encode()).hexdigest()[:16]


class InMemoryDocumentStore:
    def __init__(self):
        self.saved: dict[str, str] = {}

    def save_resume(self, job_id: str, content: str) -> str:
        self.saved[job_id] = content
        return f"memory://resumes/{job_id}.md"
