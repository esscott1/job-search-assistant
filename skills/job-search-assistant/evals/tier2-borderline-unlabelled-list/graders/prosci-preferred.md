---
type: regex
target: mock_calls
pattern: 'Prosci[^}]{0,60}?type[^a-z]{1,8}preferred'
match: contains
weight: 1
---

"A plus" is preferred.
