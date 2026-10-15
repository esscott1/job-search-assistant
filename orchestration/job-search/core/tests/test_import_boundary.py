"""Architecture test: core must not depend on any orchestration framework.

If this fails, business logic has leaked into (or is reaching for) an orchestrator.
Move the framework-specific code into approaches/<name>/ instead.
"""

import ast
from pathlib import Path

import job_search_core

FORBIDDEN = {
    "langgraph",
    "langchain",
    "langchain_core",
    "langchain_anthropic",
    "langsmith",
    "temporalio",
    "claude_agent_sdk",
    "crewai",
    "autogen",
    "prefect",
    "job_search_langgraph",
}

CORE_ROOT = Path(job_search_core.__file__).parent


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_imports_no_orchestration_framework():
    offenders = {
        str(p.relative_to(CORE_ROOT)): sorted(_imported_roots(p) & FORBIDDEN)
        for p in CORE_ROOT.rglob("*.py")
    }
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, f"core imports orchestration frameworks: {offenders}"
