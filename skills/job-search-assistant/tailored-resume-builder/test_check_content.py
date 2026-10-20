"""Tests for check_content.py: content.json checked against the full resume's work history.
Run with: python3 -m pytest -q skills/job-search-assistant/tailored-resume-builder

Uses the synthetic Full-Resume-history.md and history_content.json in ../evals/fixtures, with
today pinned so the 15-year rule doesn't move as time passes.
"""

import copy
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("docx")  # check_content reuses render_resume's rules

HERE = Path(__file__).parent
FIXTURES = HERE.parent / "evals" / "fixtures"
sys.path.insert(0, str(HERE))
from check_content import check, is_old, parse_inventory  # noqa: E402

INVENTORY = (FIXTURES / "Full-Resume-history.md").read_text(encoding="utf-8")
CONTENT = json.loads((FIXTURES / "history_content.json").read_text(encoding="utf-8"))
TODAY = dt.date(2026, 10, 16)


def run(content=None, inventory=INVENTORY):
    return check(inventory, content or CONTENT, TODAY, 15)


def edited(fn):
    c = copy.deepcopy(CONTENT)
    fn(c)
    return c


def test_inventory_headings_are_parsed():
    employers = parse_inventory(INVENTORY)
    assert [e.name for e in employers] == ["Example Corp, Columbus, OH", "Sample Systems, Dayton, OH",
                                           "Contoso Retail Example, Dayton, OH", "Vandelay Example, Cincinnati, OH"]
    assert [r.dates for r in employers[0].roles] == ["2021 - Present", "2018 - 2021"]
    assert employers[1].roles[0].title == "IT Project Manager, Dayton, OH"


def test_clean_content_passes_and_lists_the_old_role_left_out():
    res = run()
    assert res["ok"], res["errors"]
    assert res["errors"] == [] and res["warnings"] == []
    assert res["omitted_old_roles"] == [
        {"company": "Contoso Retail Example, Dayton, OH", "title": "Store Operations Supervisor, Dayton, OH",
         "dates": "2004 - 2008"}]


def test_dropping_a_recent_role_is_an_error():
    res = run(edited(lambda c: c["experience"].pop(1)))  # Sample Systems, ended 2018
    assert not res["ok"]
    assert any("IT Project Manager" in e and "must stay" in e for e in res["errors"])


def test_changed_dates_or_title_is_an_error():
    res = run(edited(lambda c: c["experience"][0]["roles"][1].update(dates="2017 - 2021")))
    assert any("Senior IT Program Manager" in e and "don't match" in e for e in res["errors"])
    res = run(edited(lambda c: c["experience"][0]["roles"][0].update(title="VP, IT Program Delivery")))
    assert any("no role with that title" in e for e in res["errors"])
    res = run(edited(lambda c: c["experience"][1].update(dates="2011 - 2018")))
    assert any(e.startswith("Sample Systems: dates") for e in res["errors"])


def test_company_description_is_an_error():
    res = run(edited(lambda c: c["experience"][0].update(description="A fictional logistics company.")))
    assert any("company descriptions" in e for e in res["errors"])


def test_role_with_no_line_is_an_error():
    res = run(edited(lambda c: c["experience"][1]["roles"][0].pop("summary")))
    assert any("needs at least one line" in e for e in res["errors"])


def test_dashes_and_spacing_dont_matter():
    res = run(edited(lambda c: c["experience"][0].update(dates="2018–Present")))
    assert res["ok"], res["errors"]


def test_unknown_employer_is_a_warning_not_an_error():
    def add(c):
        c["experience"].append({"company": "Initech Example", "dates": "1999 - 2001",
                                "roles": [{"title": "Analyst", "dates": "1999 - 2001", "bullets": ["Did a thing."]}]})
    res = run(edited(add))
    assert res["ok"] and any("Initech Example" in w for w in res["warnings"])


def test_inventory_without_headings_skips_history_but_checks_content():
    flat = "# JANE EXAMPLE\n\n## Experience\nExample Corp, 2018 - Present: Director.\n"
    res = run(inventory=flat)
    assert res["ok"] and "history checks skipped" in res["warnings"][0]
    res = run(edited(lambda c: c["experience"][0].update(description="x")), inventory=flat)
    assert not res["ok"]


@pytest.mark.parametrize("dates, old", [
    ("Jan 2005 - Oct 2011", False),  # exactly 15 years before October 2026: not older than 15 years
    ("Jan 2005 - Nov 2011", False),
    ("Jan 2005 - Sep 2011", True),
    ("2005 - 2011", False),  # a year-only end counts as December
    ("2005 - 2010", True),
    ("June 2015 – Present", False),
    ("2001 to 2004", True),
    ("sometime", None),
])
def test_fifteen_year_boundary(dates, old):
    assert is_old(dates, TODAY, 15) is old


def test_inventory_alone_prints_the_work_history(tmp_path):
    inv = tmp_path / "inv.md"
    inv.write_text(INVENTORY, encoding="utf-8")

    def cli(path):
        return subprocess.run([sys.executable, str(HERE / "check_content.py"), "--inventory", str(path)],
                              capture_output=True, text=True, encoding="utf-8")
    r = cli(inv)
    res = json.loads(r.stdout)
    assert r.returncode == 0 and res["ok"] and res["warnings"] == []
    assert [e["name"] for e in res["employers"]][-1] == "Vandelay Example, Cincinnati, OH"
    assert res["employers"][0]["roles"] == [
        {"title": "Director, IT Program Delivery, Columbus, OH", "dates": "2021 - Present"},
        {"title": "Senior IT Program Manager, Columbus, OH", "dates": "2018 - 2021"}]
    inv.write_text("# JANE EXAMPLE\n\nDirector at Example Corp, 2018 to now.\n", encoding="utf-8")
    r = cli(inv)
    res = json.loads(r.stdout)
    assert r.returncode == 1 and not res["ok"] and "isn't in '### Employer | dates'" in res["warnings"][0]


def test_cli_exit_codes(tmp_path):
    inv, good, bad = tmp_path / "inv.md", tmp_path / "good.json", tmp_path / "bad.json"
    inv.write_text(INVENTORY, encoding="utf-8")
    good.write_text(json.dumps(CONTENT), encoding="utf-8")
    bad.write_text(json.dumps(edited(lambda c: c["experience"].pop(0))), encoding="utf-8")

    def cli(content):
        return subprocess.run([sys.executable, str(HERE / "check_content.py"), "--inventory", str(inv),
                               "--content", str(content), "--today", "2026-10-16"],
                              capture_output=True, text=True, encoding="utf-8")
    r = cli(good)
    assert r.returncode == 0 and json.loads(r.stdout)["ok"]
    r = cli(bad)
    assert r.returncode == 1 and not json.loads(r.stdout)["ok"]
    r = cli(tmp_path / "missing.json")
    assert r.returncode == 2
