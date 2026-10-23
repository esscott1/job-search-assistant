"""The Google Sheets adapters on FakeSheets: the plugin's tracker read for dedup, and B's shadow
tracker behind TrackerPort. No network; `jobs auth google` checks the real API (setup guide)."""

import pytest
from job_search_core import profile, usecases
from job_search_core.adapters.fakes import (
    SYNTHETIC_PROFILE,
    FakeSheets,
    InMemoryKnownJobs,
    InMemoryProfileSource,
)
from job_search_core.adapters.google_auth import (
    DRIVE_FILE,
    GMAIL_READONLY,
    SIGN_IN,
    missing_scopes,
)
from job_search_core.adapters.google_sheets import (
    HISTORY,
    HISTORY_HEADERS,
    JD_HEADERS,
    JDS,
    JOB_LOG,
    SHADOW_HEADERS,
    ProfileKnownJobs,
    SheetsKnownJobs,
    SheetsSettings,
    SheetsTracker,
    TrackerSheetError,
    create_shadow,
)
from job_search_core.domain import (
    DuplicateJobId,
    FitResult,
    IllegalTransition,
    Job,
    KnownJob,
    Status,
)

# The plugin's tracker: its columns in its own order, one the user added, and a checkbox.
A_LOG = [
    ["ID", "Date Found", "Company", "Job Title", "My notes", "Run Tier 2", "Canonical URL"],
    ["JS-002", "2026-10-14", "Acme Widgets", "Senior Cloud Program Manager", "call", False,
     "https://www.linkedin.com/jobs/view/4000000002/"],
    ["JS-001", "2026-10-13", "Example Corp", "IT Vendor Manager", "", True,
     "https://www.linkedin.com/jobs/view/4000000001/"],
]  # fmt: skip
A_ARCHIVE = [
    ["ID", "Company", "Job Title", "Canonical URL", "Archived On", "Archive Reason"],
    ["JS-005", "Umbrella Example", "Program Manager, Infrastructure", "", "2026-10-01", "stale"],
    ["JS-004", "Initrode", "Delivery Lead", "", "2026-09-20"],
    ["JS-003", "Globex Corp", "Senior IT Program Manager",
     "https://www.linkedin.com/jobs/view/4000000101/", "2026-10-02", "reset"],
]  # fmt: skip


def a_tracker(archive: bool = True) -> FakeSheets:
    sheets = FakeSheets()
    tabs = {"Job Log": A_LOG, "Status Guide": [["Status", "Meaning"]]}
    if archive:
        tabs["Archive"] = A_ARCHIVE
    sheets.add_book("a-tracker", "Job_Search_Tracker", tabs)
    return sheets


# --- the plugin's tracker, read for dedup ---


def test_known_jobs_come_from_the_job_log_and_archive_by_header():
    known = SheetsKnownJobs(a_tracker(), "a-tracker").known_jobs()
    assert [k.id for k in known] == ["JS-002", "JS-001", "JS-005", "JS-004"]
    assert known[1] == KnownJob(
        id="JS-001",
        company="Example Corp",
        title="IT Vendor Manager",
        canonical_url="https://www.linkedin.com/jobs/view/4000000001/",
    )


def test_rows_archived_by_a_reset_may_be_logged_again_but_stale_ones_may_not():
    ids = {k.id for k in SheetsKnownJobs(a_tracker(), "a-tracker").known_jobs()}
    assert "JS-003" not in ids  # Archive Reason: reset
    assert {"JS-005", "JS-004"} <= ids  # stale, and blank (archived before the column existed)


def test_known_jobs_add_bs_own_rows_and_a_tracker_may_have_no_archive_yet():
    own = InMemoryKnownJobs([KnownJob(id="LG-0001", company="Initech", title="TPM")])
    known = SheetsKnownJobs(a_tracker(archive=False), "a-tracker", also=own).known_jobs()
    assert [k.id for k in known] == ["JS-002", "JS-001", "LG-0001"]


def test_the_profile_names_the_tracker_and_a_change_takes_effect_at_once():
    sheets = a_tracker()
    sheets.add_book("moved", "Job_Search_Tracker", {"Job Log": [A_LOG[0], A_LOG[1]]})
    source = InMemoryProfileSource(SYNTHETIC_PROFILE + "\n## Tracker\n- Sheet ID: a-tracker\n")
    own = InMemoryKnownJobs([KnownJob(id="LG-0001", company="Initech", title="TPM")])
    known = ProfileKnownJobs(sheets, source, also=own)
    assert [k.id for k in known.known_jobs()] == ["JS-002", "JS-001", "JS-005", "JS-004", "LG-0001"]

    source.text_value = source.text_value.replace("a-tracker", "moved")
    assert [k.id for k in known.known_jobs()] == ["JS-002", "LG-0001"]


def test_a_profile_naming_no_tracker_leaves_bs_own_rows():
    own = InMemoryKnownJobs([KnownJob(id="LG-0001", company="Initech", title="TPM")])
    known = ProfileKnownJobs(FakeSheets(), InMemoryProfileSource(SYNTHETIC_PROFILE), also=own)
    assert [k.id for k in known.known_jobs()] == ["LG-0001"]


def test_a_tracker_missing_a_needed_column_is_reported_not_guessed():
    sheets = FakeSheets()
    sheets.add_book("t", "Tracker", {"Job Log": [["ID", "Company"], ["JS-001", "Acme"]]})
    with pytest.raises(TrackerSheetError, match='"Job Title"'):
        SheetsKnownJobs(sheets, "t").known_jobs()
    sheets.add_book("u", "Tracker", {"Sheet1": [["ID"]]})
    with pytest.raises(TrackerSheetError, match='no "Job Log" tab'):
        SheetsKnownJobs(sheets, "u").known_jobs()


# --- B's shadow tracker ---


def shadow(jd_chunk: int = 10) -> tuple[FakeSheets, str, SheetsTracker]:
    sheets = FakeSheets()
    spreadsheet_id = create_shadow(sheets)
    return sheets, spreadsheet_id, SheetsTracker(sheets, spreadsheet_id, jd_chunk=jd_chunk)


def job(n: int, **changes) -> Job:
    return Job(
        id=f"LG-{n:04d}", company="Globex Corp", title="Senior IT Program Manager", **changes
    )


def column(sheets: FakeSheets, spreadsheet_id: str, name: str) -> list[str]:
    rows = sheets.read(spreadsheet_id, JOB_LOG)
    i = rows[0].index(name)
    return [r[i] if i < len(r) else "" for r in rows[1:]]


def test_the_shadow_has_a_job_log_history_and_jds_tab():
    sheets, spreadsheet_id, _ = shadow()
    assert sheets.read(spreadsheet_id, JOB_LOG) == [SHADOW_HEADERS]
    assert sheets.read(spreadsheet_id, HISTORY) == [HISTORY_HEADERS]
    assert sheets.read(spreadsheet_id, JDS) == [JD_HEADERS]


def test_a_job_round_trips_with_its_fit_and_a_jd_split_over_cells():
    sheets, spreadsheet_id, tracker = shadow(jd_chunk=10)
    fit = FitResult(
        score=7, top_gaps=["No PMP", "Azure not shown"], rationale="", breakdown="T1 title strong"
    )
    jd = "Responsibilities and qualifications"  # 35 characters: 4 cells of 10
    original = job(1, fit=fit, scoring_tier="T1", jd_text=jd, gmail_message_id="MSG_A1")
    tracker.add(original)

    stored = tracker.get("LG-0001")
    assert stored.model_dump() == original.model_dump()
    assert sheets.read(spreadsheet_id, JDS)[1] == [
        "LG-0001",
        jd[:10],
        jd[10:20],
        jd[20:30],
        jd[30:],
    ]
    assert column(sheets, spreadsheet_id, "Gaps") == ["• No PMP\n• Azure not shown"]
    assert column(sheets, spreadsheet_id, "Score Breakdown") == ["Alert email | T1 title strong"]
    assert column(sheets, spreadsheet_id, "Pipeline Status") == ["new"]
    assert "Responsibilities" not in column(sheets, spreadsheet_id, "Pipeline Data")[0]


def test_new_rows_go_at_the_top_and_ids_count_up_from_the_highest():
    sheets, spreadsheet_id, tracker = shadow()
    tracker.add(job(1))
    tracker.add(job(5))
    assert column(sheets, spreadsheet_id, "ID") == ["LG-0005", "LG-0001"]
    assert tracker.next_id("LG") == "LG-0006"
    assert tracker.next_id("JS") == "JS-0001"
    assert [j.id for j in tracker.list()] == ["LG-0001", "LG-0005"]
    with pytest.raises(DuplicateJobId):
        tracker.add(job(5))


def test_status_changes_only_through_transition_and_each_is_recorded():
    _, _, tracker = shadow()
    tracker.add(job(1))
    changed = tracker.get("LG-0001")
    changed.status = Status.SCORED
    with pytest.raises(ValueError, match="transition"):
        tracker.save(changed)

    tracker.transition("LG-0001", Status.SCORED, "pipeline", "fit 7/10")
    with pytest.raises(IllegalTransition):
        tracker.transition("LG-0001", Status.SUBMITTED, "user")
    assert [(h.from_status, h.to_status, h.note) for h in tracker.history("LG-0001")] == [
        (None, Status.NEW, "created"),
        (Status.NEW, Status.SCORED, "fit 7/10"),
    ]
    assert [j.id for j in tracker.list({Status.SCORED})] == ["LG-0001"]
    assert tracker.list({Status.NEW}) == []


def test_use_cases_work_unchanged_on_the_sheet():
    _, _, tracker = shadow()
    tracker.add(job(1, jd_text="The JD"))
    fit = FitResult(score=8, top_gaps=[], rationale="good", breakdown="b")
    usecases.record_score(tracker, "LG-0001", fit)
    stored = tracker.get("LG-0001")
    assert (stored.status, stored.scoring_tier, stored.fit.score, stored.jd_text) == (
        Status.SCORED,
        "T2",
        8,
        "The JD",
    )


def test_rows_are_found_by_id_after_the_user_sorts_and_their_own_columns_survive():
    sheets, spreadsheet_id, tracker = shadow()
    tracker.add(job(1))
    tracker.add(job(2))
    log = sheets.books[spreadsheet_id][JOB_LOG]
    log[0].append("My notes")
    log[1], log[2] = log[2], log[1]  # sorted: LG-0001 is now on row 2
    log[1] += [""] * (len(log[0]) - len(log[1]))
    log[1][-1] = "ask about remote"

    updated = tracker.get("LG-0001")
    updated.notes = "pipeline note"
    tracker.save(updated)

    assert column(sheets, spreadsheet_id, "ID") == ["LG-0001", "LG-0002"]
    assert column(sheets, spreadsheet_id, "My notes") == ["ask about remote", ""]
    assert tracker.get("LG-0001").notes == "pipeline note"
    assert tracker.get("LG-0002").notes is None


def test_a_shorter_jd_clears_the_cells_a_longer_one_used():
    sheets, spreadsheet_id, tracker = shadow(jd_chunk=10)
    tracker.add(job(1, jd_text="x" * 25))
    shorter = tracker.get("LG-0001")
    shorter.jd_text = "short"
    tracker.save(shorter)
    assert sheets.read(spreadsheet_id, JDS)[1] == ["LG-0001", "short"]
    assert tracker.get("LG-0001").jd_text == "short"


def test_a_missing_job_is_a_key_error():
    _, _, tracker = shadow()
    with pytest.raises(KeyError):
        tracker.get("LG-0404")


# --- settings, scopes and the profile ---


def test_sheets_settings_keep_only_bs_shadow(tmp_path):
    assert SheetsSettings.load(tmp_path) == SheetsSettings()
    SheetsSettings(shadow_id="b-shadow").save(tmp_path)
    assert SheetsSettings.load(tmp_path) == SheetsSettings("b-shadow")
    # An older file also held the tracker; the profile names it now, so that's ignored.
    (tmp_path / "sheets.json").write_text('{"tracker_id": "a-tracker", "shadow_id": "b-shadow"}')
    assert SheetsSettings.load(tmp_path) == SheetsSettings("b-shadow")


def test_a_permission_left_unticked_is_reported():
    asked = SIGN_IN + [DRIVE_FILE, GMAIL_READONLY]
    assert missing_scopes(SIGN_IN + [GMAIL_READONLY], asked) == [DRIVE_FILE]
    assert missing_scopes(asked, asked) == []
    assert missing_scopes(None, [DRIVE_FILE]) == [DRIVE_FILE]


def test_profile_names_the_tracker_sheet():
    text = (
        SYNTHETIC_PROFILE + "\n## Tracker\n- Sheet ID: 1AbC_dEf\n- Sheet name: Job_Search_Tracker\n"
    )
    assert profile.tracker_sheet_id(text) == "1AbC_dEf"
    assert profile.tracker_sheet_id(SYNTHETIC_PROFILE) == ""
