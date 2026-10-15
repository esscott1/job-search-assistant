# JobSearchAssistant

The `job-search-assistant` plugin: skills that find job leads in your email, log them to a Google Sheet tracker with a quick Tier 1 fit score, score the leads you pick against your full resume, help you close gaps that are really just missing resume content, and build tailored resumes.

| Skill | Trigger | Depends on |
|---|---|---|
| [`job-search-profile`](job-search-profile/SKILL.md) | On demand: "set up my job search" the first time, then whenever something changes ("add a job alert sender", "search for openings at Acme", "my tracker moved") | Google Drive and Google Sheets connectors; Gmail to confirm email senders; web search and web fetch to find and test career sites |
| [`job-lead-intake-scan`](job-lead-intake-scan/SKILL.md) | A daily schedule | Gmail, Google Drive and Google Sheets connectors only. Runs in the cloud; no computer needed |
| [`job-lead-tier2-scoring`](job-lead-tier2-scoring/SKILL.md) | A schedule every 2-4 hours, scoring only rows ticked in **Run Tier 2**; or on demand for named rows | Web search and fetch, Google Drive and Google Sheets connectors. Cloud only, never LinkedIn |
| [`job-lead-manual-jd-lookup`](job-lead-manual-jd-lookup/SKILL.md) | On demand, at your computer, for rows Tier 2 marked `T2-pending-manual` | Your signed-in Chrome (for LinkedIn) or the desktop app's built-in browser, plus the Sheets connector |
| [`job-fit-rubric`](job-fit-rubric/SKILL.md) | Never on its own; loaded whenever a skill sets a Fit Score | Python 3 for `score.py` |
| [`job-tracker`](job-tracker/SKILL.md) | Never on its own; loaded by every skill that reads or writes the tracker | Python 3 for `canonical_url.py` |
| [`job-tracker-cleanup`](job-tracker-cleanup/SKILL.md) | A weekly schedule; or on demand to clean up now or restore a row | Google Sheets connector only. Runs in the cloud |
| [`tailored-resume-builder`](tailored-resume-builder/SKILL.md) | On demand only: "build ticked resumes" for rows ticked in **Build Resume**, a named row, or a pasted job description | Your full resume and a Word resume template in Drive, plus Python (`python-docx`, LibreOffice) |

## Getting started

The full walkthrough, from requirements and install to the daily routine and troubleshooting, is in [docs/getting-started.md](../../docs/getting-started.md).

Say **"set up my job search"**. The `job-search-profile` skill interviews you and writes **`job-search-profile.md`** to your Google Drive. It records your name, your full-resume file, where your tracker sheet is, the roles you're targeting, your home ZIP code and how far you'd commute, and which job-alert emails to scan. It's plain Markdown, like a CLAUDE.md: the skill keeps it up to date when you tell Claude something changed, and you can edit it by hand. If your tracker sheet doesn't exist yet, the skill offers to create it.

## How to use it

1. **Review the new rows each day.** Intake runs on its schedule and logs each new lead with a Tier 1 score from the alert email alone. Sort the Job Log by Fit Score and tick **Run Tier 2** on the leads worth a real look.
2. **Tier 2 scores them.** The scheduled run finds each ticked job's real description, saves it, scores it against your full resume, and unticks the box. The **Gaps** cell shows the top three; the **Fit Report** link opens the full list: every requirement with the evidence for it, gaps first.
3. **Close the gaps that aren't real.** If a gap is something you have done but left out of your full resume, add it there and tick **Run Tier 2** again. A rescore reuses the saved job description and the same requirement list, so a changed score comes from your edit, and the new fit report lists what changed since the last run. Repeat as often as you like.
4. **Build the resume.** When the gaps that remain are real, tick **Build Resume** and say "build ticked resumes". A 2-page .docx and PDF are saved in the job's folder, and the row links to the PDF.

Once a week, cleanup moves rows you never acted on (still "Need to review" more than 30 days after they were found, or the age set in your profile) to the **Archive** tab, so the Job Log stays short. Anything you've ticked, noted, moved to another status, or built a resume for stays put.

If Tier 2 can't reach a job description (Score Tier `T2-pending-manual`, usually a LinkedIn-only posting), run the manual lookup from your computer. Once it has saved the description, rescores work from the cloud again.

### What to say

| Say | What happens |
|---|---|
| "run Tier 2 now" | Scores every row ticked in Run Tier 2 without waiting for the schedule |
| "rescore JS-123" (or "run Tier 2 on JS-123") | Scores that row against your current resume, ticked or not. Uses the saved job description if there is one |
| "run manual JD lookup" | Reads the job description in your own browser for every `T2-pending-manual` row. Needs your computer on |
| "update my job search profile" (or just say what changed) | Changes the profile, showing each line before → after |
| "build ticked resumes" | Builds a tailored resume for every row ticked in Build Resume, then unticks it |
| "clean up the tracker now" | Archives stale rows without waiting for the weekly run |
| "restore JS-123" | Moves an archived row back to the top of the Job Log |
| "build a resume for JS-123" | Builds one for that row, ticked or not. Needs a saved job description, so run Tier 2 first |

To make Tier 2 fetch a job description again (for example, the posting changed), trash that row's `<ID>_JD.md` in Drive and tick **Run Tier 2**.

## Where things live

Everything lives in one Google Drive folder, the one you named for your tracker in your profile:

- **`job-search-profile.md`**: your settings (see Getting started).
- **The tracker**: a Google Sheet (named in your profile, `Job_Search_Tracker` by default). **Job Log** and **Status Guide** come with it; **Archive** is added by the first cleanup run. **Job Log** has one row per job, with new leads added at the top, newest first; **Status Guide** explains the statuses and the scoring and counts rows by status. **Archive** holds rows moved out of the Job Log by cleanup, with the date they were archived; it still counts for dedup, so an archived job isn't logged again. The full column list, and which skill writes each column, is in [`job-tracker`](job-tracker/SKILL.md#columns). Columns that only you change: **Status**, **Next Action / Notes**, and the two checkboxes, **Run Tier 2** and **Build Resume**.
- **Your full resume**: a Markdown file holding your whole career history, not a two-page selection. It's the only evidence the skills score against or build resumes from, and only you edit it.
- **A Word resume template**: the layout every tailored resume uses. Today that has to be a copy of the Job-Seeker-6 template, the only layout the resume builder supports.
- **One folder per company** (for example `Acme_Corp/`), created the first time a job there gets a full read. It holds `<ID>_JD.md` (the saved job description), one `<ID>_fit_r<n>_<date>.md` per scoring run, and any tailored resumes as .pdf and .docx, versioned `_v2`, `_v3` rather than overwritten.

**Only setup creates a tracker.** If the sheet in your profile isn't found, every skill stops and says so rather than starting a blank one. `job-search-profile` offers to create the folder and sheet during setup, and only with your yes.

Nothing about you is written into the skills: every skill reads your name, files, tracker, target roles, location rules and email sources from `job-search-profile.md`, and stops with a clear message if a setting it needs is blank.

## How it's built

The tracker is a Google Sheet edited in place through the Google Sheets connector, so every skill can update individual rows without replacing the file. `job-tracker` is its contract: which skill owns which column, how rows are found and added, how duplicates are caught, and the format of the per-job files. The other skills load it instead of each carrying their own copy of the Sheets rules.

### One rubric, split into judgment and arithmetic

Every skill that scores fit does it through `job-fit-rubric`. The model reads the job description and the full resume and fills in an evidence table: each requirement quoted from the job description, marked required or preferred, and matched to the resume as strong, partial or none, plus title fit and work arrangement. `score.py` turns that table into the 1-10 score with fixed weights (required qualifications count three times as much as nice-to-haves) and hard ceilings (a job that needs a move your profile rules out can't score above 3). The model's classifications stay visible and checkable, and the arithmetic is deterministic and unit-tested. The breakdown is written to each row's Score Breakdown column, so every score shows how it was reached.

### Why separate skills

The stages have different requirements. Intake and web-search scoring run unattended and must work when your computer is off; the manual lookup needs a live, signed-in browser session and only makes sense when you're at your computer; building a resume is always an explicit request. Splitting them means each skill's description names exactly when it applies, and none silently depends on something another doesn't need.

### The tiered-scoring idea

A week of job-alert email easily contains 40-80+ individual postings. Reading a full job description for every one of them isn't practical, so the pipeline screens cheaply first (title, company and location from the alert email) and escalates to a full read (web search first, your own browser as the last resort) only for leads worth the extra cost. Every row's **Score Tier** column says which tier produced its score (`T1`, `T2`, `T2-manual`, or why a job description couldn't be read), so trust in the number is explicit rather than assumed.

### You decide what gets the expensive read

The agent doesn't decide which leads are worth a full read; you do. Tick **Run Tier 2** on the rows you want, and the scheduled Tier 2 run picks up only those, unticks each one when it's done, and stamps the date. An empty queue costs one sheet read. The checkboxes are the human-in-the-loop gates: automation does the cheap screening and the bookkeeping, and your judgment decides where the costly work goes and when a resume is ready to build.

### Rescoring measures your resume, not the search

A rescore reuses the saved job description and the previous run's requirement list and only re-judges the evidence. Holding everything else fixed means the score change between runs comes from the edit you made to your resume, and each run is kept as its own fit report so the history is visible.
