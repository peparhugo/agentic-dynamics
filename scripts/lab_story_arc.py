"""
Lab Book: Story Arc — does cost compound across the 5-session story?

Aggregates per-session cost, tokens, and tests across the canonical story corpus,
broken down by session number (the greenfield -> cross-cutting arc) and by
perturbation condition. This is the Snowball Rule measured directly.

CANONICAL INPUT (semantic-integrity release, phase s2)
------------------------------------------------------
This lab is publication-eligible, so it consumes the registry resolver
(``agentic_dynamics.reporting.canonical_corpus``) and nothing else — no
``_results_summary.json``, no ``stories/*.json`` glob. The resolver returns only
``lifecycle_state == "current"`` story rows, so tombstoned cells cannot reach the
website, and it applies the no-op condition relabel once
(``docs/data_integrity_findings.md`` treatment rule 1) so this lab reports the
*corrected* condition rather than the raw label.

The output embeds a ``lab_contract`` block (input dataset id, manifest hash, registry
version, metric definition version, data-integrity policy, external-service
requirement). ``build_data.py`` re-checks that hash against the current manifest and
refuses to publish a stale artifact.

Usage:
    python scripts/lab_story_arc.py

Output:
    experiments/results/lab_story_arc.json
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.reporting.canonical_corpus import load_canonical_tables
from agentic_dynamics.reporting.lab_contract import (
    ContributionReport,
    attach_contribution,
    record_id,
)
from agentic_dynamics.reporting.measurement_coverage import cost_captured, cost_coverage

#: This script's name, as classified in scripts/lab_manifest.json — the contract key.
LAB = "lab_story_arc.py"
OUTPUT_PATH = Path("experiments/results/lab_story_arc.json")

SESSION_LABELS = {
    1: "greenfield",
    2: "feature",
    3: "integration",
    4: "refactor",
    5: "cross_cutting",
}


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _avg(lst):
    """Mean with a 0.0 fallback for countable fields (tokens, tests) — 0 is a real value."""
    return round(sum(lst) / len(lst), 4) if lst else 0.0


def _captured_avg(lst):
    """Mean over captured values only; ``None`` when nothing captured (m2 null-not-zero)."""
    return round(sum(lst) / len(lst), 4) if lst else None


def compute(stories: list[dict]) -> tuple[dict, ContributionReport]:
    """Aggregate the per-session arc over the canonical story payloads.

    Returns ``(result, contribution)`` (m3): every current story is consumed, so the
    contribution reports ``used == resolved`` with no exclusions.

    Split out of :func:`main` so the analysis is testable without touching the registry
    or the filesystem.
    """
    by_session = defaultdict(lambda: {"cost": [], "tokens": [], "tests": [], "n": 0})
    by_cond_session = defaultdict(lambda: {"cost": [], "n": 0})
    by_model_session = defaultdict(lambda: defaultdict(lambda: {"cost": [], "n": 0}))
    used_refs: list[str] = []

    for d in stories:
        model = _short_model(d.get("model", "unknown"))
        used_refs.append(record_id(d))
        # `_canonical_condition` is the relabelled condition the resolver computed;
        # the raw `perturbation_condition` is deliberately not used here.
        cond = d.get("_canonical_condition") or "clean"
        for s in d.get("sessions", []):
            sn = s.get("session_number", 0)
            if not sn:
                continue
            # m2 null-not-zero: an absent/zero session cost is "not captured" and must not
            # be inserted into the average as 0 (the review's P1 story-arc finding).
            cost = s.get("cost_usd")
            a = s.get("agentic", {}) or {}
            tokens = a.get("total_tokens") or s.get("total_tokens")
            tests = a.get("tests_total", 0) or 0
            if tokens is not None:
                by_session[sn]["tokens"].append(tokens)
            by_session[sn]["tests"].append(tests)
            by_session[sn]["n"] += 1
            if cost_captured(cost):
                by_session[sn]["cost"].append(cost)
                by_cond_session[(cond, sn)]["cost"].append(cost)
                by_model_session[model][sn]["cost"].append(cost)
            by_cond_session[(cond, sn)]["n"] += 1
            by_model_session[model][sn]["n"] += 1

    sessions = []
    for sn in sorted(by_session):
        v = by_session[sn]
        cost_stats = cost_coverage(v["cost"], n_total=v["n"])
        sessions.append(
            {
                "session_number": sn,
                "task_type": SESSION_LABELS.get(sn, "?"),
                "n": v["n"],
                # Captured-only mean (None when nothing captured) + the five shared
                # coverage fields, so a session's cost denominator is explicit.
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "total_captured_cost": cost_stats["total_captured_cost"],
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "cost_coverage": cost_stats["cost_coverage"],
                "avg_tokens": round(_avg(v["tokens"]), 0) if v["tokens"] else None,
                "avg_tests": round(_avg(v["tests"]), 1),
            }
        )

    # Snowball factor: session 5 cost / session 1 cost (None when either is un-captured).
    s1 = sessions[0]["avg_cost"] if sessions else None
    s5 = sessions[-1]["avg_cost"] if sessions else None
    snowball = round(s5 / s1, 2) if (s1 and s5) else None

    result = {
        "experiment_id": "lab_story_arc",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "snowball_factor": snowball,
            "session1_cost": s1,
            "session5_cost": s5,
            "stories": len(stories),
        },
        "sessions": sessions,
        "by_condition": {
            f"{cond}_s{sn}": _captured_avg(v["cost"])
            for (cond, sn), v in sorted(by_cond_session.items())
        },
        "by_model": {
            m: {str(sn): _captured_avg(v["cost"]) for sn, v in sorted(sessions_map.items())}
            for m, sessions_map in sorted(by_model_session.items())
        },
    }
    contribution = ContributionReport.of(used_record_refs=used_refs)
    return result, contribution


def main():
    tables = load_canonical_tables("story")
    output, contribution = compute(tables.stories)
    attach_contribution(output, LAB, tables, contribution)

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(f"  canonical input: {len(tables.stories)} stories ({tables.identity.registry_version})")
    for s in output["sessions"]:
        cost = "—" if s["avg_cost"] is None else f"${s['avg_cost']:>7.4f}"
        print(
            f"  session {s['session_number']} ({s['task_type']:14s}) n={s['n']:4d} "
            f"cost={cost} tokens={s['avg_tokens']:>7.0f} tests={s['avg_tests']}"
        )
    print(f"Snowball factor (S5/S1): {output['summary']['snowball_factor']}x")


if __name__ == "__main__":
    main()
