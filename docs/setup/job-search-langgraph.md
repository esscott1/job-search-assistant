# Setup guide: job-search pipeline (LangGraph approach)

This guide takes you from a fresh clone to evaluating a real job posting with your own resume. Budget about 45 minutes, most of it the one-time Google Cloud setup in step 3.

| Step | What | Needed for |
|---|---|---|
| 1 | Install tools and run the demo | Everything (no keys needed) |
| 2 | Add an Anthropic API key | Scoring and tailoring |
| 3 | Google Cloud OAuth app | Gmail intake (M2), Drive tracker import (M2) |
| 4 | Your master resume | Scoring and tailoring |
| 5 | Evaluate your first job | — |
| 6 | Optional: tracing and Studio | Debugging, screenshots |

Steps 1, 2, 4 and 5 are enough to use the evaluate graph today. Step 3 can wait until you start on intake, but do it early if you can: it's the step most likely to need a second attempt.

---

## 1. Install tools and run the demo

Prerequisites: Python 3.11+, git, and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/esscott1/job-search-assistant.git
cd job-search-assistant/orchestration/job-search
uv sync --all-packages          # creates .venv with core + the langgraph approach
uv run pytest -q                # all tests use fakes — no keys, no network
uv run jobs demo                # walks the three graph paths with fake data
```

The demo shows a strong fit pausing for your review, a weak fit stopping below threshold, and a LinkedIn posting pausing for a manual job description. If that runs, your install is good.

## 2. Add an Anthropic API key

```bash
cp .env.example .env
```

Create a key in the [Anthropic Console](https://console.anthropic.com/) and paste it into `.env` as `ANTHROPIC_API_KEY`. `JOBS_MODEL` pins the model so eval results stay comparable over time. Change it deliberately, then re-run the evals (step 6).

`.env` is gitignored. Never commit it.

## 3. Google Cloud OAuth app (Gmail and Drive, read-only)

The pipeline signs in to Google as you, with **read-only** scopes (`gmail.readonly`, `drive.readonly`). It can't send mail or change files.

### 3a. Create a project and enable the APIs

1. Open the [Google Cloud console](https://console.cloud.google.com/) and create a project (for example, `job-search-pipeline`).
2. In **APIs & Services → Library**, enable the **Gmail API** and the **Google Drive API**.

### 3b. Configure the consent screen

In **Google Auth Platform** (older consoles call it **OAuth consent screen**):

1. **Branding:** app name `job-search-pipeline`, your email as support and developer contact.
2. **Audience:** user type **External** (required for a personal @gmail.com account).
3. **Data access:** add the scopes `.../auth/gmail.readonly` and `.../auth/drive.readonly`.

### 3c. Publish the app — don't skip this

> **This is the step that prevents weekly failures.** While an External app's publishing status is **Testing**, Google issues refresh tokens that [expire after 7 days](https://developers.google.com/identity/protocols/oauth2#expiration). The pipeline would then fail with authentication errors about once a week.

In **Audience**, click **Publish app** to move the status to **In production**. You do **not** need Google's verification for this. Google's verification rules [exempt apps used only by you](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification) or a few people you know. The cost is a "Google hasn't verified this app" warning when you sign in. Click **Advanced → Go to job-search-pipeline (unsafe)**. That's expected for a personal app.

### 3d. Create the OAuth client

1. **Clients → Create client**, application type **Desktop app**.
2. Download the JSON and save it as `orchestration/job-search/data/google/credentials.json`.

### 3e. Sign in once

```bash
uv run jobs auth google
```

A browser window opens. Sign in, accept the warning from 3c, and grant both read-only permissions. The command saves a refresh token to `data/google/token.json` and verifies it with one read call each to Gmail and Drive:

```
Signed in. Gmail: you@gmail.com  Drive: you@gmail.com
```

From then on the pipeline refreshes access silently. **`token.json` is a credential.** It's gitignored and created with owner-only permissions. You can revoke it anytime at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## 4. Your master resume and job-search profile

Scoring and tailoring read your master resume as Markdown from `data/master_resume.md`. It's gitignored, so it never reaches the public repo. To convert your existing `.docx` with [pandoc](https://pandoc.org/installing.html):

```bash
pandoc path/to/your_master_resume.docx -t gfm -o data/master_resume.md
```

Skim the result: tables and text boxes sometimes convert awkwardly, and the model can only score what it can read.

Scoring also reads your **job-search profile**, `data/job-search-profile.md`. It's the same file the Claude plugin's `job-search-profile` skill writes to your tracker folder in Google Drive, so copy that file into `data/`. Only its **Target roles** and **Location** sections are used: title and seniority are judged against the first, and work arrangement against the second. Without the file, `jobs evaluate` stops and says where to put it. To keep it elsewhere, set `JOBS_PROFILE` in `.env`. When you later edit the master resume, the refresh graph (roadmap M5) detects the change by content hash and re-tailors unsubmitted resumes.

## 5. Evaluate your first job

```bash
uv run jobs add --company "Acme" --title "AI Enablement Architect" \
    --url "https://boards.greenhouse.io/acme/jobs/123"
# → LG-0001
uv run jobs evaluate LG-0001
```

Depending on the posting, one of three things happens:

| Outcome | What you see | What to do |
|---|---|---|
| JD fetched, score ≥ 7 | `resume_drafted`, waiting on `resume_review` | Read `data/resumes/LG-0001.md`, then `uv run jobs review LG-0001 --approve` (or `--reject --note "..."`) |
| JD fetched, score < 7 | `below_threshold` with the three gaps | Nothing. It stays logged with its score. |
| JD not reachable (LinkedIn, blocked ATS) | `needs_manual_jd` | Copy the JD into a text file, then `uv run jobs provide-jd LG-0001 --file jd.txt` |

Other commands:

```bash
uv run jobs list                          # everything, with status and score
uv run jobs list --status resume_ready
uv run jobs show LG-0001                  # details, status history, what it's waiting on
uv run jobs submit LG-0001                # you applied: records it as your action
uv run jobs set-status LG-0001 interviewing --note "Recruiter screen 10/8"
```

The status lifecycle is enforced. For example, a `below_threshold` job can't be marked `submitted`, and a submitted job can't be re-scored. Every change is recorded with who made it (`pipeline` or `user`), and later `email` when the status sweep lands.

To reuse IDs from your existing Excel tracker during shadow mode, pass `--id JS-042` to `jobs add`.

## 6. Optional: tracing, Studio, and evals

**LangSmith tracing.** Uncomment the `LANGSMITH_*` lines in `.env` and add a key from [smith.langchain.com](https://smith.langchain.com). Note that the LLM calls go through the Anthropic SDK directly (core doesn't depend on LangChain), so you'll see graph and node spans. Per-call LLM traces are a roadmap item.

**LangGraph Studio.** This gives a visual graph, step-through, and state inspection:

```bash
cd approaches/langgraph
uv run --with "langgraph-cli[inmem]" langgraph dev
```

**Evals.** These check that the scoring prompt and model still land in expected bands against a synthetic candidate:

```bash
uv run python evals/job-fit/run_evals.py           # real model; writes results/latest.json
uv run python evals/job-fit/run_evals.py --fake    # harness only
```

To run evals in GitHub Actions on pull requests that change prompts, add `ANTHROPIC_API_KEY` as a repository secret (**Settings → Secrets and variables → Actions**).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Google refresh token was rejected` about once a week | OAuth app still in **Testing** | Step 3c, then `jobs auth google` once more |
| `invalid_grant` right after setup | Signed in with a different Google account than the one you meant | Revoke at myaccount.google.com/permissions, rerun `jobs auth google` |
| `Access blocked: app has not completed verification` with no Advanced link | Scopes changed after publishing, or a Workspace admin policy | Re-check 3b; for Workspace accounts ask the admin to trust the client |
| `Master resume not found` | Step 4 not done, or `JOBS_MASTER_RESUME` points elsewhere | Check `.env` |
| `needs_manual_jd` for a site that works in your browser | Site blocks non-browser requests | Paste the JD with `provide-jd`; the job continues from where it paused |
| `This job is paused waiting on you` | You ran `evaluate` on a paused job | Answer the pending step, or `jobs evaluate ID --restart` |
