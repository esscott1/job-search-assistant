#!/usr/bin/env python3
"""Build the eval mocks from the readable fixtures, so the two can't drift apart.

    python build_mocks.py           # write the mocks
    python build_mocks.py --check   # exit 1 if any mock is out of date (CI runs this via pytest)

Sources (edit these, then rebuild):
- fixtures/*.md: the synthetic Drive files (profile, full resumes, saved JDs, fit reports).
- DRIVE, TRACKER_ROWS and CASES below: what each case's Drive and Job Log contain.

Outputs:
- mocks/gdrive/...: shared Drive mocks; download_file_content serves fixtures by file id.
- mocks/gsheets/get_values.md: the shared Job Log (nothing ticked).
- <case>/mocks/...: per-case overrides, and <case>/gstub/: the connector stub plugin.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"

FOLDER = "FOLDER_EVAL_0001"
SHEET = "SHEET_EVAL_0001"

# Drive file id -> (title, source fixture, parent folder id, mimeType)
DRIVE = {
    "FILE_PROFILE_0001": ("job-search-profile.md", "job-search-profile.md", FOLDER, "text/markdown"),
    "FILE_RESUME_0001": ("Full-Resume.md", "Full-Resume.md", FOLDER, "text/markdown"),
    "FILE_JD_JS101": ("JS-101_JD.md", "JS-101_JD.md", "FOLDER_Northwind_Logistics", "text/markdown"),
    "FILE_JD_JS102": ("JS-102_JD.md", "JS-102_JD.md", "FOLDER_Contoso_Health", "text/markdown"),
    "FILE_JD_JS103": ("JS-103_JD.md", "JS-103_JD.md", "FOLDER_Fabrikam_Robotics", "text/markdown"),
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
}

# Cases with their own Job Log or Drive. "ticked": rows with Run Tier 2 TRUE.
# "drive": extra or replacement Drive files {file id: (title, fixture, parent, mimeType)}.
CASES = {
    "tier2-nothing-ticked": {},
    "tier2-gold-strong-fit": {"rows": ["JS-101", "JS-002"], "ticked": ["JS-101"]},
    "tier2-gold-partial-fit": {"rows": ["JS-102", "JS-002"], "ticked": ["JS-102"]},
    "tier2-gold-relocation-mismatch": {"rows": ["JS-103", "JS-002"], "ticked": ["JS-103"]},
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

STUB = {
    "name": "gstub",
    "version": "0.0.0",
    "description": "Eval-only stand-ins for the Google Drive and Google Sheets connectors. "
    "Every tool is mocked; the servers are never started.",
    "mcpServers": {
        "gdrive": {"command": "python", "args": ["-c", "raise SystemExit('eval stub: mocked only')"]},
        "gsheets": {"command": "python", "args": ["-c", "raise SystemExit('eval stub: mocked only')"]},
    },
}

CREATE_FILE = {
    "id": "FILE_NEW_0001",
    "title": "{{input.title}}",
    "viewUrl": "https://drive.google.com/file/d/FILE_NEW_0001/view",
}


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def row(job_id: str, ticked: bool, tier: tuple | None) -> list:
    company, title, location, t1, url = TRACKER_ROWS[job_id]
    cells = dict.fromkeys(HEADERS, "")
    score_tier, score, breakdown = tier or ("T1", t1, "Alert email | Rubric v1.1 | Tier 1")
    cells.update({
        "ID": job_id, "Date Found": "2026-10-12", "Source": "LinkedIn alerts", "Company": company,
        "Job Title": title, "Job Description": "View posting", "Type / Location": location,
        "Fit Score (1-10)": score, "Score Tier": score_tier, "Gaps": "• JD not read yet",
        "Run Tier 2": ticked, "Build Resume": False, "Status": "Need to review",
        "Last Updated": "2026-10-12", "Email Received": "2026-10-12", "Score Breakdown": breakdown,
        "Canonical URL": url,
    })
    return [cells[h] for h in HEADERS]


def job_log(rows: list[str], ticked: list[str], tiers: dict) -> str:
    values = [HEADERS] + [row(r, r in ticked, tiers.get(r)) for r in rows]
    end_row = len(values)
    return dumps({"range": f"Job Log!A1:AB{end_row}", "majorDimension": "ROWS", "values": values})


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
    }
    for fid, (_, source, _, mime) in files.items():
        text = (FIXTURES / source).read_text(encoding="utf-8")
        out[f"fixtures/{fid}.json"] = dumps({"content": base64.b64encode(text.encode()).decode(), "mimeType": mime})
    return out


def build() -> dict[Path, str]:
    out: dict[Path, str] = {}
    for name, text in drive_files(DRIVE).items():
        out[HERE / "mocks/gdrive" / name] = text
    out[HERE / "mocks/gsheets/get_values.md"] = job_log(["JS-002", "JS-001"], [], {})
    for case, spec in CASES.items():
        out[HERE / case / "gstub/.claude-plugin/plugin.json"] = dumps(STUB)
        if "rows" in spec:
            out[HERE / case / "mocks/gsheets/get_values.md"] = job_log(spec["rows"], spec["ticked"], spec.get("tier", {}))
        if "drive" in spec:
            for name, text in drive_files({**DRIVE, **spec["drive"]}).items():
                out[HERE / case / "mocks/gdrive" / name] = text
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    for path, text in build().items():
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
