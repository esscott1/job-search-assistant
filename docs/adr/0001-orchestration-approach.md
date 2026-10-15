# ADR 0001: Orchestrate the job-search workflow with a LangGraph state graph, behind a framework-free core

- **Status:** Accepted
- **Date:** 2026-10-01

## Context

The job-search workflow has four parts: email intake with a quick screen, full-JD fit scoring with gaps, resume tailoring for strong fits, and status tracking through submission to final outcome. It currently runs as Claude skills on scheduled tasks using managed Gmail and Drive connectors (`skills/job-search-assistant/`).

That version was fast to build, but it fails intermittently on Gmail, Drive, and job-description access. When it fails, the failure lives in a chat transcript rather than in a state anyone can query or resume from. Each fix has been a tweak to skill instructions rather than to the access layer itself.

Two goals shape the decision: (1) a reliable system to run an actual job search, and (2) a public reference implementation demonstrating agent orchestration judgment for AI enablement consulting.

## Options considered

| Option | Fit for this workflow |
|---|---|
| Claude skills + scheduled tasks (current) | Fastest to build, but no control over connector reliability, retries, or state |
| Plain Python pipeline | Workable; the evaluate flow is nearly linear. Pausing for a human and resuming would have to be hand-built |
| **LangGraph state graph** | Conditional routing, checkpointed state per job, `interrupt()` for human steps, resume after failure |
| Orchestrator–worker (agent SDK) | Model-chosen ordering adds cost and unpredictability to a process whose order is known in advance |
| Durable workflow engine (Temporal) | Best durability, but heavy infrastructure for one user |
| Hierarchical, swarm/handoffs, pure event-driven | Built for open-ended or conversational routing, or for decoupled teams; none match this workflow |

## Decision

1. **LangGraph** is the first full orchestration approach. Each job is its own thread (`thread_id = job_id`), so it can pause for a manual JD or a resume review and resume later.
2. **Business logic is in a framework-free `core` package**: domain model, status transitions, policy (the fit threshold and similar rules), steps, prompts, and adapters behind ports. Graph nodes are thin wrappers, and routing calls `core.policy`. A test fails CI if `core` imports any orchestration framework.
3. **Approaches are siblings** under `orchestration/job-search/approaches/`. Adding a second one later (for example, an orchestrator–worker spike) is one new folder that depends on `core`. Nothing moves.
4. **We own the integrations**: Gmail and Drive through our own OAuth client with read-only scopes, HTTP fetches with retries, and LLM calls through the Anthropic SDK with schema-validated output. Failures become explicit states such as `needs_manual_jd`, not errors.
5. **Shadow-mode migration.** The Claude-skills version keeps running as production while the LangGraph version runs alongside it on its own tracker. Each graph is cut over only once its evals and spot checks match.

## Consequences

- **More operational ownership:** token storage, hosting, scheduling and monitoring are ours now. The setup guide documents the Google OAuth "Testing" trap (7-day refresh tokens), because missing it would recreate the original failures.
- **JD access isn't magically fixed.** LinkedIn and some ATS sites still block unattended fetches. The difference is that failure is now a paused job rather than a failed run.
- **Explicit state.** Every job's status and history is queryable, and a crash mid-run resumes rather than repeats.
- **No shared multi-approach contract or comparison harness yet.** That's deliberate: we'll build one once a second full implementation shows what is actually common.
- **Lock-in is confined** to `approaches/langgraph/`. The rules, prompts and integrations are reusable by any future approach.
