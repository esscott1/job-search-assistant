"""The parts of the job-search profile the pipeline reads.

The profile is the Markdown file the plugin's `job-search-profile` skill writes, so one file
serves both approaches. It names the full resume (Candidate → Full resume). Only its Target
roles and Location sections go into the scoring prompt: the rubric judges title and
seniority against the first and work arrangement against the second.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SCORING_SECTIONS = ("Target roles", "Location")


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class EmailSource:
    """A row of the profile's Email sources table: which sender to search, and its label."""

    label: str
    sender: str
    notes: str = ""


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


def _section(markdown: str, name: str) -> str:
    """One `## ` section's body, or "" when the profile has none (a missing section is empty)."""
    try:
        return sections(markdown, (name,)).split("\n", 1)[-1]
    except ProfileError:
        return ""


def email_sources(markdown: str) -> list[EmailSource]:
    """The Email sources table (Source | Sender | Notes), header and divider rows left out."""
    out = []
    for line in _section(markdown, "Email sources").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[1] or cells[0] == "Source" or set(cells[0]) <= set("-: "):
            continue
        out.append(EmailSource(cells[0], cells[1], cells[2] if len(cells) > 2 else ""))
    return out


def never_scan(markdown: str) -> list[str]:
    """Senders listed under Never scan: their mail is never read for leads."""
    body = _section(markdown, "Never scan")
    return [m.strip() for m in re.findall(r"(?m)^- (.+)$", body) if m.strip()]


def never_interested(markdown: str) -> list[str]:
    """The comma-separated terms on Target roles → Never interested."""
    match = re.search(r"(?m)^- Never interested:[ \t]*(.*)$", _section(markdown, "Target roles"))
    return [t.strip() for t in match.group(1).split(",") if t.strip()] if match else []
