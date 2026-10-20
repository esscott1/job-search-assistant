---
name: "job-search-profile"
description: "On demand: sets up or updates the user's job-search profile, job-search-profile.md in their Google Drive. It holds their name, full-resume file, tracker sheet and folder, target roles, location and relocation rules, job sources (job-alert email senders and company career sites), housekeeping settings, and the look of their tailored resumes (resume-style.md, converted once from a Word template or style file they attach). Use it the first time someone sets up the job-search plugin ('set up my job search'), and whenever they change something in chat ('add a job alert sender', 'search for openings at Acme', 'watch https://careers.example.com/jobs', 'I'd relocate to Austin now', 'my tracker moved', 'set up my resume style', 'make my resume headings navy'). Interviews the user in short, menu-driven steps, pre-filled from their full resume; can save a full resume they attach or paste; checks the Gmail connector; finds and tests career sites. The other job-search skills read the profile; they never write it."
---

# Job Search Profile

Every job-search skill in this plugin works from one file: **`job-search-profile.md`** in the user's Google Drive. It plays the part a CLAUDE.md plays for a codebase: plain Markdown that this skill writes and keeps current, and that the user can also edit by hand. Nothing about a particular user is written into the skills themselves; it all comes from here.

This skill creates the profile by interviewing the user, and updates it whenever they tell Claude something changed.

## Key files and systems
- **The profile:** a plain-text Markdown file named exactly `job-search-profile.md`, stored in the user's job-search folder. It's found by name (`search_files` with `title = 'job-search-profile.md'`), so its location never has to be configured. Drive search can't filter out trashed files, so this skill never leaves a trashed file with that name (see step 4).
- **The job-search folder** (the profile's **Tracker → Folder**) holds everything: the tracker, the profile, the full resume, the resume style, and a folder per company with its job descriptions, fit reports and tailored resumes.
- **The full resume:** one Markdown file in that folder with the user's whole career. Its format is `full-resume-format.md` in this skill's folder.
- **Google Drive connector** to find, read, create, rename and trash files. Read the profile with `download_file_content` and base64-decode it: `read_file_content` can return an empty result for a Markdown file created in the last few minutes. **Google Sheets connector** to check the tracker. **Gmail connector** to confirm email senders. **Web search and web fetch** to find and test career sites.
- **`job-tracker` skill:** load it for the tracker's tab and column layout when checking or creating a tracker.
- **The `tailored-resume-builder` skill's folder**, next to this skill's folder, holds the scripts this skill uses:
  - `extract_style.py`: drafts a style file from a Word template.
  - `render_resume.py`: builds a resume from a style file. Used here for previews, and to check a style file (an invalid one exits 2 with the line and the reason).
  - `check_content.py --inventory <full resume>`: lists the employers and roles a full resume's headings describe, or says it found none.
  - `resume-style-format.md` (the style file's format) and `default-style.md`.

## How to talk to the user
Setup is often done on a phone. Every message must fit on one screen.
- **One question per message.** Two to four closely related questions may share one multiple-choice call (step 2 says where).
- **At most 3 short lines before the choices.** No preamble, no restating what the user just answered, no explanations unless they ask ("why?", "more", or a "What's this?" option).
- **Offer choices, not open questions.**
  - If a multiple-choice tool is available (`AskUserQuestion` in Claude Code, on a computer or a phone), use it: at most 4 options, the recommended or default one first with "(Recommended)" after its label. The tool adds "Other" for a typed answer.
  - Otherwise, write the options as a numbered list and end with "Reply with a number, or type your own."
  - Always accept a typed answer, and "skip" for anything optional.
  - Offer only choices about what the user asked. Don't add options for changes they didn't ask for (asked for navy headings, don't offer a navy name too).
- **Suggest from what you already know.** Pre-fill choices from the full resume, the files in the folder, and the user's Gmail, rather than asking the user to type.
- **Start each first-time setup step with a progress tag**, like `Setup 3/9 · You`.
- **Confirm with one line per change**, never the whole file. Show the whole setting line before and after, even a long one, so the user can see nothing else moved: `- Remote: no` → `- Remote: yes`. Never shorten it with "…".
- **Long work** (finding careers pages, testing sites, converting a resume or template): one line before it starts, then one line per result (`Acme: feed ✓ 14 postings`).

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
- Resume style: <resume-style.md, or "default" for the plugin's default look>
- Tailored resume prefix: <file-name prefix for tailored resumes, e.g. Jane_Example_Resume>

## Tracker
- Sheet name: <Google Sheet name, e.g. Job_Search_Tracker>
- Folder: <Drive folder path, e.g. My Drive/Job Search>
- Folder ID: <filled in by this skill>
- Sheet ID: <filled in by this skill>
- Time zone: <IANA time zone used for dates, e.g. America/Denver>
- Local Drive folder: <optional: where this folder appears on the user's computer, if Google Drive for desktop syncs it>

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

## Career sites
| Source | Company | URL | Method | Notes |
|---|---|---|---|---|
| <label written to the Source column, e.g. Careers: Acme> | <company name> | <listing page, feed or site: scope> | <page / feed / search> | <the ATS if known, the human careers page for a feed, filters in the URL, quirks> |

## Never scan
- <sender addresses that look like job mail but aren't postings>

## Housekeeping
- Archive after days: <30>
- Tier 2 rows per run: <10>
- Career site leads per run: <15>
~~~

Email sources and Career sites are both optional, but intake needs at least one source to scan. A profile written before Career sites existed simply has no such section; skills treat a missing section as empty.

## 1. Find the profile
Search Drive for `title = 'job-search-profile.md'`.
- **One found:** read it (`download_file_content`, decoded) and go to step 3.
- **None found:** if a `job-search-profile.previous.md` exists, an earlier update stopped partway: tell the user, read that file as the current profile, and finish the update from step 4. Otherwise this is a new setup: go to step 2.
- **More than one:** stop and list them with their folders and modified dates (one may be a copy the user trashed by hand). Ask which one is current, as a menu; never pick one yourself.

## 2. First-time setup
Nine short steps, in this order, following **How to talk to the user**. Keep the answers as you go, and write nothing until the final confirm, except a full resume the user asks you to save (2) and a tracker they agree to create (4).

1. **Folder.** Say once, in one line: "This folder will hold your tracker, profile, full resume, job descriptions and tailored resumes." Search Drive for folders (`mimeType = 'application/vnd.google-apps.folder'`), preferring titles with "job", "career" or "resume". Menu: up to 3 likely folders, "Create a new folder (Job Search)", and Other. Record **Folder** (its path) and **Folder ID**; create a new folder only when chosen.
2. **Full resume.** List the folder's Markdown files. Menu: each likely full resume found (newest first, at most 2), "Attach or paste my resume", and "What's a full resume?" (answer in two lines from `full-resume-format.md`, then ask again).
   - **A file in the folder:** use it.
   - **Attach or paste:** save it into the folder as `Full-Resume.md`, so the user never has to upload it to Drive themselves. If a file with that name is already there, use `Full-Resume-2.md`; never replace an existing file.
     - **A `.md` file or pasted Markdown:** keep it as given. Save it to a scratch file and run `check_content.py --inventory` on it. If it lists the roles, go on. If it found no headings, say so in one line and offer "Reformat it for me (Recommended)" or "Keep as is" (resume checks then happen by hand).
     - **A `.docx`, a `.pdf`, plain pasted text, or "Reformat it for me":** convert it as `full-resume-format.md` describes: every line kept word for word, nothing invented, anything you couldn't place listed. Check the result with `check_content.py --inventory`.
     - **Confirm before saving:** show the employers and roles found, newest first, one line each, plus anything unplaced, then "Save (Recommended)" / "Fix something". Save with `create_file` (`parentId` the folder, `contentMimeType` `text/markdown`, `disableConversionToGoogleType` true, the text in `textContent`), and read it back to check it, as in step 4.
     - Say once that the original .docx or PDF isn't copied to Drive: a binary can only go through the connector as base64, which corrupts it. The user keeps the original.
   - Read the full resume. The next steps suggest answers from it.
3. **You.** One multiple-choice call with three questions, each with its suggestion first:
   - **Name:** from the resume's first line, in normal capitalisation.
   - **Home area:** from the resume's contact line.
   - **Tailored resume prefix:** derived from the name (`Jane_Example_Resume`).
   Then set **Time zone** from the home area, without asking.
4. **Tracker.**
   - Menu: "Create Job_Search_Tracker here (Recommended)", up to two Google Sheets found in the folder, and Other (a name). Then follow step 5; creating it needs this choice or another explicit yes.
   - Then: "Is this folder synced to this computer by Google Drive for desktop?" Menu: "Yes" (then ask for the path, suggesting a likely one such as `C:\Users\<name>\Google Drive\My Drive\<Folder>` or a path you can see), "No", "Not sure" (one line: it's Google's app that mirrors Drive to a folder on the computer; then ask again). If this session can see the computer's files, check the path exists and holds the folder's files before writing it as **Local Drive folder**.
5. **Target roles.**
   - **Role families:** a multi-select menu of up to 4 families suggested from the resume's titles and headline, with the closest match first.
   - **Seniority:** a menu suggested from the most recent title (for example "Senior / Lead / Director / Other").
   - **Adjacent roles and Never interested:** one menu, "Skip (Recommended)" / "Add some".
6. **Location.** One multiple-choice call:
   - **Remote OK?** Yes / No / Hybrid only.
   - **Max commute, one way:** 15 / 25 / 35 / 50 miles.
   - **Relocation:** No / Anywhere / Only to certain places (then ask which).
   Then ask for the **ZIP code** as a typed answer, or skip.
7. **Job sources.** A multi-select: "Job-alert email", "Company career sites". Then step 6 for each one picked.
8. **Resume style.** Step 7.
9. **Housekeeping.** Menu: "Use the defaults (Recommended)" (archive after 30 days, 10 Tier 2 rows per run, 15 career-site leads per site per run) / "Customize".

**Final confirm.** Show a compact summary, at most 12 lines: name, folder, full resume, tracker, role families and seniority, home area and commute, remote and relocation, the number of email sources and career sites, and the style. Menu: "Save (Recommended)", "Change something", "Show the full profile". Save with step 4.

## 3. Update or review an existing profile
When the user tells you something changed (in this conversation or in a request that loaded this skill), change only the lines it affects, and keep everything else exactly as it is, including the user's own wording and comments. Follow **How to talk to the user**.
- **A clear change:** show the changed lines as one line each, before → after, then a menu: "Save (Recommended)" / "Cancel". Write the file with step 4.
- **An ambiguous request** ("add Indeed"): ask the one question needed, as a menu built from what you can see (for example the Indeed senders found in Gmail).
- **"Show my job search profile":** a short overview, at most 10 lines, flagging anything blank or inconsistent (for example Relocation "only to" with no places). Then a menu: "See a section", "Change something", "Done". Don't print the whole file unless asked.

A request about the look of tailored resumes ("set up my resume style", "make the headings navy", "use Garamond", "use this template instead") follows step 7.

A request that adds a job source ("add Indeed alerts", "search for openings at Acme", "watch https://careers.example.com/jobs") follows step 6 for that one source. "Stop watching Acme" removes its Career sites row; show it before → after like any other change.

"Use this resume instead", with an attachment or pasted text, follows step 2's **Attach or paste**, saving under a new name and pointing **Candidate → Full resume** at it once the user confirms.

## 4. Write the profile
The Drive connector can create, rename and trash files but can't change a file's contents, so an update replaces the file:
1. If a profile exists, rename it to `job-search-profile.previous.md` with `update_file` (`title`).
2. Create the new `job-search-profile.md` with `create_file`: `parentId` the tracker's folder ID, `contentMimeType` `text/markdown`, `disableConversionToGoogleType` true, the full text in `textContent`, and **Last updated** set to today.
3. Read it back with `download_file_content`, decode it, and check that it matches what you meant to write.
4. Rename the previous copy to `job-search-profile.replaced-<YYYYMMDD-HHMM>.md`, then trash it with `trash_file`. Renaming first means no trashed file ever carries a name this skill searches for. Drive keeps trashed files for 30 days, so the user can still recover it.

If step 2 or 3 fails, rename the previous copy back to `job-search-profile.md` and report the failure.

`resume-style.md` is written the same way, with its own names (`resume-style.previous.md`, `resume-style.replaced-<YYYYMMDD-HHMM>.md`) and `contentMimeType` `text/markdown`. A full resume saved in step 2 is only ever created, never replaced, so it uses steps 2 and 3 alone.

## 5. Check the tracker
1. The folder comes from setup step 1 (or, for "my tracker moved", search for the folder name with `mimeType = 'application/vnd.google-apps.folder'`, following the path the user gave from the top; if there's more than one match, ask which, as a menu). Record its **Folder ID**.
2. Find the sheet in that folder: `title = '<Sheet name>' and mimeType = 'application/vnd.google-apps.spreadsheet' and parentId = '<Folder ID>'`. Record its **Sheet ID**.
3. If it exists, open it with the Sheets connector and check it has a **Job Log** tab with the headers `job-tracker` lists. Report any missing headers. Don't add them without asking.
4. If the folder or sheet doesn't exist, create it only with an explicit yes (the setup menu choice counts). Create the folder if needed (`create_file`, `mimeType` folder), and create the sheet in it (`create_file`, `mimeType` `application/vnd.google-apps.spreadsheet`, `parentId` the folder). Rename its first tab to **Job Log**, and write the headers in the order `job-tracker` lists them. Add the Status dropdown and the two checkbox columns' validation, freeze row 1, and add a **Status Guide** tab with each status, what it means and a `COUNTIF` count of rows in that status.

## 6. Job sources
In setup, the user has already picked email, career sites or both (setup step 7). On its own ("add my email sources"), go straight to the kind asked for. They can add more any time later.

### Email
1. **Check for a mail connector.** Email is read through the Gmail connector: see whether its tools (`search_threads`, `get_thread`) are available in this session.
   - **Gmail is available:** go on to 2.
   - **Another mail connector but not Gmail** (for example Outlook): say in one line that email scanning supports Gmail only for now. Menu: "Set up career sites instead", "Skip email for now".
   - **No mail connector:** say in two lines that intake reads job-alert email through the Gmail connector, added in Claude under **Customize → Connectors → Gmail**. Menu: "Carry on without email (Recommended)", "I've added it, check again". Leave Email sources empty until a sender can be confirmed; never write a sender you couldn't check.
2. **Offer the senders you find.** Search the last 30 days of Gmail for job-alert mail (LinkedIn job alerts, job boards, recruiters, companies' own alerts). Show a multi-select menu of up to 4 senders found, each labelled with the sender and how many alerts arrived (`jobalerts-noreply@linkedin.com · 12 alerts`). Other lets the user type one you didn't find. For each sender picked, write a one-line note on how to read it (one job per email or a digest of several, any link quirks). If nothing turns up, say so and ask for a sender as a typed answer, or skip.
3. **Never scan:** if they picked LinkedIn alerts, add LinkedIn's non-posting senders (`messages-noreply@`, `notifications-noreply@`, `groups-noreply@`, `updates-noreply@`, `editors-noreply@linkedin.com`) after a one-line "Save / Skip" menu.

### Career sites
Ask once, as a typed answer: "Which companies? Type names or careers URLs, separated by commas." Then, for each one:
1. **Find the listing page.**
   - **A URL:** use it as given.
   - **A company name:** search the web for its official careers page (`<company> careers jobs`). Prefer the company's own domain or the applicant-tracking board its careers page links to (Greenhouse, Lever, Workday, iCIMS, Ashby, SmartRecruiters and the like). Never use a job aggregator or a LinkedIn page. Company names collide, so confirm it with a menu: "Yes, this one" (showing the URL), "Not this one" (then show up to 3 other candidates), "Skip".
2. **Test how it can be read from the cloud.** Intake runs on a schedule with no browser, so try these in order and record the first that works as **Method**:
   - **`feed`:** the board is on an applicant-tracking system with a public job feed that a plain GET returns: Greenhouse `https://boards-api.greenhouse.io/v1/boards/<board>/jobs`, Lever `https://api.lever.co/v0/postings/<company>?mode=json`, Ashby `https://api.ashbyhq.com/posting-api/job-board/<board>`, SmartRecruiters `https://api.smartrecruiters.com/v1/companies/<company>/postings`. Fetch it and check it lists postings. Put the feed URL in **URL** and the human careers page in **Notes**.
   - **`page`:** fetch the listing page and check that it shows real job titles with links to postings, not just a search box or an empty shell built by JavaScript. If the site puts its search in the URL (for example `?q=architect&location=Columbus`), build that URL from Target roles and Location, test it again, and record it.
   - **`search`:** neither works, which is common on JavaScript-only boards such as many Workday sites. Run a web search `site:<careers host and path> <a role keyword>` and check that some results are posting pages on that host. Record the scope as **URL** (`site:acme.example-ats.com/careers`); intake adds role keywords from Target roles. Note in **Notes** that results depend on the search index and can lag the site by days.
   - **None works:** say in one line that this site can't be read without a browser, and suggest the company's own job-alert email instead (once alerts arrive, add the sender as an email source). Don't add the row.
3. **Report one line per site** (`Acme: feed ✓ 14 postings`, `Globex: search ✓`, `Initech: can't be read, try its job alerts`). In setup, the rows are saved with the profile at the final confirm. On their own, show the new rows as before → after with "Save / Cancel" and write them (step 4).

Then: "More companies?" Menu: "No, that's all (Recommended)" / "Add more".

## 7. Resume style
Tailored resumes take their look from `resume-style.md`, a short text file of fonts, sizes, colours, margins and layout, so no Word file ever has to pass through the Drive connector. It's made once, from a Word template the user already likes or a style file they already have, or the user takes the plugin's default.

1. **Ask**, as a menu:
   - "Use resume-style.md found in <folder> (Recommended)", when the folder already has one;
   - "Default style" (Recommended when there's no style file in the folder);
   - "Attach a Word template (.docx)";
   - "Attach a style file (.md)".
   In setup, "Decide later" is acceptable as a typed answer; set Resume style to `default` and say it can be changed any time.
2. **A Word template.** Get the .docx as a real file:
   - **Attached to this conversation:** use the attached file.
   - **On the user's computer, with a Local Drive folder:** read it from disk if they name it there.
   - **Never download a .docx through the Drive connector.** It arrives as base64 that has to be copied by hand, which corrupts files. Ask them to attach it instead.

   **Convert:** `python3 <tailored-resume-builder folder>/extract_style.py <template.docx> --out <scratch>/resume-style.md`. It prints a report of what it guessed, how, and with what confidence, and what it can't carry over. On exit 2, say in one line that the file couldn't be read as a Word resume and offer the default style.
3. **A style file** (attached, pasted, or found in the folder): save it to `<scratch>/resume-style.md` as given. The preview in item 4 checks it: `render_resume.py` exits 2 with the line and the reason when a style file is invalid. Then show that one line and offer "Fix it for me (Recommended)" (edit only that line, following `resume-style-format.md`, and preview again), "Attach another", "Use the default style".
4. **Preview with the user's own content.** Make a small `content.json` from the full resume only:
   - the name and contact line;
   - a headline from their current title;
   - two or three sentences of summary;
   - six competencies and two highlights;
   - the two most recent roles, with up to three bullets each.

   Never invent anything for a preview. Run `render_resume.py --style <scratch>/resume-style.md --content content.json --out preview.docx --pdf`. If a PDF came out, turn its first page into an image (`pdftoppm -png -r 80 -f 1 -l 1 preview.pdf preview`) and show it. Otherwise give the .docx as a download, and say the preview couldn't be rendered here.
5. **Check with the user**, briefly:
   - For a converted template, list the low-confidence guesses from the report, and everything under "Not carried over" (pictures, text boxes, columns, header or footer content, uncommon fonts), one line each, so nothing is lost silently.
   - Menu: "Looks right (Recommended)", "Change something" (then apply it, for example "make the headings navy" or "dates after the title", by editing the style file's lines in the documented format, and re-render).
6. **Save** `resume-style.md` to the folder (step 4) only after they confirm (in setup, at the final confirm), and set **Candidate → Resume style** to `resume-style.md`.
7. **Default style:** set Resume style to `default`, and show a preview of `default-style.md` with their content. If they want to adjust the default, copy it to their own `resume-style.md`, then edit and save it as above.

**Later changes:**
- "make the section headings navy", "use Garamond", "put the dates after the title": change only those lines of their `resume-style.md`, show before → after, preview, and save.
- "use this template instead", with an attachment: convert again from item 2 above. "use this style file", with an attachment: item 3.
- The original .docx isn't needed after conversion. Don't upload, copy or keep it.

A profile written before this step has **Resume template: <file>.docx** instead of Resume style. Offer to convert that template once (asking the user to attach it), and replace the line with **Resume style** when the style file is saved.

## 8. End-of-run summary
At most 6 lines; offer details if the user asks.
- What was created, updated or only reviewed, and where (a link to the folder or the profile).
- Anything still blank that other skills need (for example, intake has nothing to scan without an email source or career site; scoring needs Target roles and Location), and whether email was skipped for lack of the Gmail connector.
- For a new setup, the single next step: schedule the daily intake task (and Tier 2 and weekly cleanup) in the Claude app, as `docs/getting-started.md` describes.

## Known constraints
- The only files this skill writes are `job-search-profile.md` and `resume-style.md`, a full resume the user attached or pasted and asked to save (never replacing an existing file), and a folder or tracker the user explicitly chose to create.
- Never moves a Word file or PDF through the Drive connector, and never uploads or keeps the user's template or original resume file; only their text versions are saved.
- Never invents profile values or resume content. If the user hasn't said it and the resume doesn't show it, it stays blank and is listed in the summary. A career site's URL is written only after the user confirms it.
- Testing a career site only reads it. Never sign in, apply, create an account, or sign up for job alerts on the user's behalf.
- Never deletes a profile outright; an update trashes the previous copy only after the new one is written and checked.
- Never changes the user's other files: not an existing full resume, not the tracker's rows, not job files.
- The profile holds personal details. It stays in the user's Drive and is never copied into a repository, an issue or a public page.
