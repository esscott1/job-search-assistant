"""File-based adapters: master resume source and tailored-resume store."""

from __future__ import annotations

import hashlib
from pathlib import Path


class FileResumeSource:
    """Reads the master resume from a Markdown/text file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> str:
        if not self.path.exists():
            raise FileNotFoundError(
                f"Master resume not found at {self.path}. "
                "See docs/setup/job-search-langgraph.md, step 4."
            )
        return self.path.read_text(encoding="utf-8")

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
