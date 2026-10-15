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
