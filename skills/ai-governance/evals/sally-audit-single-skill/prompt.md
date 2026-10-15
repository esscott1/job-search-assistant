---
tags: [sally-audit]
runs: 3
max_turns: 40
allowed_tools: [Read, Glob, Grep, Skill]
---

[Eval fixture mode: the world for this task is the folder `evals/sally-audit-single-skill/world/` inside the ai-governance plugin's directory. That directory is the parent of the sally-audit skill's base directory, which is shown when the skill loads. Read the world's CONTEXT.md first. Treat its `repo/` folder as the main branch of the skills repository and its `installed/` folder as what is installed in the maintainer's Claude account. Read only inside the world folder; do not use the network or any other repository.]

Is my job-lead-tier2-scoring skill up to date with GitHub?
