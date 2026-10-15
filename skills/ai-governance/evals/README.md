# Evals: ai-governance

Eval cases for [`sally-audit`](../sally-audit/SKILL.md), the read-only skill that reports which skills are in sync, drifted, unregistered or installed twice. They use the same format and conventions as the job-search suite; [its README](../../job-search-assistant/evals/README.md) covers how to run cases, the grader types and the redaction rules.

```bash
claude plugin eval skills/ai-governance --trust-plugin --no-publish --output-dir ../eval-runs/ai-governance
```

These cases need no shell, so they run on Windows too.

## How a case gives the skill a world to audit

sally-audit reads two things: the repository's `main` branch and what's installed in the maintainer's Claude account. Each case freezes both in its own `world/` folder:

- `world/repo/`: the repository as `main` looks in that scenario.
- `world/installed/`: the installed skills, with `INSTALLED.md` saying what the session can see and how each skill is installed.
- `world/CONTEXT.md`: open PRs, Sally's queue and today's date.

The case's `case.yaml` grants read access to that folder (`context.add_dirs: ["world"]`). The runner grants access to the folder where it sits, but doesn't tell the agent where that is. So the prompt names the path relative to the plugin, which the agent learns when the skill loads. The CLI only lets a case grant access inside its own folder, so a world shared by several cases is copied into each. `test_eval_worlds.py` keeps the copies identical and checks that no world holds a file ID or a personal email address.

Freezing the worlds means a case keeps testing the same situation after the real drift it was drawn from is fixed. The worlds use a synthetic maintainer (Alex Example) and placeholders (`<TRACKER_FILE_ID>`, `recruiter@example.com`), and keep the repository layout of the time they were captured (a `personal-productivity` category, an older registry format). `lint-check`, `release-notes` and PR #14 are invented for the script-drift and repo-health cases.

## Cases

| Case | World | What it proves |
|---|---|---|
| `sally-audit-full-audit` | real-snapshot | Finds the real drift and gets the direction right: two skills installed-ahead, one unregistered, sally repo-ahead, sally-audit not installed |
| `sally-audit-single-skill` | real-snapshot | Answers a narrow question without telling the maintainer to reinstall an older version |
| `sally-audit-refuses-to-fix` | real-snapshot | "Audit and fix it, push to GitHub": still audits, stays read-only, hands the fix to Sally |
| `sally-audit-all-in-sync` | all-in-sync | No false alarms |
| `sally-audit-description-only` | description-only | Never claims "in sync" from a description alone; reports `unverified` |
| `sally-audit-duplicate-install` | duplicate-install | Spots a skill installed both standalone and through its plugin |
| `sally-audit-script-drift` | script-drift | Compares the whole folder, not just SKILL.md |
| `sally-audit-repo-health` | repo-defects | Marketplace gap, broken script reference, orphan registry row, stale PR |

Every case also checks that nothing was written or edited and no shell command ran, because the skill is read-only. The no-plugin baseline (`--ablation with-without`, the default) shows what the skill adds over Claude reading the same folders unaided.
