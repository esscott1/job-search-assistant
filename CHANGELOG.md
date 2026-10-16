# Changelog

Versions follow the pre-1.0 policy in [`CLAUDE.md`](CLAUDE.md): until 1.0.0, a change that breaks existing users bumps the minor version and anything else bumps the patch. 1.0.0 will be the first release meant for general use.

## job-search-assistant 0.2.2

- Evals for `job-lead-intake-scan` and `job-tracker-cleanup`.
  - **Intake:** new leads from email logged at the top with the right IDs, canonical links and T1 scores; Never-interested jobs, duplicates under other tracking parameters, archived jobs and sign-in tokens never written; a career site read from its feed; nothing to scan.
  - **Cleanup:** only untouched rows past the archive age are archived, in one revision-checked batch; the Archive tab is created when missing; the archive age is honoured; a row is restored.
- The eval stubs gain a Gmail stand-in and Sheets batch operations. Skills are unchanged.

## job-search-assistant 0.2.1, ai-governance 0.1.3

- No `.claude-plugin` folder sits below either plugin's root any more. The eval stub plugins declare their mock servers in a bare `.mcp.json` (no manifest), and sally-audit's frozen test worlds name their manifest folders `_claude-plugin`, which the case prompts explain. A test keeps it that way. Nested manifest folders are suspected of breaking the Claude app's marketplace sync, though that isn't confirmed. Skills are unchanged.

## job-search-assistant 0.2.0

**Breaking:** tailored resumes take their look from a text style file instead of a Word template. Say "set up my resume style" once, and attach the Word template you were using.

- `job-search-profile`: a resume style step. You attach a Word template, and `extract_style.py` converts its page setup, fonts, colours and layout into `resume-style.md`. The skill previews the result with your own resume content, goes over uncertain guesses and anything that can't be carried over (pictures, text boxes, columns), and saves only once you confirm. "Make the headings navy" and similar requests edit the style. A new **Candidate → Resume style** setting replaces **Resume template**, and a new optional **Tracker → Local Drive folder** names where Google Drive for desktop syncs your folder.
- `tailored-resume-builder`: renders with `render_resume.py` from your style file, or the default. No Word file is downloaded or uploaded through the Drive connector any more, because copying a file as base64 corrupted templates and uploads. On your computer with a Local Drive folder, the .docx and PDF are written straight into the job's folder. From the cloud, they're handed over as downloads. `build_resume.py` (Job-Seeker-6 only) is retired.
- `job-tracker`: **Tailored Resume** can hold a file name marked `(syncing to Drive)` or `(download; add to <folder>/)` until a link is available.
- `extract_style.py` adds two layout settings, header order and section heading alignment.

## job-search-assistant 0.1.6

- `tailored-resume-builder` gains `render_resume.py`, which builds a resume .docx (and PDF) from scratch, using a small text **style file** for the user's look. The style file sets page size, margins, fonts, colours, section order and titles, the competencies grid or list, bullets and date alignment. No Word template is needed. `default-style.md` is a clean single-column default, and `resume-style-format.md` documents the format. The skill doesn't use it yet; the next releases add converting a user's Word template to a style file, and switch the skill over.

## job-search-assistant 0.1.5

- `tailored-resume-builder`: a tailored resume is at most 2 pages, not exactly 2. When the full resume doesn't hold two pages of relevant, true content, a shorter resume is the right result; it's never padded. When LibreOffice isn't available to count pages, the .docx is still saved and the page count is reported as unverified. `build_resume.py` warns only when a resume runs over 2 pages.

## job-search-assistant 0.1.4, ai-governance 0.1.2

- Every eval suite now uses the native `claude plugin eval` format, inside its plugin. The old skill-creator suites under the repo-root `evals/` are gone.
- `ai-governance` gains `evals/` with the eight sally-audit cases. Each case's frozen repo-and-install world lives in the case, and is read through `add_dirs`.
- `job-search-assistant` gains four tailored-resume-builder cases: a resume built for a pasted JD, no invented skills, a missing full resume, and a ticked row with no saved JD. A synthetic resume template (same structure as the real one, placeholder text only) lets these cases build a real .docx, and lets `build_resume.py`'s unit tests run in CI instead of being skipped.
- `sally-audit`: `"skills": ["./"]` is not a marketplace mismatch; only a category that lists its skill folders one by one can miss one. The eval run caught the earlier wording flagging it.

## job-search-assistant 0.1.3, ai-governance 0.1.1

- `job-search-assistant` now ships an eval suite in `evals/`, in the format `claude plugin eval` runs. It has two cases to start: the resume builder asks for a job description instead of guessing, and Tier 2 with nothing ticked reads the profile and tracker and stops. A small stub plugin stands in for the Google Drive and Sheets connectors, so cases can check exactly what a skill reads and writes.
- The plugin's manifest lists each skill folder instead of `"./"`, so `evals/` isn't loaded as part of the plugin. A test fails if a skill folder is missing from the list.
- `sally` adds new skills to that list, and `sally-audit` reports a skill folder missing from it.

## job-search-assistant 0.1.2

- `job-lead-intake-scan`: also scans the **Career sites** in the profile, reading each one by the method setup recorded (public job feed, listing page, or site-scoped web search). Each site logs at most **Career site leads per run** new rows (default 15). A site that can't be read is reported, not retried in a browser. Intake now stops only when the profile has no email sources and no career sites, and still scans career sites when the Gmail connector isn't connected.
- `job-tracker`: Source covers career sites, and the email-only columns stay blank on career-site rows. Dedup by company and title also catches the same job from an alert email and a career site.
- `canonical_url.py`: canonical forms for Workday, iCIMS, Ashby and SmartRecruiters posting links, and Greenhouse embed links.

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
