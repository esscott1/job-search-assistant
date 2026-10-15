---
type: regex
target: trace
pattern: 'competencies\W{1,8}\[[^\]]*(Kubernetes|CKA|Rust)'
match: not_contains
weight: 3
---

The full resume shows no Kubernetes certification and no Rust.
