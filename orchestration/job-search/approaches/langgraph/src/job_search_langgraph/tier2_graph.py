"""Tier 2 graph, shadow mode: B scores the jobs the plugin finished Tier 2 on, from its saved JD.

    START → plan ─(one Send per job due)→ assess ─→ record → END
                └──────(none due, or a dry run)──────↗

`plan` reads the plugin's Job Log, read-only, and picks the jobs with a plugin run B hasn't
mirrored yet (core.policy), then reads each one's saved `<ID>_JD.md`. `assess` is the only model
call: one per job, fanned out with `Send`. `record` is deterministic: the shared rubric's score,
then the job, its JD and the score in B's tracker under the plugin's ID, marked with the run it
mirrors.

Both approaches score the same JD, so comparing them measures judgment, not fetching. B never
writes the plugin's tracker or touches its Run Tier 2 checkbox. A job whose assessment fails is
reported and left unmarked, so the next run tries it again.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from job_search_core import policy, steps, usecases
from job_search_core.domain import EvidenceTable, FitAssessment, PluginJob
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .deps import Deps


class Tier2State(TypedDict, total=False):
    dry_run: bool  # input: report what would be scored, call no model, write nothing
    limit: int | None  # input: score at most this many jobs this run
    due: list[dict]  # {"row": PluginJob fields, "jd_text"}, to score this run
    waiting: list[dict]  # {"id", "reason"}: due, but not scored this run
    assessed: Annotated[list[dict], operator.add]  # {"id", "assessment"} or {"id", "error"}
    scored: list[dict]  # {"id", "company", "title", "score", "plugin_score", "run", "rescore"}
    failed: list[dict]  # {"id", "error"}


def build_tier2_graph(deps: Deps, checkpointer=None):
    if deps.plugin_jobs is None or deps.job_files is None:
        raise ValueError("Tier 2 shadow mode needs deps.plugin_jobs and deps.job_files")

    def previous_evidence(job_id: str, jd_text: str) -> EvidenceTable | None:
        try:
            return policy.rescore_basis(deps.tracker.get(job_id), jd_text)
        except KeyError:
            return None  # not mirrored before

    def plan(state: Tier2State) -> Tier2State:
        mirrored = {job.id: job.plugin_run for job in deps.tracker.list()}
        limit = state.get("limit")
        due, waiting = [], []
        for row in deps.plugin_jobs.jobs():
            if not policy.shadow_tier2_due(row, mirrored.get(row.id)):
                continue
            jd_text = deps.job_files.saved_jd(row.id)
            if jd_text is None:
                waiting.append(
                    {"id": row.id, "reason": f"{row.id}_JD.md isn't in the synced job folder"}
                )
            elif limit is not None and len(due) >= limit:
                waiting.append({"id": row.id, "reason": "over this run's limit"})
            else:
                due.append({"row": row.model_dump(), "jd_text": jd_text})
        return {"due": due, "waiting": waiting}

    def route_jobs(state: Tier2State):
        if state.get("dry_run"):
            return "record"
        return [Send("assess", item) for item in state["due"]] or "record"

    def assess(item: dict) -> Tier2State:
        job_id = item["row"]["id"]
        try:
            assessment = steps.assess_fit(
                item["jd_text"],
                deps.resume.read(),
                deps.profile.read(),
                deps.llm,
                previous=previous_evidence(job_id, item["jd_text"]),
            )
        except Exception as exc:  # one job's failure leaves the others to be recorded
            return {"assessed": [{"id": job_id, "error": f"{type(exc).__name__}: {exc}"}]}
        return {"assessed": [{"id": job_id, "assessment": assessment.model_dump()}]}

    def record(state: Tier2State) -> Tier2State:
        if state.get("dry_run"):
            return {"scored": [], "failed": []}
        assessed = {a["id"]: a for a in state.get("assessed", [])}
        scored, failed = [], []
        for item in state["due"]:  # the plugin's order, whatever order the calls finished in
            row, jd_text = PluginJob.model_validate(item["row"]), item["jd_text"]
            result = assessed[row.id]
            if "error" in result:
                failed.append({"id": row.id, "error": result["error"]})
                continue
            previous = previous_evidence(row.id, jd_text)  # read before the JD is recorded
            fit = steps.compute_fit(FitAssessment(**result["assessment"]), previous=previous)
            usecases.record_shadow_job(deps.tracker, row, jd_text)
            usecases.record_score(
                deps.tracker, row.id, fit, row.scoring_tier, plugin_run=row.fit_run
            )
            scored.append(
                {
                    "id": row.id,
                    "company": row.company,
                    "title": row.title,
                    "score": fit.score,
                    "plugin_score": row.score,
                    "run": row.fit_run,
                    "rescore": previous is not None,
                }
            )
        return {"scored": scored, "failed": failed}

    builder = StateGraph(Tier2State)
    builder.add_node("plan", plan)
    builder.add_node("assess", assess)
    builder.add_node("record", record)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", route_jobs, ["assess", "record"])
    builder.add_edge("assess", "record")
    builder.add_edge("record", END)
    return builder.compile(checkpointer=checkpointer)
