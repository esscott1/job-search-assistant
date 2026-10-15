# Agent registry

One row per agent in this repo. [Sally](ai-governance/sally/SKILL.md) updates this file in the same commit as any agent change; see her SKILL.md for what each column means and the lifecycle stages.

- **Version** is the version on `main`. Before 1.0.0, a breaking change bumps the minor version and anything else the patch (see Sally's *Versioning*).
- The registry describes the repo only. Whether an account has a skill installed, and which version, isn't recorded here; [sally-audit](ai-governance/sally-audit/SKILL.md) reports it for the account it runs in.

| Agent | Category | Version | Stage | Runs on | Schedule | Files | Last change |
|---|---|---|---|---|---|---|---|
| [`job-search-profile`](job-search-assistant/job-search-profile/SKILL.md) | job-search-assistant | 0.1.1 | released | Any surface; Google Drive and Google Sheets connectors; Gmail, web search and web fetch for job sources | On demand | SKILL.md only | 2026-10-15: guided job-sources step (Gmail connector check, Career sites found and tested) |
| [`job-lead-intake-scan`](job-search-assistant/job-lead-intake-scan/SKILL.md) | job-search-assistant | 0.1.1 | released | Cloud (Gmail, Google Drive, Google Sheets; web search and web fetch for career sites) | Daily | SKILL.md only | 2026-10-15: scans the profile's career sites as well as email |
| [`job-lead-tier2-scoring`](job-search-assistant/job-lead-tier2-scoring/SKILL.md) | job-search-assistant | 0.1.0 | released | Cloud (web search and fetch, Google Drive, Google Sheets); no browser | Every 2-4 hours (ticked rows only), or on demand | SKILL.md only | 2026-10-15: first public pre-release |
| [`job-lead-manual-jd-lookup`](job-search-assistant/job-lead-manual-jd-lookup/SKILL.md) | job-search-assistant | 0.1.0 | released | The user's computer (signed-in browser) and Google Sheets | On demand | SKILL.md only | 2026-10-15: first public pre-release |
| [`job-fit-rubric`](job-search-assistant/job-fit-rubric/SKILL.md) | job-search-assistant | 0.1.0 | released | Any surface; Python 3 for score.py | Loaded by the job-lead skills | SKILL.md, score.py, test_score.py | 2026-10-15: first public pre-release |
| [`job-tracker`](job-search-assistant/job-tracker/SKILL.md) | job-search-assistant | 0.1.1 | released | Any surface; Python 3 for canonical_url.py | Loaded by the job-lead skills and tailored-resume-builder | SKILL.md, canonical_url.py, test_canonical_url.py | 2026-10-15: career-site rows (Source, blank email columns, dedup); canonical forms for Workday, iCIMS, Ashby, SmartRecruiters |
| [`job-tracker-cleanup`](job-search-assistant/job-tracker-cleanup/SKILL.md) | job-search-assistant | 0.1.0 | released | Cloud (Google Sheets) | Weekly, or on demand | SKILL.md only | 2026-10-15: first public pre-release |
| [`tailored-resume-builder`](job-search-assistant/tailored-resume-builder/SKILL.md) | job-search-assistant | 0.1.0 | released | Cloud or the user's computer; python-docx and LibreOffice | On demand only ("build ticked resumes") | SKILL.md, build_resume.py, test_build_resume.py | 2026-10-15: first public pre-release |
| [`sally`](ai-governance/sally/SKILL.md) | ai-governance | 0.1.1 | released | Any surface; GitHub write access, or a claude.ai Project queue | On demand | SKILL.md only | 2026-10-15: explicit `skills` list in plugin.json (new skills are added to it; audit reports missing ones) |
| [`sally-audit`](ai-governance/sally-audit/SKILL.md) | ai-governance | 0.1.1 | released | Any surface; read-only | On demand | SKILL.md only | 2026-10-15: explicit `skills` list in plugin.json (new skills are added to it; audit reports missing ones) |
