"""Turn a `claude plugin eval --json` result for the shared cases into results/a.json.

    python3 extract_a.py <eval result.json> [--traces-dir DIR] [--out results/a.json]

run_a.sh calls this straight after the eval, in the same session: each run's trace sits in the
eval's kept sandbox under /tmp, which WSL clears when the distro stops. Standard library only,
because it runs under the system Python.

What comes from where, for each run:
- the evidence table, score and breakdown: the fit report the skill wrote (the `create_file`
  call for `<ID>_fit_r<n>_<date>.md`), whose JSON block is the table it scored;
- tokens, turns and time: the trace's final `result` event (per-message usage in a streamed
  trace under-counts output);
- the eval's own verdict: the grader score from the eval result.

Only named fields are copied. The eval result and the trace also carry the runner's cost
estimates, and those must never reach the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import inputs

FENCED_JSON = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)
WEB_TOOLS = ("WebSearch", "WebFetch", "web_search", "gstub_web__")


def read_trace(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def tool_calls(events: list[dict]) -> list[dict]:
    calls = []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for block in e.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                calls.append(block)
    return calls


def failed_tool_ids(events: list[dict]) -> set[str]:
    failed = set()
    for e in events:
        if e.get("type") != "user":
            continue
        content = e.get("message", {}).get("content", [])
        for block in content if isinstance(content, list) else []:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and block.get("is_error")
            ):
                failed.add(block.get("tool_use_id"))
    return failed


def fit_report(calls: list[dict]) -> dict | None:
    """The last fit report the run wrote: its evidence table, score and breakdown."""
    reports = [
        c
        for c in calls
        if c["name"].endswith("create_file") and "_fit_r" in str(c.get("input", {}).get("title"))
    ]
    if not reports:
        return None
    text = reports[-1]["input"].get("textContent") or ""
    table = FENCED_JSON.search(text)
    score = re.search(r"^Score: (\d+)", text, re.M)
    breakdown = re.search(r"^Breakdown: (.+)$", text, re.M)
    return {
        "table": json.loads(table.group(1)) if table else None,
        "score": int(score.group(1)) if score else None,
        "breakdown": breakdown.group(1).strip() if breakdown else None,
    }


def run_row(case_id: str, n: int, run: dict, events: list[dict] | None) -> dict:
    failures = []
    if run.get("error"):
        failures.append(f"run_error: {run['error']}"[:200])
    row = {
        "case": case_id,
        "run": n,
        "ok": False,
        "score": None,
        "breakdown": None,
        "table": None,
        "tokens": None,
        "model_calls": None,
        "turns": run.get("turns"),
        "seconds": run.get("durationSeconds"),
        "api_seconds": None,
        "eval_score": run.get("score"),
        "models": [],
        "failures": failures,
    }
    if events is None:
        failures.append("no_trace")
        return row

    calls = tool_calls(events)
    report = fit_report(calls)
    if report is None:
        failures.append("no_fit_report")
    elif report["table"] is None:
        failures.append("fit_report_without_table")
    else:
        row.update(report)
    score_runs = [c for c in calls if c["name"] == "Bash" and "score.py" in json.dumps(c["input"])]
    if not score_runs:
        failures.append("score_py_not_run")
    failed = failed_tool_ids(events)
    failures += ["score_py_error"] * sum(c["id"] in failed for c in score_runs)
    if any(any(w in c["name"] for w in WEB_TOOLS) for c in calls):
        failures.append("web_used")

    messages = {}
    for e in events:
        if e.get("type") == "assistant" and e.get("message", {}).get("id"):
            messages[e["message"]["id"]] = e["message"].get("model")
    row["model_calls"] = len(messages)
    row["models"] = sorted({m for m in messages.values() if m})
    final = [e for e in events if e.get("type") == "result"]
    if final:
        usage = final[-1].get("usage") or {}
        row["tokens"] = {
            "input": usage.get("input_tokens", 0),
            "output": usage.get("output_tokens", 0),
            "cache_read": usage.get("cache_read_input_tokens", 0),
            "cache_write": usage.get("cache_creation_input_tokens", 0),
        }
        row["turns"] = final[-1].get("num_turns", row["turns"])
        row["api_seconds"] = round((final[-1].get("duration_api_ms") or 0) / 1000, 1)
    else:
        failures.append("no_result_event")
    row["ok"] = row["table"] is not None and row["score"] is not None
    return row


def extract(result: dict, traces: dict[str, list[dict] | None]) -> dict:
    """`traces` maps each run's tracePath to its events (None when it couldn't be read)."""
    cfg = inputs.load_cases()
    by_a_case = {c["a_case"]: c["id"] for c in cfg["cases"]}
    runs, seen = [], set()
    for case in result["cases"]:
        if case["name"] not in by_a_case:
            continue
        seen.add(case["name"])
        for n, run in enumerate(case["arms"]["with"], start=1):
            runs.append(run_row(by_a_case[case["name"]], n, run, traces.get(run.get("tracePath"))))
    missing = set(by_a_case) - seen
    if missing:
        raise SystemExit(f"eval result has no runs for {sorted(missing)}")
    plugin = next(
        (p for p in result["suite"]["plugins"] if p["name"] == "job-search-assistant"), {}
    )
    meta = {
        "approach": "A",
        "date": (result.get("startedAt") or "")[:10],
        "models": sorted({m for r in runs for m in r["models"]}),
        "plugin_version": plugin.get("version"),
        "claude_code": result.get("claudeVersion"),
        "runs_per_case": max((r["run"] for r in runs), default=0),
    }
    return {"meta": meta, "runs": runs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result", help="the eval's --json output")
    ap.add_argument("--traces-dir", help="also copy each run's trace here (outside the repo)")
    ap.add_argument("--out", default=str(inputs.RESULTS / "a.json"))
    args = ap.parse_args(argv)

    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    traces: dict[str, list[dict] | None] = {}
    for i, run in enumerate(r for c in result["cases"] for r in c["arms"]["with"]):
        path = Path(run.get("tracePath") or "")
        traces[str(path)] = read_trace(path) if path.is_file() else None
        if args.traces_dir and path.is_file():
            Path(args.traces_dir).mkdir(parents=True, exist_ok=True)
            shutil.copy(path, Path(args.traces_dir) / f"{i:02d}-trace.jsonl")
    data = extract(result, traces)
    inputs.write_json(Path(args.out), data)
    for r in data["runs"]:
        print(
            f"{r['case']:<22} run {r['run']}  score {r['score']}  {r['seconds']}s  {r['failures'] or ''}"
        )
    print(f"wrote {args.out}")
    return 0 if all(r["ok"] for r in data["runs"]) else 1


if __name__ == "__main__":
    sys.exit(main())
