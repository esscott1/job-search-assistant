# Getting started with JobSearchAssistant

A step-by-step walkthrough of the `job-search-assistant` plugin, from installing it to sending a tailored resume. Plan on about 20 minutes for setup; after that, the daily routine takes a few minutes.

**How it works in one paragraph.** Each day the plugin reads your job-alert emails and the career sites of companies you choose, and logs promising leads to a Google Sheet with a quick fit score. You tick the ones worth a closer look; it finds each real job description, scores it against your full resume, and shows every gap. If a gap is something you've done but left off your resume, you add it and rescore. When you're happy, you tick another box and it builds a tailored resume of at most two pages. You decide what gets the expensive work; the plugin does the reading, scoring and bookkeeping.

## 1. What you need

- **Claude with plugins, connectors and scheduled tasks** (the Claude desktop app or claude.ai).
- **Code execution turned on** in Claude's settings (code execution / file creation). The scoring, dedup and resume-building steps are small Python scripts.
- **Connectors:** **Google Drive** (for your profile, resume and the files the plugin saves) and **Google Sheets** (for the tracker), plus **Gmail** if you want job-alert email scanned. Setup checks for Gmail and tells you how to add it.
- **Web search** turned on, if you want company career sites watched.
- **Optional:** **Claude in Chrome**, signed in to LinkedIn, or the desktop app's built-in browser. It's used only for job descriptions that web search can't reach, usually LinkedIn-only postings.
- **Your full resume as one Markdown file**, for example `Full-Resume.md`. It covers your **whole** career, not a two-page version: every role, project, tool, certification and accomplishment. Every score and every tailored resume comes only from this file, so anything missing from it shows up as a gap.
- **Optional, for tailored resumes:** a Word resume (.docx) whose look you like. Setup converts its fonts, colours and layout once into a small style file; without one, the plugin's clean default style is used.
- **Optional: Google Drive for desktop.** If your Drive is synced to your computer, resumes built from the desktop app are written straight into your job folders.
- **At least one job source:** job-alert emails arriving in Gmail (for example LinkedIn job alerts for your target titles and location; recruiter emails and job-board alerts work too), or a list of companies whose career sites you want watched, or both.

## 2. Install the plugin

**Claude app:**
1. Customize > Plugins > add a marketplace: `esscott1/job-search-assistant`.
2. Install **`job-search-assistant`**.

The `ai-governance` plugin in the same marketplace is for people who maintain or modify the skills; you don't need it to use the job search.

**Claude Code:**
```
claude plugin marketplace add esscott1/job-search-assistant
claude plugin install job-search-assistant@esscott
```

## 3. Set up your profile and tracker

1. **Make a Google Drive folder** for your job search, for example `Job Search`. Upload your `Full-Resume.md` into it.
2. **Start a new chat and say "set up my job search."** The `job-search-profile` skill interviews you one section at a time:
   - **Candidate:**
     - your name;
     - the full-resume file name;
     - **your resume style:** attach the Word resume whose look you want, or say no for the default. It converts the template, shows a preview with your own resume content, tells you anything it couldn't carry over (pictures, text boxes, columns), and saves `resume-style.md` once you confirm;
     - a file-name prefix for tailored resumes, such as `Jane_Example_Resume` (it proposes one).
   - **Tracker:** the Google Sheet's name (for example `Job_Search_Tracker`) and the Drive folder it's in. If the sheet doesn't exist yet, it offers to create it, with all the columns, checkboxes, a Status dropdown and a Status Guide tab. If you use Google Drive for desktop, it also asks where that folder appears on your computer.
   - **Target roles:**
     - the kinds of roles you want;
     - the level;
     - adjacent roles that count as a partial match;
     - anything to always discard.
   - **Location:**
     - your home area;
     - your **ZIP code**;
     - your **maximum one-way commute in miles**;
     - whether remote is fine;
     - whether you'd relocate (no / yes / only to certain places).
   - **Job sources:** where you want to find openings: job-alert email, specific companies' career sites, or both.
     - **Email:** it checks that the Gmail connector is connected (and explains how to add it if not), then finds a recent example of each alert email, confirms the sender address with you, and notes how to read it.
     - **Career sites:** name a company ("Acme") or paste its careers URL. It finds the official careers page, asks you to confirm it, and tests how it can be read from the cloud. If a site can't be read, it suggests that company's job-alert email instead.
   - **Housekeeping:** how long before untouched rows are archived (30 days), how many rows to score per run (10), and how many new leads to log per career site per run (15). The defaults are fine.
3. **Review the profile** it shows you and confirm. It saves **`job-search-profile.md`** to your folder.

Your settings live only in that file, in your own Drive. Change them any time in plain language ("add Indeed alerts", "I'd relocate to Austin now") and the skill shows each change before → after. You can also edit the file by hand.

## 4. Schedule the automatic parts

Create three scheduled tasks in the Claude app, at different times so they don't edit the sheet at the same moment:

| Task | When | Prompt |
|---|---|---|
| Intake | Daily, early morning | `Run job-lead-intake-scan` |
| Tier 2 scoring | Every 2-4 hours | `Run job-lead-tier2-scoring` |
| Cleanup | Weekly | `Run job-tracker-cleanup` |

The first intake run looks back 7 days. If runs were missed, it catches up as far as the newest row it already logged, up to 30 days.

## 5. Daily routine

1. **Review the new rows.** The newest leads are at the top of the Job Log. Each has a **Fit Score** from the alert email alone and the top **Gaps** next to it. Sort or filter however you like; the plugin always finds rows by ID.
2. **Tick Run Tier 2** on the rows worth a real look. The next Tier 2 run, or "run Tier 2 now":
   - finds the real job description on the company's or an ATS site (never LinkedIn directly) and saves it in a folder named for the company;
   - scores it against your full resume and fills in the new **Fit Score**, **Gaps** and a **Fit Report** link;
   - unticks the box.
3. **Open the Fit Report.** It lists every requirement in the job description, gaps first, with the line of your resume that supports each one, or "none".
4. **Fix false gaps.** If a gap is something you have done but didn't write down, add it to your full resume and tick **Run Tier 2** again. A rescore reuses the saved job description and the same requirement list, so a changed score comes only from your edit, and the new report lists what changed. Repeat as often as you like.
5. **If the description can't be reached** (Score Tier `T2-pending-manual`, usually a LinkedIn-only posting): at your computer, with Chrome signed in, say "run manual JD lookup". After that, rescores work from the cloud again.
6. **Build the resume.** When the remaining gaps are real, tick **Build Resume** and say "build ticked resumes". You get a .docx and PDF of at most 2 pages in your resume style (`_v2`, `_v3` if you rebuild, never overwritten). From the desktop app with Google Drive for desktop, they're written straight into the job's folder and the row links to the PDF; from the cloud, you download them and drop them into that folder. The run ends with the gaps it couldn't cover.
7. **Track your progress** with **Status** (Read and contemplating → Good fit / needs resume → Resume ready → Submitted → Interviewing → Rejected or Closed) and **Next Action / Notes**. The plugin never changes these.
8. **Each week**, cleanup moves rows still "Need to review" 30 days after they were found to an **Archive** tab. Nothing is deleted, and an archived job is never logged again. Say "restore JS-123" to bring one back.

## 6. What to say

| Say | What happens |
|---|---|
| "set up my job search" | First-time interview; writes your profile and creates the tracker if needed |
| "update my job search profile" / "show my job search profile" | Change or review your settings |
| "search for openings at Acme" / "watch https://careers.example.com/jobs" | Add a company career site to watch |
| "stop watching Acme" | Stop watching that career site |
| "run Tier 2 now" | Score every row ticked in Run Tier 2 right away |
| "rescore JS-123" | Score one row against your current resume, ticked or not |
| "run manual JD lookup" | Read unreachable job descriptions in your own browser |
| "build ticked resumes" / "build a resume for JS-123" | Build tailored resumes |
| "clean up the tracker now" / "restore JS-123" | Archive stale rows now / bring an archived row back |

## 7. Reading the tracker

- **Fit Score (1-10):** green 8-10 is strong, yellow 6-7 is workable with gaps, red 1-5 is a stretch. It comes from a fixed rubric:
  - 70% requirements, with a required item counting three times a nice-to-have;
  - 20% title and seniority;
  - 10% work arrangement.
  - A job that needs a move you won't make is capped at 3, and a score from the alert email alone is capped at 8.
- **Score Tier:**
  - `T1`: from the alert email only;
  - `T2`: real job description, found by web search;
  - `T2-manual`: real job description, read in your browser;
  - `T2-pending-manual`: web search couldn't reach it;
  - `T2-no-jd`: no description exists anywhere reachable;
  - `T2-closed`: the posting is closed or filled.
- **Score Breakdown:** where the description came from and the scorer's arithmetic, so every score can be checked.

## 8. Troubleshooting

| You see | What to do |
|---|---|
| "No job-search profile found" | Say "set up my job search" |
| `Profile setting "…" is blank` | Say "update my job search profile" and fill in that setting |
| `Tracker is missing the "…" column` | Add that header to row 1 of the Job Log (the exact names are in the [`job-tracker`](../skills/job-search-assistant/job-tracker/SKILL.md#columns) skill), or ask the profile skill to check your tracker |
| Too many leads you don't want | Tighten Target roles and "Never interested" in your profile, or remove a noisy email source |
| Nearby offices marked "Location unclear" | Add your ZIP code, or list nearby cities under "Commutable to" |
| The resume build fails | Run "build ticked resumes" from the desktop app on your computer; the builder needs python-docx, and LibreOffice for the PDF and page count |
| Resumes don't look like your template | Say "set up my resume style" and attach the template again, or describe the change ("make the headings navy", "use Garamond") |
| "Careers: … could not be read" in the intake summary | The site changed or blocked reading. Say "update my job search profile" and ask to re-test that site, or switch to its job-alert email |
| "email was skipped" in the intake summary | The Gmail connector isn't connected. Add it under Customize → Connectors |
| Ticking a box does nothing | Ticking only queues the row. The scheduled task picks it up, or say "run Tier 2 now" / "build ticked resumes" |
