"""Intake's core: the profile's sources, the mail window, sender and dedup rules, the Tier 1 score,
and recording a lead. No model calls; FakeLLM stands in where one would be."""

from datetime import UTC, date, datetime

from job_search_core import policy, profile, steps, usecases
from job_search_core.adapters.fakes import SYNTHETIC_PROFILE, FakeLLM, digest_leads
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.domain import EmailLeads, KnownJob, LeadCard
from job_search_core.ports import MailMessage

TODAY = date(2026, 10, 22)


def card(**changes) -> LeadCard:
    base = dict(
        company="Globex Corp",
        title="Senior IT Program Manager",
        location="United States (Remote)",
        posting_url="https://www.linkedin.com/comm/jobs/view/4000000101/?trk=eml&otpToken=SECRET",
        title_seniority="strong",
        work_arrangement="remote",
        keep=True,
    )
    return LeadCard(**{**base, **changes})


# --- the profile ---


def test_profile_lists_email_sources_never_scan_and_never_interested():
    sources = profile.email_sources(SYNTHETIC_PROFILE)
    assert [(s.label, s.sender) for s in sources] == [
        ("LinkedIn alerts", "jobalerts-noreply@linkedin.com")
    ]
    assert profile.never_scan(SYNTHETIC_PROFILE) == ["messages-noreply@linkedin.com"]
    assert profile.never_interested(SYNTHETIC_PROFILE) == ["sales", "retail"]


def test_a_missing_section_is_empty():
    bare = "# Job search profile\n\n## Target roles\n- Role families: program management\n"
    assert profile.email_sources(bare) == []
    assert profile.never_scan(bare) == []
    assert profile.never_interested(bare) == []


# --- the mail window ---


def test_the_window_is_the_last_week():
    assert policy.mail_window(None, TODAY) == ("newer_than:7d", False)
    assert policy.mail_window(date(2026, 10, 19), TODAY) == ("newer_than:7d", False)


def test_a_gap_since_the_newest_email_is_caught_up_at_most_30_days_back():
    assert policy.mail_window(date(2026, 10, 10), TODAY) == ("after:2026/10/10", True)
    assert policy.mail_window(date(2026, 7, 1), TODAY) == ("after:2026/09/22", True)


# --- senders ---


def test_linkedin_messages_and_never_scan_senders_are_not_read():
    assert policy.reads_for_leads("LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>", [])
    assert not policy.reads_for_leads("LinkedIn <messages-noreply@linkedin.com>", [])
    assert not policy.reads_for_leads("Recruiter <ann@agency.example>", ["ann@agency.example"])


# --- dedup ---

KNOWN = [
    KnownJob(
        id="JS-001",
        company="Example Corp",
        title="IT Vendor Manager",
        canonical_url="https://www.linkedin.com/jobs/view/4000000001/",
    ),
    KnownJob(id="JS-005", company="Umbrella Example", title="Program Manager, Infrastructure"),
]


def test_the_same_canonical_link_is_a_duplicate_whatever_the_title():
    found = policy.find_duplicate(
        "https://www.linkedin.com/jobs/view/4000000001/", "Example", "Vendor Mgr", KNOWN
    )
    assert found.id == "JS-001"


def test_the_same_company_and_title_is_a_duplicate_without_a_link():
    assert (
        policy.find_duplicate(
            "", "Umbrella Example Inc.", "Program Manager - Infrastructure", KNOWN
        ).id
        == "JS-005"
    )
    assert (
        policy.find_duplicate("", "Umbrella Example", "Program Manager, Infra...", KNOWN).id
        == "JS-005"
    )
    assert policy.find_duplicate("", "Umbrella Example", "Program Director", KNOWN) is None
    assert policy.find_duplicate("", "Other Co", "IT Vendor Manager", KNOWN) is None


def test_a_company_name_with_words_added_is_the_same_company():
    known = [
        KnownJob(id="JS-010", company="Initech Partners", title="Senior AI Architect"),
        KnownJob(id="JS-011", company="Vandelay", title="Director, Data Office"),
    ]
    assert policy.find_duplicate("", "Initech", "Senior AI Architect", known).id == "JS-010"
    assert policy.find_duplicate("", "Vandelay ACC", "Director, Data Office", known).id == "JS-011"
    # Whole words from the start only, and the titles must still match.
    assert policy.find_duplicate("", "Initechs", "Senior AI Architect", known) is None
    assert policy.find_duplicate("", "Partners", "Senior AI Architect", known) is None
    assert policy.find_duplicate("", "Initech", "AI Delivery Lead", known) is None
    # A blank company never matches a named one.
    assert policy.find_duplicate("", "", "Senior AI Architect", known) is None


def test_never_interested_matches_whole_words_only():
    assert policy.is_never_interested("Retail Store Manager", ["sales", "retail"])
    assert not policy.is_never_interested("Salesforce Program Manager", ["sales"])


# --- reading an email and the Tier 1 score ---


def test_reading_an_email_gives_the_model_the_profile_and_the_email():
    seen = []

    def leads_for(email_text):
        seen.append(email_text)
        return EmailLeads(leads=[card()])

    message = MailMessage(
        id="M1",
        thread_id="T1",
        sender="LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
        subject="New jobs",
        received_at=datetime(2026, 10, 14, 13, 5, tzinfo=UTC),
        body_text="Senior IT Program Manager\nGlobex Corp",
    )
    cards = steps.read_alert_email(message, SYNTHETIC_PROFILE, FakeLLM(leads_for=leads_for))
    assert [c.company for c in cards] == ["Globex Corp"]
    assert "Subject: New jobs" in seen[0] and "Globex Corp" in seen[0]


def test_tier1_scores_a_strong_remote_lead_7_and_caps_relocation_at_3():
    fit = steps.tier1_fit(card())
    assert fit.score == 7 and fit.top_gaps == ["JD not read yet"]
    assert fit.evidence.mode == "tier1" and fit.prompt_version.startswith("lead-reading/")

    far = steps.tier1_fit(card(work_arrangement="relocation_required", location="Austin, TX"))
    assert far.score == 3
    assert far.top_gaps == ["JD not read yet", "Relocation required (Austin, TX)"]


def test_digest_stand_in_reads_cards_like_the_fixture_inbox():
    text = (
        "Your job alert\n\nSenior IT Program Manager\nGlobex Corp\nUnited States (Remote)\n"
        "$150K-$170K / year\nView job: https://www.linkedin.com/comm/jobs/view/4000000101/?x=1"
    )
    [lead] = digest_leads(text).leads
    assert (lead.company, lead.pay_range) == ("Globex Corp", "$150K-$170K / year")


# --- recording ---


def test_a_recorded_lead_keeps_the_canonical_link_never_the_emails_own():
    tracker = SqliteTracker()
    message = MailMessage(
        id="MSG_A1",
        thread_id="T",
        sender="s",
        subject="x",
        received_at=datetime(2026, 10, 14, 13, 5, tzinfo=UTC),
        body_text="",
    )
    lead = card()
    job = usecases.record_lead(
        tracker,
        lead,
        steps.tier1_fit(lead),
        canonical_url="https://www.linkedin.com/jobs/view/4000000101/",
        source="LinkedIn alerts",
        message=message,
        today=TODAY,
    )
    stored = tracker.get(job.id)
    assert stored.id == "LG-0001" and stored.scoring_tier == "T1" and stored.fit.score == 7
    assert stored.url == stored.canonical_url == "https://www.linkedin.com/jobs/view/4000000101/"
    assert "otpToken" not in stored.model_dump_json()
    assert (stored.found_on, stored.email_received, stored.gmail_message_id) == (
        TODAY,
        date(2026, 10, 14),
        "MSG_A1",
    )
