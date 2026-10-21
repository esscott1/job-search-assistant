# Measured comparison: A (plugin) and B (LangGraph pipeline)

Roadmap milestone 5. Both approaches score a job the same way: the model fills an evidence table, and the same rubric code (`score.py`, copied to `core/rubric.py`) turns it into a score. This folder measures what's left to differ (the model's judgment and the work around it) on the same inputs and the same model, and commits the numbers.

**The results are in [`results/RESULTS.md`](results/RESULTS.md).**

## What's compared

- **The cases** (`cases.json`) are the plugin's three Tier 2 gold eval cases: JS-101 (strong fit), JS-102 (partial fit) and JS-103 (relocation mismatch). Each has a saved JD and a **hand-written gold evidence table** (`skills/job-search-assistant/evals/fixtures/gold/`). Both approaches get the same JD, the same synthetic full resume and the same synthetic job-search profile, read from the plugin's fixtures (nothing is copied).
- **A** runs as a user would trigger it: `claude plugin eval` gives Claude "run Tier 2 now" with the plugin installed and the Google connectors stubbed. The skill reads the profile, the tracker and the resume, judges the evidence, runs `score.py`, writes a fit report and updates the row.
- **B** calls the steps the evaluate graph uses, `assess_fit` (the model) then `compute_fit` (the rubric), with the JD, resume and profile passed in.
- **Scoring only.** A finds the saved JD in Drive, so it doesn't search the web, and B is given the JD; fetching isn't measured. Neither is rescoring or tailoring.
- **The same model.** Both run on `JOBS_MODEL`, or `claude-sonnet-5-5` by default. A gets it through `--model`; `extract_a.py` records the models seen in each trace, so a mismatch shows.

## Running it

From `orchestration/job-search`:

```bash
uv run python evals/comparison/run_b.py --runs 3                 # B: needs ANTHROPIC_API_KEY (.env)
wsl -d Ubuntu -- bash /mnt/c/<repo>/orchestration/job-search/evals/comparison/run_a.sh --runs 3
uv run python evals/comparison/compare.py                        # no model calls
```

- **`run_b.py`** writes `results/b.json`. `--fake` checks the harness with no key and writes nothing.
- **`run_a.sh`** needs a shell for `score.py`, so Linux, macOS or WSL ([setup](../../../../docs/setup/windows-wsl-evals.md)). It runs the eval with each run's trace kept (`--keep-temp`), then `extract_a.py` reads the traces and writes `results/a.json`, then it deletes the kept sandboxes. Raw output and copies of the traces stay in `~/eval-runs/comparison-*`, outside the repository. The extraction has to happen in the same session as the eval, because WSL clears `/tmp` when the distro stops.
- **`compare.py`** reads both files and the gold tables and writes `results/comparison.json` and `results/RESULTS.md`. It's deterministic: rerun it on the committed JSON and the output doesn't change.

Usage: three runs per case is 9 plugin eval runs (a few minutes at `-j 3`, on your Claude plan) and 9 API calls for B (on the API key).

## What's measured

| Measure | How |
|---|---|
| **Score agreement** | Each run's score against the gold table's score (within ±1, and exact), and every A run against every B run on the same case (within ±1). |
| **Requirement overlap** | The requirements in two tables are matched one-to-one (below). Overlap is matched ÷ the longer list. For matched pairs, how often the evidence call (strong, partial, none) agrees. Reported A–gold, B–gold and A–B. |
| **Model work per job** | Median tokens per scored job: new input, cache writes, cache reads and output. A's come from the trace's final `result` event and cover its **whole run**: loading the skills, reading the profile, tracker and resume, writing the fit report and the row. B's come from the adapter's per-request log and cover **only the scoring call**. That difference is the finding, not a flaw in it. |
| **Time** | Median seconds per job. A's is the eval run's duration, which includes the small model that plays the Google Sheets stand-in. |
| **Failure modes** | Per run. A: run errors, no fit report, `score.py` not run or exiting with an error, any web search. B: answers that didn't validate, refusals, exceptions. |

**Tokens, never prices.** The eval runner and the trace both carry cost estimates. `extract_a.py` copies named fields only, and a test checks that no cost field reaches its output. The repository's rule is in `CLAUDE.md`.

### Matching requirements

Two tables word the same requirement differently ("Experience leading migrations to Microsoft Azure" and "Azure migration leadership"). `compare.py` matches them by text, with no model, so the measurement adds no judgment of its own:

1. Each text is reduced to its significant words: lowercased, punctuation dropped, filler words removed ("experience", "years", "certification", "strong", …), a trailing plural *s* removed.
2. Two texts' similarity is the Dice coefficient of those word sets: 1 for the same words, 0 for none in common.
3. Pairs are taken best first, one-to-one, down to a threshold of 0.5.

The threshold is calibrated on the gold tables: a test checks that no two requirements of the same JD reach it, so different requirements aren't merged. Every comparison in `comparison.json` lists its unmatched requirements and any match that wasn't word-for-word, so the matching can be checked by eye.

## Limits

- **Three cases, written to be unambiguous.** High agreement here says the approaches agree on clear-cut JDs. Borderline cases (mid-band, mixed required and preferred, unclear location) are where judgment would differ; adding them is the next step.
- **One job per A run.** A Tier 2 run that scores several ticked rows loads its skills once, so its tokens per job would be lower than measured here.
- **A's stand-ins.** The Google connectors are stubbed. The Sheets stand-in is played by a small model, whose tokens aren't in A's trace and whose time is in A's duration.
