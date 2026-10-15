---
type: regex
target: trace
pattern: 'highlights\W{1,8}\[[^\]]*(Kubernetes|CKA|Rust)'
match: not_contains
weight: 3
---
