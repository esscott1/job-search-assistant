# Full resume format

The full resume is one Markdown file, usually `Full-Resume.md` in the job-search folder. It holds the user's **whole** career, not a two-page selection: every role, project, tool, certification and accomplishment. Every fit score and every tailored resume comes only from this file, so anything missing from it shows up as a gap, and tailored resumes choose from it, never add to it.

## Rules

- **Keep everything.** Never trim to fit a page; tailored resumes do the selecting.
- **Write each fact once, in the user's words.** When converting an existing resume, keep bullets and summaries word for word. Don't reword, merge, or add anything the source doesn't say.
- **Dates and titles exactly as the user gives them.** Any of `2018 - Present`, `June 2024 – August 2026`, `2012 - 2018` work.
- **No company descriptions are needed.** If the source has one (an italic line under the employer), it may stay, but tailored resumes never show it.

## Layout

The work history uses two heading levels, which the resume checks read (`check_content.py`):

```markdown
# JANE EXAMPLE
Columbus, OH · jane@example.com · 555-0100 · linkedin.com/in/jane-example

## Summary
Two to four sentences.

## Core Competencies
- One skill per line

## Professional Experience

### Example Corp, Columbus, OH | 2018 - Present
#### Director, IT Program Delivery, Columbus, OH | 2021 - Present
One optional line describing the role.
- One accomplishment per bullet.
#### Senior IT Program Manager, Columbus, OH | 2018 - 2021
- …

### Sample Systems, Dayton, OH | 2012 - 2018
#### IT Project Manager, Dayton, OH | 2012 - 2018
- …

## Additional Experience
- Older or minor roles, one line each, if the user wants them kept but not as headings.

## Education
- **Degree**, School, Year

## Certifications
- Name, Issuer, Year (credential IDs optional)
```

- **`### Employer, Location | dates`** for each employer, newest first.
- **`#### Title, Location | dates`** for each role under it, newest first. An employer with one role still gets its `####` line.
- Each role has at least one line under it: a summary line or a bullet.
- The first line is the user's name; the second is the contact line tailored resumes copy.

## Converting an existing resume

When the user attaches a `.docx` or `.pdf` (or pastes text) during setup:
1. Extract the text: `python3 -c "import docx,sys; print('\n'.join(p.text for p in docx.Document(sys.argv[1]).paragraphs))" resume.docx`, or `pdftotext -layout resume.pdf -`.
2. Arrange it in the layout above. Keep every line; put anything that doesn't fit a section under `## Additional Information` rather than dropping it.
3. Run `python3 <tailored-resume-builder folder>/check_content.py --inventory Full-Resume.md` and check every employer and role it lists against the source.
4. Show the user the roles found (newest first) and anything you couldn't place, and save only after they confirm.
