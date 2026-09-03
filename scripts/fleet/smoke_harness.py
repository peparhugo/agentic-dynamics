#!/usr/bin/env python3
"""smoke_harness — the DURABLE-evidence smoke harness (fleet_launch_container_smoke cs2_durable_evidence).

The container-smoke wave's f3 close-out. The predecessor smoke wave's mount proof was a ``--rm``
observation (the fleet_launch_smoke adversarial F3): the RW=false docker-inspect record was
transcribed into a review doc from a container that ``docker run --rm`` deleted at exit, so the
evidence was a memory — re-derivable from nothing but the doc. This module is the successor of
that ad-hoc smoke launch: the harness a smoke (cs3_container_smoke or any future smoke) drives a
cell through, and it makes EVERY smoke artifact — container id, the docker-inspect mount proof
(RW=false for the clone), the exit code, the verdict — DURABLE, persisted to
``experiments/results/smoke/<spec>/<timestamp>.json`` **before** the container is removed.

The load-bearing guarantees (each proven by ``tests/test_smoke_harness.py``):

1. **The durable file is the artifact, never the container.** The blocking launch runs in a
   background thread while this harness polls a caller-supplied ``capture`` callback for the
   LIVE cell container (the read-only observation seam — ``docker inspect`` at most, never a
   launch). The instant ``capture`` returns the container id + mount proof, the harness writes
   the evidence SNAPSHOT to its durable path — while the container is still running,
   structurally before the broker's ``docker run --rm`` can remove it. The file is then
   atomically replaced as the launch completes (exit code + verdict) and again as cleanup runs.
   If the harness process is killed at any point, the durable file already holds everything
   captured up to that instant — a re-derivable artifact, never a recorded observation.

2. **Removal is gated on persistence.** The ``cleanup`` callback (the removal: ``docker rm``
   for a harness-owned container, a gone-verification for a broker ``--rm`` cell) is invoked
   ONLY after the evidence file has been durably written; a write failure skips cleanup
   entirely (fail-closed — a container whose evidence could not be recorded is never removed
   silently).

3. **Honest capture.** If the live container was never observed (the capture window was
   missed), the evidence records ``captured: false`` with a null container id and an empty
   mount proof — the artifact stays honest, never a fabricated inspect.

Docker posture: this module's only docker-touching helper (:func:`docker_inspect`) is a
READ-ONLY observation — the same documented read-only posture as the game board's ``docker ps``
(``scripts/system_snapshot.py``, fb3 f4). The launch broker remains the ONLY docker caller that
LAUNCHES; this harness never builds a ``docker run`` / ``docker compose`` argv (guarded by the
``tests/test_launch_broker.py`` docker-call-site scan).

The evidence schema is :data:`SMOKE_EVIDENCE_SCHEMA`; the artifact key set
(:data:`SMOKE_ARTIFACT_KEYS`) is the round-trip contract a reader asserts after load.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: The evidence schema id — the durable file's first key. A file carrying any other schema is
#: not this contract's artifact, whatever its extension claims.
SMOKE_EVIDENCE_SCHEMA = "fleet-smoke-evidence/v1"

#: The closed top-level key set of a durable smoke-evidence file — the round-trip contract.
#: ``container_id`` + ``mount_proof`` are the container-bound artifacts (the ones a ``--rm``
#: launch would otherwise destroy); ``exit_code`` + ``verdict`` are the launch outcome; the
#: ``cleanup`` block records what removed the container and when (after persistence, by
#: construction). Every key is present in every persisted record — null when not yet known —
#: so a reader never guesses whether a missing key means "absent" or "forgotten".
SMOKE_ARTIFACT_KEYS: tuple[str, ...] = (
    "schema",
    "spec",
    "run_id",
    "phase",
    "started_at",
    "ended_at",
    "captured",
    "container_id",
    "image",
    "mount_proof",
    "exit_code",
    "verdict",
    "cleanup",
    "persisted_at",
    "launch_context",
)

#: The keys a single normalized mount-proof entry carries (a subset of docker inspect's
#: ``Mounts`` record, renamed to the mount vocabulary this repo's contract already speaks).
MOUNT_PROOF_KEYS: tuple[str, ...] = ("source", "target", "rw")


@dataclass
class SmokeRunResult:
    """The outcome of one :func:`run_smoke` invocation — the evidence + how the run ended.

    ``evidence_path`` is the durable file that was written (the re-derivable artifact);
    ``evidence`` is its final content; ``outcome`` is the launch's returned outcome dict (exit
    code + verdict source); ``captured`` records whether the live container evidence was ever
    observed; ``error`` carries the launch thread's exception when it raised (never a silent
    pass — a launch that crashed is recorded as an error, not as a successful smoke).
    """

    evidence_path: Path
    evidence: dict[str, Any]
    outcome: Any | None
    captured: bool
    error: str | None = None
    events: list[str] = field(default_factory=list)


def utcnow_iso() -> str:
    """The current UTC instant as an ISO-8601 string (the evidence timestamps' format)."""
    return datetime.now(timezone.utc).isoformat()


def default_results_root() -> Path:
    """The durable smoke-evidence root — ``FINOPS_RESULTS_DIR`` when set, else the repo's results dir.

    The smoke evidence lives under ``<results>/smoke/<spec>/`` (spec's cs2 example:
    ``experiments/results/smoke/<spec>/<timestamp>.json``). Tests and operators pass an explicit
    ``results_root`` to :func:`run_smoke` / :func:`evidence_path_for`; this default mirrors the
    ``PathConfig`` results-dir env contract (``FINOPS_RESULTS_DIR``) so a host override applies
    everywhere the rest of the framework's durable results go.
    """
    env = os.environ.get("FINOPS_RESULTS_DIR")
    if env:
        return Path(env)
    return _REPO_ROOT / "experiments" / "results"


def _safe_spec_dirname(spec: str) -> str:
    """Map a spec name onto a single safe path segment (no ``..``, no slash, no absolute path).

    The spec name becomes ``<results>/smoke/<spec>/`` — a spec name that could walk the tree
    would be an evidence file written outside the smoke evidence root. Same rule as the fleet
    contract's namespace sanitizer: hostile separators collapse to nothing, empty collapses to
    ``unnamed``.
    """
    parts = [p for p in str(spec).replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return "/".join(parts) if parts else "unnamed"


def evidence_filename(started_at: datetime | None = None) -> str:
    """The durable evidence file name — ``<UTC %Y%m%dT%H%M%SZ>.json`` (the run-ledger convention)."""
    moment = started_at or datetime.now(timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%SZ") + ".json"


def evidence_dir(results_root: str | Path, spec: str) -> Path:
    """``<results_root>/smoke/<spec>`` — the durable smoke-evidence directory for ``spec``."""
    return Path(results_root) / "smoke" / _safe_spec_dirname(spec)


def evidence_path_for(
    results_root: str | Path,
    spec: str,
    *,
    started_at: datetime | None = None,
) -> Path:
    """The durable evidence path for one smoke run — ``<results>/smoke/<spec>/<ts>.json``."""
    return evidence_dir(results_root, spec) / evidence_filename(started_at)


def validate_evidence(obj: Any) -> list[str]:
    """Validate a smoke-evidence object against the schema contract. Empty list = valid.

    Checks the closed top-level key set (:data:`SMOKE_ARTIFACT_KEYS`) is present in full and
    the schema id matches. Values may be null (a pre-launch snapshot legitimately has no exit
    code yet) — key PRESENCE is the contract a reader relies on, never a value that might not
    exist yet. Used by :func:`write_evidence` so a bug that would persist a key-less record
    refuses loudly instead of writing a memory, and by readers (:func:`load_evidence`) so a
    foreign/truncated file is a named error, never a silent misread.
    """
    errors: list[str] = []
    if not isinstance(obj, dict):
        return [f"evidence must be a JSON object, got {type(obj).__name__!r}"]
    if obj.get("schema") != SMOKE_EVIDENCE_SCHEMA:
        errors.append(f"evidence schema {obj.get('schema')!r} != {SMOKE_EVIDENCE_SCHEMA!r}")
    missing = [k for k in SMOKE_ARTIFACT_KEYS if k not in obj]
    if missing:
        errors.append(f"evidence is missing artifact key(s) {missing}")
    return errors


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically + durably (tmp in the same dir, fsync, rename).

    The evidence must SURVIVE: a crash mid-write must never leave a truncated JSON at the
    artifact path (a truncated artifact is worse than none — it looks like evidence). The write
    goes to a temp file in the target directory, is flushed + fsync'd, and is renamed over the
    target only when fully on disk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def write_evidence(evidence: dict[str, Any], path: str | Path) -> Path:
    """Persist ``evidence`` to ``path`` durably. Returns the path.

    Refuses (raises :class:`ValueError`) a record that fails :func:`validate_evidence` — the
    artifact's key set is the round-trip contract, enforced at write time so a missing key is a
    loud bug, never a durable memory.
    """
    errors = validate_evidence(evidence)
    if errors:
        raise ValueError(
            "refusing to persist an evidence record that fails the schema contract:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
    text = json.dumps(evidence, indent=2, default=str) + "\n"
    path = Path(path)
    _atomic_write_text(path, text)
    return path


def load_evidence(path: str | Path) -> dict[str, Any]:
    """Load + validate a durable smoke-evidence file. Returns the parsed record.

    A file that is not valid JSON, or a JSON object that fails :func:`validate_evidence`, is
    raised loudly (never a silent partial read) — the round-trip direction of the same contract
    :func:`write_evidence` enforces.
    """
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_evidence(obj)
    if errors:
        raise ValueError(
            f"{path} is not a {SMOKE_EVIDENCE_SCHEMA} artifact:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
    return obj


# ── Mount-proof normalization (the docker-inspect → evidence vocabulary) ─────


def mounts_from_inspect(inspect_doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize ONE ``docker inspect`` document's ``Mounts`` onto the mount-proof vocabulary.

    Each entry becomes ``{"source", "target", "rw"}`` — ``Source`` (the host bind source,
    e.g. the run clone), ``Destination`` (the container mount target, e.g. ``/repo``) and
    ``RW`` (the read-only flag). The smoke's load-bearing claim is the CLONE mount's
    ``RW=false`` at ``/repo``; this is the exact field a reader asserts. Unknown/invalid
    entries are refused loudly (never a fabricated proof).
    """
    mounts = inspect_doc.get("Mounts")
    if not isinstance(mounts, list):
        raise ValueError(
            f"docker inspect document carries no Mounts list (got {type(mounts).__name__!r})"
        )
    proof: list[dict[str, Any]] = []
    for entry in mounts:
        if not isinstance(entry, dict):
            raise ValueError(f"mount entry {entry!r} is not a JSON object")
        source = entry.get("Source")
        target = entry.get("Destination")
        if source is None or target is None:
            raise ValueError(f"mount entry {entry!r} lacks Source/Destination — cannot prove")
        proof.append({"source": str(source), "target": str(target), "rw": bool(entry.get("RW"))})
    return proof


def docker_inspect(container_id: str, *, docker: str = "docker") -> dict[str, Any]:
    """The READ-ONLY docker observation: ``docker inspect <container_id>`` (never a launch).

    Returns the single inspect document (the container's own JSON record — mounts included).
    A missing container (``docker inspect`` exit 1 / empty) raises :class:`DockerObservationError`
    so a capture that races the broker's ``--rm`` removal is a named, recorded failure, never a
    silent empty proof. The docker binary is injectable (``FINOPS_DOCKER_BIN`` convention); the
    argv is a plain read — no ``docker run`` / ``docker compose`` construction, so the
    broker-only-caller scan (``tests/test_launch_broker.py``) stays green.
    """
    bin_path = os.environ.get("FINOPS_DOCKER_BIN", docker)
    argv = [bin_path, "inspect", str(container_id)]
    proc = subprocess.run(argv, capture_output=True, text=True)  # noqa: S603 — read-only
    if proc.returncode != 0:
        raise DockerObservationError(
            f"docker inspect {container_id} failed (exit {proc.returncode}): "
            f"{(proc.stderr or '').strip()[:300]}"
        )
    parsed = json.loads(proc.stdout or "[]")
    if not isinstance(parsed, list) or not parsed:
        raise DockerObservationError(f"docker inspect {container_id} returned no document")
    doc = parsed[0]
    if not isinstance(doc, dict):
        raise DockerObservationError(f"docker inspect {container_id} returned a non-object")
    return doc


def capture_from_container_id(
    container_id: str,
    *,
    docker: str = "docker",
    raw_inspect: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the canonical capture payload for a live/stopped container id.

    Returns ``{"container_id", "image", "mount_proof"}`` — the shape a :func:`run_smoke`
    ``capture`` callback returns. ``image`` is read from the inspect document's ``Config.Image``;
    the mount proof is the normalized ``Mounts``. When the caller already holds the inspect
    document (a capture that polled first) it may pass ``raw_inspect`` to avoid a second docker
    call; otherwise the read-only ``docker inspect`` is performed. The raw document is returned
    to the CALLER only — the harness's durable evidence persists the normalized proof, never the
    container's full config.
    """
    doc = raw_inspect if raw_inspect is not None else docker_inspect(container_id, docker=docker)
    config = doc.get("Config") or {}
    return {
        "container_id": str(container_id),
        "image": config.get("Image"),
        "mount_proof": mounts_from_inspect(doc),
    }


class DockerObservationError(RuntimeError):
    """A read-only docker observation failed (a missing container, a broken reply).

    Named (never a bare exception) so a capture path can record the failure honestly in the
    evidence and a smoke verdict can fail loudly on a missed observation.
    """


# ── The evidence lifecycle + ordering guarantee ──────────────────────────────


def _new_evidence(
    *,
    spec: str,
    run_id: str,
    phase: str,
    started_at: datetime,
    launch_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """A fresh, fully-keyed evidence record (all artifact keys present, values null/empty)."""
    return {
        "schema": SMOKE_EVIDENCE_SCHEMA,
        "spec": spec,
        "run_id": run_id,
        "phase": phase,
        "started_at": started_at.isoformat(),
        "ended_at": None,
        "captured": False,
        "container_id": None,
        "image": None,
        "mount_proof": [],
        "exit_code": None,
        "verdict": None,
        "cleanup": {"performed": False, "method": None, "at": None},
        "persisted_at": None,
        "launch_context": dict(launch_context or {}),
    }


def _apply_capture(evidence: dict[str, Any], capture_ev: dict[str, Any]) -> None:
    """Fold a successful capture payload into the evidence record.

    The evidence persists the CONTAINER-BOUND artifacts only — the container id, the image, and
    the normalized mount proof (the clone's ``RW=false``). The full ``docker inspect`` document
    is deliberately NOT persisted: it carries the container's whole config (env, mounts of
    record, labels) — none of it needed to re-derive the mount proof, and all of it surface the
    durable artifact does not need to expose.
    """
    evidence["captured"] = True
    evidence["container_id"] = capture_ev.get("container_id")
    evidence["image"] = capture_ev.get("image")
    evidence["mount_proof"] = list(capture_ev.get("mount_proof") or [])


def _outcome_artifacts(outcome: Any) -> tuple[int | None, dict[str, Any] | None]:
    """Pull the smoke's ``exit_code`` + ``verdict`` out of a launch outcome dict.

    Accepts either the broker/executor outcome shape (``returncode`` / ``state`` /
    ``test_executed_success`` / ``tests_passed`` / ``tests_total`` / ``error``) or an explicit
    ``exit_code`` / ``verdict`` pair. Absent values stay None (a launch that never produced an
    outcome is recorded as such, never as a fabricated zero).
    """
    if not isinstance(outcome, dict):
        return None, None
    exit_code = outcome.get("exit_code")
    if exit_code is None:
        rc = outcome.get("returncode")
        exit_code = int(rc) if isinstance(rc, (int, float)) and not isinstance(rc, bool) else None
    verdict = outcome.get("verdict")
    if isinstance(verdict, dict):
        return exit_code, dict(verdict)
    present = {k: outcome.get(k) for k in ("state", "test_executed_success") if k in outcome}
    if present or "ok" in outcome or exit_code is not None:
        return exit_code, {
            "ok": outcome.get("ok"),
            "state": outcome.get("state"),
            "test_executed_success": outcome.get("test_executed_success"),
            "tests_passed": outcome.get("tests_passed"),
            "tests_total": outcome.get("tests_total"),
            "error": str(outcome.get("error") or "")[:1000] or None,
        }
    return exit_code, None


def run_smoke(
    spec: str,
    *,
    launch: Callable[[], Any],
    capture: Callable[[], dict[str, Any] | None] | None = None,
    cleanup: Callable[[Path], None] | None = None,
    run_id: str = "",
    phase: str = "",
    launch_context: dict[str, Any] | None = None,
    results_root: str | Path | None = None,
    poll_interval: float = 0.25,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> SmokeRunResult:
    """Run one smoke cell and make its evidence DURABLE before the container is removed.

    ``launch`` is the BLOCKING smoke launch (e.g. a broker-seam round-trip, a ``docker compose
    run`` of the container-tier orchestrator): it runs in a background thread and returns the
    launch outcome (exit code + verdict source). While it is in flight, this harness polls
    ``capture`` — the LIVE-container observer (e.g. ``docker ps`` matching the cell, then
    :func:`capture_from_container_id`) — and the moment the capture returns the container id +
    mount proof the evidence SNAPSHOT is durably written, while the container is still running.
    Only after the launch completes is the snapshot replaced with the final record (exit code +
    verdict), and only then is ``cleanup`` — the removal — invoked. ``cleanup`` is therefore
    guaranteed to run after the evidence is on disk; a failed write skips cleanup entirely.

    ``on_event`` (optional) observes the lifecycle — ``captured`` / ``snapshot_persisted`` /
    ``launch_completed`` / ``final_persisted`` / ``cleanup_start`` / ``cleanup_complete`` /
    ``cleanup_skipped`` — with the current evidence record; a smoke driver uses it to log, a
    test uses it to prove the ordering. Returns a :class:`SmokeRunResult` with the final
    evidence + its durable path.
    """
    results_root = Path(results_root or default_results_root())
    started_at = datetime.now(timezone.utc)
    path = evidence_path_for(results_root, spec, started_at=started_at)
    events: list[str] = []
    box: dict[str, Any] = {}
    errors: list[str] = []

    def _notify(event: str, evidence: dict[str, Any]) -> None:
        events.append(event)
        if on_event is not None:
            on_event(event, dict(evidence))

    def _launch_thread() -> None:
        try:
            box["outcome"] = launch()
        except Exception as exc:  # noqa: BLE001 — a launch crash is recorded, never a silent pass
            errors.append(f"{type(exc).__name__}: {exc}")

    # 1. Launch in the background; poll for the LIVE container while it is in flight.
    evidence = _new_evidence(
        spec=spec,
        run_id=run_id,
        phase=phase,
        started_at=started_at,
        launch_context=launch_context,
    )
    thread = threading.Thread(target=_launch_thread, daemon=True)
    thread.start()
    capture_ev: dict[str, Any] | None = None
    capture_error: str | None = None
    while thread.is_alive():
        if capture is not None:
            try:
                candidate = capture()
            except Exception as exc:  # noqa: BLE001 — a failed observation is recorded honestly
                capture_error = f"{type(exc).__name__}: {exc}"
                candidate = None
            if isinstance(candidate, dict) and candidate.get("container_id"):
                capture_ev = candidate
                _apply_capture(evidence, candidate)
                _notify("captured", evidence)
                # 2. The SNAPSHOT is persisted NOW — while the container is still running and
                #    structurally before the broker's --rm (or any cleanup) can remove it.
                evidence["persisted_at"] = utcnow_iso()
                write_evidence(evidence, path)
                _notify("snapshot_persisted", evidence)
                break
        time.sleep(poll_interval)

    # 3. The launch ended (or was never observed — either way it is done now).
    thread.join()
    _notify("launch_completed", evidence)
    if capture_ev is None and capture_error is not None:
        evidence["launch_context"]["capture_error"] = capture_error

    # 4. The FINAL record — exit code + verdict, durably replacing the snapshot.
    outcome = box.get("outcome")
    exit_code, verdict = _outcome_artifacts(outcome)
    evidence["exit_code"] = exit_code
    evidence["verdict"] = verdict
    evidence["ended_at"] = utcnow_iso()
    evidence["persisted_at"] = utcnow_iso()
    write_evidence(evidence, path)
    _notify("final_persisted", evidence)

    # 5. Removal — ONLY after the evidence is durably on disk. A write failure above raised and
    #    skipped cleanup (fail-closed): a container whose evidence was never recorded is never
    #    removed silently.
    if cleanup is not None:
        evidence["cleanup"]["method"] = "harness-cleanup"
        _notify("cleanup_start", evidence)
        cleanup(path)
        evidence["cleanup"]["performed"] = True
        evidence["cleanup"]["at"] = utcnow_iso()
        evidence["persisted_at"] = utcnow_iso()
        write_evidence(evidence, path)
        _notify("cleanup_complete", evidence)
    else:
        _notify("cleanup_skipped", evidence)

    return SmokeRunResult(
        evidence_path=path,
        evidence=evidence,
        outcome=outcome,
        captured=evidence["captured"],
        error=errors[0] if errors else None,
        events=events,
    )
