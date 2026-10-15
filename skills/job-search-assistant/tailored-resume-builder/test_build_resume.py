"""Tests for build_resume.py. Needs the real template via TEMPLATE env var; skipped otherwise.
Uses only the synthetic fixture in evals/tailored-resume-builder/fixtures."""
import json, os, subprocess, sys, pathlib
import pytest
docx = pytest.importorskip("docx")
HERE = pathlib.Path(__file__).parent
TEMPLATE = os.environ.get("TEMPLATE")
pytestmark = pytest.mark.skipif(not TEMPLATE, reason="set TEMPLATE to Job-Seeker-6-Resume-Template-.docx")

def run(content, tmp_path):
    cj = tmp_path / "c.json"; cj.write_text(json.dumps(content))
    out = tmp_path / "o.docx"
    r = subprocess.run([sys.executable, str(HERE / "build_resume.py"), "--template", TEMPLATE,
                        "--content", str(cj), "--out", str(out)], capture_output=True, text=True)
    return r, out

def fixture(): return json.loads((HERE.parents[2] / "evals/tailored-resume-builder/fixtures/synthetic_content.json").read_text())

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

def test_short_resume_warns_not_two_pages(tmp_path):
    r, _ = run(fixture(), tmp_path); res = json.loads(r.stdout)
    assert any("pages" in w for w in res["warnings"])
