"""Fit-scoring evals: does a scored job land in the expected band and name the expected gaps?

    uv run python evals/job-fit/run_evals.py            # real model (needs ANTHROPIC_API_KEY)
    uv run python evals/job-fit/run_evals.py --fake     # harness smoke test, no key, no network

Evals exercise the core steps directly: assess_fit (the model fills an evidence table) and
compute_fit (the shared rubric scores it). So they measure the prompt and model plus the
rubric, not the orchestrator; any approach that calls those steps inherits these results.
Writes results/latest.json (commit it to keep a baseline you can diff in PRs).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from job_search_core import prompts, rubric, steps
from job_search_core.adapters.fakes import FakeLLM

HERE = Path(__file__).parent


def gap_hit(gaps: list[str], keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = " ".join(gaps).lower()
    return any(k.lower() in text for k in keywords)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="use the fake LLM (CI smoke test)")
    ap.add_argument("--out", default=str(HERE / "results" / "latest.json"))
    args = ap.parse_args(argv)

    if args.fake:
        llm, model = FakeLLM(), "fake"
    else:
        from dotenv import load_dotenv
        from job_search_core.adapters.anthropic_llm import AnthropicLLM

        load_dotenv()
        llm = AnthropicLLM()
        model = llm.model

    resume = (HERE / "persona_resume.md").read_text(encoding="utf-8")
    profile_text = (HERE / "persona_profile.md").read_text(encoding="utf-8")
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    version, _ = prompts.load("fit_scoring")

    rows, passed = [], 0
    for case in cases:
        t0 = time.time()
        assessment = steps.assess_fit(case["jd"], resume, profile_text, llm)
        fit = steps.compute_fit(assessment)
        lo, hi = case["expected_score"]
        in_band = lo <= fit.score <= hi
        gaps_ok = gap_hit(fit.top_gaps, case["gap_keywords_any"])
        ok = in_band and gaps_ok
        passed += ok
        rows.append(
            {
                "id": case["id"],
                "score": fit.score,
                "expected": [lo, hi],
                "in_band": in_band,
                "gaps_ok": gaps_ok,
                "gaps": fit.top_gaps,
                "breakdown": fit.breakdown,
                "requirements": len(fit.evidence.requirements),
                "seconds": round(time.time() - t0, 1),
            }
        )
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {case['id']:<32} score {fit.score:>2}  expected {lo}-{hi}")
        print(f"      {fit.breakdown}")

    summary = {
        "prompt": version,
        "rubric": rubric.RUBRIC_VERSION,
        "model": model,
        "passed": passed,
        "total": len(cases),
    }
    print(f"\n{passed}/{len(cases)} passed  ({version}, rubric v{rubric.RUBRIC_VERSION}, {model})")
    if not args.fake:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"summary": summary, "cases": rows}, indent=2) + "\n")
        print(f"wrote {out}")
    # The fake run only proves the harness works; a real run fails CI below 75%.
    return 0 if args.fake or passed / len(cases) >= 0.75 else 1


if __name__ == "__main__":
    sys.exit(main())
