"""Approach B on the shared cases: the same steps the evaluate graph runs (assess_fit, then
compute_fit), several runs per case. Writes results/b.json.

    uv run python evals/comparison/run_b.py --runs 3     # real model (needs ANTHROPIC_API_KEY)
    uv run python evals/comparison/run_b.py --fake       # harness check, no key, writes nothing

Records tokens per request from the adapter, never prices.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import inputs
from job_search_core import prompts, rubric, steps
from job_search_core.adapters.fakes import FakeLLM

TOKEN_NAMES = {
    "input_tokens": "input",
    "output_tokens": "output",
    "cache_read_input_tokens": "cache_read",
    "cache_creation_input_tokens": "cache_write",
}


def sum_tokens(calls: list[dict]) -> dict:
    total = dict.fromkeys(TOKEN_NAMES.values(), 0)
    for call in calls:
        for field, name in TOKEN_NAMES.items():
            total[name] += (call["tokens"] or {}).get(field, 0)
    return total


def score_once(case: dict, jd: str, resume: str, profile: str, llm, run: int) -> dict:
    first_call = len(llm.usage)
    started = time.time()
    fit, failures = None, []
    try:
        fit = steps.compute_fit(steps.assess_fit(jd, resume, profile, llm))
    except Exception as exc:  # a failure is a result here, not a crash
        failures.append(f"{type(exc).__name__}: {exc}"[:200])
    calls = llm.usage[first_call:]
    failures += [c["outcome"] for c in calls if c["outcome"] != "ok"]
    return {
        "case": case["id"],
        "run": run,
        "ok": fit is not None,
        "score": fit.score if fit else None,
        "breakdown": fit.breakdown if fit else None,
        "table": fit.evidence.model_dump() if fit else None,
        "tokens": sum_tokens(calls),
        "model_calls": len(calls),
        "seconds": round(time.time() - started, 1),
        "failures": failures,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3, help="runs per case")
    ap.add_argument("--fake", action="store_true", help="use the fake LLM (harness check)")
    ap.add_argument("--out", default=str(inputs.RESULTS / "b.json"))
    args = ap.parse_args(argv)

    if args.fake:
        llm, model = FakeLLM(), "fake"
    else:
        from dotenv import load_dotenv
        from job_search_core.adapters.anthropic_llm import AnthropicLLM

        load_dotenv()
        llm = AnthropicLLM()
        model = llm.model

    cfg = inputs.load_cases()
    resume = inputs.read_fixture(cfg, cfg["resume"])
    profile = inputs.read_fixture(cfg, cfg["profile"])
    runs = []
    for case in cfg["cases"]:
        jd = inputs.jd_text(cfg, case)
        for n in range(1, args.runs + 1):
            row = score_once(case, jd, resume, profile, llm, n)
            runs.append(row)
            print(
                f"{case['id']:<22} run {n}  score {row['score']}  {row['seconds']}s  {row['failures'] or ''}"
            )

    version, _ = prompts.load("fit_scoring")
    meta = {
        "approach": "B",
        "date": date.today().isoformat(),
        "model": model,
        "prompt": version,
        "rubric": rubric.RUBRIC_VERSION,
        "runs_per_case": args.runs,
    }
    if not args.fake:
        inputs.write_json(Path(args.out), {"meta": meta, "runs": runs})
        print(f"wrote {args.out}")
    return 0 if all(r["ok"] for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
