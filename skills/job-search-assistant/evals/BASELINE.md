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

**Known limit: binary files pass through the model.** The Drive connector hands a file to the skill as base64 text, and takes an upload the same way, so the model has to copy the template's base64 into a file and the finished .docx's base64 into the upload. In one run a copied template was corrupt and the skill rightly stopped before building. In another, it repaired the template and built the resume, but declined to upload it rather than risk a corrupt copy. Until the skill stops depending on that round trip, this case isn't expected to pass every run.

**Eval environment limit:** LibreOffice won't start inside the eval sandbox, so these runs can't make a PDF or count pages. The skill saves the .docx and reports the page count as unverified, as its rules say. The page-count logic itself is covered by `build_resume.py`'s unit tests, which run where LibreOffice is installed.

**Note on the rescore case.** In the 3-run baseline it scored 0.95 every time. The only failure was the `same-requirements` grader, whose pattern couldn't cross from one requirement entry to the next, so it could never match. The grader was fixed and the case rerun once: 1.00, with the r2 evidence table identical to gold. Every other grader passed in all runs.

## What a change should look like
- A scoring case dropping below 1.00 is a regression until shown otherwise. Read the run's fit report (`--keep-temp`, then the `create_file` call in `trace.jsonl`) before changing a grader.
- If a rubric change moves a gold score, `test_eval_fixtures.py` fails first. Update the gold table, the band in that case's `score-in-band.md`, and this file in the same PR.
