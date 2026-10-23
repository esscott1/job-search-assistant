"""Dependency wiring: which adapter fills each port. The only place real vs. fake is chosen."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from job_search_core.adapters.anthropic_llm import AnthropicLLM
from job_search_core.adapters.files import (
    FileDocumentStore,
    FileProfileSource,
    ProfileResumeSource,
)
from job_search_core.adapters.gmail import GmailMail
from job_search_core.adapters.google_sheets import (
    ProfileKnownJobs,
    SheetsApi,
    SheetsSettings,
    SheetsTracker,
)
from job_search_core.adapters.http_jd_fetcher import HttpJDFetcher
from job_search_core.adapters.known_jobs import TrackerKnownJobs
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.ports import (
    DocumentStorePort,
    JDFetcherPort,
    KnownJobsPort,
    LLMPort,
    MailPort,
    ProfileSourcePort,
    ResumeSourcePort,
    TrackerPort,
)


@dataclass
class Deps:
    tracker: TrackerPort
    jd_fetcher: JDFetcherPort
    llm: LLMPort
    resume: ResumeSourcePort
    docs: DocumentStorePort
    profile: ProfileSourcePort
    mail: MailPort | None = None  # intake only
    known: KnownJobsPort | None = None  # intake only: what dedup checks against


# orchestration/job-search: relative paths in the settings below are taken from here, not from
# the working directory, so the CLI (run from here) and Studio (run from approaches/langgraph)
# use the same tracker.
WORKSPACE = Path(__file__).resolve().parents[4]


def _setting_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else WORKSPACE / path


def data_dir() -> Path:
    return _setting_path(os.environ.get("JOBS_DATA_DIR", "data"))


class SettingError(RuntimeError):
    """A setting in .env or data/ is missing or wrong."""


def profile_path() -> Path:
    return _setting_path(os.environ.get("JOBS_PROFILE", data_dir() / "job-search-profile.md"))


def google_dir() -> Path:
    return data_dir() / "google"


def _tracker(d: Path, sheets: SheetsApi, settings: SheetsSettings) -> TrackerPort:
    """JOBS_TRACKER=sheets puts B on its shadow spreadsheet; SQLite stays the default until
    cut-over (roadmap milestone 6)."""
    choice = os.environ.get("JOBS_TRACKER", "sqlite")
    if choice == "sqlite":
        return SqliteTracker(d / "tracker.db")
    if choice != "sheets":
        raise SettingError(f"JOBS_TRACKER must be sqlite or sheets, not {choice!r}")
    if not settings.shadow_id:
        raise SettingError(
            "JOBS_TRACKER=sheets, but there's no shadow sheet: run `jobs auth google`"
        )
    return SheetsTracker(sheets, settings.shadow_id)


def real_deps() -> Deps:
    d = data_dir()
    # The profile names the full resume, which sits in the same folder (Candidate → Full resume).
    profile = FileProfileSource(profile_path())
    sheets = SheetsApi(google_dir())  # signs in on first use, so other commands need no token
    settings = SheetsSettings.load(google_dir())
    tracker = _tracker(d, sheets, settings)
    own = TrackerKnownJobs(tracker)
    # Dedup checks B's own rows and the plugin's tracker, which the profile names.
    known = ProfileKnownJobs(sheets, profile, also=own)
    return Deps(
        tracker=tracker,
        jd_fetcher=HttpJDFetcher(),
        llm=AnthropicLLM(),
        resume=ProfileResumeSource(profile),
        docs=FileDocumentStore(d / "resumes"),
        profile=profile,
        mail=GmailMail(google_dir=google_dir()),  # signs in on first search
        known=known,
    )
