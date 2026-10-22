---
type: regex
target: mock_calls
pattern: 'ERP implementation[^}]{0,60}?type[^a-z]{1,8}required[^}]{0,200}?evidence[^a-z]{1,8}none'
match: contains
weight: 2
---
