# Evals: job-search-assistant

Eval cases for this plugin, in the format [`claude plugin eval`](https://code.claude.com/docs) runs. Each case gives Claude a request with the plugin installed, then grades what it did. By default each case also runs **without** the plugin, so the report shows how much the plugin adds (Δ).

All data here is synthetic: the persona is Jane Example, and IDs such as `SHEET_EVAL_0001` are made up. Check any new fixture for real names, email addresses and Drive IDs before committing.

## Running it

From the repository root:

```bash
# one case, one run, no baseline: quick check while editing a skill
claude plugin eval skills/job-search-assistant --case 'tier2-*' --runs 1 --ablation none \
  --trust-plugin --no-publish --output-dir ../eval-runs/$(date +%Y%m%d-%H%M)

# the whole suite with the no-plugin baseline (3 runs per case by default)
claude plugin eval skills/job-search-assistant --trust-plugin --no-publish --output-dir ../eval-runs/full
```

- It runs as you, on your Claude login. No API key is needed locally.
- **Always pass `--output-dir` outside the plugin.** Results written inside `evals/` would ship with the plugin; `skills/*/evals/results/` is gitignored as a backstop.
- `--trust-plugin` skips the first-run prompt. Pass it only for this repo's own plugin.
- `--keep-temp` keeps each run's sandbox and `trace.jsonl` for debugging. On Windows the CLI prints the folder to delete afterwards.
- Rough cost per run, measured on the first cases: $0.10-0.21 with the plugin and about $0.06 without, plus a few cents for LLM graders.

## How a case is put together

```
evals/
  <case>/
    prompt.md              the request, with frontmatter (tags, runs, max_turns, plugins)
    graders/*.md           one check per file
    gstub/                 only for cases that touch Google Drive or Sheets (see below)
  mocks/<server>/<tool>.md canned responses for the stubbed connectors
  fixtures/                the synthetic files the mocks are built from
  test_eval_fixtures.py    keeps mocks, fixtures and stubs consistent (runs in CI, no model calls)
```

**Graders.** Prefer deterministic checks, and use an LLM judge only where judgement is the point:
- `tool_used` with `min`/`max`: a tool was or wasn't called, for example `update_values` `max: 0` for "wrote nothing".
- `regex` on the last message, the trace or a file.
- `llm`: the body states what a good reply does. A judge votes three times and two passes win. Describe the behaviour, not exact wording, because the skill's phrasing varies between runs.
- `tool_used: Skill` with an `input_match` on the skill name shows the skill fired. Under the baseline it's reported as an indicator, not scored.

### Standing in for the Google connectors

The skills use the claude.ai Gmail, Google Drive and Google Sheets connectors, which don't exist in an eval sandbox. A case that needs them ships a tiny stub plugin, `gstub`, which declares MCP servers `gdrive` and `gsheets`. Every tool on those servers is answered from `mocks/`, so the servers never start. The skills name connector tools generically (`get_values`, `search_files`), so they use the stub's tools in their place.

In the case's `prompt.md`:

```yaml
plugins: ["gstub", "../.."]
```

- **A case's `plugins` list replaces the plugin under test**, so it must name both the stub and the plugin itself (`../..`).
- **The stub must sit in the case's own folder.** The CLI refuses a plugin path that covers the case, its graders or its mocks, so each such case carries its own copy. `test_eval_fixtures.py` checks that all copies are identical.
- **Mock tool names in graders** look like `mcp__plugin_gstub_gsheets__update_values`.
- **Mocks are fixed responses.** A case that needs different data puts its own `<case>/mocks/<server>/<tool>.md` next to it, which overrides the shared one.
- **The shared profile mock is the base64 of `fixtures/job-search-profile.md`.** Change both together; the test fails if they differ.

## Cases

| Case | Skill | What it proves |
|---|---|---|
| `resume-no-jd-asks-first` | tailored-resume-builder | Without a job description it asks for one and builds nothing |
| `tier2-nothing-ticked` | job-lead-tier2-scoring | Reads the profile and tracker through the connectors, reports that nothing is ticked, and stops: no resume download, no web search, no writes |
