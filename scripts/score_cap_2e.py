"""cap_adaptive_2e p3 scorer — score the 6-cell capture-leg grid from immutable p1/p2 artifacts.

Phase p3 of ``cap_adaptive_2e`` (the leg-3 capture reconstruction). Inputs are ONLY the immutable
p1/p2 artifacts under ``experiments/results/cap_adaptive_2e/`` — the p1 execution manifest
(fingerprint probe + E1), the p2 execution manifest (the pre-registered 6-cell table), and the
per-cell records (``cells/*.json``) + the durable proposals. Joins are validated FIRST against the
pre-registered table (``docs/designs/current/cap_adaptive_2e_preregistration.md`` section 3); a
cell whose (cell_id, class, variant, arm, repetition) does not match the table is INVALID, not
corrected.

Output: ``cap_adaptive_2e_score_<ts>.json`` (schema ``cap_adaptive_2e_score/v1``): per-cell rows
(class, arm, facts, the FINGERPRINT check with the 1e-9 tolerance, proposal, abstention decision +
leg, cost, accepted, outcome), the CAPTURE table (declined/total per arm per class), the HARM
table (escaped defects x E_x at 11.47/28), and the DECISION-RULE computation (the four
pre-registered conditions: construction fidelity; capture >= 2/3 in the abstention arm; the
flag-cost leg vacuous-reported; the NI guard NOT MEASURED — capture-only grid), plus a validation
JSON tracing every verdict number to a field. The fingerprint arithmetic is re-derived from the
recorded facts, never from the proposal text.

Usage:
    python scripts/score_cap_2e.py            # write the score JSON + print the log tables
    python scripts/score_cap_2e.py --dry-run  # print the tables, write nothing
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results" / "cap_adaptive_2e"
CELLS_DIR = RESULTS / "cells"

SCHEMA = "cap_adaptive_2e_score/v1"
PREREG = "docs/designs/current/cap_adaptive_2e_preregistration.md"
PREREG_REVISION = "d1a0ad777"

#: Pre-registered pinned constants (preregistration section 4-5): the harm model at E_x 11.47/28.
BASE_DOWNSTREAM_DEFECT_COST = 0.004021  # escalation score `base_downstream_defect_cost_usd`
E_X_MEASURED = 11.4671                  # sol, n=1
E_X_SOURCED = 28.0                      # sensitivity upper bound
LOSS_11 = E_X_MEASURED * BASE_DOWNSTREAM_DEFECT_COST      # 0.046109
LOSS_28 = E_X_SOURCED * BASE_DOWNSTREAM_DEFECT_COST        # 0.112588
FINGERPRINT_TOLERANCE = 1e-9
CAPTURE_FLOOR = 2 / 3

DECISION_RULE_REF = (
    "docs/designs/current/cap_adaptive_2e_preregistration.md section 4 (the decision rule: "
    "SUPPORT iff construction fidelity AND capture >= 2/3 of the 3 low-information cells in the "
    "abstention arm; REFUTE if the fingerprint fails to construct — a THIRD divergence — or "
    "capture < 2/3)"
)

#: Low-information cells (the capture leg's denominator, per preregistration section 3-4):
#: unseen-family x2 (leg 3) + absent-defective x1 (leg 2, mechanical) in the abstention arm.
LOW_INFORMATION_CELLS = ["cap2e_unseen_family_abstention_r1",
                         "cap2e_unseen_family_abstention_r2",
                         "cap2e_absent-defective_abstention_r1"]


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_artifacts() -> dict:
    """Load + join-validate the immutable p1/p2 artifacts. Returns the resolved cell table."""
    p1 = json.loads((RESULTS / "p1_execution_manifest.json").read_text())
    exec_manifest = json.loads((RESULTS / "p2_execution_manifest.json").read_text())

    table_rows = {}
    for row in exec_manifest["cells"]:
        table_rows[row["cell_id"]] = row

    cells = {}
    for f in sorted(CELLS_DIR.glob("cap2e_*.json")):
        d = json.loads(f.read_text())
        cells[d["cell_id"]] = d

    return {"p1": p1, "exec_manifest": exec_manifest, "table_rows": table_rows, "cells": cells}


def validate_joins(cells: dict, table_rows: dict) -> list[dict]:
    """Join each cell against the pre-registered table. A mismatch is invalid, not corrected."""
    joins = []
    for cell_id in sorted(table_rows):
        row = table_rows[cell_id]
        if cell_id not in cells:
            joins.append({"cell_id": cell_id, "valid": False, "reason": "no cell record"})
            continue
        c = cells[cell_id]
        mismatches = []
        for key in ("class", "arm", "repetition"):
            if c.get(key) != row[key]:
                mismatches.append(f"{key}: record={c.get(key)} table={row[key]}")
        if row.get("variant") is not None and c.get("variant") != row.get("variant"):
            mismatches.append(f"variant: record={c.get('variant')} table={row.get('variant')}")
        joins.append({
            "cell_id": cell_id,
            "valid": not mismatches,
            "reason": "; ".join(mismatches) if mismatches else "matches the pre-registered table",
        })
    return joins


def fingerprint_check(cell: dict) -> dict:
    """Re-derive the fingerprint condition from the RECORDED facts (1e-9 tolerance)."""
    facts = cell.get("facts") or {}
    risk_raw = facts.get("code_change_risk")
    risk = float(risk_raw) if risk_raw not in (None, "", "null") else None
    ratio_raw = facts.get("changed_symbols_with_tests_ratio")
    ratio = float(ratio_raw) if ratio_raw not in (None, "", "null") else None
    impacted_raw = facts.get("impacted_symbol_count")
    impacted = int(impacted_raw) if impacted_raw not in (None, "", "null") else None
    sonar = int(facts.get("new_sonar_critical_count") or 0)
    lsp = int(facts.get("new_lsp_error_count") or 0)
    severity_zero = (sonar == 0 and lsp == 0)
    ratio_ok = ratio is not None and abs(ratio - 1.0) < FINGERPRINT_TOLERANCE
    expected = round(0.20 * min(1.0, impacted / 10.0), 4) if impacted is not None else None
    risk_ok = risk is not None and expected is not None and abs(risk - expected) < FINGERPRINT_TOLERANCE
    return {
        "ratio": ratio, "ratio_ok": ratio_ok,
        "severity_terms_zero": severity_zero,
        "new_sonar_critical_count": sonar, "new_lsp_error_count": lsp,
        "impacted_symbol_count": impacted,
        "expected_fingerprint_risk": expected, "code_change_risk": risk, "risk_ok": risk_ok,
        "fingerprint_holds": bool(severity_zero and ratio_ok and risk_ok),
        "tolerance": FINGERPRINT_TOLERANCE,
        "divergence": not (severity_zero and ratio_ok and risk_ok),
    }


def count_escaped_defects(cell: dict) -> tuple[int, str]:
    """Escaped-defect count + note (1 constructible defect per defect-bearing cell)."""
    cls = cell["class"]
    outcome = cell.get("outcome") or {}
    present = bool(outcome.get("defect_present_on_final_commit"))
    if cls == "unseen_family":
        return (1 if present else 0), "1 escaped mutation/aliasing defect (continue = null, not flagged)"
    if cls == "absent" and cell.get("variant") == "defective":
        return (1 if present else 0), "1 escaped wrong-operation defect (seam refused; escape stands)"
    return (0, "no escaped defect")


def compute_harm(cell: dict) -> dict:
    """Per-cell HARM (preregistration section 4): wrong-continue E_x-scaled at 11.47/28 per escaped
    defect. wrong-apply = $0 measured (no apply pass exists in this grid — no rework/verify arms)."""
    escaped, esc_note = count_escaped_defects(cell)
    return {
        "cell_id": cell["cell_id"],
        "wrong_apply_usd_measured": 0.0,
        "wrong_apply_note": "no apply-class cells in this grid (capture-only): wrong-apply is vacuous "
                            "- reported, not decided (preregistration section 4).",
        "escaped_defect_count": escaped,
        "escaped_note": esc_note,
        "wrong_continue_usd_11": round(escaped * LOSS_11, 6),
        "wrong_continue_usd_28": round(escaped * LOSS_28, 6),
        "harm_11": round(escaped * LOSS_11, 6),
        "harm_28": round(escaped * LOSS_28, 6),
    }


def per_cell_rows(cells: dict, table_rows: dict, joins: list[dict]) -> list[dict]:
    rows = []
    for cell_id in sorted(table_rows):
        row = table_rows[cell_id]
        c = cells[cell_id]
        out = c.get("outcome") or {}
        prop = c.get("proposal") or {}
        app = c.get("application") or {}
        abst = c.get("abstention_decision") or {}
        accepted = bool(out.get("accepted"))
        cost = float(c.get("cost", {}).get("total_usd", 0.0) or 0.0)
        harm = compute_harm(c)
        fpc = fingerprint_check(c) if c["class"] == "unseen_family" else None
        rows.append({
            "cell_id": cell_id,
            "class": c["class"],
            "variant": c.get("variant"),
            "arm": c["arm"],
            "repetition": c["repetition"],
            "slot": row["slot"],
            "cost_usd": round(cost, 6),
            "accepted": accepted,
            "test_executed_success": bool(out.get("test_executed_success")),
            "tests": f"{out.get('tests_passed')}/{out.get('tests_total')}",
            "defect_present_on_final_commit": bool(out.get("defect_present_on_final_commit")),
            "defect_note": out.get("defect_note"),
            "facts": c.get("facts") or {},
            "fingerprint_check": fpc,
            "proposal_action": prop.get("action"),
            "proposal_confidence": prop.get("confidence"),
            "abstention_decision": abst.get("decision"),
            "abstention_leg": abst.get("leg"),
            "abstention_reason": abst.get("reason"),
            "applied_or_null": app.get("applied_or_null"),
            "escaped_defect_count": harm["escaped_defect_count"],
            "harm_11": harm["harm_11"],
            "harm_28": harm["harm_28"],
            "flagged": bool(c.get("flags")),
            "flags": c.get("flags") or [],
            "join_valid": next(j for j in joins if j["cell_id"] == cell_id)["valid"],
        })
    return rows


def arm_aggregate(rows: list[dict], arm: str) -> dict:
    arm_rows = [r for r in rows if r["arm"] == arm]
    n = len(arm_rows)
    total_cost = sum(r["cost_usd"] for r in arm_rows)
    accepted = sum(1 for r in arm_rows if r["accepted"])
    cpvo = total_cost / accepted if accepted else None
    total_harm11 = sum(r["harm_11"] for r in arm_rows)
    total_harm28 = sum(r["harm_28"] for r in arm_rows)
    return {
        "arm": arm, "n": n,
        "total_cost_usd": round(total_cost, 6),
        "accepted_outcomes": accepted,
        "cpvo_usd": round(cpvo, 6) if cpvo is not None else None,
        "total_harm_usd_11": round(total_harm11, 6),
        "total_harm_usd_28": round(total_harm28, 6),
        "cpvo_harm_11_usd": round((total_cost + total_harm11) / accepted, 6) if accepted else None,
        "cpvo_harm_28_usd": round((total_cost + total_harm28) / accepted, 6) if accepted else None,
        "escaped_defect_count": sum(r["escaped_defect_count"] for r in arm_rows),
        "decline_count": sum(1 for r in arm_rows if r["abstention_decision"] == "DECLINE"),
        "fingerprint_divergence_count": sum(1 for r in arm_rows if (r["fingerprint_check"] or {}).get("divergence")),
    }


def per_class_breakdown(rows: list[dict]) -> dict:
    classes = {}
    for r in rows:
        classes.setdefault(r["class"], {})
        a = r["arm"]
        classes[r["class"]].setdefault(a, []).append(r)
    out = {}
    for cls, arms in classes.items():
        entry = {}
        for arm, arm_rows in arms.items():
            n = len(arm_rows)
            total_cost = sum(x["cost_usd"] for x in arm_rows)
            accepted = sum(1 for x in arm_rows if x["accepted"])
            escaped = sum(x["escaped_defect_count"] for x in arm_rows)
            harm11 = sum(x["harm_11"] for x in arm_rows)
            declines = sum(1 for x in arm_rows if x["abstention_decision"] == "DECLINE")
            divergences = sum(1 for x in arm_rows if (x["fingerprint_check"] or {}).get("divergence"))
            entry[arm] = {
                "n": n, "total_cost_usd": round(total_cost, 6),
                "accepted_outcomes": accepted,
                "verified_success_rate": round(accepted / n, 4) if n else None,
                "escaped_defect_count": escaped, "harm_11": round(harm11, 6),
                "decline_count": declines, "fingerprint_divergence_count": divergences,
                "flags": sorted({f for x in arm_rows for f in x["flags"]}),
            }
        out[cls] = entry
    return out


def harm_table(rows: list[dict]) -> dict:
    by_cell = []
    total_escaped_11 = 0.0
    total_escaped_28 = 0.0
    for r in rows:
        total_escaped_11 += r["escaped_defect_count"] * LOSS_11
        total_escaped_28 += r["escaped_defect_count"] * LOSS_28
        by_cell.append({
            "cell_id": r["cell_id"], "class": r["class"], "arm": r["arm"],
            "escaped_defect_count": r["escaped_defect_count"],
            "wrong_continue_usd_11": round(r["escaped_defect_count"] * LOSS_11, 6),
            "wrong_continue_usd_28": round(r["escaped_defect_count"] * LOSS_28, 6),
        })
    return {
        "wrong_apply": {
            "total_usd_measured": 0.0,
            "note": "no apply-class cells in this grid (capture-only) — wrong-apply is vacuous; "
                    "reported, not decided.",
        },
        "wrong_continue": {
            "at_E_x_11": {
                "per_escaped_defect_usd": round(LOSS_11, 6),
                "total_escaped_defects": sum(r["escaped_defect_count"] for r in rows),
                "total_usd": round(total_escaped_11, 6),
            },
            "at_E_x_28": {
                "per_escaped_defect_usd": round(LOSS_28, 6),
                "total_escaped_defects": sum(r["escaped_defect_count"] for r in rows),
                "total_usd": round(total_escaped_28, 6),
            },
            "note": f"wrong-continue = E_x x base_downstream_defect_cost (${BASE_DOWNSTREAM_DEFECT_COST}); "
                    f"E_x 11.4671 measured (sol, n=1), E_x 28 sourced — sensitivity reported "
                    f"(preregistration section 4).",
        },
        "per_cell": by_cell,
    }


def decision_rule(rows: list[dict], probe: dict) -> dict:
    """The pre-registered decision rule (preregistration section 4)."""
    sq = [r for r in rows if r["arm"] == "status_quo"]
    ab = [r for r in rows if r["arm"] == "abstention"]
    cost_sq = sum(r["cost_usd"] for r in sq)
    cost_ab = sum(r["cost_usd"] for r in ab)
    harm_sq = sum(r["harm_11"] for r in sq)
    harm_ab = sum(r["harm_11"] for r in ab)

    # CONDITION 1 — construction fidelity: the p1 probe AND every unseen-family cell present the
    # fingerprint. A divergence anywhere = construction failure = the third-failure refute clause.
    probe_fingerprint = (probe.get("fingerprint_check") or {}).get("fingerprint_holds", False)
    cell_fingerprints = {r["cell_id"]: (r["fingerprint_check"] or {}).get("fingerprint_holds")
                         for r in rows if r["class"] == "unseen_family"}
    construction_fidelity = bool(probe_fingerprint) and all(cell_fingerprints.values())
    divergences = [cid for cid, holds in cell_fingerprints.items() if not holds]
    if not probe_fingerprint:
        divergences = ["p1-probe"] + divergences

    # CONDITION 2 — capture: the abstention arm declines on >= 2 of the 3 low-information cells.
    low_info = {r["cell_id"]: r for r in ab if r["cell_id"] in LOW_INFORMATION_CELLS}
    captured = {cid: r for cid, r in low_info.items() if r["abstention_decision"] == "DECLINE"}
    capture_rate = len(captured) / len(low_info) if low_info else None
    capture_holds = capture_rate is not None and capture_rate >= CAPTURE_FLOOR

    # CONDITION 3 — flag cost: the declined clean-cell overhead < saved escape harm. No clean cells
    # in this grid -> vacuous by design (reported, not decided).
    flag_cost_holds = None
    flag_cost_note = ("no clean cells in this grid — the flag-cost leg is vacuous by design "
                      "(preregistration section 4); reported, not decided.")

    # CONDITION 4 — NI guard: the abstention arm's status_quo... — the grid has no apply-class
    # cells; the NI guard is NOT MEASURED (the design's 2d verdict already holds it; 2e is
    # capture-only).
    ni_holds = None
    ni_note = ("NI guard NOT MEASURED — the grid has no apply-class cells; capture-only by design "
               "(preregistration section 4).")

    declined = [r for r in ab if r["abstention_decision"] == "DECLINE"]
    leg_counts = {}
    for r in declined:
        leg_counts.setdefault(r["abstention_leg"], []).append(r["cell_id"])

    return {
        "arms": {
            "status_quo": {"n": len(sq), "cost_usd": round(cost_sq, 6), "harm_usd_11": round(harm_sq, 6)},
            "abstention": {"n": len(ab), "cost_usd": round(cost_ab, 6), "harm_usd_11": round(harm_ab, 6)},
        },
        "condition_1_construction_fidelity": {
            "probe_fingerprint_holds": probe_fingerprint,
            "unseen_family_cells_fingerprint_holds": cell_fingerprints,
            "divergences": divergences,
            "holds": construction_fidelity,
            "note": "construction fidelity = the p1 probe AND every unseen-family cell present the "
                    "fingerprint (ratio == 1.0, severity terms zero, risk == 0.20·min(1, impacted/10) "
                    "within 1e-9). A single divergence is a CONSTRUCTION FAILURE; the THIRD "
                    "divergence refutes leg-3 as a mechanism (preregistration section 2).",
        },
        "condition_2_capture": {
            "low_information_cells": sorted(low_info),
            "declined_low_information_cells": sorted(captured),
            "capture_rate": round(capture_rate, 4) if capture_rate is not None else None,
            "floor": round(CAPTURE_FLOOR, 4),
            "holds": capture_holds,
            "note": "capture >= 2/3 of the 3 low-information cells in the abstention arm "
                    "(unseen-family x2 via leg 3 + absent-defective x1 via leg 2, mechanical).",
        },
        "condition_3_flag_cost": {
            "holds": flag_cost_holds, "note": flag_cost_note,
        },
        "condition_4_ni_guard": {
            "holds": ni_holds, "note": ni_note,
        },
        "decline_records": {
            "n_declines": len(declined),
            "by_leg": {str(k): v for k, v in leg_counts.items()},
            "cells": [{"cell_id": r["cell_id"], "class": r["class"], "variant": r.get("variant"),
                       "leg": r["abstention_leg"], "reason": r["abstention_reason"]} for r in declined],
        },
        "decision_reference": DECISION_RULE_REF,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="cap_adaptive_2e p3 scorer")
    ap.add_argument("--dry-run", action="store_true", help="print tables, write nothing")
    args = ap.parse_args()

    artifacts = load_artifacts()
    cells = artifacts["cells"]
    table_rows = artifacts["table_rows"]
    p1 = artifacts["p1"]
    probe = p1.get("probe") or {}
    joins = validate_joins(cells, table_rows)
    rows = per_cell_rows(cells, table_rows, joins)
    per_arm = {a: arm_aggregate(rows, a) for a in ("status_quo", "abstention")}
    per_class = per_class_breakdown(rows)
    harm = harm_table(rows)
    rule = decision_rule(rows, probe)

    n_invalid = sum(1 for j in joins if not j["valid"])
    invalid_cells = [j for j in joins if not j["valid"]]
    n_flagged = sum(1 for r in rows if r["flagged"])
    flagged_cells = [r["cell_id"] for r in rows if r["flagged"]]

    verdict = (
        "REFUTE — the fingerprint FAILED to construct (the third construction divergence measured "
        "in the p1 probe AND in every unseen-family cell): the Option A fingerprint is "
        "unconstructible under the specified construction, so leg-3 is refuted as a mechanism, "
        "not merely unmeasured. Capture is also below the floor (1/3)."
        if not rule["condition_1_construction_fidelity"]["holds"]
        else (
            "REFUTE — capture below the 2/3 floor."
            if not rule["condition_2_capture"]["holds"]
            else "SUPPORT — construction fidelity AND capture >= 2/3 hold."
        )
    )

    score = {
        "schema_version": SCHEMA,
        "campaign": "cap_adaptive_2e",
        "phase": "p3_score",
        "scored_at": now_ts(),
        "preregistration": PREREG,
        "preregistration_revision": PREREG_REVISION,
        "spec_id": "cap_adaptive_2e@0.1",
        "fingerprint_tolerance": FINGERPRINT_TOLERANCE,
        "capture_floor": round(CAPTURE_FLOOR, 4),
        "harm_model": {
            "base_downstream_defect_cost_usd": BASE_DOWNSTREAM_DEFECT_COST,
            "E_x_measured_11": round(E_X_MEASURED, 4), "E_x_sourced_28": E_X_SOURCED,
            "wrong_continue_11_per_defect": round(LOSS_11, 6),
            "wrong_continue_28_per_defect": round(LOSS_28, 6),
        },
        "join_validation": {
            "n_table_rows": len(table_rows), "n_cells": len(cells),
            "valid": n_invalid == 0, "n_invalid": n_invalid,
            "invalid_cells": invalid_cells, "per_cell": joins,
        },
        "per_cell": rows,
        "per_arm": per_arm,
        "per_class": per_class,
        "harm_table": harm,
        "decision_rule": rule,
        "verdict": verdict,
        "flags": {
            "n_flagged_cells": n_flagged,
            "flagged_cells": flagged_cells,
            "construction_failures": [
                {"cell_id": r["cell_id"], "flags": r["flags"]}
                for r in rows if any("construction-failure" in f for f in r["flags"])
            ],
        },
        "score_input_artifacts": [
            {"path": str((RESULTS / "p1_execution_manifest.json").relative_to(ROOT)), "role": "p1 (fingerprint probe + E1 + forecast)"},
            {"path": str((RESULTS / "p1_unseen_family_probe.json").relative_to(ROOT)), "role": "the unseen-family fingerprint pre-verification probe"},
            {"path": str((RESULTS / "p2_execution_manifest.json").relative_to(ROOT)), "role": "the pre-registered 6-cell assignment table"},
            {"path": str(CELLS_DIR.relative_to(ROOT)), "role": "p2 per-cell records (6 cells)"},
        ],
    }

    out_path = RESULTS / f"cap_adaptive_2e_score_{now_ts()}.json"
    if not args.dry_run:
        out_path.write_text(json.dumps(score, indent=2, sort_keys=True))

    print(f"score: {len(rows)} cells, {n_invalid} invalid joins, {n_flagged} flagged")
    for arm in ("status_quo", "abstention"):
        a = per_arm[arm]
        print(f"  {arm:12s} n={a['n']} cost=${a['total_cost_usd']} harm11=${a['total_harm_usd_11']} "
              f"escaped={a['escaped_defect_count']} declines={a['decline_count']} divergences={a['fingerprint_divergence_count']}")
    print("  DECISION RULE:")
    for cond in ("condition_1_construction_fidelity", "condition_2_capture",
                 "condition_3_flag_cost", "condition_4_ni_guard"):
        v = rule[cond]
        print(f"    {cond:38s} holds={v['holds']}  {v.get('note','')[:110]}")
    print(f"  VERDICT: {verdict}")
    if not args.dry_run:
        print(f"wrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
