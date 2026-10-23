"""The intake graph end to end on fakes, with the plugin's own intake inbox (two LinkedIn digests
and a LinkedIn message notification) and the plugin's known jobs for it."""

import json
from datetime import date
from pathlib import Path

from job_search_core.adapters.fakes import (
    SYNTHETIC_PROFILE,
    FakeJDFetcher,
    FakeLLM,
    FakeMail,
    FakeSheets,
    InMemoryDocumentStore,
    InMemoryProfileSource,
    InMemoryResumeSource,
    digest_leads,
)
from job_search_core.adapters.google_sheets import SheetsKnownJobs, SheetsTracker, create_shadow
from job_search_core.adapters.known_jobs import TrackerKnownJobs
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.domain import KnownJob
from job_search_core.ports import MailMessage
from job_search_langgraph.deps import Deps
from job_search_langgraph.intake_graph import build_intake_graph

REPO = Path(__file__).resolve().parents[5]
INBOX = REPO / "skills/job-search-assistant/evals/fixtures/inbox.json"

# The plugin's intake case: JS-001 and JS-002 are in its Job Log, JS-005 in its Archive.
PLUGIN_KNOWN = [
    KnownJob(id="JS-002", company="Acme Widgets", title="Senior Cloud Program Manager",
             canonical_url="https://www.linkedin.com/jobs/view/4000000002/"),
    KnownJob(id="JS-001", company="Example Corp", title="IT Vendor Manager",
             canonical_url="https://www.linkedin.com/jobs/view/4000000001/"),
    KnownJob(id="JS-005", company="Umbrella Example", title="Program Manager, Infrastructure",
             canonical_url="https://www.linkedin.com/jobs/view/4000000005/"),
]  # fmt: skip

# The same three jobs as the plugin's Sheet holds them: two in its Job Log, one in its Archive.
PLUGIN_LOG = [["ID", "Company", "Job Title", "Canonical URL"]] + [
    [k.id, k.company, k.title, k.canonical_url] for k in PLUGIN_KNOWN[:2]
]
PLUGIN_ARCHIVE = [["ID", "Company", "Job Title", "Archive Reason"], ["JS-005", PLUGIN_KNOWN[2].company,
                  PLUGIN_KNOWN[2].title, "stale"]]  # fmt: skip

# Search every linkedin.com sender, so the message notification comes back and must be dropped.
BROAD_PROFILE = SYNTHETIC_PROFILE.replace("| jobalerts-noreply@linkedin.com |", "| linkedin.com |")


def inbox() -> list[MailMessage]:
    return [
        MailMessage(
            id=m["messageId"],
            thread_id=m["threadId"],
            sender=m["sender"],
            subject=m["subject"],
            received_at=m["date"],
            body_text=m["plaintext_body"],
        )
        for m in json.loads(INBOX.read_text(encoding="utf-8"))
    ]


class KnownWithArchive:
    """The tracker's rows plus a fixed archive, as the Sheet will provide."""

    def __init__(self, tracker, archive):
        self.rows, self.archive = TrackerKnownJobs(tracker), archive

    def known_jobs(self):
        return self.rows.known_jobs() + list(self.archive)


def make_deps(profile_text=SYNTHETIC_PROFILE, tracker=None):
    tracker = tracker or SqliteTracker()
    llm = FakeLLM(leads_for=digest_leads)
    deps = Deps(
        tracker=tracker,
        jd_fetcher=FakeJDFetcher(),
        llm=llm,
        resume=InMemoryResumeSource(),
        docs=InMemoryDocumentStore(),
        profile=InMemoryProfileSource(profile_text),
        mail=FakeMail(inbox()),
        known=KnownWithArchive(tracker, PLUGIN_KNOWN),
    )
    return deps, llm


def run(deps, **inputs):
    return build_intake_graph(deps).invoke({"today": "2026-10-16", **inputs})


def test_logs_the_two_new_leads_oldest_email_first_and_skips_the_rest():
    deps, _ = make_deps()
    result = run(deps)
    assert [(a["id"], a["company"]) for a in result["added"]] == [
        ("LG-0001", "Globex Corp"),
        ("LG-0002", "Initech"),
    ]
    reasons = {s["company"]: s["reason"] for s in result["skipped"]}
    assert reasons == {
        "ShopMart Example": "Never interested",  # kept by the reader; the profile's list catches it
        "Example Corp": "already known as JS-001",  # same posting under other tracking parameters
        "Umbrella Example": "already known as JS-005",  # archived; same company and title
    }


def test_stored_leads_are_tier_1_rows_with_canonical_links_and_no_sign_in_token():
    deps, _ = make_deps()
    run(deps)
    globex = deps.tracker.get("LG-0001")
    assert globex.url == "https://www.linkedin.com/jobs/view/4000000101/"
    assert globex.scoring_tier == "T1" and globex.fit.score == 7
    assert globex.pay_range == "$150K-$170K / year" and globex.source == "LinkedIn alerts"
    assert (globex.email_received, globex.found_on) == (date(2026, 10, 14), date(2026, 10, 16))
    assert all("otpToken" not in j.model_dump_json() for j in deps.tracker.list())


def test_never_scan_and_non_job_senders_are_not_read_or_sent_to_the_model():
    deps, llm = make_deps(BROAD_PROFILE)
    result = run(deps)
    assert [m["reason"] for m in result["not_read"]] == ["on Never scan"]
    assert len(result["emails"]) == 2 and llm.calls == ["structured", "structured"]


def test_a_dry_run_writes_nothing():
    deps, _ = make_deps()
    result = run(deps, dry_run=True)
    assert [a["id"] for a in result["added"]] == ["(dry run)", "(dry run)"]
    assert deps.tracker.list() == []


def test_running_again_adds_nothing():
    deps, _ = make_deps()
    run(deps)
    again = run(deps)
    assert again["added"] == []
    assert {s["reason"] for s in again["skipped"]} >= {
        "already known as LG-0001",
        "already known as LG-0002",
    }


def test_a_gap_since_the_last_logged_email_reads_from_its_date():
    deps, _ = make_deps()
    run(deps)  # logs leads from emails received 2026-10-14 and 2026-10-15
    result = run(deps, today="2026-10-30")
    assert (result["window"], result["catch_up"]) == ("after:2026/10/15", True)
    assert deps.mail.queries[-1] == "from:jobalerts-noreply@linkedin.com after:2026/10/15"


def test_on_sheets_leads_go_to_bs_shadow_and_dedup_reads_the_plugins_tracker():
    sheets = FakeSheets()
    sheets.add_book(
        "a-tracker", "Job_Search_Tracker", {"Job Log": PLUGIN_LOG, "Archive": PLUGIN_ARCHIVE}
    )
    tracker = SheetsTracker(sheets, create_shadow(sheets))
    deps, _ = make_deps(tracker=tracker)
    deps.known = SheetsKnownJobs(sheets, "a-tracker", also=TrackerKnownJobs(tracker))
    before = sheets.read("a-tracker", "Job Log")

    result = run(deps)
    assert [a["id"] for a in result["added"]] == ["LG-0001", "LG-0002"]
    assert {s["reason"] for s in result["skipped"]} >= {
        "already known as JS-001",
        "already known as JS-005",
    }
    assert [j.company for j in tracker.list()] == ["Globex Corp", "Initech"]
    assert sheets.read("a-tracker", "Job Log") == before  # the plugin's tracker is never written
    assert run(deps)["added"] == []


def test_no_email_sources_means_no_search_and_no_model_call():
    deps, llm = make_deps(SYNTHETIC_PROFILE.split("## Email sources")[0])
    result = run(deps)
    assert deps.mail.queries == [] and llm.calls == [] and result["added"] == []
