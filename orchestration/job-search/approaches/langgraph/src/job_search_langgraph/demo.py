"""`jobs demo`: run the evaluate graph's three paths with fakes. No API keys, no network."""

from __future__ import annotations

from job_search_core.adapters.fakes import (
    FakeJDFetcher,
    FakeLLM,
    InMemoryDocumentStore,
    InMemoryResumeSource,
)
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.domain import Job
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .deps import Deps
from .evaluate_graph import build_evaluate_graph, fresh_input, pending_interrupt

STRONG = "Enterprise architect leading AI enablement and platform strategy. " * 12
WEAK = "Retail store associate: stocking shelves and cashier duties. " * 12


def run_demo() -> None:
    tracker = SqliteTracker(":memory:")
    for job in [
        Job(
            id="DEMO-1",
            company="Acme",
            title="AI Enablement Architect",
            url="https://acme.example/1",
        ),
        Job(id="DEMO-2", company="ShopCo", title="Store Associate", url="https://shop.example/2"),
        Job(
            id="DEMO-3",
            company="Initech",
            title="Solutions Architect",
            url="https://www.linkedin.com/jobs/view/1/",
        ),
    ]:
        tracker.add(job)

    deps = Deps(
        tracker=tracker,
        jd_fetcher=FakeJDFetcher({"DEMO-1": STRONG, "DEMO-2": WEAK}),
        llm=FakeLLM(lambda jd: 3 if "Retail" in jd else 8),
        resume=InMemoryResumeSource(),
        docs=InMemoryDocumentStore(),
    )
    graph = build_evaluate_graph(deps, checkpointer=InMemorySaver())

    def run(job_id, payload):
        graph.invoke(payload, {"configurable": {"thread_id": job_id}})
        waiting = pending_interrupt(graph, job_id)
        status = tracker.get(job_id).status.value
        print(f"  {job_id}: {status}" + (f"  (paused: {waiting['kind']})" if waiting else ""))

    print("1) Strong fit → tailored → paused for your review → approved")
    run("DEMO-1", fresh_input("DEMO-1"))
    run("DEMO-1", Command(resume={"approved": True}))

    print("2) Weak fit → below threshold, no resume generated")
    run("DEMO-2", fresh_input("DEMO-2"))

    print("3) LinkedIn posting → paused for a manual JD → you paste it → scored and tailored")
    run("DEMO-3", fresh_input("DEMO-3"))
    run("DEMO-3", Command(resume=STRONG))
    run("DEMO-3", Command(resume={"approved": False, "note": "tighten the summary"}))

    print("\nStatus history for DEMO-3:")
    for h in tracker.history("DEMO-3"):
        print(f"  {h.from_status or '-':>16} → {h.to_status:<16} ({h.source}) {h.note or ''}")
