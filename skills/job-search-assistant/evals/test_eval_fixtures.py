"""Consistency checks for the eval suite's fixtures and mocks (no model calls).
Run with: python -m pytest -q skills/
"""

import base64
import json
from pathlib import Path

EVALS = Path(__file__).parent
STUB = EVALS / "tier2-nothing-ticked" / "gstub" / ".claude-plugin" / "plugin.json"


def test_profile_mock_matches_fixture():
    mock = json.loads((EVALS / "mocks/gdrive/download_file_content.md").read_text(encoding="utf-8"))
    decoded = base64.b64decode(mock["content"]).decode("utf-8")
    assert decoded == (EVALS / "fixtures/job-search-profile.md").read_text(encoding="utf-8")


def test_job_log_headers_match_job_tracker():
    mock = json.loads((EVALS / "mocks/gsheets/get_values.md").read_text(encoding="utf-8"))
    tracker = (EVALS.parent / "job-tracker" / "SKILL.md").read_text(encoding="utf-8")
    for header in mock["values"][0]:
        for name in header.split(", "):
            assert name in tracker, f"{name!r} isn't a job-tracker column"


def test_every_case_with_a_stub_uses_the_same_stub():
    for stub in EVALS.glob("*/gstub/.claude-plugin/plugin.json"):
        assert stub.read_bytes() == STUB.read_bytes(), f"{stub} differs from {STUB}"
