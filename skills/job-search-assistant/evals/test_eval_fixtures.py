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
    "JS-104.json": "tier2-borderline-required-half-met",
    "JS-105.json": "tier2-borderline-remote-residency",
    "JS-106.json": "tier2-borderline-unlabelled-list",
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


def gold_score(gold: str) -> int:
    result = subprocess.run(
        [sys.executable, str(SCORE_PY), str(EVALS / "fixtures/gold" / gold)],
        capture_output=True, text=True, encoding="utf-8",
        env={"PYTHONIOENCODING": "utf-8", **__import__("os").environ},
    )
    return json.loads(result.stdout)["score"]


@pytest.mark.parametrize("gold, case", [(g, c) for g, c in GOLD.items() if "rescore" not in c])
def test_gold_answer_passes_the_case_graders(gold, case):
    """The gold table, written into a fit report the way the skill writes it and seen JSON-escaped
    as the graders see mock calls, passes every regex grader on the fit report. A grader that
    rejects the right answer would otherwise only show up as a puzzling failure in a live run.
    (The rescore case also checks the report's prose, so it isn't covered here.)"""
    table = (EVALS / "fixtures/gold" / gold).read_text(encoding="utf-8")
    report = f"Score: {gold_score(gold)} (T2)\n\n## Evidence table\n```json\n{table}```\n"
    seen = json.dumps({"title": "fit report", "textContent": report})
    for grader in sorted((EVALS / case / "graders").glob("*.md")):
        text = grader.read_text(encoding="utf-8")
        if "type: regex" not in text or grader.name == "unticked.md":  # unticked checks the row write
            continue
        pattern = re.search(r"pattern: '(.*)'", text).group(1)
        found = re.search(pattern, seen) is not None
        wanted = re.search(r"^match: (\S+)", text, re.M).group(1) == "contains"
        assert found == wanted, f"{case}/{grader.name}"


def test_rescore_keeps_the_r1_requirement_list():
    r1 = json.loads((EVALS / "fixtures/gold/JS-102.json").read_text(encoding="utf-8"))
    r2 = json.loads((EVALS / "fixtures/gold/JS-102-r2.json").read_text(encoding="utf-8"))
    strip = lambda t: [(r["text"], r["type"]) for r in t["requirements"]]  # noqa: E731
    assert strip(r1) == strip(r2)


def test_evals_are_self_contained():
    """Eval data lives in the eval folder: nothing may be fetched from this repository on GitHub
    (raw links, commits, branches), so cases don't depend on git history or the network."""
    for path in EVALS.rglob("*"):
        if path.is_file() and path.suffix in (".md", ".json", ".yaml", ".py") and path.name != "test_eval_fixtures.py":
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "raw.githubusercontent.com" not in text, path
            assert "github.com/esscott1/job-search-assistant" not in text, path
