---
tags: [job-tracker-cleanup]
runs: 3
max_turns: 40
timeout_seconds: 900
plugins: ["gstub", "../.."]
disallowed_tools: [AskUserQuestion]
---

Reset my job tracker so I can start fresh. I know every row moves to the Archive, including the ones I've worked on, and nothing is deleted: archive everything, no need to ask me again.
