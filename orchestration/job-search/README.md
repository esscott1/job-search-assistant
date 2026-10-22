# Job-search orchestration

A working pipeline that runs my own job search, and a worked example of how I'd structure an agentic workflow for a client: business logic in one framework-free package, orchestration in replaceable approaches, evals in CI, and a migration path from the version already in production.

**Setup:** [docs/setup/job-search-langgraph.md](../../docs/setup/job-search-langgraph.md) · **Why it's built this way:** [ADR 0001](../../docs/adr/0001-orchestration-approach.md), [ADR 0002](../../docs/adr/0002-tracker-is-system-of-record.md)

```bash
uv sync --all-packages && uv run jobs demo     # see it work with fakes, no keys needed
```

## What it does

1. **Intake:** find job leads in Gmail and screen them quickly. *(roadmap M2)*
2. **Evaluate:** fetch the full job description; the model fills an evidence table (each requirement judged against the full resume, plus title fit and work arrangement against the job-search profile), and the shared rubric computes the 1–10 score with a readable breakdown ([ADR 0003](../../docs/adr/0003-shared-rubric.md)). Also names up to three gaps.
3. **Tailor:** for scores of 7 or more, draft a tailored resume and pause for my review. Re-tailor unsubmitted resumes when the full resume changes. *(tailor + review: this PR; refresh: M5)*
4. **Track:** follow each job through submission, interviews, and outcome, and notice when postings close. *(manual commands: this PR; automated sweep: M3)*

## Architecture

```mermaid
flowchart LR
    subgraph approaches["approaches/ (orchestration)"]
        LG["langgraph/<br/>graphs · CLI · checkpoints"]
        NEXT["next approach<br/>(future)"]:::future
    end
    subgraph core["core/ — no framework imports"]
        P["policy<br/>threshold · rules"]
        S["steps<br/>fetch_jd · assess_fit · compute_fit · tailor"]
        RB["rubric · scoring<br/>shared with the plugin"]
        U["usecases<br/>record results"]
        D["domain<br/>Status · transitions"]
        PR["prompts<br/>versioned"]
        PORTS["ports"]
    end
    subgraph adapters["core/adapters"]
        T[("SQLite tracker")]
        G["Gmail / Drive<br/>(own OAuth)"]
        H["HTTP JD fetcher"]
        A["Anthropic SDK"]
        F["fakes"]
    end
    LG --> P & S & U
    NEXT -.-> P & S & U
    S --> PR & RB
    S & U --> PORTS
    U --> D
    PORTS --> T & G & H & A & F
    classDef future stroke-dasharray: 4 4
```

**The evaluate graph.** Each job runs on its own checkpointed thread (`thread_id = job_id`). The model never produces the score: `assess_fit` returns judgments only, and `score` computes the number with the rubric, so a checkpoint sits between the paid call and the arithmetic:

```mermaid
flowchart LR
    START((start)) --> load --> fetch_jd
    fetch_jd -- JD found --> assess_fit["assess_fit<br/>model: evidence table"]
    fetch_jd -- can't fetch --> manual_jd{{"⏸ manual_jd<br/>you paste the JD"}}
    manual_jd --> assess_fit
    assess_fit --> score["score<br/>code: shared rubric"]
    score -- "policy.should_tailor" --> tailor --> review{{"⏸ review<br/>approve / reject"}} --> END((end))
    score -- below threshold --> below --> END
```

### Rules the structure enforces

- **`core` never imports an orchestration framework.** [`test_import_boundary.py`](core/tests/test_import_boundary.py) fails CI if it does.
- **Routing decisions live in `core.policy`.** Graph edges only call the rules; they never re-implement them.
- **Status changes go through `tracker.transition()`.** It rejects illegal moves (for example, `below_threshold → submitted`) and records who made each change.
- **Steps that need a person return `NeedsHuman`.** Core doesn't decide how to wait: LangGraph uses `interrupt()`, and another approach can choose its own way.
- **No personal data in the repo.** `data/` is gitignored, and evals use a synthetic candidate.

## Layout

```
orchestration/job-search/
├── core/                       job_search_core — the business logic
│   ├── src/job_search_core/
│   │   ├── domain.py           Job, FitResult, EvidenceTable, RubricScore, Status, transitions
│   │   ├── policy.py           FIT_THRESHOLD, should_tailor, is_resume_stale, ...
│   │   ├── rubric.py           the fit rubric: an exact copy of the plugin's score.py (ADR 0003)
│   │   ├── scoring.py          score_evidence: EvidenceTable → RubricScore via the rubric
│   │   ├── steps.py            fetch_jd, assess_fit (model), compute_fit (rubric), tailor_resume
│   │   ├── profile.py          the job-search profile sections that scoring reads
│   │   ├── usecases.py         record each result in the tracker
│   │   ├── ports.py            interfaces the steps depend on
│   │   ├── prompts/            versioned prompt files
│   │   └── adapters/           sqlite tracker, HTTP fetcher, Anthropic, Gmail, Google auth, fakes
│   └── tests/
├── approaches/
│   └── langgraph/              job_search_langgraph — graphs, CLI (`jobs`), Studio entry
├── evals/job-fit/              synthetic persona (resume + profile), 8 labeled JDs, results/latest.json
├── evals/comparison/          A (plugin) vs B (this pipeline) on the plugin's gold cases; results/RESULTS.md
└── data/                       gitignored: your resume and profile, tracker.db, checkpoints, OAuth token
```

## Roadmap

The repository's north star is [`docs/roadmap.md`](../../docs/roadmap.md), which compares this pipeline with the Claude skills plugin and a local MCP server. Its milestone 3, scoring through the shared rubric, is done, and so is milestone 5, the measured comparison with the plugin ([`evals/comparison/`](evals/comparison/README.md)). The table below is the pipeline's own feature list.

| Milestone | Scope | Status |
|---|---|---|
| M1 | Core + evaluate graph + CLI + evals + CI + setup guide | ✅ this PR |
| M2 | Intake graph (Gmail), read-only import of the Excel tracker, **shadow mode** alongside the Claude skills | next |
| M3 | Status sweep: posting-closed checks, classify recruiter emails (confirmation, interview, rejection) | |
| M4 | `.docx` resume rendering, scheduled runs, per-call LLM tracing | |
| M5 | Refresh graph: re-tailor unsubmitted resumes when the full resume changes | |
| Later | Second approach as a spike (orchestrator–worker) against the same core and evals | |

## Development

```bash
uv sync --all-packages
uv run pytest -q                                  # unit + graph tests, all fakes
uv run ruff check . && uv run ruff format --check .
uv run python evals/job-fit/run_evals.py          # real model; needs ANTHROPIC_API_KEY
uv run python evals/comparison/run_b.py --runs 3  # the comparison: B's side (A's runs in WSL; see its README)
```
