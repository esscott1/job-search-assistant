---
type: regex
target: trace
pattern: 'description\?"\s*:\s*\?"(?:Example Corp|Sample Systems) is'
match: not_contains
weight: 3
---

The full resume describes Example Corp and Sample Systems in a line under each, but no company description is written into content.json. The full resume is Markdown, so this JSON form only appears if the model wrote it.
