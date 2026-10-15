---
type: regex
pattern: '(\|\s*`?job-lead-tier2-scoring`?\s*\|[^\n]*\|\s*`?(installed-ahead|repo-ahead|diverged|direction-unclear)`?\s*\||(installed-ahead|repo-ahead|diverged|direction-unclear)\W{1,6}`?job-lead-tier2-scoring`?(?![\w-]))'
match: contains
weight: 1
---

Its description differs from main's, so it's reported as differing.
