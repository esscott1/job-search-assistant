"""Deterministic fakes for tests, demos and running without credentials."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from pydantic import BaseModel

from ..domain import EmailLeads, FitAssessment, Job, KnownJob, LeadCard, NeedsHuman, Requirement
from ..ports import MailMessage

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
    with a real model. The default answers STRONG_FIT for every JD. `leads_for(email)` returns
    the leads read from an email's text; the default finds none.
    """

    def __init__(
        self,
        assessment_for: Callable[[str], FitAssessment] | None = None,
        leads_for: Callable[[str], EmailLeads] | None = None,
    ):
        self.assessment_for = assessment_for or (lambda jd: STRONG_FIT)
        self.leads_for = leads_for or (lambda email: EmailLeads(leads=[]))
        self.calls: list[str] = []
        self.usage: list[dict] = []  # same shape as AnthropicLLM.usage; a fake spends nothing

    def structured(self, *, system: str, prompt: str, schema: type[BaseModel]):
        self.calls.append("structured")
        if schema is EmailLeads:
            return self.leads_for(prompt.split("<email>")[-1].split("</email>")[0])
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
- Never interested: sales, retail

## Location
- Home area: Columbus, OH
- Max commute (miles): 40
- Remote: yes
- Relocation: no

## Email sources
| Source | Sender | Notes |
|---|---|---|
| LinkedIn alerts | jobalerts-noreply@linkedin.com | Digest of job cards |

## Never scan
- messages-noreply@linkedin.com
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


class FakeMail:
    """A fixed mailbox. `search` honours `from:` (one sender) and ignores date filters."""

    def __init__(self, messages: list[MailMessage] | None = None):
        self.messages = messages or []
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 50) -> list[MailMessage]:
        self.queries.append(query)
        sender = next((t[5:].lower() for t in query.split() if t.startswith("from:")), None)
        found = [m for m in self.messages if sender is None or sender in m.sender.lower()]
        return found[:max_results]


class InMemoryKnownJobs:
    def __init__(self, jobs: list[KnownJob] | None = None):
        self.jobs = jobs or []

    def known_jobs(self) -> list[KnownJob]:
        return list(self.jobs)


def digest_leads(email_text: str) -> EmailLeads:
    """A stand-in for the model on LinkedIn-style digests: each card is a title, a company, a
    location, an optional pay line and a "View job:" link. Every card is kept, judged a strong
    title and remote, so tests see what code does with the cards, not what a model judged."""
    leads = []
    for block in email_text.split("\n\n"):
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        link = next(
            (x.removeprefix("View job:").strip() for x in lines if x.startswith("View job:")), ""
        )
        details = [x for x in lines if not x.startswith("View job:")]
        if not link or len(details) < 2:
            continue
        pay = next((x for x in details[3:] if "$" in x), "")
        leads.append(
            LeadCard(
                company=details[1],
                title=details[0],
                location=details[2] if len(details) > 2 else "",
                posting_url=link,
                pay_range=pay,
                title_seniority="strong",
                work_arrangement="remote",
                keep=True,
            )
        )
    return EmailLeads(leads=leads)
