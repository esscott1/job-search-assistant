---
type: tool_used
tool: Bash
input_match: 'read_posting\.py'
min: 1
weight: 1
---

Posting pages are read with job-tracker's read_posting.py first. In the eval sandbox the fictional host can't be reached, so the script reports unreachable and the skill falls back to the stub fetch.
