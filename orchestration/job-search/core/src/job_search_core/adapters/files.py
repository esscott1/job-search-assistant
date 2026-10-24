"""File-based adapters: job-search profile, full resume, the plugin's saved JDs, tailored-resume
store."""

from __future__ import annotations

import glob
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


class SyncedJobFiles:
    """The job files the plugin saves in Drive, read from the copy Drive for desktop syncs to disk.

    The plugin keeps a folder per company in its job-search folder, the folder that holds the
    profile (job-tracker, **Job files in Drive**). B can't read those files through Drive: they
    were created by the plugin, and `drive.file` doesn't reach them even in a folder picked in
    the Picker (roadmap decision D8). The plugin writes them as plain Markdown, so they sync as
    ordinary `.md` files.
    """

    def __init__(self, profile: FileProfileSource):
        self.profile = profile

    def saved_jd(self, job_id: str) -> str | None:
        """`<ID>_JD.md` in any company folder (IDs are unique), or None if it hasn't synced."""
        return self._read(f"{glob.escape(job_id)}_JD.md")

    def fit_report(self, job_id: str, run: int) -> str | None:
        """`<ID>_fit_r<n>_<date>.md` in any company folder, or None if it hasn't synced."""
        return self._read(f"{glob.escape(job_id)}_fit_r{run}_*.md")

    def _read(self, name: str) -> str | None:
        found = sorted(self.profile.path.parent.glob(f"*/{name}"))
        return found[0].read_text(encoding="utf-8") if found else None


class FileDocumentStore:
    """Writes tailored resumes as Markdown under a directory. (.docx rendering: roadmap M4.)"""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def save_resume(self, job_id: str, content: str) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{job_id}.md"
        path.write_text(content, encoding="utf-8")
        return str(path)
