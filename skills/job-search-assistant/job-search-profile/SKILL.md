---
name: "job-search-profile"
description: "On demand: sets up or updates the user's job-search profile, job-search-profile.md in their Google Drive. It holds their name, full-resume file, tracker sheet and folder, target roles, location and relocation rules, email sources and housekeeping settings. Use it the first time someone sets up the job-search plugin ('set up my job search'), and whenever they change something in chat ('add a job alert sender', 'I'd relocate to Austin now', 'my tracker moved'). Interviews the user for anything missing. The other job-search skills read the profile; they never write it."
---

# Job Search Profile

Every job-search skill in this plugin works from one file: **`job-search-profile.md`** in the user's Google Drive. It plays the part a CLAUDE.md plays for a codebase: plain Markdown that this skill writes and keeps current, and that the user can also edit by hand. Nothing about a particular user is written into the skills themselves; it all comes from here.

This skill creates the profile by interviewing the user, and updates it whenever they tell Claude something changed.

## Key files and systems
- **The profile:** a plain-text Markdown file named exactly `job-search-profile.md`, stored in the user's job-search folder. It's found by name (`search_files` with `title = 'job-search-profile.md'`), so its location never has to be configured. Drive search can't filter out trashed files, so this skill never leaves a trashed file with that name (see step 4).
- **Google Drive connector** to find, read, create, rename and trash files. Read the profile with `download_file_content` and base64-decode it: `read_file_content` can return an empty result for a Markdown file created in the last few minutes. **Google Sheets connector** to check the tracker.
- **`job-tracker` skill:** load it for the tracker's tab and column layout when checking or creating a tracker.

## The profile format
Keep this exact structure. Each setting is a `- Key: value` line under its section, so both people and skills can read it; add a short comment in parentheses after a value when it helps. Leave a value blank rather than inventing one.

~~~
# Job search profile

Maintained by the job-search-profile skill. You can edit it by hand: keep the
section headings and the "- Key: value" lines, and change the values.

Last updated: <YYYY-MM-DD>

## Candidate
- Name: <full name, as it should appear on file names>
- Full resume: <file name of the full career history in the job-search folder, e.g. Full-Resume.md>
- Resume template: <file name of the user's copy of the Job-Seeker-6 Word template, the layout tailored resumes use>
- Tailored resume prefix: <file-name prefix for tailored resumes, e.g. Jane_Example_Resume>

## Tracker
- Sheet name: <Google Sheet name, e.g. Job_Search_Tracker>
- Folder: <Drive folder path, e.g. My Drive/Job Search>
- Folder ID: <filled in by this skill>
- Sheet ID: <filled in by this skill>
- Time zone: <IANA time zone used for dates, e.g. America/Denver>

## Target roles
- Role families: <comma-separated, e.g. enterprise architecture, technical program management>
- Seniority: <e.g. senior, lead, principal, manager>
- Adjacent roles: <roles that count as a partial title match>
- Never interested: <roles or industries to discard at Tier 1>

## Location
- Home area: <metro area and state or country>
- Home ZIP: <postal code the commute is measured from; optional>
- Max commute (miles): <one-way distance the user will travel to an office, e.g. 35>
- Commutable to: <optional: cities or areas to treat as commutable regardless of distance>
- Remote: <yes / no>
- Relocation: <no / yes / only to: <places>>

## Email sources
| Source | Sender | Notes |
|---|---|---|
| <label written to the Source column> | <sender address> | <how to read these emails: one job or a digest, how reliable, link quirks> |

## Never scan
- <sender addresses that look like job mail but aren't postings>

## Housekeeping
- Archive after days: <30>
- Tier 2 rows per run: <10>
~~~

## 1. Find the profile
Search Drive for `title = 'job-search-profile.md'`.
- **One found:** read it (`download_file_content`, decoded) and go to step 3.
- **None found:** if a `job-search-profile.previous.md` exists, an earlier update stopped partway: tell the user, read that file as the current profile, and finish the update from step 4. Otherwise this is a new setup: go to step 2.
- **More than one:** stop and list them with their folders and modified dates (one may be a copy the user trashed by hand). Ask which one is current; never pick one yourself.

## 2. Interview a new user
Ask one section at a time, in the order of the format above, and confirm each section before moving on. Offer an example for every question, and accept "skip" for anything optional (Adjacent roles, Never interested, Never scan, Notes).
- **Candidate:** the name, then the full-resume file. If they don't have a Markdown full resume yet, explain it's one file with their whole career history (every role, project, certification and tool, not a two-page selection), that every score is judged against it, and that the more complete it is the fewer false gaps they'll see. Suggest a name such as `Full-Resume.md`. Derive the tailored resume prefix from the name (`Jane_Example_Resume`) and show it.
- **Tracker:** ask for the Google Sheet's name and the Drive folder it's in (or should go in). For now the tracker is always a Google Sheet. Then follow step 5.
- **Target roles and Location:** ask in plain language ("What kinds of roles are you looking for, and at what level?", "Where do you live?", "What's your ZIP code?", "How many miles, one way, would you commute to an office?", "Would you relocate? If so, where?") and turn the answers into the profile's lines. Read them back.
- **Email sources:** ask which job-alert emails they get (LinkedIn job alerts, recruiter mail, job boards). For each, find a recent example in Gmail if the Gmail connector is available, confirm the sender address with the user, and write a one-line note on how to read it (one job per email or a digest of several, any link quirks). Suggest adding LinkedIn's non-posting senders (`messages-noreply@`, `notifications-noreply@`, `groups-noreply@`, `updates-noreply@`, `editors-noreply@linkedin.com`) to **Never scan** if they use LinkedIn alerts.
- **Housekeeping:** offer the defaults (archive after 30 days, 10 Tier 2 rows per run) and change them only if asked.

Then show the whole profile and ask the user to confirm before writing it (step 4).

## 3. Update an existing profile
When the user tells you something changed (in this conversation or in a request that loaded this skill), change only the lines it affects, and keep everything else exactly as it is, including the user's own wording and comments. If a request is ambiguous ("add Indeed"), ask the one question needed ("Which sender address do Indeed alerts come from?"). Show the changed lines as before → after and confirm, then write the file (step 4).

Also use this step for a review: if asked "show my job search profile", read it back section by section and point out anything blank or inconsistent (for example Relocation "only to" with no places).

## 4. Write the profile
The Drive connector can create, rename and trash files but can't change a file's contents, so an update replaces the file:
1. If a profile exists, rename it to `job-search-profile.previous.md` with `update_file` (`title`).
2. Create the new `job-search-profile.md` with `create_file`: `parentId` the tracker's folder ID, `contentMimeType` `text/markdown`, `disableConversionToGoogleType` true, the full text in `textContent`, and **Last updated** set to today.
3. Read it back with `download_file_content`, decode it, and check that it matches what you meant to write.
4. Rename the previous copy to `job-search-profile.replaced-<YYYYMMDD-HHMM>.md`, then trash it with `trash_file`. Renaming first means no trashed file ever carries a name this skill searches for. Drive keeps trashed files for 30 days, so the user can still recover it.

If step 2 or 3 fails, rename the previous copy back to `job-search-profile.md` and report the failure.

## 5. Check the tracker
1. Find the folder: search for the folder name (`mimeType = 'application/vnd.google-apps.folder'`), following the path the user gave from the top. If there's more than one match, ask which. Record its **Folder ID**.
2. Find the sheet in that folder: `title = '<Sheet name>' and mimeType = 'application/vnd.google-apps.spreadsheet' and parentId = '<Folder ID>'`. Record its **Sheet ID**.
3. If it exists, open it with the Sheets connector and check it has a **Job Log** tab with the headers `job-tracker` lists. Report any missing headers. Don't add them without asking.
4. If the folder or sheet doesn't exist, tell the user and ask whether to create it. Create only with an explicit yes. Then create the folder if needed (`create_file`, `mimeType` folder), and create the sheet in it (`create_file`, `mimeType` `application/vnd.google-apps.spreadsheet`, `parentId` the folder). Rename its first tab to **Job Log**, and write the headers in the order `job-tracker` lists them. Add the Status dropdown and the two checkbox columns' validation, freeze row 1, and add a **Status Guide** tab with each status, what it means and a `COUNTIF` count of rows in that status.

## 6. End-of-run summary
- Whether the profile was created, updated or only reviewed, and where it is.
- The lines that changed, before → after.
- Anything still blank that other skills will need. For example, intake can't scan email without at least one email source, and scoring needs Target roles and Location.
- For a new setup, what to do next: put the full resume in the folder, then schedule the daily intake task (and Tier 2 and weekly cleanup) in the Claude app.

## Known constraints
- The only file this skill writes is `job-search-profile.md`, plus a tracker or folder the user explicitly asked it to create.
- Never invents profile values. If the user hasn't said it, it stays blank and is listed in the summary.
- Never deletes a profile outright; an update trashes the previous copy only after the new one is written and checked.
- Never changes the user's other files: not the full resume, not the tracker's rows, not job files.
- The profile holds personal details. It stays in the user's Drive and is never copied into a repository, an issue or a public page.
