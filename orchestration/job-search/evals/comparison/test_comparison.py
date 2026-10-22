"""The comparison's own checks: inputs exist, matching behaves, extraction keeps only named fields.
No model calls; the eval results and traces here are small synthetic stand-ins in the real shape."""

import copy
import json
import re

import compare
import extract_a
import inputs
import pytest
import run_b

CFG = inputs.load_cases()
GOLD = {c["id"]: inputs.gold_table(CFG, c) for c in CFG["cases"]}
PARTIAL = GOLD["partial-fit"]


# --- inputs ---


def test_every_case_points_at_existing_inputs():
    plugin_evals = inputs.REPO / "skills/job-search-assistant/evals"
    assert inputs.fixture(CFG, CFG["resume"]).is_file()
    assert inputs.fixture(CFG, CFG["profile"]).is_file()
    for case in CFG["cases"]:
        assert inputs.jd_text(CFG, case).strip()
        assert inputs.gold_table(CFG, case)["requirements"]
        assert (plugin_evals / case["a_case"] / "prompt.md").is_file()


def test_the_comparison_tag_selects_exactly_the_shared_cases():
    """run_a.sh selects A's cases by the `comparison` tag, so the tag and cases.json must agree."""
    plugin_evals = inputs.REPO / "skills/job-search-assistant/evals"
    tagged = {
        p.parent.name
        for p in plugin_evals.glob("*/prompt.md")
        if re.search(r"^tags: \[.*\bcomparison\b.*\]$", p.read_text(encoding="utf-8"), re.M)
    }
    assert tagged == {c["a_case"] for c in CFG["cases"]}


# --- matching ---


def test_a_table_matches_itself_completely():
    result = compare.compare_tables(PARTIAL, PARTIAL)
    assert result["overlap"] == 1
    assert result["evidence_agree"] == 1
    assert result["unmatched_first"] == result["unmatched_second"] == []


def test_paraphrases_match_and_different_requirements_do_not():
    assert (
        compare.similarity("8+ years of IT program management", "IT program management (8+ years)")
        == 1
    )
    assert (
        compare.similarity(
            "Experience leading migrations to Microsoft Azure", "Azure migration leadership"
        )
        >= compare.MATCH_THRESHOLD
    )
    assert (
        compare.similarity("Vendor management", "IT program management") < compare.MATCH_THRESHOLD
    )
    assert compare.similarity("Vendor management", "Managed budgets over $2m") == 0


@pytest.mark.parametrize("case", sorted(GOLD))
def test_no_two_gold_requirements_are_confusable(case):
    """The threshold's calibration: within one JD, distinct requirements never match each other."""
    reqs = GOLD[case]["requirements"]
    for i, a in enumerate(reqs):
        for b in reqs[i + 1 :]:
            assert compare.similarity(a["text"], b["text"]) < compare.MATCH_THRESHOLD, (a, b)


def test_matching_is_one_to_one():
    one = [{"text": "Vendor management"}]
    two = [{"text": "Vendor management"}, {"text": "Vendor management experience"}]
    assert len(compare.match(one, two)) == 1


def test_a_changed_call_and_a_missing_requirement_are_counted():
    other = copy.deepcopy(PARTIAL)
    other["requirements"][1]["evidence"] = "strong"  # Azure: partial -> strong
    del other["requirements"][-1]  # Power BI left out
    result = compare.compare_tables(PARTIAL, other)
    assert result["overlap"] == pytest.approx(8 / 9)
    assert result["evidence_agree"] == pytest.approx(7 / 8)
    assert result["unmatched_first"] == ["Power BI"]


# --- extracting approach A ---


def trace(table: dict, *, score_py_failed=False, web=False) -> list[dict]:
    report = (
        "# JS-102 Contoso Health: IT Program Manager, fit run r1\nScore: 7 (T2)\n"
        "Breakdown: Rubric v1.1 | Req 3.5/6 | raw 6.8 → 7\n\n## Evidence table\n"
        f"```json\n{json.dumps(table)}\n```\n"
    )
    calls = [
        {
            "type": "tool_use",
            "id": "t1",
            "name": "Bash",
            "input": {"command": "python3 score.py ev.json"},
        },
        {
            "type": "tool_use",
            "id": "t2",
            "name": "mcp__plugin_gstub_gdrive__create_file",
            "input": {"title": "JS-102_fit_r1_2026-10-21.md", "textContent": report},
        },
    ]
    if web:
        calls.append({"type": "tool_use", "id": "t3", "name": "WebSearch", "input": {"query": "x"}})
    return [
        {
            "type": "assistant",
            "message": {"id": "m1", "model": "claude-sonnet-5-5", "content": calls[:1]},
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "is_error": score_py_failed}
                ]
            },
        },
        {
            "type": "assistant",
            "message": {"id": "m2", "model": "claude-sonnet-5-5", "content": calls[1:]},
        },
        {
            "type": "result",
            "num_turns": 23,
            "duration_api_ms": 37469,
            "total_cost_usd": 0.25,
            "usage": {
                "input_tokens": 24,
                "output_tokens": 5391,
                "cache_read_input_tokens": 389291,
                "cache_creation_input_tokens": 40591,
            },
            "modelUsage": {"claude-sonnet-5-5": {"costUSD": 0.25}},
        },
    ]


def eval_result(error=None) -> dict:
    run = {
        "score": 1,
        "turns": 23,
        "durationSeconds": 62,
        "error": error,
        "costUsd": 0.26,
        "judgeCostUsd": 0,
    }
    return {
        "startedAt": "2026-10-21T14:00:00Z",
        "claudeVersion": "2.1.301",
        "costUsd": 0.78,
        "suite": {"plugins": [{"name": "job-search-assistant", "version": "0.4.5", "path": "/x"}]},
        "cases": [
            {
                "name": c["a_case"],
                "arms": {
                    "with": [dict(run, tracePath=f"/tmp/claude-eval-{c['id']}/out/trace.jsonl")]
                },
            }
            for c in CFG["cases"]
        ],
    }


def keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(keys(v) for v in value)) if value else set()
    return set()


def test_extract_reads_the_table_tokens_and_score_from_the_trace():
    result = eval_result()
    traces = {r["tracePath"]: trace(PARTIAL) for c in result["cases"] for r in c["arms"]["with"]}
    data = extract_a.extract(result, traces)
    row = next(r for r in data["runs"] if r["case"] == "partial-fit")
    assert row["ok"] and row["failures"] == []
    assert row["table"] == PARTIAL
    assert row["score"] == 7
    assert row["tokens"] == {
        "input": 24,
        "output": 5391,
        "cache_read": 389291,
        "cache_write": 40591,
    }
    assert row["model_calls"] == 2 and row["turns"] == 23 and row["api_seconds"] == 37.5
    assert data["meta"]["models"] == ["claude-sonnet-5-5"]
    assert data["meta"]["plugin_version"] == "0.4.5"


def test_extract_never_copies_a_cost_field():
    result = eval_result()
    traces = {r["tracePath"]: trace(PARTIAL) for c in result["cases"] for r in c["arms"]["with"]}
    found = {
        k
        for k in keys(extract_a.extract(result, traces))
        if "cost" in k.lower() or "usd" in k.lower()
    }
    assert found == set()


def test_extract_records_failures():
    result = eval_result(error="timeout")
    traces = {
        r["tracePath"]: trace(PARTIAL, score_py_failed=True, web=True)
        for c in result["cases"]
        for r in c["arms"]["with"]
    }
    traces[result["cases"][0]["arms"]["with"][0]["tracePath"]] = None
    data = extract_a.extract(result, traces)
    assert data["runs"][0]["failures"] == ["run_error: timeout", "no_trace"]
    assert data["runs"][1]["failures"] == ["run_error: timeout", "score_py_error", "web_used"]


# --- comparing ---


def approach_runs(scores: dict[str, list[int]], tokens: dict) -> dict:
    runs = [
        {
            "case": case,
            "run": n,
            "ok": True,
            "score": s,
            "table": GOLD[case],
            "tokens": tokens,
            "model_calls": 1,
            "seconds": 5,
            "failures": [],
        }
        for case, ss in scores.items()
        for n, s in enumerate(ss, start=1)
    ]
    return {"meta": {"model": "m", "models": ["m"], "rubric": "1.1"}, "runs": runs}


def test_summary_and_report():
    tokens = {"input": 3296, "output": 758, "cache_read": 0, "cache_write": 0}
    a = approach_runs(
        {"strong-fit": [10, 9], "partial-fit": [7, 7], "relocation-mismatch": [1, 1]}, tokens
    )
    b = approach_runs(
        {"strong-fit": [10, 10], "partial-fit": [7, 5], "relocation-mismatch": [1, 2]}, tokens
    )
    summary = compare.summarize(a, b, CFG)
    partial = next(c for c in summary["cases"] if c["case"] == "partial-fit")
    assert partial["gold_score"] == 7
    assert partial["A"]["within_1_of_gold"] == 1
    assert partial["B"]["within_1_of_gold"] == 0.5
    assert partial["A_vs_B"]["within_1"] == 0.5
    assert partial["A_vs_B"]["overlap"] == 1
    assert summary["per_job"]["B"]["tokens"]["total"] == 4054
    report = compare.render(summary)
    assert "| partial-fit (JS-102) | 7 | 7 · 7 | 7 · 5 |" in report
    assert "$" not in report and "usd" not in report.lower()


def test_run_b_harness_works_with_the_fake_model(capsys):
    assert run_b.main(["--fake", "--runs", "1"]) == 0
    assert "partial-fit" in capsys.readouterr().out
