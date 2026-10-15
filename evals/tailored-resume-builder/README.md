# Evals: tailored-resume-builder

Cases for [`tailored-resume-builder`](../../skills/job-search-assistant/tailored-resume-builder/SKILL.md): it should tailor from the inventory only, report gaps instead of filling them, and stop when it lacks a JD or the inventory.

| # | Case | What it proves |
|---|---|---|
| 1 | Cloud-migration JD | Selects and orders true content, 2 pages, files saved together in a company folder |
| 2 | No JD | Asks instead of guessing |
| 3 | JD requires CKA and Rust | Never invents missing skills; lists them as gaps |
| 4 | Inventory missing | Stops; no fallback to an older Word resume |

Fixtures are synthetic (a fictional person and fictional companies); nothing here comes from a real person's resume. The real template isn't in the repo, so case 1's layout checks need it supplied.

The mechanical checks (layout preserved, input validation, page warning) are unit tests: `TEMPLATE=/path/to/Job-Seeker-6-Resume-Template-.docx python3 -m pytest -q skills/job-search-assistant/tailored-resume-builder`.

Run the cases with skill-creator against `skills/job-search-assistant/tailored-resume-builder/`, as for [`sally-audit`](../sally-audit/README.md). No results are committed yet.
