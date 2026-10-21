"""Deterministic fakes for tests, demos and running without credentials."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from pydantic import BaseModel

from ..domain import FitAssessment, Job, NeedsHuman, Requirement

# A close match: every requirement met, remote, the right level. The rubric scores it 10.
STRONG_FIT = FitAssessment(
    title_seniority="strong",
    work_arrangement="remote",
    requirements=[
        Requirement(
            text="10+ years in enterprise architecture", type="required", evidence="strong"
        ),
        Requirement(text="AI program leadership", type="required", evidence="strong"),
        Requirement(text="AWS certification", type="preferred", evidence="strong"),
    ],
    top_gaps=[],
    rationale="fake: strong fit",
)

# Good on paper, but on-site somewhere the profile won't move to. The evidence alone would
# score 9; the rubric's relocation cap holds it at 3, so it ends below the threshold.
WEAK_FIT = FitAssessment(
    title_seniority="strong",
    work_arrangement="relocation_required",
    requirements=[
        Requirement(
            text="10+ years in enterprise architecture", type="required", evidence="strong"
        ),
        Requirement(text="Utilities industry experience", type="preferred", evidence="partial"),
    ],
    top_gaps=["Relocation required (TX)", "Utilities experience thin"],
    rationale="fake: strong on paper, but needs a move the profile rules out",
)


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
    """Assesses by a caller-supplied rule; tailoring echoes a marker so tests can assert on it.

    `assessment_for(jd)` returns the FitAssessment for a JD; the rubric then scores it, as
    with a real model. The default answers STRONG_FIT for every JD.
    """

    def __init__(self, assessment_for: Callable[[str], FitAssessment] | None = None):
        self.assessment_for = assessment_for or (lambda jd: STRONG_FIT)
        self.calls: list[str] = []

    def structured(self, *, system: str, prompt: str, schema: type[BaseModel]):
        self.calls.append("structured")
        if schema is not FitAssessment:
            raise NotImplementedError(schema)
        jd = prompt.split("<job_description>")[-1].split("</job_description>")[0]
        return self.assessment_for(jd)

    def text(self, *, system: str, prompt: str) -> str:
        self.calls.append("text")
        return "# Tailored resume (fake)\n"


class InMemoryResumeSource:
    def __init__(self, text: str = "Synthetic full resume"):
        self.text_value = text

    def read(self) -> str:
        return self.text_value

    def content_hash(self) -> str:
        return hashlib.sha256(self.text_value.encode()).hexdigest()[:16]


SYNTHETIC_PROFILE = """# Job search profile

## Candidate
- Name: Jordan Example
- Full resume: Full-Resume.md

## Target roles
- Role families: enterprise architecture, AI enablement
- Seniority: senior, principal
- Adjacent roles: solutions architect

## Location
- Home area: Columbus, OH
- Max commute (miles): 40
- Remote: yes
- Relocation: no
"""


class InMemoryProfileSource:
    def __init__(self, text: str = SYNTHETIC_PROFILE):
        self.text_value = text

    def read(self) -> str:
        return self.text_value


class InMemoryDocumentStore:
    def __init__(self):
        self.saved: dict[str, str] = {}

    def save_resume(self, job_id: str, content: str) -> str:
        self.saved[job_id] = content
        return f"memory://resumes/{job_id}.md"
