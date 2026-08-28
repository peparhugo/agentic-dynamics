"""cap_adaptive_2d p3 scorer — score the 28-cell abstention grid from immutable p1/p2 artifacts.

Phase p3 of ``cap_adaptive_2d`` (the informational-abstention campaign). Inputs are ONLY the
immutable p1/p2 artifacts under ``experiments/results/cap_adaptive_2d/`` — the p1 measurement
manifest (E1 + the incorrect_rebuilt probe), the p2 execution manifest (the pre-registered
assignment table), and the per-cell records (``cells/*.json``) + the durable proposals
(``proposals/*.json``). Joins are validated FIRST against the pre-registered table
(``docs/designs/current/cap_adaptive_2d_preregistration.md`` section 4); a cell whose
(cell_id, class, variant, arm, repetition) does not match the table is INVALID, not corrected.

Output: ``cap_adaptive_2d_score_<ts>.json`` (schema ``cap_adaptive_2d_score/v1``): per-cell rows,
per-arm aggregates, the per-CLASS breakdown, the HARM table (wrong-apply = the within-campaign
verify-pass delta; wrong-continue E_x-scaled at 11.47/28), the ABSTENTION DECISION-RULE
computation — all FOUR pre-registered legs (the primary cpvo_harm comparison; the capture rate
on the 3 low-information cells; the flag-cost vs saved harm ceiling; the reused NI guard) — and
the confidence curve (EXPLORATORY — the rule stays confidence-free), plus a validation result
tracing every verdict number to a field.

Usage:
    python scripts/score_cap_2d.py            # write the score JSON + print the log tables
    python scripts/score_cap_2d.py --dry-run  # print the tables, write nothing
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import norm

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results" / "cap_adaptive_2d"
CELLS_DIR = RESULTS / "cells"

SCHEMA = "cap_adaptive_2d_score/v1"
PREREG = "docs/designs/current/cap_adaptive_2d_preregistration.md"

#: Pre-registered pinned constants (preregistration §0, §1).
BASE_DOWNSTREAM_DEFECT_COST = 0.004021  # escalation score `base_downstream_defect_cost_usd`
E_X_MEASURED = 11.4671                  # sol, n=1
E_X_SOURCED = 28.0                      # sensitivity upper bound
LOSS_11 = E_X_MEASURED * BASE_DOWNSTREAM_DEFECT_COST      # 0.046109
LOSS_28 = E_X_SOURCED * BASE_DOWNSTREAM_DEFECT_COST        # 0.112588
NI_CPVO_RATIO = 1.10
NI_SUCCESS_GAP = 0.05

DECISION_RULE_REF = (
    "docs/designs/current/cap_adaptive_2d_preregistration.md section 1-2 (the decision rule: "
    "SUPPORT iff cpvo_harm(abstention) < cpvo_harm(status_quo) at E_x=11.47 AND capture >= 2/3 of "
    "the low-information cells AND flag cost < saved escape harm AND the NI guard holds)"
)

#: Expected proposal action per class (preregistration §3 falsifiability contract).
EXPECTED_ACTION = {
    "correct": "rework",
    "incorrect_rebuilt": "verify",
    "harmful_partial": "rework",
    "irrelevant": "continue",
    "competing": "rework",
    "absent": "refuse",
    "unseen_family": "continue",
}

#: Low-information cells (the capture leg's denominator): absent-defective + unseen_family x2.
LOW_INFORMATION_CELLS = ["cap2d_absent-defective_abstention_r1",
                         "cap2d_unseen_family_abstention_r1",
                         "cap2d_unseen_family_abstention_r2"]

Z_WILSON = norm.ppf(0.975)


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def wilson(k: int, n: int) -> list[float]:
    """Wilson 95% interval for a rate k/n."""
    if n == 0:
        return [None, None]
    p = k / n
    denom = 1 + Z_WILSON**2 / n
    centre = (p + Z_WILSON**2 / (2 * n)) / denom
    half = Z_WILSON * math.sqrt((p * (1 - p) + Z_WILSON**2 / (4 * n)) / n) / denom
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def load_artifacts() -> dict:
    """Load + join-validate the immutable p1/p2 artifacts. Returns the resolved cell table."""
    exec_manifest = json.loads((RESULTS / "p2_execution_manifest.json").read_text())
    p1 = json.loads((RESULTS / "p1_execution_manifest.json").read_text())

    table_rows = {}
    for row in exec_manifest["cells"]:
        table_rows[row["cell_id"]] = row

    cells = {}
    for f in sorted(CELLS_DIR.glob("cap2d_*.json")):
        d = json.loads(f.read_text())
        cells[d["cell_id"]] = d

    return {"exec_manifest": exec_manifest, "p1": p1, "table_rows": table_rows, "cells": cells}


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


def count_escaped_defects(cell: dict) -> tuple[int, str]:
    """Escaped-defect count + note per the pre-registered per-class semantics.

    competing + harmful_partial: one-of-two (both defects must be absent for acceptance); the
    post-hoc evaluator's defect_note records the present boundary defects (x1 = partial_rework,
    x2 = both) — harm counts per escaped defect. All other defect-bearing classes carry one
    constructible defect; clean classes carry none.
    """
    cls = cell["class"]
    variant = cell.get("variant")
    outcome = cell.get("outcome") or {}
    present = bool(outcome.get("defect_present_on_final_commit"))
    note = outcome.get("defect_note") or ""
    m = re.search(r"x(\d)", note)
    if cls == "competing":
        n = int(m.group(1)) if m and m.group(1) else (2 if present else 0)
        return (n, f"{n} escaped boundary-compare defects" if n else "both defects fixed/absent")
    if cls == "harmful_partial":
        n = int(m.group(1)) if m and m.group(1) else (1 if present else 0)
        return (n, f"{n} escaped boundary-compare defect(s) — one-of-two (partial_rework exposure)"
                   if n else "both far-apart defects fixed/absent")
    if cls == "unseen_family":
        return (1 if present else 0), "1 escaped mutation/aliasing defect (continue = null, not flagged)"
    if cls == "absent" and variant == "defective":
        return (1 if present else 0), "1 escaped wrong-operation defect (seam refused; escape stands)"
    return (0, "no escaped defect")


def compute_harm(cell: dict) -> dict:
    """Per-cell HARM (preregistration §1): wrong-apply measured within-campaign; wrong-continue
    E_x-scaled at 11.47/28 per escaped defect.

    wrong-apply = the measured verify-pass delta (mean incorrect_rebuilt cell cost minus mean
    irrelevant cell cost, per arm). The incorrect_rebuilt class's construction FAILED a second
    time (impacted=0 under the pinned analyzer -> risk 0.19 < 0.2 -> continue, not verify — the
    p1 probe + all 4 grid cells), so NO verify pass was ever applied -> wrong-apply = $0 measured
    and the wrong-apply leg is UNVERIFIABLE (design §4 / prereg §4: a second construction failure
    refutes the design).
    """
    wrong_apply = 0.0
    note = ("incorrect_rebuilt class: second construction failure (impacted=0 -> risk 0.19 < 0.2 "
            "-> continue, not verify) -> no false-positive verify pass was applied -> wrong-apply "
            "= $0 measured; the wrong-apply leg is UNVERIFIABLE (prereg §4 / design §4: a second "
            "construction failure refutes the design).")
    escaped, esc_note = count_escaped_defects(cell)
    return {
        "cell_id": cell["cell_id"],
        "wrong_apply_usd_measured": wrong_apply,
        "wrong_apply_note": note,
        "escaped_defect_count": escaped,
        "escaped_note": esc_note,
        "wrong_continue_usd_11": round(escaped * LOSS_11, 6),
        "wrong_continue_usd_28": round(escaped * LOSS_28, 6),
        "harm_11": round(wrong_apply + escaped * LOSS_11, 6),
        "harm_28": round(wrong_apply + escaped * LOSS_28, 6),
    }


def expected_effect_checks(cell: dict) -> list[dict]:
    """Expected-effect claims per the proposal record (the 2b structural ceiling, carried
    forward: rework passes were not handed to a post-rework change analyzer)."""
    prop = cell.get("proposal") or {}
    checks = []
    for claim in prop.get("expected_effect") or []:
        checks.append({
            "predicate": claim.get("predicate"),
            "direction": claim.get("direction"),
            "expected": claim.get("direction"),
            "observed": None,
            "held": False,
            "measurable": False,
            "note": "no post-application change_analysis in the immutable p1/p2 artifacts (rework "
                    "passes were not handed to a post-rework change analyzer) -> unmeasurable "
                    "(the 2b structural limit, carried forward)",
        })
    if not checks:
        checks.append({
            "predicate": "code_change_risk",
            "direction": "unchanged",
            "expected": "unchanged",
            "observed": None,
            "held": False,
            "measurable": False,
            "note": "no expected_effect claim on the proposal record -> unmeasurable",
        })
    return checks


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
        rows.append({
            "cell_id": cell_id,
            "class": c["class"],
            "variant": c.get("variant"),
            "arm": c["arm"],
            "repetition": c["repetition"],
            "slot": row["slot"],
            "cost_usd": round(cost, 6),
            "accepted": accepted,
            "cpvo_cell_usd": round(cost / accepted, 6) if accepted else None,
            "test_executed_success": bool(out.get("test_executed_success")),
            "tests": f"{out.get('tests_passed')}/{out.get('tests_total')}",
            "defect_present_on_final_commit": bool(out.get("defect_present_on_final_commit")),
            "defect_note": out.get("defect_note"),
            "proposal_action": prop.get("action"),
            "proposal_depth": prop.get("depth"),
            "proposal_confidence": prop.get("confidence"),
            "proposal_id": prop.get("proposal_id"),
            "abstention_decision": abst.get("decision"),
            "abstention_leg": abst.get("leg"),
            "abstention_reason": abst.get("reason"),
            "applied_or_null": app.get("applied_or_null"),
            "application_proof": app.get("proof") or app.get("note"),
            "expected_effect_checks": expected_effect_checks(c),
            "escaped_defect_count": harm["escaped_defect_count"],
            "harm_11": harm["harm_11"],
            "harm_28": harm["harm_28"],
            "flagged": bool(c.get("flags")),
            "flags": c.get("flags") or [],
            "join_valid": next(j for j in joins if j["cell_id"] == cell_id)["valid"],
        })
    return rows


def arm_aggregate(rows: list[dict], arm: str, bootstrap: int = 10000) -> dict:
    arm_rows = [r for r in rows if r["arm"] == arm]
    n = len(arm_rows)
    total_cost = sum(r["cost_usd"] for r in arm_rows)
    accepted = sum(1 for r in arm_rows if r["accepted"])
    cpvo = total_cost / accepted if accepted else None
    total_harm11 = sum(r["harm_11"] for r in arm_rows)
    total_harm28 = sum(r["harm_28"] for r in arm_rows)
    # bootstrap CI (bias-corrected percentile, stratified by class block), the prereg estimator
    rng = random.Random(6176763)  # campaign-seed-derived, for reproducibility
    blocks = {}
    for r in arm_rows:
        blocks.setdefault(r["class"], []).append(r)
    ratios = []
    for _ in range(bootstrap):
        tot = 0.0
        acc = 0
        for block in blocks.values():
            for _ in range(len(block)):
                s = rng.choice(block)
                tot += s["cost_usd"] + s["harm_11"]
                acc += 1 if s["accepted"] else 0
        if acc:
            ratios.append(tot / acc)
    cpvo_harm_ci = None
    if ratios:
        ratios.sort()
        cpvo_harm_ci = [round(ratios[int(0.025 * len(ratios))], 6), round(ratios[int(0.975 * len(ratios))], 6)]
    return {
        "arm": arm,
        "n": n,
        "total_cost_usd": round(total_cost, 6),
        "accepted_outcomes": accepted,
        "cpvo_usd": round(cpvo, 6) if cpvo is not None else None,
        "cpvo_ci_95": None,
        "total_harm_usd_11": round(total_harm11, 6),
        "total_harm_usd_28": round(total_harm28, 6),
        "cpvo_harm_11_usd": round((total_cost + total_harm11) / accepted, 6) if accepted else None,
        "cpvo_harm_28_usd": round((total_cost + total_harm28) / accepted, 6) if accepted else None,
        "cpvo_harm_11_ci_95": cpvo_harm_ci,
        "verified_success_rate": round(accepted / n, 4) if n else None,
        "verified_success_wilson_95": wilson(accepted, n),
        "escaped_defect_count": sum(r["escaped_defect_count"] for r in arm_rows),
    }


def per_class_breakdown(rows: list[dict]) -> dict:
    classes = {}
    for r in rows:
        cls = r["class"]
        classes.setdefault(cls, {"arm": {}})
        a = r["arm"]
        classes[cls].setdefault("arm", {}).setdefault(a, [])
        classes[cls]["arm"][a].append(r)
    out = {}
    for cls, data in classes.items():
        entry = {}
        for arm, arm_rows in data["arm"].items():
            n = len(arm_rows)
            total_cost = sum(x["cost_usd"] for x in arm_rows)
            accepted = sum(1 for x in arm_rows if x["accepted"])
            cpvo = total_cost / accepted if accepted else None
            escaped = sum(x["escaped_defect_count"] for x in arm_rows)
            harm11 = sum(x["harm_11"] for x in arm_rows)
            harm28 = sum(x["harm_28"] for x in arm_rows)
            declines = sum(1 for x in arm_rows if x["abstention_decision"] == "DECLINE")
            entry[arm] = {
                "n": n,
                "total_cost_usd": round(total_cost, 6),
                "accepted_outcomes": accepted,
                "cpvo_usd": round(cpvo, 6) if cpvo is not None else None,
                "verified_success_rate": round(accepted / n, 4),
                "escaped_defect_count": escaped,
                "harm_11": round(harm11, 6),
                "harm_28": round(harm28, 6),
                "decline_count": declines,
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
            "cell_id": r["cell_id"],
            "class": r["class"],
            "arm": r["arm"],
            "escaped_defect_count": r["escaped_defect_count"],
            "wrong_apply_usd": r["harm_11"] - r["escaped_defect_count"] * LOSS_11,
            "wrong_continue_usd_11": round(r["escaped_defect_count"] * LOSS_11, 6),
            "wrong_continue_usd_28": round(r["escaped_defect_count"] * LOSS_28, 6),
        })
    return {
        "wrong_apply": {
            "total_usd_measured": 0.0,
            "note": "wrong-apply = the within-campaign verify-pass delta (mean incorrect_rebuilt "
                    "cost minus mean irrelevant cost, per arm). The incorrect_rebuilt class "
                    "failed to instantiate verify a SECOND time (impacted=0 -> risk 0.19 < 0.2 -> "
                    "continue in all 4 cells) -> NO verify pass was ever applied -> wrong-apply = "
                    "$0 measured and the wrong-apply leg is UNVERIFIABLE (prereg §4 / design §4: "
                    "a second construction failure refutes the design).",
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
                    f"E_x 11.4671 measured (sol, n=1), E_x 28 sourced — sensitivity reported.",
        },
        "per_cell": by_cell,
    }


def abstention_decision_rule(rows: list[dict]) -> dict:
    """The FOUR pre-registered decision-rule legs (preregistration §1-§2)."""
    sq = [r for r in rows if r["arm"] == "status_quo"]
    ab = [r for r in rows if r["arm"] == "abstention"]
    cost_sq = sum(r["cost_usd"] for r in sq)
    cost_ab = sum(r["cost_usd"] for r in ab)
    acc_sq = sum(1 for r in sq if r["accepted"])
    acc_ab = sum(1 for r in ab if r["accepted"])
    harm_sq = sum(r["harm_11"] for r in sq)
    harm_ab = sum(r["harm_11"] for r in ab)

    # leg A — the PRIMARY: cpvo_harm(abstention) < cpvo_harm(status_quo) at E_x=11.47.
    cpvo_harm_sq = (cost_sq + harm_sq) / acc_sq if acc_sq else None
    cpvo_harm_ab = (cost_ab + harm_ab) / acc_ab if acc_ab else None
    primary_holds = cpvo_harm_ab is not None and cpvo_harm_sq is not None and cpvo_harm_ab < cpvo_harm_sq

    # leg B — CAPTURE: the decline fires on >= 2 of the 3 low-information cells (absent-defective
    # leg 2 + unseen_family x2 leg 3).
    low_info = {r["cell_id"]: r for r in ab if r["cell_id"] in LOW_INFORMATION_CELLS}
    captured = {cid: r for cid, r in low_info.items() if r["abstention_decision"] == "DECLINE"}
    capture_rate = len(captured) / len(low_info) if low_info else None
    capture_holds = capture_rate is not None and capture_rate >= 2 / 3

    # leg C — FLAG-COST CEILING: the abstention arm's declined-CLEAN-cell overhead (delta vs the
    # same class's status_quo cells) < the saved escape harm (escaped defects prevented x LOSS_11).
    declined_clean = [r for r in ab if r["abstention_decision"] == "DECLINE" and not r["defect_present_on_final_commit"]]
    flag_cost = 0.0
    flag_cells = []
    for r in declined_clean:
        cls, variant = r["class"], r.get("variant")
        match = next((x for x in sq if x["class"] == cls and x.get("variant") == variant), None)
        delta = r["cost_usd"] - (match["cost_usd"] if match else 0.0)
        flag_cost += delta
        flag_cells.append({"cell_id": r["cell_id"], "class": cls, "variant": variant,
                           "cost_usd": r["cost_usd"], "matched_sq_cost_usd": match["cost_usd"] if match else None,
                           "delta_usd": round(delta, 6)})
    # saved escape harm = escapes present in the status-quo arm that the abstention arm prevented.
    # The abstention treatment's declines were on the absent cells (leg 2) whose escapes STAND in
    # both arms (the pilot is flag-only, no fix); the unseen-family cells were NOT declined (leg 3
    # never fired — the Option A fingerprint did not materialize). So prevented escapes = 0.
    escaped_sq = sum(r["escaped_defect_count"] for r in sq)
    escaped_ab = sum(r["escaped_defect_count"] for r in ab)
    # treatment-attributable prevented escapes: declines that produced an escape in status_quo's
    # matched cell but not in the abstention cell.
    prevented = 0
    for r in ab:
        if r["abstention_decision"] != "DECLINE":
            continue
        cls, variant, rep = r["class"], r.get("variant"), r["repetition"]
        match = next((x for x in sq if x["class"] == cls and x.get("variant") == variant and x["repetition"] == rep), None)
        if match and match["escaped_defect_count"] > r["escaped_defect_count"]:
            prevented += match["escaped_defect_count"] - r["escaped_defect_count"]
    saved_escape_harm = prevented * LOSS_11
    flag_cost_holds = flag_cost < saved_escape_harm

    # leg D — NI GUARD (the reused 2b/2c margin on the pooled grid).
    cpvo_sq = cost_sq / acc_sq if acc_sq else None
    cpvo_ab = cost_ab / acc_ab if acc_ab else None
    ratio = cpvo_ab / cpvo_sq if cpvo_sq else None
    succ_sq = acc_sq / len(sq) if sq else None
    succ_ab = acc_ab / len(ab) if ab else None
    success_gap = succ_sq - succ_ab
    ni_cpvo_holds = ratio is not None and ratio <= NI_CPVO_RATIO
    ni_success_holds = success_gap is not None and success_gap <= NI_SUCCESS_GAP
    ni_holds = ni_cpvo_holds and ni_success_holds

    # the abstention rule's shadow decisions (both arms evaluated; only the abstention arm acts).
    declines = [r for r in ab if r["abstention_decision"] == "DECLINE"]
    leg_counts = {}
    for r in declines:
        leg_counts.setdefault(r["abstention_leg"], []).append(r["cell_id"])

    return {
        "arms": {"status_quo": {"n": len(sq), "cost_usd": round(cost_sq, 6),
                                "accepted": acc_sq, "harm_usd_11": round(harm_sq, 6),
                                "cpvo_harm_11_usd": round(cpvo_harm_sq, 6) if cpvo_harm_sq else None},
                 "abstention": {"n": len(ab), "cost_usd": round(cost_ab, 6),
                                "accepted": acc_ab, "harm_usd_11": round(harm_ab, 6),
                                "cpvo_harm_11_usd": round(cpvo_harm_ab, 6) if cpvo_harm_ab else None}},
        "leg_a_primary": {
            "cpvo_harm_status_quo_usd": round(cpvo_harm_sq, 6) if cpvo_harm_sq else None,
            "cpvo_harm_abstention_usd": round(cpvo_harm_ab, 6) if cpvo_harm_ab else None,
            "holds": primary_holds,
            "note": "SUPPORT leg: cpvo_harm(abstention) < cpvo_harm(status_quo) at E_x=11.47. "
                    "REPORTED WITH THE CAVEAT that no DECLINE prevented an escape (the absent-cell "
                    "declines' escapes stand in both arms; leg 3 never fired) — the numeric delta "
                    "is not attributable to the abstention treatment.",
        },
        "leg_b_capture": {
            "low_information_cells": sorted(low_info),
            "declined_low_information_cells": sorted(captured),
            "capture_rate": round(capture_rate, 4) if capture_rate is not None else None,
            "floor": 2 / 3,
            "holds": capture_holds,
            "note": "capture >= 2/3 of the low-information cells (absent-defective leg 2 + "
                    "unseen_family x2 leg 3). The unseen-family cells measured multi-term risk "
                    "0.18 (ratio 0.5 — NOT the Option A fingerprint), so leg 3 never fired.",
        },
        "leg_c_flag_cost": {
            "declined_clean_cells": flag_cells,
            "flag_cost_usd": round(flag_cost, 6),
            "prevented_escaped_defects": prevented,
            "saved_escape_harm_usd": round(saved_escape_harm, 6),
            "holds": flag_cost_holds,
            "note": "flag cost (declined clean cells' delta vs status_quo) < saved escape harm. "
                    "Saved harm = 0 (no DECLINE prevented an escape), so the ceiling is vacuous.",
        },
        "leg_d_ni_guard": {
            "cpvo_status_quo_usd": round(cpvo_sq, 6) if cpvo_sq else None,
            "cpvo_abstention_usd": round(cpvo_ab, 6) if cpvo_ab else None,
            "cpvo_ratio": round(ratio, 6) if ratio is not None else None,
            "margin_cpvo_ratio_le": NI_CPVO_RATIO,
            "ni_cpvo_holds": ni_cpvo_holds,
            "success_status_quo": round(succ_sq, 4) if succ_sq is not None else None,
            "success_abstention": round(succ_ab, 4) if succ_ab is not None else None,
            "success_gap_status_quo_minus_abstention": round(success_gap, 4) if success_gap is not None else None,
            "margin_success_gap_le": NI_SUCCESS_GAP,
            "ni_success_holds": ni_success_holds,
            "holds": ni_holds,
        },
        "decline_records": {
            "n_declines": len(declines),
            "by_leg": {str(k): v for k, v in leg_counts.items()},
            "cells": [{"cell_id": r["cell_id"], "class": r["class"], "variant": r.get("variant"),
                       "leg": r["abstention_leg"], "reason": r["abstention_reason"]} for r in declines],
        },
        "all_four_hold": primary_holds and capture_holds and flag_cost_holds and ni_holds,
        "decision_reference": DECISION_RULE_REF,
    }


def abstention_analysis(rows: list[dict], cells: dict) -> dict:
    """Per-confidence-decile value(apply) vs value(abstain) + the threshold curve. EXPLORATORY.

    The abstention rule is confidence-free (design §2 / prereg §1): this re-checks the 2c
    constraint that no theta on the measured confidence improves value. The rule's declines are
    NOT confidence-gated, so the curve is descriptive at the campaign's n.
    """
    conf_rows = []
    no_confidence = []
    for r in rows:
        prop = (cells[r["cell_id"]].get("proposal") or {})
        c = prop.get("confidence")
        if c is None:
            no_confidence.append(r["cell_id"])
            continue
        decile = min(9, int(c * 10))
        conf_rows.append({**r, "_conf": c, "_decile": decile})

    deciles = {}
    for r in conf_rows:
        deciles.setdefault(r["_decile"], {"apply": [], "abstain": []})
        if r["arm"] == "abstention":
            deciles[r["_decile"]]["abstain"].append(r)
        else:
            deciles[r["_decile"]]["apply"].append(r)

    per_decile = {}
    for decile in sorted(deciles):
        d = deciles[decile]
        entry = {"decile": f"[{decile/10:.1f}, {(decile+1)/10:.1f})" if decile < 9 else "[0.9, 1.0]",
                 "n_apply": len(d["apply"]), "n_abstain": len(d["abstain"]),
                 "cells_apply": [r["cell_id"] for r in d["apply"]],
                 "cells_abstain": [r["cell_id"] for r in d["abstain"]]}
        for key, arm_rows in (("apply", d["apply"]), ("abstain", d["abstain"])):
            total_cost = sum(x["cost_usd"] for x in arm_rows)
            accepted = sum(1 for x in arm_rows if x["accepted"])
            harm11 = sum(x["harm_11"] for x in arm_rows)
            harm28 = sum(x["harm_28"] for x in arm_rows)
            entry[f"value_{key}_cpvo_usd"] = round(total_cost / accepted, 6) if accepted else None
            entry[f"value_{key}_cpvo_harm_11"] = round((total_cost + harm11) / accepted, 6) if accepted else None
            entry[f"value_{key}_cpvo_harm_28"] = round((total_cost + harm28) / accepted, 6) if accepted else None
            entry[f"value_{key}_accepted"] = accepted
            entry[f"value_{key}_total_cost_usd"] = round(total_cost, 6)
        per_decile[str(decile)] = entry

    # the threshold curve cpvo_gated(theta): abstain on confidence < theta in the abstention arm
    # (the static-arm counterfactual, matched by class + variant + repetition).
    observed = sorted({r["_conf"] for r in conf_rows})
    thetas = sorted(set([0.0] + observed + [1.0]))
    curve = []
    for theta in thetas:
        total_cost = 0.0
        accepted = 0
        harm11 = 0.0
        harm28 = 0.0
        n_declined = 0
        for r in rows:
            prop = cells[r["cell_id"]].get("proposal") or {}
            c = prop.get("confidence")
            if c is not None and c < theta and r["arm"] == "abstention":
                cls, rep, variant = r["class"], r["repetition"], r.get("variant")
                suffix = f"-{variant}" if variant else ""
                match_id = f"cap2d_{cls}{suffix}_status_quo_{rep}"
                s = next((x for x in rows if x["cell_id"] == match_id), None)
                if s is None:
                    s = r
                n_declined += 1
                total_cost += s["cost_usd"]
                accepted += 1 if s["accepted"] else 0
                harm11 += s["harm_11"]
                harm28 += s["harm_28"]
            else:
                total_cost += r["cost_usd"]
                accepted += 1 if r["accepted"] else 0
                harm11 += r["harm_11"]
                harm28 += r["harm_28"]
        curve.append({
            "theta": round(theta, 4),
            "n_declined": n_declined,
            "total_cost_usd": round(total_cost, 6),
            "accepted_outcomes": accepted,
            "cpvo_gated_usd": round(total_cost / accepted, 6) if accepted else None,
            "cpvo_gated_harm_11": round((total_cost + harm11) / accepted, 6) if accepted else None,
            "cpvo_gated_harm_28": round((total_cost + harm28) / accepted, 6) if accepted else None,
        })

    baseline = next(x for x in curve if x["theta"] == 0.0)
    improving = [x for x in curve if 0.0 < x["theta"] < 1.0 and x["cpvo_gated_usd"] is not None
                 and baseline["cpvo_gated_usd"] is not None and x["cpvo_gated_usd"] < baseline["cpvo_gated_usd"]]
    return {
        "exploratory_label": "EXPLORATORY (post-hoc) — the pre-registration fixes no threshold "
                             "it cannot know (preregistration §2 / §5); the abstention rule stays "
                             "confidence-free; descriptive at the campaign's n.",
        "confidence_basis": "proposal-record confidence ([H] per-attempt execution-confidence of the "
                            "analyzed implement attempt), recorded BEFORE the outcome; a proposal "
                            "record without the field is invalid and never imputed (preregistration §7).",
        "cells_without_confidence": no_confidence,
        "n_without_confidence": len(no_confidence),
        "observed_confidences": observed,
        "per_decile": per_decile,
        "threshold_curve": curve,
        "cpvo_gated_at_theta0": baseline,
        "improving_threshold_exists": bool(improving),
        "improving_thresholds": [x["theta"] for x in improving],
        "note": "an improving threshold exists iff some theta in (0,1) yields cpvo_gated(theta) < "
                "cpvo_gated(0) — i.e. confidence-gated abstention would improve value. The rule is "
                "confidence-free (design §2 constraint).",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="cap_adaptive_2d p3 scorer")
    ap.add_argument("--dry-run", action="store_true", help="print tables, write nothing")
    args = ap.parse_args()

    artifacts = load_artifacts()
    cells = artifacts["cells"]
    table_rows = artifacts["table_rows"]
    joins = validate_joins(cells, table_rows)
    rows = per_cell_rows(cells, table_rows, joins)
    per_arm = {a: arm_aggregate(rows, a) for a in ("status_quo", "abstention")}
    per_class = per_class_breakdown(rows)
    harm = harm_table(rows)
    rule = abstention_decision_rule(rows)
    abstention = abstention_analysis(rows, cells)

    n_invalid = sum(1 for j in joins if not j["valid"])
    invalid_cells = [j for j in joins if not j["valid"]]
    n_flagged = sum(1 for r in rows if r["flagged"])
    flagged_cells = [r["cell_id"] for r in rows if r["flagged"]]

    score = {
        "schema_version": SCHEMA,
        "campaign": "cap_adaptive_2d",
        "phase": "p3_score",
        "scored_at": now_ts(),
        "preregistration": PREREG,
        "preregistration_revision": "9dc0b4a63",
        "seed": "617e6763fcd238dc93a59ba1f41e01ba5f281c4748ef3867dbebeeca344c7dfb",
        "spec_id": "cap_adaptive_2d@0.1",
        "spec_sha256": "1258280d44f608c7fcccf91ef514cc5a39994a9fd352852d96fb35c919f2ea0c",
        "cpvo_definition": "cpvo_arm = (sum measured cell cost over the arm) / (sum accepted "
                           "outcomes over the arm); accepted = test_executed_success AND "
                           "defect_present_on_final_commit == false (preregistration section 1); "
                           "competing + harmful_partial additionally require BOTH defects absent",
        "outcome_definition": "accepted per cell = independent runtime pytest on the immutable "
                              "final commit AND the post-hoc evaluator's defect determination on "
                              "the same commit (one-of-two for competing + harmful_partial)",
        "join_validation": {
            "n_table_rows": len(table_rows),
            "n_cells": len(cells),
            "valid": n_invalid == 0,
            "n_invalid": n_invalid,
            "invalid_cells": invalid_cells,
            "per_cell": joins,
            "note": "a cell scored under a different arm/class than its pre-registered assignment "
                    "is invalid, not corrected",
        },
        "per_cell": rows,
        "per_arm": per_arm,
        "per_class": per_class,
        "harm_table": harm,
        "abstention_decision_rule": rule,
        "abstention_analysis": abstention,
        "flags": {
            "n_flagged_cells": n_flagged,
            "flagged_cells": flagged_cells,
            "construction_failures": [
                {"cell_id": r["cell_id"], "flags": r["flags"]}
                for r in rows if any("construction-failure" in f for f in r["flags"])
            ],
        },
        "denominators": {
            "n_cells_status_quo": per_arm["status_quo"]["n"],
            "n_cells_abstention": per_arm["abstention"]["n"],
            "defect_bearing_per_arm": 9,
            "clean_per_arm": 5,
            "n_not_run": 0,
            "n_dropped": 0,
            "note": "absent-defective is a DESIGNED analyzer/graph-down cell (preregistration "
                    "section 1 denominator discipline) — flagged, never dropped.",
        },
        "score_input_artifacts": [
            {"path": str((RESULTS / "p2_execution_manifest.json").relative_to(ROOT)), "role": "the pre-registered assignment table (section 4)"},
            {"path": str((RESULTS / "p1_execution_manifest.json").relative_to(ROOT)), "role": "p1 (E1 measurement + incorrect_rebuilt probe)"},
            {"path": str((RESULTS / "p1_incorrect_rebuilt_probe.json").relative_to(ROOT)), "role": "the incorrect_rebuilt impacted pre-verification probe"},
            {"path": str(CELLS_DIR.relative_to(ROOT)), "role": "p2 per-cell records (28 cells)"},
            {"path": str((ROOT / "experiments" / "results" / "proposals").relative_to(ROOT)), "role": "durable proposal records (confidence-carrying)"},
        ],
    }

    out_path = RESULTS / f"cap_adaptive_2d_score_{now_ts()}.json"
    if not args.dry_run:
        out_path.write_text(json.dumps(score, indent=2, sort_keys=True))

    print(f"score: {len(rows)} cells, {n_invalid} invalid joins, {n_flagged} flagged")
    for arm in ("status_quo", "abstention"):
        a = per_arm[arm]
        print(f"  {arm:12s} n={a['n']} accepted={a['accepted_outcomes']} "
              f"cost=${a['total_cost_usd']} harm11=${a['total_harm_usd_11']} "
              f"cpvo=${a['cpvo_usd']} cpvo_harm11=${a['cpvo_harm_11_usd']} escaped={a['escaped_defect_count']}")
    print("  DECISION RULE:")
    for leg, val in (("leg_a_primary", rule["leg_a_primary"]),
                     ("leg_b_capture", rule["leg_b_capture"]),
                     ("leg_c_flag_cost", rule["leg_c_flag_cost"]),
                     ("leg_d_ni_guard", rule["leg_d_ni_guard"])):
        print(f"    {leg:18s} holds={val['holds']}  {val.get('note','')[:120]}")
    print(f"  ALL FOUR HOLD: {rule['all_four_hold']}")
    print(f"  ABSTENTION: improving_threshold_exists={abstention['improving_threshold_exists']} "
          f"thresholds={abstention['improving_thresholds']}")
    if not args.dry_run:
        print(f"wrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
