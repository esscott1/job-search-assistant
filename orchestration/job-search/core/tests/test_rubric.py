"""The shared rubric: core's copy must match the plugin's, and both must score alike (ADR 0003).

The plugin's `skills/job-search-assistant/job-fit-rubric/score.py` is the source of truth.
These tests read it from the repository checkout, which CI always has.
"""

import json
import os
import subprocess
import sys
import typing
from pathlib import Path

import pytest
from job_search_core import rubric
from job_search_core.domain import EvidenceTable, FitAssessment, Requirement
from job_search_core.scoring import EvidenceError, score_evidence

REPO = Path(__file__).resolve().parents[4]
PLUGIN_SCORE = REPO / "skills/job-search-assistant/job-fit-rubric/score.py"
GOLD = sorted((REPO / "skills/job-search-assistant/evals/fixtures/gold").glob("*.json"))


def _text(path: Path) -> bytes:
    # Compare content, not checkout line endings (a Windows checkout may use CRLF).
    return path.read_bytes().replace(b"\r\n", b"\n")


def _literal(model: type, field: str) -> set[str]:
    hint = typing.get_type_hints(model)[field]
    return set(typing.get_args(hint))


def test_rubric_matches_plugin_copy():
    assert _text(Path(rubric.__file__)) == _text(PLUGIN_SCORE), (
        "core's rubric differs from the plugin's: copy "
        "skills/job-search-assistant/job-fit-rubric/score.py over "
        "orchestration/job-search/core/src/job_search_core/rubric.py"
    )


def test_schema_matches_rubric_constants():
    assert _literal(EvidenceTable, "title_seniority") == set(rubric.TITLE_CREDIT)
    assert _literal(EvidenceTable, "work_arrangement") == set(rubric.ARRANGEMENT_CREDIT)
    assert _literal(Requirement, "evidence") == set(rubric.EVIDENCE_CREDIT)
    # The model's answer schema offers exactly the same categories.
    for field in ("title_seniority", "work_arrangement"):
        assert _literal(FitAssessment, field) == _literal(EvidenceTable, field)


def test_there_are_gold_tables():
    assert len(GOLD) >= 4


@pytest.mark.parametrize("gold", GOLD, ids=lambda p: p.stem)
def test_gold_tables_score_identically(gold: Path):
    table = EvidenceTable.model_validate_json(gold.read_text(encoding="utf-8"))
    ours = score_evidence(table)
    # The breakdown contains "→" and "·"; ask for UTF-8 so a Windows console encoding can't fail it.
    run = subprocess.run(
        [sys.executable, str(PLUGIN_SCORE), str(gold)],
        capture_output=True,
        encoding="utf-8",
        env=os.environ | {"PYTHONIOENCODING": "utf-8"},
        check=True,
    )
    plugin = json.loads(run.stdout)
    assert ours.model_dump() == plugin


def _table(**overrides) -> EvidenceTable:
    fields = {
        "mode": "tier2",
        "title_seniority": "strong",
        "work_arrangement": "remote",
        "requirements": [
            {"text": "Program management", "type": "required", "evidence": "strong"},
            {"text": "Vendor management", "type": "required", "evidence": "strong"},
        ],
    }
    return EvidenceTable.model_validate(fields | overrides)


def test_strong_remote_fit_scores_ten():
    assert score_evidence(_table()).score == 10


def test_relocation_required_is_capped_at_three():
    result = score_evidence(_table(work_arrangement="relocation_required"))
    assert result.score == 3
    assert any("relocation" in cap for cap in result.caps_applied)


def test_tier1_needs_no_requirements_and_is_capped():
    result = score_evidence(_table(mode="tier1", requirements=[]))
    assert result.score <= 8


def test_tier2_without_requirements_is_rejected_by_the_rubric():
    with pytest.raises(EvidenceError):
        score_evidence(_table(requirements=[]))
