---
type: regex
target: mock_calls
pattern: 'Score: [6-8] \(T2'
match: contains
weight: 3
---

Gold evidence table (fixtures/gold/JS-104.json) scores 7. Accept 6-8. Exactly half the required items are met (two strong, two partial), so the fewer-than-half cap must not apply: judging either partial as none drops the score to 5.
