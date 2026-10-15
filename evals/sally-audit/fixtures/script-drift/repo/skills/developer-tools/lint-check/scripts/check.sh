#!/bin/bash
# Markdown lint checks for changed files.
for f in "$@"; do
  grep -n -E '^#{7,}' "$f" | sed "s|^|$f: heading deeper than h6: |"
done
for f in "$@"; do
  grep -n -E '[[:space:]]+$' "$f" | sed "s|^|$f: trailing whitespace: |"
done
