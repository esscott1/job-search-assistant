# Roadmap: one job search, three architectures

This is the north star for the repository: the milestones that turn [the three-approach comparison](architecture/three-approaches.html) from a drawing into something that runs and is measured. [`architecture/roadmap.html`](architecture/roadmap.html) shows the same plan as a picture. **This file is the source of truth**; when a milestone's status or scope changes, update it here and in the picture in the same PR.

## The goal

The same problem (find job leads, score fit against a full resume, show the gaps, tailor a resume) is solved three ways, so the trade-offs between them can be shown with numbers rather than argued:

| | Approach | Who decides the next step | Status |
|---|---|---|---|
| **A** | Claude skills plugin (`skills/job-search-assistant/`) | The model, following SKILL.md steps | Released, 0.4.x |
| **B** | LangGraph pipeline (`orchestration/job-search/approaches/langgraph/`) | Code: a state graph that calls the model only to score and tailor | First milestone: evaluate graph, tested with fakes |
| **C** | Local MCP server (`job-search-local` plugin) | The model picks a tool; code computes the answer | Proposed |

## Principles that hold across every milestone

- **Business rules live once.** The fit rubric, the tracker rules and the routing policy belong to `core` (and the `job-tracker` skill for A). A new approach is a new front end, never a rewrite of the rules.
- **Same inputs, same tests.** Every approach is measured against the same synthetic persona, job descriptions and gold scores.
- **Measure, don't assert.** Claims about token use, accuracy or reliability come with eval results committed to the repo.
- **Each approach stays usable on its own.** A never depends on B or C being installed or running.
- **Public repo hygiene.** Synthetic data only; nothing personal in code, docs, fixtures or results.

## Milestones

The critical path to a measured comparison is **1 → 2 → 3 → 5**. Milestone 4 runs in parallel from the start. 6 and 7 follow 5.

### 1. Foundations ✅ done

- **A:** the plugin is released at 0.4.x with an eval suite covering intake, Tier 2 scoring, resume building, the profile and cleanup ([`evals/BASELINE.md`](../skills/job-search-assistant/evals/BASELINE.md)).
- **B:** `core` (domain, ports, policy, adapters) and the evaluate graph (`fetch_jd → score → tailor → review`), with a CLI, a demo and unit tests on fakes.
- **Decisions:** [ADR 0001](adr/0001-orchestration-approach.md) (why a code-defined orchestration) and [ADR 0002](adr/0002-tracker-is-system-of-record.md) (the tracker is the system of record).

### 2. One rubric · shared core

- **Goal:** both A and B turn an evidence table into a score with the same code.
- **Deliverables:**
  - `core/src/job_search_core/rubric.py`: an exact copy of `job-fit-rubric/score.py`, with a typed `EvidenceTable`;
  - a test that fails if the two copies differ (the skill keeps its own copy, because skills must be self-contained folders);
  - ADR 0003: how the rubric is shared.
- **Done when:** the same evidence table gives the same score and breakdown in both, and CI enforces it. No behaviour change in either approach.

### 3. B scores like A · LangGraph

- **Goal:** B produces an evidence table with the model and scores it with the shared rubric, instead of asking the model for a number.
- **Deliverables:**
  - the graph splits scoring into `assess_fit` (model: evidence table) and `score` (code: rubric);
  - the Anthropic adapter moves from forced `tool_choice` to structured outputs, so it works on current models;
  - the job-search profile (target roles, location) becomes an input, as it is for A;
  - Score Tier names match the tracker's (`T1`, `T2`, `T2-pending-manual`, …);
  - prompt `fit-scoring/2.0`, and the first real job-fit baseline committed (`evals/job-fit/results/latest.json`).
- **Needs:** an Anthropic API key for the evals (decision D1 below).
- **Done when:** `run_evals.py` passes at least 75% of cases against the live model, and the baseline is committed.

### 4. Local MCP server · C (parallel track)

- **Goal:** a small, local, read-mostly MCP server that answers questions across all of a user's job files cheaply and exactly.
- **4a, the probe:** a minimal server that logs what the client sends. It settles whether Claude Code and the desktop app start servers declared by a plugin, and whether they send MCP **Roots**.
- **4b, the server:** a new plugin, `skills/job-search-local/`, that starts `server.py` over stdio from its `.mcp.json`.
  - **Roots** name the job-search folder, with a `JOB_SEARCH_FOLDER` fallback; every path is checked against the roots.
  - **Resources:** the profile, the full resume, the resume style.
  - **Tools:** `find_files(kind, company)`, `get_jd(job_id)`.
  - Unit tests on a temporary folder; checked with the MCP Inspector.
- **4c, the payoff:**
  - `gap_summary(since)` parses every fit report's evidence table in code ("Kubernetes missing in 14 of 22 jobs");
  - a prompt (weekly gap review) and a skill that uses it;
  - one eval case that runs the real server;
  - ADR 0004: why a local server, why read-mostly, why Roots.
- **Done when:** in Claude Code, "what am I most often missing since September?" is answered from the server's counts, and the eval passes. The cloud plugin is unchanged.

### 5. Measured comparison · shared evals

- **Goal:** the comparison page's claims become numbers.
- **Deliverables:**
  - the same synthetic job descriptions and resume run through A's Tier 2 eval cases and B's `assess_fit` + `score`;
  - a results table in the repo, with:
    - score agreement (within ±1);
    - requirement-list overlap (at least 80%);
    - tokens per job;
    - run time;
    - failure modes;
  - the numbers added to [the comparison page](architecture/three-approaches.html).
- **Depends on:** 2 and 3.
- **Done when:** the results are committed and reproducible with one documented command per approach.

### 6. B to parity · LangGraph

- **Goal:** B runs the whole workflow, alongside A, on the same tracker.
- **Deliverables:**
  - an intake graph: Gmail → source parsers → canonical URL and dedup (`canonical_url.py` moved into `core`) → Tier 1 score → rows;
  - a Tier 2 graph whose entry point is the **Run Tier 2** checkbox;
  - a `SheetsTracker` adapter behind `TrackerPort`, so B can read and write the same Google Sheet. Shadow-mode writes go to a separate tab until cut-over, and ADR 0002 is updated;
  - local scheduling;
  - the known fixes (ID collisions in `next_id`, real dependencies built at import in `studio.py`).
- **Depends on:** 5.
- **Done when:** B runs in shadow mode for a week next to A, with an agreement report.

### 7. Packaging for readers · docs

- **Goal:** a reader gets from the problem to the evidence in two minutes.
- **Deliverables:**
  - a README rewrite: problem → the architecture picture → a short demo (A in chat, `jobs demo`, the MCP Inspector) → the results from 5 → the ADRs → what's next;
  - a written case study comparing the approaches.
- **Depends on:** 5 for a first pass, 6 for the final one.

### Later, behind a decision

- **A hosted MCP server.** Drive and Sheets under the `drive.file` scope, with Gmail left on Anthropic's connector, so the server works in claude.ai scheduled runs. This only makes sense if C proves useful; it brings OAuth custody, Google verification and hosting.
- **B's remaining milestones:** a status sweep (closed postings, recruiter replies) and re-tailoring when the full resume changes.

## Open decisions

| # | Decision | Needed by | Current lean |
|---|---|---|---|
| D1 | An Anthropic API key for B's live evals (billed per token, separate from a Claude plan) | 3 | A small prepaid credit and a local `.env` key |
| D2 | B's tracker: SQLite (ADR 0002 today) or the Google Sheet through `SheetsTracker` | 6 | The Sheet, with SQLite kept for tests and the offline demo |
| D3 | Whether the Claude desktop app starts plugin-declared MCP servers and sends Roots | 4b | Settled by the 4a probe; Claude Code is the target either way |
| D4 | Whether to host an MCP server | Later | Not until 4c shows it's worth it |

## Status

| Milestone | Status |
|---|---|
| 1. Foundations | ✅ Done |
| 2. One rubric | Next; planned |
| 3. B scores like A | Planned; needs D1 |
| 4. Local MCP server | Proposed; can start any time |
| 5. Measured comparison | Waiting on 2 and 3 |
| 6. B to parity | Waiting on 5 |
| 7. Packaging | Waiting on 5 |
