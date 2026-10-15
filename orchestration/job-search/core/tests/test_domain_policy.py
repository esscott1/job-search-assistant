import pytest
from job_search_core import policy
from job_search_core.domain import (
    TERMINAL,
    TRANSITIONS,
    FitResult,
    IllegalTransition,
    Job,
    Status,
    check_transition,
)
from pydantic import ValidationError


def fit(score: int) -> FitResult:
    return FitResult(score=score, top_gaps=["a", "b", "c"], rationale="r")


def test_every_status_has_a_transition_entry():
    assert set(TRANSITIONS) == set(Status)


def test_terminal_statuses_go_nowhere():
    for s in TERMINAL:
        assert TRANSITIONS[s] == frozenset()


@pytest.mark.parametrize(
    "current,target",
    [
        (Status.BELOW_THRESHOLD, Status.SUBMITTED),  # can't submit an untailored job
        (Status.NEW, Status.RESUME_READY),
        (Status.REJECTED, Status.INTERVIEWING),
        (Status.SUBMITTED, Status.SCORED),  # never re-score after submission
    ],
)
def test_illegal_transitions_raise(current, target):
    with pytest.raises(IllegalTransition):
        check_transition("JS-1", current, target)


def test_fit_result_requires_exactly_three_gaps_and_score_in_range():
    with pytest.raises(ValidationError):
        FitResult(score=8, top_gaps=["a", "b"], rationale="r")
    with pytest.raises(ValidationError):
        FitResult(score=11, top_gaps=["a", "b", "c"], rationale="r")


@pytest.mark.parametrize("score,expected", [(6, False), (7, True), (10, True)])
def test_threshold(score, expected):
    assert policy.should_tailor(fit(score)) is expected


def test_status_after_scoring():
    assert policy.status_after_scoring(fit(9)) == Status.RESUME_DRAFTED
    assert policy.status_after_scoring(fit(4)) == Status.BELOW_THRESHOLD


def test_cannot_evaluate_after_submission():
    assert policy.can_evaluate(Job(id="1", company="c", title="t", status=Status.RESUME_READY))
    assert not policy.can_evaluate(Job(id="1", company="c", title="t", status=Status.SUBMITTED))


def test_resume_staleness_only_before_submission():
    job = Job(id="1", company="c", title="t", status=Status.RESUME_READY, resume_source_hash="old")
    assert policy.is_resume_stale(job, "new")
    assert not policy.is_resume_stale(job, "old")
    job.status = Status.SUBMITTED
    assert not policy.is_resume_stale(job, "new")
