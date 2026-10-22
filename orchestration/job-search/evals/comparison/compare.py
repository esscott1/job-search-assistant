"""Compare approaches A and B on the shared cases. No model calls.

    uv run python evals/comparison/compare.py

Reads results/a.json, results/b.json and the gold evidence tables; writes results/comparison.json
and results/RESULTS.md. Rerunning it on the same inputs gives the same output.

Requirements from two evidence tables are matched one-to-one by a deterministic text similarity
(below), not by a model, so the measurement adds no judgment of its own. Every comparison lists
what it left unmatched and any match that wasn't word-for-word, so a reader can check it.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

import inputs
from job_search_core import rubric

# Words that say nothing about which requirement it is ("5+ years of experience with ...").
STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to",
    "with", "within", "experience", "experienced", "ability", "proven", "demonstrated",
    "strong", "knowledge", "working", "including", "plus", "year", "years", "skill", "skills",
    "certification", "certified", "certificate",
}  # fmt: skip
# Calibrated on the gold tables: paraphrases of one requirement score 0.5 or more; different
# requirements that share a word ("vendor management", "program management") score below it.
MATCH_THRESHOLD = 0.5
TOKEN_KINDS = ("input", "cache_write", "cache_read", "output")


def words(text: str) -> set[str]:
    out = set()
    for w in re.sub(r"[^a-z0-9+]+", " ", text.lower()).split():
        if w in STOPWORDS:
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


def similarity(a: str, b: str) -> float:
    """Dice coefficient of the two texts' significant words."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return 2 * len(wa & wb) / (len(wa) + len(wb))


def match(reqs_a: list[dict], reqs_b: list[dict]) -> list[tuple[int, int, float]]:
    """One-to-one matches, best first, each at or above MATCH_THRESHOLD."""
    scored = sorted(
        (
            (similarity(ra["text"], rb["text"]), i, j)
            for i, ra in enumerate(reqs_a)
            for j, rb in enumerate(reqs_b)
        ),
        reverse=True,
    )
    used_a, used_b, pairs = set(), set(), []
    for sim, i, j in scored:
        if sim < MATCH_THRESHOLD:
            break
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            pairs.append((i, j, round(sim, 2)))
    return pairs


def compare_tables(a: dict, b: dict) -> dict:
    """How far two evidence tables agree: requirement overlap, then the calls on what matched."""
    ra, rb = a["requirements"], b["requirements"]
    pairs = match(ra, rb)
    n = len(pairs)
    return {
        "overlap": n / max(len(ra), len(rb), 1),
        "evidence_agree": sum(ra[i]["evidence"] == rb[j]["evidence"] for i, j, _ in pairs) / n
        if n
        else 0.0,
        "type_agree": sum(ra[i]["type"] == rb[j]["type"] for i, j, _ in pairs) / n if n else 0.0,
        "title_agree": a["title_seniority"] == b["title_seniority"],
        "arrangement_agree": a["work_arrangement"] == b["work_arrangement"],
        "unmatched_first": [
            r["text"] for k, r in enumerate(ra) if k not in {i for i, _, _ in pairs}
        ],
        "unmatched_second": [
            r["text"] for k, r in enumerate(rb) if k not in {j for _, j, _ in pairs}
        ],
        "inexact_matches": [
            {"first": ra[i]["text"], "second": rb[j]["text"], "similarity": s}
            for i, j, s in pairs
            if s < 1
        ],
    }


def mean(values) -> float | None:
    values = list(values)
    return round(statistics.fmean(values), 3) if values else None


def median(values) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def against(tables: list[dict], other: dict) -> dict:
    """Average agreement of several runs' tables with one table (gold)."""
    results = [compare_tables(t, other) for t in tables]
    return {
        "overlap": mean(r["overlap"] for r in results),
        "evidence_agree": mean(r["evidence_agree"] for r in results),
        "title_agree": mean(r["title_agree"] for r in results),
        "arrangement_agree": mean(r["arrangement_agree"] for r in results),
        "details": results,
    }


def approach_case(runs: list[dict], gold: dict, gold_score: int) -> dict:
    ok = [r for r in runs if r["ok"]]
    scores = [r["score"] for r in ok]
    return {
        "runs": len(runs),
        "scored": len(ok),
        "scores": scores,
        "median": median(scores),
        "spread": [min(scores), max(scores)] if scores else None,
        "within_1_of_gold": mean(abs(s - gold_score) <= 1 for s in scores),
        "exact_gold": mean(s == gold_score for s in scores),
        "vs_gold": against([r["table"] for r in ok], gold),
    }


def a_vs_b(runs_a: list[dict], runs_b: list[dict]) -> dict:
    pairs = [(a, b) for a in runs_a if a["ok"] for b in runs_b if b["ok"]]
    tables = [compare_tables(a["table"], b["table"]) for a, b in pairs]
    return {
        "pairs": len(pairs),
        "within_1": mean(abs(a["score"] - b["score"]) <= 1 for a, b in pairs),
        "median_difference": median(a["score"] - b["score"] for a, b in pairs),
        "overlap": mean(t["overlap"] for t in tables),
        "evidence_agree": mean(t["evidence_agree"] for t in tables),
        "details": tables,
    }


def cost_of_a_job(runs: list[dict]) -> dict:
    """Median tokens, model calls and seconds per scored job. Tokens only, never prices."""
    with_tokens = [r for r in runs if r.get("tokens")]
    tokens = {k: median(r["tokens"][k] for r in with_tokens) for k in TOKEN_KINDS}
    tokens["total"] = median(sum(r["tokens"][k] for k in TOKEN_KINDS) for r in with_tokens)
    return {
        "tokens": tokens,
        "model_calls": median(r.get("model_calls") for r in runs),
        "seconds": median(r.get("seconds") for r in runs),
    }


def failure_counts(runs: list[dict]) -> dict:
    return dict(Counter(f.split(":")[0] for r in runs for f in r["failures"]))


def summarize(a: dict, b: dict, cfg: dict) -> dict:
    cases = []
    for case in cfg["cases"]:
        gold = inputs.gold_table(cfg, case)
        gold_score = rubric.score(gold)["score"]
        runs_a = [r for r in a["runs"] if r["case"] == case["id"]]
        runs_b = [r for r in b["runs"] if r["case"] == case["id"]]
        cases.append(
            {
                "case": case["id"],
                "job": case["job"],
                "gold_score": gold_score,
                "A": approach_case(runs_a, gold, gold_score),
                "B": approach_case(runs_b, gold, gold_score),
                "A_vs_B": a_vs_b(runs_a, runs_b),
            }
        )
    return {
        "meta": {"A": a["meta"], "B": b["meta"], "match_threshold": MATCH_THRESHOLD},
        "cases": cases,
        "per_job": {"A": cost_of_a_job(a["runs"]), "B": cost_of_a_job(b["runs"])},
        "failures": {"A": failure_counts(a["runs"]), "B": failure_counts(b["runs"])},
    }


def pct(x) -> str:
    return "n/a" if x is None else f"{round(100 * x)}%"


def num(x) -> str:
    return "n/a" if x is None else f"{round(x):,}"


def render(s: dict) -> str:
    ma, mb = s["meta"]["A"], s["meta"]["B"]
    lines = [
        "# Measured comparison: A (plugin) and B (LangGraph pipeline)",
        "",
        "Generated by `compare.py` from `a.json`, `b.json` and the gold evidence tables; don't edit it by hand. "
        "Method and caveats: [`../README.md`](../README.md).",
        "",
        f"- **A:** plugin {ma.get('plugin_version')}, Claude Code {ma.get('claude_code')}, "
        f"model {', '.join(ma.get('models') or ['?'])}, {ma.get('runs_per_case')} runs per case, {ma.get('date')}.",
        f"- **B:** prompt `{mb.get('prompt')}`, model {mb.get('model')}, "
        f"{mb.get('runs_per_case')} runs per case, {mb.get('date')}.",
        f"- **Rubric:** v{mb.get('rubric')} for both (the same code).",
        "",
        "## Scores",
        "",
        "| Case | Gold | A scores | B scores | A within ±1 of gold | B within ±1 of gold | A–B pairs within ±1 |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in s["cases"]:
        lines.append(
            f"| {c['case']} ({c['job']}) | {c['gold_score']} | {' · '.join(map(str, c['A']['scores'])) or 'none'} "
            f"| {' · '.join(map(str, c['B']['scores'])) or 'none'} | {pct(c['A']['within_1_of_gold'])} "
            f"| {pct(c['B']['within_1_of_gold'])} | {pct(c['A_vs_B']['within_1'])} |"
        )
    lines += [
        "",
        "## Requirements",
        "",
        "Overlap is matched requirements ÷ the longer list. Evidence agreement is the share of matched "
        "requirements given the same call (strong, partial or none).",
        "",
        "| Case | A–gold overlap | B–gold overlap | A–B overlap | A–gold evidence | B–gold evidence | A–B evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in s["cases"]:
        ga, gb, ab = c["A"]["vs_gold"], c["B"]["vs_gold"], c["A_vs_B"]
        lines.append(
            f"| {c['case']} | {pct(ga['overlap'])} | {pct(gb['overlap'])} | {pct(ab['overlap'])} "
            f"| {pct(ga['evidence_agree'])} | {pct(gb['evidence_agree'])} | {pct(ab['evidence_agree'])} |"
        )
    lines += [
        "",
        "## Model work per job (median)",
        "",
        "| Approach | Model calls | Input, new | Cache write | Cache read | Output | All tokens | Seconds |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, label in (("A", "A · plugin, whole run"), ("B", "B · pipeline, scoring calls")):
        j = s["per_job"][name]
        t = j["tokens"]
        lines.append(
            f"| {label} | {num(j['model_calls'])} | {num(t['input'])} | {num(t['cache_write'])} "
            f"| {num(t['cache_read'])} | {num(t['output'])} | {num(t['total'])} | {num(j['seconds'])} |"
        )
    lines += ["", "## Failures", ""]
    for name in ("A", "B"):
        counts = s["failures"][name]
        found = ", ".join(f"{k} × {v}" for k, v in sorted(counts.items())) or "none"
        lines.append(f"- **{name}:** {found}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default=str(inputs.RESULTS / "a.json"))
    ap.add_argument("--b", default=str(inputs.RESULTS / "b.json"))
    ap.add_argument("--out-dir", default=str(inputs.RESULTS))
    args = ap.parse_args(argv)

    a = json.loads(Path(args.a).read_text(encoding="utf-8"))
    b = json.loads(Path(args.b).read_text(encoding="utf-8"))
    summary = summarize(a, b, inputs.load_cases())
    out = Path(args.out_dir)
    inputs.write_json(out / "comparison.json", summary)
    (out / "RESULTS.md").write_text(render(summary), encoding="utf-8")
    print(render(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
