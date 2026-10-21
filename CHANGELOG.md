# Changelog

Versions follow the pre-1.0 policy in [`CLAUDE.md`](CLAUDE.md): until 1.0.0, a change that breaks existing users bumps the minor version and anything else bumps the patch. 1.0.0 will be the first release meant for general use.

## job-search-assistant 0.4.5

- `job-fit-rubric`: `score.py` is reformatted to 100 columns, with no change to how it scores; its unit tests pass unchanged. The repository's code-defined pipeline now keeps an identical copy, checked by a test ([ADR 0003](docs/adr/0003-shared-rubric.md)). Updating the installed plugin is optional.

## job-search-assistant 0.4.4

- **"reset my job tracker"** (`job-tracker-cleanup`): start fresh with an empty Job Log. After you confirm, every row moves to the Archive, whatever its status. Nothing is deleted: saved job descriptions, fit reports and tailored resumes stay in their Drive folders, your profile and full resume aren't touched, and any row can be restored. Reinstall the plugin to pick it up.
  - The Archive gains an **Archive Reason** column: `stale` from the weekly cleanup, `reset` from a reset. Cleanup adds it to an existing Archive; older rows stay blank, which means `stale`.
  - Intake leaves rows archived by a reset out of dedup, so a job still in your alerts comes back as a new row with a new ID. Jobs archived as stale stay out, as before. The catch-up window is based on the Job Log only, so the first scan after a reset looks back the usual 7 days.
  - Restoring a row whose job is already back in the Job Log says so and asks before adding a second copy.

## job-search-assistant 0.4.3

- Open postings are no longer read as filled. Some career platforms put the whole job description in data embedded in the page and ship a hidden "this position has been filled" banner on every job page, so a page reader that drops scripts saw an open job as filled, with no description. Reinstall the plugin to pick up the fix.
  - `job-tracker`: new **Reading a posting page** rules, shared by every skill that opens a posting. A posting is closed only on hard evidence: a 404 or 410, a redirect away from the posting, an expired `validThrough`, gone from the company's own feed, or a closure notice next to the job's own description where hidden elements are left out. A banner on a page with no description, and boilerplate such as "will remain active until the position is filled", never count. Every closed call records its evidence in the row.
  - New `read_posting.py` reads a posting's JSON-LD or embedded job data (description, pay, location, posted date) and reports `open`, `closed`, `unknown` or `unreachable`. When code execution can't reach the site, the skills fall back to a plain fetch under the same rules.
  - `job-lead-intake-scan` reads posting pages this way and skips a lead as closed only on that evidence, listing each one in its summary. `job-lead-tier2-scoring` sets `T2-closed` only on it; a banner-only page goes to `T2-pending-manual`. `job-lead-manual-jd-lookup` tries `read_posting.py` before opening a browser.
- Rows already marked `T2-closed` by mistake: tick **Run Tier 2** again to re-read them.

## job-search-assistant 0.4.2

- Marketplace category set to Productivity (Development for `ai-governance`), and the plugin's description reworded to say "job openings" instead of "leads". No skill changes; update the plugin to see the new listing.

## job-search-assistant 0.4.1

- `job-search-profile`: setup is brief and menu-driven, so it works on a phone. Reinstall the plugin to pick it up.
  - Each message asks one thing in at most three short lines, with choices to tap (Claude Code's multiple-choice prompt) or numbers to reply with. Answers are suggested from the full resume, the folder's files and Gmail.
  - A new order of 9 steps starts with the folder, and says it holds the tracker, profile, full resume, job descriptions and tailored resumes.
  - The full resume can be attached or pasted (.md, .docx or .pdf). It's arranged in the format in the new `full-resume-format.md`, confirmed, and saved to the folder as text. Originals aren't copied to Drive.
  - A style file (.md) can be attached as well as a Word template, and is checked with the renderer before it's saved.
  - Later changes are confirmed as one before → after line, and reviews show a short overview.
- `check_content.py --inventory` on its own lists the employers and roles a full resume's headings describe, or says it found none.
- The profile's format is unchanged.

## job-search-assistant 0.4.0

- `tailored-resume-builder`: every build also saves the resume as a **Google Doc** in the job's company folder in Drive, and the tracker's Tailored Resume cell links to it. It's there wherever the build ran: in the cloud, or on a computer that's been switched off since. Reinstall the plugin to pick it up.
  - `render_resume.py --html` writes the resume as HTML that Drive converts into a Google Doc. It's text, so it goes through the Drive connector safely; the .docx and PDF still never do.
  - New `check_doc_text.py` reads the Doc back and checks it holds every line of the resume, since the HTML passes through the model on its way to Drive.
  - The .docx and PDF are unchanged and stay the page-checked versions: written to the synced folder with Google Drive for desktop, or handed over as downloads. Google lays out the Doc itself, so its page breaks can differ slightly, and a long date range can wrap.
- `job-tracker`: Tailored Resume links to the Google Doc; the PDF link and the "(syncing to Drive)" and "(download; …)" notes remain only for when no Doc could be made.

## job-search-assistant 0.3.0

- `tailored-resume-builder`: new rules for what a tailored resume shows. Reinstall the plugin to pick them up.
  - **Length:** at most 3 pages by default, instead of 2. Ask for fewer for a particular resume ("keep it to 2 pages"). A 3rd page must be at least half full; otherwise the resume is trimmed to 2 pages, never padded. `render_resume.py` takes `--max-pages` and reports how full the last page is (`last_page_fill`, measured with `pdftotext`).
  - **No company descriptions.** Employers show their name, location and dates only, even when the full resume describes the company. `render_resume.py` rejects a `description` in `content.json`.
  - **Dates once.** A role's dates and location are shown only where they differ from the employer's, so a single-role employer's dates no longer appear twice.
  - **Every role has a line:** a summary or a bullet. `render_resume.py` rejects a role with neither.
  - **Older roles:** a role that ended more than 15 years ago may be left out when it isn't relevant to the job; every other role stays. The end-of-run summary lists what was left out.
  - New `check_content.py` checks `content.json` against the full resume before delivery: employers, titles and dates match, no role from the last 15 years is missing, and the rules above hold.

## job-search-assistant 0.2.2

- Evals for `job-lead-intake-scan` and `job-tracker-cleanup`.
  - **Intake:** new leads from email logged at the top with the right IDs, canonical links and T1 scores; Never-interested jobs, duplicates under other tracking parameters, archived jobs and sign-in tokens never written; a career site read from its feed; nothing to scan.
  - **Cleanup:** only untouched rows past the archive age are archived, in one revision-checked batch; the Archive tab is created when missing; the archive age is honoured; a row is restored.
- The eval stubs gain Gmail and web-fetch stand-ins and Sheets batch operations. Every eval is self-contained: test data lives in the eval folder, and nothing is fetched from the network or this repository. Skills are unchanged.

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
