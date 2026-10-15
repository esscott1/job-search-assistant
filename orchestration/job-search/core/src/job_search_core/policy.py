"""Business rules. Orchestrators ask these questions; they never re-implement the answers.

If a routing decision lives in a graph edge instead of here, a second orchestration
approach cannot reuse it — keep the rule here and let the edge call it.
"""

from __future__ import annotations

from .domain import PRE_SUBMISSION, FitResult, Job, Status

FIT_THRESHOLD = 7
"""Jobs scoring at or above this get a tailored resume."""

MIN_JD_CHARS = 400
"""Fetched text shorter than this is treated as 'no real job description found'."""


def should_tailor(fit: FitResult) -> bool:
    return fit.score >= FIT_THRESHOLD


def status_after_scoring(fit: FitResult) -> Status:
    return Status.RESUME_DRAFTED if should_tailor(fit) else Status.BELOW_THRESHOLD


def can_evaluate(job: Job) -> bool:
    """A job can be (re-)evaluated only before its resume has gone to the employer."""
    return job.status in PRE_SUBMISSION


def is_resume_stale(job: Job, current_master_hash: str) -> bool:
    """True when a tailored, not-yet-submitted resume was built from an older master resume."""
    return (
        job.status in {Status.RESUME_DRAFTED, Status.NEEDS_EDIT, Status.RESUME_READY}
        and job.resume_source_hash is not None
        and job.resume_source_hash != current_master_hash
    )


def looks_like_real_jd(text: str | None) -> bool:
    return bool(text) and len(text.strip()) >= MIN_JD_CHARS
