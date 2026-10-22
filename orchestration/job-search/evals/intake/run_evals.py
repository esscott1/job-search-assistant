"""Intake evals: the plugin's intake case, run through the intake graph with a real model.

    uv run python evals/intake/run_evals.py --runs 3   # real model (needs ANTHROPIC_API_KEY)
    uv run python evals/intake/run_evals.py --fake     # harness smoke test, no key, no network

The inputs are the plugin's own (skills/job-search-assistant/evals/): its inbox (two LinkedIn
digests and a LinkedIn message notification), its synthetic profile, and the jobs its
`intake-logs-new-leads` case already has (JS-001 and JS-002 in the Job Log, JS-005 archived).
The right outcome is that case's: Globex and Initech logged, in that order; the retail job, the
JS-001 duplicate and the archived Umbrella job skipped; no sign-in token stored. Writes
results/latest.json with each run's checks and tokens (never prices).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from job_search_core import prompts
from job_search_core.adapters.fakes import (
    FakeJDFetcher,
    FakeLLM,
    FakeMail,
    InMemoryDocumentStore,
    InMemoryProfileSource,
    InMemoryResumeSource,
    digest_leads,
)
from job_search_core.adapters.known_jobs import TrackerKnownJobs
from job_search_core.adapters.sqlite_tracker import SqliteTracker
from job_search_core.domain import KnownJob
from job_search_core.ports import MailMessage
from job_search_langgraph.deps import Deps
from job_search_langgraph.intake_graph import build_intake_graph

HERE = Path(__file__).parent
FIXTURES = HERE.parents[3] / "skills/job-search-assistant/evals/fixtures"
TODAY = "2026-10-16"

KNOWN = [
    KnownJob(id="JS-002", company="Acme Widgets", title="Senior Cloud Program Manager",
             canonical_url="https://www.linkedin.com/jobs/view/4000000002/"),
    KnownJob(id="JS-001", company="Example Corp", title="IT Vendor Manager",
             canonical_url="https://www.linkedin.com/jobs/view/4000000001/"),
    KnownJob(id="JS-005", company="Umbrella Example", title="Program Manager, Infrastructure",
             canonical_url="https://www.linkedin.com/jobs/view/4000000005/"),
]  # fmt: skip
EXPECTED_ADDED = ["Globex Corp", "Initech"]
EXPECTED_DUPLICATES = {"Example Corp": "JS-001", "Umbrella Example": "JS-005"}
OFF_TARGET = "ShopMart Example"
T1_BAND = (6, 8)


def inbox() -> list[MailMessage]:
    raw = json.loads((FIXTURES / "inbox.json").read_text(encoding="utf-8"))
    return [
        MailMessage(
            id=m["messageId"],
            thread_id=m["threadId"],
            sender=m["sender"],
            subject=m["subject"],
            received_at=m["date"],
            body_text=m["plaintext_body"],
        )
        for m in raw
    ]


class KnownWithArchive:
    def __init__(self, tracker):
        self.rows = TrackerKnownJobs(tracker)

    def known_jobs(self):
        return self.rows.known_jobs() + KNOWN


def checks(result: dict, tracker: SqliteTracker) -> dict[str, bool]:
    added = [a["company"] for a in result["added"]]
    reasons = {s["company"]: s["reason"] for s in result["skipped"]}
    scores = [a["score"] for a in result["added"]]
    return {
        "logs exactly Globex then Initech": added == EXPECTED_ADDED,
        "skips the duplicates": all(
            reasons.get(c) == f"already known as {i}" for c, i in EXPECTED_DUPLICATES.items()
        ),
        "skips the retail job as off-target": OFF_TARGET in reasons
        and not reasons[OFF_TARGET].startswith("already known"),
        f"Tier 1 scores in {T1_BAND[0]}-{T1_BAND[1]}": bool(scores)
        and all(T1_BAND[0] <= s <= T1_BAND[1] for s in scores),
        "stores no sign-in token": all(
            "otpToken" not in j.model_dump_json() for j in tracker.list()
        ),
    }


def run_once(llm) -> dict:
    tracker = SqliteTracker()
    deps = Deps(
        tracker=tracker,
        jd_fetcher=FakeJDFetcher(),
        llm=llm,
        resume=InMemoryResumeSource(),
        docs=InMemoryDocumentStore(),
        profile=InMemoryProfileSource(
            (FIXTURES / "job-search-profile.md").read_text(encoding="utf-8")
        ),
        mail=FakeMail(inbox()),
        known=KnownWithArchive(tracker),
    )
    first_call, started = len(llm.usage), time.time()
    result = build_intake_graph(deps).invoke({"today": TODAY})
    calls = llm.usage[first_call:]
    tokens = {
        name: sum((c["tokens"] or {}).get(field, 0) for c in calls)
        for name, field in (("input", "input_tokens"), ("output", "output_tokens"))
    }
    return {
        "checks": checks(result, tracker),
        "added": result["added"],
        "skipped": result["skipped"],
        "model_calls": len(calls),
        "tokens": tokens,
        "seconds": round(time.time() - started, 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--fake", action="store_true", help="use the digest stand-in (CI smoke test)")
    ap.add_argument("--out", default=str(HERE / "results" / "latest.json"))
    args = ap.parse_args(argv)

    if args.fake:
        llm, model = FakeLLM(leads_for=digest_leads), "fake"
    else:
        from dotenv import load_dotenv
        from job_search_core.adapters.anthropic_llm import AnthropicLLM

        load_dotenv()
        llm = AnthropicLLM()
        model = llm.model

    runs = []
    for n in range(1, args.runs + 1):
        run = run_once(llm)
        runs.append(run)
        failed = [name for name, ok in run["checks"].items() if not ok]
        print(f"run {n}: {'PASS' if not failed else 'FAIL ' + ', '.join(failed)}")
        for a in run["added"]:
            print(f"    added   {a['company']} — {a['title']} (T1 {a['score']})")
        for s in run["skipped"]:
            print(f"    skipped {s['company']} — {s['title']}: {s['reason']}")

    passed = sum(all(r["checks"].values()) for r in runs)
    version, _ = prompts.load("lead_reading")
    summary = {
        "prompt": version,
        "model": model,
        "passed": passed,
        "runs": len(runs),
        "date": date.today().isoformat(),
    }
    print(f"\n{passed}/{len(runs)} runs passed  ({version}, {model})")
    if not args.fake:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"summary": summary, "runs": runs}, indent=1) + "\n", encoding="utf-8"
        )
        print(f"wrote {out}")
    return 0 if passed == len(runs) else 1


if __name__ == "__main__":
    sys.exit(main())
