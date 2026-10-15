#!/usr/bin/env python3
"""Deterministic fit score for one job, from an evidence table the model has filled in.

The model's job is judgment: read the JD and the master resume and classify each item.
This script's job is arithmetic: turn those classifications into a 1-10 score the same
way every time, and explain how it got there.

Usage:
    python3 score.py evidence.json          # or pipe the JSON on stdin
Prints one JSON object: score, raw, caps_applied, breakdown, rubric_version.
Exits 2 with a message on stderr if the evidence table is invalid.

Weights live in the constants below and are documented in RUBRIC.md. Change both
together and bump RUBRIC_VERSION.
"""

from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_UP, Decimal

RUBRIC_VERSION = "1.1"

# How much each component contributes to the 0-10 raw score (sums to 1.0).
W_REQUIREMENTS = 0.70
W_TITLE = 0.20
W_ARRANGEMENT = 0.10

# A required qualification counts three times as much as a preferred ("nice to have") one.
WEIGHT_REQUIRED = 3.0
WEIGHT_PREFERRED = 1.0

EVIDENCE_CREDIT = {"strong": 1.0, "partial": 0.5, "none": 0.0}
TITLE_CREDIT = {"strong": 1.0, "partial": 0.5, "weak": 0.0}

# Judged against the Location section of the user's job-search profile.
ARRANGEMENT_CREDIT = {
    "remote": 1.0,
    "commutable_onsite": 1.0,  # office within the user's daily commute
    "commutable_hybrid": 1.0,
    "unknown": 0.5,
    "relocation_acceptable": 0.5,  # needs a move the profile says the user would make
    "relocation_required": 0.0,  # needs a move the user won't make
}
ARRANGEMENT_LABEL = {
    "remote": "Remote",
    "commutable_onsite": "Commutable on-site",
    "commutable_hybrid": "Commutable hybrid",
    "unknown": "Location unclear",
    "relocation_acceptable": "Relocation acceptable",
    "relocation_required": "Relocation required",
}
# Evidence tables written under rubric v1.0 are reused on a rescore; read their names.
ARRANGEMENT_ALIASES = {"colorado_onsite": "commutable_onsite", "colorado_hybrid": "commutable_hybrid"}

RELOCATION_CAP = 3  # hard ceiling for any job that needs a move the user won't make
LOW_REQUIRED_COVERAGE = 0.5  # below this share of required items met...
LOW_REQUIRED_CAP = 5  # ...the score can't go above this
TIER1_REQUIREMENTS_PRIOR = 0.6  # assumed coverage when no JD has been read
TIER1_CAP = 8  # a title-only screen never claims a top score


class EvidenceError(ValueError):
    pass


def _pick(value: object, allowed: dict, field: str) -> str:
    if value not in allowed:
        raise EvidenceError(f"{field} must be one of {sorted(allowed)}, got {value!r}")
    return value  # type: ignore[return-value]


def _round(x: float) -> int:
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _fmt(x: float) -> str:
    return f"{x:g}"


def score(evidence: dict) -> dict:
    mode = _pick(evidence.get("mode"), {"tier1": 0, "tier2": 0}, "mode")
    title = _pick(evidence.get("title_seniority"), TITLE_CREDIT, "title_seniority")
    arrangement = evidence.get("work_arrangement")
    arrangement = _pick(ARRANGEMENT_ALIASES.get(arrangement, arrangement), ARRANGEMENT_CREDIT, "work_arrangement")

    parts: list[str] = []
    caps: list[str] = []

    if mode == "tier2":
        items = evidence.get("requirements")
        if not isinstance(items, list) or not items:
            raise EvidenceError("tier2 needs a non-empty 'requirements' list")
        req_earned = req_total = pref_earned = pref_total = 0.0
        for i, item in enumerate(items):
            kind = _pick(item.get("type"), {"required": 0, "preferred": 0}, f"requirements[{i}].type")
            credit = EVIDENCE_CREDIT[_pick(item.get("evidence"), EVIDENCE_CREDIT, f"requirements[{i}].evidence")]
            if not str(item.get("text", "")).strip():
                raise EvidenceError(f"requirements[{i}].text is empty; quote the JD")
            if kind == "required":
                req_total += 1
                req_earned += credit
            else:
                pref_total += 1
                pref_earned += credit
        weighted_total = WEIGHT_REQUIRED * req_total + WEIGHT_PREFERRED * pref_total
        coverage = (WEIGHT_REQUIRED * req_earned + WEIGHT_PREFERRED * pref_earned) / weighted_total
        parts.append(
            f"Req {_fmt(req_earned)}/{_fmt(req_total)}" if req_total else "Req none listed"
        )
        parts.append(f"Pref {_fmt(pref_earned)}/{_fmt(pref_total)}")
        parts.append(f"coverage {coverage:.0%}")
        required_share = req_earned / req_total if req_total else 1.0
    else:
        coverage = TIER1_REQUIREMENTS_PRIOR
        parts.append(f"no JD (assumed {coverage:.0%})")
        required_share = 1.0

    parts.append(f"Title {title}")
    parts.append(ARRANGEMENT_LABEL[arrangement])

    raw = 10 * (
        W_REQUIREMENTS * coverage
        + W_TITLE * TITLE_CREDIT[title]
        + W_ARRANGEMENT * ARRANGEMENT_CREDIT[arrangement]
    )
    final = max(1, min(10, _round(raw)))

    if mode == "tier1" and final > TIER1_CAP:
        final = TIER1_CAP
        caps.append(f"Tier 1 max {TIER1_CAP}")
    if required_share < LOW_REQUIRED_COVERAGE and final > LOW_REQUIRED_CAP:
        final = LOW_REQUIRED_CAP
        caps.append(f"<{LOW_REQUIRED_COVERAGE:.0%} of required met, max {LOW_REQUIRED_CAP}")
    if arrangement == "relocation_required" and final > RELOCATION_CAP:
        final = RELOCATION_CAP
        caps.append(f"relocation max {RELOCATION_CAP}")

    breakdown = f"Rubric v{RUBRIC_VERSION} | " + " · ".join(parts) + f" | raw {raw:.1f} → {final}"
    if caps:
        breakdown += " (" + "; ".join(caps) + ")"

    return {
        "score": final,
        "raw": round(raw, 2),
        "caps_applied": caps,
        "breakdown": breakdown,
        "rubric_version": RUBRIC_VERSION,
    }


def main() -> int:
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    try:
        result = score(json.load(src))
    except (EvidenceError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        print(f"invalid evidence: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
