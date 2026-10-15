---
type: regex
target: mock_calls
pattern: 'Rust[^}]{0,200}?evidence[^a-z]{1,8}none'
match: contains
weight: 1
---
