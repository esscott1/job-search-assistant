---
name: "tailored-resume-builder"
description: "On demand only, never scheduled: when the user says 'build ticked resumes' (tracker rows ticked in Build Resume), names tracker rows, or pastes a job description: picks the most relevant true content from the user's full resume and renders a .docx and PDF of at most 2 pages in the user's own resume style (resume-style.md, or the plugin's default). Never invents experience; reports gaps instead. Not for scoring (that's job-fit-rubric), not for editing the master inventory, and not for setting up the resume style (that's job-search-profile)."
---

# Tailored Resume Builder

Turns one job description into one resume of at most 2 pages, in the user's own look. Shorter is fine: a one-page resume is the right result when the full resume doesn't hold two pages of relevant, true content. It's the last step of the tracker loop: the user ticks Run Tier 2, works through the gaps in the fit report (adding anything true but missing to their full resume and re-ticking to rescore), and when they're done ticks **Build Resume** and asks for "build ticked resumes". The model does the judgment (which true things to show, in what words); `render_resume.py` does the layout from the user's style file, so every resume looks the same and nothing is hand-built.

## Key files and systems
- **Profile and tracker:** load the `job-tracker` skill before anything else. It explains how to find the user's job-search profile and tracker, the Build Resume checkbox, the columns this skill writes, and the job files in Drive (`<ID>_JD.md`, the fit reports, the company folder). This skill uses the profile's **Candidate** settings (Full resume, Resume style, Tailored resume prefix) and **Tracker → Local Drive folder**.
- **Content source** (the only source of facts): the full resume named in the profile, found as `job-tracker` describes. It's read-only here; the user edits it. If it isn't found, stop and say so.
- **Look:** the style file named in **Candidate → Resume style**, usually `resume-style.md` in the tracker folder. It's small text, so read it with the Drive connector like any other Markdown file. `default` (or a blank setting) means `default-style.md` in this skill's folder. The format is in `resume-style-format.md` here. If the profile still names a **Resume template** (.docx) instead, use the default style for now, and tell the user to say "set up my resume style" to convert their template. **Never download a .docx through the Drive connector.** It arrives as base64 that has to be copied by hand, which corrupts files.
- **`render_resume.py`** (this folder): `python3 render_resume.py --style <style.md> --content content.json --out <file>.docx --pdf`. It needs `python-docx`; page counting and the PDF need LibreOffice (`soffice`) and `pdfinfo`. It prints JSON with `pages` and `warnings`, and exits 2 with a reason if the style file or `content.json` is invalid.
- **Also here:** `extract_style.py`, which `job-search-profile` uses to convert a Word template into a style file. This skill doesn't call it.
- **Evals:** the `resume-*` cases in this plugin's `evals/` folder.

## Procedure
1. **Pick the jobs and get each job description.**
   - **"Build ticked resumes":** every tracker row with **Build Resume** ticked, lowest ID first. **Named rows:** exactly those. Build the first 3, then check in before doing more.
   - For a tracker row, the JD is the saved `<ID>_JD.md` (`search_files` with `title = '<ID>_JD.md'`). If there isn't one, skip the row, leave it ticked, and report "run Tier 2 first". Don't search for the JD here.
   - **Pasted or attached JD** with no tracker row: use it as given.
   - If there is no usable JD, stop and ask. Never tailor to a job title alone.
2. **Read the full resume and the style file** (see Key files). Save the style text to a scratch file for `render_resume.py`.
3. **Map the job to the inventory.** Load `job-fit-rubric` and build its evidence table: each JD requirement quoted, marked required or preferred, and matched strong, partial or none to a pointer in the full resume. For a tracker row, start from the evidence table in its latest fit report (`title contains '<ID>_fit_r'`, highest run). Keep its requirement list, and check each match against the current full resume, since the user may have edited it since. Use the table as the selection guide: strong matches get the most room, and `none` matches are gaps.
4. **Write `content.json`** (shape below) using only what the inventory supports:
   - Keep every employer, title, location and date exactly as in the inventory. Never change dates, titles, numbers, team sizes, technologies or outcomes.
   - Reword for the JD's vocabulary only when the inventory already says the same thing (e.g. "ATO process" if the inventory says Authority to Operate). Never add a skill, tool, credential, metric or responsibility the inventory doesn't contain, even if the JD asks for it.
   - Headline: a short line matching the target role, built from titles and strengths the user really has. The style decides its capitalisation.
   - Competencies: at most 12, only ones the inventory evidences, ordered by JD relevance.
   - Career highlights: 3 to 5, the strongest matches to the JD's required items.
   - Experience: all roles stay, newest first. Give the most bullets to the roles that best match the JD, and trim older or less relevant roles to 1-3 bullets. Drop a role's summary before dropping a strong bullet.
   - Education and certifications: include as in the inventory. Certification credential IDs are optional; leave them out to save space.
5. **Build:** run `render_resume.py` with `--pdf`.
   - **Over 2 pages:** trim the least relevant bullets and shorten summaries, then rebuild until it's 2 pages or fewer.
   - **Under 2 pages:** fine. Use the room for relevant bullets the inventory really has, and never pad with filler to reach a length.
   - **`pages` is null** (LibreOffice isn't available, so the page count can't be checked): keep the content within the limits above, and say in the summary that the page count is unverified.
   - **Look at the PDF** (convert its pages to images) to check nothing is broken: dates line up at the right margin, and there's no stray blank page.
6. **Check truthfulness.** For every bullet, headline, highlight and competency in the output, confirm it traces to a line in the full resume. Fix or remove anything that doesn't. Do not skip this even when running unattended.
7. **Deliver.** File names: `<Tailored resume prefix>_<Company>_<Role>.docx` and `.pdf`, using the prefix from the profile (e.g. `Jane_Example_Resume_Acme_Corp_Program_Manager.pdf`). If a resume with that name already exists for the job, add `_v2`, `_v3` and so on; never overwrite an earlier one. They belong in the job's company folder, `<tracker folder>/<Company_Folder>/` (naming rule in `job-tracker`).

   **Never upload a .docx or PDF through the Drive connector.** A binary upload has to be copied by hand as base64, which corrupts files. Deliver the resume one of these ways:
   - **On the user's computer, with a Local Drive folder** (the profile's **Tracker → Local Drive folder** exists on this machine): write the .docx and PDF straight into `<Local Drive folder>/<Company_Folder>/`, creating the folder if needed. Google Drive for desktop syncs them. To link the tracker row, look the PDF up by title with `search_files`, trying for about a minute while it syncs. If it isn't there yet, write the file name followed by `(syncing to Drive)`, and say so.
   - **Otherwise (the cloud, or no Local Drive folder):** hand the .docx and PDF to the user as downloads (in the Claude app, send the files; elsewhere, give their paths). Say which folder to put them in.

   Text files still go through the connector. For a pasted JD only, save `<Tailored resume prefix>_<Company>_<Role>_JD.txt` with the job description in the company folder (`create_file` with `textContent`), so it's there if an interview follows. Tracker rows already have `<ID>_JD.md`.

   **For a tracker row:**
   - Write **Tailored Resume**: a link to the PDF labelled with its file name, or the file name followed by `(syncing to Drive)`, or `(download; add to <Company_Folder>/)`.
   - Write **Resume Created** and **Last Updated** (today), then untick **Build Resume** as the last write (`job-tracker` has the rules).
   - If the build failed or is over 2 pages, leave the box ticked and say why.
   - If there's no PDF because the page count couldn't be checked, deliver the .docx, refer to it in the row, and say so.
   - Never touch Status or Next Action / Notes.

   **At the start of a run,** replace any `(syncing to Drive)` cell from an earlier run with a link, if the file can now be found.
8. **Tell the user the gaps.** End with the required JD items the inventory has no evidence for. They can then decide whether the inventory is missing something true (and add it to their full resume) or it's a real gap.

## content.json shape
```json
{
  "name": "JANE EXAMPLE",
  "contact": ["phone", "city, state", "email", "linkedin url"],
  "headline": "ROLE-ALIGNED HEADLINE",
  "summary": "2-4 sentences, all true to the inventory",
  "competencies": ["up to 12 short phrases"],
  "highlights": ["3-5 one-sentence achievements"],
  "experience": [
    {"company": "...", "location": "...", "dates": "...", "description": "one-line company description",
     "roles": [{"title": "...", "location": "...", "dates": "...", "summary": "optional", "bullets": ["..."]}]}
  ],
  "education": [{"degree": "...", "school": "..."}],
  "certifications": [{"name": "...", "detail": "issuer, year"}],
  "additional": ["optional lines"]
}
```
Take contact details from the inventory's contact line, not from memory.

## Known constraints
- Never invents or inflates anything; gaps are reported, not filled.
- Never edits the full resume, the style file, or any earlier tailored resume. Style changes go through `job-search-profile`.
- Never moves a .docx or PDF through the Drive connector, in either direction.
- Never commits the style file, the inventory, a generated resume or a JD to the repo (it's a public repo).
- Never sends a resume or applies to a job; the user does that.
- Never runs on a schedule. Building a resume is always the user's explicit request.
- If the inventory can't be found, the style file is invalid, or the output can't be brought to 2 pages or fewer, say so rather than delivering something off-format.

## End-of-run summary
- Job and files produced: names, where they were delivered (written to the synced folder, or handed over as downloads), page count, and which tracker rows were unticked.
- The style used (the user's `resume-style.md`, or the default) and, if the profile still names a Word template, how to convert it.
- Ticked rows skipped, and why (no saved JD, build failed).
- What was emphasized and what was trimmed.
- Gaps: required JD items with no support in the inventory.
- Anything you couldn't verify, such as the page count.
