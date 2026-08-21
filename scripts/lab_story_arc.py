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
from agentic_dynamics.reporting.lab_contract import attach_contract

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
    return round(sum(lst) / len(lst), 4) if lst else 0.0


def compute(stories: list[dict]) -> dict:
    """Aggregate the per-session arc over the canonical story payloads.

    Split out of :func:`main` so the analysis is testable without touching the registry
    or the filesystem.
    """
    by_session = defaultdict(lambda: {"cost": [], "tokens": [], "tests": [], "n": 0})
    by_cond_session = defaultdict(lambda: {"cost": [], "n": 0})
    by_model_session = defaultdict(lambda: defaultdict(lambda: {"cost": [], "n": 0}))

    for d in stories:
        model = _short_model(d.get("model", "unknown"))
        # `_canonical_condition` is the relabelled condition the resolver computed;
        # the raw `perturbation_condition` is deliberately not used here.
        cond = d.get("_canonical_condition") or "clean"
        for s in d.get("sessions", []):
            sn = s.get("session_number", 0)
            if not sn:
                continue
            cost = s.get("cost_usd", 0) or 0
            a = s.get("agentic", {}) or {}
            tokens = a.get("total_tokens", 0) or s.get("total_tokens", 0) or 0
            tests = a.get("tests_total", 0) or 0
            by_session[sn]["cost"].append(cost)
            by_session[sn]["tokens"].append(tokens)
            by_session[sn]["tests"].append(tests)
            by_session[sn]["n"] += 1
            by_cond_session[(cond, sn)]["cost"].append(cost)
            by_cond_session[(cond, sn)]["n"] += 1
            by_model_session[model][sn]["cost"].append(cost)
            by_model_session[model][sn]["n"] += 1

    sessions = []
    for sn in sorted(by_session):
        v = by_session[sn]
        sessions.append(
            {
                "session_number": sn,
                "task_type": SESSION_LABELS.get(sn, "?"),
                "n": v["n"],
                "avg_cost": _avg(v["cost"]),
                "avg_tokens": round(_avg(v["tokens"]), 0),
                "avg_tests": round(_avg(v["tests"]), 1),
            }
        )

    # Snowball factor: session 5 cost / session 1 cost.
    s1 = sessions[0]["avg_cost"] if sessions else 0
    s5 = sessions[-1]["avg_cost"] if sessions else 0
    snowball = round(s5 / s1, 2) if s1 else 0.0

    return {
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
            f"{cond}_s{sn}": _avg(v["cost"]) for (cond, sn), v in sorted(by_cond_session.items())
        },
        "by_model": {
            m: {str(sn): _avg(v["cost"]) for sn, v in sorted(sessions_map.items())}
            for m, sessions_map in sorted(by_model_session.items())
        },
    }


def main():
    tables = load_canonical_tables("story")
    output = compute(tables.stories)
    # The contract records WHICH corpus produced these numbers; build_data re-checks it.
    # Record scope (public-truth review P1): every current story is consumed, so
    # eligible == used == resolved — declared explicitly, not via a permissive default.
    attach_contract(
        output,
        LAB,
        tables,
        n_eligible_records=len(tables.stories),
        n_used_records=len(tables.stories),
    )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(f"  canonical input: {len(tables.stories)} stories ({tables.identity.registry_version})")
    for s in output["sessions"]:
        print(
            f"  session {s['session_number']} ({s['task_type']:14s}) n={s['n']:4d} "
            f"cost=${s['avg_cost']:>7.4f} tokens={s['avg_tokens']:>7.0f} tests={s['avg_tests']}"
        )
    print(f"Snowball factor (S5/S1): {output['summary']['snowball_factor']}x")


if __name__ == "__main__":
    main()
