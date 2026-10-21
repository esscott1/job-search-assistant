"""Fit score from an evidence table, through the shared rubric.

`rubric.py` is a copy of the plugin's `job-fit-rubric/score.py` (ADR 0003), so both approaches
compute a score with the same code. This module is the only place in core that handles the
rubric's untyped dicts.
"""

from __future__ import annotations

from . import rubric
from .domain import EvidenceTable, RubricScore

EvidenceError = rubric.EvidenceError


def score_evidence(table: EvidenceTable) -> RubricScore:
    """Score a validated evidence table. Raises EvidenceError if the rubric rejects it."""
    return RubricScore.model_validate(rubric.score(table.model_dump()))
