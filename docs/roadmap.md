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

The critical path to a measured comparison was **1 → 2 → 3 → 5**, and it is complete. Milestone 4 runs in parallel from the start. 6 and 7 follow 5, and 8, the local app, follows 6.

### 1. Foundations ✅ done

- **A:** the plugin is released at 0.4.x with an eval suite covering intake, Tier 2 scoring, resume building, the profile and cleanup ([`evals/BASELINE.md`](../skills/job-search-assistant/evals/BASELINE.md)).
- **B:** `core` (domain, ports, policy, adapters) and the evaluate graph (`fetch_jd → score → tailor → review`), with a CLI, a demo and unit tests on fakes.
- **Decisions:** [ADR 0001](adr/0001-orchestration-approach.md) (why a code-defined orchestration) and [ADR 0002](adr/0002-tracker-is-system-of-record.md) (the tracker is the system of record).

### 2. One rubric · shared core ✅ done

- **Goal:** both A and B turn an evidence table into a score with the same code.
- **Deliverables:**
  - `core/src/job_search_core/rubric.py`: an exact copy of `job-fit-rubric/score.py`, with a typed `EvidenceTable`;
  - a test that fails if the two copies differ (the skill keeps its own copy, because skills must be self-contained folders);
  - [ADR 0003](adr/0003-shared-rubric.md): how the rubric is shared.
- **Done when:** the same evidence table gives the same score and breakdown in both, and CI enforces it. No behaviour change in either approach.

### 3. B scores like A · LangGraph ✅ done

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

### 5. Measured comparison · shared evals ✅ done

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
- **Result (2026-10-21):** [`orchestration/job-search/evals/comparison/`](../orchestration/job-search/evals/comparison/README.md), on the plugin's three gold Tier 2 cases, both on `claude-sonnet-5-5`, 3 runs each:
  - every run of both approaches matched the gold score, the gold requirement list and every evidence call;
  - the difference is the work around the judgment: A's whole run used a median of 12 model calls and about 436,000 tokens (about 90% of them cache reads) in 79 seconds; B's scoring call used 1 call and about 4,000 tokens in 5 seconds;
  - no failures in either.
- **Borderline cases (2026-10-22):** three more gold cases, each turning on one judgment call the rubric spells out (exactly half the required items met, a "remote" role that requires moving, an unlabelled list of qualifications). Over all six cases, 3 runs each:
  - A was within ±1 of gold in 18 of 18 runs;
  - B was within ±1 in 16 of 18. Both misses were on the half-met case: B called a comparable tool `none` and counted JD duties as requirements, which tripped the fewer-than-half cap (7 → 5).
- **Follow-up:** B's fit prompt (`fit-scoring/2.0`) lists Responsibilities lines as requirements in about a third of runs. A prompt change, rerun against these cases.

### 6. B to parity · LangGraph

- **Goal:** B runs the whole workflow, alongside A, on the same tracker.
- **Deliverables:**
  - an intake graph: Gmail → the model reads each email's job cards → canonical URL and dedup (`canonical_url.py` copied into `core`) → Tier 1 score → rows;
  - a Tier 2 graph whose entry point is the **Run Tier 2** checkbox;
  - a `SheetsTracker` adapter behind `TrackerPort`, so B can read A's Google Sheet. During shadow mode B writes to a separate spreadsheet of its own, never to A's tracker, and ADR 0002 is updated;
  - local scheduling;
  - the known fixes (ID collisions in `next_id`, real dependencies built at import in `studio.py`).
- **Google access in this milestone** is the developer's own OAuth client (the setup guide's step 3). That's fine for building B and for the shadow week, but it isn't something to ask of every user: reading Gmail needs a restricted scope. Milestone 8 replaces it for users.
- **Depends on:** 5.
- **Done when:** B runs in shadow mode for a week next to A, with an agreement report.
- **Decided (2026-10-22):**
  - B's shadow is a separate spreadsheet it creates, so it only ever needs the `drive.file` scope.
  - In shadow mode B's Tier 2 mirrors A: it scores the rows A finished, from A's saved JD.
  - Intake reads each email with one structured model call; code does the rest.
- **Progress:** the foundations (job IDs, Studio, the shared dedup key) and the intake graph (`jobs run intake`, 3 of 3 live runs passing the plugin's intake case) are done. Next: reading A's Sheet and writing the shadow, then Tier 2 from the Sheet, then scheduling and the agreement report.

### 7. Packaging for readers · docs

- **Goal:** a reader gets from the problem to the evidence in two minutes.
- **Deliverables:**
  - a README rewrite: problem → the architecture picture → a short demo (A in chat, `jobs demo`, the MCP Inspector) → the results from 5 → the ADRs → what's next;
  - a written case study comparing the approaches.
- **Depends on:** 5 for a first pass, 6 for the final one.

### 8. Local app · a desktop UI over B

- **Goal:** a web page that runs on the user's own computer (at `localhost`) and is one place to see and run the job search: tracker status, the actions (search for jobs, Tier 2 scoring, a tailored resume) and statistics. No user creates a Google Cloud project.
- **Google access, split by what each scope costs:**
  - **One OAuth client, shipped with the repo.** The maintainer registers one Desktop client; users click **Sign in with Google**. It asks only for `openid`, `email` and `drive.file`. `drive.file` is non-sensitive, so publishing the app needs Google's brand check, not the security assessment that a Gmail scope needs.
  - **The Google Picker.** The user picks their tracker Sheet and job folder once. `drive.file` then covers those, and the files the app creates (B's shadow sheet, JD files, resumes), and nothing else in their Drive.
  - **Gmail stays with Claude.** Every Gmail read scope is restricted (a yearly security assessment for a public app), so the app never asks for one. Intake runs on the user's Claude account, through Claude's Gmail connector: the plugin's scheduled intake in claude.ai, or the page's **Search for jobs** button running the plugin's intake skill through headless Claude Code.
- **Spikes (2026-10-22):**
  - **Headless Claude Code:** `claude -p`, on the user's Claude login with no API key, loaded the plugin and used the claude.ai Gmail, Drive and Sheets connectors unattended, with only read tools on its allowlist. The intake skill, as a dry run over a week of alerts, took about 7 minutes. Its scripts need `python` on the allowlist (on Windows it tried `python3` and `py`).
  - **Sign-in and the Picker:** a Desktop client asking only for `openid`, `email` and `drive.file`, with the Picker served from `localhost`, read a picked copy of a tracker and wrote to it (added a tab, wrote a cell, read it back, removed the tab). Before the pick, `drive.file` saw no files. Silent token refresh worked.
  - **Found on the way:** Google's consent screen lets people untick the Drive permission, so the app checks what was granted; and Python has to use the operating system's certificate store (`truststore`) on machines that intercept TLS.
- **Deliverables:**
  - **8a, the app shell:** a small local server (FastAPI) and one page, as a new front end under `approaches/` (its README states its maturity). Sign-in with the shipped client, the Picker, a check of the granted scopes, `truststore`. Tokens stay in `data/`.
  - **8b, tracker and statistics:** the Job Log and Archive through 6c's Sheets adapter; counts by status, score band and Tier 2 backlog; gap statistics computed in `core`, as the same function 4c's `gap_summary` exposes, so the page and the MCP server can't disagree.
  - **8c, actions:** each button starts a background job and shows its progress.
    - **Search for jobs:** the plugin's intake skill through headless Claude Code, with a fixed tool allowlist. Needs Claude Code installed and signed in.
    - **Score (Tier 2)** and **Build resume:** B's graphs (decision D6).
  - **8d, publishing:** the OAuth app moves to Production after the brand check, so users see no "unverified app" warning and their sign-in doesn't expire weekly. ADR 0005: why Google access is split this way.
- **Depends on:** 6c (the Sheets adapter) and 6d (the Tier 2 graph). The statistics code is shared with 4c; whichever comes first builds it in `core`.
- **Done when:** a new user starts the app, signs in with Google, picks their tracker, sees its status and statistics, scores a job and builds a resume from the page, all without any Google Cloud setup of their own.

### Later, behind a decision

- **A hosted MCP server.** Drive and Sheets under the `drive.file` scope, with Gmail left on Anthropic's connector, so the server works in claude.ai scheduled runs. This only makes sense if C proves useful; it brings OAuth custody, Google verification and hosting.
- **B's remaining milestones:** a status sweep (closed postings, recruiter replies) and re-tailoring when the full resume changes.

## Open decisions

| # | Decision | Needed by | Current lean |
|---|---|---|---|
| D1 | An Anthropic API key for B's live evals (billed per token, separate from a Claude plan) | 3 | ✅ Decided: a local `.env` key; not a GitHub secret |
| D2 | B's tracker: SQLite (ADR 0002 today) or the Google Sheet through `SheetsTracker` | 6 | The Sheet, with SQLite kept for tests and the offline demo |
| D3 | Whether the Claude desktop app starts plugin-declared MCP servers and sends Roots | 4b | Settled by the 4a probe; Claude Code is the target either way |
| D4 | Whether to host an MCP server | Later | Not until 4c shows it's worth it |
| D5 | How users give the app Google access without their own Cloud project | 8 | ✅ Decided: one shipped Desktop client with `drive.file` and the Picker; Gmail through Claude's connector |
| D6 | What runs the app's Score and Build resume buttons: B on the user's Anthropic API key, or the plugin through headless Claude Code on their Claude plan | 8c | B, which milestone 5 measured as far lighter per job; the plugin path for users without a key |

## Status

| Milestone | Status |
|---|---|
| 1. Foundations | ✅ Done |
| 2. One rubric | ✅ Done ([ADR 0003](adr/0003-shared-rubric.md)) |
| 3. B scores like A | ✅ Done (ADR 0003 update; baseline 8/8 in `evals/job-fit/results/latest.json`) |
| 4. Local MCP server | Proposed; can start any time |
| 5. Measured comparison | ✅ Done, with borderline cases ([results](../orchestration/job-search/evals/comparison/results/RESULTS.md)); B's fit prompt follow-up open |
| 6. B to parity | In progress: foundations and intake done; Sheets next |
| 7. Packaging | First pass can start; final after 6 |
| 8. Local app | Planned; spikes done; starts after 6c and 6d |
