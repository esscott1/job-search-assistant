#!/usr/bin/env python3
"""Check that a Google Doc made from a resume's HTML holds every line of its content.json.

Usage: check_doc_text.py --content content.json --doc doc.md

doc.md is the Doc read back as text, for example the Drive connector's read_file_content result
saved to a file. The HTML passes through the model on its way to Drive, so a dropped or altered
line would otherwise go unnoticed. Markdown and table markup is ignored, and so are case,
spacing and the kind of dash or quote.

Prints JSON: {"ok": bool, "checked": N, "missing": [...]}. Exit 0 when ok, 1 when lines are
missing, 2 when an input can't be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def norm(text: str) -> str:
    text = re.sub(r"[*_`|\\#]", " ", text)
    text = re.sub(r"[‐-―−]", "-", text)
    text = re.sub(r"[‘’‛`]", "'", text).replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def expected_lines(c: dict) -> list[str]:
    lines = [c.get("name", ""), c.get("headline", ""), c.get("summary", "")]
    lines += c.get("contact", []) + c.get("competencies", []) + c.get("highlights", []) + c.get("additional", [])
    for job in c.get("experience", []):
        lines += [job.get("company", ""), job.get("location", ""), job.get("dates", "")]
        for role in job.get("roles", []):
            lines += [role.get("title", ""), role.get("location", ""), role.get("dates", ""), role.get("summary", "")]
            lines += role.get("bullets") or []
    for it in c.get("education", []):
        lines += [it.get("degree", ""), it.get("school", "")]
    for it in c.get("certifications", []):
        lines += [it.get("name", ""), it.get("detail", "")]
    return [line for line in lines if line and line.strip()]


def check(content: dict, doc_text: str) -> dict:
    doc = norm(doc_text)
    lines = expected_lines(content)
    missing = [line for line in lines if norm(line) not in doc]
    return {"ok": not missing, "checked": len(lines), "missing": missing}


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--content", required=True)
    a.add_argument("--doc", required=True)
    a = a.parse_args()
    try:
        content = json.loads(Path(a.content).read_text(encoding="utf-8"))
        doc_text = Path(a.doc).read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(2)
    result = check(content, doc_text)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
