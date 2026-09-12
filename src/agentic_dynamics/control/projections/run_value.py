"""P5 ``run_value`` — observed-only accepted outcomes and cost per accepted outcome (d3 §5 P5).

The formula is the preregistered site KPI, in its correct orientation:

    cost_per_accepted = total_cost / accepted_outcomes

(d3's acceptance line printed ``accepted/cost`` — the inverted ratio; the close record and
the preregistrations (``cap_2b_preregistration`` §1: ``cpvo = total arm cost / accepted
outcomes``) are the authority. The inversion is pinned by a test.)

Observed-only, by construction:

* ``total_cost`` sums only captured costs (``cost_captured``) — an absent cost leaves the
  ratio ``None`` with the reason ``unmeasured_cost``, never a zero denominator or a $0.00;
* zero accepted outcomes in a group yields ``None`` with the reason ``no_accepted_outcomes``
  (a ratio with a zero denominator is unknown, never 0.0 or infinite);
* **BVI is NOT computed.** It is a declared modeled scenario: its inputs (H human cost, W
  workload) have no owners, so the payload carries ``state: "modeled"`` with null value and
  null inputs — the honest label until the inputs have owners (close record: "modeled BVI
  stays a declared scenario until its inputs have owners").

Rows are injected; ``load_attempt_value_rows`` is the module's only IO (attempt-ledger
payloads: ``cells[].status`` + ``cells[].realized_cost``).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from agentic_dynamics.reporting.measurement_coverage import captured_costs

SCHEMA = "run-value/v1"

#: The published formula — carried in the payload so the orientation is never guessed.
FORMULA = "cost_per_accepted = total_cost / accepted_outcomes"

#: Terminal attempt statuses that are explicit non-acceptances (a measured False). Any other
#: non-empty status is an outcome that has not settled (or a designed stop) -> None.
NOT_ACCEPTED_STATUSES = frozenset({"failed", "dead_letter", "timeout", "canceled", "cancelled"})


def _accepted_from_status(status: str) -> bool | None:
    """Map an attempt status to the outcome flag; unknown/empty stays None (never False)."""
    if status == "accepted":
        return True
    if status in NOT_ACCEPTED_STATUSES:
        return False
    return None


def load_attempt_value_rows(results_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read attempt-ledger payloads into value rows, returning ``(rows, paths_read)``.

    A payload is an attempt ledger when it carries a ``cells`` list with at least one
    ``attempts`` array (the same discriminator ``aggregate_workflow_metrics`` documents); a
    missing directory is an honest empty population.
    """
    rows: list[dict[str, Any]] = []
    paths: list[str] = []
    if not results_dir.is_dir():
        return rows, paths
    for path in sorted(results_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cells = payload.get("cells") if isinstance(payload, dict) else None
        if not isinstance(cells, list):
            continue
        if not any(isinstance(c, dict) and isinstance(c.get("attempts"), list) for c in cells):
            continue
        paths.append(str(path))
        spec = str(payload.get("spec_id") or path.stem)
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            cost = cell.get("realized_cost")
            rows.append(
                {
                    "run": spec,
                    "arm": str(cell.get("policy_arm") or cell.get("model") or "unknown"),
                    "accepted": _accepted_from_status(str(cell.get("status") or "")),
                    "cost_usd": float(cost)
                    if isinstance(cost, (int, float)) and not isinstance(cost, bool)
                    else None,
                    "cost_source": "realized_cost",
                }
            )
    return rows, paths


def build_run_value(
    rows: list[dict[str, Any]],
    *,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Group rows by (run, arm) and compute the observed-only value block per group.

    Pure given its inputs. Each group reports its coverage (cost captured / outcomes
    measured) before the ratio, and both unknown reasons are named.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    order: list[tuple[str, str]] = []
    for row in rows:
        key = (str(row.get("run") or ""), str(row.get("arm") or ""))
        if key not in groups:
            order.append(key)
        groups[key].append(row)

    blocks: list[dict[str, Any]] = []
    for key in order:
        group = groups[key]
        costs = captured_costs(r.get("cost_usd") for r in group)
        measured = [r for r in group if isinstance(r.get("accepted"), bool)]
        accepted = sum(1 for r in measured if r["accepted"])
        total_cost = round(sum(costs), 6) if costs else None
        ratio = (
            round(total_cost / accepted, 6)
            if (total_cost is not None and accepted > 0)
            else None
        )
        block: dict[str, Any] = {
            "run": key[0],
            "arm": key[1],
            "outcomes_total": len(group),
            "outcomes_measured": len(measured),
            "accepted_outcomes": accepted,
            "cost_captured_records": len(costs),
            "cost_coverage": round(len(costs) / len(group), 4) if group else 0.0,
            "total_cost_usd": total_cost,
            "cost_per_accepted": ratio,
        }
        if ratio is None:
            if accepted == 0:
                block["cost_per_accepted_reason"] = "no_accepted_outcomes"
            elif total_cost is None:
                block["cost_per_accepted_reason"] = "unmeasured_cost"
        blocks.append(block)

    return {
        "schema": SCHEMA,
        "generated_at": now,
        "source": dict(source or {}),
        "formula": FORMULA,
        "observed_only": True,
        "rows": blocks,
        "bvi": {
            "state": "modeled",
            "class": "[P]",
            "value": None,
            "inputs": {"H": None, "W": None},
            "reason": (
                "modeled scenario — H (human cost) and W (workload) have no owners; "
                "not computed (G-36/G-37)"
            ),
        },
        "degraded": [],
    }
