# How this repo is maintained

Changes are drafted through a chat with Claude, then landed here on their own feature branch and opened as a pull request rather than pushed straight to `main` — same review-before-merge discipline as any other codebase, even though the "codebase" is a set of skill instructions. `main` only moves when a PR is merged. Pull with `git pull` to sync your local clone whenever you want the latest merged state. Merged feature branches are deleted on request ("clean up"), not automatically. [`CLAUDE.md`](CLAUDE.md) describes the procedure Claude follows for that and the rest of this workflow.

## Adding a new skill

1. Pick the category it belongs to under `skills/` (`job-search-assistant`, `ai-governance`) — or propose a new one if it genuinely doesn't fit either. A new category gets its own `README.md`, `plugin.json` and marketplace entry in the same PR as its first skill.
2. Follow the conventions in [`docs/skill-template.md`](docs/skill-template.md) for the SKILL.md itself.
3. Add the skill's folder to the `skills` list in the category's `.claude-plugin/plugin.json` (`"./<skill-name>"`). Then add or update that category's `README.md` table with the new skill, trigger, and dependencies, and its row in [`skills/REGISTRY.md`](skills/REGISTRY.md).
4. If the skill changes what's in the root `README.md`'s category index (a brand-new category, say), update that too.
5. Each category is one plugin. Bump the `version` in the category's `.claude-plugin/plugin.json`: until 1.0.0, a breaking change bumps the minor version and anything else the patch. A new skill starts at `0.1.0`. If this is the category's first skill, create that `plugin.json` (starting at `0.1.0`) and add the category to `.claude-plugin/marketplace.json`.
6. Keep the skill generic: nothing about a particular user (names, IDs, locations, senders) goes in a skill. User settings belong in the user's own configuration.
7. Run `claude plugin validate .` and `claude plugin validate ./skills/<category>`. If the skill ships Python scripts, give them tests next to them (`test_*.py`) and run `python -m pytest -q skills/`. CI runs both checks.
8. Add eval cases for the new behaviour under `skills/<category>/evals/` and run them (see that folder's README).

## Working on `orchestration/`

Python code under `orchestration/job-search/` is a [uv](https://docs.astral.sh/uv/) workspace. Before opening a PR:

```bash
cd orchestration/job-search
uv sync --all-packages
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

CI runs the same checks on every PR that touches `orchestration/job-search/`.

- **Business logic goes in `core/`; orchestration goes in `approaches/<name>/`.** If a graph edge or node starts making a business decision, move that rule into `core/policy.py`. The import-boundary test fails if `core` imports a framework.
- **Changing a prompt?** Bump its `version:` line and run the evals (`uv run python evals/job-fit/run_evals.py`). Commit the updated `results/latest.json` so the PR shows the before and after. The evals workflow re-runs them in CI when the `ANTHROPIC_API_KEY` secret is set.
- **Adding an orchestration approach?** Create `approaches/<name>/` as its own package that depends on `job-search-core`, give it a README stating its maturity (`spike` or `production`), and reuse the existing evals.
- **Never commit personal data.** Resumes, profiles, the tracker database, and OAuth tokens stay in the gitignored `data/` folder.
