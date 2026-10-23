# ADR 0002: The tracker database is the system of record; graph runs are short

- **Status:** Accepted
- **Date:** 2026-10-01

## Context

A job application's lifecycle runs for weeks or months: found, scored, tailored, submitted, interviewing, and finally an outcome. LangGraph checkpoints could hold that state in one long-lived thread per job, but checkpoints are an execution detail. They're awkward to query ("show everything I'm interviewing for"), are tied to one framework, and their schema changes as graphs evolve.

## Decision

- Job status and history live in the **tracker** (SQLite to start, behind `TrackerPort`). All approaches read and write it through `core`.
- Status changes go only through `tracker.transition()`, which enforces `domain.TRANSITIONS` and records `from → to`, the **source** (`pipeline`, `user`, `email`, `import`) and a note.
- Graph runs are **short**: evaluate one job, sweep statuses once, refresh once. Checkpoints exist so a run can pause for a human or resume after a crash, not to hold the lifecycle.
- Submissions are recorded by you (`jobs submit`), and later also detected from confirmation emails. The source field records which.

## Consequences

- A second orchestration approach works against the same tracker with no migration.
- The existing Excel tracker remains Version A's record during shadow mode. Importing it read-only is roadmap M2. Nothing writes to both.
- If the tracker and a checkpoint ever disagree, the tracker wins, and the graph run is restarted with `--restart`.

## Update, 2026-10-03

Version A's tracker (the Claude skills) moved from the Excel workbook to a native Google Sheet, `Job_Search_Tracker`, edited cell by cell through the Google Sheets connector. Replacing the whole .xlsx on every cloud save changed its file ID each time and hit a size limit for unattended runs. The old workbook is kept as a read-only archive. The roadmap M2 read-only import should read from the Sheet.

## Update, 2026-10-22: B's tracker can be a Google Sheet

Roadmap decision D2 is settled: the tracker behind `TrackerPort` can be a Google Sheet.

- **`SheetsTracker`** implements `TrackerPort` on a spreadsheet B creates for itself, its shadow. Its Job Log uses the plugin's column names for what B fills in, so the two can be compared column by column, plus **Pipeline Status** (B's `Status`) and **Pipeline Data** (the `Job` as JSON, which B reads back). Status changes still go only through `transition()`, which checks `domain.TRANSITIONS` and adds a row to a **History** tab. JD text lives in a **JDs** tab, split across cells under the 50,000-character cell limit.
- **The plugin's tracker is read, never written.** B reads its Job Log and Archive by column header for intake's dedup. The plugin's **Status** column remains the user's own.
- **The profile names the plugin's tracker** (Tracker → Sheet ID), for B as for the plugin; B keeps no copy of it, and records only its own shadow's ID.
- **Access is `drive.file`:** the user approves the tracker the profile names once, in the Google Picker, and B creates its shadow, so B can reach those two spreadsheets and nothing else in the user's Drive.
- **SQLite stays** for tests, the offline demo, and as the default until cut-over; `JOBS_TRACKER=sheets` selects the Sheet. Nothing writes to both.
