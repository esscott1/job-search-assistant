---
type: regex
pattern: 'marketplace-mismatch[^\n]{0,300}developer-tools|developer-tools[^\n]{0,300}marketplace-mismatch'
match: contains
weight: 1
---

developer-tools has a skill (lint-check) but no marketplace entry or plugin.json.
