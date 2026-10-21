"""Steps: the units of work. Each takes plain inputs plus the ports it needs.

Steps do not touch the tracker and do not decide what runs next — that is the job of
`usecases` (recording results) and the orchestrator (sequencing).
"""

from __future__ import annotations

import json

from . import policy, profile, prompts, scoring
from .domain import EvidenceTable, FitAssessment, FitResult, Job, NeedsHuman, Requirement
from .ports import JDFetcherPort, LLMPort


class RescoreMismatch(ValueError):
    """A rescore came back with a different number of requirements than the last run."""


def fetch_jd(job: Job, fetcher: JDFetcherPort) -> str | NeedsHuman:
    if policy.looks_like_real_jd(job.jd_text):
        return job.jd_text  # already have it (e.g. supplied manually earlier)
    result = fetcher.fetch(job)
    if isinstance(result, NeedsHuman):
        return result
    if not policy.looks_like_real_jd(result):
        return NeedsHuman(
            kind="manual_jd",
            job_id=job.id,
            reason="Fetched page did not contain a usable job description",
            payload={"url": job.url, "chars": len(result or "")},
        )
    return result


def assess_fit(
    jd_text: str,
    resume_text: str,
    profile_text: str,
    llm: LLMPort,
    previous: EvidenceTable | None = None,
) -> FitAssessment:
    """The model's judgment: an evidence table and the top gaps. Never a score.

    On a rescore (`previous` given), the model must judge the same requirements again. If it
    returns a different number of them, it gets one more try before RescoreMismatch.
    """
    _, system = prompts.load("fit_scoring")
    prompt = (
        f"<candidate_profile>\n{profile.sections(profile_text)}\n</candidate_profile>\n\n"
        f"<resume>\n{resume_text}\n</resume>\n\n"
        f"<job_description>\n{jd_text}\n</job_description>\n\n"
    )
    if previous and previous.requirements:
        listed = [{"text": r.text, "type": r.type} for r in previous.requirements]
        prompt += (
            f"<previous_requirements>\n{json.dumps(listed, indent=1)}\n</previous_requirements>\n\n"
            "This is a rescore: return exactly these requirements, in this order, with the same "
            "text and type, and judge only their evidence again.\n\n"
        )
    prompt += "Assess the fit."

    assessment = llm.structured(system=system, prompt=prompt, schema=FitAssessment)
    if previous and previous.requirements:
        expected = len(previous.requirements)
        if len(assessment.requirements) != expected:
            retry = f"{prompt}\n\nYour last answer had {len(assessment.requirements)} "
            retry += f"requirements; return exactly {expected}."
            assessment = llm.structured(system=system, prompt=retry, schema=FitAssessment)
            if len(assessment.requirements) != expected:
                raise RescoreMismatch(
                    f"rescore returned {len(assessment.requirements)} requirements, "
                    f"expected {expected}"
                )
    return assessment


def compute_fit(assessment: FitAssessment, previous: EvidenceTable | None = None) -> FitResult:
    """Deterministic: build the evidence table and score it with the shared rubric.

    A JD was read, so the table is Tier 2. On a rescore the previous run's requirement text
    and type are kept, so a changed score comes from changed evidence, not a reworded list.
    """
    requirements = assessment.requirements
    if previous and len(previous.requirements) == len(requirements):
        requirements = [
            Requirement(
                text=old.text,
                type=old.type,
                evidence=new.evidence,
                resume_evidence=new.resume_evidence,
            )
            for old, new in zip(previous.requirements, requirements, strict=True)
        ]
    table = EvidenceTable(
        mode="tier2",
        title_seniority=assessment.title_seniority,
        work_arrangement=assessment.work_arrangement,
        requirements=requirements,
    )
    result = scoring.score_evidence(table)
    version, _ = prompts.load("fit_scoring")
    return FitResult(
        score=result.score,
        top_gaps=assessment.top_gaps,
        rationale=assessment.rationale,
        breakdown=result.breakdown,
        rubric_version=result.rubric_version,
        prompt_version=version,
        evidence=table,
    )


def tailor_resume(jd_text: str, resume_text: str, fit: FitResult, llm: LLMPort) -> str:
    _, system = prompts.load("tailor_resume")
    gaps = "\n".join(f"- {g}" for g in fit.top_gaps)
    prompt = (
        f"<master_resume>\n{resume_text}\n</master_resume>\n\n"
        f"<job_description>\n{jd_text}\n</job_description>\n\n"
        f"<known_gaps>\n{gaps}\n</known_gaps>\n\n"
        "Write the tailored resume."
    )
    return llm.text(system=system, prompt=prompt)
