# CLAUDE.md

Guidance for Claude Code sessions in this repo. Claude reads this file at the start of every session.

## What this repo is

A public Claude plugin marketplace that anyone can install, plus a code-defined version of the same workflow. It has two halves:

- `skills/`: Claude skills (SKILL.md files) grouped by category; each category is one installable plugin.
- `orchestration/job-search/`: the same job-search workflow as an owned, code-defined pipeline (LangGraph). See its README and `docs/adr/`.

Treat everything here as public. Code quality, commit messages and PR descriptions are part of the product.

**Keep everything generic.** Skills, docs, commit messages, PR descriptions and PR comments describe the plugins for any user. Never name or describe a particular person's use of them: their name, inbox, tracker contents, installs, schedules, results or outages. Anything user-specific (names, file and folder IDs, locations, email senders) belongs in that user's own configuration, such as the job-search profile, never in a skill. The only personal names in the repo are authorship credits (`LICENSE`, `author` in `plugin.json`, the marketplace `owner`).

## Git workflow

- **Never commit to `main`.** Make every change on a feature branch (`feat/…`, `fix/…`, `docs/…`, `restructure/…`) and open a pull request. The maintainer reviews and merges; Claude does not merge.
- Keep each PR to one concern. The description says what changed, why, what was verified, and what wasn't.
- **"Clean up"** means: for each remote branch other than `main`:
  1. Confirm its PR is **merged**.
  2. Confirm the branch has **no commits missing from `main`**, for example with `git log origin/main..origin/<branch>` returning nothing.
  3. Delete the branch on the remote (`git push origin --delete <branch>`) and locally, then `git fetch --prune`.

  List what will be deleted before deleting it. Never delete `main`, an unmerged branch, or a branch whose PR is still open. Do this only when the maintainer asks to clean up. Automatic deletion on merge is deliberately **off** for this repo.
- If the session can't delete branches (cloud sessions push only to their own branch), do the checks anyway and give the maintainer the exact command to run.

## Skills (`skills/`)

- Follow `docs/skill-template.md`. Front-load the `description` with when the skill runs (scheduled, on demand, needs the computer).
- When you add or change a skill, update that category's `README.md` table and its row in `skills/REGISTRY.md` (version, stage, last change). Sally's SKILL.md defines the registry columns.
- **The repo is a plugin marketplace.** `.claude-plugin/marketplace.json` at the root lists one plugin per category, and each category folder with skills has `.claude-plugin/plugin.json`. Its `skills` key lists each skill folder (`"./<skill>"`), not `"./"`, so the category's `evals/` folder isn't loaded as part of the plugin; a new skill is added to that list in the same PR, and `skills/test_manifests.py` fails if one is missing. Keep the entry `name` in `marketplace.json` identical to the `name` in that `plugin.json`.
- **A category with no skills stays out of `marketplace.json`.** When its first skill lands, add its `plugin.json` and its marketplace entry in the same PR.
- **Bump the plugin's `version`** in its `plugin.json` whenever a skill in it changes. Installed copies stay on the old version until it changes.
- **Versions stay below 1.0.0 during active development.** A change that breaks existing users (a changed trigger, a changed input or output another skill depends on, a new required setting) bumps the **minor** version; anything else bumps the **patch**. Never bump the major version; 1.0.0 is reserved for the first release meant for general use. New skills and new category plugins start at `0.1.0`. Sally's SKILL.md has the full rule.
- **Evals** live in `skills/<category>/evals/`, in the format `claude plugin eval` runs; see `skills/job-search-assistant/evals/README.md`. When a change alters what a skill does, run its cases locally (they use your own Claude login, no API key) with `--output-dir` outside the plugin, and quote the result in the PR. CI doesn't run them yet.
- Run `claude plugin validate .` and `claude plugin validate ./skills/<category>` before opening a PR that touches `skills/` or `.claude-plugin/`. If a skill's Python scripts changed, also run `python -m pytest -q skills/`. CI runs the same checks.
- **Editing a SKILL.md here does not update an installed skill** in anyone's Claude account. Installing is a separate step in the Claude app. Say so in the PR when a change needs reinstalling. The repo and the installed skills can drift, so check before assuming they match.

## Orchestration (`orchestration/job-search/`)

This is a uv workspace with one framework-free package (`core/`) and one package per orchestration approach (`approaches/<name>/`).

- **Business logic goes in `core`; orchestration goes in `approaches/`.** `core` must never import LangGraph, LangChain, or any other orchestration framework; `core/tests/test_import_boundary.py` enforces this.
- **Routing decisions are business rules.** They live in `core/policy.py`. Graph edges call them and never re-implement them.
- **Status changes only go through `tracker.transition()`**, which enforces `domain.TRANSITIONS`. Don't bypass it.
- **Nodes stay thin:** call a `core` step, record the result with a `core.usecases` function, return a small state update. A node that calls `interrupt()` does nothing with side effects before the interrupt, because LangGraph re-runs the node on resume.
- **A new orchestration approach** is a new folder under `approaches/` that depends on `job-search-core`, with a README stating its maturity (`spike` or `production`). Nothing in `core` should need to move.
- **Changing a prompt** (`core/src/job_search_core/prompts/`): bump its `version:` line, run the evals, and commit `evals/job-fit/results/latest.json` so the PR shows the effect.

Before opening a PR that touches this folder:

```bash
cd orchestration/job-search
uv sync --all-packages
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

Use the same commands CI does. Tests use fakes only, so they need no keys or network.

## Personal data: never commit it

A user's job-search profile, real resume, tracker contents, the tracker database, LangGraph checkpoints, OAuth credentials and tokens, and `.env` all stay in the gitignored `data/` folder or in `.env`. Evals and demos use the synthetic persona in `evals/job-fit/`. Before committing, check that `git status` shows nothing under any `data/` folder except `data/README.md`.

## Where things run

- **Local (VS Code / terminal):** building and testing the pipeline, `jobs auth google` (opens a browser), real evaluations against `data/`, LangGraph Studio, and all git operations.
- **Claude app:** the currently scheduled skills and their Gmail/Drive connectors, and installing the plugins into an account.

The setup guide is `docs/setup/job-search-langgraph.md`.
