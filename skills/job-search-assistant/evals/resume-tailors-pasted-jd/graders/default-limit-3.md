---
type: regex
target: trace
pattern: 'max_pages\W{1,6}3\b'
match: contains
weight: 1
---

With no page limit in the request, the resume is built to the default limit of 3 pages.
