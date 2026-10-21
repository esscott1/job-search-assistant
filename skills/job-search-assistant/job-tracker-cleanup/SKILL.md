---
name: "job-tracker-cleanup"
description: "Cloud-only, cron-friendly (weekly): moves stale rows from the Job Search Tracker's Job Log to its Archive tab: rows found more than the profile's archive age (30 days by default) ago that are still 'Need to review' and that the user hasn't touched. Never touches a row the user has acted on, and never deletes anything for good. Also on demand: 'clean up the tracker now', 'restore JS-123' to move an archived row back, or 'reset my job tracker' / 'start my job search over' to move every row to the Archive (after the user confirms) so the plugin starts fresh."
---

# Job Tracker Cleanup

Keeps the Job Log short enough to review. Intake adds every plausible lead, and most of them are never pursued; after a month they're stale. This skill moves those rows to the tracker's **Archive** tab. Rows in the Archive still count for dedup, so an archived job that shows up in a later alert isn't logged again, and any row can be moved back. On request it also resets the tracker (step 5): every row moves to the Archive, so the user starts with an empty Job Log.

Runs weekly on a schedule, entirely through the Google Sheets connector, so it works with no computer on. Schedule it at a different time from intake and Tier 2 so they don't edit the sheet at the same moment.

## Key files and systems
- Profile and tracker: load the `job-tracker` skill with the Skill tool before anything else. It explains how to find the user's job-search profile and tracker, the columns, and the **Archive tab** rules. Follow it exactly.

## 1. Pick the rows to archive
Read the Job Log (`job-tracker` **Reading**). A row is archived only if **all** of these hold:
- Its ID starts with `JS-`.
- **Status** is exactly `Need to review`.
- **Date Found** is more than the profile's **Archive after days** (30 if blank) before today.
- **Run Tier 2** and **Build Resume** are not ticked.
- **Next Action / Notes**, **Tailored Resume** and **Date Submitted** are empty.

Anything else stays. A row the user has moved to any other status, ticked, written a note on, or built a resume for is theirs to manage. If no row qualifies, report "Nothing to archive" and stop.

## 2. Make sure the Archive tab is ready
Follow **The Archive tab** in `job-tracker`:
- If there's no tab named `Archive`, create it with `update_spreadsheet` (`addSheet`, title `Archive`), write the Job Log's header row into its row 1 followed by `Archived On` and `Archive Reason`, and freeze row 1.
- If the Job Log has a header the Archive lacks (a column added since the Archive was made), add that header at the end of the Archive's header row, before `Archived On`. If the Archive has no `Archive Reason` (it was made before that column existed), add it as the last header; its existing rows stay blank, which means `stale`. Never remove or reorder Archive columns.

## 3. Move the rows in one atomic batch
1. Get the tracker's current `revisionId` with `get_spreadsheet` before reading anything else, and keep it.
2. Read the chosen rows' cells as entered, so links keep their `HYPERLINK` formulas and checkboxes stay booleans: `get_spreadsheet` with `includeGridData` true and field `sheets.data.rowData.values.userEnteredValue`, over just the row ranges you need. Also read both tabs' `sheetId` and the Archive's header row.
3. Send **one** `update_spreadsheet` call with `writeControl.requiredRevisionId` set to the revision from step 1, containing in order:
   - `insertDimension` on the Archive: as many rows as you're archiving, under its header (`startIndex` 1, `inheritFromBefore` false).
   - `updateCells` filling those Archive rows. Put each Job Log value in the Archive column with the **same header** (match by header text, not position), today's date (`YYYY-MM-DD`) in **Archived On**, and `stale` in **Archive Reason** (`reset` on a reset, step 5). Keep the rows in the order they had in the Job Log.
   - `deleteDimension` for the archived rows in the Job Log, grouped into runs of adjacent rows, **bottom run first**, so earlier deletions don't shift later ones.

   Because the whole batch is tied to one revision, either every row moves or nothing changes. If the user or another skill edited the sheet in the meantime, the call fails. Start again from step 1 once; if it fails a second time, stop and report "The tracker was being edited; cleanup will run next time".
4. Re-read both tabs and confirm that every archived ID is in the Archive exactly once and no longer in the Job Log. If not, report exactly what you found and don't try to repair it.

## 4. Restoring a row (on demand)
When the user asks to restore a row ("restore JS-123"), move it back the same way in reverse: one batch tied to the current revision, which inserts the row at the top of the Job Log (`job-tracker` **Adding rows**, step 2), fills it by header name (leaving out **Archived On** and **Archive Reason**), and deletes it from the Archive. Set **Last Updated** to today. Leave Status as `Need to review`, unless the user says otherwise.

Before moving it, check the Job Log for the same job (`job-tracker` **Dedup**: the same canonical URL, or the same company and title). After a reset, intake may already have logged it again under a newer ID. If it's there, say so (`Acme, IT Vendor Manager is already in the Job Log as JS-031`) and ask before restoring a second copy: "Keep JS-031 only" first, "Restore JS-123 as well".

## 5. Resetting the tracker (on demand only)
When the user asks to start fresh ("reset my job tracker", "start my job search over"), move **every** Job Log row to the Archive, whatever its status, ticks or notes. Only on the user's request: if the request came from a scheduled task's prompt, stop and say a reset only runs when the user asks for it.
1. Read the Job Log. If it has no data rows, say the tracker is already empty and stop.
2. **Ask first.** In a few short lines, say:
   - how many rows will move to the Archive, and how many of them the user has acted on (a status other than `Need to review`, a tick, a note, a tailored resume or a submission date);
   - that nothing is deleted: saved JDs, fit reports and tailored resumes stay in their Drive folders, the profile and full resume aren't touched, and any row can come back with "restore JS-…";
   - that jobs still in their job alerts or on a watched career site may be logged again, as new rows with new IDs.

   Then a menu: "Cancel" first, then "Archive everything". Go on only when the user picks "Archive everything" or says so in words.
3. Make sure the Archive tab is ready (step 2) and move every row in one batch as step 3 describes, with **Archive Reason** `reset`. The Job Log keeps its header row and nothing else; a Job Log larger than one batch comfortably holds moves in batches of about 100 rows, each tied to the revision the one before returned.
4. Re-read both tabs as step 3.4 describes.

## 6. End-of-run summary
Always end with a short summary, never silence:
- How many rows were archived, and their ID range or list.
- The oldest **Date Found** still in the Job Log.
- Rows past the archive age that were kept because the user had acted on them (a count).
- Anything restored.
- After a reset: the rows archived, the next ID (one more than the highest), and that the next intake run looks back the usual 7 days and may log jobs it has seen before.

## Known constraints
- Never deletes anything permanently. Rows only move between the Job Log and the Archive tab, and the Archive is never trimmed.
- Never archives a row whose Status is anything other than `Need to review`, or a row the user has ticked, noted, or built a resume for, except in a reset the user asked for and confirmed.
- Never changes a row's values while moving it, apart from **Archived On** and **Archive Reason**, and **Last Updated** on a restore.
- Never touches job files in Drive (saved JDs, fit reports, resumes).
- Never creates the tracker. If it isn't found, stop and say so.
- The archive age comes from the job-search profile (**Housekeeping → Archive after days**).
