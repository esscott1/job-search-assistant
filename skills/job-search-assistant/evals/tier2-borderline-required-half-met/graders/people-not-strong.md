---
type: regex
target: mock_calls
pattern: 'managing people[^}]{0,200}?evidence[^a-z]{1,8}strong'
match: not_contains
weight: 1
---

The JD asks for 7+ years managing people; the resume shows about 5 (PMO lead since 2021). Fewer years is partial, never strong.
