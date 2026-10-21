#!/usr/bin/env python3
"""Build the eval mocks from the readable fixtures, so the two can't drift apart.

    python build_mocks.py           # write the mocks
    python build_mocks.py --check   # exit 1 if any mock is out of date (CI runs this via pytest)

Sources (edit these, then rebuild):
- fixtures/*.md: the synthetic Drive files (profile, full resumes, saved JDs, fit reports).
- fixtures/web/: pages and feeds the stub web fetch serves, one fixed reply ("web") or one per URL ("web_pages").
- DRIVE, TRACKER_ROWS and CASES below: what each case's Drive and Job Log contain.

Outputs:
- mocks/gdrive/...: shared Drive mocks; download_file_content serves fixtures by file id.
- mocks/gsheets/get_values.md: the shared Job Log (nothing ticked).
- <case>/mocks/...: per-case overrides, and <case>/gstub/: the connector stub plugin. A case with
  its own Job Log gets a Sheets mock played by a small model (type: agent) that keeps the
  sheet's state, so read-after-write checks in the skills see their own writes.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"

FOLDER = "FOLDER_EVAL_0001"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SHEET = "SHEET_EVAL_0001"

# Drive file id -> (title, source fixture, parent folder id, mimeType)
DRIVE = {
    "FILE_PROFILE_0001": ("job-search-profile.md", "job-search-profile.md", FOLDER, "text/markdown"),
    "FILE_RESUME_0001": ("Full-Resume.md", "Full-Resume.md", FOLDER, "text/markdown"),
    "FILE_JD_JS101": ("JS-101_JD.md", "JS-101_JD.md", "FOLDER_Northwind_Logistics", "text/markdown"),
    "FILE_JD_JS102": ("JS-102_JD.md", "JS-102_JD.md", "FOLDER_Contoso_Health", "text/markdown"),
    "FILE_JD_JS103": ("JS-103_JD.md", "JS-103_JD.md", "FOLDER_Fabrikam_Robotics", "text/markdown"),
    "FILE_STYLE_0001": ("resume-style.md", "resume-style.md", FOLDER, "text/markdown"),
}
FOLDERS = {
    FOLDER: ("Job Search", "root"),
    "FOLDER_Northwind_Logistics": ("Northwind_Logistics", FOLDER),
    "FOLDER_Contoso_Health": ("Contoso_Health", FOLDER),
    "FOLDER_Fabrikam_Robotics": ("Fabrikam_Robotics", FOLDER),
}

HEADERS = [
    "ID", "Date Found", "Source", "Company", "Job Title", "Job Description", "Type / Location",
    "Pay Range", "Fit Score (1-10)", "Score Tier", "Gaps", "Fit Report", "Run Tier 2",
    "Build Resume", "Status", "Next Action / Notes", "Contact / Referrer", "Tailored Resume",
    "Resume Created", "Date Submitted", "Submission Email", "Last Updated", "Source Email",
    "Gmail Message ID", "Email Received", "Score Breakdown", "Tier 2 Date", "Canonical URL",
]

# id -> (company, title, location, Tier 1 score, posting URL)
TRACKER_ROWS = {
    "JS-101": ("Northwind Logistics", "Senior IT Program Manager, Cloud", "Remote (US)", 8,
               "https://careers.northwind.example/jobs/101"),
    "JS-102": ("Contoso Health", "IT Program Manager, Data Platforms", "Columbus, OH (hybrid)", 7,
               "https://careers.contosohealth.example/jobs/102"),
    "JS-103": ("Fabrikam Robotics", "Senior Software Engineer, Rust", "Austin, TX (on-site)", 3,
               "https://careers.fabrikam.example/jobs/103"),
    "JS-002": ("Acme Widgets", "Senior Cloud Program Manager", "Remote", 7,
               "https://www.linkedin.com/jobs/view/4000000002/"),
    "JS-001": ("Example Corp", "IT Vendor Manager", "Remote", 6,
               "https://www.linkedin.com/jobs/view/4000000001/"),
    # cleanup cases: all found long ago; each differs in one way the cleanup rules care about
    "JS-010": ("Vandelay Example", "IT Program Manager", "Remote", 5, "https://www.linkedin.com/jobs/view/4000000010/"),
    "JS-011": ("Hooli Example", "Cloud Program Lead", "Remote", 6, "https://www.linkedin.com/jobs/view/4000000011/"),
    "JS-012": ("Pied Piper Example", "Senior Program Manager", "Remote", 7, "https://www.linkedin.com/jobs/view/4000000012/"),
    "JS-013": ("Wonka Example", "IT Vendor Manager", "Remote", 6, "https://www.linkedin.com/jobs/view/4000000013/"),
    "JS-014": ("Stark Example", "Technical Program Manager", "Remote", 7, "https://www.linkedin.com/jobs/view/4000000014/"),
    "JS-015": ("Wayne Example", "Program Manager, Cloud", "Remote", 8, "https://www.linkedin.com/jobs/view/4000000015/"),
    "JS-016": ("Tyrell Example", "IT Program Director", "Remote", 6, "https://www.linkedin.com/jobs/view/4000000016/"),
    "JS-005": ("Umbrella Example", "Program Manager, Infrastructure", "Remote", 5,
               "https://www.linkedin.com/jobs/view/4000000005/"),
}

OLD = "2025-08-04"  # long past any archive age, so cleanup cases stay valid over time
CLEANUP_ROWS = ["JS-010", "JS-011", "JS-012", "JS-013", "JS-014", "JS-015", "JS-016"]
# Row overrides {id: {header: value}}: what the user has done to each cleanup row
CLEANUP_CHANGES = {
    **{r: {"Date Found": OLD, "Last Updated": OLD, "Email Received": OLD} for r in CLEANUP_ROWS},
}
CLEANUP_CHANGES["JS-012"]["Run Tier 2"] = True
CLEANUP_CHANGES["JS-013"]["Next Action / Notes"] = "Call the recruiter on Monday"
CLEANUP_CHANGES["JS-014"]["Status"] = "Submitted"
CLEANUP_CHANGES["JS-015"]["Tailored Resume"] = "Jane_Example_Resume_Wayne_Example_Program_Manager.pdf"
CLEANUP_CHANGES["JS-016"]["Build Resume"] = True

# Cases with their own Job Log or Drive. "ticked": rows with Run Tier 2 TRUE; "build": rows
# with Build Resume TRUE. "drive": extra or replacement Drive files
# {file id: (title, fixture, parent, mimeType)}, or {file id: None} to remove one.
CASES = {
    "tier2-nothing-ticked": {},
    "tier2-gold-strong-fit": {"rows": ["JS-101", "JS-002"], "ticked": ["JS-101"]},
    "tier2-gold-partial-fit": {"rows": ["JS-102", "JS-002"], "ticked": ["JS-102"]},
    "tier2-gold-relocation-mismatch": {"rows": ["JS-103", "JS-002"], "ticked": ["JS-103"]},
    "resume-tailors-pasted-jd": {},
    "profile-convert-template": {},
    "profile-style-update": {},
    # first-time setup: no profile yet, so the skill starts the interview
    "profile-setup-starts-brief": {"drive": {"FILE_PROFILE_0001": None}},
    "profile-setup-prefills-from-resume": {"drive": {"FILE_PROFILE_0001": None}},
    "profile-setup-saves-pasted-resume": {"drive": {"FILE_PROFILE_0001": None, "FILE_RESUME_0001": None}},
    "profile-setup-checks-style-file": {},
    "profile-update-is-brief": {},
    "resume-does-not-invent": {},
    "resume-delivers-to-synced-folder": {
        "drive": {"FILE_PROFILE_0001": ("job-search-profile.md", "job-search-profile-local.md", FOLDER, "text/markdown")},
    },
    "resume-full-resume-missing": {
        "drive": {
            "FILE_RESUME_0001": None,
            "FILE_OLD_RESUME_0001": ("Old-Resume.docx", "Old-Resume.docx", FOLDER, DOCX),
        },
    },
    "resume-ticked-row-needs-jd": {"rows": ["JS-002", "JS-001"], "ticked": [], "build": ["JS-002"]},
    "resume-history-rules": {
        "drive": {
            "FILE_PROFILE_0001": ("job-search-profile.md", "job-search-profile-local.md", FOLDER, "text/markdown"),
            "FILE_RESUME_0001": ("Full-Resume.md", "Full-Resume-history.md", FOLDER, "text/markdown"),
        },
    },
    "resume-honours-requested-page-limit": {},
    "cleanup-archives-untouched-rows": {"rows": CLEANUP_ROWS, "ticked": [], "changes": CLEANUP_CHANGES,
                                        "archive": ["JS-005"]},
    "cleanup-creates-archive-tab": {"rows": ["JS-010", "JS-014"], "ticked": [], "changes": CLEANUP_CHANGES,
                                    "archive": None},
    "cleanup-honours-archive-age": {
        "rows": ["JS-010", "JS-011"], "ticked": [], "changes": CLEANUP_CHANGES, "archive": ["JS-005"],
        "drive": {"FILE_PROFILE_0001": ("job-search-profile.md", "job-search-profile-archive-never.md", FOLDER, "text/markdown")},
    },
    "cleanup-restores-a-row": {"rows": ["JS-002", "JS-001"], "ticked": [], "archive": ["JS-005"]},
    "intake-logs-new-leads": {"rows": ["JS-002", "JS-001"], "ticked": [], "archive": ["JS-005"], "inbox": "inbox.json"},
    "intake-scans-career-site": {
        "rows": ["JS-101", "JS-002"], "ticked": [], "archive": ["JS-005"], "web": "web/northwind-feed.json",
        "drive": {"FILE_PROFILE_0001": ("job-search-profile.md", "job-search-profile-careers.md", FOLDER, "text/markdown")},
    },
    # A career site whose posting pages read as plain text show a "filled" banner and no description,
    # and an open posting that says it "will remain active until the position is filled".
    "intake-banner-is-not-closed": {
        "rows": ["JS-002", "JS-001"], "ticked": [], "archive": ["JS-005"],
        "web_pages": {
            "https://careers.tailspin.example/global/en/search-results?keywords=program%20manager":
                "web/tailspin-search-results.md",
            "https://careers.tailspin.example/global/en/job/TS4401/Program-Manager-Cloud-Operations":
                "web/tailspin-TS4401-banner-only.md",
            "https://careers.tailspin.example/global/en/job/TS4402/IT-Vendor-Manager": "web/tailspin-TS4402-posting.md",
        },
        "drive": {"FILE_PROFILE_0001": ("job-search-profile.md", "job-search-profile-careers-page.md", FOLDER,
                                        "text/markdown")},
    },
    "intake-nothing-to-scan": {
        "rows": ["JS-002", "JS-001"], "ticked": [], "archive": ["JS-005"],
        "drive": {"FILE_PROFILE_0001": ("job-search-profile.md", "job-search-profile-no-sources.md", FOLDER, "text/markdown")},
    },
    "tier2-rescore-closes-gap": {
        "rows": ["JS-102", "JS-002"],
        "ticked": ["JS-102"],
        "tier": {"JS-102": ("T2", 7, "Rubric v1.1 | Req 3.5/6 · Pref 1/3 · coverage 55% · Title strong · Commutable hybrid | raw 6.8 → 7")},
        "drive": {
            "FILE_RESUME_0001": ("Full-Resume.md", "Full-Resume-v2.md", FOLDER, "text/markdown"),
            "FILE_FIT_JS102_R1": ("JS-102_fit_r1_2026-10-14.md", "JS-102_fit_r1_2026-10-14.md",
                                  "FOLDER_Contoso_Health", "text/markdown"),
        },
    },
}

# The connector stub is a plugin with no manifest: just .mcp.json, so its name comes from its
# folder ("gstub"). Keeping .claude-plugin/ folders out of the plugin tree means nothing inside
# evals/ can be mistaken for a real plugin by tools that scan the repository.
STUB = {
    "mcpServers": {
        "gdrive": {"command": "python", "args": ["-c", "raise SystemExit('eval stub: mocked only')"]},
        "gsheets": {"command": "python", "args": ["-c", "raise SystemExit('eval stub: mocked only')"]},
        "gmail": {"command": "python", "args": ["-c", "raise SystemExit('eval stub: mocked only')"]},
        # Stands in for web fetching in cases that disallow the built-in WebFetch, so they read
        # their pages from fixtures/ instead of the network.
        "web": {"command": "python", "args": ["-c", "raise SystemExit('eval stub: mocked only')"]},
    },
}

WEB_TOOLS = {"tools": [{
    "name": "fetch",
    "description": "Fetches a URL and returns its content as text (pages, JSON feeds).",
    "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "prompt": {"type": "string"}},
                    "required": ["url"]},
}]}

# Each created file gets its own id, made from its title, so a run that creates a folder and then
# files inside it doesn't see one id come back for all of them.
CREATE_FILE = {
    "id": "NEW_{{input.title}}",
    "title": "{{input.title}}",
    "viewUrl": "https://drive.google.com/file/d/NEW_{{input.title}}/view",
}

# Renaming and trashing, which the profile skill uses to replace its own files. The real connector
# has both, and without them a run can't follow the skill's write steps.
UPDATE_FILE = {"id": "{{input.fileId}}", "title": "{{input.title}}"}
TRASH_FILE = {"id": "{{input.fileId}}", "trashed": True}


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def row(job_id: str, ticked: bool, tier: tuple | None, build: bool = False, changes: dict | None = None) -> list:
    company, title, location, t1, url = TRACKER_ROWS[job_id]
    cells = dict.fromkeys(HEADERS, "")
    score_tier, score, breakdown = tier or ("T1", t1, "Alert email | Rubric v1.1 | Tier 1")
    cells.update({
        "ID": job_id, "Date Found": "2026-10-12", "Source": "LinkedIn alerts", "Company": company,
        "Job Title": title, "Job Description": "View posting", "Type / Location": location,
        "Fit Score (1-10)": score, "Score Tier": score_tier, "Gaps": "• JD not read yet",
        "Run Tier 2": ticked, "Build Resume": build, "Status": "Need to review",
        "Last Updated": "2026-10-12", "Email Received": "2026-10-12", "Score Breakdown": breakdown,
        "Canonical URL": url,
    })
    cells.update((changes or {}).get(job_id, {}))
    return [cells[h] for h in HEADERS]


def job_log(rows: list[str], ticked: list[str], tiers: dict) -> str:
    values = [HEADERS] + [row(r, r in ticked, tiers.get(r)) for r in rows]
    end_row = len(values)
    return dumps({"range": f"Job Log!A1:AB{end_row}", "majorDimension": "ROWS", "values": values})


SHEET_AGENT = """---
type: agent
---

You play the Google Sheets API for one spreadsheet, {sheet}, titled Job_Search_Tracker. Its tabs: {tabs}.

The Job Log starts as this grid (row 1 is the header; columns A to AB). It has {log_rows} rows: the header plus {log_data} data rows, so its gridProperties.rowCount starts at {log_rows}:
{grid}
{archive}
Behave like the real API, and keep state for the whole conversation. Every write applies to the grids, so later reads see it. Before answering any call, work out each tab's current grid step by step from its starting grid and every write so far; never drop or duplicate a row by accident.
Row indexes in requests are 0-based: index 0 is the header (row 1 in A1 notation), index 1 is the first data row. gridProperties.rowCount is the number of rows the tab has right now, header included.
- get_values: return {{"range": ..., "majorDimension": "ROWS", "values": [...]}} for the requested A1 range.
- update_values / update_formulas: apply the values or formulas to the range and return {{"updatedRange": ..., "updatedRows": n, "updatedColumns": n, "updatedCells": n}}. A formula such as =HYPERLINK("url","label") reads back through get_values as its label.
- insert_dimension: insert empty rows (or columns) at startIndex..endIndex (0-based) in the sheet with that sheetId, shifting the rest down; return {{}}.
- get_spreadsheet: return {{"spreadsheetId", "properties": {{"title"}}, "sheets": [{{"properties": {{"sheetId", "title", "gridProperties"}}}}]}} and the current "revisionId" (start at "rev-1"; every write makes a new one: rev-2, rev-3, ...). With includeGridData true, include "data": [{{"rowData": [{{"values": [{{"userEnteredValue": {{"stringValue"|"numberValue"|"boolValue"|"formulaValue": ...}}}}]}}]}}] for the requested ranges.
- update_spreadsheet: apply the requests strictly in order, each to the result of the one before (addSheet, insertDimension, deleteDimension, updateCells, updateSheetProperties, ...). insertDimension adds empty rows at startIndex..endIndex-1 and shifts the rows from startIndex down; deleteDimension removes rows startIndex..endIndex-1 and shifts later rows up; updateCells writes its rows starting at start.rowIndex/columnIndex (or the range's top-left). Rows not named by a request never change. If writeControl.requiredRevisionId is given and isn't the current revision, change nothing and return an error saying the revision doesn't match. Otherwise return {{"spreadsheetId", "replies": [...], "writeControl": {{"requiredRevisionId": <new revision>}}}}.
Reply with JSON only.
"""


def sheet_agent(rows: list[str], ticked: list[str], tiers: dict, build: list[str] = (), changes: dict | None = None,
                archive: list[str] | None = ()) -> str:
    """A Sheets mock played by a small model, so a read after a write sees the write.

    Skills re-find a row before writing and may read it back afterwards; a fixed mock would
    return the old row and make a correct run look like a failed write.
    """
    grid = [HEADERS] + [row(r, r in ticked, tiers.get(r), r in build, changes) for r in rows]
    if archive is None:
        tabs, archive_text = '"Job Log" (sheetId 0) and "Status Guide" (1). There is no Archive tab yet', ""
    else:
        tabs = '"Job Log" (sheetId 0), "Status Guide" (1) and "Archive" (2)'
        old = {r: {"Date Found": OLD, "Last Updated": OLD, "Email Received": OLD} for r in archive}
        archived = [row(r, False, None, False, {**old, **(changes or {})}) + ["2025-09-15"] for r in archive]
        archive_text = (f"\nThe Archive starts as this grid (row 1 is the header; the Job Log's columns, then Archived On). "
                        f"It has {len(archived) + 1} rows: the header plus {len(archived)} data rows:\n"
                        + json.dumps([HEADERS + ["Archived On"]] + archived, ensure_ascii=False) + "\n")
    return SHEET_AGENT.format(sheet=SHEET, tabs=tabs, grid=json.dumps(grid, ensure_ascii=False), archive=archive_text,
                              log_rows=len(grid), log_data=len(grid) - 1)


GMAIL_AGENT = """---
type: agent
---

You play the Gmail API for one mailbox. These are all its messages (each is its own thread):
{inbox}

Treat every message as recent enough to match any date limit in a query (newer_than:, after:, older_than: and the like), and filter only on the other operators (from:, subject:, OR, -, ...).
- search_threads: return {{"threads": [{{"id": <threadId>, "messages": [{{"id", "sender", "subject", "snippet" (first 120 characters of the body), "date"}}]}}]}} for the matching messages, or {{}} if none match.
- get_thread: return {{"id": <threadId>, "messages": [{{"id", "sender", "subject", "date", "plaintext_body"}}]}} with the body exactly as given above.
Reply with JSON only.
"""


def gmail_agent(inbox: str) -> str:
    """A Gmail mock played by a small model, so search queries filter the fixture inbox."""
    messages = json.loads((FIXTURES / inbox).read_text(encoding="utf-8"))
    return GMAIL_AGENT.format(inbox=json.dumps(messages, ensure_ascii=False, indent=1))


WEB_AGENT = """---
type: agent
---

You play a web fetch tool. It returns a page as plain text, the way a page reader that drops scripts sees it. These are the only pages that exist, each under its URL:
{pages}

- fetch: if the url is one of the URLs above (ignoring the scheme, a trailing slash and letter case), return that page's text exactly as given. For any other URL, return exactly: 404 Not Found: there is no page at <url>
Return the page text only, with nothing added.
"""


def web_agent(pages: dict[str, str]) -> str:
    """A web mock played by a small model, so each URL gets its own page."""
    listing = "\n".join(f"\n=== {url}\n{(FIXTURES / source).read_text(encoding='utf-8').strip()}"
                        for url, source in pages.items())
    return WEB_AGENT.format(pages=listing)


def drive_files(files: dict) -> dict[str, str]:
    """The Drive mocks for one set of files: search lists everything, download serves by id."""
    listing = [
        {"id": fid, "title": title, "mimeType": "application/vnd.google-apps.folder", "parentId": parent}
        for fid, (title, parent) in FOLDERS.items()
    ] + [
        {"id": fid, "title": title, "mimeType": mime, "parentId": parent, "modifiedTime": "2026-10-13T12:00:00Z"}
        for fid, (title, _, parent, mime) in files.items()
    ]
    out = {
        "search_files.md": dumps({"files": listing}),
        "download_file_content.md": "{{file:fixtures/{input.fileId}.json}}\n",
        "create_file.md": dumps(CREATE_FILE),
        "update_file.md": dumps(UPDATE_FILE),
        "trash_file.md": dumps(TRASH_FILE),
    }
    for fid, (_, source, _, mime) in files.items():
        path = FIXTURES / source
        # Text is read with universal newlines so a Windows checkout builds the same mocks.
        data = path.read_text(encoding="utf-8").encode() if mime.startswith("text/") else path.read_bytes()
        out[f"fixtures/{fid}.json"] = dumps({"content": base64.b64encode(data).decode(), "mimeType": mime})
    return out


def build() -> dict[Path, str]:
    out: dict[Path, str] = {}
    for name, text in drive_files(DRIVE).items():
        out[HERE / "mocks/gdrive" / name] = text
    out[HERE / "mocks/gsheets/get_values.md"] = job_log(["JS-002", "JS-001"], [], {})
    for case, spec in CASES.items():
        out[HERE / case / "gstub/.mcp.json"] = dumps(STUB)
        if "rows" in spec:
            agent = sheet_agent(spec["rows"], spec["ticked"], spec.get("tier", {}), spec.get("build", []),
                                spec.get("changes"), spec.get("archive", ()))
            for tool in ("get_values", "update_values", "get_spreadsheet", "update_formulas", "insert_dimension",
                         "update_spreadsheet"):
                out[HERE / case / f"mocks/gsheets/{tool}.md"] = agent
        if "web" in spec:
            out[HERE / case / "mocks/web/_tools.json"] = dumps(WEB_TOOLS)
            out[HERE / case / "mocks/web/fetch.md"] = (FIXTURES / spec["web"]).read_text(encoding="utf-8")
        if "web_pages" in spec:
            out[HERE / case / "mocks/web/_tools.json"] = dumps(WEB_TOOLS)
            out[HERE / case / "mocks/web/fetch.md"] = web_agent(spec["web_pages"])
        if "inbox" in spec:
            agent = gmail_agent(spec["inbox"])
            for tool in ("search_threads", "get_thread"):
                out[HERE / case / f"mocks/gmail/{tool}.md"] = agent
        if "drive" in spec:
            files = {k: v for k, v in {**DRIVE, **spec["drive"]}.items() if v is not None}
            for name, text in drive_files(files).items():
                out[HERE / case / "mocks/gdrive" / name] = text
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    built = build()
    # Generated Drive fixtures this build no longer produces (a file removed from DRIVE or a case)
    for leftover in sorted(HERE.glob("**/mocks/gdrive/fixtures/*.json")):
        if leftover not in built:
            stale.append(leftover.relative_to(HERE))
            if not check:
                leftover.unlink()
    for path, text in built.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(path.relative_to(HERE))
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    if check and stale:
        print("Out of date (run python build_mocks.py):", *stale, sep="\n  ")
        return 1
    print(f"{len(stale)} file(s) {'stale' if check else 'written'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
