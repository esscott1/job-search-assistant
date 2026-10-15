"""Each category plugin's manifest must list every skill folder in that category.

Plugins list their skills explicitly (not "./") so the plugin's evals/ folder isn't
treated as a component location. This test catches a new skill that wasn't added.
Run with: python -m pytest -q skills/
"""

import json
from pathlib import Path

import pytest

SKILLS = Path(__file__).parent
PLUGINS = sorted(p.parent.parent for p in SKILLS.glob("*/.claude-plugin/plugin.json"))


@pytest.mark.parametrize("plugin", PLUGINS, ids=lambda p: p.name)
def test_manifest_lists_every_skill(plugin):
    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    declared = manifest["skills"]
    if declared == ["./"]:
        assert not (plugin / "evals").exists(), "a plugin with evals/ must list its skills explicitly"
        return
    on_disk = sorted(f"./{d.name}" for d in plugin.iterdir() if (d / "SKILL.md").is_file())
    assert sorted(declared) == on_disk
