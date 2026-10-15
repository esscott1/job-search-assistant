---
type: regex
target: mock_calls
pattern: 'Score: [1-3] \(T2'
match: contains
weight: 3
---

Gold evidence table (fixtures/gold/JS-103.json) scores 1; relocation caps it at 3 anyway.
