---
type: regex
target: mock_calls
pattern: 'Changes since r1[^#]{0,600}Kubernetes'
match: contains
weight: 2
---

The new report says what moved since r1.
