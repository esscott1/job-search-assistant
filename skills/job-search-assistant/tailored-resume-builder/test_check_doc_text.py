"""Tests for check_doc_text.py: a Google Doc read back as text, checked against its content.json.
Run with: python3 -m pytest -q skills/job-search-assistant/tailored-resume-builder

history_doc_readback.md in ../evals/fixtures is history_content.json as Drive's read_file_content
returns a converted Doc: bold markers, Markdown tables, escaped bullets.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXTURES = HERE.parent / "evals" / "fixtures"
sys.path.insert(0, str(HERE))
from check_doc_text import check, norm  # noqa: E402

CONTENT = json.loads((FIXTURES / "history_content.json").read_text(encoding="utf-8"))
DOC = (FIXTURES / "history_doc_readback.md").read_text(encoding="utf-8")


def test_complete_doc_passes():
    res = check(CONTENT, DOC)
    assert res["ok"], res["missing"]
    assert res["checked"] > 20


def test_dropped_bullet_is_missing():
    doc = DOC.replace("  - Ran a network refresh across 22 sites with three vendors.\n", "")
    assert check(CONTENT, doc)["missing"] == ["Ran a network refresh across 22 sites with three vendors."]


def test_changed_date_or_word_is_missing():
    assert "2018 - 2021" in check(CONTENT, DOC.replace("| 2018 - 2021 |", "| 2017 - 2021 |"))["missing"]
    res = check(CONTENT, DOC.replace("40 supplier contracts", "4 supplier contracts"))
    assert res["missing"] == ["Negotiated and tracked 40 supplier contracts, cutting renewal costs by 8%."]


def test_markup_dashes_quotes_and_case_are_ignored():
    assert norm("**Sr. Manager** – Ops") == norm("sr. manager - ops")
    assert norm("the organization’s first") == norm("the organization's first")
    c = copy.deepcopy(CONTENT)
    c["experience"][0]["dates"] = "2018 – Present"
    assert check(c, DOC)["ok"]


def test_cli(tmp_path):
    content, doc = tmp_path / "c.json", tmp_path / "d.md"
    content.write_text(json.dumps(CONTENT), encoding="utf-8")
    doc.write_text(DOC, encoding="utf-8")

    def cli(*args):
        return subprocess.run([sys.executable, str(HERE / "check_doc_text.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")
    r = cli("--content", str(content), "--doc", str(doc))
    assert r.returncode == 0 and json.loads(r.stdout)["ok"]
    doc.write_text(DOC.replace("ITIL 4 Foundation", "ITIL Foundation"), encoding="utf-8")
    assert cli("--content", str(content), "--doc", str(doc)).returncode == 1
    assert cli("--content", str(content), "--doc", str(tmp_path / "none.md")).returncode == 2
