"""Versioned prompts. Each file starts with a `version:` line so eval results can cite it."""

from __future__ import annotations

from importlib.resources import files


def load(name: str) -> tuple[str, str]:
    """Return (version, body) for prompts/<name>.md."""
    raw = files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")
    first, _, body = raw.partition("\n")
    if not first.startswith("version:"):
        raise ValueError(f"prompt '{name}' must start with a 'version:' line")
    return first.removeprefix("version:").strip(), body.strip()
