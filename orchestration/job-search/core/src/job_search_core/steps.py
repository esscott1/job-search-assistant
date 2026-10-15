"""Steps: the units of work. Each takes plain inputs plus the ports it needs.

Steps do not touch the tracker and do not decide what runs next — that is the job of
`usecases` (recording results) and the orchestrator (sequencing).
"""

from __future__ import annotations

from . import policy, prompts
from .domain import FitResult, Job, NeedsHuman
from .ports import JDFetcherPort, LLMPort


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


def score_fit(jd_text: str, resume_text: str, llm: LLMPort) -> FitResult:
    _, system = prompts.load("fit_scoring")
    prompt = (
        f"<resume>\n{resume_text}\n</resume>\n\n"
        f"<job_description>\n{jd_text}\n</job_description>\n\n"
        "Score the fit and list the top three gaps."
    )
    return llm.structured(system=system, prompt=prompt, schema=FitResult)


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
