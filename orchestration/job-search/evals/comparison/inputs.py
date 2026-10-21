"""The shared cases and their inputs, for every comparison script.

Standard library only: extract_a.py runs under the system Python in WSL, outside the uv workspace.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[3]
RESULTS = HERE / "results"


def load_cases() -> dict:
    return json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


def fixture(cfg: dict, name: str) -> Path:
    return REPO / cfg["fixtures"] / name


def read_fixture(cfg: dict, name: str) -> str:
    return fixture(cfg, name).read_text(encoding="utf-8")


def jd_text(cfg: dict, case: dict) -> str:
    return read_fixture(cfg, f"{case['job']}_JD.md")


def gold_table(cfg: dict, case: dict) -> dict:
    return json.loads(read_fixture(cfg, f"gold/{case['job']}.json"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
