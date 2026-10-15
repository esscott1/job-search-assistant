"""Evaluate graph: one job in, a scored (and possibly tailored + reviewed) job out.

    START → load → fetch_jd ─(got JD)──────────────→ score ─(policy.should_tailor)→ tailor → review → END
                       └─(NeedsHuman)→ manual_jd ──↗        └──────────────────────→ below → END

Each node is thin: call a core step, record the result through a core use case, return a
small state update. Routing asks core.policy — no business rule lives in this file.

Human-in-the-loop uses `interrupt()`. The graph pauses, its state is checkpointed under
thread_id = job_id, and it resumes when the CLI sends `Command(resume=...)`. Interrupt
nodes contain no other side effects before the interrupt, because LangGraph re-runs the
whole node on resume.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from job_search_core import policy, steps, usecases
from job_search_core.domain import FitResult, NeedsHuman
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .deps import Deps


class EvalState(TypedDict, total=False):
    job_id: str
    jd_text: str | None
    needs_human: dict | None  # NeedsHuman payload when the JD couldn't be fetched
    fit: dict | None  # FitResult as a plain dict (keeps checkpoints JSON-friendly)
    resume_path: str | None
    outcome: str | None  # final status, for the caller


def build_evaluate_graph(deps: Deps, checkpointer=None):
    def load(state: EvalState) -> EvalState:
        job = usecases.begin_evaluation(deps.tracker, state["job_id"])
        return {"jd_text": job.jd_text, "needs_human": None}

    def fetch_jd(state: EvalState) -> EvalState:
        job = deps.tracker.get(state["job_id"])
        result = steps.fetch_jd(job, deps.jd_fetcher)
        if isinstance(result, NeedsHuman):
            usecases.record_needs_manual_jd(deps.tracker, job.id, result.reason)
            return {"needs_human": result.model_dump()}
        usecases.record_jd(deps.tracker, job.id, result)
        return {"jd_text": result, "needs_human": None}

    def manual_jd(state: EvalState) -> EvalState:
        ask = dict(state["needs_human"])
        text = interrupt(ask)
        while not policy.looks_like_real_jd(text):
            text = interrupt({**ask, "reason": "That text is too short to be a job description"})
        usecases.record_jd(deps.tracker, state["job_id"], text)
        return {"jd_text": text, "needs_human": None}

    def score(state: EvalState) -> EvalState:
        fit = steps.score_fit(state["jd_text"], deps.resume.read(), deps.llm)
        usecases.record_score(deps.tracker, state["job_id"], fit)
        return {"fit": fit.model_dump()}

    def below(state: EvalState) -> EvalState:
        job = usecases.record_below_threshold(deps.tracker, state["job_id"])
        return {"outcome": job.status.value}

    def tailor(state: EvalState) -> EvalState:
        fit = FitResult(**state["fit"])
        content = steps.tailor_resume(state["jd_text"], deps.resume.read(), fit, deps.llm)
        job = usecases.record_tailored_resume(
            deps.tracker, deps.docs, state["job_id"], content, deps.resume.content_hash()
        )
        return {"resume_path": job.resume_path}

    def review(state: EvalState) -> EvalState:
        decision = interrupt(
            {
                "kind": "resume_review",
                "job_id": state["job_id"],
                "resume_path": state["resume_path"],
                "fit": state["fit"],
            }
        )
        job = usecases.record_review(
            deps.tracker, state["job_id"], bool(decision.get("approved")), decision.get("note")
        )
        return {"outcome": job.status.value}

    def after_fetch(state: EvalState) -> Literal["manual_jd", "score"]:
        return "manual_jd" if state.get("needs_human") else "score"

    def after_score(state: EvalState) -> Literal["tailor", "below"]:
        return "tailor" if policy.should_tailor(FitResult(**state["fit"])) else "below"

    g = StateGraph(EvalState)
    for name, fn in [
        ("load", load),
        ("fetch_jd", fetch_jd),
        ("manual_jd", manual_jd),
        ("score", score),
        ("below", below),
        ("tailor", tailor),
        ("review", review),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "load")
    g.add_edge("load", "fetch_jd")
    g.add_conditional_edges("fetch_jd", after_fetch)
    g.add_edge("manual_jd", "score")
    g.add_conditional_edges("score", after_score)
    g.add_edge("below", END)
    g.add_edge("tailor", "review")
    g.add_edge("review", END)
    return g.compile(checkpointer=checkpointer)


def fresh_input(job_id: str) -> EvalState:
    """Input for a new evaluation run; clears anything left from a previous run on the thread."""
    return {
        "job_id": job_id,
        "jd_text": None,
        "needs_human": None,
        "fit": None,
        "resume_path": None,
        "outcome": None,
    }


def pending_interrupt(graph, job_id: str) -> dict | None:
    """The payload the graph is waiting on for this job, if it is paused."""
    snapshot = graph.get_state({"configurable": {"thread_id": job_id}})
    for task in snapshot.tasks:
        for intr in getattr(task, "interrupts", ()) or ():
            return intr.value
    return None
