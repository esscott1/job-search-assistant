# Agent registry

One row per agent in this repo. [Sally](ai-governance/sally/SKILL.md) updates this file in the same commit as any agent change; see her SKILL.md for what each column means and the lifecycle stages.

- **Version** is the version on `main`. **Installed version** is what Alex has in Claude, and stays `unverified` until someone compares the installed copy to the repo.
- **Install method** is `standalone` (the skill folder uploaded as a ZIP) or `plugin` (the category plugin installed from this marketplace). A skill is installed one way, never both.

| Agent | Category | Version | Stage | Install method | Installed version | Runs on | Schedule | Files | Last change |
|---|---|---|---|---|---|---|---|---|---|
| [`job-lead-intake-scan`](personal-productivity/job-lead-intake-scan/SKILL.md) | personal-productivity | 1.0.0 | released | standalone | 1.0.0 | Cloud (Gmail + Google Drive) | Daily, 8:00am local time | SKILL.md only | 2026-09-29: moved into the `personal-productivity` category |
| [`job-lead-tier2-scoring`](personal-productivity/job-lead-tier2-scoring/SKILL.md) | personal-productivity | 1.0.0 | released | standalone | 1.0.0 | Alex's computer (signed-in browser) | On demand | SKILL.md only | 2026-09-29: moved into the `personal-productivity` category |
| [`sally`](ai-governance/sally/SKILL.md) | ai-governance | 2.0.0 | released | standalone | 2.0.0 | Any surface; GitHub write access or the JobSearch Project queue | On demand | SKILL.md only | 2026-10-07: front door; status and drift moved to `sally-audit` |
| [`sally-audit`](ai-governance/sally-audit/SKILL.md) | ai-governance | 1.0.0 | released | standalone | 1.0.0 | Any surface; read-only | On demand | SKILL.md only | 2026-10-07: split out of `sally` as the read-only status and drift report |
