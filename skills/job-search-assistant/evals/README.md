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
- A case takes a minute or two per run; a scoring or resume case, which runs scripts, takes longer. Each case's three runs count against your Claude plan's usage.
- **The Google Doc read-back isn't stubbed.** The stub Drive has no `read_file_content`, so resume runs can't check the Doc they created and say it wasn't verified. `check_doc_text.py` is covered by its unit tests instead.
- **The resume style** is `fixtures/resume-style.md`, which the stub Drive serves as the user's `resume-style.md`. Resume cases render a real .docx with `render_resume.py`. `fixtures/Old-Resume.docx` is only there as an older Word resume the skill must never use.
- **Scoring and resume-building cases need a shell, which means Linux or macOS.** They run the rubric's `score.py`, so they need `--allow-tools Bash Write`. The eval runner grants a shell only inside an OS sandbox. On Windows it refuses the run, so use WSL: [`docs/setup/windows-wsl-evals.md`](../../../docs/setup/windows-wsl-evals.md) walks through the one-time setup ([`scripts/setup-wsl-evals.sh`](../../../scripts/setup-wsl-evals.sh) installs bubblewrap, socat, Node, Claude Code, and the resume tools), and [`scripts/run-evals-wsl.sh`](../../../scripts/run-evals-wsl.sh) runs cases from Ubuntu or from Claude Code on Windows. Cases that need no shell run anywhere.

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
- `regex` on the last message, the trace or a file. **Don't write `\\` in a pattern:** the runner reads it as a single backslash, so a pattern like `ok\\?"` silently becomes "the text `ok?"`" and never matches (and a `not_contains` grader then always passes). JSON in the trace has escaped quotes, so step over quotes and escapes with `\W{1,6}`, as in `max_pages\W{1,6}3\b`.
- An `llm` judge sees the final message, not the trace, so it can't check what was written to a file or passed to a script. Check those with `regex` on the trace, or `tool_used` with `input_match`.
- `llm`: the body states what a good reply does. A judge votes three times and two passes win. Describe the behaviour, not exact wording, because the skill's phrasing varies between runs.
- `tool_used: Skill` with an `input_match` on the skill name shows the skill fired. Under the baseline it's reported as an indicator, not scored.

### Standing in for the Google connectors

The skills use the claude.ai Gmail, Google Drive and Google Sheets connectors, which don't exist in an eval sandbox. A case that needs them ships a tiny stub plugin, `gstub`: just a `.mcp.json` declaring MCP servers `gdrive` and `gsheets`, with no `.claude-plugin` manifest, so nothing inside the plugin looks like a second plugin. Every tool on those servers is answered from `mocks/`, so the servers never start. The skills name connector tools generically (`get_values`, `search_files`), so they use the stub's tools in their place.

In the case's `prompt.md`:

```yaml
plugins: ["gstub", "../.."]
```

- **A case's `plugins` list replaces the plugin under test**, so it must name both the stub and the plugin itself (`../..`).
- **The stub must sit in the case's own folder.** The CLI refuses a plugin path that covers the case, its graders or its mocks, so each such case carries its own copy. `test_eval_fixtures.py` checks that all copies are identical.
- **Mock tool names in graders** look like `mcp__plugin_gstub_gsheets__update_values`.
- **Mocks are fixed responses**, built by `build_mocks.py`; never edit them by hand. Drive downloads are served per file id (`{{file:fixtures/{input.fileId}.json}}`, resolved next to the mock), so each fixture file is one Drive file. A case with its own Job Log or Drive gets `<case>/mocks/...`, which overrides the shared mock.
- **Gmail** is a third stub server. A case with an inbox (`fixtures/inbox.json`) gets a Gmail mock played by a small model, which filters the fixture messages by sender and treats every message as within any date limit.
- **Dates in cleanup fixtures are in 2025**, long past any archive age, so the cases stay valid as time passes. `cleanup-honours-archive-age` tests the age rule from the other side, with an archive age no row can reach.
- **Web pages and feeds** come from `fixtures/web/`. A case that reads a page sets `disallowed_tools: [WebFetch, WebSearch]`, and the stub plugin's `web` server answers `fetch` from the fixture (`<case>/mocks/web/fetch.md`, built by `build_mocks.py`): one fixed reply (`"web"` in `CASES`), or a page per URL (`"web_pages"`), played by a small model that returns 404 for any other URL. `read_posting.py` can't reach the fictional `.example` hosts, so it reports `unreachable` and the skills fall back to the stub. The skills say "fetch the URL" without naming a tool, so they use the stub. Nothing is fetched from the network or from this repository, and `test_eval_fixtures.py` checks that.
- **A case that writes to the sheet gets a Sheets mock played by a small model** (`type: agent`), seeded with that case's Job Log. Skills re-find a row before writing and sometimes read it back afterwards, and a fixed mock would return the old row and make a correct run look like a failed write. Don't adopt its recordings into `.replay/`: each run should start from the seeded sheet. Edit the fixtures or the tables at the top of `build_mocks.py`, then run `python build_mocks.py`. The test fails if a mock is stale.

## Scoring cases: a known right answer

A scoring eval only means something if the right answer is fixed in advance. Each scoring case pairs a saved job description (`fixtures/JS-1xx_JD.md`) with the synthetic full resume (`fixtures/Full-Resume.md`). Because the JD is already saved as `<ID>_JD.md`, Tier 2 reads it instead of searching the web, so the input is the same on every run.

- **The gold answer** is a hand-written evidence table in `fixtures/gold/`: every requirement, required or preferred, and how well the resume shows it. `score.py` turns it into the expected score.
- **Graders** check that the score lands within ±1 of gold, and that the clear-cut requirements are judged as gold has them (for example, Kubernetes is `none`, vendor management is `strong`). They also check that `score.py` ran, that no web search happened, and that a fit report was written and the row updated. The ±1 allows for honest judgement calls, such as `partial` vs `none` on Azure when the resume shows AWS.
- **The `tier2-gold-*` JDs are written to be unambiguous.** Each has explicit Required and Preferred sections and requirements the resume either clearly meets or clearly lacks, so a disagreement with gold points to a real change in behaviour.
- **The `tier2-borderline-*` JDs each turn on one judgment call the rubric spells out,** where a careless reading moves the score by more than 1:
  - exactly half the required items met, so calling one `partial` as `none` trips the fewer-than-half cap;
  - a "remote" role that requires living in another time zone, which is `relocation_required`;
  - one unlabelled list, whose hedged items ("familiarity with", "a plus") are preferred.

  Their gold answers follow the rubric's own definitions, and `test_eval_fixtures.py` checks that each gold table passes its case's graders.
- **The `comparison` tag** marks the six first-run scoring cases that `orchestration/job-search/evals/comparison/` also gives to the LangGraph pipeline.
- **When the rubric changes,** the gold scores move. `test_eval_fixtures.py` reruns `score.py` on every gold table and fails if a score falls outside its case's band, which tells you which graders to update in the same PR.
- **The baseline** is in [`BASELINE.md`](BASELINE.md): every case over 3 runs, with the plugin. Run the scoring cases before and after a change to a scoring skill or the rubric, and put both in the PR.

## Cases

| Case | Skill | What it proves |
|---|---|---|
| `cleanup-archives-untouched-rows` | job-tracker-cleanup | Archives exactly the two untouched rows past the archive age, in one batch tied to the sheet's revision, and keeps the five the user acted on (Run Tier 2 or Build Resume ticked, a note, a non-default status, a tailored resume) |
| `cleanup-creates-archive-tab` | job-tracker-cleanup | With no Archive tab, creates it (with an Archived On column) in the same batch |
| `cleanup-honours-archive-age` | job-tracker-cleanup | The profile's Archive after days is beyond every row's age: nothing moves, and it says so |
| `cleanup-restores-a-row` | job-tracker-cleanup | "restore JS-005" moves the archived row back to the Job Log in one revision-checked batch |
| `cleanup-reset-asks-first` | job-tracker-cleanup | "reset my job tracker": says all seven rows would move, five of them ones the user acted on, that nothing is deleted, and asks before writing anything |
| `cleanup-reset-archives-everything` | job-tracker-cleanup | A reset the user has already confirmed: every row, whatever its status, moves to the Archive in one revision-tied batch with Archive Reason `reset` (adding that column to an older Archive); nothing in Drive is touched |
| `intake-logs-new-leads` | job-lead-intake-scan | Needs a shell. Two LinkedIn digests and a Never-scan message: logs Globex and Initech as JS-006 and JS-007 (the Archive holds JS-005), inserted at the top, with canonical links and T1 scores from score.py. Skips the Never-interested retail job, the job already logged under other tracking parameters, the job already in the Archive, and never stores a sign-in token |
| `intake-scans-career-site` | job-lead-intake-scan | Needs a shell and web fetch. A profile with only a career site (method feed): reads the feed, logs the two matching new jobs with Source "Careers: Northwind", and skips the off-target job and the one already in the tracker |
| `intake-banner-is-not-closed` | job-lead-intake-scan | Needs a shell and web fetch. A career site (method page) whose posting pages read as plain text: one shows only a "position has been filled" banner and no description, the other ends "will remain active until the position is filled". Both are open, so both are logged, and neither is reported as closed |
| `intake-nothing-to-scan` | job-lead-intake-scan | No email sources and no career sites: says there's nothing to scan, and writes nothing |
| `intake-after-reset` | job-lead-intake-scan | Needs a shell. The first scan after a reset: an empty Job Log, so the normal 7-day window; a job archived by the reset is logged again as JS-006 onwards, while one archived as stale is still skipped |
| `profile-setup-starts-brief` | job-search-profile | No profile yet. "set up my job search": the first reply is one short question (at most 700 characters) asking which Drive folder to use, with numbered choices, and nothing is written |
| `profile-setup-prefills-from-resume` | job-search-profile | No profile yet, folder and full resume named: reads the resume and offers its name (Jane Example), home area and a prefix as choices, in one short reply |
| `profile-setup-saves-pasted-resume` | job-search-profile | Needs a shell. No profile and no full resume; the user pastes their resume: the roles found are listed, newest first, for confirmation, and nothing is saved yet |
| `profile-setup-checks-style-file` | job-search-profile | Needs a shell. A pasted style file with a bad Bullet line: render_resume.py catches it, the reply names the line and offers fix / another / default, and nothing is saved |
| `profile-update-is-brief` | job-search-profile | "I'd relocate to Austin now": one before → after line for Relocation and a save-or-cancel choice, in at most 500 characters, before anything is written |
| `profile-convert-template` | job-search-profile | Needs a shell. The user attaches a Word template: it's converted with extract_style.py, a preview is rendered with render_resume.py, the look is described (font, accent colour, centred header, 2-column grid), and nothing is saved before the user confirms |
| `profile-style-update` | job-search-profile | "Make my resume's section headings navy": reads resume-style.md, shows only that line before → after with a navy colour, and waits for confirmation before saving |
| `resume-no-jd-asks-first` | tailored-resume-builder | Without a job description it asks for one and builds nothing |
| `resume-tailors-pasted-jd` | tailored-resume-builder | Needs a shell. Builds a resume for a pasted JD with render_resume.py and the user's style file, leading with the JD's supported requirements, employer and dates unchanged, named `<prefix>_<Company>_<Role>.docx`, to the default 3-page limit and checked with `check_content.py`. Saves a Google Doc from HTML text through the connector, hands the .docx and PDF over without uploading a binary, and ends with the gaps |
| `resume-does-not-invent` | tailored-resume-builder | Needs a shell. The JD asks for a Kubernetes certification and Rust, which the resume doesn't show: neither appears in the competencies or highlights, and both are reported as gaps |
| `resume-delivers-to-synced-folder` | tailored-resume-builder | Needs a shell. The profile has a Local Drive folder (Google Drive for desktop): the .docx is written straight into its company folder, a Google Doc is saved from HTML text, and nothing binary goes through the connector |
| `resume-history-rules` | tailored-resume-builder | Needs a shell. A full resume with company descriptions, a single-role employer, a role with only a summary, and two roles that ended over 15 years ago: no company description reaches content.json, `check_content.py` runs and passes, the old but relevant Vendor Contracts Analyst role stays, every role has a line, and an old role left out is reported |
| `resume-honours-requested-page-limit` | tailored-resume-builder | Needs a shell. "Keep this one to a maximum of 2 pages": render_resume.py runs with `--max-pages 2`, never 3, and the summary says so |
| `resume-full-resume-missing` | tailored-resume-builder | The profile's full resume isn't in Drive: it stops and says so, and never falls back to the older Word resume that is there |
| `resume-ticked-row-needs-jd` | tailored-resume-builder | "build ticked resumes" on a row with no saved JD: skips it, leaves Build Resume ticked, says to run Tier 2 first, and doesn't search for the JD |
| `tier2-nothing-ticked` | job-lead-tier2-scoring | Reads the profile and tracker through the connectors, reports that nothing is ticked, and stops: no resume download, no web search, no writes |
| `tier2-gold-strong-fit` | job-lead-tier2-scoring, job-fit-rubric | Remote senior cloud program role the resume covers almost fully. Gold 10 (accept 9-10); PMP is the one gap |
| `tier2-gold-partial-fit` | job-lead-tier2-scoring, job-fit-rubric | Hybrid role in the home city with real gaps (Kubernetes, healthcare) and an AWS-vs-Azure partial. Gold 7 (accept 6-8) |
| `tier2-gold-relocation-mismatch` | job-lead-tier2-scoring, job-fit-rubric | On-site Rust engineering role in another state, with relocation ruled out. Gold 1 (accept 1-3): wrong discipline, relocation required |
| `tier2-rescore-closes-gap` | job-lead-tier2-scoring, job-fit-rubric | The JS-102 row re-ticked after the resume gained a Kubernetes platform. Keeps r1's requirement list, writes r2 with "Changes since r1", score 7 → 8 (accept 7-9) |
| `tier2-borderline-required-half-met` | job-lead-tier2-scoring, job-fit-rubric | Remote finance-systems role. Two required items strong, two partial (7+ years managing people vs about 5; Azure vs AWS), two none: exactly half met, so no cap. Gold 7 (accept 6-8); judging either partial as none drops it to 5 |
| `tier2-borderline-remote-residency` | job-lead-tier2-scoring, job-fit-rubric | A "Remote (US)" role that requires living in the Pacific or Mountain time zone, which the profile's no-relocation rule rules out. The resume covers almost everything (raw 8.5), but it's `relocation_required`. Gold 3 (accept 1-3) |
| `tier2-borderline-unlabelled-list` | job-lead-tier2-scoring, job-fit-rubric | One "What you'll bring" list with no Required or Preferred headings: plain items are required, hedged ones (familiarity with, exposure to, a plus) preferred. The office is "one of our Ohio sites", so the arrangement is `unknown`. Gold 7 (accept 6-8) |
