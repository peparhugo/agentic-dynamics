"""
Retrospective session-routing evaluation — the evidence-seed study for the
session-routing experiment (experiments/definitions/cap_session_routing_evidence.yaml).

Replays the attempt lineage already on disk — the workflow-run corpus
(experiments/results/workflows/<spec>/*.json, per-run phase records) — as
counterfactual arms over SESSION TRANSITIONS, the same shape as
routing.simulate_strategies but for session policy instead of model policy:

  continue     — the next phase reused the previous phase's session_id
  fork_cached  — new session_id, and the phase read token cache (cache_read_tokens > 0)
  fork_blind   — new session_id, no token-cache reuse
  escalate     — run-level: a failed run followed by a later successful run (any model change)

Null hypothesis (per the experiment spec): no arm outperforms `continue` on cost per
verified outcome. Coverage semantics follow reporting.measurement_coverage: an
uncaptured cost is null with zero coverage — never a zero-cost observation.

Usage:
    python scripts/retro_session_routing.py

Output:
    experiments/results/session_routing_retrospective.json   (machine-readable)
"""

import json
from collections import defaultdict
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

RESULTS = Path(__file__).resolve().parent.parent / "experiments" / "results"
WORKFLOWS = RESULTS / "workflows"
OUT = RESULTS / "session_routing_retrospective.json"

ARMS = ("continue", "fork_cached", "fork_blind", "escalate")


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _tokens_in(phase: dict) -> float | None:
    tokens = phase.get("tokens") or {}
    if isinstance(tokens, dict):
        return _num(tokens.get("in")) or _num(tokens.get("total"))
    return _num(tokens)


def collect_transitions() -> list[dict]:
    """One row per consecutive phase pair (prev, cur) across the workflow-run corpus."""
    rows = []
    for run_file in sorted(WORKFLOWS.glob("*/*.json")):
        try:
            run = json.loads(run_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(run, dict):
            continue
        phases = [p for p in (run.get("phases") or []) if isinstance(p, dict)]
        for prev, cur in zip(phases, phases[1:]):
            sid_prev, sid_cur = prev.get("session_id"), cur.get("session_id")
            if not sid_cur:
                continue
            cached = _num(cur.get("cache_read_tokens") or 0) > 0
            arm = "continue" if sid_cur == sid_prev else ("fork_cached" if cached else "fork_blind")
            rows.append({
                "spec": run.get("spec_name"),
                "model": run.get("model"),
                "arm": arm,
                "verified": cur.get("status") == "ok",
                "cost": _num(cur.get("cost_usd")),
                "cache_read": _num(cur.get("cache_read_tokens")),
                "tokens_in": _tokens_in(cur),
                "tokens_out": _num((cur.get("tokens") or {}).get("out")),
                "phase": cur.get("phase"),
            })
    return rows


def collect_escalations() -> list[dict]:
    """Run-level: a workflow whose earlier run failed and a later run (model change) passed."""
    rows = []
    by_spec = defaultdict(list)
    for run_file in sorted(WORKFLOWS.glob("*/*.json")):
        try:
            run = json.loads(run_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(run, dict):
            continue
        by_spec[run.get("spec_name")].append(run)
    for spec, runs in by_spec.items():
        if len(runs) < 2:
            continue
        runs.sort(key=lambda r: r.get("ended_at") or "")
        if not runs[-1].get("ok"):
            continue
        escalations = [r for r in runs[:-1] if not r.get("ok")]
        if not escalations:
            continue
        failed_cost = sum(_num(r.get("total_cost_usd")) or 0 for r in escalations)
        success = runs[-1]
        rows.append({
            "spec": spec,
            "model": escalations[-1].get("model"),
            "arm": "escalate",
            "verified": True,
            "cost": _num(success.get("total_cost_usd")) or 0 + failed_cost,
            "cache_read": None,
            "tokens_in": None,
            "tokens_out": None,
            "phase": "__escalation__",
        })
    return rows


def arm_stats(rows: list[dict]) -> dict:
    stats = {}
    for arm in ARMS:
        arm_rows = [r for r in rows if r["arm"] == arm]
        n = len(arm_rows)
        verified = sum(1 for r in arm_rows if r["verified"])
        costs = [r["cost"] for r in arm_rows if r["cost"] is not None]
        cached_obs = sum(1 for r in arm_rows if r["cache_read"] and r["cache_read"] > 0)
        reuse = [
            (r["cache_read"] or 0) / r["tokens_in"]
            for r in arm_rows
            if r["tokens_in"] and r["cache_read"] is not None
        ]
        stats[arm] = {
            "n": n,
            "verified": verified,
            "success_rate": round(verified / n, 4) if n else None,
            "cost": {
                "value": round(sum(costs) / len(costs), 4) if costs else None,
                "n_available": len(costs),
                "n_total": n,
                "coverage": round(len(costs) / n, 4) if n else 0.0,
            },
            "cost_per_verified_outcome": {
                "value": round(sum(costs) / verified, 4) if costs and verified else None,
                "n_available": len(costs),
                "n_verified": verified,
            },
            "cache_reuse_rate": round(cached_obs / n, 4) if n else None,
            "cache_token_ratio": round(sum(reuse) / len(reuse), 4) if reuse else None,
        }
    return stats


def main() -> None:
    rows = collect_transitions() + collect_escalations()
    stats = arm_stats(rows)
    by_spec = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_spec[r["spec"]][r["arm"]] += 1
    payload = {
        "study": "cap_session_routing_retrospective/v1",
        "source": "experiments/results/workflows/**/*.json (run-level phase transitions)",
        "arms": ARMS,
        "null_hypothesis": "no arm outperforms `continue` on cost per verified outcome",
        "notes": [
            "verified success = the phase committed with status ok (the per-phase gate)",
            "escalate is run-level (failed run(s) then a later successful run); cost includes the failed attempts",
            "coverage semantics: uncaptured cost is null with zero coverage, never zero",
        ],
        "arms": stats,
        "observations_by_spec": {k: dict(v) for k, v in sorted(by_spec.items())},
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT} — {len(rows)} transition observations across {len(by_spec)} workflow specs")
    for arm in ARMS:
        s = stats[arm]
        cost = s["cost"]["value"]
        print(
            f"  {arm:12s} n={s['n']:3d}  success={s['success_rate']}  "
            f"cost_mean={cost} (cov {s['cost']['coverage']})  "
            f"cache_reuse={s['cache_reuse_rate']}"
        )


if __name__ == "__main__":
    main()
