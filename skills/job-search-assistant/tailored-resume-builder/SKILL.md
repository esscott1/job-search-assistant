---
name: "tailored-resume-builder"
description: "On demand only, never scheduled: when the user says 'build ticked resumes' (tracker rows ticked in Build Resume), names tracker rows, or pastes a job description: picks the most relevant true content from the user's full resume and fills the Job-Seeker-6 Word template into a 2-page .docx and PDF. Never invents experience; reports gaps instead. Not for scoring (that's job-fit-rubric) and not for editing the master inventory."
---

# Tailored Resume Builder

Turns one job description into one 2-page resume in the Job-Seeker-6 layout. It's the last step of the tracker loop: the user ticks Run Tier 2, works through the gaps in the fit report (adding anything true but missing to their full resume and re-ticking to rescore), and when they're done ticks **Build Resume** and asks for "build ticked resumes". The model does the judgment (which true things to show, in what words); `build_resume.py` does the layout, so every resume has the same format as the template instead of a hand-built approximation.

## Key files and systems
- Profile and tracker: load the `job-tracker` skill before anything else. It explains how to find the user's job-search profile and tracker, the Build Resume checkbox, the columns this skill writes, and the job files in Drive (`<ID>_JD.md`, the fit reports, the company folder). This skill uses the profile's **Candidate** settings: Full resume, Resume template and Tailored resume prefix.
- Content source (the only source of facts): the full resume named in the profile, found as `job-tracker` describes. Read-only here; the user edits it. If it isn't found, stop and say so.
- Layout source (format only, no content): the Word file named in the profile's **Resume template**, in the same folder. It must be a copy of the Job-Seeker-6 resume template, the only layout `build_resume.py` supports today; if it isn't, stop and say so rather than producing a broken layout. The template's sample text (a different person's career) must never reach the output; the script replaces all of it.
- `build_resume.py` (this directory): `python3 build_resume.py --template <template.docx> --content content.json --out <file.docx> --pdf`. Needs `python-docx`; page counting needs LibreOffice (`soffice`) and `pdfinfo`. It prints JSON with `pages` and `warnings`, and exits 2 with a reason if `content.json` is invalid.
- Evals live in the repo-level `evals/tailored-resume-builder/` (cases and a synthetic fixture).

## Procedure
1. **Pick the jobs and get each job description.**
   - **"Build ticked resumes":** every tracker row with **Build Resume** ticked, lowest ID first. **Named rows:** exactly those. Build the first 3, then check in before doing more.
   - For a tracker row, the JD is the saved `<ID>_JD.md` (`search_files` with `title = '<ID>_JD.md'`). If there isn't one, skip the row, leave it ticked, and report "run Tier 2 first". Don't search for the JD here.
   - **Pasted or attached JD** with no tracker row: use it as given.
   - If there is no usable JD, stop and ask. Never tailor to a job title alone.
2. **Read both files** (content source, template). Download the template to a scratch directory; don't edit it in place.
3. **Map the job to the inventory.** Load `job-fit-rubric` and build its evidence table (each JD requirement quoted, marked required or preferred, matched strong/partial/none to a pointer in the full resume). For a tracker row, start from the evidence table in its latest fit report (`title contains '<ID>_fit_r'`, highest run): keep its requirement list and check each match against the current full resume, since the user may have edited it since. Use the table as the selection guide: strong matches get the most room, `none` matches are gaps.
4. **Write `content.json`** (shape below) using only what the inventory supports:
   - Keep every employer, title, location and date exactly as in the inventory. Never change dates, titles, numbers, team sizes, technologies or outcomes.
   - Reword for the JD's vocabulary only when the inventory already says the same thing (e.g. "ATO process" if the inventory says Authority to Operate). Never add a skill, tool, credential, metric or responsibility the inventory doesn't contain, even if the JD asks for it.
   - Headline: a short all-caps line matching the target role, built from titles and strengths the user really has.
   - Competencies: at most 12, only ones the inventory evidences, ordered by JD relevance.
   - Career highlights: 3 to 5, the strongest matches to the JD's required items.
   - Experience: all roles stay, newest first. Give the most bullets to the roles that best match the JD, trim older or less relevant roles to 1-3 bullets, and drop a role's summary before dropping a strong bullet.
   - Education and certifications: include as in the inventory (certification credential IDs are optional; leave them out to save space).
5. **Build:** run `build_resume.py` with `--pdf`. If `pages` isn't 2, adjust and rebuild: over 2 pages, trim the least relevant bullets and shorten summaries; under 2, restore relevant bullets from the inventory (never pad with filler). Repeat until it's exactly 2 pages. Look at the PDF (convert to an image) to check nothing is broken: dates line up at the right margin, no sample text, no stray blank page.
6. **Check truthfulness.** For every bullet, headline, highlight and competency in the output, confirm it traces to a line in the full resume. Fix or remove anything that doesn't. Do not skip this even when running unattended.
7. **Deliver and save.** Everything for one job goes in its company folder, `<tracker folder>/<Company_Folder>/` (naming rule in `job-tracker`; e.g. `Acme_Corp/`). Reuse the folder if it already exists, and create it if not. In it put:
   - `<Tailored resume prefix>_<Company>_<Role>.docx` and `.pdf` (the prefix from the profile, e.g. `Jane_Example_Resume_Acme_Corp_Program_Manager.pdf`). If a resume with that name is already there, add `_v2`, `_v3` and so on; never overwrite an earlier one.
   - For a pasted JD only: `<Tailored resume prefix>_<Company>_<Role>_JD.txt` with the job description, so it's there if an interview follows. Tracker rows already have `<ID>_JD.md` in the same folder.
   Put each job's JD only beside the resumes made for that job. On the user's computer, write the files straight into that folder. From the cloud, create the subfolder and upload through the Drive connector if the files are small enough; otherwise send them with SendUserFile and say which folder to put them in. For a tracker row, write **Tailored Resume** (a link to the PDF, labelled with its file name), **Resume Created** and **Last Updated** (today), then untick **Build Resume** as the last write (`job-tracker` has the rules). If the build failed or wasn't exactly 2 pages, leave the box ticked and say why. Never touch Status or Next Action / Notes.
8. **Tell the user the gaps.** End with the required JD items the inventory has no evidence for, so they can decide whether the inventory is missing something true (then they add it to their full resume) or it's a real gap.

## content.json shape
```json
{
  "name": "JANE EXAMPLE",
  "contact": ["phone", "city, state", "email", "linkedin url"],
  "headline": "ALL CAPS ROLE-ALIGNED HEADLINE",
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
- Never edits the full resume, the template, or any earlier tailored resume.
- Never commits the template, the inventory, a generated resume or a JD to the repo (public portfolio repo).
- Never sends a resume or applies to a job; the user does that.
- Never runs on a schedule. Building a resume is always the user's explicit request.
- If the template or inventory can't be found, or the output can't be brought to exactly 2 pages, say so rather than delivering something off-format.

## End-of-run summary
- Job and files produced (names, where they're saved), page count, and which tracker rows were unticked.
- Ticked rows skipped, and why (no saved JD, build failed).
- What was emphasized and what was trimmed.
- Gaps: required JD items with no support in the inventory.
- Anything you couldn't verify.
