# Eval baseline: job-search-assistant

The reference result to compare against when a skill, the rubric or a prompt changes. Rerun the same command after the change, put both tables in the PR, and explain any case that moved.

**Run:** 2026-10-15 · plugin 0.1.3 · rubric v1.1 · Claude Code 2.1.301 (default model) · WSL Ubuntu · 3 runs per case, with the plugin only (`--ablation none`; without the plugin there's no rubric or `score.py`, so a scoring comparison says nothing).

```bash
claude plugin eval skills/job-search-assistant --runs 3 --ablation none --allow-tools Bash Write -j 3 \
  --trust-plugin --no-publish --output-dir ~/eval-runs/<date>
```

| Case | Gold | Score (3 runs) | Cost per run | What the runs did |
|---|---|---|---|---|
| `tier2-gold-strong-fit` | 10 | 1.00 · 1.00 · 1.00 | $0.68-0.69 | Score in the 9-10 band; PMP the gap; AWS and budget met |
| `tier2-gold-partial-fit` | 7 | 1.00 · 1.00 · 1.00 | $0.68-0.69 | Evidence table matched gold exactly in the traced run (score 7) |
| `tier2-gold-relocation-mismatch` | 1 | 1.00 · 1.00 · 1.00 | $0.64-0.66 | `relocation_required`, title `weak`, Rust gap |
| `tier2-rescore-closes-gap` | 7 → 8 | 1.00 (see note) | $0.67-0.81 | r2 written with r1's nine requirements unchanged; Kubernetes none → strong; score 8, "was 7" |
| `tier2-nothing-ticked` | n/a | 1.00 · 1.00 · 1.00 | $0.25-0.31 | Reported nothing ticked; no resume download, search or writes |
| `resume-no-jd-asks-first` | n/a | 1.00 · 1.00 · 1.00 | $0.15-0.16 | Asked for the job description; wrote nothing |

Total: 18 runs, $9.51, about 10 minutes at `-j 3`.

**Added 2026-10-15 (plugin 0.1.4), resume cases that need no shell, run on Windows:**

| Case | Score (3 runs) | Cost per run | What the runs did |
|---|---|---|---|
| `resume-full-resume-missing` | 1.00 · 1.00 · 1.00 | $0.23 | Said Full-Resume.md wasn't found; never read the older Word resume; built nothing |
| `resume-ticked-row-needs-jd` | 1.00 · 1.00 · 1.00 | $0.26 | Skipped JS-002 for lack of a saved JD, left Build Resume ticked, said to run Tier 2 first |

**Added 2026-10-15 (plugin 0.1.5), resume cases that build a real resume, run in WSL:**

| Case | Score (3 runs) | Usage per run (API-equivalent) | What the runs did |
|---|---|---|---|
| `resume-does-not-invent` | 1.00 · 1.00 · 1.00 | $1.34-1.64 | Built the resume with vendor management featured; no Kubernetes, CKA or Rust anywhere; listed both as gaps |
| `resume-tailors-pasted-jd` | 1.00 · 0.78 · 0.56 | $1.17-1.58 | Content was right in every run. The two partial runs failed on moving files, not on judgement (see below) |

**Intake and cleanup cases**, 3 runs each, 2026-10-16. Intake runs needing a shell were in WSL (with `--allow-tools Bash Write`); cleanup and nothing-to-scan ran on Windows. `intake-scans-career-site` was rerun 3 times after its feed moved from a GitHub URL to the stub `web` server (1.00 each):

| Case | Score (3 runs) | Usage per run (API-equivalent) |
|---|---|---|
| `intake-logs-new-leads` | 1.00 · 1.00 · 1.00 | $0.56-0.59 |
| `intake-scans-career-site` | 1.00 · 1.00 · 1.00 | $0.60-0.65 |
| `intake-nothing-to-scan` | 1.00 · 1.00 · 0.83 | $0.22-0.26 |
| `cleanup-archives-untouched-rows` | 0.95 · 0.95 · 0.95 | $0.45-0.51 |
| `cleanup-creates-archive-tab` | 1.00 · 1.00 · 1.00 | $0.37-0.50 |
| `cleanup-honours-archive-age` | 1.00 · 1.00 · 1.00 | $0.22 |
| `cleanup-restores-a-row` | 1.00 · 1.00 · 1.00 | $0.36-0.37 |

Every deterministic check passed in every run: which rows were written, moved or skipped, one revision-checked batch, inserts at the top, canonical links, no sign-in tokens, and score.py and canonical_url.py actually run. The misses were LLM-judge checks on the final summary:
- In `cleanup-archives-untouched-rows`, the simulated spreadsheet (a small model playing Sheets) miscounted the Job Log's rows (7 instead of 8) and lost the last row when applying the batch. The skill's read-back check caught it and reported it honestly without repairing anything, as the skill says to. The Sheets mock now states each tab's exact row count. After that, the case scored 1.00 in 3 of 3 runs, and every cleanup case scored 1.00 in a further single pass. The summary judge also accepts an honest mismatch report, since that's the right behaviour if the sheet really changes.
- In `intake-nothing-to-scan`, the judge wanted a suggestion of where to add a source. It now asks only that the reply says why there's nothing to scan.

**Resume and profile cases at 0.2.0** (style file, no Word files through the connector), run in WSL with `--scaffold`, 3 runs each, 2026-10-15:

| Case | Score (3 runs) | Usage per run (API-equivalent) |
|---|---|---|
| `resume-tailors-pasted-jd` | 1.00 · 1.00 · 0.92 | $0.64-0.76 |
| `resume-does-not-invent` | 1.00 · 0.87 · 1.00 | $0.65-0.74 |
| `resume-delivers-to-synced-folder` | 1.00 · 1.00 · 1.00 | $0.70-0.72 |
| `resume-full-resume-missing` | 1.00 · 1.00 · 1.00 | $0.32-0.35 |
| `resume-ticked-row-needs-jd` | 1.00 · 1.00 · 1.00 | $0.33-0.34 |
| `resume-no-jd-asks-first` | 1.00 · 1.00 · 1.00 | $0.16 |
| `profile-convert-template` | 1.00 · 1.00 · 1.00 | $0.41-0.57 |
| `profile-style-update` | 1.00 · 1.00 · 1.00 | $0.41-0.51 |

Total: 24 runs, $11.53 of API-equivalent usage, about 12 minutes at `-j 3`. Every deterministic check passed in every run: render_resume.py ran with the style file, the style was read, nothing binary was uploaded, no invented skills, and the file landed in the synced folder. The two misses were single LLM-judge checks in one run each: "lists the gaps" (does-not-invent) and "nothing beyond the full resume" (pasted JD, a 2-1 split vote). Building a resume now takes about 2 minutes, down from 5-15.

**Superseded in 0.2.0.** The resume builder no longer moves Word files through the connector: it renders from the user's text style file and delivers the .docx and PDF by download or a synced Drive folder. The note below describes 0.1.5.

**Known limit (0.1.5): binary files pass through the model.** The Drive connector hands a file to the skill as base64 text, and takes an upload the same way, so the model has to copy the template's base64 into a file and the finished .docx's base64 into the upload. In one run a copied template was corrupt and the skill rightly stopped before building. In another, it repaired the template and built the resume, but declined to upload it rather than risk a corrupt copy. Until the skill stops depending on that round trip, this case isn't expected to pass every run.

**Eval environment limit:** LibreOffice won't start inside the eval sandbox, so these runs can't make a PDF or count pages. The skill saves the .docx and reports the page count as unverified, as its rules say. The page-count logic itself is covered by `build_resume.py`'s unit tests, which run where LibreOffice is installed.

**Note on the rescore case.** In the 3-run baseline it scored 0.95 every time. The only failure was the `same-requirements` grader, whose pattern couldn't cross from one requirement entry to the next, so it could never match. The grader was fixed and the case rerun once: 1.00, with the r2 evidence table identical to gold. Every other grader passed in all runs.

## What a change should look like
- A scoring case dropping below 1.00 is a regression until shown otherwise. Read the run's fit report (`--keep-temp`, then the `create_file` call in `trace.jsonl`) before changing a grader.
- If a rubric change moves a gold score, `test_eval_fixtures.py` fails first. Update the gold table, the band in that case's `score-in-band.md`, and this file in the same PR.
