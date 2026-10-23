"""assess_fit and compute_fit: the model judges, the shared rubric scores (ADR 0003)."""

import pytest
from job_search_core import profile, prompts, rubric, steps
from job_search_core.adapters.fakes import (
    STRONG_FIT,
    SYNTHETIC_PROFILE,
    WEAK_FIT,
    FakeLLM,
)
from job_search_core.domain import EvidenceTable, FitAssessment, Requirement

JD = "Enterprise architect, AI enablement. " * 20


def test_strong_assessment_scores_through_the_rubric():
    fit = steps.compute_fit(STRONG_FIT)
    assert fit.score == 10
    assert fit.breakdown.startswith(f"Rubric v{rubric.RUBRIC_VERSION} |")
    assert fit.rubric_version == rubric.RUBRIC_VERSION
    assert fit.prompt_version == prompts.load("fit_scoring")[0]
    assert fit.evidence.mode == "tier2"
    assert len(fit.evidence.requirements) == len(STRONG_FIT.requirements)


def test_relocation_required_is_capped():
    fit = steps.compute_fit(WEAK_FIT)
    assert fit.score == 3  # the evidence alone would score well above it
    assert "relocation max 3" in fit.breakdown


def test_rescore_keeps_the_previous_requirement_wording():
    previous = steps.compute_fit(STRONG_FIT).evidence
    reworded = STRONG_FIT.model_copy(
        update={
            "requirements": [
                Requirement(text=f"reworded {i}", type="preferred", evidence="none")
                for i, _ in enumerate(STRONG_FIT.requirements)
            ]
        }
    )
    fit = steps.compute_fit(reworded, previous=previous)
    assert [r.text for r in fit.evidence.requirements] == [r.text for r in previous.requirements]
    assert [r.type for r in fit.evidence.requirements] == [r.type for r in previous.requirements]
    assert {r.evidence for r in fit.evidence.requirements} == {"none"}  # the new judgment


def test_assess_fit_sends_only_the_scoring_sections_of_the_profile():
    seen = {}

    def answer(jd):
        return STRONG_FIT

    llm = FakeLLM(answer)
    original = llm.structured

    def spy(*, system, prompt, schema):
        seen["prompt"] = prompt
        return original(system=system, prompt=prompt, schema=schema)

    llm.structured = spy
    steps.assess_fit(
        JD, "resume", SYNTHETIC_PROFILE + "\n## Email sources\nsecret@example.com\n", llm
    )
    assert "## Target roles" in seen["prompt"] and "## Location" in seen["prompt"]
    assert "secret@example.com" not in seen["prompt"]


def test_profile_without_a_scoring_section_is_an_error():
    with pytest.raises(profile.ProfileError, match="Location"):
        profile.sections("# Job search profile\n\n## Target roles\n- Role families: x\n")


def _counting_llm(answers: list[FitAssessment]) -> FakeLLM:
    it = iter(answers)
    return FakeLLM(lambda jd: next(it))


def test_rescore_with_a_different_requirement_count_retries_once():
    previous = steps.compute_fit(STRONG_FIT).evidence
    short = STRONG_FIT.model_copy(update={"requirements": STRONG_FIT.requirements[:1]})
    llm = _counting_llm([short, STRONG_FIT])
    steps.assess_fit(JD, "resume", SYNTHETIC_PROFILE, llm, previous=previous)
    assert llm.calls == ["structured", "structured"]


def test_rescore_that_still_mismatches_raises():
    previous = steps.compute_fit(STRONG_FIT).evidence
    short = STRONG_FIT.model_copy(update={"requirements": STRONG_FIT.requirements[:1]})
    with pytest.raises(steps.RescoreMismatch):
        steps.assess_fit(
            JD, "r", SYNTHETIC_PROFILE, _counting_llm([short, short]), previous=previous
        )


def test_no_gaps_on_a_job_that_falls_short_gets_one_more_try():
    gapless = WEAK_FIT.model_copy(update={"top_gaps": []})
    llm = _counting_llm([gapless, WEAK_FIT])
    assessment = steps.assess_fit(JD, "resume", SYNTHETIC_PROFILE, llm)
    assert llm.calls == ["structured", "structured"]
    assert assessment.top_gaps == WEAK_FIT.top_gaps


def test_no_gaps_twice_is_kept_and_a_full_match_needs_none():
    gapless = WEAK_FIT.model_copy(update={"top_gaps": []})
    llm = _counting_llm([gapless, gapless])
    assert steps.assess_fit(JD, "resume", SYNTHETIC_PROFILE, llm).top_gaps == []
    assert llm.calls == ["structured", "structured"]

    every_strong = FakeLLM()  # STRONG_FIT: every requirement strong, no gaps
    steps.assess_fit(JD, "resume", SYNTHETIC_PROFILE, every_strong)
    assert every_strong.calls == ["structured"]


def test_prompt_names_every_rubric_category():
    """A category added to the rubric fails this until the prompt explains it."""
    _, body = prompts.load("fit_scoring")
    categories = (
        set(rubric.EVIDENCE_CREDIT)
        | set(rubric.TITLE_CREDIT)
        | set(rubric.ARRANGEMENT_CREDIT)
        | {"required", "preferred"}
    )
    missing = sorted(c for c in categories if f"`{c}`" not in body)
    assert not missing, f"fit_scoring.md doesn't define: {missing}"


def test_assessment_cannot_carry_a_score():
    assert "score" not in FitAssessment.model_fields
    assert set(EvidenceTable.model_fields) - {"mode"} <= set(FitAssessment.model_fields)
