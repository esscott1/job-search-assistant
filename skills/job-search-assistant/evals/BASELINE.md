# Eval baseline: job-search-assistant

The reference result to compare against when a skill, the rubric or a prompt changes. Rerun the same command after the change, put both tables in the PR, and explain any case that moved.

**Run:** 2026-10-15 · plugin 0.1.3 · rubric v1.1 · Claude Code 2.1.301 (default model) · WSL Ubuntu · 3 runs per case, with the plugin only (`--ablation none`; without the plugin there's no rubric or `score.py`, so a scoring comparison says nothing).

```bash
claude plugin eval skills/job-search-assistant --runs 3 --ablation none --allow-tools Bash Write -j 3 \
  --trust-plugin --no-publish --output-dir ~/eval-runs/<date>
```

| Case | Gold | Score (3 runs) | What the runs did |
|---|---|---|---|
| `tier2-gold-strong-fit` | 10 | 1.00 · 1.00 · 1.00 | Score in the 9-10 band; PMP the gap; AWS and budget met |
| `tier2-gold-partial-fit` | 7 | 1.00 · 1.00 · 1.00 | Evidence table matched gold exactly in the traced run (score 7) |
| `tier2-gold-relocation-mismatch` | 1 | 1.00 · 1.00 · 1.00 | `relocation_required`, title `weak`, Rust gap |
| `tier2-rescore-closes-gap` | 7 → 8 | 1.00 (see note) | r2 written with r1's nine requirements unchanged; Kubernetes none → strong; score 8, "was 7" |
| `tier2-nothing-ticked` | n/a | 1.00 · 1.00 · 1.00 | Reported nothing ticked; no resume download, search or writes |
| `resume-no-jd-asks-first` | n/a | 1.00 · 1.00 · 1.00 | Asked for the job description; wrote nothing |

Total: 18 runs, about 10 minutes at `-j 3`.

**Added 2026-10-15 (plugin 0.1.4), resume cases that need no shell, run on Windows:**

| Case | Score (3 runs) | What the runs did |
|---|---|---|
| `resume-full-resume-missing` | 1.00 · 1.00 · 1.00 | Said Full-Resume.md wasn't found; never read the older Word resume; built nothing |
| `resume-ticked-row-needs-jd` | 1.00 · 1.00 · 1.00 | Skipped JS-002 for lack of a saved JD, left Build Resume ticked, said to run Tier 2 first |

**Added 2026-10-15 (plugin 0.1.5), resume cases that build a real resume, run in WSL:**

| Case | Score (3 runs) | What the runs did |
|---|---|---|
| `resume-does-not-invent` | 1.00 · 1.00 · 1.00 | Built the resume with vendor management featured; no Kubernetes, CKA or Rust anywhere; listed both as gaps |
| `resume-tailors-pasted-jd` | 1.00 · 0.78 · 0.56 | Content was right in every run. The two partial runs failed on moving files, not on judgement (see below) |

**Intake and cleanup cases**, 3 runs each, 2026-10-16. Intake runs needing a shell were in WSL (with `--allow-tools Bash Write`); cleanup and nothing-to-scan ran on Windows. `intake-scans-career-site` was rerun 3 times after its feed moved from a GitHub URL to the stub `web` server (1.00 each):

| Case | Score (3 runs) |
|---|---|
| `intake-logs-new-leads` | 1.00 · 1.00 · 1.00 |
| `intake-scans-career-site` | 1.00 · 1.00 · 1.00 |
| `intake-nothing-to-scan` | 1.00 · 1.00 · 0.83 |
| `cleanup-archives-untouched-rows` | 0.95 · 0.95 · 0.95 |
| `cleanup-creates-archive-tab` | 1.00 · 1.00 · 1.00 |
| `cleanup-honours-archive-age` | 1.00 · 1.00 · 1.00 |
| `cleanup-restores-a-row` | 1.00 · 1.00 · 1.00 |

Every deterministic check passed in every run: which rows were written, moved or skipped, one revision-checked batch, inserts at the top, canonical links, no sign-in tokens, and score.py and canonical_url.py actually run. The misses were LLM-judge checks on the final summary:
- In `cleanup-archives-untouched-rows`, the simulated spreadsheet (a small model playing Sheets) miscounted the Job Log's rows (7 instead of 8) and lost the last row when applying the batch. The skill's read-back check caught it and reported it honestly without repairing anything, as the skill says to. The Sheets mock now states each tab's exact row count. After that, the case scored 1.00 in 3 of 3 runs, and every cleanup case scored 1.00 in a further single pass. The summary judge also accepts an honest mismatch report, since that's the right behaviour if the sheet really changes.
- In `intake-nothing-to-scan`, the judge wanted a suggestion of where to add a source. It now asks only that the reply says why there's nothing to scan.

**Resume and profile cases at 0.2.0** (style file, no Word files through the connector), run in WSL with `--scaffold`, 3 runs each, 2026-10-15:

| Case | Score (3 runs) |
|---|---|
| `resume-tailors-pasted-jd` | 1.00 · 1.00 · 0.92 |
| `resume-does-not-invent` | 1.00 · 0.87 · 1.00 |
| `resume-delivers-to-synced-folder` | 1.00 · 1.00 · 1.00 |
| `resume-full-resume-missing` | 1.00 · 1.00 · 1.00 |
| `resume-ticked-row-needs-jd` | 1.00 · 1.00 · 1.00 |
| `resume-no-jd-asks-first` | 1.00 · 1.00 · 1.00 |
| `profile-convert-template` | 1.00 · 1.00 · 1.00 |
| `profile-style-update` | 1.00 · 1.00 · 1.00 |

Total: 24 runs, about 12 minutes at `-j 3`. Every deterministic check passed in every run: render_resume.py ran with the style file, the style was read, nothing binary was uploaded, no invented skills, and the file landed in the synced folder. The two misses were single LLM-judge checks in one run each: "lists the gaps" (does-not-invent) and "nothing beyond the full resume" (pasted JD, a 2-1 split vote). Building a resume now takes about 2 minutes, down from 5-15.

**Cleanup and intake cases at 0.4.4** ("reset my job tracker"; Archive Reason), run in WSL, 3 runs each, 2026-10-20:

| Case | Score (3 runs) |
|---|---|
| `cleanup-reset-asks-first` (new) | 1.00 · 1.00 · 1.00 |
| `cleanup-reset-archives-everything` (new) | 1.00 · 1.00 · 1.00 |
| `cleanup-archives-untouched-rows` | 1.00 · 1.00 · 1.00 |
| `cleanup-creates-archive-tab` | 1.00 · 1.00 · 1.00 |
| `cleanup-honours-archive-age` | 1.00 · 1.00 · 1.00 |
| `cleanup-restores-a-row` | 1.00 · 1.00 · 1.00 |
| `intake-after-reset` (new) | 1.00 · 1.00 · 1.00 |
| `intake-banner-is-not-closed` | 1.00 · 1.00 · 1.00 |
| `intake-logs-new-leads` | 1.00 · 1.00 · 1.00 |
| `intake-nothing-to-scan` | 1.00 · 1.00 · 1.00 |
| `intake-scans-career-site` | 1.00 · 1.00 · 1.00 |

`cleanup-archives-untouched-rows` now also checks that the weekly cleanup writes Archive Reason `stale`, adding the column to an Archive that predates it. `intake-after-reset` checks the job archived by a reset is logged again as JS-006 onwards, the stale-archived one is still skipped, and the Gmail search uses the normal 7-day window.

**Intake and Tier 2 cases at 0.4.3** (posting pages read with `read_posting.py`; closed only on hard evidence), run in WSL, 3 runs each, 2026-10-20:

| Case | Score (3 runs) |
|---|---|
| `intake-banner-is-not-closed` (new) | 1.00 · 1.00 · 1.00 |
| `intake-logs-new-leads` | 1.00 · 1.00 · 1.00 |
| `intake-nothing-to-scan` | 1.00 · 1.00 · 1.00 |
| `intake-scans-career-site` | 1.00 · 1.00 · 1.00 |
| `tier2-gold-strong-fit` | 1.00 · 1.00 · 1.00 |
| `tier2-gold-partial-fit` | 1.00 · 1.00 · 1.00 |
| `tier2-gold-relocation-mismatch` | 1.00 · 1.00 · 1.00 |
| `tier2-rescore-closes-gap` | 1.00 · 1.00 · 1.00 |
| `tier2-nothing-ticked` | 1.00 · 1.00 · 1.00 |

In every run of the new case, `read_posting.py` was tried first and reported the fictional host unreachable, the skill fell back to the stub fetch, and both open jobs were logged: the banner-only one at Tier 1, the one with the boilerplate line at Tier 2. One run also skipped a third posting whose page returned 404, with that evidence in the summary. The first pass of the case scored 0.89: the judge failed two correct replies for quoting the banner or adding "check the posting yourself". The judge now grades what the reply does with the leads, not whether it repeats the banner. No scoring case moved.

**Profile cases at 0.4.1** (brief, menu-driven setup), run in WSL, 3 runs each, 2026-10-20. Every case disallows `AskUserQuestion`, so the numbered-list menus are what's graded:

| Case | Score (3 runs) |
|---|---|
| `profile-setup-starts-brief` (new) | 1.00 · 1.00 · 1.00 |
| `profile-setup-prefills-from-resume` (new) | 1.00 · 1.00 · 1.00 |
| `profile-setup-saves-pasted-resume` (new) | 1.00 · 1.00 · 1.00 |
| `profile-setup-checks-style-file` (new) | 1.00 · 1.00 · 1.00 |
| `profile-update-is-brief` (new) | 1.00 · 1.00 · 1.00 |
| `profile-style-update` | 1.00 · 1.00 · 1.00 |
| `profile-convert-template` | 1.00 · 1.00 · 1.00 |

Getting there:
- **`profile-style-update`:**
  - **The judge fails a shortened line.** The first pass shortened the changed line with "…". The skill now shows the whole setting line before and after.
  - **A missing stub tool.** The Drive stub had no `update_file` or `trash_file`, so the run couldn't follow the profile's replace-the-file steps and offered workarounds instead of "Save / Cancel". The stub now has both, as the real connector does.
  - **An unasked-for choice.** The run then added a "make my name navy too" choice, which the judge read as a second change. The skill now offers only choices about what was asked.
- **`profile-setup-saves-pasted-resume`:** a 1-2 judge split on a correct reply. The roles-in-order check is now a regex, with a lighter judge for "asks before saving, invents nothing".

**Resume cases at 0.4.0** (adds a Google Doc of every tailored resume, made from `render_resume.py --html` and sent to Drive as text), run in WSL with `--scaffold`, 3 runs each, 2026-10-19:

| Case | Score (3 runs) |
|---|---|
| `resume-tailors-pasted-jd` | 1.00 · 1.00 · 1.00 |
| `resume-delivers-to-synced-folder` | 1.00 · 1.00 · 1.00 |
| `resume-history-rules` | 1.00 · 1.00 · 1.00 |
| `resume-honours-requested-page-limit` | 1.00 · 1.00 · 1.00 |
| `resume-does-not-invent` | 1.00 · 1.00 · 1.00 |
| `resume-full-resume-missing` | 1.00 · 1.00 · 1.00 |
| `resume-ticked-row-needs-jd` | 1.00 · 1.00 · 1.00 |
| `resume-no-jd-asks-first` | 1.00 · 1.00 · 1.00 |

The new `creates-google-doc` grader passed in every run of the five cases that build a resume: the Doc was created from HTML text, and nothing went to Drive as base64.

The first pass scored `resume-tailors-pasted-jd` 0.89. Its `delivered` judge still said the reply mustn't claim to have uploaded the resume to Drive, which the Google Doc now correctly does; the judge was reworded. The same pass showed the Drive stub returning one id (`FILE_NEW_0001`) for every created file, so the folder, the Doc and the JD shared an id and the runs warned about it. Each created file now gets an id from its title. After both fixes, the two cases that deliver files were rerun (above), with `tier2-rescore-closes-gap` once as a check on the stub change: 1.00.

The stub has no `read_file_content`, so these runs report the Doc as not verified; `check_doc_text.py` is covered by its unit tests.

**Resume cases at 0.3.0** (3-page limit, the user's lower limit, no company descriptions, every role has a line, the 15-year rule, check_content.py), run in WSL with `--scaffold`, 3 runs each, 2026-10-16:

| Case | Score (3 runs) |
|---|---|
| `resume-history-rules` (new) | 1.00 · 1.00 · 1.00 |
| `resume-honours-requested-page-limit` (new) | 1.00 · 1.00 · 1.00 |
| `resume-tailors-pasted-jd` | 1.00 · 1.00 · 0.94 |
| `resume-delivers-to-synced-folder` | 1.00 · 1.00 · 1.00 |
| `resume-does-not-invent` | 1.00 · 1.00 · 1.00 |
| `resume-full-resume-missing` | 1.00 · 1.00 · 1.00 |
| `resume-ticked-row-needs-jd` | 1.00 · 1.00 · 1.00 |
| `resume-no-jd-asks-first` | 1.00 · 1.00 · 1.00 |

Every deterministic check passed in every run:
- `check_content.py` ran and reported ok.
- No company description reached `content.json`.
- The old but relevant Vendor Contracts Analyst role was kept.
- `--max-pages 2` reached the renderer when the user asked, and the default was 3 otherwise.

The one miss was the existing `truthful` judge in one pasted-JD run. That summary also gave a fit score, which this skill doesn't calculate; every resume line traced to the full resume.

In a first pass, three new graders failed even though the skill had behaved correctly. Two regex patterns used `\\`, which the runner reads as a single backslash (see README). A judge also tried to check `content.json`, but a judge sees only the final message. Those graders were fixed or removed before the runs above. The first pass also showed the model leaving out `"bullets"` on a summary-only role, which the checker rejected until the model added it, so `bullets` is now optional when a role has a summary.

The page limit and the half-full 3rd page can't be exercised here, because LibreOffice can't run in the sandbox. They're covered by `test_render_resume.py`, which renders real PDFs where LibreOffice is installed.

**Superseded in 0.2.0.** The resume builder no longer moves Word files through the connector: it renders from the user's text style file and delivers the .docx and PDF by download or a synced Drive folder. The note below describes 0.1.5.

**Known limit (0.1.5): binary files pass through the model.** The Drive connector hands a file to the skill as base64 text, and takes an upload the same way, so the model has to copy the template's base64 into a file and the finished .docx's base64 into the upload. In one run a copied template was corrupt and the skill rightly stopped before building. In another, it repaired the template and built the resume, but declined to upload it rather than risk a corrupt copy. Until the skill stops depending on that round trip, this case isn't expected to pass every run.

**Eval environment limit:** LibreOffice won't start inside the eval sandbox, so these runs can't make a PDF or count pages. The skill saves the .docx and reports the page count as unverified, as its rules say. The page-count logic itself is covered by `build_resume.py`'s unit tests, which run where LibreOffice is installed.

**Note on the rescore case.** In the 3-run baseline it scored 0.95 every time. The only failure was the `same-requirements` grader, whose pattern couldn't cross from one requirement entry to the next, so it could never match. The grader was fixed and the case rerun once: 1.00, with the r2 evidence table identical to gold. Every other grader passed in all runs.

**Borderline scoring cases** (new) and the clear-cut gold cases, plugin 0.4.5, run through the measured comparison (`orchestration/job-search/evals/comparison/run_a.sh`), which pins the model to `claude-sonnet-5-5`. WSL Ubuntu, Claude Code 2.1.301, 3 runs each, 2026-10-22:

| Case | Gold | Scores | Grader score (3 runs) |
|---|---|---|---|
| `tier2-borderline-required-half-met` | 7 | 7 · 7 · 7 | 1.00 · 1.00 · 1.00 |
| `tier2-borderline-remote-residency` | 3 | 3 · 3 · 3 | 0.81 · 1.00 · 1.00 |
| `tier2-borderline-unlabelled-list` | 7 | 7 · 7 · 7 | 0.88 · 1.00 · 0.88 |
| `tier2-gold-strong-fit` | 10 | 10 · 10 · 9 | 1.00 · 1.00 · 1.00 |
| `tier2-gold-partial-fit` | 7 | 7 · 7 · 7 | 1.00 · 1.00 · 1.00 |
| `tier2-gold-relocation-mismatch` | 1 | 1 · 1 · 1 | 1.00 · 1.00 · 1.00 |

Every score was within ±1 of gold, and every judgment call the borderline cases turn on was made as gold has it. The three misses:
- **`remote-residency`, run 1:** the score was right (3, relocation required), but the fit report's first line read `Score: 3 (T1 → scored against saved JD; …)` instead of `Score: 3 (T2)`, so `score-in-band` didn't match. That's a formatting slip in the fit report, not a scoring error.
- **`unlabelled-list`, runs 1 and 3:** "ERP implementation experience (SAP or Oracle)" was judged `partial`, where gold has `none` (the resume shows no ERP work). The score held at 7.
- **`strong-fit`, run 3:** "10+ years of experience delivering IT programs" was judged `partial` (programs since 2018, projects before that), so the score was 9. It's within the band, and a defensible reading.

## What a change should look like
- A scoring case dropping below 1.00 is a regression until shown otherwise. Read the run's fit report (`--keep-temp`, then the `create_file` call in `trace.jsonl`) before changing a grader.
- If a rubric change moves a gold score, `test_eval_fixtures.py` fails first. Update the gold table, the band in that case's `score-in-band.md`, and this file in the same PR.
