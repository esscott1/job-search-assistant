---
type: regex
pattern: '(\|\s*`?job-lead-tier2-scoring`?\s*\|[^\n]*\|\s*`?installed-ahead`?\s*\||installed-ahead\W{1,6}`?job-lead-tier2-scoring`?(?![\w-]))'
match: contains
weight: 2
---

The installed copy is newer than main, not repo-ahead or in-sync.
