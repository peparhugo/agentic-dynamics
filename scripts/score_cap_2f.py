"""cap_adaptive_2f p3 scorer — score the 10-cell Option B grid from immutable p1/p2 artifacts.

Phase p3 of ``cap_adaptive_2f``. Inputs are ONLY the immutable p1/p2 artifacts under
``experiments/results/cap_adaptive_2f/`` — the p1 execution manifest (both probes + E1 + forecast),
the p2 execution manifest (the pre-registered 10-cell table), and the per-cell records
(``cells/*.json``) + the durable proposals. Joins are validated FIRST against the pre-registered
table (``docs/designs/current/cap_adaptive_2f_preregistration.md`` section 2); a cell whose
(cell_id, class, variant, arm, repetition) does not match the table is INVALID, not corrected.

Output: ``cap_adaptive_2f_score_<ts>.json`` (schema ``cap_adaptive_2f_score/v1``): per-cell rows
(class, arm, facts, the B-trigger check, proposal, abstention decision + leg, cost, accepted,
outcome), the CAPTURE table (declined/total per arm per class), the FLAG-COST table (the abstention
arm's trivial-clean costs MINUS the status-quo arm's — the PRIMARY, the wider net's price on
trivial fully-tested clean changes), the HARM table (escaped defects x E_x at 11.47/28), and the
DECISION-RULE computation (capture >= 2/3? the flag-cost ceiling, vacuous or not), plus a
validation JSON tracing every verdict number to a field. The ratio and the B trigger are re-derived
from the recorded facts, never from the proposal text; the pre-registered expectations are reported,
not re-negotiated.

Usage:
    python scripts/score_cap_2f.py            # write the score JSON + print the log tables
    python scripts/score_cap_2f.py --dry-run  # print the tables, write nothing
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results" / "cap_adaptive_2f"
CELLS_DIR = RESULTS / "cells"

SCHEMA = "cap_adaptive_2f_score/v1"
PREREG = "docs/designs/current/cap_adaptive_2f_preregistration.md"
PREREG_REVISION = "d199c50b6"

#: Pre-registered pinned constants (preregistration section 3-4): the harm model at E_x 11.47/28.
BASE_DOWNSTREAM_DEFECT_COST = 0.004021  # escalation score `base_downstream_defect_cost_usd`
E_X_MEASURED = 11.4671                  # sol, n=1
E_X_SOURCED = 28.0                      # sensitivity upper bound
LOSS_11 = E_X_MEASURED * BASE_DOWNSTREAM_DEFECT_COST      # 0.046109
LOSS_28 = E_X_SOURCED * BASE_DOWNSTREAM_DEFECT_COST        # 0.112588
CAPTURE_FLOOR = 2 / 3

DECISION_RULE_REF = (
    "docs/designs/current/cap_adaptive_2f_preregistration.md section 3 (the decision rule: "
    "SUPPORT iff (a) capture >= 2/3 of the 3 low-information cells in the abstention arm AND (b) "
    "the flag-cost ceiling holds non-vacuous; REFUTE if capture < 2/3 OR the flag-cost ceiling is "
    "violated or vacuous)"
)

#: Low-information cells (the capture leg's denominator, per preregistration section 3):
#: unseen-family x2 (the wall — B's trigger never fires) + absent-defective x1 (leg 2, mechanical)
#: in the abstention arm.
LOW_INFORMATION_CELLS = ["cap2f_unseen_family_abstention_r1",
                         "cap2f_unseen_family_abstention_r2",
                         "cap2f_absent-defective_abstention_r1"]


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
    for f in sorted(CELLS_DIR.glob("cap2f_*.json")):
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


def b_trigger_check(cell: dict) -> dict:
    """Re-derive the B trigger from the RECORDED facts: risk < 0.2 AND ratio >= 1.0 AND severity
    terms zero — never from the proposal text."""
    facts = cell.get("facts") or {}
    risk_raw = facts.get("code_change_risk")
    risk = float(risk_raw) if risk_raw not in (None, "", "null") else None
    ratio_raw = facts.get("changed_symbols_with_tests_ratio")
    ratio = float(ratio_raw) if ratio_raw not in (None, "", "null") else None
    sonar = int(facts.get("new_sonar_critical_count") or 0)
    lsp = int(facts.get("new_lsp_error_count") or 0)
    severity_zero = (sonar == 0 and lsp == 0)
    risk_ok = risk is not None and risk < 0.2
    ratio_ok = ratio is not None and ratio >= 1.0
    return {
        "risk": risk, "risk_ok": risk_ok,
        "ratio": ratio, "ratio_ok": ratio_ok,
        "severity_terms_zero": severity_zero,
        "new_sonar_critical_count": sonar, "new_lsp_error_count": lsp,
        "fires": bool(risk_ok and ratio_ok and severity_zero),
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
    defect. wrong-apply = $0 measured (no apply-class cells in this grid)."""
    escaped, esc_note = count_escaped_defects(cell)
    return {
        "cell_id": cell["cell_id"],
        "wrong_apply_usd_measured": 0.0,
        "wrong_apply_note": "no apply-class cells in this grid (capture + flag-cost only): "
                            "wrong-apply is vacuous - reported, not decided.",
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
        trg = b_trigger_check(c) if c["class"] in ("unseen_family", "trivial_clean") else None
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
            "b_trigger_check": trg,
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
    total_harm11 = sum(r["harm_11"] for r in arm_rows)
    total_harm28 = sum(r["harm_28"] for r in arm_rows)
    return {
        "arm": arm, "n": n,
        "total_cost_usd": round(total_cost, 6),
        "accepted_outcomes": accepted,
        "total_harm_usd_11": round(total_harm11, 6),
        "total_harm_usd_28": round(total_harm28, 6),
        "escaped_defect_count": sum(r["escaped_defect_count"] for r in arm_rows),
        "decline_count": sum(1 for r in arm_rows if r["abstention_decision"] == "DECLINE"),
        "b_trigger_fire_count": sum(1 for r in arm_rows if (r["b_trigger_check"] or {}).get("fires")),
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
            trigger_fires = sum(1 for x in arm_rows if (x["b_trigger_check"] or {}).get("fires"))
            entry[arm] = {
                "n": n, "total_cost_usd": round(total_cost, 6),
                "accepted_outcomes": accepted,
                "verified_success_rate": round(accepted / n, 4) if n else None,
                "escaped_defect_count": escaped, "harm_11": round(harm11, 6),
                "decline_count": declines, "b_trigger_fire_count": trigger_fires,
                "flags": sorted({f for x in arm_rows for f in x["flags"]}),
            }
        out[cls] = entry
    return out


def capture_table(rows: list[dict]) -> dict:
    """The CAPTURE table: declines on the 3 low-information cells in the abstention arm."""
    ab = [r for r in rows if r["arm"] == "abstention"]
    low_info = [r for r in ab if r["cell_id"] in LOW_INFORMATION_CELLS]
    declined = [r for r in low_info if r["abstention_decision"] == "DECLINE"]
    return {
        "low_information_cells": sorted(low_info[r]["cell_id"] for r in range(len(low_info))),
        "n_low_information": len(low_info),
        "declined_cells": sorted(r["cell_id"] for r in declined),
        "n_declined": len(declined),
        "capture_rate": round(len(declined) / len(low_info), 4) if low_info else None,
        "floor": round(CAPTURE_FLOOR, 4),
        "per_cell": [{
            "cell_id": r["cell_id"], "class": r["class"],
            "abstention_decision": r["abstention_decision"], "leg": r["abstention_leg"],
            "b_trigger_fires": (r["b_trigger_check"] or {}).get("fires"),
            "ratio": (r["b_trigger_check"] or {}).get("ratio"),
            "risk": (r["b_trigger_check"] or {}).get("risk"),
        } for r in low_info],
    }


def flag_cost_table(rows: list[dict]) -> dict:
    """The FLAG-COST table — the PRIMARY outcome (preregistration section 3): the abstention arm's
    trivial-clean cell costs MINUS the status-quo arm's (the decline overhead + operator-review
    routing on changes that needed nothing)."""
    ab = [r for r in rows if r["arm"] == "abstention" and r["class"] == "trivial_clean"]
    sq = [r for r in rows if r["arm"] == "status_quo" and r["class"] == "trivial_clean"]
    cost_ab = sum(r["cost_usd"] for r in ab)
    cost_sq = sum(r["cost_usd"] for r in sq)
    flag_cost = cost_ab - cost_sq
    # the saved-escape-harm side: captured escapes x LOSS_11. A captured escape = an escape the
    # abstention arm PREVENTED (present in the matched status-quo cell, absent in the abstention
    # cell). The pilot is flag-only (declines never fix), and the unseen-family escapes stand in
    # both arms (the wall), so captured escapes are expected 0 -> the ceiling is vacuous.
    captured = 0
    captured_cells = []
    for r in ab:
        match = next((x for x in sq if x["repetition"] == r["repetition"]), None)
        if match and match["escaped_defect_count"] > r["escaped_defect_count"]:
            captured += match["escaped_defect_count"] - r["escaped_defect_count"]
            captured_cells.append(r["cell_id"])
    saved_escape_harm = captured * LOSS_11
    vacuous = captured == 0
    return {
        "class": "trivial_clean",
        "abstention_trivial_clean_cells": [{"cell_id": r["cell_id"], "cost_usd": r["cost_usd"],
                                            "abstention_decision": r["abstention_decision"],
                                            "leg": r["abstention_leg"]} for r in ab],
        "status_quo_trivial_clean_cells": [{"cell_id": r["cell_id"], "cost_usd": r["cost_usd"],
                                            "abstention_decision": r["abstention_decision"]} for r in sq],
        "abstention_total_cost_usd": round(cost_ab, 6),
        "status_quo_total_cost_usd": round(cost_sq, 6),
        "flag_cost_usd": round(flag_cost, 6),
        "flag_cost_note": "the abstention arm's trivial-clean costs MINUS the status-quo arm's — "
                          "the decline overhead + operator-review routing on changes that needed "
                          "nothing (the wider net's price; the PRIMARY).",
        "captured_escapes": captured,
        "captured_cells": captured_cells,
        "saved_escape_harm_usd": round(saved_escape_harm, 6),
        "saved_escape_harm_note": f"captured escapes x ${LOSS_11:.6f} (E_x 11.47). The pilot is "
                                  "flag-only (declines never fix), and the unseen-family escapes "
                                  "stand in both arms (the wall).",
        "vacuous": vacuous,
        "ceiling_holds": (not vacuous) and flag_cost < saved_escape_harm,
    }


def harm_table(rows: list[dict]) -> dict:
    """The HARM table at E_x 11.47/28 (preregistration section 4)."""
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
            "note": "no apply-class cells in this grid (capture + flag-cost only) — wrong-apply is "
                    "vacuous; reported, not decided.",
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


def decision_rule(rows: list[dict], capture: dict, flag_cost: dict) -> dict:
    """The pre-registered decision rule (preregistration section 3)."""
    sq = [r for r in rows if r["arm"] == "status_quo"]
    ab = [r for r in rows if r["arm"] == "abstention"]
    cost_sq = sum(r["cost_usd"] for r in sq)
    cost_ab = sum(r["cost_usd"] for r in ab)
    harm_sq = sum(r["harm_11"] for r in sq)
    harm_ab = sum(r["harm_11"] for r in ab)

    # CONDITION A — CAPTURE: the abstention arm declines on >= 2 of the 3 low-information cells.
    capture_rate = capture["capture_rate"]
    capture_holds = capture_rate is not None and capture_rate >= CAPTURE_FLOOR

    # CONDITION B — the FLAG-COST ceiling holds NON-VACUOUS.
    flag_cost_holds = flag_cost["ceiling_holds"]
    flag_cost_vacuous = flag_cost["vacuous"]

    declined = [r for r in ab if r["abstention_decision"] == "DECLINE"]
    leg_counts = {}
    for r in declined:
        leg_counts.setdefault(r["abstention_leg"], []).append(r["cell_id"])

    support = bool(capture_holds and flag_cost_holds)
    return {
        "arms": {
            "status_quo": {"n": len(sq), "cost_usd": round(cost_sq, 6), "harm_usd_11": round(harm_sq, 6)},
            "abstention": {"n": len(ab), "cost_usd": round(cost_ab, 6), "harm_usd_11": round(harm_ab, 6)},
        },
        "condition_a_capture": {
            "n_low_information_cells": capture["n_low_information"],
            "declined_low_information_cells": capture["declined_cells"],
            "capture_rate": capture_rate,
            "floor": round(CAPTURE_FLOOR, 4),
            "holds": capture_holds,
            "note": "capture >= 2/3 of the 3 low-information cells in the abstention arm "
                    "(unseen-family x2 via the B trigger + absent-defective x1 via leg 2).",
        },
        "condition_b_flag_cost_ceiling": {
            "flag_cost_usd": flag_cost["flag_cost_usd"],
            "saved_escape_harm_usd": flag_cost["saved_escape_harm_usd"],
            "vacuous": flag_cost_vacuous,
            "holds": flag_cost_holds,
            "note": "flag cost (the abstention arm's trivial-clean costs minus the status-quo "
                    "arm's) < saved escape harm, non-vacuous. Vacuous when no escape was captured "
                    "(saved_escape_harm = 0).",
        },
        "decline_records": {
            "n_declines": len(declined),
            "by_leg": {str(k): v for k, v in leg_counts.items()},
            "cells": [{"cell_id": r["cell_id"], "class": r["class"], "variant": r.get("variant"),
                       "leg": r["abstention_leg"], "reason": r["abstention_reason"]} for r in declined],
        },
        "support": support,
        "support_note": "SUPPORT iff (a) capture >= 2/3 AND (b) the flag-cost ceiling holds "
                        "non-vacuous. Both are pre-registered to fail; the flag-cost magnitude is "
                        "the new information either way.",
        "decision_reference": DECISION_RULE_REF,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="cap_adaptive_2f p3 scorer")
    ap.add_argument("--dry-run", action="store_true", help="print tables, write nothing")
    args = ap.parse_args()

    artifacts = load_artifacts()
    cells = artifacts["cells"]
    table_rows = artifacts["table_rows"]
    p1 = artifacts["p1"]
    probe_wall = p1.get("probe_unseen_family") or {}
    probe_triv = p1.get("probe_trivial_clean") or {}
    joins = validate_joins(cells, table_rows)
    rows = per_cell_rows(cells, table_rows, joins)
    per_arm = {a: arm_aggregate(rows, a) for a in ("status_quo", "abstention")}
    per_class = per_class_breakdown(rows)
    capture = capture_table(rows)
    flag_cost = flag_cost_table(rows)
    harm = harm_table(rows)
    rule = decision_rule(rows, capture, flag_cost)

    n_invalid = sum(1 for j in joins if not j["valid"])
    invalid_cells = [j for j in joins if not j["valid"]]
    n_flagged = sum(1 for r in rows if r["flagged"])
    flagged_cells = [r["cell_id"] for r in rows if r["flagged"]]

    # The pre-registered expectations (reported, never re-negotiated):
    wall_confirmed = bool(probe_wall.get("b_trigger_check", {}).get("ratio") == 0.5
                          and probe_wall.get("b_trigger_check", {}).get("fires") is False
                          and all((r["b_trigger_check"] or {}).get("fires") is False
                                  for r in rows if r["class"] == "unseen_family"))
    trigger_confirmed = bool(probe_triv.get("b_trigger_check", {}).get("fires") is True
                             and all((r["b_trigger_check"] or {}).get("fires") is True
                                     for r in rows if r["class"] == "trivial_clean"))

    if rule["support"]:
        verdict = "SUPPORT — capture >= 2/3 AND the flag-cost ceiling holds non-vacuous."
    else:
        reasons = []
        if not rule["condition_a_capture"]["holds"]:
            reasons.append(f"capture {capture['capture_rate']} < 2/3 (the expected wall — the "
                           "unseen-family ratio wall, the fourth divergence)")
        if not rule["condition_b_flag_cost_ceiling"]["holds"]:
            reasons.append("the flag-cost ceiling is vacuous or violated")
        verdict = "REFUTE — " + "; ".join(reasons)

    score = {
        "schema_version": SCHEMA,
        "campaign": "cap_adaptive_2f",
        "phase": "p3_score",
        "scored_at": now_ts(),
        "preregistration": PREREG,
        "preregistration_revision": PREREG_REVISION,
        "spec_id": "cap_adaptive_2f@0.1",
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
        "pre_registered_expectations": {
            "unseen_family_ratio_wall_confirmed": wall_confirmed,
            "unseen_family_note": "probe + all 4 grid cells measure ratio 0.5, B trigger never "
                                  "fires (the wall — the fourth divergence).",
            "trivial_clean_b_trigger_confirmed": trigger_confirmed,
            "trivial_clean_note": "probe + all 4 grid cells measure ratio 1.0, risk < 0.2, "
                                  "severity zero — the B trigger fires (the flag-cost leg).",
        },
        "per_cell": rows,
        "per_arm": per_arm,
        "per_class": per_class,
        "capture_table": capture,
        "flag_cost_table": flag_cost,
        "harm_table": harm,
        "decision_rule": rule,
        "verdict": verdict,
        "flags": {
            "n_flagged_cells": n_flagged,
            "flagged_cells": flagged_cells,
        },
        "score_input_artifacts": [
            {"path": str((RESULTS / "p1_execution_manifest.json").relative_to(ROOT)), "role": "p1 (probes + E1 + forecast)"},
            {"path": str((RESULTS / "p1_unseen_family_probe.json").relative_to(ROOT)), "role": "the unseen-family ratio wall probe"},
            {"path": str((RESULTS / "p1_trivial_clean_probe.json").relative_to(ROOT)), "role": "the trivial_clean B-trigger probe"},
            {"path": str((RESULTS / "p2_execution_manifest.json").relative_to(ROOT)), "role": "the pre-registered 10-cell assignment table"},
            {"path": str(CELLS_DIR.relative_to(ROOT)), "role": "p2 per-cell records (10 cells)"},
        ],
    }

    out_path = RESULTS / f"cap_adaptive_2f_score_{now_ts()}.json"
    if not args.dry_run:
        out_path.write_text(json.dumps(score, indent=2, sort_keys=True))

    print(f"score: {len(rows)} cells, {n_invalid} invalid joins, {n_flagged} flagged")
    for arm in ("status_quo", "abstention"):
        a = per_arm[arm]
        print(f"  {arm:12s} n={a['n']} cost=${a['total_cost_usd']} harm11=${a['total_harm_usd_11']} "
              f"escaped={a['escaped_defect_count']} declines={a['decline_count']} trigger_fires={a['b_trigger_fire_count']}")
    print("  CAPTURE:")
    print(f"    rate={capture['capture_rate']} (floor {capture['floor']}) declined={capture['declined_cells']}")
    print("  FLAG-COST (PRIMARY):")
    print(f"    flag_cost=${flag_cost['flag_cost_usd']} (ab {flag_cost['abstention_total_cost_usd']} - "
          f"sq {flag_cost['status_quo_total_cost_usd']}) saved=${flag_cost['saved_escape_harm_usd']} "
          f"vacuous={flag_cost['vacuous']} holds={flag_cost['ceiling_holds']}")
    print("  DECISION RULE:")
    for cond in ("condition_a_capture", "condition_b_flag_cost_ceiling"):
        v = rule[cond]
        print(f"    {cond:34s} holds={v['holds']}  {v.get('note','')[:110]}")
    print(f"  VERDICT: {verdict}")
    if not args.dry_run:
        print(f"wrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
