"""Google Sheets: reading the plugin's tracker, and B's own shadow tracker.

- `SheetsKnownJobs` reads A's tracker (the plugin's Job Log and Archive), read-only, for
  intake's dedup. Columns are found by header, as the job-tracker contract requires.
- `SheetsTracker` implements `TrackerPort` on B's shadow spreadsheet, which B creates
  (`create_shadow`) and A never sees. B never writes to A's tracker.

Both reach Sheets through `SheetsClient`, a narrow interface: `SheetsApi` is the real one
(the `google` extra and a `drive.file` token), `fakes.FakeSheets` the one tests use. Which
spreadsheets to use is kept in `data/google/sheets.json` (`tracker_id`, `shadow_id`).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from ..domain import (
    DuplicateJobId,
    Job,
    KnownJob,
    Status,
    StatusChange,
    StatusSource,
    check_transition,
    now,
)
from ..ports import KnownJobsPort

JOB_LOG, ARCHIVE, HISTORY, JDS = "Job Log", "Archive", "History", "JDs"
CELL_LIMIT = 50_000  # characters Google Sheets allows in one cell

# The shadow's Job Log: the plugin's headers for what B fills in, so the two can be compared
# column by column, then B's own two. Pipeline Data (the Job as JSON, without its JD) is what
# B reads back; the other columns are a readable copy of it.
SHADOW_HEADERS = [
    "ID",
    "Date Found",
    "Source",
    "Company",
    "Job Title",
    "Job Description",
    "Type / Location",
    "Pay Range",
    "Fit Score (1-10)",
    "Score Tier",
    "Gaps",
    "Score Breakdown",
    "Last Updated",
    "Source Email",
    "Gmail Message ID",
    "Email Received",
    "Canonical URL",
    "Pipeline Status",
    "Pipeline Data",
]
HISTORY_HEADERS = ["Job ID", "From", "To", "Source", "Note", "At"]
JD_HEADERS = ["ID", "JD text"]  # longer JDs continue in the columns after "JD text"


class TrackerSheetError(RuntimeError):
    pass


class SheetsClient(Protocol):
    def title(self, spreadsheet_id: str) -> str: ...
    def tabs(self, spreadsheet_id: str) -> list[str]: ...
    def read(self, spreadsheet_id: str, tab: str) -> list[list[str]]:
        """Every row of a tab as displayed text, trailing empty cells and rows left out."""
        ...

    def write_row(self, spreadsheet_id: str, tab: str, row: int, values: list) -> None:
        """Write `values` from column A of 1-based `row`, as plain values (never formulas)."""
        ...

    def insert_rows(self, spreadsheet_id: str, tab: str, at: int, count: int = 1) -> None:
        """Insert empty rows so the first new one is 1-based row `at`."""
        ...

    def append_rows(self, spreadsheet_id: str, tab: str, rows: list[list]) -> None: ...
    def create(self, title: str, tabs: dict[str, list[str]]) -> str:
        """Create a spreadsheet with these tabs and header rows; return its ID."""
        ...


@dataclass
class SheetsSettings:
    tracker_id: str = ""  # A's tracker, picked in the Google Picker
    shadow_id: str = ""  # B's shadow spreadsheet, created by B

    @classmethod
    def load(cls, google_dir: Path) -> SheetsSettings:
        path = google_dir / "sheets.json"
        return cls(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else cls()

    def save(self, google_dir: Path) -> None:
        google_dir.mkdir(parents=True, exist_ok=True)
        (google_dir / "sheets.json").write_text(json.dumps(asdict(self), indent=1) + "\n")


def records(rows: list[list[str]]) -> list[tuple[int, dict[str, str]]]:
    """(1-based row number, {header: value}) for each non-empty row under the header row."""
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    out = []
    for number, row in enumerate(rows[1:], start=2):
        if any(str(v).strip() for v in row):
            padded = list(row) + [""] * (len(header) - len(row))
            out.append((number, dict(zip(header, (str(v) for v in padded), strict=False))))
    return out


def _require(header: list[str], needed: list[str], tab: str) -> None:
    for name in needed:
        if name not in header:
            raise TrackerSheetError(f'{tab} is missing the "{name}" column')


class SheetsKnownJobs:
    """Every job in A's tracker that intake must not log again, plus `also` (B's own rows).

    Archive rows whose Archive Reason is `reset` are left out: the user asked to start fresh,
    so those jobs may be logged again.
    """

    def __init__(self, client: SheetsClient, tracker_id: str, also: KnownJobsPort | None = None):
        self.client, self.tracker_id, self.also = client, tracker_id, also

    def known_jobs(self) -> list[KnownJob]:
        tabs = self.client.tabs(self.tracker_id)
        if JOB_LOG not in tabs:
            raise TrackerSheetError('Tracker has no "Job Log" tab')
        out = []
        for tab in (JOB_LOG, ARCHIVE):
            if tab not in tabs:
                continue
            rows = self.client.read(self.tracker_id, tab)
            if tab == JOB_LOG:
                _require(
                    [h.strip() for h in rows[0]] if rows else [],
                    ["ID", "Company", "Job Title"],
                    tab,
                )
            for _, r in records(rows):
                if not r.get("ID", "").strip():
                    continue
                if tab == ARCHIVE and r.get("Archive Reason", "").strip().lower() == "reset":
                    continue
                out.append(
                    KnownJob(
                        id=r["ID"].strip(),
                        company=r.get("Company", ""),
                        title=r.get("Job Title", ""),
                        canonical_url=r.get("Canonical URL", "").strip(),
                    )
                )
        return out + (self.also.known_jobs() if self.also else [])


def create_shadow(client: SheetsClient, title: str = "Job Search Tracker (pipeline shadow)") -> str:
    return client.create(
        title, {JOB_LOG: SHADOW_HEADERS, HISTORY: HISTORY_HEADERS, JDS: JD_HEADERS}
    )


def _cells(job: Job) -> dict[str, object]:
    """The shadow's columns for one job. Pipeline Data leaves the JD out (it goes to JDs)."""
    fit = job.fit
    link = job.canonical_url or job.url or ""
    breakdown = ""
    if fit and fit.breakdown:
        where = "Alert email" if job.scoring_tier == "T1" else (f"JD: {link}" if link else "JD")
        breakdown = f"{where} | {fit.breakdown}"
    data = job.model_dump_json(exclude={"jd_text"})
    if len(data) > CELL_LIMIT:
        raise TrackerSheetError(f"{job.id}: its data is too long for one cell ({len(data)})")
    message = job.gmail_message_id
    return {
        "ID": job.id,
        "Date Found": job.found_on.isoformat() if job.found_on else "",
        "Source": job.source or "",
        "Company": job.company,
        "Job Title": job.title,
        "Job Description": link,
        "Type / Location": job.location or "",
        "Pay Range": job.pay_range or "",
        "Fit Score (1-10)": fit.score if fit else "",
        "Score Tier": job.scoring_tier or "",
        "Gaps": "\n".join(f"• {g}" for g in fit.top_gaps) if fit else "",
        "Score Breakdown": breakdown,
        "Last Updated": job.updated_at.date().isoformat(),
        "Source Email": f"https://mail.google.com/mail/u/0/#all/{message}" if message else "",
        "Gmail Message ID": message or "",
        "Email Received": job.email_received.isoformat() if job.email_received else "",
        "Canonical URL": job.canonical_url,
        "Pipeline Status": job.status.value,
        "Pipeline Data": data,
    }


class SheetsTracker:
    """TrackerPort on B's shadow spreadsheet: one Job Log row per job, newest at the top.

    Rows are found by ID at the moment of writing and columns by header, so sorting the sheet
    or adding a column of your own is safe; columns B doesn't know are left as they are.
    Status changes go through `transition`, which checks domain.TRANSITIONS and adds a row
    to the History tab.
    """

    def __init__(self, client: SheetsClient, spreadsheet_id: str, jd_chunk: int = 45_000):
        self.client, self.id, self.jd_chunk = client, spreadsheet_id, jd_chunk

    # -- reads -------------------------------------------------------------------------
    def _log(self) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
        rows = self.client.read(self.id, JOB_LOG)
        header = [h.strip() for h in rows[0]] if rows else []
        _require(header, ["ID", "Pipeline Status", "Pipeline Data"], f"The shadow's {JOB_LOG}")
        return header, records(rows)

    def _find(self, job_id: str) -> tuple[list[str], int | None, dict[str, str]]:
        header, rows = self._log()
        for number, r in rows:
            if r["ID"].strip() == job_id:
                return header, number, r
        return header, None, {}

    def _jd_row(self, job_id: str) -> tuple[int | None, list[str]]:
        rows = self.client.read(self.id, JDS)
        for number, row in enumerate(rows[1:], start=2):
            if row and row[0] == job_id:
                return number, row
        return None, []

    def get(self, job_id: str) -> Job:
        _, number, r = self._find(job_id)
        if number is None:
            raise KeyError(job_id)
        job = Job.model_validate_json(r["Pipeline Data"])
        _, jd = self._jd_row(job_id)
        job.jd_text = "".join(jd[1:]) or None
        return job

    def list(self, statuses: set[Status] | None = None) -> list[Job]:
        _, rows = self._log()
        jobs = [Job.model_validate_json(r["Pipeline Data"]) for _, r in rows if r["Pipeline Data"]]
        return sorted((j for j in jobs if not statuses or j.status in statuses), key=lambda j: j.id)

    def history(self, job_id: str) -> list[StatusChange]:
        return [
            StatusChange(
                job_id=job_id,
                from_status=Status(r["From"]) if r["From"] else None,
                to_status=Status(r["To"]),
                source=r["Source"],
                note=r["Note"] or None,
                at=r["At"],
            )
            for _, r in records(self.client.read(self.id, HISTORY))
            if r["Job ID"] == job_id
        ]

    def next_id(self, prefix: str = "LG") -> str:
        """Highest number used with this prefix, plus one."""
        numbers = []
        for _, r in self._log()[1]:
            head, _, tail = r["ID"].strip().partition("-")
            if head == prefix and tail.isdigit():
                numbers.append(int(tail))
        return f"{prefix}-{max(numbers, default=0) + 1:04d}"

    # -- writes ------------------------------------------------------------------------
    def add(self, job: Job) -> Job:
        header, number, _ = self._find(job.id)
        if number is not None:
            raise DuplicateJobId(job.id)
        self.client.insert_rows(self.id, JOB_LOG, at=2)
        self._write(header, 2, {}, job)
        if job.jd_text:
            self._write_jd(job.id, job.jd_text)
        self._record(job.id, None, job.status, "pipeline", "created")
        return job

    def save(self, job: Job) -> Job:
        stored = self.get(job.id)
        if job.status != stored.status:
            raise ValueError("status changes must go through transition()")
        job.updated_at = now()
        self._update(job)
        if job.jd_text != stored.jd_text:
            self._write_jd(job.id, job.jd_text or "")
        return job

    def transition(
        self, job_id: str, to: Status, source: StatusSource, note: str | None = None
    ) -> Job:
        job = self.get(job_id)
        check_transition(job_id, job.status, to)
        previous = job.status
        job.status = to
        job.updated_at = now()
        self._update(job)
        self._record(job_id, previous, to, source, note)
        return job

    # -- internals ---------------------------------------------------------------------
    def _update(self, job: Job) -> None:
        header, number, existing = self._find(job.id)  # re-read: the user may have sorted
        if number is None:
            raise KeyError(job.id)
        self._write(header, number, existing, job)

    def _write(self, header: list[str], number: int, existing: dict[str, str], job: Job) -> None:
        cells = _cells(job)
        values = [cells.get(h, existing.get(h, "")) for h in header]
        self.client.write_row(self.id, JOB_LOG, number, values)

    def _write_jd(self, job_id: str, text: str) -> None:
        chunks = [text[i : i + self.jd_chunk] for i in range(0, len(text), self.jd_chunk)]
        number, old = self._jd_row(job_id)
        values = [job_id, *chunks]
        values += [""] * (len(old) - len(values))  # clear chunks a longer JD left behind
        if number is None:
            self.client.append_rows(self.id, JDS, [values])
        else:
            self.client.write_row(self.id, JDS, number, values)

    def _record(self, job_id, from_status, to_status, source, note) -> None:
        row = [
            job_id,
            from_status.value if from_status else "",
            to_status.value,
            source,
            note or "",
            now().isoformat(),
        ]
        self.client.append_rows(self.id, HISTORY, [row])


def _a1(tab: str) -> str:
    return "'" + tab.replace("'", "''") + "'"


def _column(n: int) -> str:
    """1 → A, 27 → AA."""
    name = ""
    while n:
        n, rest = divmod(n - 1, 26)
        name = chr(65 + rest) + name
    return name


class SheetsApi:
    """SheetsClient over the Google Sheets v4 API, signed in with a `drive.file` token."""

    def __init__(self, google_dir: Path | None = None, service=None):
        self.google_dir = google_dir or Path("data/google")
        self._service = service
        self._sheet_ids: dict[tuple[str, str], int] = {}

    @property
    def service(self):
        if self._service is None:
            from googleapiclient.discovery import build

            from .google_auth import load_credentials

            creds = load_credentials(self.google_dir)
            self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return self._service

    def _meta(self, spreadsheet_id: str) -> dict:
        fields = "properties.title,sheets.properties(sheetId,title)"
        meta = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields=fields)
        meta = meta.execute()
        for s in meta.get("sheets", []):
            props = s["properties"]
            self._sheet_ids[(spreadsheet_id, props["title"])] = props["sheetId"]
        return meta

    def title(self, spreadsheet_id: str) -> str:
        return self._meta(spreadsheet_id)["properties"]["title"]

    def tabs(self, spreadsheet_id: str) -> list[str]:
        return [s["properties"]["title"] for s in self._meta(spreadsheet_id).get("sheets", [])]

    def read(self, spreadsheet_id: str, tab: str) -> list[list[str]]:
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=_a1(tab))
            .execute()
        )
        return result.get("values", [])

    def write_row(self, spreadsheet_id: str, tab: str, row: int, values: list) -> None:
        cells = f"{_a1(tab)}!A{row}:{_column(max(len(values), 1))}{row}"
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=cells,
            valueInputOption="RAW",
            body={"values": [values]},
        ).execute()

    def insert_rows(self, spreadsheet_id: str, tab: str, at: int, count: int = 1) -> None:
        if (spreadsheet_id, tab) not in self._sheet_ids:
            self._meta(spreadsheet_id)
        rows = {
            "sheetId": self._sheet_ids[(spreadsheet_id, tab)],
            "dimension": "ROWS",
            "startIndex": at - 1,
            "endIndex": at - 1 + count,
        }
        request = {"insertDimension": {"range": rows, "inheritFromBefore": False}}
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": [request]}
        ).execute()

    def append_rows(self, spreadsheet_id: str, tab: str, rows: list[list]) -> None:
        self.service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{_a1(tab)}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    def create(self, title: str, tabs: dict[str, list[str]]) -> str:
        frozen = {"gridProperties": {"frozenRowCount": 1}}
        body = {
            "properties": {"title": title},
            "sheets": [{"properties": {"title": name, **frozen}} for name in tabs],
        }
        created = self.service.spreadsheets().create(body=body).execute()
        spreadsheet_id = created["spreadsheetId"]
        for name, header in tabs.items():
            self.write_row(spreadsheet_id, name, 1, header)
        return spreadsheet_id
