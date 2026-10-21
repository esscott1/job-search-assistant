# ADR 0003: One rubric; the model judges, code computes

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

Both approaches score how well a job fits a full resume, but until now they did it differently:

- **The Claude skills plugin** splits the work. The model reads the job description and the resume and fills in an evidence table: each requirement quoted from the job description, marked required or preferred, and judged strong, partial or none, plus title fit and work arrangement. `job-fit-rubric/score.py` turns that table into a 1–10 score with fixed weights and caps, and a breakdown that shows the arithmetic.
- **The LangGraph pipeline** asked the model for the number directly (`prompts/fit_scoring.md`, `domain.FitResult`), with no weights, caps or breakdown.

So a difference between the two scores could come from the model's judgment or from the arithmetic, and there was no way to tell which. Comparing the approaches, which is the point of the roadmap's milestone 5, needs the arithmetic held constant.

## Decision

- **The model judges and code computes, in both approaches.** The only model output that feeds a score is the evidence table. The score itself always comes from the rubric.
- **The plugin's `score.py` is the source of truth.** It's the deployed copy, and its unit tests, the `job-fit-rubric` documentation and the gold eval fixtures all use it. A rubric change is reviewed as a plugin change, and plugin changes carry a version bump.
- **`core/src/job_search_core/rubric.py` is an exact copy, not an import.** An installed plugin contains only its own folder, so it can't import from `orchestration/`. `core` is an installable package, so it can't import from `skills/`. A generated copy or a build-time include would add tooling without removing the second file.
- **Tests keep the copies identical** (`core/tests/test_rubric.py`):
  - the files must match, and the failure message names the fix;
  - the typed `EvidenceTable` must accept exactly the categories the rubric's credit tables define;
  - every gold evidence table must score the same through `scoring.score_evidence` as through the plugin's script.

  The `job-search CI` workflow also runs on changes to `score.py` and the gold fixtures, so a plugin-only change can't skip the check.
- **`core` handles the rubric through types.** `EvidenceTable` and `RubricScore` (in `domain.py`) wrap it, and `scoring.score_evidence` is the only code that touches the rubric's untyped dicts.

## Consequences

- Once LangGraph scores through the rubric (roadmap milestone 3), a score difference between the approaches comes only from judgment, meaning which requirements the model found and how it rated each one. That's what the milestone 5 comparison measures.
- A rubric change is one edit to `score.py`, copied to `core` in the same PR. The tests fail until the copy is made.
- `score.py` follows the orchestration workspace's formatting (ruff, 100 columns), so the copy passes the workspace's format check unchanged.
- The rubric version (`RUBRIC_VERSION`, v1.1 today) appears in every score breakdown in both approaches, so a score always says which arithmetic produced it.
