"""Use cases: record the outcome of a step in the tracker, applying business rules.

Orchestrator nodes should be thin: load state, call a step, call one of these, return.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from . import policy
from .domain import DuplicateJobId, FitResult, Job, LeadCard, ScoringTier, Status
from .ports import DocumentStorePort, MailMessage, TrackerPort


class NotEvaluable(RuntimeError):
    pass


def add_new_job(
    tracker: TrackerPort, make_job: Callable[[str], Job], prefix: str = "LG", attempts: int = 3
) -> Job:
    """Add a job under the next free ID, trying again if another writer takes that ID first."""
    for _ in range(attempts):
        job = make_job(tracker.next_id(prefix))
        try:
            return tracker.add(job)
        except DuplicateJobId:
            continue
    raise DuplicateJobId(job.id)


def record_lead(
    tracker: TrackerPort,
    card: LeadCard,
    fit: FitResult,
    *,
    canonical_url: str,
    source: str,
    message: MailMessage,
    today: date,
    prefix: str = "LG",
) -> Job:
    """Add a lead from an alert email as a new Tier 1 job, under the next free ID.

    The link stored is the canonical one only: the email's own link can carry a sign-in token.
    """

    def make_job(job_id: str) -> Job:
        return Job(
            id=job_id,
            company=card.company,
            title=card.title,
            url=canonical_url or None,
            source=source,
            location=card.location or None,
            pay_range=card.pay_range or None,
            fit=fit,
            scoring_tier="T1",
            canonical_url=canonical_url,
            found_on=today,
            gmail_message_id=message.id,
            email_received=message.received_at.date(),
        )

    return add_new_job(tracker, make_job, prefix)


def begin_evaluation(tracker: TrackerPort, job_id: str) -> Job:
    job = tracker.get(job_id)
    if not policy.can_evaluate(job):
        raise NotEvaluable(f"{job_id} is '{job.status}' — already submitted or closed")
    return job


def record_needs_manual_jd(tracker: TrackerPort, job_id: str, reason: str) -> Job:
    job = tracker.get(job_id)
    if job.status != Status.NEEDS_MANUAL_JD:
        job = tracker.transition(job_id, Status.NEEDS_MANUAL_JD, "pipeline", reason)
    if job.scoring_tier != "T2-pending-manual":
        job.scoring_tier = "T2-pending-manual"
        job = tracker.save(job)
    return job


def record_jd(tracker: TrackerPort, job_id: str, jd_text: str) -> Job:
    job = tracker.get(job_id)
    job.jd_text = jd_text
    return tracker.save(job)


def record_score(
    tracker: TrackerPort, job_id: str, fit: FitResult, tier: ScoringTier = "T2"
) -> Job:
    """Record a rubric score. `tier` says where the JD came from: T2 fetched, T2-manual pasted."""
    job = tracker.get(job_id)
    job.fit = fit
    job.scoring_tier = tier
    tracker.save(job)
    if job.status != Status.SCORED:  # idempotent on re-run after a crash
        job = tracker.transition(job_id, Status.SCORED, "pipeline", f"fit {fit.score}/10")
    return job


def record_below_threshold(tracker: TrackerPort, job_id: str) -> Job:
    return tracker.transition(
        job_id, Status.BELOW_THRESHOLD, "pipeline", f"below threshold {policy.FIT_THRESHOLD}"
    )


def record_tailored_resume(
    tracker: TrackerPort,
    docs: DocumentStorePort,
    job_id: str,
    content: str,
    resume_hash: str,
) -> Job:
    path = docs.save_resume(job_id, content)
    job = tracker.get(job_id)
    job.resume_path = path
    job.resume_source_hash = resume_hash
    tracker.save(job)
    return tracker.transition(job_id, Status.RESUME_DRAFTED, "pipeline", path)


def record_review(
    tracker: TrackerPort, job_id: str, approved: bool, note: str | None = None
) -> Job:
    target = Status.RESUME_READY if approved else Status.NEEDS_EDIT
    return tracker.transition(job_id, target, "user", note)


def record_submission(tracker: TrackerPort, job_id: str, note: str | None = None) -> Job:
    return tracker.transition(job_id, Status.SUBMITTED, "user", note)
