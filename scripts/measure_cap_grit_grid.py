"""E4 grid measurement — run the registered rules over the grid ledger.

Phase x3 of ``cap_grit_grid_execute`` (runplan §6, step 5): run the spec's registered
measurement rules over ``experiments/results/cap_grit_grid_ledger.json`` and write
``experiments/results/cap_grit_grid_metrics.json``.

Coverage-first discipline (the spec's m2 guard): cost_coverage_ratio and
test_verification_coverage_ratio are computed and reported BEFORE any denominator use;
a rule whose inputs are absent returns an explicit "unmeasured" result (NaN / n=0) —
never a fabricated number. This mirrors ``compile_experiment.evaluate_rules``'s own
contract ("a rule with no data yields an explicit unmeasured result").

Rules (per the spec):
  attempt_coverage_precheck  — cost + test-verification coverage ratios over attempts
  grit                      — grit/retention/grit_auc/recovery_premium (compile evaluator)
  verified_success_rate     — per cell, over captured test_executed_success
  cost_per_verified_outcome — captured-only intersection (numerator over captured cost,
                              denominator over non-null test_executed_success from the SAME set)
  rework_cost_report        — rework_cost per cell
  retry_policy_fidelity     — realized retry rate vs declared policy (finding 4), violations
  arm_comparison            — baseline vs grit_retry regret stratified by condition_strength

Usage:
    python scripts/measure_cap_grit_grid.py
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import _bootstrap  # noqa: E402
except ImportError:
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.experiment.compile_experiment import evaluate_rules

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO_ROOT / "experiments/results/cap_grit_grid_ledger.json"
SPEC_PATH = REPO_ROOT / "experiments/definitions/cap_grit_strength_grid.yaml"
OUT_PATH = REPO_ROOT / "experiments/results/cap_grit_grid_metrics.json"


def _num(value):
    return value if isinstance(value, (int, float)) else None


def attempt_coverage_precheck(attempts: list[dict]) -> dict:
    """Coverage FIRST: how many attempts captured the two non-optional fields?"""
    n = len(attempts)
    cost_ok = sum(1 for a in attempts if a.get("actual_cost") is not None)
    test_ok = sum(1 for a in attempts if a.get("test_executed_success") is not None)
    return {
        "n_attempts": n,
        "cost_coverage_ratio": round(cost_ok / n, 4) if n else None,
        "test_verification_coverage_ratio": round(test_ok / n, 4) if n else None,
        "n_cost_captured": cost_ok,
        "n_test_verification_captured": test_ok,
    }


def verified_success_rate_per_cell(cells: list[dict]) -> list[dict]:
    """Per-cell verified success rate over captured test_executed_success."""
    out = []
    for c in cells:
        attempts = c.get("attempts") or []
        captured = [a.get("test_executed_success") for a in attempts
                    if a.get("test_executed_success") is not None]
        out.append({
            "cell_id": c["cell_id"],
            "condition_strength": c["condition_strength"],
            "policy_arm": c["policy_arm"],
            "n_attempts": len(attempts),
            "n_captured": len(captured),
            "verified_success_rate": round(sum(captured) / len(captured), 4) if captured else None,
            "last_attempt_ok": captured[-1] if captured else None,
        })
    return out


def cost_per_verified_outcome_per_cell(cells: list[dict]) -> list[dict]:
    """Cost per verified outcome, captured-only intersection (house discipline)."""
    out = []
    for c in cells:
        attempts = c.get("attempts") or []
        pairs = [
            (a.get("actual_cost"), a.get("test_executed_success"))
            for a in attempts
            if a.get("actual_cost") is not None and a.get("test_executed_success") is not None
        ]
        captured_cost = sum(p[0] for p in pairs)
        verified = sum(1 for p in pairs if p[1])
        out.append({
            "cell_id": c["cell_id"],
            "condition_strength": c["condition_strength"],
            "policy_arm": c["policy_arm"],
            "n_captured_pairs": len(pairs),
            "captured_total_cost": round(captured_cost, 8),
            "n_verified": verified,
            "cost_per_verified_outcome": round(captured_cost / verified, 8) if verified else None,
        })
    return out


def rework_cost_report(cells: list[dict]) -> list[dict]:
    """Rework cost per cell (the spec's dedicated rework_cost ledger field)."""
    out = []
    for c in cells:
        attempts = c.get("attempts") or []
        rework = sum(_num(a.get("rework_cost")) or 0.0 for a in attempts)
        out.append({
            "cell_id": c["cell_id"],
            "condition_strength": c["condition_strength"],
            "policy_arm": c["policy_arm"],
            "rework_cost_per_cell": round(rework, 8),
        })
    return out


def retry_policy_fidelity(cells: list[dict]) -> dict:
    """Realized retry behavior vs the DECLARED policy (finding 4).

    Declared: grit_retry -> max_attempts=2, second attempt ONLY when the first's
    test_executed_success is false; baseline -> max_attempts=1 (no second attempt, ever).
    A violation is a cell whose attempts contradict that rule (a retry that fired without
    a failed first attempt, or a baseline cell with a second attempt, or a grit_retry
    cell whose first failed attempt was NOT followed by a retry).
    """
    violations = []
    retries = 0
    eligible_failures = 0
    for c in cells:
        attempts = c.get("attempts") or []
        arm = c["policy_arm"]
        nums = sorted(a.get("attempt_number", 0) for a in attempts)
        has_second = len(attempts) >= 2
        first = attempts[0] if attempts else None
        first_failed = bool(first) and first.get("test_executed_success") is False
        if first_failed:
            eligible_failures += 1
            if has_second:
                retries += 1
            else:
                violations.append({"cell_id": c["cell_id"], "violation": "failed first attempt, no retry fired"})
        if arm == "baseline" and has_second:
            violations.append({"cell_id": c["cell_id"], "violation": "baseline cell ran a second attempt"})
        if arm == "grit_retry" and has_second and not first_failed:
            violations.append({"cell_id": c["cell_id"], "violation": "retry fired without failed first attempt"})
    return {
        "n_attempts_total": sum(len(c.get("attempts") or []) for c in cells),
        "n_retries_fired": retries,
        "n_failed_first_attempts": eligible_failures,
        "retry_triggered_rate": round(retries / eligible_failures, 4) if eligible_failures else None,
        "retry_policy_violations": violations,
    }


def arm_comparison(per_cell: list[dict], per_cell_cost: list[dict], per_cell_success: list[dict]) -> dict:
    """Baseline vs grit_retry regret on cost_per_verified_outcome, by condition_strength.

    Stratified: a strength-dependent effect is never averaged away. Uses the captured-only
    cost_per_verified_outcome (None when no cell verified => unmeasured, not 0).
    """
    cost_by = {r["cell_id"]: r for r in per_cell_cost}
    succ_by = {r["cell_id"]: r for r in per_cell_success}
    strata: dict[str, dict] = {}
    for c in per_cell:
        if not c.get("condition_strength"):
            continue
        key = c["condition_strength"]
        s = strata.setdefault(key, {"condition_strength": key, "baseline": None, "grit_retry": None})
        if c["policy_arm"] == "baseline":
            s["baseline"] = c
        else:
            s["grit_retry"] = c
    rows = []
    for key, s in sorted(strata.items()):
        b = s["baseline"]
        g = s["grit_retry"]
        b_cost = cost_by[b["cell_id"]]["cost_per_verified_outcome"] if b else None
        g_cost = cost_by[g["cell_id"]]["cost_per_verified_outcome"] if g else None
        b_succ = succ_by[b["cell_id"]]["verified_success_rate"] if b else None
        g_succ = succ_by[g["cell_id"]]["verified_success_rate"] if g else None
        if b_cost is not None and g_cost is not None:
            regret = round(g_cost - b_cost, 8)
            better_arm = "baseline" if regret > 0 else ("grit_retry" if regret < 0 else "tie")
        else:
            regret = None
            better_arm = None
        rows.append({
            "condition_strength": key,
            "baseline_cost_per_verified": b_cost,
            "grit_retry_cost_per_verified": g_cost,
            "baseline_verified_success_rate": b_succ,
            "grit_retry_verified_success_rate": g_succ,
            "routing_arm_regret": regret,
            "better_arm": better_arm,
        })
    return {"stratified": rows, "best_arm": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine JSON to stdout")
    args = parser.parse_args()

    ledger = json.loads(LEDGER_PATH.read_text())
    cells = ledger["cells"]
    attempts = [a for c in cells for a in (c.get("attempts") or [])]

    # ── COVERAGE FIRST (the m2 guard) ───────────────────────────
    coverage = attempt_coverage_precheck(attempts)
    if not args.json:
        print(f"grid_status: {ledger.get('grid_status', 'unknown')}")
        print(f"COVERAGE: {coverage['n_cost_captured']}/{coverage['n_attempts']} cost, "
              f"{coverage['n_test_verification_captured']}/{coverage['n_attempts']} test-verified")

    # ── Registered rules ────────────────────────────────────────
    # grit: reuse the compile evaluator's registered implementation (the spec's rule by name).
    spec = load_spec(SPEC_PATH)
    rules = evaluate_rules(spec, attempts)
    grit_result = next((r for r in rules if r.rule == "grit"), None)

    verified = verified_success_rate_per_cell(cells)
    cpvo = cost_per_verified_outcome_per_cell(cells)
    rework = rework_cost_report(cells)
    fidelity = retry_policy_fidelity(cells)
    arm = arm_comparison(verified, cpvo, verified)

    metrics = {
        "schema": "cap_grit_grid_metrics/v1",
        "spec_id": spec.spec_id,
        "generated_at": ledger.get("generated_at", ""),
        "grid_status": ledger.get("grid_status", "unknown"),
        "coverage": coverage,
        "grit": {
            "rule": "grit",
            "metric": grit_result.metric if grit_result else None,
            "uncertainty": grit_result.uncertainty if grit_result else None,
            "produces": grit_result.produces if grit_result else {},
            "evidence_class": grit_result.evidence_class if grit_result else "[M]",
        },
        "verified_success_rate_per_cell": verified,
        "cost_per_verified_outcome_per_cell": cpvo,
        "rework_cost_report": rework,
        "retry_policy_fidelity": fidelity,
        "arm_comparison": arm,
        "realized_total_cost": round(sum(_num(c.get("realized_cost")) or 0.0 for c in cells), 8),
        "realized_n_attempts": len(attempts),
    }

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"\nwrote {OUT_PATH.relative_to(REPO_ROOT)}")

    # ── table ───────────────────────────────────────────────────
    print("\nPER-CELL TABLE (condition_strength | arm | n_attempts | verified_rate | cpvo | rework)")
    for r, c, rw in zip(verified, cpvo, rework):
        rate = "—" if r["verified_success_rate"] is None else r["verified_success_rate"]
        cost = "—" if c["cost_per_verified_outcome"] is None else c["cost_per_verified_outcome"]
        print(f"  {r['condition_strength']:12s} {r['policy_arm']:10s} "
              f"{r['n_attempts']}  {rate}  {cost}  ${rw['rework_cost_per_cell']}")


if __name__ == "__main__":
    main()
