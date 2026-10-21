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
from job_search_core.adapters.http_jd_fetcher import HttpJDFetcher
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.ports import (
    DocumentStorePort,
    JDFetcherPort,
    LLMPort,
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


def data_dir() -> Path:
    return Path(os.environ.get("JOBS_DATA_DIR", "./data"))


def real_deps() -> Deps:
    d = data_dir()
    # The profile names the full resume, which sits in the same folder (Candidate → Full resume).
    profile = FileProfileSource(os.environ.get("JOBS_PROFILE", d / "job-search-profile.md"))
    return Deps(
        tracker=SqliteTracker(d / "tracker.db"),
        jd_fetcher=HttpJDFetcher(),
        llm=AnthropicLLM(),
        resume=ProfileResumeSource(profile),
        docs=FileDocumentStore(d / "resumes"),
        profile=profile,
    )
