"""Consistency checks for the eval suite's fixtures, mocks and gold answers (no model calls).
Run with: python -m pytest -q skills/
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

EVALS = Path(__file__).parent
SCORE_PY = EVALS.parent / "job-fit-rubric" / "score.py"

# Gold evidence table -> the case whose score-in-band grader it backs.
GOLD = {
    "JS-101.json": "tier2-gold-strong-fit",
    "JS-102.json": "tier2-gold-partial-fit",
    "JS-103.json": "tier2-gold-relocation-mismatch",
    "JS-102-r2.json": "tier2-rescore-closes-gap",
}


def test_mocks_are_built_from_the_fixtures():
    result = subprocess.run(
        [sys.executable, str(EVALS / "build_mocks.py"), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout


def test_job_log_headers_match_job_tracker():
    mock = json.loads((EVALS / "mocks/gsheets/get_values.md").read_text(encoding="utf-8"))
    tracker = (EVALS.parent / "job-tracker" / "SKILL.md").read_text(encoding="utf-8")
    for header in mock["values"][0]:
        assert header in tracker, f"{header!r} isn't a job-tracker column"


@pytest.mark.parametrize("gold, case", GOLD.items())
def test_gold_score_is_inside_the_case_band(gold, case):
    """If the rubric changes, the gold scores move; this says which graders need updating."""
    result = subprocess.run(
        [sys.executable, str(SCORE_PY), str(EVALS / "fixtures/gold" / gold)],
        capture_output=True, text=True, encoding="utf-8",
        env={"PYTHONIOENCODING": "utf-8", **__import__("os").environ},
    )
    assert result.returncode == 0, result.stdout
    score = json.loads(result.stdout)["score"]
    grader = (EVALS / case / "graders/score-in-band.md").read_text(encoding="utf-8")
    pattern = re.search(r"pattern: '(.*)'", grader).group(1)
    assert re.search(pattern, f"Score: {score} (T2)"), f"gold score {score} is outside {pattern}"


def test_rescore_keeps_the_r1_requirement_list():
    r1 = json.loads((EVALS / "fixtures/gold/JS-102.json").read_text(encoding="utf-8"))
    r2 = json.loads((EVALS / "fixtures/gold/JS-102-r2.json").read_text(encoding="utf-8"))
    strip = lambda t: [(r["text"], r["type"]) for r in t["requirements"]]  # noqa: E731
    assert strip(r1) == strip(r2)


def test_career_feed_url_points_at_the_feed_fixture():
    """The careers profile fetches the feed from GitHub at a pinned commit; the path must match the file."""
    profile = (EVALS / "fixtures/job-search-profile-careers.md").read_text(encoding="utf-8")
    url = re.search(r"https://raw\.githubusercontent\.com/esscott1/job-search-assistant/([0-9a-f]{40})/(\S+?) \|", profile)
    assert url, "the career site URL must be pinned to a full commit SHA"
    repo_root = EVALS.parents[2]
    assert (repo_root / url.group(2)).is_file(), url.group(2)
