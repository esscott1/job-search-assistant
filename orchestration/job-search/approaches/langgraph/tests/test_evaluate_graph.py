"""Graph tests: routing, interrupts and resume — all with fakes, no network or API key."""

import pytest
from job_search_core.adapters.fakes import (
    FakeJDFetcher,
    FakeLLM,
    InMemoryDocumentStore,
    InMemoryResumeSource,
)
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.domain import Job, Status
from job_search_langgraph.deps import Deps
from job_search_langgraph.evaluate_graph import (
    build_evaluate_graph,
    fresh_input,
    pending_interrupt,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

STRONG = "Enterprise architect, AI enablement, cloud platforms. " * 15
WEAK = "Retail associate, cashier, stocking. " * 20


@pytest.fixture
def env():
    tracker = SqliteTracker(":memory:")
    tracker.add(Job(id="J1", company="Acme", title="Architect", url="https://acme.example/1"))
    tracker.add(Job(id="J2", company="Shop", title="Associate", url="https://shop.example/2"))
    tracker.add(
        Job(id="J3", company="Initech", title="Architect", url="https://linkedin.com/jobs/view/3")
    )
    fetcher = FakeJDFetcher({"J1": STRONG, "J2": WEAK})
    llm = FakeLLM(lambda jd: 3 if "Retail" in jd else 8)
    docs = InMemoryDocumentStore()
    deps = Deps(tracker, fetcher, llm, InMemoryResumeSource(), docs)
    graph = build_evaluate_graph(deps, checkpointer=InMemorySaver())
    return graph, deps


def run(graph, job_id, payload):
    return graph.invoke(payload, {"configurable": {"thread_id": job_id}})


def test_strong_fit_pauses_for_review_then_becomes_ready(env):
    graph, deps = env
    run(graph, "J1", fresh_input("J1"))
    assert deps.tracker.get("J1").status == Status.RESUME_DRAFTED
    assert pending_interrupt(graph, "J1")["kind"] == "resume_review"
    assert "J1" in deps.docs.saved

    run(graph, "J1", Command(resume={"approved": True}))
    assert deps.tracker.get("J1").status == Status.RESUME_READY
    assert pending_interrupt(graph, "J1") is None


def test_rejected_review_marks_needs_edit(env):
    graph, deps = env
    run(graph, "J1", fresh_input("J1"))
    run(graph, "J1", Command(resume={"approved": False, "note": "too long"}))
    assert deps.tracker.get("J1").status == Status.NEEDS_EDIT
    assert deps.tracker.history("J1")[-1].source == "user"


def test_weak_fit_ends_below_threshold_without_tailoring(env):
    graph, deps = env
    result = run(graph, "J2", fresh_input("J2"))
    assert result["outcome"] == Status.BELOW_THRESHOLD.value
    assert "J2" not in deps.docs.saved
    assert deps.llm.calls == ["structured"]  # scored, never tailored


def test_missing_jd_pauses_and_resumes_without_refetching(env):
    graph, deps = env
    run(graph, "J3", fresh_input("J3"))
    assert deps.tracker.get("J3").status == Status.NEEDS_MANUAL_JD
    assert pending_interrupt(graph, "J3")["kind"] == "manual_jd"
    fetches_before = len(deps.jd_fetcher.calls)

    run(graph, "J3", Command(resume=STRONG))
    assert len(deps.jd_fetcher.calls) == fetches_before  # resume did not re-run the fetch
    assert deps.tracker.get("J3").jd_text == STRONG
    assert pending_interrupt(graph, "J3")["kind"] == "resume_review"


def test_too_short_manual_jd_asks_again(env):
    graph, deps = env
    run(graph, "J3", fresh_input("J3"))
    run(graph, "J3", Command(resume="see attached"))
    waiting = pending_interrupt(graph, "J3")
    assert waiting["kind"] == "manual_jd" and "too short" in waiting["reason"]
    assert deps.tracker.get("J3").status == Status.NEEDS_MANUAL_JD


def test_submitted_job_cannot_be_reevaluated(env):
    graph, deps = env
    run(graph, "J1", fresh_input("J1"))
    run(graph, "J1", Command(resume={"approved": True}))
    deps.tracker.transition("J1", Status.SUBMITTED, "user")
    with pytest.raises(Exception, match="already submitted"):
        run(graph, "J1", fresh_input("J1"))
