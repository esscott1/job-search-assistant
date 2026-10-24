"""Domain model: jobs, fit results, statuses and the legal transitions between them."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


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
# or re-tailored (for example after the full resume changes).
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


class DuplicateJobId(ValueError):
    def __init__(self, job_id: str):
        super().__init__(f"{job_id} is already in the tracker")
        self.job_id = job_id


def check_transition(job_id: str, current: Status, target: Status) -> None:
    """Raise IllegalTransition unless `current -> target` is allowed."""
    if target not in TRANSITIONS[current]:
        raise IllegalTransition(job_id, current, target)


def now() -> datetime:
    return datetime.now(UTC)


# The rubric's categories for title fit and work arrangement (job-fit-rubric); the Tier 1 and
# Tier 2 judgments both use them, and test_rubric.py checks they match the rubric's tables.
TitleSeniority = Literal["strong", "partial", "weak"]
WorkArrangement = Literal[
    "remote",
    "commutable_onsite",
    "commutable_hybrid",
    "unknown",
    "relocation_acceptable",
    "relocation_required",
]


class Requirement(BaseModel):
    """One qualification from the JD, judged against the full resume."""

    text: Annotated[str, Field(min_length=1)]  # quoted from the JD
    type: Literal["required", "preferred"]
    evidence: Literal["strong", "partial", "none"]
    resume_evidence: str = ""


class EvidenceTable(BaseModel):
    """What the model judges; `scoring.score_evidence` turns it into a score.

    The Literal values mirror the rubric's credit tables; test_rubric.py checks they agree.
    """

    mode: Literal["tier1", "tier2"]
    title_seniority: TitleSeniority
    work_arrangement: WorkArrangement
    requirements: list[Requirement] = []


class RubricScore(BaseModel):
    """The rubric's output: the final score, the raw score, caps and a readable breakdown."""

    score: Annotated[int, Field(ge=1, le=10)]
    raw: float
    caps_applied: list[str]
    breakdown: str
    rubric_version: str


class FitAssessment(BaseModel):
    """What the model returns after reading a JD: judgments only, never a score.

    There is no score field, so the model can't express one; `steps.compute_fit` builds
    the evidence table from this and the rubric computes the score.
    """

    title_seniority: TitleSeniority
    work_arrangement: WorkArrangement
    requirements: Annotated[list[Requirement], Field(min_length=1)]
    top_gaps: Annotated[list[str], Field(max_length=3)]  # Gaps-cell phrases, biggest first
    rationale: str


class FitResult(BaseModel):
    """The recorded result of scoring a job: the rubric's score plus what produced it.

    `score` always comes from the rubric (`steps.compute_fit`), never from the model. The
    fields after `rationale` default to empty so rows saved before they existed still load.
    """

    score: Annotated[int, Field(ge=1, le=10)]
    top_gaps: Annotated[list[str], Field(max_length=3)]
    rationale: str
    breakdown: str = ""  # the rubric's breakdown line
    rubric_version: str | None = None
    prompt_version: str | None = None
    evidence: EvidenceTable | None = None  # kept so a rescore can reuse the requirement list


class LeadCard(BaseModel):
    """One job in an alert or recruiter email, as the model reads it: what the email says, plus
    the Tier 1 judgments (title fit and work arrangement) the rubric scores. Never a score."""

    company: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    location: str = ""
    posting_url: str = ""  # the job's link exactly as the email gives it; code canonicalises it
    pay_range: str = ""
    title_seniority: TitleSeniority
    work_arrangement: WorkArrangement
    keep: bool  # false only when clearly off-target or in the profile's Never interested list
    skip_reason: str = ""  # why, when keep is false


class EmailLeads(BaseModel):
    """The model's answer for one email: every job it offers, or none."""

    leads: list[LeadCard]


class KnownJob(BaseModel):
    """A job intake must not log again: a tracker row, or (with the Sheet) an archived one."""

    id: str
    company: str
    title: str
    canonical_url: str = ""


# The tracker's Score Tier values (skills/job-search-assistant/job-tracker/SKILL.md). The
# pipeline sets T2, T2-manual and T2-pending-manual; the others belong to stages it doesn't
# have yet (intake, a status sweep) but keep the vocabulary complete.
ScoringTier = Literal["T1", "T2", "T2-manual", "T2-pending-manual", "T2-no-jd", "T2-closed"]
_LEGACY_TIERS = {"full_jd": "T2", "tier1_alert_only": "T1"}


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
    resume_source_hash: str | None = None  # full-resume hash the tailored resume was built from
    notes: str | None = None
    # Intake fields, as the Sheet's Job Log has them (job-tracker). Optional, so older rows load.
    canonical_url: str = ""  # the dedup key, from canonical_url.canonical(); "" if none
    found_on: date | None = None
    gmail_message_id: str | None = None
    email_received: date | None = None
    plugin_run: int | None = None  # shadow mode: the plugin's fit-report run this score mirrors
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    @field_validator("scoring_tier", mode="before")
    @classmethod
    def _read_legacy_tier(cls, value: object) -> object:
        """Rows saved before the tracker's tier names were adopted still load."""
        return _LEGACY_TIERS.get(value, value) if isinstance(value, str) else value


class PluginJob(BaseModel):
    """A row of the plugin's Job Log, as shadow mode reads it. B never writes the plugin's tracker.

    `fit_run` is n in the Fit Report cell (`r<n>: <score>`): every Tier 2 run the plugin finishes
    with a score writes a new fit report, so it says which run the row's score came from.
    """

    id: str
    company: str
    title: str
    source: str = ""
    location: str = ""
    pay_range: str = ""
    canonical_url: str = ""
    score: int | None = None  # the plugin's Fit Score
    scoring_tier: str = ""  # the plugin's Score Tier, as written
    fit_run: int | None = None


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
