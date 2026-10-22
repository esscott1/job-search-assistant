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


def real_deps() -> Deps:
    d = data_dir()
    # The profile names the full resume, which sits in the same folder (Candidate → Full resume).
    profile = FileProfileSource(
        _setting_path(os.environ.get("JOBS_PROFILE", d / "job-search-profile.md"))
    )
    tracker = SqliteTracker(d / "tracker.db")
    return Deps(
        tracker=tracker,
        jd_fetcher=HttpJDFetcher(),
        llm=AnthropicLLM(),
        resume=ProfileResumeSource(profile),
        docs=FileDocumentStore(d / "resumes"),
        profile=profile,
        mail=GmailMail(),  # signs in on first search, so other commands need no Google token
        known=TrackerKnownJobs(tracker),
    )
