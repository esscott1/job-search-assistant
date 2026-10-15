"""Consistency checks for the sally-audit eval worlds (no model calls).
Run with: python -m pytest -q skills/
"""

import re
from pathlib import Path

import pytest

EVALS = Path(__file__).parent
CASES = sorted(p.parent for p in EVALS.glob("*/prompt.md"))

# The real-snapshot world is shared; this case owns it and the others carry copies.
REAL_SNAPSHOT = {"sally-audit-full-audit": ["sally-audit-single-skill", "sally-audit-refuses-to-fix"]}


def files(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_case_reads_its_own_world(case):
    assert (case / "world" / "CONTEXT.md").is_file()
    assert 'add_dirs: ["world"]' in (case / "case.yaml").read_text(encoding="utf-8")
    assert f"`evals/{case.name}/world/`" in (case / "prompt.md").read_text(encoding="utf-8")


def test_shared_world_copies_are_identical():
    for owner, copies in REAL_SNAPSHOT.items():
        original = files(EVALS / owner / "world")
        for copy in copies:
            assert files(EVALS / copy / "world") == original, f"{copy}/world differs from {owner}/world"


# Drive-style file IDs (long, letters mixed with digits) and personal email addresses must never
# appear; worlds use placeholders. Public job-alert senders are fine.
DRIVE_ID = re.compile(r"\b(?=[\w-]*\d)(?=[\w-]*[A-Za-z])[\w-]{25,}\b")
EMAIL = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")
PUBLIC_DOMAINS = {"example.com", "linkedin.com", "alerts.myjobhelper.com"}


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_worlds_hold_no_ids_or_real_addresses(case):
    for name, text in files(case / "world").items():
        assert not DRIVE_ID.findall(text), f"{name}: looks like a real file ID"
        for domain in EMAIL.findall(text):
            assert domain.rstrip(".") in PUBLIC_DOMAINS, f"{name}: email address at {domain}"
