---
type: regex
target: mock_calls
pattern: 'Kubernetes[^}]{0,200}?evidence[^a-z]{1,8}none'
match: contains
weight: 2
---
