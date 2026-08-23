#!/usr/bin/env python3
"""shadow_decision_report.py — CAP I6's gate: agreement/divergence vs ``step_routing``.

Design §9 I6's gate: "agreement/divergence vs step_routing measurable — a small report...
prints agreement rate and expected_effect scoring over the recorded decisions." Read-only.

Recorded shadow decisions (``control.rules.record_shadow_decision``) live as loose,
content-addressed JSON artifacts under ``KB_ARTIFACT_DIR`` — DELIBERATELY never published to the
registry/stream (design §8.6: the plane arms no actuation; a shadow decision is a
``source_type="actuation"`` artifact that never enters the live registry a real consumer would
react to — see ``docs/context_abstraction/implementation_notes.md``). This script scans that
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
from pathlib import Path
from typing import Any

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.control.actuation_ingestion import EXTRACTOR_VERSION  # noqa: E402
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR  # noqa: E402
from agentic_dynamics.experiment.compile_experiment import decision_calibration  # noqa: E402


def load_shadow_decisions(*, artifact_dir: Path = KB_ARTIFACT_DIR) -> list[dict[str, Any]]:
    """Scan ``artifact_dir`` for recorded shadow-decision artifacts and return their
    ``decision_calibration``-shaped rows (``{action, baseline_action, model, baseline_model}``)."""
    if not artifact_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(artifact_dir.glob("*.json")):
        try:
            artifact = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if artifact.get("source_type") != "actuation":
            continue
        if artifact.get("extractor_version") != EXTRACTOR_VERSION:
            continue
        try:
            body = json.loads(artifact.get("text") or "{}")
        except json.JSONDecodeError:
            continue
        payload = body.get("requested_action") or {}
        parameters = payload.get("parameters") or {}
        if "baseline_action" not in parameters:
            continue  # an actuation artifact from a different producer, not a shadow decision
        rows.append({
            "action": payload.get("action"),
            "baseline_action": parameters.get("baseline_action"),
            "model": parameters.get("model"),
            "baseline_model": parameters.get("baseline_model"),
        })
    return rows


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
