"""Domain model: jobs, fit results, statuses and the legal transitions between them."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Status(StrEnum):
    NEW = "new"
    NEEDS_MANUAL_JD = "needs_manual_jd"
    SCORED = "scored"
    BELOW_THRESHOLD = "below_threshold"
    RESUME_DRAFTED = "resume_drafted"
    NEEDS_EDIT = "needs_edit"
    RESUME_READY = "resume_ready"
    SUBMITTED = "submitted"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    CLOSED_BY_EMPLOYER = "closed_by_employer"


# Statuses after which nothing changes.
TERMINAL: frozenset[Status] = frozenset(
    {Status.ACCEPTED, Status.DECLINED, Status.REJECTED, Status.WITHDRAWN, Status.CLOSED_BY_EMPLOYER}
)

# Statuses where the resume has not gone to the employer yet, so it may be re-scored
# or re-tailored (for example after the master resume changes).
PRE_SUBMISSION: frozenset[Status] = frozenset(
    {
        Status.NEW,
        Status.NEEDS_MANUAL_JD,
        Status.SCORED,
        Status.BELOW_THRESHOLD,
        Status.RESUME_DRAFTED,
        Status.NEEDS_EDIT,
        Status.RESUME_READY,
    }
)

_CLOSABLE = {Status.CLOSED_BY_EMPLOYER, Status.WITHDRAWN}

TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.NEW: frozenset({Status.NEEDS_MANUAL_JD, Status.SCORED} | _CLOSABLE),
    Status.NEEDS_MANUAL_JD: frozenset({Status.SCORED} | _CLOSABLE),
    Status.SCORED: frozenset({Status.BELOW_THRESHOLD, Status.RESUME_DRAFTED} | _CLOSABLE),
    Status.BELOW_THRESHOLD: frozenset({Status.SCORED} | _CLOSABLE),  # re-score
    Status.RESUME_DRAFTED: frozenset(
        {Status.RESUME_READY, Status.NEEDS_EDIT, Status.SCORED} | _CLOSABLE
    ),
    Status.NEEDS_EDIT: frozenset({Status.RESUME_DRAFTED, Status.SCORED} | _CLOSABLE),
    Status.RESUME_READY: frozenset(
        {Status.SUBMITTED, Status.RESUME_DRAFTED, Status.SCORED} | _CLOSABLE
    ),
    Status.SUBMITTED: frozenset({Status.INTERVIEWING, Status.REJECTED} | _CLOSABLE),
    Status.INTERVIEWING: frozenset({Status.OFFER, Status.REJECTED} | _CLOSABLE),
    Status.OFFER: frozenset({Status.ACCEPTED, Status.DECLINED}),
    **{s: frozenset() for s in TERMINAL},
}

StatusSource = Literal["pipeline", "user", "email", "import"]


class IllegalTransition(ValueError):
    def __init__(self, job_id: str, current: Status, target: Status):
        super().__init__(f"{job_id}: cannot move from '{current}' to '{target}'")
        self.job_id, self.current, self.target = job_id, current, target


def check_transition(job_id: str, current: Status, target: Status) -> None:
    """Raise IllegalTransition unless `current -> target` is allowed."""
    if target not in TRANSITIONS[current]:
        raise IllegalTransition(job_id, current, target)


def now() -> datetime:
    return datetime.now(UTC)


class FitResult(BaseModel):
    """Output of the fit-scoring step. Exactly three gaps, score 1-10."""

    score: Annotated[int, Field(ge=1, le=10)]
    top_gaps: Annotated[list[str], Field(min_length=3, max_length=3)]
    rationale: str


ScoringTier = Literal["tier1_alert_only", "full_jd"]


class Job(BaseModel):
    id: str
    company: str
    title: str
    url: str | None = None
    source: str | None = None
    location: str | None = None
    pay_range: str | None = None
    status: Status = Status.NEW
    jd_text: str | None = None
    fit: FitResult | None = None
    scoring_tier: ScoringTier | None = None
    resume_path: str | None = None
    resume_source_hash: str | None = None  # master-resume hash the tailored resume was built from
    notes: str | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class StatusChange(BaseModel):
    job_id: str
    from_status: Status | None
    to_status: Status
    source: StatusSource
    note: str | None = None
    at: datetime = Field(default_factory=now)


class NeedsHuman(BaseModel):
    """Returned by a step that cannot finish without a person.

    Core never decides *how* to wait. Each orchestration approach handles this its own
    way: LangGraph interrupts, a plain pipeline parks the job, Temporal waits on a signal.
    """

    kind: Literal["manual_jd", "resume_review"]
    job_id: str
    reason: str
    payload: dict = Field(default_factory=dict)
