"""The parts of the job-search profile the pipeline reads.

The profile is the Markdown file the plugin's `job-search-profile` skill writes, so one file
serves both approaches. It names the full resume (Candidate → Full resume). Only its Target
roles and Location sections go into the scoring prompt: the rubric judges title and
seniority against the first and work arrangement against the second.
"""

from __future__ import annotations

import re

SCORING_SECTIONS = ("Target roles", "Location")


class ProfileError(ValueError):
    pass


def sections(markdown: str, names: tuple[str, ...] = SCORING_SECTIONS) -> str:
    """Return the named `## ` sections, heading included, in the order asked for."""
    found: dict[str, str] = {}
    for block in re.split(r"(?m)^(?=## )", markdown):
        heading = (
            block.splitlines()[0].removeprefix("## ").strip() if block.startswith("## ") else ""
        )
        if heading in names:
            found[heading] = block.strip()
    missing = [n for n in names if n not in found]
    if missing:
        raise ProfileError(f"job-search profile has no '## {missing[0]}' section")
    return "\n\n".join(found[n] for n in names)


def full_resume_name(markdown: str) -> str:
    """The file name on the profile's `- Full resume:` line, under `## Candidate`."""
    candidate = sections(markdown, ("Candidate",))
    match = re.search(r"(?m)^- Full resume:[ \t]*(\S.*?)\s*$", candidate)
    if not match:
        raise ProfileError('Profile setting "Candidate → Full resume" is blank')
    return match.group(1)
