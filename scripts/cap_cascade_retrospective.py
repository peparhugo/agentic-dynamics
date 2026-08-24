#!/usr/bin/env python3
"""cap_cascade_retrospective.py — E2 confidence-gated cascade retrospective evaluator.

Runs the measurement rules of ``experiments/definitions/cap_confidence_cascade.yaml`` over the
backfilled workflow-run corpus (``experiments/results/workflows/**/*.json``, the same source the
fact producers read). RETROSPECTIVE ONLY: every cascade arm is a counterfactual — nothing is
escalated, no model is called; the numbers below replay what a *live* ``model_cascade`` policy
(escalate to a stronger model when ``attempt_confidence < theta``) WOULD have touched.

Headline semantics (per the spec's finding 2, the load-bearing honesty rule):
- **Escalation trigger rate** (per theta) is the ONE genuinely measurable quantity: the fraction
  of confidence-captured attempts a live cascade would have escalated. Uncaptured confidence is
  EXCLUDED (never assumed non-escalating).
- **Cascade cost-per-verified-outcome** (per theta) is computed over the NON-escalated subset
  only (confidence >= theta) and labeled *baseline-equivalent*: on that subset the cascade's
  executions are byte-identical to baseline's, so the number is a tautology, not a measurement of
  escalation's effect. The escalated subset's true post-escalation cost/outcome is genuinely
  UNKNOWN — ``*_unmeasured_escalated_n`` reports how many attempts sit there.
- **``routing_arm_regret_theta_*`` is 0.0 by construction** (same subset, same executions) and is
  NEVER a "no threshold hurts" signal; ``null_testable_theta_*`` is the honest flag (false
  whenever the escalated subset is non-empty — i.e. every theta today).

"Verified success" == ``phase_status == "ok"`` (a completion signal, 100% covered) per the spec's
explicit substitution; ``phase_test_verified`` (independently-tested correctness) is out of this
spec's fixed ``requires_facts`` scope and is confirmed at ~0% on the agent-phase corpus.

Costs follow the F1 sanitizer (``scripts/kb_produce_facts.py:_sanitize_run``): a failed-before-call
phase's ``0.0`` is a STRUCTURAL zero recorded as ``None`` (uncaptured) — never a measured zero —
so the captured-only intersection matches the backfilled fact store, not the raw ledger.

Usage:
    python scripts/cap_cascade_retrospective.py            # per-threshold table + PASS/FAIL
    python scripts/cap_cascade_retrospective.py --json      # dump the full JSON to stdout
    python scripts/cap_cascade_retrospective.py --recompute # re-run, overwrite the artifact

Output:
    experiments/results/cap_cascade_retrospective.json   (machine-readable)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

RESULTS = Path(__file__).resolve().parent.parent / "experiments" / "results"
WORKFLOWS = RESULTS / "workflows"
OUT = RESULTS / "cap_cascade_retrospective.json"

THETAS = (0.3, 0.5, 0.7)
_THETA_KEY = {0.3: "0_3", 0.5: "0_5", 0.7: "0_7"}


def _is_failed_before_call(phase: dict) -> bool:
    """F1 structural-zero discriminant (mirrors ``kb_produce_facts._is_failed_before_call``)."""
    if phase.get("kind") not in (None, "agent"):
        return False
    if phase.get("status") not in ("failed", "error", "timeout", "blocked"):
        return False
    if phase.get("cost_usd") not in (0, 0.0):
        return False
    tokens = phase.get("tokens") or {}
    if isinstance(tokens, dict):
        return not any(tokens.get(k) for k in ("in", "out", "total"))
    return True


def load_phases() -> tuple[list[dict[str, Any]], int, int]:
    """Flatten the workflow corpus into per-phase rows; F1-sanitize costs.

    Returns ``(rows, n_runs, n_runs_ok)`` — a run is counted only once for ``n_runs`` even though
    its ``ok`` flag is replicated onto every phase row.
    """
    rows: list[dict[str, Any]] = []
    n_runs = 0
    n_runs_ok = 0
    n_runs_status_captured = 0
    for path in sorted(WORKFLOWS.rglob("*.json")):
        try:
            run = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(run, dict):
            continue
        n_runs += 1
        if "ok" in run:
            n_runs_status_captured += 1
        run_ok = run.get("ok") is True
        if run_ok:
            n_runs_ok += 1
        run_model = run.get("model")
        for phase in run.get("phases") or []:
            if not isinstance(phase, dict):
                continue
            cost = phase.get("cost_usd")
            if _is_failed_before_call(phase):
                cost = None  # F1: uncaptured, not a measured zero
            rows.append({
                "spec": run.get("spec_name"),
                "run_model": run_model,
                "job_ok": run_ok,
                "kind": str(phase.get("kind") or "agent"),
                "status": str(phase.get("status") or "") or None,
                "cost": cost,
                "confidence": phase.get("confidence"),
                "model": phase.get("model") or run_model,
            })
    return rows, n_runs, n_runs_ok, n_runs_status_captured


def _cost_captured(r: dict) -> bool:
    return isinstance(r["cost"], (int, float)) and not isinstance(r["cost"], bool)


def _verified(r: dict) -> bool:
    return r["status"] == "ok"


def cost_per_verified(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost per verified outcome over the captured-only intersection (house style).

    Numerator = total captured cost over the cost-captured set; denominator = number of
    verified (status ok) phases IN that same cost-captured set. Unverified-but-captured phases
    still pay their cost; phases whose cost is uncaptured (None) are excluded entirely.
    """
    captured = [r for r in rows if _cost_captured(r)]
    n_verified = sum(1 for r in captured if _verified(r))
    total = sum(float(r["cost"]) for r in captured)
    return {
        "value": round(total / n_verified, 4) if captured and n_verified else None,
        "n_captured": len(captured),
        "n_total": len(rows),
        "coverage": round(len(captured) / len(rows), 4) if rows else 0.0,
        "captured_total_cost_usd": round(total, 4),
        "n_verified": n_verified,
    }


def verified_success_rate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Verified-success coverage: n_verified / n_status_captured, with the coverage window."""
    status_captured = [r for r in rows if r["status"] is not None]
    n_verified = sum(1 for r in status_captured if _verified(r))
    return {
        "value": round(n_verified / len(status_captured), 4) if status_captured else None,
        "n_verified": n_verified,
        "n_status_captured": len(status_captured),
        "n_total": len(rows),
        "coverage": round(len(status_captured) / len(rows), 4) if rows else 0.0,
    }


def _escalation_subset(rows: list[dict[str, Any]], theta: float) -> tuple[list, list]:
    """(non_escalated, escalated) split over confidence-CAPTURED attempts only."""
    captured = [r for r in rows if r["confidence"] is not None]
    non_esc = [r for r in captured if r["confidence"] >= theta]
    esc = [r for r in captured if r["confidence"] < theta]
    return non_esc, esc


def escalation_trigger_rate(rows: list[dict[str, Any]], theta: float) -> dict[str, Any]:
    captured = [r for r in rows if r["confidence"] is not None]
    n_esc = sum(1 for r in captured if r["confidence"] < theta)
    return {
        "value": round(n_esc / len(captured), 4) if captured else None,
        "n_escalated": n_esc,
        "n_captured_confidence": len(captured),
    }


def per_model_trigger_range(rows: list[dict[str, Any]], theta: float) -> float | None:
    """max-min per-model escalation trigger rate (the model x threshold confound indicator)."""
    rates: list[float] = []
    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r["confidence"] is None:
            continue
        m = r["model"] or r["run_model"] or "?"
        by_model.setdefault(m, []).append(r)
    for model, mrows in by_model.items():
        n_esc = sum(1 for r in mrows if r["confidence"] < theta)
        rates.append(n_esc / len(mrows))
    if not rates:
        return None
    return round(max(rates) - min(rates), 4)


def _theta_arm(rows: list[dict[str, Any]], theta: float, *, by_job: bool = False) -> dict[str, Any]:
    non_esc, esc = _escalation_subset(rows, theta)
    key = _THETA_KEY[theta]
    arm: dict[str, Any] = {
        "theta": theta,
        "escalation_trigger_rate": escalation_trigger_rate(rows, theta),
        "n_escalation_eligible": sum(1 for r in rows if r["confidence"] is not None),
        "escalated_unmeasured": {
            "n": len(esc),
            "note": (
                "confidence < theta — a live cascade WOULD have escalated these; their true "
                "post-escalation cost/outcome is unknown (never fabricated)"
            ),
        },
        "non_escalated_subset": {
            "n": len(non_esc),
            "cost_per_verified_outcome": cost_per_verified(non_esc),
            "verified_success_rate": verified_success_rate(non_esc),
            "label": "baseline-equivalent (same executions as baseline on this subset)",
        },
        "per_model_trigger_range": per_model_trigger_range(rows, theta),
    }
    if by_job:
        arm["by_job_status"] = {}
        for job_ok in (True, False):
            sub = [r for r in rows if r["job_ok"] is job_ok]
            arm["by_job_status"][str(job_ok)] = {
                "escalation_trigger_rate": escalation_trigger_rate(sub, theta),
                "cost_per_verified_outcome": cost_per_verified(sub),
            }
    return arm


def compute(
    *, rows: list[dict[str, Any]], n_runs: int, n_runs_ok: int, n_runs_status_captured: int
) -> dict[str, Any]:
    n_total = len(rows)
    n_conf = sum(1 for r in rows if r["confidence"] is not None)
    n_status = sum(1 for r in rows if r["status"] is not None)

    precheck = {
        "confidence_coverage_ratio": round(n_conf / n_total, 4) if n_total else 0.0,
        "n_confidence_available": n_conf,
        "n_confidence_total": n_total,
        "status_coverage_ratio": round(n_status / n_total, 4) if n_total else 0.0,
        "n_status_available": n_status,
        "n_status_total": n_total,
        "job_status_coverage_ratio": (
            round(n_runs_status_captured / n_runs, 4) if n_runs else 0.0
        ),
        "n_jobs_status_captured": n_runs_status_captured,
        "n_jobs_ok": n_runs_ok,
        "n_jobs": n_runs,
        "verdict": (
            "EVALUABLE_WITH_CAVEAT"
            if n_conf > 0
            else "INCONCLUSIVE: zero confidence-captured attempts — near-zero coverage per the spec's n=0 lesson"
        ),
    }

    baseline = {
        "label": "single-model baseline as actually run (no escalation)",
        "n": n_total,
        "cost_per_verified_outcome": cost_per_verified(rows),
        "verified_success_rate": verified_success_rate(rows),
    }

    arms = {_THETA_KEY[t]: _theta_arm(rows, t, by_job=True) for t in THETAS}

    # arm_comparison (spec rule): regret is 0.0 by construction; null_testable is the honest flag.
    comparison = {"baseline": baseline, "arms": {}}
    for t in THETAS:
        key = _THETA_KEY[t]
        esc_n = arms[key]["escalated_unmeasured"]["n"]
        comparison["arms"][key] = {
            "routing_arm_regret": 0.0,
            "regret_basis": (
                "0.0 by construction — the cascade arm on the non-escalated subset is byte-identical "
                "to baseline on that same subset; NOT evidence a threshold is safe"
            ),
            "null_testable": esc_n == 0,
            "null_testable_note": (
                "false whenever the escalated (unmeasured) subset is non-empty — the null is "
                "untestable-by-construction from this corpus, not merely under-covered"
            ),
        }

    return {
        "schema": "cap_cascade_retrospective/v1",
        "spec_id": "cap_confidence_cascade@0.1",
        "source": "experiments/results/workflows/**/*.json (workflow-run ledgers; F1-sanitized costs)",
        "n_runs": n_runs,
        "n_phases": n_total,
        "coverage_precheck": precheck,
        "baseline": baseline,
        "arms": arms,
        "arm_comparison": comparison,
        "null_hypothesis": (
            "no threshold improves cost-per-verified-outcome over baseline — structurally "
            "untestable from this corpus (nothing was ever actually escalated), recorded honestly"
        ),
        "notes": [
            "verified success == phase_status == 'ok' (completion signal); phase_test_verified is "
            "out of this spec's requires_facts scope (confirmed ~0% on agent phases)",
            "escalation is counterfactual only — no attempt in the corpus was ever actually "
            "escalated by a confidence-gated policy",
            "confidence is a self-report ([H]/advisory); uncaptured confidence is excluded, never "
            "assumed non-escalating",
            "uncaptured cost is null with zero coverage, never a zero-cost observation (F1 semantics)",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the full JSON to stdout")
    parser.add_argument(
        "--recompute", action="store_true", help="recompute and overwrite the artifact"
    )
    args = parser.parse_args(argv)

    rows, n_runs, n_runs_ok, n_runs_status_captured = load_phases()
    payload = compute(
        rows=rows, n_runs=n_runs, n_runs_ok=n_runs_ok, n_runs_status_captured=n_runs_status_captured
    )

    if args.json or args.recompute:
        OUT.write_text(json.dumps(payload, indent=2) + "\n")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    pc = payload["coverage_precheck"]
    print(
        f"coverage pre-check: confidence {pc['n_confidence_available']}/{pc['n_confidence_total']} "
        f"({pc['confidence_coverage_ratio']:.1%}) | status {pc['n_status_available']}/{pc['n_status_total']} "
        f"({pc['status_coverage_ratio']:.1%}) | jobs {pc['n_jobs_ok']}/{pc['n_jobs']} ok"
    )
    print(f"verdict: {pc['verdict']}")
    if pc["n_confidence_available"] == 0:
        print("INCONCLUSIVE — cascade not evaluable (confidence coverage is zero).")
        return 0

    print(f"\ncorpus: {payload['n_runs']} runs / {payload['n_phases']} phases")
    b = payload["baseline"]
    bcpv = b["cost_per_verified_outcome"]
    bvs = b["verified_success_rate"]
    print(
        f"baseline: cost/verified={bcpv['value']} (n_captured={bcpv['n_captured']}/{bcpv['n_total']}, "
        f"n_verified={bcpv['n_verified']}) verified_success={bvs['value']} "
        f"(n={bvs['n_verified']}/{bvs['n_status_captured']})"
    )

    print("\nper-threshold cascade table:")
    print(f"  {'theta':>6} {'trigger':>9} {'esc_n':>6} {'cascade_cpv':>12} {'subset_n':>9} {'model_range':>11}")
    for t in THETAS:
        a = payload["arms"][_THETA_KEY[t]]
        tr = a["escalation_trigger_rate"]["value"]
        esc_n = a["escalated_unmeasured"]["n"]
        ccpv = a["non_escalated_subset"]["cost_per_verified_outcome"]["value"]
        sub_n = a["non_escalated_subset"]["n"]
        rng = a["per_model_trigger_range"]
        print(
            f"  {t:>6.1f} {tr:>9.1%} {esc_n:>6d} {str(ccpv):>12} {sub_n:>9d} {str(rng):>11}"
        )

    print("\narm comparison (regret is 0.0 by construction, never a safety signal):")
    for t in THETAS:
        c = payload["arm_comparison"]["arms"][_THETA_KEY[t]]
        print(f"  theta={t:.1f} regret={c['routing_arm_regret']} null_testable={c['null_testable']}")

    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
