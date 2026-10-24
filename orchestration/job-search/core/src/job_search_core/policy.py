"""Business rules. Orchestrators ask these questions; they never re-implement the answers.

If a routing decision lives in a graph edge instead of here, a second orchestration
approach cannot reuse it — keep the rule here and let the edge call it.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from .domain import PRE_SUBMISSION, EvidenceTable, FitResult, Job, KnownJob, PluginJob, Status

FIT_THRESHOLD = 7
"""Jobs scoring at or above this get a tailored resume.

This is the pipeline's own gate. The plugin has no automatic threshold: there, the user
ticks Build Resume. Both compare against the same rubric score.
"""

MIN_JD_CHARS = 400
"""Fetched text shorter than this is treated as 'no real job description found'."""


def should_tailor(fit: FitResult) -> bool:
    return fit.score >= FIT_THRESHOLD


def status_after_scoring(fit: FitResult) -> Status:
    return Status.RESUME_DRAFTED if should_tailor(fit) else Status.BELOW_THRESHOLD


def can_evaluate(job: Job) -> bool:
    """A job can be (re-)evaluated only before its resume has gone to the employer."""
    return job.status in PRE_SUBMISSION


def is_resume_stale(job: Job, current_resume_hash: str) -> bool:
    """True when a tailored, not-yet-submitted resume was built from an older full resume."""
    return (
        job.status in {Status.RESUME_DRAFTED, Status.NEEDS_EDIT, Status.RESUME_READY}
        and job.resume_source_hash is not None
        and job.resume_source_hash != current_resume_hash
    )


def looks_like_real_jd(text: str | None) -> bool:
    return bool(text) and len(text.strip()) >= MIN_JD_CHARS


# --- Tier 2 in shadow mode: B mirrors the plugin's finished runs (roadmap milestone 6) ------

SHADOW_TIER2_TIERS = frozenset({"T2", "T2-manual"})
"""The plugin's Score Tiers that mean it scored the full JD, which it saves as `<ID>_JD.md`."""


def shadow_tier2_due(row: PluginJob, mirrored_run: int | None) -> bool:
    """True when the plugin has finished a Tier 2 run on this job that B hasn't mirrored yet.

    Each run the plugin finishes with a score writes a new fit report, so its run number changes
    even when the user rescores twice in a day. Rows it couldn't score (pending manual, no JD,
    closed) have nothing to mirror.
    """
    return (
        row.scoring_tier in SHADOW_TIER2_TIERS
        and row.fit_run is not None
        and row.fit_run != mirrored_run
    )


def rescore_basis(job: Job, jd_text: str) -> EvidenceTable | None:
    """The evidence table a rescore keeps the requirement list from: the last Tier 2 run's, if
    it read this same JD. A replaced JD is read fresh, as the plugin does when the user trashes
    `<ID>_JD.md` to force a new fetch."""
    if job.fit and job.fit.evidence and job.fit.evidence.mode == "tier2" and job.jd_text == jd_text:
        return job.fit.evidence
    return None


# --- Intake: the plugin's job-lead-intake-scan and job-tracker rules ----------------------

INTAKE_WINDOW_DAYS = 7
CATCH_UP_MAX_DAYS = 30

NOT_LEAD_SENDERS = frozenset(
    {
        "messages-noreply@linkedin.com",
        "notifications-noreply@linkedin.com",
        "groups-noreply@linkedin.com",
        "updates-noreply@linkedin.com",
        "editors-noreply@linkedin.com",
    }
)
"""LinkedIn senders whose mail is never a lead (messages, notifications and the like)."""

_COMPANY_SUFFIXES = {"inc", "llc", "ltd", "corp", "corporation", "co", "company", "plc", "gmbh"}


def sender_address(sender: str) -> str:
    """`Name <addr@host>` or `addr@host` → `addr@host`, lowercased."""
    match = re.search(r"<([^>]+)>", sender)
    return (match.group(1) if match else sender).strip().lower()


def reads_for_leads(sender: str, never_scan: list[str]) -> bool:
    """False for LinkedIn's non-job senders and anyone on the profile's Never scan list."""
    address = sender_address(sender)
    return address not in NOT_LEAD_SENDERS and address not in {s.lower() for s in never_scan}


def mail_window(newest_received: date | None, today: date) -> tuple[str, bool]:
    """The Gmail date filter for a scan, and whether it's a catch-up.

    Normally the last 7 days. If the newest email already logged is older than that, read from
    its date instead, at most 30 days back, so a gap between runs loses nothing.
    """
    if newest_received and (today - newest_received).days > INTAKE_WINDOW_DAYS:
        start = max(newest_received, today - timedelta(days=CATCH_UP_MAX_DAYS))
        return f"after:{start:%Y/%m/%d}", True
    return f"newer_than:{INTAKE_WINDOW_DAYS}d", False


def is_never_interested(title: str, terms: list[str]) -> bool:
    """True when the title contains one of the profile's Never interested terms as words."""
    words = f" {_words(title)} "
    return any(f" {_words(term)} " in words for term in terms if _words(term))


def find_duplicate(
    canonical_url: str, company: str, title: str, known: list[KnownJob]
) -> KnownJob | None:
    """A known job that is the same posting: the same canonical URL, or else the same company
    and the same title (a title cut short with "..." matches any title it begins)."""
    if canonical_url:
        for job in known:
            if job.canonical_url == canonical_url:
                return job
    for job in known:
        if _same_company(job.company, company) and _same_title(job.title, title):
            return job
    return None


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", text.lower()).split())


def _company(name: str) -> list[str]:
    return [w for w in _words(name).split() if w not in _COMPANY_SUFFIXES]


def _same_company(a: str, b: str) -> bool:
    """The same name, or one name is the other with words added ("Sia" and "Sia Partners"): an
    alert email and a career site often shorten or lengthen the same employer's name."""
    x, y = _company(a), _company(b)
    if not x or not y:
        return x == y
    shorter, longer = sorted((x, y), key=len)
    return longer[: len(shorter)] == shorter


def _same_title(a: str, b: str) -> bool:
    for x, y in ((a, b), (b, a)):
        stripped = x.rstrip().removesuffix("...").removesuffix("…")
        if stripped != x.rstrip() and _words(y).startswith(_words(stripped)):
            return True
    return _words(a) == _words(b)
