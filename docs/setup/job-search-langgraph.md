# Setup guide: job-search pipeline (LangGraph approach)

This guide takes you from a fresh clone to evaluating a real job posting with your own resume. Budget about 45 minutes, most of it the one-time Google Cloud setup in step 3.

| Step | What | Needed for |
|---|---|---|
| 1 | Install tools and run the demo | Everything (no keys needed) |
| 2 | Add an Anthropic API key | Scoring and tailoring |
| 3 | Google Cloud OAuth app | Reading your tracker, B's shadow sheet, and Gmail intake |
| 4 | Your job-search profile and full resume | Scoring and tailoring |
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

## 3. Google Cloud OAuth app (your tracker, and Gmail for intake)

The pipeline signs in to Google as you with the **`drive.file`** scope. It reaches only the files you pick in the Google Picker (your tracker, which it only reads) and the files it creates itself (its shadow spreadsheet), and nothing else in your Drive. For B's own Gmail intake it can also ask for **`gmail.readonly`**, a read-only but restricted scope.

> **This step is for developers.** Today you register your own Google app. Roadmap milestone 8 ships one with the local app, so its users sign in without any of this; Gmail then stays with Claude's connector, and only `drive.file` is asked for.

### 3a. Create a project and enable the APIs

1. Open the [Google Cloud console](https://console.cloud.google.com/) and create a project (for example, `job-search-pipeline`).
2. In **APIs & Services → Library**, enable the **Google Drive API**, the **Google Sheets API** and the **Google Picker API**. Add the **Gmail API** if you'll run intake.

### 3b. Configure the consent screen

In **Google Auth Platform** (older consoles call it **OAuth consent screen**):

1. **Branding:** app name `job-search-pipeline`, your email as support and developer contact.
2. **Audience:** user type **External** (required for a personal @gmail.com account). Under **Test users**, add your own address.

### 3c. Publish the app, or sign in again weekly

> While an External app's publishing status is **Testing**, Google issues refresh tokens that [expire after 7 days](https://developers.google.com/identity/protocols/oauth2#expiration), so you'd run `jobs auth google --sign-in` about once a week.

In **Audience**, click **Publish app** to move the status to **In production**. You don't need Google's verification for an app only you use: its verification rules [exempt apps used only by you](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification) or a few people you know. The cost is a "Google hasn't verified this app" warning when you sign in; click **Advanced → Go to job-search-pipeline (unsafe)**.

### 3d. Create the OAuth client and the Picker key

1. **Clients → Create client**, application type **Desktop app**. Leave "Use this client for an AI-powered agent" unticked. Download the JSON and save it as `orchestration/job-search/data/google/credentials.json`.
2. **APIs & Services → Credentials → Create credentials → API key.** Restrict it to the **Google Picker API**.
3. Note the **project number** from the project's dashboard (**Project info**; the number, not the project ID).
4. Save both in `orchestration/job-search/data/google/picker.json`:

   ```json
   {"api_key": "AIza...", "project_number": "123456789012"}
   ```

### 3e. Sign in and approve your tracker

Do step 4 first: the pipeline finds your tracker the way the plugin does, from your profile's **Tracker → Sheet ID**, and keeps no copy of it.

```bash
uv run jobs auth google            # add --gmail to also allow intake to read Gmail
```

1. A browser tab opens. Sign in, accept the warning from 3c, and **tick every box** on the permissions screen. Google lets you leave one unticked; the command then stops and says which.
2. The first time, a second tab opens the **Google Picker**, showing only the tracker your profile names. Select it: that's how `drive.file` grants access to a file, and picking any other spreadsheet is refused.
3. The command reads the tracker (by column header, as the plugin's contract says), and creates **Job Search Tracker (pipeline shadow)** in your Drive, the only spreadsheet the pipeline writes:

```
Signed in as you@gmail.com
Tracker, as your profile names it: Job_Search_Tracker (412 jobs for dedup)
Created B's shadow spreadsheet. B writes only there, never to your tracker.
Shadow: Job Search Tracker (pipeline shadow)  https://docs.google.com/spreadsheets/d/…
```

Run it again any time: it reuses your sign-in, and `--sign-in` signs in again (for another account, or after the token expires). If your profile later names a different tracker, the pipeline says it needs approval; run `jobs auth google` once more. The shadow's ID is kept in `data/google/sheets.json`, since your profile doesn't know about it.

**Keep B's jobs in the shadow.** Set `JOBS_TRACKER=sheets` in `.env`. B's jobs then live in the shadow's Job Log, with the plugin's column names plus **Pipeline Status** and **Pipeline Data**, which is what B reads back; its **History** tab records every status change, and its **JDs** tab holds job descriptions. Without the setting, B keeps using `data/tracker.db`. Either way, intake skips jobs already in your tracker (its Job Log and Archive).

**`token.json` is a credential.** It's gitignored and created with owner-only permissions. You can revoke it anytime at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## 4. Your job-search profile and full resume

The pipeline reads two files, the same two the Claude plugin uses:

- **`job-search-profile.md`**, the profile the plugin's `job-search-profile` skill writes to your job-search folder in Google Drive. Scoring judges title and seniority against its **Target roles**, and work arrangement against its **Location**.
- **Your full resume**: your whole career history as Markdown, not a two-page selection. Its file name comes from the profile's **Candidate → Full resume** line (the plugin's setup saves it as `Full-Resume.md`), and it must be in **the same folder as the profile**.

Choose where they live:

- **Copy them into `data/`.** Put `job-search-profile.md` and the resume it names into `orchestration/job-search/data/`. That's the default (`JOBS_PROFILE=./data/job-search-profile.md`), and `data/` is gitignored.
- **Or use them where they are.** If Google Drive for desktop syncs your job-search folder to this computer, set `JOBS_PROFILE` in `.env` to the profile in that folder. The pipeline then reads the plugin's own files, so there's nothing to copy or keep in step.

No full resume yet? The plugin's setup ("set up my job search") makes one from a resume you attach. Or convert a Word file with [pandoc](https://pandoc.org/installing.html), save it under the name your profile gives, and skim the result: tables and text boxes sometimes convert awkwardly, and the model can only score what it can read.

```bash
pandoc path/to/your_resume.docx -t gfm -o data/Full-Resume.md
```

If either file is missing, `jobs evaluate` stops and says which one and where it looked. When you later edit the full resume, the refresh graph (roadmap M5) detects the change by content hash and re-tailors unsubmitted resumes.

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

### Log leads from your job-alert email

Intake reads the senders in your profile's **Email sources** table, as the plugin's intake scan does, and logs each new job as a Tier 1 lead. It needs step 3, signed in with `--gmail`. Try it with `--dry-run` first: it shows what it would log and writes nothing.

```bash
uv run jobs run intake --dry-run
uv run jobs run intake
```

- **What it reads:** the last 7 days of mail from each Email sources sender. If the newest email already logged is older than that, it reads from that email's date instead, at most 30 days back. It never reads the senders under **Never scan**, nor LinkedIn's message and notification senders.
- **What it does with each email:** the model lists the email's jobs and judges each one's title fit and work arrangement against your profile. Code then cleans each link to its canonical form and skips anything already known (the same link, or the same company and title, where a company name with words added, such as "Acme" and "Acme Partners", counts as the same company). It also skips anything on your **Never interested** list or clearly off-target. The rubric's Tier 1 score is computed for the rest, and each one becomes a new row, oldest email first.
- **Running it again** adds nothing new: everything it logged is already known.

### Score the plugin's Tier 2 jobs in shadow mode

In shadow mode, B scores each job the plugin has already scored against its full job description, from the JD file the plugin saved, so the two scores can be compared. It needs step 3 (B only reads your tracker), `JOBS_PROFILE` pointing at the profile in your Drive-synced job-search folder (step 4), and Google Drive for desktop syncing that folder: B reads the plugin's `<ID>_JD.md` files from disk, because the `drive.file` permission can't reach files the plugin created. Set `JOBS_TRACKER=sheets` so the results go to B's shadow spreadsheet.

```bash
uv run jobs run tier2 --dry-run          # the jobs it would score; no model call
uv run jobs run tier2 --limit 5          # score at most five this run
uv run jobs run tier2
```

- **What it picks:** rows whose Score Tier is `T2` or `T2-manual` and whose latest fit-report run (`r<n>` in the Fit Report cell) B hasn't scored yet. When the plugin rescores a job, B scores it again, keeping the requirement list from its last run on that same JD.
- **What it writes:** B's score, gaps and breakdown in its shadow spreadsheet, under the plugin's ID. It never writes your tracker or touches the Run Tier 2 checkbox.
- **What it skips:** a job whose JD file isn't in the synced folder is listed and picked up on a later run, as is a job whose model call failed.

### Run the shadow week

The shadow week runs B next to the plugin for a week, then measures how far they agree. B only reads your tracker; everything it finds and scores goes to its shadow spreadsheet.

1. **Before the week:** sign in with Gmail (`uv run jobs auth google --gmail`) and run `uv run jobs run intake --dry-run` once, to check B reads your job-alert email as you expect. While your Google app is in Testing mode, a sign-in lasts 7 days, so expect to sign in again once during the week.
2. **Start it:** in `.env`, set `JOBS_TRACKER=sheets` and `JOBS_SHADOW_SINCE` to the first day, for example `JOBS_SHADOW_SINCE=2026-11-02`. From that day, the leads the plugin logs don't count as known to B's intake, so B logs each of the week's leads itself, whether it runs before or after the plugin. Older rows still count, so B doesn't log last month's jobs again.
3. **Each day,** after the plugin's scheduled runs:

   ```bash
   uv run jobs run intake
   uv run jobs run tier2
   ```

4. **At any time, and at the end:**

   ```bash
   uv run jobs report agreement                                  # from JOBS_SHADOW_SINCE
   uv run jobs report agreement --markdown evals/shadow/RESULTS.md
   ```

   The report compares the week's job-alert leads (found by both, by the plugin only, by B only), the Tier 1 scores on the leads both found, and the Tier 2 scores and evidence tables on the jobs B mirrored. The Markdown file holds counts and rates only, so it can be committed. The job IDs behind each number are printed for you and never written to it.
5. **After the week,** clear `JOBS_SHADOW_SINCE`.

## 6. Optional: tracing, Studio, and evals

**LangSmith tracing.** Uncomment the `LANGSMITH_*` lines in `.env` and add a key from [smith.langchain.com](https://smith.langchain.com). Note that the LLM calls go through the Anthropic SDK directly (core doesn't depend on LangChain), so you'll see graph and node spans. Per-call LLM traces are a roadmap item.

**LangGraph Studio.** This gives a visual graph, step-through, and state inspection:

```bash
cd approaches/langgraph
uv run --with "langgraph-cli[inmem]" langgraph dev
```

Studio uses the same tracker, profile and data folder as the `jobs` command, even though it runs from `approaches/langgraph`: relative paths in `.env` are taken from `orchestration/job-search`.

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
| `Google refresh token was rejected` about once a week | OAuth app still in **Testing** | Step 3c, then `jobs auth google --sign-in` |
| `Can't open spreadsheet …: the pipeline hasn't been given access` | Your profile names a tracker you haven't approved yet (new, or moved) | `jobs auth google`, and select it in the Picker |
| `Profile setting "Tracker → Sheet ID" is blank` | The profile has no tracker yet, or `JOBS_PROFILE` points at another file | Finish the plugin's setup ("set up my job search"), or fix `JOBS_PROFILE` |
| `Sign-in didn't grant …drive.file` | The Drive box was left unticked on Google's permissions screen | `jobs auth google --sign-in`, and tick every box |
| `Google access to …gmail.readonly wasn't granted` | Signed in without `--gmail` | `jobs auth google --gmail` |
| `CERTIFICATE_VERIFY_FAILED` | Antivirus or a company network inspecting TLS | The pipeline uses the system's certificates (`truststore`); if it persists, check that the inspecting certificate is installed in Windows or macOS |
| `invalid_grant` right after setup | Signed in with a different Google account than the one you meant | Revoke at myaccount.google.com/permissions, rerun `jobs auth google` |
| `Access blocked: app is in testing` | Your address isn't a test user | Step 3b: add it under **Test users** |
| `Access blocked: app has not completed verification` with no Advanced link | A Workspace admin policy | Ask the admin to trust the client |
| `Full resume '…' not found` or `Job-search profile not found` | Step 4 not done, or `JOBS_PROFILE` points elsewhere | The resume must be in the profile's folder, under the name on its "Full resume" line |
| `needs_manual_jd` for a site that works in your browser | Site blocks non-browser requests | Paste the JD with `provide-jd`; the job continues from where it paused |
| `This job is paused waiting on you` | You ran `evaluate` on a paused job | Answer the pending step, or `jobs evaluate ID --restart` |
