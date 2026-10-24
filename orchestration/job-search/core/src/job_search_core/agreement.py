"""How far the plugin (A) and the pipeline (B) agree, measured in code with no model call.

Milestone 5's comparison and the shadow week's agreement report (roadmap milestone 6e) both use
it. Requirements from two evidence tables are matched one-to-one by a deterministic text
similarity, so the measurement adds no judgment of its own.

The report's numbers are counts and rates only; the job IDs behind them are in `details`, for
the person running it, and never go into the committed Markdown.
"""

from __future__ import annotations

import re
import statistics
from datetime import date

from pydantic import ValidationError

from . import policy
from .domain import EvidenceTable, Job, KnownJob, PluginJob

# Words that say nothing about which requirement it is ("5+ years of experience with ...").
STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to",
    "with", "within", "experience", "experienced", "ability", "proven", "demonstrated",
    "strong", "knowledge", "working", "including", "plus", "year", "years", "skill", "skills",
    "certification", "certified", "certificate", "management", "manage", "managing", "managed",
}  # fmt: skip
# Calibrated on the gold tables: paraphrases of one requirement score 0.5 or more; different
# requirements that share only a generic word ("vendor management", "change management")
# score below it, which test_no_two_gold_requirements_are_confusable checks.
MATCH_THRESHOLD = 0.5


def words(text: str) -> set[str]:
    out = set()
    for w in re.sub(r"[^a-z0-9+]+", " ", text.lower()).split():
        if w in STOPWORDS:
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


def similarity(a: str, b: str) -> float:
    """Dice coefficient of the two texts' significant words."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return 2 * len(wa & wb) / (len(wa) + len(wb))


def match(reqs_a: list[dict], reqs_b: list[dict]) -> list[tuple[int, int, float]]:
    """One-to-one matches, best first, each at or above MATCH_THRESHOLD."""
    scored = sorted(
        (
            (similarity(ra["text"], rb["text"]), i, j)
            for i, ra in enumerate(reqs_a)
            for j, rb in enumerate(reqs_b)
        ),
        reverse=True,
    )
    used_a, used_b, pairs = set(), set(), []
    for sim, i, j in scored:
        if sim < MATCH_THRESHOLD:
            break
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            pairs.append((i, j, round(sim, 2)))
    return pairs


def compare_tables(a: dict, b: dict) -> dict:
    """How far two evidence tables agree: requirement overlap, then the calls on what matched."""
    ra, rb = a["requirements"], b["requirements"]
    pairs = match(ra, rb)
    n = len(pairs)
    return {
        "overlap": n / max(len(ra), len(rb), 1),
        "evidence_agree": sum(ra[i]["evidence"] == rb[j]["evidence"] for i, j, _ in pairs) / n
        if n
        else 0.0,
        "type_agree": sum(ra[i]["type"] == rb[j]["type"] for i, j, _ in pairs) / n if n else 0.0,
        "title_agree": a["title_seniority"] == b["title_seniority"],
        "arrangement_agree": a["work_arrangement"] == b["work_arrangement"],
        "unmatched_first": [
            r["text"] for k, r in enumerate(ra) if k not in {i for i, _, _ in pairs}
        ],
        "unmatched_second": [
            r["text"] for k, r in enumerate(rb) if k not in {j for _, j, _ in pairs}
        ],
        "inexact_matches": [
            {"first": ra[i]["text"], "second": rb[j]["text"], "similarity": s}
            for i, j, s in pairs
            if s < 1
        ],
    }


# --- The shadow week ----------------------------------------------------------------------

_EVIDENCE_BLOCK = re.compile(r"^## Evidence table\s*```(?:json)?\s*(\{.*?\})\s*```", re.M | re.S)


def fit_report_evidence(text: str) -> EvidenceTable | None:
    """The evidence table in a plugin fit report (its `## Evidence table` JSON block), or None
    if there isn't a valid one (job-tracker, **Job files in Drive**)."""
    found = _EVIDENCE_BLOCK.search(text)
    if not found:
        return None
    try:
        return EvidenceTable.model_validate_json(found.group(1))
    except ValidationError:
        return None


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _mean(values) -> float | None:
    values = list(values)
    return round(statistics.fmean(values), 3) if values else None


def _scores(pairs: list[tuple[int, int]]) -> dict:
    """Exact and within-±1 agreement of (A, B) score pairs."""
    return {
        "pairs": len(pairs),
        "exact": _rate(sum(a == b for a, b in pairs), len(pairs)),
        "within_1": _rate(sum(abs(a - b) <= 1 for a, b in pairs), len(pairs)),
    }


def pair_leads(
    a_leads: list[PluginJob], b_leads: list[Job]
) -> tuple[list[tuple[PluginJob, Job]], list[PluginJob], list[Job]]:
    """Each of B's leads matched to at most one of A's, by intake's own dedup rule (the same
    canonical URL, or the same company and title): (pairs, A's only, B's only)."""
    unmatched = {a.id: a for a in a_leads}
    pairs, b_only = [], []
    for b in b_leads:
        known = [
            KnownJob(id=a.id, company=a.company, title=a.title, canonical_url=a.canonical_url)
            for a in unmatched.values()
        ]
        same = policy.find_duplicate(b.canonical_url, b.company, b.title, known)
        if same:
            pairs.append((unmatched.pop(same.id), b))
        else:
            b_only.append(b)
    return pairs, list(unmatched.values()), b_only


def shadow_report(
    plugin_jobs: list[PluginJob],
    b_jobs: list[Job],
    fit_report,
    since: date,
) -> dict:
    """The shadow week's agreement, from the plugin's Job Log, B's tracker and the plugin's fit
    reports (`fit_report(job_id, run)` returns a report's text, or None).

    - **Intake:** leads from job-alert email found on or after `since`, A's and B's, paired by
      `pair_leads`. A's career-site leads are left out: B doesn't scan career sites. Tier 1
      scores are compared where both rows are still Tier 1 (a Tier 2 run replaces A's score).
    - **Tier 2:** each job B mirrored whose plugin run finished on or after `since`, if A hasn't
      rescored it since (then it's pending, and B mirrors it on its next run): the scores, and
      the evidence tables from A's fit report and B's run.
    """
    a_leads = [a for a in plugin_jobs if a.gmail_message_id and a.found_on and a.found_on >= since]
    b_leads = [b for b in b_jobs if b.gmail_message_id and b.found_on and b.found_on >= since]
    pairs, a_only, b_only = pair_leads(a_leads, b_leads)
    tier1 = [(a, b) for a, b in pairs if a.scoring_tier == "T1" and b.scoring_tier == "T1"]
    tier1 = [(a, b) for a, b in tier1 if a.score is not None and b.fit]

    by_id = {a.id: a for a in plugin_jobs}
    mirrored = [b for b in b_jobs if b.plugin_run is not None and b.id in by_id]
    in_window = [b for b in mirrored if by_id[b.id].tier2_date and by_id[b.id].tier2_date >= since]
    current = [b for b in in_window if by_id[b.id].fit_run == b.plugin_run]
    pending = [b.id for b in in_window if by_id[b.id].fit_run != b.plugin_run]
    tier2 = [(by_id[b.id], b) for b in current if by_id[b.id].score is not None and b.fit]

    tables, no_table = [], []
    for a, b in tier2:
        text = fit_report(a.id, a.fit_run)
        a_table = fit_report_evidence(text) if text else None
        if a_table is None or b.fit.evidence is None:
            no_table.append(a.id)
            continue
        tables.append((a.id, compare_tables(a_table.model_dump(), b.fit.evidence.model_dump())))

    return {
        "since": since.isoformat(),
        "intake": {
            "a_leads": len(a_leads),
            "b_leads": len(b_leads),
            "both": len(pairs),
            "a_only": len(a_only),
            "b_only": len(b_only),
            "share_of_a_found_by_b": _rate(len(pairs), len(a_leads)),
            "share_of_b_found_by_a": _rate(len(pairs), len(b_leads)),
            "tier1": {
                **_scores([(a.score, b.fit.score) for a, b in tier1]),
                "not_comparable": len(pairs) - len(tier1),
            },
        },
        "tier2": {
            **_scores([(a.score, b.fit.score) for a, b in tier2]),
            "pending": len(pending),
            "requirements": {
                "tables": len(tables),
                "overlap": _mean(t["overlap"] for _, t in tables),
                "evidence_agree": _mean(t["evidence_agree"] for _, t in tables),
                "title_agree": _mean(t["title_agree"] for _, t in tables),
                "arrangement_agree": _mean(t["arrangement_agree"] for _, t in tables),
                "no_table": len(no_table),
            },
        },
        "details": {  # for the person running the report; never committed
            "a_only": [a.id for a in a_only],
            "b_only": [b.id for b in b_only],
            "pairs": [(a.id, b.id) for a, b in pairs],
            "tier1_apart": [
                (a.id, b.id, a.score, b.fit.score)
                for a, b in tier1
                if abs(a.score - b.fit.score) > 1
            ],
            "tier2_apart": [
                (a.id, a.score, b.fit.score) for a, b in tier2 if abs(a.score - b.fit.score) > 1
            ],
            "tier2_pending": pending,
            "low_overlap": [
                (job_id, round(t["overlap"], 2)) for job_id, t in tables if t["overlap"] < 0.8
            ],  # fmt: skip
            "no_table": no_table,
        },
    }


def _shown(value) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:.0%}"
    return str(value)


def render(report: dict, generated: date) -> str:
    """The report as Markdown: counts and rates only, no companies, titles or job IDs."""
    i, t2 = report["intake"], report["tier2"]
    t1, req = i["tier1"], t2["requirements"]
    rows = [
        "# Shadow week: the plugin (A) and the pipeline (B) side by side",
        "",
        f"From {report['since']}, generated {generated.isoformat()}. Counts and rates only.",
        "",
        "## Intake (job-alert email)",
        "",
        "| | |",
        "|---|---|",
        f"| A's leads | {i['a_leads']} |",
        f"| B's leads | {i['b_leads']} |",
        f"| Found by both | {i['both']} |",
        f"| A only | {i['a_only']} |",
        f"| B only | {i['b_only']} |",
        f"| Share of A's leads B also found | {_shown(i['share_of_a_found_by_b'])} |",
        f"| Share of B's leads A also found | {_shown(i['share_of_b_found_by_a'])} |",
        "",
        "## Tier 1 scores (leads found by both, both still Tier 1)",
        "",
        "| | |",
        "|---|---|",
        f"| Pairs compared | {t1['pairs']} |",
        f"| Same score | {_shown(t1['exact'])} |",
        f"| Within ±1 | {_shown(t1['within_1'])} |",
        f"| Not comparable (A has scored Tier 2 since) | {t1['not_comparable']} |",
        "",
        "## Tier 2 scores (the same saved JD)",
        "",
        "| | |",
        "|---|---|",
        f"| Jobs compared | {t2['pairs']} |",
        f"| Same score | {_shown(t2['exact'])} |",
        f"| Within ±1 | {_shown(t2['within_1'])} |",
        f"| Pending (A rescored after B's run) | {t2['pending']} |",
        f"| Evidence tables compared | {req['tables']} |",
        f"| Requirement overlap (mean) | {_shown(req['overlap'])} |",
        f"| Same evidence call on matched requirements (mean) | {_shown(req['evidence_agree'])} |",
        f"| Same title call | {_shown(req['title_agree'])} |",
        f"| Same work-arrangement call | {_shown(req['arrangement_agree'])} |",
        f"| No fit report to compare | {req['no_table']} |",
        "",
    ]
    return "\n".join(rows)
