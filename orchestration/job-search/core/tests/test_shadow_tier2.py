"""Tier 2 shadow mode in core: which plugin runs are due, reading the plugin's Job Log and saved
JDs, and recording B's score under the plugin's ID."""

import pytest
from job_search_core import policy, steps, usecases
from job_search_core.adapters.fakes import (
    STRONG_FIT,
    SYNTHETIC_PROFILE,
    FakeSheets,
    InMemoryProfileSource,
)
from job_search_core.adapters.files import FileProfileSource, SyncedJobFiles
from job_search_core.adapters.google_sheets import (
    JOB_LOG,
    ProfilePluginJobs,
    SheetsPluginJobs,
    TrackerSheetError,
)
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.domain import PluginJob, Status

LOG_HEADER = ["ID", "Company", "Job Title", "Type / Location", "Fit Score (1-10)", "Score Tier",
              "Fit Report", "Run Tier 2", "Canonical URL", "Source"]  # fmt: skip
LOG = [
    LOG_HEADER,
    ["JS-003", "Globex", "Lead Architect", "Remote", "7", "T2", "r2: 7", "FALSE",
     "https://jobs.example.com/globex/1", "LinkedIn alerts"],
    ["JS-002", "Initech", "Principal Architect", "", "4", "T2-manual", "r1: 4", "FALSE"],
    ["JS-001", "Acme", "Architect", "", "6", "T1", "", "TRUE"],
]  # fmt: skip


def row(**fields) -> PluginJob:
    return PluginJob(**{"id": "JS-001", "company": "Acme", "title": "Architect", **fields})


@pytest.mark.parametrize(
    "tier,run,mirrored,due",
    [
        ("T2", 1, None, True),  # never mirrored
        ("T2-manual", 1, None, True),
        ("T2", 2, 1, True),  # the plugin rescored since
        ("T2", 2, 2, False),  # already mirrored
        ("T1", None, None, False),  # no JD read yet
        ("T2-pending-manual", 1, None, False),  # an earlier run's report, but no JD now
        ("T2-closed", 1, None, False),
        ("T2-no-jd", None, None, False),
        ("T2", None, None, False),  # a T2 row without a fit report has no run to mirror
    ],
)
def test_a_job_is_due_when_the_plugin_has_a_scored_run_b_has_not_mirrored(tier, run, mirrored, due):
    assert policy.shadow_tier2_due(row(scoring_tier=tier, fit_run=run), mirrored) is due


def test_reads_the_plugins_job_log_by_header():
    sheets = FakeSheets()
    sheets.add_book("a", "Tracker", {JOB_LOG: LOG})
    jobs = {j.id: j for j in SheetsPluginJobs(sheets, "a").jobs()}
    assert jobs["JS-003"] == PluginJob(
        id="JS-003", company="Globex", title="Lead Architect", source="LinkedIn alerts",
        location="Remote", canonical_url="https://jobs.example.com/globex/1", score=7,
        scoring_tier="T2", fit_run=2,
    )  # fmt: skip
    assert (jobs["JS-002"].fit_run, jobs["JS-002"].scoring_tier) == (1, "T2-manual")
    assert jobs["JS-001"].fit_run is None


def test_a_missing_column_is_reported_not_guessed():
    sheets = FakeSheets()
    sheets.add_book("a", "Tracker", {JOB_LOG: [[h for h in LOG_HEADER if h != "Fit Report"]]})
    with pytest.raises(TrackerSheetError, match='"Fit Report"'):
        SheetsPluginJobs(sheets, "a").jobs()


def test_the_profile_names_the_plugins_tracker():
    sheets = FakeSheets()
    sheets.add_book("a-tracker", "Tracker", {JOB_LOG: LOG})
    text = SYNTHETIC_PROFILE + "\n## Tracker\n- Sheet ID: a-tracker\n"
    assert len(ProfilePluginJobs(sheets, InMemoryProfileSource(text)).jobs()) == 3
    with pytest.raises(TrackerSheetError, match="Sheet ID"):
        ProfilePluginJobs(sheets, InMemoryProfileSource(SYNTHETIC_PROFILE)).jobs()


def test_saved_jds_are_read_from_any_company_folder_beside_the_profile(tmp_path):
    (tmp_path / "job-search-profile.md").write_text(SYNTHETIC_PROFILE, encoding="utf-8")
    (tmp_path / "Globex").mkdir()
    (tmp_path / "Globex" / "JS-003_JD.md").write_text("# JS-003 Globex", encoding="utf-8")
    (tmp_path / "Globex" / "JS-0031_JD.md").write_text("another job", encoding="utf-8")
    (tmp_path / "Initech").mkdir()
    (tmp_path / "Initech" / "JS-002_JD.md.gdoc").write_text("{}", encoding="utf-8")  # a stub
    files = SyncedJobFiles(FileProfileSource(tmp_path / "job-search-profile.md"))
    assert files.saved_jd("JS-003") == "# JS-003 Globex"
    assert files.saved_jd("JS-002") is None
    assert files.saved_jd("JS-00?") is None  # an ID is never a pattern


def test_shadow_job_is_added_under_the_plugins_id_and_marked_with_the_run_it_mirrors():
    tracker = SqliteTracker()
    plugin = row(id="JS-003", scoring_tier="T2", fit_run=2, canonical_url="https://x.example/1")
    usecases.record_shadow_job(tracker, plugin, "JD text")
    fit = steps.compute_fit(STRONG_FIT)
    job = usecases.record_score(tracker, "JS-003", fit, "T2", plugin_run=2)
    assert (job.status, job.scoring_tier, job.plugin_run) == (Status.SCORED, "T2", 2)
    assert (job.jd_text, job.url, job.canonical_url) == ("JD text", "https://x.example/1",
                                                         "https://x.example/1")  # fmt: skip


def test_a_rescore_keeps_the_requirements_only_for_the_same_jd():
    tracker = SqliteTracker()
    usecases.record_shadow_job(tracker, row(), "JD one")
    usecases.record_score(tracker, "JS-001", steps.compute_fit(STRONG_FIT), plugin_run=1)
    job = tracker.get("JS-001")
    assert policy.rescore_basis(job, "JD one") == job.fit.evidence
    assert policy.rescore_basis(job, "JD two") is None
    # The plugin's JD was replaced: the new one is recorded on the next mirror.
    assert usecases.record_shadow_job(tracker, row(), "JD two").jd_text == "JD two"
