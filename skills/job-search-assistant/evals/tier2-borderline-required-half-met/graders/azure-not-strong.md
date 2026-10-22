---
type: regex
target: mock_calls
pattern: 'Azure[^}]{0,200}?evidence[^a-z]{1,8}strong'
match: not_contains
weight: 1
---

The resume shows AWS, not Azure: partial or none, never strong.
