"""The shadow week's agreement report: pairing A's and B's leads, comparing scores and evidence
tables, and a Markdown report with counts and rates only."""

from datetime import date

from job_search_core import agreement, steps
from job_search_core.adapters.fakes import STRONG_FIT, FakeSheets
from job_search_core.adapters.google_sheets import JOB_LOG, SheetsKnownJobs, SheetsPluginJobs
from job_search_core.domain import FitResult, Job, PluginJob

SINCE = date(2026, 10, 25)
B_TABLE = steps.compute_fit(STRONG_FIT).evidence
# A's table for the same JD: the same requirements, one judged partial instead of strong.
A_TABLE = B_TABLE.model_copy(deep=True)
A_TABLE.requirements[2].evidence = "partial"
FIT_REPORT = f"""# JS-005 Acme: Architect, fit run r2
Score: 4 (T2), was 3 in r1

## Evidence table
```json
{A_TABLE.model_dump_json(indent=1)}
```
"""


def a_job(job_id, found, tier, score, url="", gmail="m", run=None, tier2=None, **kw):
    return PluginJob(id=job_id, company=kw.get("company", f"Co {job_id}"),
                     title=kw.get("title", "Architect"), canonical_url=url, score=score,
                     scoring_tier=tier, fit_run=run, found_on=found, tier2_date=tier2,
                     gmail_message_id=gmail)  # fmt: skip


def b_job(job_id, found, score, url="", tier="T1", run=None, evidence=None, **kw):
    fit = FitResult(score=score, top_gaps=[], rationale="", evidence=evidence)
    return Job(id=job_id, company=kw.get("company", f"Co {job_id}"),
               title=kw.get("title", "Architect"), canonical_url=url, found_on=found,
               gmail_message_id="m" if found else None, scoring_tier=tier, fit=fit,
               plugin_run=run)  # fmt: skip


D26, D27 = date(2026, 10, 26), date(2026, 10, 27)
PLUGIN = [
    a_job("JS-010", D26, "T1", 6, url="https://x.example/1"),
    a_job("JS-011", D26, "T2", 7, url="https://x.example/2", run=1, tier2=D27),
    a_job("JS-012", D27, "T1", 5, url="https://x.example/3"),  # B never found it
    a_job("JS-013", D26, "T1", 6, gmail=""),  # from a career site, which B doesn't scan
    a_job("JS-005", date(2026, 10, 1), "T2", 4, run=2, tier2=D26),  # rescored this week
    a_job("JS-006", date(2026, 10, 1), "T2", 8, run=3, tier2=D27),  # rescored after B's run
    a_job("JS-007", date(2026, 10, 1), "T2", 6, run=1, tier2=date(2026, 10, 2)),  # before
]
B = [
    b_job("LG-0001", D26, 7, url="https://x.example/1", company="Co JS-010"),
    b_job("LG-0002", D26, 4, company="Co JS-011"),  # no link; the same company and title
    b_job("LG-0003", D27, 6, url="https://x.example/9"),  # A never found it
    b_job("JS-005", None, 5, tier="T2", run=2, evidence=B_TABLE),
    b_job("JS-006", None, 8, tier="T2", run=2, evidence=B_TABLE),
    b_job("JS-007", None, 6, tier="T2", run=1, evidence=B_TABLE),
]


def report():
    reports = {("JS-005", 2): FIT_REPORT}
    return agreement.shadow_report(PLUGIN, B, lambda i, r: reports.get((i, r)), SINCE)


def test_leads_are_paired_by_link_or_company_and_title():
    intake = report()["intake"]
    assert (intake["a_leads"], intake["b_leads"], intake["both"]) == (3, 3, 2)
    assert (intake["a_only"], intake["b_only"]) == (1, 1)
    assert intake["share_of_a_found_by_b"] == round(2 / 3, 3)
    assert report()["details"]["pairs"] == [("JS-010", "LG-0001"), ("JS-011", "LG-0002")]


def test_tier_1_is_compared_only_while_both_rows_are_tier_1():
    tier1 = report()["intake"]["tier1"]
    assert tier1 == {"pairs": 1, "exact": 0.0, "within_1": 1.0, "not_comparable": 1}


def test_tier_2_compares_current_runs_in_the_window_and_their_evidence_tables():
    r = report()
    tier2 = r["tier2"]
    assert (tier2["pairs"], tier2["exact"], tier2["within_1"], tier2["pending"]) == (1, 0, 1, 1)
    assert r["details"]["tier2_pending"] == ["JS-006"]
    req = tier2["requirements"]
    assert (req["tables"], req["overlap"], req["no_table"]) == (1, 1.0, 0)
    assert req["evidence_agree"] == round(2 / 3, 3)


def test_the_markdown_has_counts_and_rates_but_no_ids_or_companies():
    text = agreement.render(report(), date(2026, 11, 1))
    assert "| Found by both | 2 |" in text and "| Within ±1 | 100% |" in text
    assert "JS-" not in text and "LG-" not in text and "Co " not in text


def test_a_fit_report_without_a_valid_evidence_table_has_none():
    assert agreement.fit_report_evidence(FIT_REPORT) == A_TABLE
    assert agreement.fit_report_evidence("# JS-005\nScore: 4") is None
    broken = FIT_REPORT.replace('"mode"', '"mood"')
    assert agreement.fit_report_evidence(broken) is None


def test_the_shadow_week_leaves_the_plugins_new_rows_out_of_dedup():
    sheets = FakeSheets()
    log = [["ID", "Company", "Job Title", "Date Found"],
           ["JS-011", "Globex", "Architect", "2026-10-26"],
           ["JS-004", "Initech", "Architect", "2026-10-20"],
           ["JS-003", "Umbrella", "Architect", ""]]  # fmt: skip
    sheets.add_book("a", "Tracker", {JOB_LOG: log})
    assert [k.id for k in SheetsKnownJobs(sheets, "a").known_jobs()] == ["JS-011", "JS-004",
                                                                         "JS-003"]  # fmt: skip
    window = SheetsKnownJobs(sheets, "a", found_before=SINCE).known_jobs()
    assert [k.id for k in window] == ["JS-004", "JS-003"]


def test_the_plugins_job_log_gives_the_dates_and_message_id_the_report_needs():
    sheets = FakeSheets()
    log = [
        [
            "ID",
            "Company",
            "Job Title",
            "Score Tier",
            "Fit Report",
            "Date Found",
            "Tier 2 Date",
            "Gmail Message ID",
        ],
        ["JS-011", "Globex", "Architect", "T2", "r1: 7", "2026-10-26", "2026-10-27", "m1"],
    ]
    sheets.add_book("a", "Tracker", {JOB_LOG: log})  # fmt: skip
    (job,) = SheetsPluginJobs(sheets, "a").jobs()
    assert (job.found_on, job.tier2_date, job.gmail_message_id) == (D26, D27, "m1")
