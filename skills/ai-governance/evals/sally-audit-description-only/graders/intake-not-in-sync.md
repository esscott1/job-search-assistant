---
type: regex
pattern: '(\|\s*`?job-lead-intake-scan`?\s*\|[^\n]*\|\s*`?in-sync`?\s*\||in-sync\W{1,6}`?job-lead-intake-scan`?(?![\w-]))'
match: not_contains
weight: 2
---

Only its description is visible; a matching description is not proof of sync.
