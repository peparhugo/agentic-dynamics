"""P6 ``arm_comparison`` — the compare/adapt stage over real executed phases (d3 §5 P6).

Exposes the existing derivation: ``experiment.compile_experiment.compare_arms`` (with its
comparable-coverage rule) over every recorded agent phase in the workflow run ledgers,
grouped by model — plus the shadow-decision calibration summary the
``scripts/decision_arm_comparison.py`` report carries.

This module is the ONE writer of that derivation: the script is a thin renderer over it, and
the room serves it through ``GET /api/arms/compare``. A spec with fewer than two arms gets a
NAMED state (``single_arm``/``empty``) — never an error and never a fabricated winner.

``load_phase_outcomes`` is the module's only IO; builders are pure over injected rows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_dynamics.experiment.compile_experiment import compare_arms, decision_calibration

SCHEMA = "arm-comparison/v1"

#: The default loss (design §6.1's route_next_job contract objectives, inverted into a loss):
#: cost is a cost to minimize (weight 1.0), correctness a benefit to maximize (negative weight).
DEFAULT_LOSS: dict[str, float] = {"cost": 1.0, "quality": -5.0}


def load_phase_outcomes(results_dir: Path) -> tuple[list[dict[str, Any]], int]:
    """One row per AGENT phase across every recorded workflow run — the real, measured
    executed-phase corpus ``compare_arms`` scores.

    ``correctness`` is ``1.0``/``0.0`` from the phase's own recorded ``status`` (no independent
    quality signal is joined here). ``cost`` is carried ONLY when the ledger recorded a
    numeric ``cost_usd`` — an absent cost stays absent so the coverage rule can see it,
    instead of a default zero making an unmeasured phase look free.

    Returns ``(rows, n_ledgers)``; a missing directory is an honest empty corpus.
    """
    if not results_dir.is_dir():
        return [], 0
    rows: list[dict[str, Any]] = []
    n_ledgers = 0
    for path in sorted(results_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        n_ledgers += 1
        spec_name = str(data.get("spec_name") or "")
        for phase in data.get("phases") or []:
            if not isinstance(phase, dict):
                continue
            if phase.get("kind") != "agent" or not phase.get("model"):
                continue
            row: dict[str, Any] = {
                "spec_name": spec_name,
                "model": str(phase["model"]),
                "correctness": 1.0 if phase.get("status") == "ok" else 0.0,
            }
            cost = phase.get("cost_usd")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                row["cost"] = float(cost)
            rows.append(row)
    return rows, n_ledgers


def build_arm_comparison(
    rows: list[dict[str, Any]],
    *,
    spec: str | None = None,
    loss: dict[str, float] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the arm-comparison payload over ``rows`` (optionally filtered to one spec).

    Pure given its inputs. Always carries the compare output (with per-arm coverage); the
    ``state`` field names the empty/single-arm cases rather than erroring.
    """
    selected = [r for r in rows if not spec or str(r.get("spec_name") or "") == spec]
    effective_loss = loss or DEFAULT_LOSS
    comparison = compare_arms(selected, arm_factor="model", loss=effective_loss)
    calibration = decision_calibration(decisions or [])

    distinct_arms = list(comparison["arms"])
    if not selected:
        state = "empty"
        state_reason = (
            f"no executed phases recorded for spec {spec!r}" if spec else "no executed phases recorded"
        )
    elif len(distinct_arms) < 2:
        state = "single_arm"
        state_reason = "one arm — nothing to compare"
    else:
        state = "ranked"
        state_reason = ""

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": now,
        "source": dict(source or {}),
        "spec": spec or None,
        "state": state,
        "state_reason": state_reason,
        "arm_factor": comparison["arm_factor"],
        "loss": effective_loss,
        "n_outcomes": len(selected),
        "comparison": comparison,
        "decision_calibration": {
            "n_decisions": calibration.produces.get("n_decisions", 0),
            "decision_regret": calibration.produces.get("decision_regret"),
        },
        "degraded": [],
    }
    return payload
