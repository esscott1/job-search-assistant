---
type: regex
pattern: '(\|\s*`?lint-check`?\s*\|[^\n]*\|\s*`?not-installed`?\s*\||not-installed\W{1,6}`?lint-check`?(?![\w-]))'
match: contains
weight: 1
---
