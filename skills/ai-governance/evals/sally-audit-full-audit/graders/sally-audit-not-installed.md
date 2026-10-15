---
type: regex
pattern: '(\|\s*`?sally-audit`?\s*\|[^\n]*\|\s*`?not-installed`?\s*\||not-installed\W{1,6}`?sally-audit`?(?![\w-]))'
match: contains
weight: 1
---
