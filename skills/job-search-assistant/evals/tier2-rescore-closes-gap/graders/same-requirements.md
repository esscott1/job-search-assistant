---
type: regex
target: mock_calls
pattern: 'Experience in the healthcare industry\W{1,12}type\W{1,8}required.{1,400}?Managed budgets over \$2m\W{1,12}type\W{1,8}required'
match: contains
flags: s
weight: 1
---

Requirement entries keep r1's exact text, type and order (two neighbouring entries checked).
