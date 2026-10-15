---
type: regex
target: mock_calls
pattern: 'PMP[^}]{0,200}?evidence[^a-z]{1,8}none'
match: contains
weight: 1
---

PMP isn't on the resume.
