"""Checks for score.py. Run with: python3 -m pytest -q skills/job-search-assistant/job-fit-rubric"""

import pytest

from score import EvidenceError, score


def req(kind, evidence, text="quoted JD line"):
    return {"text": text, "type": kind, "evidence": evidence}


def tier2(arrangement="remote", title="strong", requirements=None):
    return {
        "mode": "tier2",
        "title_seniority": title,
        "work_arrangement": arrangement,
        "requirements": requirements or [req("required", "strong")] * 4 + [req("preferred", "strong")] * 2,
    }


def test_perfect_remote_match_scores_10():
    assert score(tier2())["score"] == 10


def test_same_input_same_output():
    assert score(tier2()) == score(tier2())


def test_required_items_outweigh_preferred():
    missing_required = tier2(requirements=[req("required", "none"), req("preferred", "strong")])
    missing_preferred = tier2(requirements=[req("required", "strong"), req("preferred", "none")])
    assert score(missing_preferred)["score"] > score(missing_required)["score"]


def test_relocation_capped_at_3_even_for_perfect_match():
    result = score(tier2(arrangement="relocation_required"))
    assert result["score"] == 3
    assert any("relocation" in c for c in result["caps_applied"])


def test_remote_and_commutable_rank_above_relocation():
    for arrangement in ("remote", "commutable_onsite", "commutable_hybrid"):
        assert score(tier2(arrangement=arrangement))["score"] > score(tier2(arrangement="relocation_required"))["score"]


def test_acceptable_relocation_is_not_capped():
    result = score(tier2(arrangement="relocation_acceptable"))
    assert result["caps_applied"] == []
    assert score(tier2(arrangement="relocation_required"))["score"] < result["score"] <= score(tier2())["score"]


def test_v1_location_names_still_read():
    for old, new in (("colorado_onsite", "commutable_onsite"), ("colorado_hybrid", "commutable_hybrid")):
        assert score(tier2(arrangement=old))["score"] == score(tier2(arrangement=new))["score"]


def test_low_required_coverage_capped_at_5():
    reqs = [req("required", "strong"), req("required", "none"), req("required", "none")] + [req("preferred", "strong")] * 9
    assert score(tier2(requirements=reqs))["score"] <= 5


def test_tier1_never_above_8():
    assert score({"mode": "tier1", "title_seniority": "strong", "work_arrangement": "remote"})["score"] <= 8


def test_tier1_relocation_still_capped():
    assert score({"mode": "tier1", "title_seniority": "strong", "work_arrangement": "relocation_required"})["score"] <= 3


def test_breakdown_names_version_and_caps():
    text = score(tier2(arrangement="relocation_required"))["breakdown"]
    assert text.startswith("Rubric v") and "relocation max 3" in text


@pytest.mark.parametrize(
    "bad",
    [
        {"mode": "tier2", "title_seniority": "strong", "work_arrangement": "remote", "requirements": []},
        {"mode": "tier2", "title_seniority": "great", "work_arrangement": "remote", "requirements": [req("required", "strong")]},
        {"mode": "tier1", "title_seniority": "strong", "work_arrangement": "moon"},
        {"mode": "tier2", "title_seniority": "strong", "work_arrangement": "remote", "requirements": [req("required", "maybe")]},
    ],
)
def test_invalid_evidence_rejected(bad):
    with pytest.raises(EvidenceError):
        score(bad)
