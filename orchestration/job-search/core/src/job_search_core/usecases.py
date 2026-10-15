"""Use cases: record the outcome of a step in the tracker, applying business rules.

Orchestrator nodes should be thin: load state, call a step, call one of these, return.
"""

from __future__ import annotations

from . import policy
from .domain import FitResult, Job, Status
from .ports import DocumentStorePort, TrackerPort


class NotEvaluable(RuntimeError):
    pass


def begin_evaluation(tracker: TrackerPort, job_id: str) -> Job:
    job = tracker.get(job_id)
    if not policy.can_evaluate(job):
        raise NotEvaluable(f"{job_id} is '{job.status}' — already submitted or closed")
    return job


def record_needs_manual_jd(tracker: TrackerPort, job_id: str, reason: str) -> Job:
    job = tracker.get(job_id)
    if job.status != Status.NEEDS_MANUAL_JD:
        job = tracker.transition(job_id, Status.NEEDS_MANUAL_JD, "pipeline", reason)
    return job


def record_jd(tracker: TrackerPort, job_id: str, jd_text: str) -> Job:
    job = tracker.get(job_id)
    job.jd_text = jd_text
    return tracker.save(job)


def record_score(tracker: TrackerPort, job_id: str, fit: FitResult) -> Job:
    job = tracker.get(job_id)
    job.fit = fit
    job.scoring_tier = "full_jd"
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
    master_hash: str,
) -> Job:
    path = docs.save_resume(job_id, content)
    job = tracker.get(job_id)
    job.resume_path = path
    job.resume_source_hash = master_hash
    tracker.save(job)
    return tracker.transition(job_id, Status.RESUME_DRAFTED, "pipeline", path)


def record_review(
    tracker: TrackerPort, job_id: str, approved: bool, note: str | None = None
) -> Job:
    target = Status.RESUME_READY if approved else Status.NEEDS_EDIT
    return tracker.transition(job_id, target, "user", note)


def record_submission(tracker: TrackerPort, job_id: str, note: str | None = None) -> Job:
    return tracker.transition(job_id, Status.SUBMITTED, "user", note)
