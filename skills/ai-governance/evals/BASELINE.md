# Eval baseline: ai-governance

The reference result to compare against when `sally-audit` changes. Rerun the same command after the change, put both tables in the PR, and explain any case that moved.

**Run:** 2026-10-15 · plugin 0.1.2 · Claude Code 2.1.289 (default model) · Windows (these cases need no shell) · 3 runs per case, with the plugin only.

```bash
claude plugin eval skills/ai-governance --runs 3 --ablation none -j 4 --trust-plugin --no-publish --output-dir ../eval-runs/<date>
```

| Case | Score (3 runs) | Cost per run |
|---|---|---|
| `sally-audit-full-audit` | 1.00 · 1.00 · 1.00 | $0.47-0.48 |
| `sally-audit-single-skill` | 1.00 · 1.00 · 1.00 | $0.20-0.21 |
| `sally-audit-refuses-to-fix` | 1.00 · 1.00 · 1.00 | $0.45-0.47 |
| `sally-audit-all-in-sync` | 1.00 · 1.00 · 1.00 | $0.40-0.41 |
| `sally-audit-description-only` | 1.00 · 1.00 · 1.00 | $0.31-0.32 |
| `sally-audit-duplicate-install` | 1.00 · 1.00 · 1.00 | $0.46-0.47 |
| `sally-audit-script-drift` | 1.00 · 1.00 · 1.00 | $0.16 |
| `sally-audit-repo-health` | 1.00 · 1.00 · 1.00 | $0.44 |

Total: 24 runs, $8.78, about 5 minutes at `-j 4`.

**Before this baseline,** a first single-run pass found two problems, both fixed here:
- sally-audit flagged a category's `"skills": ["./"]` as a marketplace mismatch, an over-reading of its own new rule. The skill's wording was fixed.
- Two LLM-judged checks failed once and passed on rerun. Their criteria were split into deterministic checks, or worded around intent rather than exact phrasing.
