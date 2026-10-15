"""Tests for build_resume.py. Run with: python3 -m pytest -q skills/job-search-assistant/tailored-resume-builder

Uses the synthetic template and content in ../evals/fixtures (made by make_synthetic_template.py,
same structure as the real template, placeholder text only). Set TEMPLATE to test against
the real template instead."""
import json, os, subprocess, sys, pathlib
import pytest
docx = pytest.importorskip("docx")
HERE = pathlib.Path(__file__).parent
FIXTURES = HERE.parent / "evals" / "fixtures"
TEMPLATE = os.environ.get("TEMPLATE") or str(FIXTURES / "Synthetic-Resume-Template.docx")

def run(content, tmp_path):
    cj = tmp_path / "c.json"; cj.write_text(json.dumps(content))
    out = tmp_path / "o.docx"
    r = subprocess.run([sys.executable, str(HERE / "build_resume.py"), "--template", TEMPLATE,
                        "--content", str(cj), "--out", str(out)], capture_output=True, text=True)
    return r, out

def fixture(): return json.loads((FIXTURES / "synthetic_content.json").read_text())

def test_fills_template_layout(tmp_path):
    r, out = run(fixture(), tmp_path); assert r.returncode == 0, r.stdout
    d = docx.Document(out); t = [p.text for p in d.paragraphs]
    assert t[0] == "JANE EXAMPLE" and "CORE COMPETENCIES" in t and "PROFESSIONAL EXPERIENCE" in t
    assert d.sections[0].left_margin == docx.Document(TEMPLATE).sections[0].left_margin
    assert "Liberty Global" not in " ".join(t)  # no template sample text left over

def test_rejects_missing_section(tmp_path):
    c = fixture(); del c["experience"]
    r, _ = run(c, tmp_path); assert r.returncode == 2

def test_rejects_too_many_competencies(tmp_path):
    c = fixture(); c["competencies"] = [f"s{i}" for i in range(13)]
    r, _ = run(c, tmp_path); assert r.returncode == 2

def test_short_resume_is_acceptable(tmp_path):
    """Under 2 pages is fine; only an over-length resume, or an unverifiable page count, warns."""
    r, _ = run(fixture(), tmp_path); res = json.loads(r.stdout)
    if res["pages"] is None:
        assert res["warnings"] == ["could not render to PDF; page count unverified"]
    else:
        assert res["pages"] <= 2 and res["warnings"] == []


def test_over_two_pages_warns(tmp_path):
    c = fixture()
    c["experience"][0]["roles"][0]["bullets"] *= 40
    r, _ = run(c, tmp_path); res = json.loads(r.stdout)
    if res["pages"] is None:
        pytest.skip("LibreOffice not installed; page count can't be checked")
    assert res["pages"] > 2 and any("limit is 2" in w for w in res["warnings"])
