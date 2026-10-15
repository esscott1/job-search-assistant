---
type: regex
target: mock_calls
pattern: 'Score: (9|10) \(T2'
match: contains
weight: 3
---

Gold evidence table (fixtures/gold/JS-101.json) scores 10. Accept 9-10.
