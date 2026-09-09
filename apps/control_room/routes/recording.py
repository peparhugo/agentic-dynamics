"""Recording-sweep routes — the decision-record coverage rail's portal surface.

* ``GET /api/recording-audit`` — the current gap report (read-only: runs the engine's
  ``--report`` scan and returns its JSON + freshness).
* ``POST /api/recording-sweep/run`` — run the sweep now (scan + backfill + report) in the
  background; the response names the log path. Human-operator route, like the steer/
  interrupt family: no agent-callable tool wraps it (``control_room.ts`` is GET-only).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from flask import Response, jsonify

ROOT = Path(__file__).resolve().parent.parent.parent.parent
ENGINE = ROOT / "scripts" / "recording_sweep.py"
SWEEP_LOG = Path("/tmp/recording_sweep_portal.log")


def _engine_report() -> dict:
    """Run the engine's scan (read-only); never 500 the portal on an engine error."""
    report: dict = {}
    try:
        proc = subprocess.run(
            ["python3", str(ENGINE), "--report"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        if proc.returncode in (0, 1):
            # exit 1 = gaps found (the engine's loud-scan contract) — the report is valid
            report = json.loads(proc.stdout)
        else:
            report = {"error": proc.stderr[-500:], "returncode": proc.returncode}
    except Exception as exc:  # noqa: BLE001
        report = {"error": f"{type(exc).__name__}: {exc}"}
    report["fresh"] = datetime.now(timezone.utc).isoformat()
    return report


def api_recording_audit() -> Response:
    return jsonify(_engine_report())


def api_recording_sweep_run() -> Response:
    """Spawn the sweep (backfill mode: scan + record + report) detached."""
    try:
        with open(SWEEP_LOG, "a") as log:
            subprocess.Popen(
                ["python3", str(ENGINE), "--backfill"],
                stdout=log, stderr=log, cwd=str(ROOT),
                start_new_session=True,
            )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"started": False, "error": f"{type(exc).__name__}: {exc}"}), 500
    return jsonify({"started": True, "log": str(SWEEP_LOG)})


def register(app, services) -> None:
    app.get("/api/recording-audit")(api_recording_audit)
    app.post("/api/recording-sweep/run")(api_recording_sweep_run)
