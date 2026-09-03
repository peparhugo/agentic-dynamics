#!/usr/bin/env python3
"""cs3_container_smoke — THE SMOKE OF THE REAL SHAPE (fleet_launch_container_smoke).

Drives ONE cell through the CONTAINER-TIER orchestrator on this host and persists the durable
smoke evidence via ``smoke_harness.run_smoke`` (cs2_durable_evidence):

* launch  = ``docker compose run --rm workflow-runner python3 scripts/run_workflow.py
  --orchestrator --spec <cs3_smoke_cell> ...`` — the compose workflow-runner service (image
  fleet/orchestrator) whose container env carries ``FINOPS_REPO_DIR``/``FINOPS_GIT_DIR`` (cs1)
  and ``FINOPS_RUNS_ROOT`` (this phase's env addition). The orchestrator (as a container) mints
  the control run, creates the run clone, and spawns the ONE verifier cell for the smoke cell's
  ``kind: test`` phase over the host broker's seam.
* capture = poll ``docker ps`` for the LIVE fleet/base verifier cell (the broker's ``docker run
  --rm`` child) whose mounts include the run clone at ``/repo`` READ-ONLY, then inspect it.
* cleanup = gone-verification only (the broker's cell is ``--rm``; there is nothing to remove).

Evidence is written to ``<results>/smoke/fleet_launch_container_smoke/<timestamp>.json``
(schema ``fleet-smoke-evidence/v1``) BEFORE the cell is removed — the durable artifact cs4 and
the harness gate re-derive from.

Run:  python3 experiments/results/smoke/fleet_launch_container_smoke/cs3_driver.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "fleet"))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from smoke_harness import (  # noqa: E402
    capture_from_container_id,
    docker_inspect,
    run_smoke,
)

SPEC = "fleet_launch_container_smoke"
PHASE = "cs3_container_smoke"
CELL_SPEC = "experiments/results/smoke/fleet_launch_container_smoke/cs3_smoke_cell.yaml"
GOAL = "cs3 container-tier smoke: one verifier cell end-to-end through the container orchestrator"
MODEL = os.environ.get("FINOPS_SMOKE_MODEL", "deepseek/deepseek-v4-flash")
COMPOSE = _REPO_ROOT / "infrastructure" / "docker-compose.ladder.yml"
RUNS_ROOT = os.environ.get("FINOPS_RUNS_ROOT", "/tmp/agentic-dynamics-runs")

# Required compose host-side interpolations.
for var in ("AUTH_HOME", "FINOPS_REPO_DIR", "FINOPS_LAUNCH_BROKER_SOCKET"):
    if not os.environ.get(var):
        raise SystemExit(f"{var} must be exported to interpolate the ladder compose mounts")


def _docker_ps_running() -> list[dict]:
    """List running containers (read-only observation, the game-board posture)."""
    out = subprocess.run(
        ["docker", "ps", "--no-trunc", "--format", "{{json .}}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def _find_live_verifier_cell() -> dict | None:
    """The broker's LIVE fleet/base verifier cell: image fleet/base AND a mount whose source is
    a runs-root clone mounted READ-ONLY at /repo (the cell under smoke). Returns the canonical
    capture payload (container_id + mount_proof) or None while none is running."""
    for ps in _docker_ps_running():
        image = ps.get("Image") or ""
        if "fleet/base" not in image:
            continue
        cid = ps.get("ID")
        if not cid:
            continue
        try:
            doc = docker_inspect(cid)
        except Exception:
            continue
        mounts = doc.get("Mounts") or []
        for m in mounts:
            if m.get("Destination") == "/repo" and m.get("RW") is False:
                src = str(m.get("Source") or "")
                if RUNS_ROOT in src and src.rstrip("/").endswith("/repo"):
                    return capture_from_container_id(cid, raw_inspect=doc)
    return None


def launch() -> dict:
    """The blocking container-tier orchestrator drive (docker compose run workflow-runner)."""
    argv = [
        "docker-compose", "-f", str(COMPOSE), "run", "--rm",
        "workflow-runner",
        "python3", "scripts/run_workflow.py",
        "--spec", CELL_SPEC,
        "--goal", GOAL,
        "--model", MODEL,
        "--workdir", "/repo",
        "--orchestrator",
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    stdout = proc.stdout or ""
    # The child run_workflow.py prints its WorkflowRunResult as a multi-line JSON doc at the end
    # of stdout. docker-compose may prefix its own banner; extract the LAST top-level JSON object
    # (brace-depth scan) and read the single phase record off it.
    verdict = None
    exit_code = proc.returncode
    ok = proc.returncode == 0
    envelope = _last_json_object(stdout)
    if isinstance(envelope, dict) and envelope.get("phases"):
        phases = envelope.get("phases") or []
        if phases:
            ph = phases[0]
            verdict = {
                "ok": bool(envelope.get("ok")),
                "state": envelope.get("state"),
                "test_executed_success": ph.get("test_executed_success"),
                "tests_passed": ph.get("tests_passed"),
                "tests_total": ph.get("tests_total"),
                "error": ph.get("error") or None,
            }
            ok = bool(envelope.get("ok"))
    elif verdict is None and exit_code != 0:
        verdict = {"ok": False, "error": (stdout + (proc.stderr or ""))[-1000:] or None}
    return {"ok": ok, "exit_code": exit_code, "returncode": proc.returncode,
            "verdict": verdict, "tail": stdout[-2000:]}


def _last_json_object(text: str) -> dict | None:
    """The last top-level JSON object in ``text`` (brace-depth scan, compose banners ignored)."""
    depth = 0
    start = -1
    in_str = False
    esc = False
    last: dict | None = None
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(text[start : i + 1])
                    if isinstance(obj, dict):
                        last = obj
                except json.JSONDecodeError:
                    pass
                start = -1
    return last


def cleanup_gone(evidence_path: Path) -> None:
    """The broker's cell is ``--rm`` — nothing to remove; verify the recorded id is gone."""
    try:
        rec = json.loads(Path(evidence_path).read_text())
    except Exception:
        return
    cid = rec.get("container_id")
    if not cid:
        return
    # read-only check: the container should already be gone (the broker --rm'd it)
    subprocess.run(["docker", "inspect", str(cid)], capture_output=True, text=True)


def main() -> int:
    launch_context = {
        "shape": "container-tier orchestrator (compose workflow-runner service, cs1 env)",
        "spec": CELL_SPEC,
        "compose": str(COMPOSE),
        "cell_spec": CELL_SPEC,
        "runs_root": RUNS_ROOT,
    }
    result = run_smoke(
        SPEC,
        launch=launch,
        capture=_find_live_verifier_cell,
        cleanup=cleanup_gone,
        run_id=os.environ.get("FINOPS_SMOKE_RUN_ID", ""),
        phase=PHASE,
        launch_context=launch_context,
        poll_interval=0.2,
    )
    print(json.dumps({
        "evidence_path": str(result.evidence_path),
        "captured": result.captured,
        "exit_code": result.evidence.get("exit_code"),
        "verdict": result.evidence.get("verdict"),
        "mount_proof": result.evidence.get("mount_proof"),
        "container_id": result.evidence.get("container_id"),
        "events": result.events,
        "error": result.error,
    }, indent=2))
    ok = bool(result.captured and result.evidence.get("exit_code") == 0
              and (result.evidence.get("verdict") or {}).get("test_executed_success"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
