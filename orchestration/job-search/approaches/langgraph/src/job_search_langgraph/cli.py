"""`jobs` command line: drive the evaluate graph and record what only you know (submissions).

jobs demo                         run all three paths with fakes — no keys needed
jobs auth google [--gmail] [--sign-in]
                                  sign in to Google, approve your tracker, create B's shadow sheet
jobs add --company X --title Y --url Z
jobs list [--status resume_ready]
jobs show JOB_ID                  job, status history, and what the graph is waiting on
jobs evaluate JOB_ID [--restart]  run until done or until it needs you
jobs provide-jd JOB_ID --file jd.txt
jobs review JOB_ID --approve | --reject [--note ...]
jobs submit JOB_ID [--note ...]
jobs set-status JOB_ID STATUS [--note ...]
jobs run intake [--dry-run]       read the profile's job-alert email and log new leads (Tier 1)
jobs run tier2 [--dry-run] [--limit N]
                                  shadow mode: score the jobs the plugin finished Tier 2 on
jobs report agreement [--since DATE] [--markdown PATH]
                                  the shadow week: how far B agrees with the plugin
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from job_search_core import agreement, usecases
from job_search_core.adapters.google_auth import GoogleAuthError
from job_search_core.adapters.google_sheets import TrackerSheetError
from job_search_core.domain import DuplicateJobId, IllegalTransition, Job, Status
from job_search_core.profile import ProfileError
from langgraph.types import Command

from .deps import (
    Deps,
    SettingError,
    data_dir,
    google_dir,
    profile_path,
    real_deps,
    shadow_since,
)
from .evaluate_graph import build_evaluate_graph, fresh_input, pending_interrupt
from .intake_graph import build_intake_graph
from .tier2_graph import build_tier2_graph


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
    tier = f" ({job.scoring_tier})" if job.scoring_tier else ""
    print(f"{job_id}: {job.status.value}{fit}{tier}")
    if job.fit:
        if job.fit.breakdown:
            print(f"  {job.fit.breakdown}")
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
    def make_job(job_id: str) -> Job:
        return Job(
            id=job_id, company=args.company, title=args.title, url=args.url, source=args.source
        )

    job = (
        deps.tracker.add(make_job(args.id))
        if args.id
        else usecases.add_new_job(deps.tracker, make_job)
    )
    print(job.id)


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


def cmd_auth(args, _deps):
    """Sign in, approve access to the tracker the profile names, and create B's shadow (once)."""
    from job_search_core import profile
    from job_search_core.adapters import google_auth, google_picker
    from job_search_core.adapters.google_sheets import (
        SheetAccessError,
        SheetsApi,
        SheetsKnownJobs,
        SheetsSettings,
        create_shadow,
    )

    path = profile_path()
    if not path.exists():
        raise SettingError(f"No job-search profile at {path}: set JOBS_PROFILE (setup, step 4)")
    tracker_id = profile.tracker_sheet_id(path.read_text(encoding="utf-8"))
    if not tracker_id:
        raise SettingError('Profile setting "Tracker → Sheet ID" is blank')

    folder = google_dir()
    needs = google_auth.GMAIL_READONLY if args.gmail else google_auth.DRIVE_FILE
    creds = None
    if not args.sign_in:
        try:
            creds = google_auth.load_credentials(folder, needs=needs)
        except GoogleAuthError:
            pass  # no token yet, or it lacks a scope: sign in below
    if creds is None:
        creds = google_auth.sign_in(folder, gmail=args.gmail)
    gmail = " (with Gmail, for intake)" if needs == google_auth.GMAIL_READONLY else ""
    print(f"Signed in as {google_auth.signed_in_as(creds)}{gmail}")

    sheets = SheetsApi(folder)
    try:
        title = sheets.title(tracker_id)
    except SheetAccessError:  # drive.file: a file is reachable once it has been picked
        google_picker.pick_spreadsheet(
            creds, folder, "Approve access to the job tracker your profile names.", only=tracker_id
        )
        title = sheets.title(tracker_id)
    known = SheetsKnownJobs(sheets, tracker_id).known_jobs()
    print(f"Tracker, as your profile names it: {title} ({len(known)} jobs for dedup)")

    settings = SheetsSettings.load(folder)
    if not settings.shadow_id:
        settings.shadow_id = create_shadow(sheets)
        print("Created B's shadow spreadsheet. B writes only there, never to your tracker.")
    settings.save(folder)
    shadow_url = f"https://docs.google.com/spreadsheets/d/{settings.shadow_id}"
    print(f"Shadow: {sheets.title(settings.shadow_id)}  {shadow_url}")
    print("Set JOBS_TRACKER=sheets in .env to have B keep its jobs there.")


def cmd_run_intake(args, deps):
    result = build_intake_graph(deps).invoke({"dry_run": args.dry_run})
    note = " (catch-up: the newest logged email is over a week old)" if result["catch_up"] else ""
    print(f"Mail window: {result['window']}{note}")
    print(f"Emails read: {len(result['emails'])}")
    for m in result["not_read"]:
        print(f'  not read: {m["sender"]} "{m["subject"]}" ({m["reason"]})')
    verb = "Would add" if args.dry_run else "Added"
    print(f"{verb} {len(result['added'])}:")
    for a in result["added"]:
        print(f"  {a['id']:10} {a['company']} — {a['title']}  (T1 {a['score']})")
    print(f"Skipped {len(result['skipped'])}:")
    for s in result["skipped"]:
        print(f"  {s['company']} — {s['title']}: {s['reason']}")


def cmd_run_tier2(args, deps):
    result = build_tier2_graph(deps).invoke({"dry_run": args.dry_run, "limit": args.limit})
    if args.dry_run:
        print(f"Would score {len(result['due'])}:")
        for d in result["due"]:
            row = d["row"]
            print(f"  {row['id']:10} {row['company']} — {row['title']}  (plugin r{row['fit_run']})")
    else:
        print(f"Scored {len(result['scored'])}:")
        for s in result["scored"]:
            kind = "rescore" if s["rescore"] else "first read"
            print(
                f"  {s['id']:10} {s['company']} — {s['title']}  B {s['score']}, "
                f"plugin {s['plugin_score']} (r{s['run']}, {kind})"
            )
        if result["failed"]:
            print(f"Failed {len(result['failed'])} (tried again next run):")
            for f in result["failed"]:
                print(f"  {f['id']:10} {f['error']}")
    if result["waiting"]:
        print(f"Not scored this run {len(result['waiting'])}:")
        for w in result["waiting"]:
            print(f"  {w['id']:10} {w['reason']}")


def cmd_report_agreement(args, deps):
    since = args.since or shadow_since()
    if since is None:
        raise SettingError("Give --since YYYY-MM-DD, or set JOBS_SHADOW_SINCE in .env")
    report = agreement.shadow_report(
        deps.plugin_jobs.jobs(), deps.tracker.list(), deps.job_files.fit_report, since
    )
    text = agreement.render(report, date.today())
    print(text)
    details = report["details"]
    print("Details (job IDs, for you; not in the Markdown):")
    for name, items in details.items():
        if items:
            more = f" … and {len(items) - 20} more" if len(items) > 20 else ""
            print(f"  {name} ({len(items)}): {', '.join(str(i) for i in items[:20])}{more}")
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(text, encoding="utf-8")
        print(f"Wrote {args.markdown}")


def cmd_demo(args, _deps):
    from .demo import run_demo

    run_demo()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobs", description="Job-search workflow (LangGraph)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo").set_defaults(fn=cmd_demo, needs_deps=False)
    a = sub.add_parser("auth")
    a.add_argument("provider", choices=["google"])
    a.add_argument("--gmail", action="store_true", help="also allow reading Gmail, for intake")
    a.add_argument("--sign-in", action="store_true", help="sign in again, even with a valid token")
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

    run = sub.add_parser("run", help="one pass of a workflow stage, then exit")
    stages = run.add_subparsers(dest="stage", required=True)
    a = stages.add_parser("intake")
    a.add_argument(
        "--dry-run", action="store_true", help="show what would be logged; write nothing"
    )
    a.set_defaults(fn=cmd_run_intake)
    a = stages.add_parser("tier2")
    a.add_argument(
        "--dry-run", action="store_true", help="show what would be scored; call no model"
    )
    a.add_argument("--limit", type=int, help="score at most N jobs this run")
    a.set_defaults(fn=cmd_run_tier2)

    report = sub.add_parser("report", help="measure B against the plugin")
    kinds = report.add_subparsers(dest="kind", required=True)
    a = kinds.add_parser("agreement")
    a.add_argument(
        "--since",
        type=date.fromisoformat,
        help="first day to count (YYYY-MM-DD); default JOBS_SHADOW_SINCE",
    )
    a.add_argument("--markdown", help="also write the counts-only report to this file")
    a.set_defaults(fn=cmd_report_agreement)
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    from googleapiclient.errors import HttpError

    args = build_parser().parse_args(argv)
    try:
        deps = real_deps() if getattr(args, "needs_deps", True) else None
        args.fn(args, deps)
    except (
        IllegalTransition,
        DuplicateJobId,
        GoogleAuthError,
        TrackerSheetError,
        SettingError,
        HttpError,
        ProfileError,
        usecases.NotEvaluable,
        KeyError,
        FileNotFoundError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
