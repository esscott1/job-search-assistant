# Roadmap: one job search, three architectures

This is the north star for the repository: the milestones that turn [the three-approach comparison](architecture/three-approaches.html) from a drawing into something that runs and is measured. [`architecture/roadmap.html`](architecture/roadmap.html) shows the same plan as a picture. **This file is the source of truth**; when a milestone's status or scope changes, update it here and in the picture in the same PR.

## The goal

The same problem (find job leads, score fit against a full resume, show the gaps, tailor a resume) is solved three ways, so the trade-offs between them can be shown with numbers rather than argued:

| | Approach | Who decides the next step | Status |
|---|---|---|---|
| **A** | Claude skills plugin (`skills/job-search-assistant/`) | The model, following SKILL.md steps | Released, 0.4.x |
| **B** | LangGraph pipeline (`orchestration/job-search/approaches/langgraph/`) | Code decides the route: a state graph. The model reads, judges and writes inside a step, and, in an agent node (milestone 9), a headless Claude agent decides how to do that one step | Scores like A on the gold cases; intake and the Google Sheet done; reaching parity (milestone 6) |
| **C** | Local MCP server (`job-search-local` plugin) | The model picks a tool; code computes the answer | Proposed |

### What B is, stated precisely

**B is LangGraph orchestration of headless Claude agents, with deterministic control flow.**

- **The graph owns control.** Code decides which step runs next (`core.policy`), holds the run's state and checkpoints, pauses for a person with `interrupt()`, and records every result in the tracker through `core.usecases`.
- **A node is one of three kinds:**
  - a **code step** (fetch a page, dedup a URL, compute the score with the rubric);
  - a **single structured model call**, for judgment that code can check (the evidence table, a tailored resume);
  - an **agent node**, only where the path to the answer can't be known in advance (reading a week of job-alert email, hunting for a job description across sites). The agent is headless Claude, bounded by a tool allowlist, a pinned model, a turn and time limit, and a result that must validate against a schema.
- **B doesn't implement an agent loop of its own.** Agent nodes reuse Anthropic's (headless Claude Code, or the Claude Agent SDK) and the plugin's own skills, so A and B share one copy of each procedure. What B builds is the harness around them: routing, state, human review, guardrails, the system of record and evals.
- **Today** B's nodes are code steps and structured calls; agent nodes arrive in milestone 9.

Why this shape: cost and behaviour stay predictable where they can be (the score is computed in code, and milestone 5 measured one call per job against the plugin's twelve), agency is used only where it earns its place, and the local app (milestone 8) gets one stable backend interface, graphs, instead of driving skills or agents directly.

## Principles that hold across every milestone

- **Business rules live once.** The fit rubric, the tracker rules and the routing policy belong to `core` (and the `job-tracker` skill for A). A new approach is a new front end, never a rewrite of the rules.
- **Same inputs, same tests.** Every approach is measured against the same synthetic persona, job descriptions and gold scores.
- **Measure, don't assert.** Claims about token use, accuracy or reliability come with eval results committed to the repo.
- **Each approach stays usable on its own.** A never depends on B or C being installed or running.
- **Public repo hygiene.** Synthetic data only; nothing personal in code, docs, fixtures or results.
- **Agency only where it earns it.** Judgment that code can check stays a structured call. A step becomes an agent node only when the path to its answer can't be known in advance, and an eval shows it beats the code or manual version.
- **Front ends talk to graphs.** The local app (and any later hosted service) calls the graphs through one API. It never runs a skill or an agent directly, so every action gets the same routing, checkpoints, review steps and tracker rules.

## Milestones

The critical path to a measured comparison was **1 → 2 → 3 → 5**, and it is complete. Milestone 4 runs in parallel from the start. 6 and 7 follow 5. 9, agent nodes, follows 6's shadow week and 6d's cut-over mode; 8, the local app, follows 6 and needs 9b for its **Search for jobs** button. A hosted service is a stretch goal after 8, recorded as a strawman.

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
- **Fixed (2026-10-22): B's fit prompt.** `fit-scoring/2.1` takes requirements only from a JD's qualifications, never its duties, and counts the same kind of tool from another vendor (AWS for Azure) as `partial`. `assess_fit` also asks once more when a job that falls short comes back with no gaps. Rerun of B, 3 runs per case: **18 of 18 exactly on gold**, every requirement list matching gold, no duties listed. B's job-fit evals: 8 of 8 in three runs, after `salesforce-architect`'s band moved from 3–6 to 2–6 (its 3 came from counting the JD's opening duty; the plugin's rubric skill scored the same JD 3, 2, 3, the 2 when it left the duty out).
- **Follow-up for A:** the plugin's rubric text doesn't rule out duties either, and on a JD without headings it counted one in 2 of 3 runs. The same two sentences could go into `job-fit-rubric`, with A's scoring evals rerun.

### 6. B to parity · LangGraph

- **Goal:** B runs the whole workflow, alongside A, on the same tracker.
- **Deliverables:**
  - an intake graph: Gmail → the model reads each email's job cards → canonical URL and dedup (`canonical_url.py` copied into `core`) → Tier 1 score → rows;
  - a Tier 2 graph: in shadow mode it scores the rows A finished Tier 2 on, from A's saved JD; after cut-over its entry point is the **Run Tier 2** checkbox;
  - a `SheetsTracker` adapter behind `TrackerPort`, so B can read A's Google Sheet. During shadow mode B writes to a separate spreadsheet of its own, never to A's tracker, and ADR 0002 is updated;
  - local scheduling (decision D7);
  - the known fixes (ID collisions in `next_id`, real dependencies built at import in `studio.py`).
- **Google access in this milestone** is the developer's own OAuth client (the setup guide's step 3). That's fine for building B and for the shadow week, but it isn't something to ask of every user: reading Gmail needs a restricted scope. Milestone 8 replaces it for users.
- **Depends on:** 5.
- **Done when:** B runs in shadow mode for a week next to A, with an agreement report.
- **Decided (2026-10-22):**
  - B's shadow is a separate spreadsheet it creates, so it only ever needs the `drive.file` scope.
  - In shadow mode B's Tier 2 mirrors A: it scores the rows A finished, from A's saved JD.
  - Intake reads each email with one structured model call; code does the rest.
- **Progress:**
  - **6a, foundations:** job IDs, Studio, the shared dedup key. Done.
  - **6b, intake:** `jobs run intake`, 3 of 3 live runs passing the plugin's intake case. Done; not yet run against a real inbox.
  - **6c, Sheets:** `jobs auth google` signs in with `drive.file` and the Google Picker (milestone 8's sign-in). B reads A's tracker for dedup and keeps its own jobs in a shadow spreadsheet through `SheetsTracker` (ADR 0002, updated). The tracker is named only by the profile's **Tracker → Sheet ID**, as for the plugin: the Picker approves access to that file, and B keeps no copy of its ID. Done.
  - B's fit prompt fixed (`fit-scoring/2.1`, milestone 5).
- **D8 spike (2026-10-23):** under `drive.file`, picking a folder in the Picker grants access to the folder alone. Before and after the pick, B could not open or list the files inside it, at the top level or in a company subfolder, whether `.md` or Google Doc. The plugin saves job files as unconverted Markdown, so Drive for desktop syncs them to disk as ordinary `.md` files.
  - **6d, Tier 2 from the Sheet, in two parts:**
    - **Shadow mode: done.** `jobs run tier2 [--dry-run] [--limit N]` reads A's Job Log (never writing it) and picks each job A scored against the full JD (`T2` or `T2-manual`) whose latest run, the `r<n>` in its Fit Report cell, B hasn't mirrored yet. It reads A's saved `<ID>_JD.md` from the Drive-synced job-search folder on disk, the folder holding the profile `JOBS_PROFILE` points to (decision D8), and scores it with `assess_fit` and the rubric. B's shadow records the result under A's ID, with the run it mirrors, so a rescore by A is mirrored again with the same requirement list. Run live against a real tracker, which B only reads: a dry run listed the jobs due and the ones with no saved JD, one scored job matched A's score, and the next dry run no longer listed it.
    - **Cut-over mode: later, before milestone 9.** The **Run Tier 2** checkbox is the entry point, B fetches the JD itself, and the plugin's rules apply (results first, then Tier 2 Date, untick last; a rescore when `<ID>_JD.md` exists). This is the Tier 2 graph that 9c extends and the app's **Score (Tier 2)** button runs. It will be built and tested on fakes; switching it on in place of the plugin's Tier 2 is a later decision.
- **Next, 6e: the shadow week.** The agreement report (`jobs report agreement`), scheduling (D7), then a week of `jobs run intake` and `jobs run tier2` next to A. It comes before milestone 9 builds on B's graphs.

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
  - **The Google Picker.** The user approves, once, the tracker Sheet their profile names (the profile stays the only place it's named). `drive.file` then covers it, and the files the app creates (B's shadow sheet, JD files, resumes), and nothing else in their Drive. Picking the job folder does not reach the files the plugin saved in it (the D8 spike); how the app reads them is decision D10.
  - **Gmail stays with Claude.** Every Gmail read scope is restricted (a yearly security assessment for a public app), so the app never asks for one. Intake runs on the user's Claude account, through Claude's Gmail connector: the plugin's scheduled intake in claude.ai, or the page's **Search for jobs** button running the plugin's intake skill through headless Claude Code.
- **Spikes (2026-10-22):**
  - **Headless Claude Code:** `claude -p`, on the user's Claude login with no API key, loaded the plugin and used the claude.ai Gmail, Drive and Sheets connectors unattended, with only read tools on its allowlist. The intake skill, as a dry run over a week of alerts, took about 7 minutes. Its scripts need `python` on the allowlist (on Windows it tried `python3` and `py`).
  - **Sign-in and the Picker:** a Desktop client asking only for `openid`, `email` and `drive.file`, with the Picker served from `localhost`, read a picked copy of a tracker and wrote to it (added a tab, wrote a cell, read it back, removed the tab). Before the pick, `drive.file` saw no files. Silent token refresh worked.
  - **Found on the way:** Google's consent screen lets people untick the Drive permission, so the app checks what was granted; and Python has to use the operating system's certificate store (`truststore`) on machines that intercept TLS.
- **Deliverables:**
  - **8a, the app shell:** a small local server (FastAPI) and one page, as a new front end under `approaches/` (its README states its maturity). Sign-in with the shipped client, a check of the granted scopes, `truststore`. Tokens stay in `data/`.
    - **The run API, the page's only backend.** The page calls the graphs through a small HTTP API and never starts a skill, an agent or `claude -p` itself:
      - `POST /runs` starts a graph (`intake`, `tier2`, `evaluate`) for a job or a date range and returns a run ID (the LangGraph thread);
      - `GET /runs/{id}` gives the status and current node, and `GET /runs/{id}/events` streams progress (server-sent events), so a several-minute agent node shows what it's doing;
      - `GET /interrupts` lists the steps waiting on the user (paste a JD, review a resume), and `POST /interrupts/{run_id}` resumes one with the user's answer;
      - `GET /jobs` and `GET /stats` read the tracker and the statistics.
    - Run state lives in LangGraph's checkpoints, job state in the tracker (ADR 0002). The API's OpenAPI schema is committed and the page is written against it, so a later hosted service (the stretch goal) can keep the same contract. Whether this is our own FastAPI layer or LangGraph's server API is decision D12.
    - **Onboarding without `.env`:** the user picks their `job-search-profile.md` in the Picker once, and the app reads it from Drive by that file ID. Today's pipeline needs `JOBS_PROFILE` pointing at a Drive-synced copy, because `drive.file` can't search Drive; the app removes that step. The profile then names the tracker, and the Picker approves it (as `jobs auth google` does now).
  - **8b, tracker and statistics:** the Job Log and Archive through 6c's Sheets adapter; counts by status, score band and Tier 2 backlog; gap statistics computed in `core`, as the same function 4c's `gap_summary` exposes, so the page and the MCP server can't disagree.
  - **8c, actions:** each button starts a graph run through the run API and shows its progress.
    - **Search for jobs:** the intake graph with its agent node (9b), which runs the plugin's intake skill through headless Claude Code on the user's Claude login. Needs Claude Code installed and signed in.
    - **Score (Tier 2):** the Tier 2 graph in cut-over mode (6d); when a JD can't be fetched, the JD agent node (9c) tries before the page asks the user to paste it.
    - **Build resume:** the evaluate graph's tailor step; the review pause shows on the page as a card to approve or reject (decision D6).
  - **8d, publishing:** the OAuth app moves to Production after the brand check, so users see no "unverified app" warning and their sign-in doesn't expire weekly. ADR 0005: why Google access is split this way.
- **B's own Gmail intake (6b)** stays for developers with their own Google project and for the shadow week; app users get intake through Claude instead.
- **Depends on:** 6c (the Sheets adapter), 6d (the Tier 2 graph), 9b (the intake agent node, for **Search for jobs**) and decision D10 (how the app reads the plugin's job files). The statistics code is shared with 4c; whichever comes first builds it in `core`.
- **Done when:** a new user starts the app, signs in with Google, approves the tracker their profile names, sees its status and statistics, scores a job and builds a resume from the page, all without any Google Cloud setup of their own.

### 9. Agent nodes · headless Claude inside B

- **Goal:** where the path to an answer can't be known in advance, a node runs a headless Claude agent, and the graph keeps control of everything around it. This is what makes B an orchestration of agents rather than only a workflow; see [What B is](#what-b-is-stated-precisely).
- **Deliverables:**
  - **9a, the agent port.** An `AgentPort` in `core/ports.py`: `run(task, skill, allowed_tools, model, max_turns, timeout, output_schema) → AgentResult`, where the result holds the validated output, the transcript's path under `data/`, and what was measured (turns, tokens, duration). `core` stays framework-free; the port is plain Python.
    - Adapters: `claude_code_headless` (`claude -p` with a JSON result, the fixed allowlist and a pinned `--model`, on the user's Claude login, as the 2026-10-22 spike ran it) and a fake for tests. A Claude Agent SDK adapter on an API key is decision D11.
    - The result contract: the agent ends with JSON that must validate against `output_schema`. An invalid result gets one retry, then the node returns `NeedsHuman`.
  - **9b, intake as an agent node.** The intake graph's first step runs the plugin's `job-lead-intake-scan` skill in a dry-run mode that returns candidate rows instead of writing them. Code does the rest, as today: canonical-URL dedup in `core`, the Tier 1 score, rows recorded through `core.usecases`. App users get intake through Claude's Gmail connector (decision D5) without B asking for a Gmail scope; 6b's Gmail adapter stays for developers.
  - **9c, JD lookup as an agent node.** When `fetch_jd` can't reach a JD, an agent node searches company and ATS sites (never LinkedIn directly, as the plugin's rule) before the graph pauses for the user to paste it: `fetch_jd → find_jd (agent) → manual_jd (interrupt)`.
  - **9d, evals and ADR.** Agent nodes are measured like milestone 5: the intake node against the plugin's intake case, the JD node against a set of postings that the plugin marked `T2-pending-manual`; success rate, turns, tokens and duration, 3 runs each. ADR 0006: why agent nodes, why headless Claude, and the rules below.
- **Rules every agent node follows:**
  - **The agent never writes the tracker.** It returns a result; the node records it through `core.usecases`, so status changes still go through `tracker.transition()`.
  - **Read-only by default.** Its allowlist has no tool that sends, deletes or writes outside `data/`; email and web pages are untrusted input.
  - **One node is one checkpoint.** LangGraph checkpoints before and after the node, not inside the agent's run, so a failure re-runs the whole agent. Agent nodes must therefore be safe to re-run.
  - **Scoring stays a structured call.** `assess_fit` is not an agent: its path is known, and milestone 5 measured the difference.
- **Depends on:** 6d's cut-over mode (the Tier 2 graph that 9c extends), 6e's shadow week, and the 2026-10-22 headless spike.
- **Done when:** the intake graph with its agent node passes the plugin's intake case in 3 of 3 runs; the JD node finds the JD for most of its eval set and routes the rest to the paste step; graph tests on the fake show an agent failure ending in `NeedsHuman`, never a crash or a tracker write.

### Later, behind a decision

- **A hosted MCP server.** Drive and Sheets under the `drive.file` scope, with Gmail left on Anthropic's connector, so the server works in claude.ai scheduled runs. This only makes sense if C proves useful; it brings OAuth custody, Google verification and hosting.
- **B's remaining milestones:** a status sweep (closed postings, recruiter replies) and re-tailoring when the full resume changes.
- **The same requirements rule for A** (milestone 5's follow-up): two sentences in `job-fit-rubric`, a plugin release, and A's scoring evals rerun.

### Stretch: a hosted service · strawman

A placeholder goal, recorded now so earlier milestones don't close it off, and to be fleshed out after milestone 8. Nothing here is scheduled; whether to build it at all is decision D13.

- **Goal:** the local app's page and run API, hosted for the public on a subscription basis.
- **What carries over:** the run API contract (8a), the graphs, `core`, the evals, and the split of Google access by scope.
- **What has to change, as questions to settle:**
  - **Model access and who pays for it.** Headless Claude Code on a user's own Claude login is a local, personal pattern; a hosted service runs agent nodes on the operator's own API account (the Claude Agent SDK in a sandbox per user, or Anthropic's hosted agents), behind `AgentPort` (D11). The subscription has to cover per-token use, so each user gets a quota and every run is metered. Milestone 9d's tokens per run are the input for sizing it.
  - **Gmail.** A hosted service can't use a user's Claude connector. Options: the restricted Gmail scope with its yearly security assessment; users forward job alerts to an inbound address of their own; or intake stays in the user's Claude (the plugin) and the service reads only the tracker.
  - **Google Drive and Sheets.** A Web OAuth client instead of the Desktop one, Google's verification for a public app, and `drive.file` still as the only Drive scope.
  - **Tenancy and data.** Separate data per user (tracker, checkpoints on Postgres instead of SQLite, job files, transcripts), sign-in, export and deletion, a privacy policy and retention rules: resumes are personal data.
  - **Safety.** Prompt-injection hardening, because job emails and postings are untrusted and the service acts for many users; per-user rate limits.
  - **Running it.** Hosting, a queue for agent runs that take minutes, tracing per call, billing and plans.
  - **Terms.** Anthropic's commercial terms and usage policies for a public product, and Google's API user-data policy.
- **Gate:** D13 is decided after 8 ships, with 9d's measurements in hand.

## Open decisions

| # | Decision | Needed by | Current lean |
|---|---|---|---|
| D1 | An Anthropic API key for B's live evals (billed per token, separate from a Claude plan) | 3 | ✅ Decided: a local `.env` key; not a GitHub secret |
| D2 | B's tracker: SQLite (ADR 0002 today) or the Google Sheet through `SheetsTracker` | 6 | ✅ Decided: the Sheet (B's own shadow spreadsheet), with SQLite kept for tests, the offline demo and as the default until cut-over ([ADR 0002](adr/0002-tracker-is-system-of-record.md)) |
| D3 | Whether the Claude desktop app starts plugin-declared MCP servers and sends Roots | 4b | Settled by the 4a probe; Claude Code is the target either way |
| D4 | Whether to host an MCP server | Later | Not until 4c shows it's worth it |
| D5 | How users give the app Google access without their own Cloud project | 8 | ✅ Decided: one shipped Desktop client with `drive.file` and the Picker; Gmail through Claude's connector |
| D6 | What runs the app's Score and Build resume buttons: B on the user's Anthropic API key, or the plugin through headless Claude Code on their Claude plan | 8c | B's graphs, which milestone 5 measured as far lighter per job. For users without a key, an `LLMPort` adapter that makes B's structured calls through headless Claude Code would keep the graphs and avoid the plugin path; measure it in 9d |
| D7 | How B runs during the shadow week: manual commands (`jobs run intake`, `jobs run tier2`) or a scheduler (Windows Task Scheduler, cron) | 6e | Open |
| D8 | How B reads the job files the plugin saves in Drive (`<ID>_JD.md`, fit reports): `drive.file` reaches only picked or app-created files | 6d | ✅ Decided (2026-10-23 spike): picking the job folder grants the folder, not the files in it, so B reads them from the Drive-synced folder on disk, the folder holding the profile `JOBS_PROFILE` points to. No broader scope |
| D9 | Whether the app's Desktop OAuth client file is committed to the repo (Google treats a Desktop client's secret as not confidential) or fetched at first run | 8a | Open |
| D10 | How the app reads the plugin's job files for users who don't sync Drive to disk: the Picker can't grant them (D8), and `drive.readonly` is restricted | 8 | Open. Options: require Drive for desktop, as B does; or the plugin also writes each JD into the tracker Sheet the user already picks (a JDs tab, as B's shadow keeps), which changes the plugin's contract |
| D11 | What runs B's agent nodes: headless Claude Code on the user's Claude login, or the Claude Agent SDK on an API key | 9a | Headless Claude Code for the local app (the spike works, and users need no key); the Agent SDK for a hosted service. Both behind `AgentPort` |
| D12 | The local app's run API: our own thin FastAPI layer over the graphs, or LangGraph's server API | 8a | Our own layer: the schema stays ours and portable, and `core` and the graphs don't change either way |
| D13 | Whether to build the hosted service (the stretch goal) | After 8 | Strawman only; decide after 8 ships, with 9d's tokens per run and the Gmail question answered |

## Status

| Milestone | Status |
|---|---|
| 1. Foundations | ✅ Done |
| 2. One rubric | ✅ Done ([ADR 0003](adr/0003-shared-rubric.md)) |
| 3. B scores like A | ✅ Done (ADR 0003 update; baseline 8/8 in `evals/job-fit/results/latest.json`) |
| 4. Local MCP server | Proposed; can start any time |
| 5. Measured comparison | ✅ Done, with borderline cases ([results](../orchestration/job-search/evals/comparison/results/RESULTS.md)); B's fit prompt fixed (18/18 on gold); the same rule for A's rubric is a follow-up |
| 6. B to parity | In progress: 6a foundations, 6b intake, 6c Sheets and 6d's shadow mode done; 6e (agreement report, D7, the shadow week) next; 6d's cut-over mode before 9 |
| 7. Packaging | First pass can start; final after 6 |
| 8. Local app | Planned; spikes done; starts after 6d (6c done); needs D10, and 9b for Search for jobs; run API added to 8a |
| 9. Agent nodes | Planned; follows the shadow week (6e) and 6d's cut-over mode; decision D11 |
| Stretch: hosted service | Strawman; decision D13 after 8 |
