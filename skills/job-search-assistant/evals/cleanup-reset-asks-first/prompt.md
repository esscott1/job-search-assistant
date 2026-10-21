---
tags: [job-tracker-cleanup]
runs: 3
max_turns: 40
timeout_seconds: 900
plugins: ["gstub", "../.."]
disallowed_tools: [AskUserQuestion]
---

reset my job tracker
