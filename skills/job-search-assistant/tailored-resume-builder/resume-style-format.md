# Resume style file format (version 1)

A user's resume look is a small Markdown file, `resume-style.md`, kept in their job-search folder next to `job-search-profile.md`. `render_resume.py` reads it and builds the .docx (and PDF) from scratch, so any user's look works and no Word template has to travel through the Drive connector. `default-style.md` in this folder is the style used when the profile names none, and is a complete example.

Like the profile, it's plain text: one `- Key: value` line per setting under a section heading. A skill writes it, and the user can edit it by hand. `render_resume.py` rejects an unknown section, key or value with exit code 2 and names the line.

## Header
- `# Resume style` on the first line.
- `Style format: 1`: required. The renderer refuses other versions.
- `Source: <template file it was converted from, or "plugin default">, <date>`: informational.
- Any other text before the first `##` section is ignored.

## `## Page`
| Key | Value |
|---|---|
| Size | `Letter` or `A4` |
| Margins (in) | `top 0.5, bottom 0.5, left 0.6, right 0.6`, or one number for all four |

## `## Text`
Each line styles one kind of text. The value is a comma-separated list, in any order, of:
- a font name, such as `Calibri` or `Garamond`;
- a size in points, such as `10.5`;
- `bold`, `italic`, `caps`, `underline`;
- `color RRGGBB`, a hex colour such as `color 1F3864`;
- `rule`, for **Section headings** only: a line under the heading.

Anything not given is taken from **Body**: its font, size and colour. Bold, italic, caps and underline are off unless listed.

| Key | Styles |
|---|---|
| Body | Summary, bullets, everything not listed below. Must give a font and a size |
| Name | The name at the top |
| Headline | The role-aligned line under the name |
| Contact | The contact line |
| Section headings | Section titles |
| Company | Employer name on the company line |
| Company description | Accepted so older style files still load, but not used: tailored resumes don't show company descriptions |
| Role | Job title on the role line |
| Location | Locations on company and role lines |
| Dates | Dates on company and role lines |

## `## Layout`
| Key | Value |
|---|---|
| Header alignment | `left` or `center`: name, headline and contact line |
| Header order | `name, headline, contact` in any order |
| Section heading alignment | `left` or `center` |
| Contact separator | Text between contact items. Quote it to keep spaces: `" · "` |
| Section order | Comma-separated, from: `summary, competencies, highlights, experience, education, certifications, additional`. Sections left out aren't shown |
| Section titles | `section = Title` pairs separated by `;`. An empty title (`summary = `) shows the section without a heading. Sections not listed use a plain default title |
| Competencies | `grid N`: a borderless table with N columns (1-4). Or `inline "<separator>"`: one line |
| Bullet | The bullet character, such as `•`, `▪`, `–` |
| Dates | `right`: dates right-aligned on the company and role lines. Or `inline`: after the title, separated by ` \| ` |
| Accomplishments label | A line before each role's bullets, such as `Key Accomplishments:`. Empty for none |
| Space after section heading (pt) | A number |
| Space between roles (pt) | A number |

## `## Not carried over`
A free-form list. When the style was converted from a Word template, this names anything the renderer can't reproduce: images, text boxes, sidebar columns, header or footer content, unusual fonts. The renderer ignores it; it's there so the user knows.
