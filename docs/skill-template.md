# SKILL.md conventions used in this repo

Every skill here follows the same shape so they're easy to skim side by side, whatever category they're in.

## Frontmatter

```yaml
---
name: "skill-name-in-kebab-case"
description: "One or two sentences: what it does, and — critically — when it should (and shouldn't) run. If it's schedule-bound, device-bound, or on-demand-only, say so here, not just in the body."
---
```

The `description` is what a scheduler or an agent picking a skill actually reads to decide relevance, so front-load the trigger condition, not just the capability.

## Body sections (use what applies, skip what doesn't)

- **One-line summary** — what this skill does and, if it's one half of a pipeline, how it relates to the other half(s).
- **Key files / systems** — exact IDs, paths, sheet/tab names, connector names it depends on. Specific enough that a rerun doesn't require re-discovering them.
- **Numbered procedure** — the actual steps, in order. Call out any non-obvious gotchas inline (e.g. a known bug in a library, a rate limit, a site that blocks fetches) as an `IMPORTANT:` note rather than burying it in prose.
- **Known constraints** — what this skill will *never* do (e.g. advance a status, send email, delete data) and what it depends on that, if missing, means it should stop and say so rather than improvising.
- **End-of-run summary** — what it reports back when done, so a human (or the next skill in a pipeline) knows what happened without re-reading logs.

## Category READMEs

Each `skills/<category>/README.md` is a short index for that category only — one line on what the category is for, then a table of its skills with trigger + dependencies. The root `README.md` links to category READMEs, not to individual skills, so it stays skimmable as the count grows.
