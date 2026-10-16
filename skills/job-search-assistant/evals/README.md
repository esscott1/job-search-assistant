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
- Rough cost per run, measured on the first cases: $0.10-0.21 with the plugin and about $0.06 without, plus a few cents for LLM graders. A scoring case reads more and runs `score.py`, so expect more per run.
- **The resume style** is `fixtures/resume-style.md`, which the stub Drive serves as the user's `resume-style.md`. Resume cases render a real .docx with `render_resume.py`. `fixtures/Old-Resume.docx` is only there as an older Word resume the skill must never use.
- **Scoring and resume-building cases need a shell, which means Linux or macOS.** They run the rubric's `score.py`, so they need `--allow-tools Bash Write`. The eval runner grants a shell only inside an OS sandbox. On Windows it refuses the run, so use WSL: [`scripts/setup-wsl-evals.sh`](../../../scripts/setup-wsl-evals.sh) sets up Ubuntu (bubblewrap, socat, Node, Claude Code, and python-docx, LibreOffice and pdfinfo for the resume cases), and you sign in once. Cases that need no shell run anywhere.

  ```bash
  # the scoring baseline: every case, 3 runs, with the plugin only
  claude plugin eval skills/job-search-assistant --runs 3 --ablation none --allow-tools Bash Write -j 3     --trust-plugin --no-publish --output-dir ~/eval-runs/$(date +%Y%m%d-%H%M)
  ```

## How a case is put together

```
evals/
  <case>/
    prompt.md              the request, with frontmatter (tags, runs, max_turns, plugins)
    graders/*.md           one check per file
    gstub/                 only for cases that touch Google Drive or Sheets (see below)
  mocks/<server>/<tool>.md canned responses for the stubbed connectors
  fixtures/                the synthetic files the mocks are built from
    gold/                  the expected evidence table for each scoring case
  build_mocks.py           builds mocks/ and each case's mocks/ and gstub/ from fixtures/
  test_eval_fixtures.py    checks the mocks are current and the gold answers match the graders (CI, no model calls)
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
- **Mocks are fixed responses**, built by `build_mocks.py`; never edit them by hand. Drive downloads are served per file id (`{{file:fixtures/{input.fileId}.json}}`, resolved next to the mock), so each fixture file is one Drive file. A case with its own Job Log or Drive gets `<case>/mocks/...`, which overrides the shared mock.
- **A case that writes to the sheet gets a Sheets mock played by a small model** (`type: agent`), seeded with that case's Job Log. Skills re-find a row before writing and sometimes read it back afterwards, and a fixed mock would return the old row and make a correct run look like a failed write. The model costs a fraction of a cent per run. Don't adopt its recordings into `.replay/`: each run should start from the seeded sheet. Edit the fixtures or the tables at the top of `build_mocks.py`, then run `python build_mocks.py`. The test fails if a mock is stale.

## Scoring cases: a known right answer

A scoring eval only means something if the right answer is fixed in advance. Each scoring case pairs a saved job description (`fixtures/JS-1xx_JD.md`) with the synthetic full resume (`fixtures/Full-Resume.md`). Because the JD is already saved as `<ID>_JD.md`, Tier 2 reads it instead of searching the web, so the input is the same on every run.

- **The gold answer** is a hand-written evidence table in `fixtures/gold/`: every requirement, required or preferred, and how well the resume shows it. `score.py` turns it into the expected score.
- **Graders** check that the score lands within ±1 of gold, and that the clear-cut requirements are judged as gold has them (for example, Kubernetes is `none`, vendor management is `strong`). They also check that `score.py` ran, that no web search happened, and that a fit report was written and the row updated. The ±1 allows for honest judgement calls, such as `partial` vs `none` on Azure when the resume shows AWS.
- **The JDs are written to be unambiguous.** Each has explicit Required and Preferred sections and requirements the resume either clearly meets or clearly lacks, so a disagreement with gold points to a real change in behaviour.
- **When the rubric changes,** the gold scores move. `test_eval_fixtures.py` reruns `score.py` on every gold table and fails if a score falls outside its case's band, which tells you which graders to update in the same PR.
- **The baseline** is in [`BASELINE.md`](BASELINE.md): every case over 3 runs, with the plugin. Run the scoring cases before and after a change to a scoring skill or the rubric, and put both in the PR.

## Cases

| Case | Skill | What it proves |
|---|---|---|
| `profile-convert-template` | job-search-profile | Needs a shell. The user attaches a Word template: it's converted with extract_style.py, a preview is rendered with render_resume.py, the look is described (font, accent colour, centred header, 2-column grid), and nothing is saved before the user confirms |
| `profile-style-update` | job-search-profile | "Make my resume's section headings navy": reads resume-style.md, shows only that line before → after with a navy colour, and waits for confirmation before saving |
| `resume-no-jd-asks-first` | tailored-resume-builder | Without a job description it asks for one and builds nothing |
| `resume-tailors-pasted-jd` | tailored-resume-builder | Needs a shell. Builds a resume for a pasted JD with render_resume.py and the user's style file, leading with the JD's supported requirements, employer and dates unchanged, named `<prefix>_<Company>_<Role>.docx`. Hands it over without uploading a binary to Drive, and ends with the gaps |
| `resume-does-not-invent` | tailored-resume-builder | Needs a shell. The JD asks for a Kubernetes certification and Rust, which the resume doesn't show: neither appears in the competencies or highlights, and both are reported as gaps |
| `resume-delivers-to-synced-folder` | tailored-resume-builder | Needs a shell. The profile has a Local Drive folder (Google Drive for desktop): the .docx is written straight into its company folder, and nothing binary goes through the connector |
| `resume-full-resume-missing` | tailored-resume-builder | The profile's full resume isn't in Drive: it stops and says so, and never falls back to the older Word resume that is there |
| `resume-ticked-row-needs-jd` | tailored-resume-builder | "build ticked resumes" on a row with no saved JD: skips it, leaves Build Resume ticked, says to run Tier 2 first, and doesn't search for the JD |
| `tier2-nothing-ticked` | job-lead-tier2-scoring | Reads the profile and tracker through the connectors, reports that nothing is ticked, and stops: no resume download, no web search, no writes |
| `tier2-gold-strong-fit` | job-lead-tier2-scoring, job-fit-rubric | Remote senior cloud program role the resume covers almost fully. Gold 10 (accept 9-10); PMP is the one gap |
| `tier2-gold-partial-fit` | job-lead-tier2-scoring, job-fit-rubric | Hybrid role in the home city with real gaps (Kubernetes, healthcare) and an AWS-vs-Azure partial. Gold 7 (accept 6-8) |
| `tier2-gold-relocation-mismatch` | job-lead-tier2-scoring, job-fit-rubric | On-site Rust engineering role in another state, with relocation ruled out. Gold 1 (accept 1-3): wrong discipline, relocation required |
| `tier2-rescore-closes-gap` | job-lead-tier2-scoring, job-fit-rubric | The JS-102 row re-ticked after the resume gained a Kubernetes platform. Keeps r1's requirement list, writes r2 with "Changes since r1", score 7 → 8 (accept 7-9) |
