# data/ (gitignored)

Everything in this folder except this README is ignored by git. It holds your personal data:

| Path | What |
|---|---|
| `job-search-profile.md` | Your job-search profile, the plugin's file. It names your full resume, and scoring reads its Target roles and Location |
| `Full-Resume.md` (the name your profile gives) | Your full resume in Markdown, your whole career history: the source of truth for scoring and tailoring |
| `tracker.db` | SQLite tracker (system of record for job status) |
| `checkpoints.db` | LangGraph checkpoints (one thread per job) |
| `resumes/` | Tailored resumes, one per job |
| `google/credentials.json` | OAuth client secret downloaded from Google Cloud |
| `google/token.json` | Your OAuth refresh token — treat it like a password |
