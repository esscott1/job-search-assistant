"""Intake graph: job-alert email in, new Tier 1 leads in the tracker out.

    START → plan → fetch_mail ─(one Send per email)→ read_email ─→ record → END
                       └─────────(no email)──────────────────────↗

`plan` picks the mail window (the last 7 days, or a catch-up). `fetch_mail` searches each of the
profile's Email sources and drops senders that never carry leads (core.policy). `read_email`
is the only model call: one per email, fanned out with `Send`, each returning the email's job
cards with their Tier 1 judgments. `record` is deterministic: canonical links, the Never
interested backstop, dedup against known jobs and the leads already accepted in this run, the
rubric's Tier 1 score, then a new row per lead, oldest email first.

Nodes stay thin: core steps, core policy and core use cases do the work. Running intake again is
safe: anything recorded is a known job on the next run, so it's skipped as a duplicate.
"""

from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, TypedDict

from job_search_core import canonical_url, policy, profile, steps, usecases
from job_search_core.domain import KnownJob, LeadCard
from job_search_core.ports import MailMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .deps import Deps


class IntakeState(TypedDict, total=False):
    today: str  # ISO date the run counts as today (input; defaults to the real date)
    dry_run: bool  # input: report what would be logged, write nothing
    window: str  # Gmail date filter, e.g. "newer_than:7d"
    catch_up: bool
    emails: list[dict]  # MailMessage fields plus "source" (the Email sources label), oldest first
    not_read: list[dict]  # {"sender", "subject", "reason"}
    read: Annotated[list[dict], operator.add]  # {"message_id", "cards": [LeadCard dicts]}
    added: list[dict]  # {"id", "company", "title", "score"}
    skipped: list[dict]  # {"company", "title", "reason"}


def build_intake_graph(deps: Deps, checkpointer=None):
    if deps.mail is None or deps.known is None:
        raise ValueError("intake needs deps.mail and deps.known")

    def plan(state: IntakeState) -> IntakeState:
        today = date.fromisoformat(state.get("today") or date.today().isoformat())
        received = [j.email_received for j in deps.tracker.list() if j.email_received]
        window, catch_up = policy.mail_window(max(received, default=None), today)
        return {"today": today.isoformat(), "window": window, "catch_up": catch_up}

    def fetch_mail(state: IntakeState) -> IntakeState:
        text = deps.profile.read()
        never_scan = profile.never_scan(text)
        emails, not_read, seen = [], [], set()
        for source in profile.email_sources(text):
            for message in deps.mail.search(f"from:{source.sender} {state['window']}"):
                if message.id in seen:
                    continue
                seen.add(message.id)
                if not policy.reads_for_leads(message.sender, never_scan):
                    address = policy.sender_address(message.sender)
                    on_list = address in {s.lower() for s in never_scan}
                    reason = "on Never scan" if on_list else "this sender never has leads"
                    not_read.append(
                        {"sender": message.sender, "subject": message.subject, "reason": reason}
                    )
                    continue
                emails.append({**message.model_dump(mode="json"), "source": source.label})
        emails.sort(key=lambda e: e["received_at"])
        return {"emails": emails, "not_read": not_read}

    def route_emails(state: IntakeState):
        return [Send("read_email", {"email": e}) for e in state["emails"]] or "record"

    def read_email(payload: dict) -> IntakeState:
        message = MailMessage.model_validate(payload["email"])
        cards = steps.read_alert_email(message, deps.profile.read(), deps.llm)
        return {"read": [{"message_id": message.id, "cards": [c.model_dump() for c in cards]}]}

    def record(state: IntakeState) -> IntakeState:
        today = date.fromisoformat(state["today"])
        terms = profile.never_interested(deps.profile.read())
        known = deps.known.known_jobs()
        cards_by_email = {r["message_id"]: r["cards"] for r in state.get("read", [])}
        added, skipped = [], []
        for email in state["emails"]:  # oldest first, so IDs follow the order leads arrived
            message = MailMessage.model_validate(email)
            for raw in cards_by_email.get(message.id, []):
                card = LeadCard.model_validate(raw)
                canonical = canonical_url.canonical(card.posting_url) if card.posting_url else ""
                reason = None
                if not card.keep:
                    reason = card.skip_reason or "off-target"
                elif policy.is_never_interested(card.title, terms):
                    reason = "Never interested"
                elif duplicate := policy.find_duplicate(canonical, card.company, card.title, known):
                    reason = f"already known as {duplicate.id}"
                if reason:
                    skipped.append({"company": card.company, "title": card.title, "reason": reason})
                    continue
                fit = steps.tier1_fit(card)
                job_id = "(dry run)"
                if not state.get("dry_run"):
                    job_id = usecases.record_lead(
                        deps.tracker,
                        card,
                        fit,
                        canonical_url=canonical,
                        source=email["source"],
                        message=message,
                        today=today,
                    ).id
                known.append(
                    KnownJob(
                        id=job_id, company=card.company, title=card.title, canonical_url=canonical
                    )
                )
                added.append(
                    {"id": job_id, "company": card.company, "title": card.title, "score": fit.score}
                )
        return {"added": added, "skipped": skipped}

    builder = StateGraph(IntakeState)
    builder.add_node("plan", plan)
    builder.add_node("fetch_mail", fetch_mail)
    builder.add_node("read_email", read_email)
    builder.add_node("record", record)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "fetch_mail")
    builder.add_conditional_edges("fetch_mail", route_emails, ["read_email", "record"])
    builder.add_edge("read_email", "record")
    builder.add_edge("record", END)
    return builder.compile(checkpointer=checkpointer)
