# Changelog

Versions follow the pre-1.0 policy in [`CLAUDE.md`](CLAUDE.md): until 1.0.0, a change that breaks existing users bumps the minor version and anything else bumps the patch. 1.0.0 will be the first release meant for general use.

## job-search-assistant 0.1.1

- `job-search-profile`: the interview now has a guided **Job sources** step. It checks for the Gmail connector and explains how to add it when it's missing. It also adds an optional **Career sites** section: name a company or give a careers URL, and the skill finds the official page, confirms it with you, and tests how it can be read from the cloud (a public job feed, the listing page, or a site-scoped web search). Adds the optional Housekeeping setting **Career site leads per run** (default 15). Existing profiles keep working unchanged.

## 0.1.0 — first public pre-release

**`job-search-assistant` plugin 0.1.0**
- `job-search-profile`: interviews the user and maintains `job-search-profile.md` in their Google Drive (name, full resume, tracker, target roles, home ZIP and commute radius, relocation, email sources, housekeeping). Every other skill reads its settings from this file.
- `job-lead-intake-scan`: scans the email sources in the profile on a daily schedule, screens leads against the profile's target roles and location, and logs new ones at the top of the tracker sheet with a Tier 1 score and a canonical link for dedup.
- `job-lead-tier2-scoring`: scores only the rows the user ticks in **Run Tier 2**, against the real job description found by web search. Saves the JD and a fit report per run; re-ticking rescores the saved JD against the current resume.
- `job-lead-manual-jd-lookup`: reads job descriptions that web search can't reach in the user's own browser.
- `tailored-resume-builder`: builds a 2-page tailored resume for rows ticked in **Build Resume**, from the saved JD and the full resume, without inventing experience.
- `job-tracker-cleanup`: weekly, moves rows nobody acted on to an Archive tab; nothing is deleted.
- `job-fit-rubric` (rubric v1.1) and `job-tracker`: the shared scoring rubric with deterministic arithmetic, and the tracker contract every skill follows.

**`ai-governance` plugin 0.1.0**
- `sally`: lands every skill change as a reviewed pull request and keeps the registry and marketplace current.
- `sally-audit`: a read-only status and drift report comparing the repo with the installed skills.
