#!/usr/bin/env python3
"""shadow_decision_report.py — CAP I6's gate: agreement/divergence vs ``step_routing``.

Design §9 I6's gate: "agreement/divergence vs step_routing measurable — a small report...
prints agreement rate and expected_effect scoring over the recorded decisions." Read-only.

Recorded shadow decisions (``control.rules.record_shadow_decision``) live as loose,
content-addressed JSON artifacts under ``KB_ARTIFACT_DIR`` — DELIBERATELY never published to the
registry/stream (design §8.6: the plane arms no actuation; a shadow decision is a
``source_type="actuation"`` artifact that never enters the live registry a real consumer would
react to — see ``docs/designs/implemented/implementation_notes.md``). This script scans that
directory directly (``extractor_version == "actuation/v1"``) rather than reading
``experiments/data_manifest.json``, unlike ``context_snapshot_report.py`` (I4's snapshots ARE
observation-family and DO go through the normal registry pipe).

    python scripts/shadow_decision_report.py           # human-readable summary
    python scripts/shadow_decision_report.py --json     # machine-readable

Zero decisions is not an error — the seam has not been enabled yet
(``scripts/run_workflow.py --cap-shadow``).
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.control.rules import load_shadow_decisions  # noqa: E402
from agentic_dynamics.experiment.compile_experiment import decision_calibration  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    decisions = load_shadow_decisions()
    result = decision_calibration(decisions)

    if args.json:
        print(json.dumps(
            {"rule": result.rule, "metric": result.metric, "produces": result.produces},
            indent=2, sort_keys=True,
        ))
        return 0

    if not decisions:
        print("No shadow decisions found — the seam has not recorded anything yet.")
        print("Enable it with `scripts/run_workflow.py --cap-shadow`, then re-run.")
        return 0

    n = result.produces.get("n_decisions", len(decisions))
    regret = result.produces.get("decision_regret")
    print(f"shadow decisions recorded: {n}")
    print(f"decision_regret (disagreement rate vs step_routing): {regret:.1%}")
    print(f"agreement rate: {1 - regret:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
