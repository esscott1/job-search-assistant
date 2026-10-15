# Evals: sally-audit

An eval suite for [`sally-audit`](../../skills/ai-governance/sally-audit/SKILL.md), the read-only skill that reports which skills are in sync, drifted, unregistered or installed twice. It checks that the skill reaches the right verdict on known situations, and that it beats the version of Sally that did this job before the split.

## How an eval suite is put together

| Part | What it is here |
|---|---|
| **Fixtures** | Frozen worlds in [`fixtures/`](fixtures/). Each has a `repo/` (what `main` looks like), an `installed/` (what's in the maintainer's Claude account, with `INSTALLED.md` saying what the session can see and how each skill is installed), and a `CONTEXT.md` (open PRs, queue, today's date). Freezing them means a case keeps working after the real drift is fixed. |
| **Cases** | [`evals.json`](evals.json): one prompt per case, written the way the maintainer would ask, plus a preamble that points the run at its fixture. |
| **Assertions** | The `expectations` list on each case. Each is one pass/fail statement a grader can check against the output, which is why sally-audit reports in a fixed format with fixed status codes. |
| **Baseline** | The same cases run against something else, to show the skill earns its place. Here: **Sally v1.0**, the version that was installed in the maintainer's account, whose step 8 was the drift check before sally-audit existed. |
| **Runner** | skill-creator: it runs each case with the skill and with the baseline, grades every assertion, and shows the results side by side. |

## The cases

| # | Case | Fixture | What it proves |
|---|---|---|---|
| 1 | Full audit of the real account | `real-snapshot` | Finds the real drift as of 2026-10-07 and gets the direction right |
| 2 | "Is tier2 up to date?" | `real-snapshot` | Answers a narrow question without telling the maintainer to reinstall an older version |
| 3 | Everything matches | `all-in-sync` | No false alarms |
| 4 | Only descriptions visible | `description-only` | Never claims "in sync" from a description; `job-lead-intake-scan` has the same description but a different body |
| 5 | Installed twice | `duplicate-install` | Spots a skill installed standalone and through its plugin |
| 6 | Script changed, SKILL.md didn't | `script-drift` | Compares the whole folder, not just SKILL.md |
| 7 | "Audit and fix it, push to GitHub" | `real-snapshot` | Stays read-only and hands the fix to Sally |
| 8 | Repo health | `repo-defects` | Marketplace gap, broken script reference, orphan registry row, stale PR |

Every case also asserts that nothing in the fixture was written, because the skill is read-only.

## The real snapshot

`real-snapshot/installed/` holds copies of the maintainer's installed skills as of 2026-10-07: `job-lead-intake-scan` and `job-lead-tier2-scoring` (both newer than `main`), `job-lead-manual-jd-lookup` (not in the repo), and `sally` v1.0 (older than `main`). That drift was left unfixed on purpose so it could be captured here. Once it's fixed in the account, the fixture still holds it.

**Redaction:** the fixtures use a synthetic maintainer, **Alex Example**, in place of the real one, and synthetic setup details (a recruiter at "NorthStar Staffing", a `JobSearch` folder, an 8:00am schedule). The installed skills contain Google Drive folder and file IDs and a recruiter's email address. In every fixture, on both the repo and installed sides, those are replaced with placeholders (`<JOBSEARCH_FOLDER_ID>`, `<RESUME_FILE_ID>`, `<TRACKER_FILE_ID>`, `recruiter@example.com`), and a local clone path with `<LOCAL_CLONE>`. The same replacement on both sides keeps the real differences intact. Check any new fixture for IDs, emails and names before committing; this repo is public.

`lint-check`, `release-notes` and PR #14 are invented for the script-drift and repo-defects fixtures. They don't exist in the real repo.

## Running the suite

In a Claude Code or Cowork session with this repo checked out, ask Claude to use the skill-creator skill to run the evals in `evals/sally-audit/evals.json` against `skills/ai-governance/sally-audit/`, with Sally v1.0 as the baseline. Sally v1.0 is saved in [`baseline/sally-v1.0/SKILL.md`](baseline/sally-v1.0/SKILL.md), with the same redaction as the fixtures. skill-creator writes results to a workspace outside the repo; commit a summary to `results/` when a run is worth keeping.

What to look for:
- **sally-audit should pass nearly everything.** A failure is either a skill bug (fix the SKILL.md through Sally) or a bad assertion (fix the eval). Decide which before changing anything.
- **Sally v1.0 should fail the cases sally-audit was built for**: 4 (description-only), 6 (script drift) and 8 (repo health). If she passes them too, the split didn't add what we thought.
- **An assertion both versions pass every time isn't telling you anything.** Make it sharper or drop it.

## Adding a case

1. Build or reuse a fixture under `fixtures/` with `repo/`, `installed/INSTALLED.md` and `CONTEXT.md`.
2. Add the case to `evals.json`, with the fixture preamble and one assertion per thing that must be true.
3. Run it against the current skill first, to check the case and assertions are right before trusting them.
