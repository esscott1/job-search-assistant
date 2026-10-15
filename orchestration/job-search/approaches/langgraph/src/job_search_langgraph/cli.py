"""`jobs` command line: drive the evaluate graph and record what only you know (submissions).

jobs demo                         run all three paths with fakes — no keys needed
jobs auth google                  one-time Google sign-in, then verify Gmail + Drive
jobs add --company X --title Y --url Z
jobs list [--status resume_ready]
jobs show JOB_ID                  job, status history, and what the graph is waiting on
jobs evaluate JOB_ID [--restart]  run until done or until it needs you
jobs provide-jd JOB_ID --file jd.txt
jobs review JOB_ID --approve | --reject [--note ...]
jobs submit JOB_ID [--note ...]
jobs set-status JOB_ID STATUS [--note ...]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from job_search_core import usecases
from job_search_core.domain import IllegalTransition, Job, Status
from langgraph.types import Command

from .deps import Deps, data_dir, real_deps
from .evaluate_graph import build_evaluate_graph, fresh_input, pending_interrupt


def _graph(deps: Deps):
    from langgraph.checkpoint.sqlite import SqliteSaver

    path = data_dir() / "checkpoints.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    saver = SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))
    return build_evaluate_graph(deps, checkpointer=saver)


def _cfg(job_id: str) -> dict:
    return {"configurable": {"thread_id": job_id}}


def _report(graph, deps: Deps, job_id: str) -> None:
    job = deps.tracker.get(job_id)
    fit = f" fit {job.fit.score}/10" if job.fit else ""
    print(f"{job_id}: {job.status.value}{fit}")
    if job.fit:
        for gap in job.fit.top_gaps:
            print(f"  gap: {gap}")
    waiting = pending_interrupt(graph, job_id)
    if waiting:
        kind = waiting.get("kind")
        print(f"  waiting on you: {kind} — {waiting.get('reason', '')}".rstrip(" —"))
        if kind == "manual_jd":
            print(
                f"  next: jobs provide-jd {job_id} --file <jd.txt>   ({waiting.get('payload', {}).get('url', '')})"
            )
        elif kind == "resume_review":
            print(
                f"  review {waiting.get('resume_path')}, then: jobs review {job_id} --approve|--reject"
            )


def cmd_evaluate(args, deps):
    graph = _graph(deps)
    if pending_interrupt(graph, args.job_id) and not args.restart:
        print("This job is paused waiting on you (see below). Use --restart to start over.")
    else:
        graph.invoke(fresh_input(args.job_id), _cfg(args.job_id))
    _report(graph, deps, args.job_id)


def cmd_provide_jd(args, deps):
    graph = _graph(deps)
    text = Path(args.file).read_text(encoding="utf-8")
    graph.invoke(Command(resume=text), _cfg(args.job_id))
    _report(graph, deps, args.job_id)


def cmd_review(args, deps):
    graph = _graph(deps)
    graph.invoke(Command(resume={"approved": args.approve, "note": args.note}), _cfg(args.job_id))
    _report(graph, deps, args.job_id)


def cmd_add(args, deps):
    job_id = args.id or deps.tracker.next_id()
    deps.tracker.add(
        Job(id=job_id, company=args.company, title=args.title, url=args.url, source=args.source)
    )
    print(job_id)


def cmd_list(args, deps):
    statuses = {Status(args.status)} if args.status else None
    for job in deps.tracker.list(statuses):
        fit = f"{job.fit.score:>2}" if job.fit else " -"
        print(f"{job.id:10} {job.status.value:18} {fit}  {job.company} — {job.title}")


def cmd_show(args, deps):
    job = deps.tracker.get(args.job_id)
    print(json.dumps(job.model_dump(mode="json", exclude={"jd_text"}), indent=2))
    print("history:")
    for h in deps.tracker.history(args.job_id):
        print(
            f"  {h.at:%Y-%m-%d %H:%M} {h.from_status or '-'} → {h.to_status} ({h.source}) {h.note or ''}"
        )
    waiting = pending_interrupt(_graph(deps), args.job_id)
    if waiting:
        print(f"waiting on: {waiting.get('kind')}")


def cmd_submit(args, deps):
    print(usecases.record_submission(deps.tracker, args.job_id, args.note).status.value)


def cmd_set_status(args, deps):
    print(deps.tracker.transition(args.job_id, Status(args.status), "user", args.note).status.value)


def cmd_auth(args, deps):
    from job_search_core.adapters import google_auth

    google_auth.load_credentials(interactive=True)
    who = google_auth.verify()
    print(f"Signed in. Gmail: {who['gmail']}  Drive: {who['drive']}")


def cmd_demo(args, _deps):
    from .demo import run_demo

    run_demo()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobs", description="Job-search workflow (LangGraph)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo").set_defaults(fn=cmd_demo, needs_deps=False)
    a = sub.add_parser("auth")
    a.add_argument("provider", choices=["google"])
    a.set_defaults(fn=cmd_auth, needs_deps=False)

    a = sub.add_parser("add")
    a.add_argument("--company", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--url")
    a.add_argument("--source")
    a.add_argument("--id", help="use an existing ID, e.g. JS-042 from the Excel tracker")
    a.set_defaults(fn=cmd_add)

    a = sub.add_parser("list")
    a.add_argument("--status", choices=[s.value for s in Status])
    a.set_defaults(fn=cmd_list)

    for name, fn in [("show", cmd_show), ("evaluate", cmd_evaluate)]:
        a = sub.add_parser(name)
        a.add_argument("job_id")
        if name == "evaluate":
            a.add_argument("--restart", action="store_true")
        a.set_defaults(fn=fn)

    a = sub.add_parser("provide-jd")
    a.add_argument("job_id")
    a.add_argument("--file", required=True)
    a.set_defaults(fn=cmd_provide_jd)

    a = sub.add_parser("review")
    a.add_argument("job_id")
    g = a.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true")
    g.add_argument("--reject", dest="approve", action="store_false")
    a.add_argument("--note")
    a.set_defaults(fn=cmd_review)

    a = sub.add_parser("submit")
    a.add_argument("job_id")
    a.add_argument("--note")
    a.set_defaults(fn=cmd_submit)

    a = sub.add_parser("set-status")
    a.add_argument("job_id")
    a.add_argument("status", choices=[s.value for s in Status])
    a.add_argument("--note")
    a.set_defaults(fn=cmd_set_status)
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    deps = real_deps() if getattr(args, "needs_deps", True) else None
    try:
        args.fn(args, deps)
    except (IllegalTransition, usecases.NotEvaluable, KeyError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
