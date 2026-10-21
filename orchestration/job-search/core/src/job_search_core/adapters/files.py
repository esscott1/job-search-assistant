"""File-based adapters: job-search profile, full resume and tailored-resume store."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..profile import full_resume_name


class FileProfileSource:
    """Reads the job-search profile, the Markdown file the plugin's profile skill writes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> str:
        if not self.path.exists():
            raise FileNotFoundError(
                f"Job-search profile not found at {self.path}. Copy job-search-profile.md "
                "from your tracker folder into data/, or set JOBS_PROFILE to it "
                "(docs/setup/job-search-langgraph.md, step 4)."
            )
        return self.path.read_text(encoding="utf-8")


class ProfileResumeSource:
    """The full resume the profile names (Candidate → Full resume), in the profile's folder.

    The plugin finds the resume the same way, so pointing JOBS_PROFILE at the profile in the
    plugin's own job-search folder makes both approaches read the same files.
    """

    def __init__(self, profile: FileProfileSource):
        self.profile = profile

    @property
    def path(self) -> Path:
        return self.profile.path.parent / full_resume_name(self.profile.read())

    def read(self) -> str:
        path = self.path
        if not path.exists():
            raise FileNotFoundError(
                f"Full resume '{path.name}' (named in {self.profile.path.name}) not found in "
                f"{path.parent}. See docs/setup/job-search-langgraph.md, step 4."
            )
        return path.read_text(encoding="utf-8")

    def content_hash(self) -> str:
        return hashlib.sha256(self.read().encode("utf-8")).hexdigest()[:16]


class FileDocumentStore:
    """Writes tailored resumes as Markdown under a directory. (.docx rendering: roadmap M4.)"""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def save_resume(self, job_id: str, content: str) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{job_id}.md"
        path.write_text(content, encoding="utf-8")
        return str(path)
