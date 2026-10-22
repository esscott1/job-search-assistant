"""Studio's entry point: importing it has no side effects, and it shares the CLI's data folder."""

import asyncio
import importlib

from job_search_langgraph import deps


def test_importing_studio_opens_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_DATA_DIR", str(tmp_path / "data"))
    studio = importlib.reload(importlib.import_module("job_search_langgraph.studio"))
    assert not (tmp_path / "data").exists()

    graph = asyncio.run(studio.make_graph())
    assert (tmp_path / "data" / "tracker.db").exists()  # built on first use
    assert "assess_fit" in graph.get_graph().nodes
    studio._deps.cache_clear()


def test_relative_data_dir_is_taken_from_the_workspace_not_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # as when Studio runs from approaches/langgraph
    monkeypatch.setenv("JOBS_DATA_DIR", "data")
    assert deps.data_dir() == deps.WORKSPACE / "data"
    assert "[tool.uv.workspace]" in (deps.WORKSPACE / "pyproject.toml").read_text(encoding="utf-8")
