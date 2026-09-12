#!/usr/bin/env python3
"""decision_arm_comparison.py — CAP I7's ``compare_arms`` hookup: evidence for the flip decision.

Design §9 I7: "compare_arms hookup: a script/report that scores the shadow decisions against
step_routing via compile_experiment.compare_arms-style loss (cost/quality) so the operator can
make the I7 flip decision with measured evidence."

HONEST LIMITATION, stated up front (recorded in
``docs/designs/implemented/implementation_notes.md``): in shadow mode (I6), the plane's ``route``
proposal is NEVER applied — only ``step_routing``'s choice ever executes a phase, so there is no
independently measured cost/quality outcome for "what if the plane's choice had run instead".
This script therefore reports TWO complementary signals rather than one fused "plane vs
step_routing" arm:

1. ``compile_experiment.compare_arms`` over the REAL executed phases (every recorded workflow
   run, ``experiments/results/workflows/**/*.json``), grouped by ``arm_factor="model"`` — the
   measured cost/quality loss per model that actually ran.
2. ``compile_experiment.decision_calibration``'s agreement rate (the same signal
   ``shadow_decision_report.py`` prints) — how often the plane's proposal WOULD have matched
   ``step_routing``'s actual choice.

Read together: a HIGH agreement rate means the plane mostly proposes what already runs (flipping
is low-risk almost by construction, since the "different" case is rare); a LOW agreement rate
means the plane is proposing something DIFFERENT more often — cross-reference (1)'s per-model
loss against the models the plane proposed on its DIVERGENT decisions (``--divergent-models``) to
see whether its typical alternative has a WORSE measured loss than the baseline, before ever
flipping ``workflow.params.control_route`` on for a real spec. Neither signal alone answers "is
it safe" — that judgment call is the operator's (design §9 I7's explicit gate), this script only
assembles the measured inputs to it.

Step 6: the derivation moved to ``control.projections.arm_comparison`` — this script is now a
renderer over that ONE implementation (the Control Room's ``GET /api/arms/compare`` serves the
same payload), so the report and the room can never disagree on the ranking.

    python scripts/decision_arm_comparison.py                # human-readable summary
    python scripts/decision_arm_comparison.py --json           # machine-readable
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

from agentic_dynamics.control.projections import arm_comparison as projection  # noqa: E402
from agentic_dynamics.control.rules import load_shadow_decisions  # noqa: E402
from agentic_dynamics.core.paths import PROJECT_ROOT  # noqa: E402

WORKFLOWS_RESULTS_DIR = PROJECT_ROOT / "experiments" / "results" / "workflows"

#: The default loss lives with the derivation (one definition, not two).
DEFAULT_LOSS: dict[str, float] = projection.DEFAULT_LOSS


def compute_report(
    *,
    results_dir: Path = WORKFLOWS_RESULTS_DIR,
    loss: dict[str, float] | None = None,
) -> dict[str, Any]:
    """The report payload: the shared projection's comparison + calibration summary."""
    outcomes, n_ledgers = projection.load_phase_outcomes(results_dir)
    payload = projection.build_arm_comparison(
        outcomes, loss=loss, decisions=load_shadow_decisions()
    )
    return {
        "n_executed_phases": len(outcomes),
        "n_workflow_ledgers": n_ledgers,
        "arms": payload["comparison"],
        "decision_calibration": payload["decision_calibration"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    report = compute_report()

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    print(f"executed phases (real, measured): {report['n_executed_phases']}")
    if report["n_executed_phases"] == 0:
        print("No workflow run ledgers found — nothing to compare arms over yet.")
    else:
        arms = report["arms"]
        print(f"best measured arm (model): {arms['best_arm']}")
        for arm, stats in sorted(arms["arms"].items()):
            print(f"  {arm}: n={stats['n']} weighted_loss={stats['weighted_loss']}")

    regret = report["decision_calibration"]["decision_regret"]
    n_decisions = report["decision_calibration"]["n_decisions"]
    print(f"\nshadow decisions recorded: {n_decisions}")
    if regret is not None:
        print(f"decision_regret (disagreement vs step_routing): {regret:.1%}")
    else:
        print("decision_regret: unmeasured (no shadow decisions recorded yet — "
              "`scripts/run_workflow.py --cap-shadow`)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
