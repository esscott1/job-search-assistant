# Approach: LangGraph state graph

**Maturity:** production target (M1: evaluate graph)

Orchestrates the job-search workflow as LangGraph state graphs over `job_search_core`. This package holds only orchestration: graph wiring, the CLI, and dependency selection. Every rule, prompt and integration comes from `core`.

| File | Role |
|---|---|
| `evaluate_graph.py` | fetch JD → score → (tailor → review) or below-threshold; human steps via `interrupt()` |
| `deps.py` | Picks the adapter for each port; the only place real versus fake is decided |
| `cli.py` | The `jobs` command: evaluate, provide-jd, review, submit, list, show, auth |
| `demo.py` | `jobs demo`: all three paths with fakes |
| `studio.py` + `langgraph.json` | Entry point for LangGraph Studio (`langgraph dev`) |

## What LangGraph contributes here

- **Checkpointed threads.** `thread_id = job_id`, persisted to `data/checkpoints.db`. A paused or crashed job resumes where it stopped, even in a new process.
- **`interrupt()` for human steps.** These are the manual JD and the resume review. Interrupt nodes do nothing before the interrupt, because LangGraph re-runs the node on resume; the test `test_missing_jd_pauses_and_resumes_without_refetching` guards this.
- **Conditional edges that call `core.policy`**, so the graph shows where decisions happen without owning them.

## What it deliberately doesn't do

- **Hold the job lifecycle in checkpoints.** The tracker is the system of record ([ADR 0002](../../../../docs/adr/0002-tracker-is-system-of-record.md)).
- **Use LangChain model wrappers.** LLM calls go through `core`'s Anthropic adapter, so `core` stays framework-free.
