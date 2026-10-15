# Installed skills visible in this session

Only the available-skills list is visible: each installed skill's name and description. The installed SKILL.md files and folders are **not** readable in this session.

| Skill | Method | Description |
|---|---|---|
| job-lead-intake-scan | standalone | Scan Alex's Gmail for new job leads (NorthStar Staffing/Jordan, LinkedIn job alerts, MyJobHelper), screen them for fit, and log new candidates to the Job Search Tracker. Cloud-only — runs on the daily schedule, no computer/browser needed. |
| job-lead-tier2-scoring | standalone | Cloud-only, cron-friendly: for tracker rows still tagged Tier 1, search the open web and fetch the real JD from company/ATS pages (never LinkedIn directly), then score and update the row. Rows it can't resolve get flagged in Notes recommending job-lead-manual-jd-lookup. |
| job-lead-manual-jd-lookup | standalone | On-demand, requires Alex's computer: for tracker rows job-lead-tier2-scoring flagged as unreachable by web search (LinkedIn postings with no JD body, sites that block fetch), read the real JD using Alex's own browser session and update the row. |
| sally | standalone | Sally manages the agent development lifecycle (ADLC) for every skill/agent Alex builds: proposing, drafting, versioning, registering, and landing agent definitions in GitHub repo esscott1/ClaudeCowork as a branch + PR (Alex merges), then tracking install and drift. Use whenever Alex asks to create, change, rename, retire, check in, sync, or review the status of any agent or skill, or says 'Sally'. Works from any surface (desktop app, phone, claude.ai web, cloud/scheduled); when the current session can't write to GitHub she queues the change in the JobSearch Project instead of improvising. |
