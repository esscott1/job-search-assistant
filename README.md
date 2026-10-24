# job-search-assistant

Claude plugins for a human-in-the-loop job search, plus the same workflow built as an owned LangGraph pipeline with evals and CI. The skills do the repetitive work (reading job-alert email, screening, scoring against your full resume, building tailored resumes), and checkboxes in a Google Sheet decide where the costly work goes.

> **JobSearchAssistant: a Claude plugin.** The job-search skills install together as one plugin that finds job leads in your job-alert email and on the company career sites you choose, screens them against your target roles and location, logs them to a tracker sheet, scores the ones you pick against your full resume, and builds tailored resumes on request. **New here? Follow [Getting started](docs/getting-started.md)**: install, a 20-minute setup, and the daily routine.

## Categories

| Category | What it's for |
|---|---|
| [`skills/job-search-assistant/`](skills/job-search-assistant/README.md) | JobSearchAssistant: job-lead intake from email, tiered fit scoring, gap reports, tailored resumes, and tracker housekeeping, all driven by a per-user profile |
| [`skills/ai-governance/`](skills/ai-governance/README.md) | Lifecycle management for the skills themselves: landing every change as a reviewed PR, and a read-only status and drift report |

Each category has its own README with its skills, their triggers, and dependencies. New categories are added when their first skill lands.

## Install as a plugin

This repo is a Claude plugin marketplace ([`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)). Each category that has skills is one installable plugin.

- **claude.ai or the desktop app:** Customize > Plugins, add `esscott1/job-search-assistant` as a marketplace, then install a plugin from it.
- **Claude Code:** `claude plugin marketplace add esscott1/job-search-assistant`, then `claude plugin install job-search-assistant@esscott`.

| Plugin | What it is | Skills |
|---|---|---|
| `job-search-assistant` | A job-search assistant driven by your own profile: email intake, fit scoring, gap reports, tailored resumes | `job-search-profile`, `job-lead-intake-scan`, `job-lead-tier2-scoring`, `job-lead-manual-jd-lookup`, `job-fit-rubric`, `job-tracker`, `job-tracker-cleanup`, `tailored-resume-builder` |
| `ai-governance` | Sally, the lifecycle manager that lands every skill change as a reviewed PR, and her read-only status and drift report | `sally`, `sally-audit` |

The job-search plugin needs the Gmail, Google Drive and Google Sheets connectors. Your settings live in `job-search-profile.md` in your own Google Drive, never in the plugin.

## Orchestration: the same workflow, owned end to end

Skills are one way to run a workflow. [`orchestration/`](orchestration/job-search/README.md) holds the other: code-defined pipelines that own their integrations, state and failure handling.

| Path | What it is |
|---|---|
| [`orchestration/job-search/`](orchestration/job-search/README.md) | The job-search workflow as a LangGraph state graph. Business logic lives in a framework-free `core` package, and each orchestration approach is a sibling under `approaches/` |
| [`docs/adr/`](docs/adr/) | Architecture decision records: why LangGraph here, why the tracker is the system of record |
| [`docs/roadmap.md`](docs/roadmap.md) | The north star: milestones that turn the skills plugin, the LangGraph pipeline and a local MCP server into three measured approaches to the same problem (pictured in [`docs/architecture/`](docs/architecture/)) |
| [`docs/setup/`](docs/setup/job-search-langgraph.md) | Setup guide, including Google OAuth for a personal account |

The skills version can keep running while the orchestrated version runs alongside it in shadow mode. Each part is cut over once its evals match ([ADR 0001](docs/adr/0001-orchestration-approach.md)).

### What the pipeline is, stated precisely

**LangGraph orchestration of headless Claude agents, with deterministic control flow.** Code decides which step runs next, holds the state and checkpoints, pauses for a person to paste a job description or review a resume, and records every result in the tracker. Each step is a code step, a single structured model call, or, only where the path can't be known in advance, a headless Claude agent with a tool allowlist, a pinned model and a result that must validate against a schema.

To be exact about what is built here and what is reused:

- **Built here:** the harness around the model. Routing rules in a framework-free `core`, checkpointed and resumable runs, human-in-the-loop steps, structured-output validation, a model adapter behind an interface, guardrails, the tracker as system of record, and evals in CI, including a measured comparison with the skills plugin.
- **Reused:** the agent loop. Agent steps run Anthropic's (headless Claude Code or the Claude Agent SDK) and the plugin's own skills. The pipeline doesn't implement an agent loop of its own.
- **Today:** the steps are code and structured calls; agent steps are [roadmap milestone 9](docs/roadmap.md#9-agent-nodes--headless-claude-inside-b). The fit score is never agentic: the model fills an evidence table and code computes the score.

## Conventions

Every SKILL.md here follows a common shape, documented in [`docs/skill-template.md`](docs/skill-template.md), so skills stay easy to compare across categories as the list grows.

## Status

In active development and below 1.0.0: until then, a breaking change bumps the minor version and anything else the patch. 1.0.0 will be the first release meant for general use.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how this repo is maintained (branch + PR workflow) and how to add a new skill.

## License

[MIT](LICENSE). Personal data (profiles, resumes, tracker contents, tokens) is never part of this repo; see [`CLAUDE.md`](CLAUDE.md).
