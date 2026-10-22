import pytest
from job_search_core import steps, usecases
from job_search_core.adapters.fakes import (
    FakeJDFetcher,
    FakeLLM,
    InMemoryDocumentStore,
    InMemoryProfileSource,
    InMemoryResumeSource,
)
from job_search_core.adapters.http_jd_fetcher import HttpJDFetcher, html_to_text
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.domain import (
    DuplicateJobId,
    FitResult,
    IllegalTransition,
    Job,
    NeedsHuman,
    Status,
)

LONG_JD = "Enterprise architect role. " * 40


@pytest.fixture
def tracker():
    t = SqliteTracker(":memory:")
    t.add(
        Job(id="JS-1", company="Acme", title="Enterprise Architect", url="https://acme.example/1")
    )
    return t


def test_transition_records_history_with_source(tracker):
    tracker.transition("JS-1", Status.SCORED, "pipeline", "fit 8/10")
    hist = tracker.history("JS-1")
    assert [(h.from_status, h.to_status, h.source) for h in hist] == [
        (None, Status.NEW, "pipeline"),
        (Status.NEW, Status.SCORED, "pipeline"),
    ]


def test_tracker_rejects_illegal_transition(tracker):
    with pytest.raises(IllegalTransition):
        tracker.transition("JS-1", Status.SUBMITTED, "user")


def test_save_cannot_sneak_a_status_change(tracker):
    job = tracker.get("JS-1")
    job.status = Status.SUBMITTED
    with pytest.raises(ValueError):
        tracker.save(job)


def test_record_score_is_idempotent(tracker):
    fit = FitResult(score=8, top_gaps=["a", "b", "c"], rationale="r")
    usecases.record_score(tracker, "JS-1", fit)
    usecases.record_score(tracker, "JS-1", fit)  # re-run after a crash must not raise
    assert tracker.get("JS-1").status == Status.SCORED


def test_full_happy_path_through_usecases(tracker):
    llm, docs, resume = FakeLLM(), InMemoryDocumentStore(), InMemoryResumeSource()
    job = usecases.begin_evaluation(tracker, "JS-1")
    jd = steps.fetch_jd(job, FakeJDFetcher({"JS-1": LONG_JD}))
    usecases.record_jd(tracker, "JS-1", jd)
    assessment = steps.assess_fit(jd, resume.read(), InMemoryProfileSource().read(), llm)
    fit = steps.compute_fit(assessment)
    usecases.record_score(tracker, "JS-1", fit)
    content = steps.tailor_resume(jd, resume.read(), fit, llm)
    usecases.record_tailored_resume(tracker, docs, "JS-1", content, resume.content_hash())
    usecases.record_review(tracker, "JS-1", approved=True)
    usecases.record_submission(tracker, "JS-1")
    final = tracker.get("JS-1")
    assert final.status == Status.SUBMITTED
    assert final.resume_source_hash == resume.content_hash()
    with pytest.raises(usecases.NotEvaluable):
        usecases.begin_evaluation(tracker, "JS-1")


def test_short_page_is_not_treated_as_a_jd(tracker):
    result = steps.fetch_jd(tracker.get("JS-1"), FakeJDFetcher({"JS-1": "Sign in to continue"}))
    assert isinstance(result, NeedsHuman) and result.kind == "manual_jd"


def test_linkedin_is_never_fetched():
    job = Job(id="JS-2", company="c", title="t", url="https://www.linkedin.com/jobs/view/123/")
    result = HttpJDFetcher().fetch(job)
    assert isinstance(result, NeedsHuman)
    assert "linkedin.com" in result.reason


def test_html_to_text_drops_scripts():
    assert html_to_text("<p>Hello</p><script>evil()</script><p>World</p>") == "Hello\nWorld"


def test_next_id_follows_the_highest_number_not_the_row_count():
    tracker = SqliteTracker()
    tracker.add(Job(id="LG-0007", company="Acme", title="PM"))  # added by hand with --id
    tracker.add(Job(id="JS-042", company="Acme", title="PM"))  # another prefix doesn't count
    assert tracker.next_id("LG") == "LG-0008"
    assert tracker.next_id("XX") == "XX-0001"


def test_adding_a_taken_id_is_a_clear_error():
    tracker = SqliteTracker()
    tracker.add(Job(id="LG-0001", company="Acme", title="PM"))
    with pytest.raises(DuplicateJobId, match="LG-0001"):
        tracker.add(Job(id="LG-0001", company="Other", title="PM"))


def test_add_new_job_retries_when_another_writer_takes_the_id():
    tracker = SqliteTracker()
    real_next_id = tracker.next_id

    def raced(prefix):
        if not tracker.list():  # another process adds LG-0001 between next_id and add
            tracker.add(Job(id="LG-0001", company="Other", title="PM"))
            return "LG-0001"
        return real_next_id(prefix)

    tracker.next_id = raced
    job = usecases.add_new_job(tracker, lambda job_id: Job(id=job_id, company="Acme", title="PM"))
    assert job.id == "LG-0002"
    assert tracker.get("LG-0002").company == "Acme"
