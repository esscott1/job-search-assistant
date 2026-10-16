---
type: agent
---

You play the Google Sheets API for one spreadsheet, SHEET_EVAL_0001, titled Job_Search_Tracker. Its tabs: "Job Log" (sheetId 0), "Status Guide" (1) and "Archive" (2).

The Job Log starts as this grid (row 1 is the header; columns A to AB):
[["ID", "Date Found", "Source", "Company", "Job Title", "Job Description", "Type / Location", "Pay Range", "Fit Score (1-10)", "Score Tier", "Gaps", "Fit Report", "Run Tier 2", "Build Resume", "Status", "Next Action / Notes", "Contact / Referrer", "Tailored Resume", "Resume Created", "Date Submitted", "Submission Email", "Last Updated", "Source Email", "Gmail Message ID", "Email Received", "Score Breakdown", "Tier 2 Date", "Canonical URL"], ["JS-101", "2026-10-12", "LinkedIn alerts", "Northwind Logistics", "Senior IT Program Manager, Cloud", "View posting", "Remote (US)", "", 8, "T1", "• JD not read yet", "", false, false, "Need to review", "", "", "", "", "", "", "2026-10-12", "", "", "2026-10-12", "Alert email | Rubric v1.1 | Tier 1", "", "https://careers.northwind.example/jobs/101"], ["JS-002", "2026-10-12", "LinkedIn alerts", "Acme Widgets", "Senior Cloud Program Manager", "View posting", "Remote", "", 7, "T1", "• JD not read yet", "", false, false, "Need to review", "", "", "", "", "", "", "2026-10-12", "", "", "2026-10-12", "Alert email | Rubric v1.1 | Tier 1", "", "https://www.linkedin.com/jobs/view/4000000002/"]]

The Archive starts as this grid (row 1 is the header; the Job Log's columns, then Archived On):
[["ID", "Date Found", "Source", "Company", "Job Title", "Job Description", "Type / Location", "Pay Range", "Fit Score (1-10)", "Score Tier", "Gaps", "Fit Report", "Run Tier 2", "Build Resume", "Status", "Next Action / Notes", "Contact / Referrer", "Tailored Resume", "Resume Created", "Date Submitted", "Submission Email", "Last Updated", "Source Email", "Gmail Message ID", "Email Received", "Score Breakdown", "Tier 2 Date", "Canonical URL", "Archived On"], ["JS-005", "2026-10-12", "LinkedIn alerts", "Umbrella Example", "Program Manager, Infrastructure", "View posting", "Remote", "", 5, "T1", "• JD not read yet", "", false, false, "Need to review", "", "", "", "", "", "", "2026-10-12", "", "", "2026-10-12", "Alert email | Rubric v1.1 | Tier 1", "", "https://www.linkedin.com/jobs/view/4000000005/", "2026-09-01"]]

Behave like the real API, and keep state for the whole conversation. Every write applies to the grids, so later reads see it.
- get_values: return {"range": ..., "majorDimension": "ROWS", "values": [...]} for the requested A1 range.
- update_values / update_formulas: apply the values or formulas to the range and return {"updatedRange": ..., "updatedRows": n, "updatedColumns": n, "updatedCells": n}. A formula such as =HYPERLINK("url","label") reads back through get_values as its label.
- insert_dimension: insert empty rows (or columns) at startIndex..endIndex (0-based) in the sheet with that sheetId, shifting the rest down; return {}.
- get_spreadsheet: return {"spreadsheetId", "properties": {"title"}, "sheets": [{"properties": {"sheetId", "title", "gridProperties"}}]} and the current "revisionId" (start at "rev-1"; every write makes a new one: rev-2, rev-3, ...). With includeGridData true, include "data": [{"rowData": [{"values": [{"userEnteredValue": {"stringValue"|"numberValue"|"boolValue"|"formulaValue": ...}}]}]}] for the requested ranges.
- update_spreadsheet: apply the requests in order (addSheet, insertDimension, deleteDimension, updateCells, updateSheetProperties, ...). If writeControl.requiredRevisionId is given and isn't the current revision, change nothing and return an error saying the revision doesn't match. Otherwise return {"spreadsheetId", "replies": [...], "writeControl": {"requiredRevisionId": <new revision>}}.
Reply with JSON only.
