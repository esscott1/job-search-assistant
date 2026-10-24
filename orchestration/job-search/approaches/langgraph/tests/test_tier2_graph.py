"""The Tier 2 shadow graph end to end on fakes: B mirrors the plugin's finished Tier 2 runs from
the plugin's saved JDs, on SQLite and on its Sheets shadow, and never writes the plugin's tracker."""

from job_search_core.adapters.fakes import (
    STRONG_FIT,
    WEAK_FIT,
    FakeJDFetcher,
    FakeLLM,
    FakeSheets,
    InMemoryDocumentStore,
    InMemoryJobFiles,
    InMemoryPluginJobs,
    InMemoryProfileSource,
    InMemoryResumeSource,
)
from job_search_core.adapters.google_sheets import (
    JOB_LOG,
    SheetsPluginJobs,
    SheetsTracker,
    create_shadow,
)
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.domain import FitAssessment, PluginJob, Requirement
from job_search_langgraph.deps import Deps
from job_search_langgraph.tier2_graph import build_tier2_graph

GLOBEX_JD = "# JS-003 Globex: Lead Architect\nSource: https://jobs.example.com/1\n\nGLOBEX duties."
INITECH_JD = "# JS-002 Initech: Principal Architect\n\nINITECH qualifications."


def plugin_rows(globex_run=1):
    return [
        PluginJob(id="JS-003", company="Globex", title="Lead Architect", score=9,
                  scoring_tier="T2", fit_run=globex_run),
        PluginJob(id="JS-002", company="Initech", title="Principal Architect", score=3,
                  scoring_tier="T2-manual", fit_run=1),
        PluginJob(id="JS-001", company="Acme", title="Architect", score=6, scoring_tier="T1"),
    ]  # fmt: skip


def by_jd(jd: str) -> FitAssessment:
    if "BROKEN" in jd:
        raise RuntimeError("model returned nothing usable")
    return WEAK_FIT if "INITECH" in jd else STRONG_FIT


def make_deps(rows=None, jds=None, tracker=None, assessment_for=by_jd):
    llm = FakeLLM(assessment_for=assessment_for)
    deps = Deps(
        tracker=tracker or SqliteTracker(),
        jd_fetcher=FakeJDFetcher(),
        llm=llm,
        resume=InMemoryResumeSource(),
        docs=InMemoryDocumentStore(),
        profile=InMemoryProfileSource(),
        plugin_jobs=InMemoryPluginJobs(plugin_rows() if rows is None else rows),
        job_files=InMemoryJobFiles(
            {"JS-003": GLOBEX_JD, "JS-002": INITECH_JD} if jds is None else jds
        ),
    )
    return deps, llm


def run(deps, **inputs):
    return build_tier2_graph(deps).invoke(inputs)


def test_scores_each_finished_plugin_run_from_its_saved_jd_under_the_plugins_id():
    deps, llm = make_deps()
    result = run(deps)
    assert [(s["id"], s["score"], s["plugin_score"], s["rescore"]) for s in result["scored"]] == [
        ("JS-003", 10, 9, False),
        ("JS-002", 3, 3, False),
    ]
    assert llm.calls == ["structured", "structured"]  # nothing for the Tier 1 row
    globex = deps.tracker.get("JS-003")
    assert (globex.scoring_tier, globex.plugin_run, globex.jd_text) == ("T2", 1, GLOBEX_JD)
    assert deps.tracker.get("JS-002").scoring_tier == "T2-manual"  # the JD's origin carries over


def test_running_again_scores_nothing_until_the_plugin_rescores():
    deps, llm = make_deps()
    run(deps)
    assert run(deps)["scored"] == [] and len(llm.calls) == 2
    deps.plugin_jobs = InMemoryPluginJobs(plugin_rows(globex_run=2))
    again = run(deps)
    assert [(s["id"], s["run"], s["rescore"]) for s in again["scored"]] == [("JS-003", 2, True)]
    assert deps.tracker.get("JS-003").plugin_run == 2


def test_a_rescore_judges_the_same_requirements_again():
    deps, _ = make_deps()
    run(deps)
    first = deps.tracker.get("JS-003").fit.evidence.requirements
    reworded = STRONG_FIT.model_copy(
        update={"requirements": [Requirement(text=f"reworded {i}", type="required",
                                             evidence="partial") for i in range(len(first))]}
    )  # fmt: skip
    deps.llm.assessment_for = lambda jd: reworded
    deps.plugin_jobs = InMemoryPluginJobs(plugin_rows(globex_run=2))
    run(deps)
    again = deps.tracker.get("JS-003").fit.evidence.requirements
    assert [r.text for r in again] == [r.text for r in first]  # the list is held fixed
    assert {r.evidence for r in again} == {"partial"}  # only the evidence is judged again


def test_a_jd_not_on_disk_yet_waits_for_the_next_run():
    deps, llm = make_deps(jds={"JS-002": INITECH_JD})
    result = run(deps)
    assert [s["id"] for s in result["scored"]] == ["JS-002"]
    assert result["waiting"] == [
        {"id": "JS-003", "reason": "JS-003_JD.md isn't in the synced job folder"}
    ]
    deps.job_files.jds["JS-003"] = GLOBEX_JD
    assert [s["id"] for s in run(deps)["scored"]] == ["JS-003"]


def test_a_dry_run_calls_no_model_and_writes_nothing():
    deps, llm = make_deps()
    result = run(deps, dry_run=True)
    assert [d["row"]["id"] for d in result["due"]] == ["JS-003", "JS-002"]
    assert llm.calls == [] and deps.tracker.list() == []


def test_the_limit_leaves_the_rest_for_later():
    deps, _ = make_deps()
    result = run(deps, limit=1)
    assert [s["id"] for s in result["scored"]] == ["JS-003"]
    assert result["waiting"] == [{"id": "JS-002", "reason": "over this run's limit"}]


def test_one_failed_assessment_does_not_stop_the_others_and_is_retried():
    deps, _ = make_deps(jds={"JS-003": GLOBEX_JD + " BROKEN", "JS-002": INITECH_JD})
    result = run(deps)
    assert [s["id"] for s in result["scored"]] == ["JS-002"]
    assert result["failed"] == [
        {"id": "JS-003", "error": "RuntimeError: model returned nothing usable"}
    ]
    deps.job_files.jds["JS-003"] = GLOBEX_JD
    assert [s["id"] for s in run(deps)["scored"]] == ["JS-003"]


def test_on_sheets_b_writes_its_shadow_and_only_reads_the_plugins_tracker():
    sheets = FakeSheets()
    log = [
        ["ID", "Company", "Job Title", "Fit Score (1-10)", "Score Tier", "Fit Report", "Run Tier 2"],
        ["JS-003", "Globex", "Lead Architect", "9", "T2", "r1: 9", "FALSE"],
        ["JS-001", "Acme", "Architect", "6", "T1", "", "TRUE"],
    ]  # fmt: skip
    sheets.add_book("a-tracker", "Job_Search_Tracker", {JOB_LOG: log})
    tracker = SheetsTracker(sheets, create_shadow(sheets))
    deps, _ = make_deps(tracker=tracker)
    deps.plugin_jobs = SheetsPluginJobs(sheets, "a-tracker")
    before = sheets.read("a-tracker", JOB_LOG)

    assert [s["id"] for s in run(deps)["scored"]] == ["JS-003"]
    assert tracker.get("JS-003").jd_text == GLOBEX_JD  # the JD went to the shadow's JDs tab
    assert sheets.read("a-tracker", JOB_LOG) == before  # nor is the Run Tier 2 box touched
    assert run(deps)["scored"] == []
