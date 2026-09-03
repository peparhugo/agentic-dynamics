"""Tests for the durable-evidence smoke harness (fleet_launch_container_smoke cs2_durable_evidence).

The f3 close-out (fleet_launch_smoke adversarial F3): the predecessor smoke's mount proof was a
``--rm`` observation — the RW=false inspect was transcribed from a container that was gone at
exit, so the evidence was a memory. This suite proves the successor harness's load-bearing
ordering contract — every smoke artifact (container id, docker-inspect mount proof, exit code,
verdict) is persisted to a DURABLE file BEFORE the container is removed:

    (a) the smoke harness writes the evidence file with the container id + mount proof before
        cleanup — the cleanup sees the durable file already on disk;
    (b) the evidence file round-trips — loadable JSON with the expected artifact keys;
    (c) the harness removes the container only after persisting — cleanup runs strictly after
        the final evidence write, and a write failure skips cleanup entirely (fail-closed).

Pure unit tests: no docker, no live launch — ``launch`` / ``capture`` / ``cleanup`` are
deterministic fakes synchronized with threading events (the launch runs in a background thread
exactly as :func:`smoke_harness.run_smoke` drives a real one, so the ordering under test is the
real ordering, not a synchronous simulation).
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FLEET_DIR = str(_REPO_ROOT / "scripts" / "fleet")
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

from scripts.fleet import smoke_harness  # noqa: E402

pytestmark = pytest.mark.fast

CLONE_SOURCE = "/runs/run-smoke-1/repo"
CONTAINER_ID = "abc123def456container"
FULL_MOUNT_PROOF = [{"source": CLONE_SOURCE, "target": "/repo", "rw": False}]


def _capture_payload() -> dict:
    """A canonical capture payload: the live cell container with the clone mounted read-only."""
    return {"container_id": CONTAINER_ID, "image": "fleet/base", "mount_proof": FULL_MOUNT_PROOF}


def _full_evidence(spec: str = "smoke_spec") -> dict:
    """A complete, fully-keyed evidence record (as a real post-launch file would carry)."""
    return {
        "schema": smoke_harness.SMOKE_EVIDENCE_SCHEMA,
        "spec": spec,
        "run_id": "run-1",
        "phase": "cs3_container_smoke",
        "started_at": "2026-09-03T14:00:00.000000+00:00",
        "ended_at": "2026-09-03T14:00:05.000000+00:00",
        "captured": True,
        "container_id": CONTAINER_ID,
        "image": "fleet/base",
        "mount_proof": FULL_MOUNT_PROOF,
        "exit_code": 0,
        "verdict": {
            "ok": True,
            "state": "ok",
            "test_executed_success": True,
            "tests_passed": 1,
            "tests_total": 1,
            "error": None,
        },
        "cleanup": {"performed": True, "method": "harness-cleanup", "at": "2026-09-03T14:00:05Z"},
        "persisted_at": "2026-09-03T14:00:05Z",
        "launch_context": {"view": "host", "mount_profile": "verifier_readonly"},
    }


def _fake_launch(started: threading.Event, release: threading.Event, outcome: dict):
    """A launch fake: signal it started, block until released, then return the outcome.

    The blocking models a real broker-seam round-trip (the launch is in flight while the harness
    observes the container); the release event lets the test end the launch deterministically.
    """

    def _launch():
        started.set()
        release.wait(timeout=30)
        return dict(outcome)

    return _launch


def _fake_capture(started: threading.Event, release: threading.Event):
    """A capture fake: wait for the launch to be in flight, then report the live container.

    Setting ``release`` here models the real world where the container's run finishes on its
    own once observed — the harness persists the snapshot (while the launch is still running,
    before removal) and then the launch completes.
    """

    def _capture():
        started.wait(timeout=30)
        release.set()
        return _capture_payload()

    return _capture


# ── (a) the evidence file is written (id + mount proof) BEFORE cleanup ──────


def test_harness_persists_container_id_and_mount_proof_before_cleanup(tmp_path):
    """The cleanup sees the durable file on disk, carrying the container id + the clone's RW=false proof.

    A real cleanup that removed the container first could never inspect it afterwards; this
    proves the harness persisted the id + mount proof BEFORE cleanup is allowed to run.
    """
    started, release = threading.Event(), threading.Event()
    calls: list[str] = []

    def cleanup(evidence_path: Path):
        calls.append("cleanup")
        assert evidence_path.exists(), "cleanup ran before the evidence file was persisted"
        on_disk = smoke_harness.load_evidence(evidence_path)
        assert on_disk["container_id"] == CONTAINER_ID
        clone_mount = [m for m in on_disk["mount_proof"] if m["target"] == "/repo"]
        assert clone_mount and clone_mount[0] == {
            "source": CLONE_SOURCE,
            "target": "/repo",
            "rw": False,
        }
        assert on_disk["exit_code"] == 0
        assert on_disk["verdict"]["state"] == "ok"

    result = smoke_harness.run_smoke(
        "smoke_spec",
        launch=_fake_launch(
            started,
            release,
            {
                "returncode": 0,
                "state": "ok",
                "test_executed_success": True,
                "tests_passed": 1,
                "tests_total": 1,
            },
        ),
        capture=_fake_capture(started, release),
        cleanup=cleanup,
        run_id="run-1",
        phase="cs3_container_smoke",
        launch_context={"view": "host"},
        results_root=tmp_path,
    )

    assert calls == ["cleanup"]
    assert result.captured is True
    # The ordering the f3 close-out demands: the snapshot (with the id + mount proof) was
    # persisted while the launch was still in flight — structurally before the container could
    # be removed — and only afterwards did the launch complete.
    assert result.events.index("snapshot_persisted") < result.events.index("launch_completed")
    assert result.events.index("snapshot_persisted") < result.events.index("cleanup_start")
    assert result.evidence_path.exists()


# ── (b) the evidence file round-trips with the expected keys ────────────────


def test_evidence_file_round_trips_with_expected_artifact_keys(tmp_path):
    """A persisted evidence file is loadable JSON carrying every expected artifact key.

    Round-trip both directions: write a full record → load it back → every
    ``SMOKE_ARTIFACT_KEYS`` key is present with the written value, and the file is plain JSON
    a reader can re-derive from without the harness.
    """
    path = smoke_harness.evidence_path_for(tmp_path, "smoke_spec")
    written = smoke_harness.write_evidence(_full_evidence(), path)

    assert written == path and path.exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert set(smoke_harness.SMOKE_ARTIFACT_KEYS) <= set(raw)

    loaded = smoke_harness.load_evidence(path)
    for key in smoke_harness.SMOKE_ARTIFACT_KEYS:
        assert loaded[key] == _full_evidence()[key]
    assert loaded["schema"] == smoke_harness.SMOKE_EVIDENCE_SCHEMA
    assert loaded["mount_proof"][0]["rw"] is False
    assert loaded["container_id"] == CONTAINER_ID


def test_round_trip_refuses_a_record_missing_an_artifact_key(tmp_path):
    """The round-trip contract holds both ways: a key-less record is refused at write AND at load.

    A reader must never guess whether a missing key means absent or forgotten — so the harness
    refuses to persist a record without the full key set, and a foreign/truncated file refuses
    to load.
    """
    ev = _full_evidence()
    del ev["exit_code"]
    with pytest.raises(ValueError, match="missing artifact key"):
        smoke_harness.write_evidence(ev, smoke_harness.evidence_path_for(tmp_path, "smoke_spec"))

    path = smoke_harness.evidence_path_for(tmp_path, "smoke_spec")
    smoke_harness.write_evidence(_full_evidence(), path)
    foreign = json.loads(path.read_text(encoding="utf-8"))
    foreign.pop("verdict")
    path.write_text(json.dumps(foreign), encoding="utf-8")
    with pytest.raises(ValueError, match="missing artifact key"):
        smoke_harness.load_evidence(path)


def test_round_trip_refuses_a_foreign_schema(tmp_path):
    """A file carrying a different schema id is not this contract's artifact, whatever its name."""
    path = smoke_harness.evidence_path_for(tmp_path, "smoke_spec")
    smoke_harness.write_evidence(_full_evidence(), path)
    foreign = json.loads(path.read_text(encoding="utf-8"))
    foreign["schema"] = "something-else/v9"
    path.write_text(json.dumps(foreign), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        smoke_harness.load_evidence(path)


# ── (c) the harness removes the container only AFTER persisting ─────────────


def test_harness_removes_the_container_only_after_persisting(tmp_path):
    """Cleanup (the removal) is ordered strictly after the durable final write.

    The event stream is the proof: the final evidence write precedes the cleanup, and the
    cleanup record itself is persisted too — so the removal is always after the artifact, never
    before it.
    """
    started, release = threading.Event(), threading.Event()
    result = smoke_harness.run_smoke(
        "smoke_spec",
        launch=_fake_launch(started, release, {"returncode": 0, "ok": True}),
        capture=_fake_capture(started, release),
        cleanup=lambda path: None,
        results_root=tmp_path,
    )

    assert result.events.index("final_persisted") < result.events.index("cleanup_start")
    assert result.events.index("cleanup_start") < result.events.index("cleanup_complete")
    assert result.evidence["cleanup"]["performed"] is True


def test_harness_skips_removal_when_the_evidence_cannot_be_persisted(tmp_path, monkeypatch):
    """Fail-closed: a container whose evidence could not be written is NEVER removed.

    If the durable write fails, the harness must raise (loud — never a silent pass) and must
    not invoke the removal at all — removing the container would destroy the only source of the
    very evidence the smoke exists to keep.
    """
    started, release = threading.Event(), threading.Event()
    cleanup_calls: list[str] = []

    def _boom(*_args, **_kwargs):
        raise OSError("disk full — the evidence could not be persisted")

    monkeypatch.setattr(smoke_harness, "write_evidence", _boom)

    with pytest.raises(OSError, match="disk full"):
        smoke_harness.run_smoke(
            "smoke_spec",
            launch=_fake_launch(started, release, {"returncode": 0, "ok": True}),
            capture=_fake_capture(started, release),
            cleanup=lambda path: cleanup_calls.append("cleanup"),
            results_root=tmp_path,
        )
    assert cleanup_calls == [], "the harness removed a container whose evidence was never durable"


def test_cleanup_failure_raises_but_the_evidence_file_survives(tmp_path):
    """A removal that fails is loud, and the durable artifact is already on disk regardless.

    The evidence (id + mount proof + exit code + verdict) is fully persisted before cleanup is
    invoked, so even a failed removal leaves the smoke's claim re-derivable from the file.
    """
    started, release = threading.Event(), threading.Event()

    def failing_cleanup(path: Path):
        raise RuntimeError("docker rm failed")

    with pytest.raises(RuntimeError, match="docker rm failed"):
        smoke_harness.run_smoke(
            "smoke_spec",
            launch=_fake_launch(started, release, {"returncode": 0, "state": "ok"}),
            capture=_fake_capture(started, release),
            cleanup=failing_cleanup,
            results_root=tmp_path,
        )

    artifacts = list(tmp_path.rglob("*.json"))
    assert artifacts, "no durable evidence file after a cleanup failure"
    on_disk = smoke_harness.load_evidence(artifacts[0])
    assert on_disk["container_id"] == CONTAINER_ID
    assert on_disk["exit_code"] == 0
    assert on_disk["verdict"]["state"] == "ok"


# ── Honest capture (never a fabricated inspect) ─────────────────────────────


def test_a_missed_capture_window_is_recorded_honestly_not_fabricated(tmp_path):
    """A launch whose container was never observed records captured=false with NO invented id.

    The durable file stays honest: the outcome (exit code + verdict) is real, the container
    evidence is explicitly absent — the smoke driver's verdict logic must treat a missed proof
    as a failure, never as evidence by absence.
    """
    started, release = threading.Event(), threading.Event()
    release.set()  # the launch completes immediately, before any observation can succeed

    result = smoke_harness.run_smoke(
        "smoke_spec",
        launch=_fake_launch(started, release, {"returncode": 0, "state": "ok"}),
        capture=lambda: None,  # never sees the container
        results_root=tmp_path,
    )

    assert result.captured is False
    assert result.evidence["container_id"] is None
    assert result.evidence["mount_proof"] == []
    assert result.evidence["exit_code"] == 0
    on_disk = smoke_harness.load_evidence(result.evidence_path)
    assert on_disk["captured"] is False and on_disk["container_id"] is None


# ── Mount-proof normalization (the docker-inspect vocabulary) ───────────────


def test_mounts_from_inspect_marks_the_clone_read_only():
    """The inspect → evidence normalization keeps the clone's RW=false (the f3 load-bearing claim).

    A synthetic ``docker inspect`` document (the shape the real broker-launched cell carries)
    normalizes onto the mount-proof vocabulary: the clone at ``/repo`` is RW=false, a writable
    results overlay stays RW=true — the reader asserts exactly this pair.
    """
    doc = {
        "Id": CONTAINER_ID,
        "Config": {"Image": "fleet/base"},
        "Mounts": [
            {
                "Type": "bind",
                "Source": CLONE_SOURCE,
                "Destination": "/repo",
                "Mode": "",
                "RW": False,
                "Propagation": "rprivate",
            },
            {
                "Type": "bind",
                "Source": "/host/results",
                "Destination": "/app/experiments/results",
                "Mode": "",
                "RW": True,
                "Propagation": "rprivate",
            },
        ],
    }
    proof = smoke_harness.mounts_from_inspect(doc)
    by_target = {m["target"]: m for m in proof}
    assert by_target["/repo"] == {"source": CLONE_SOURCE, "target": "/repo", "rw": False}
    assert by_target["/app/experiments/results"]["rw"] is True
    assert set(by_target) == {"/repo", "/app/experiments/results"}


def test_mounts_from_inspect_refuses_a_document_without_mounts():
    """An inspect document with no Mounts list cannot be a mount proof — refused, never empty."""
    with pytest.raises(ValueError, match="no Mounts list"):
        smoke_harness.mounts_from_inspect({"Id": CONTAINER_ID, "Config": {}})


# ── The durable-evidence path shape (spec's cs2 example) ────────────────────


def test_evidence_path_is_results_smoke_spec_timestamp_json(tmp_path):
    """The evidence lands at ``<results>/smoke/<spec>/<timestamp>.json`` (the spec's example)."""
    path = smoke_harness.evidence_path_for(tmp_path, "fleet_launch_container_smoke")
    assert path.parent == tmp_path / "smoke" / "fleet_launch_container_smoke"
    assert path.name.endswith(".json")
    assert path.name[:-5].endswith("Z")  # the run-ledger %Y%m%dT%H%M%SZ convention


def test_evidence_dirname_cannot_escape_the_smoke_root(tmp_path):
    """A hostile spec name cannot walk the tree — evidence stays under ``smoke/<spec>``."""
    assert smoke_harness.evidence_dir(tmp_path, "../../etc") == tmp_path / "smoke" / "etc"
    assert smoke_harness.evidence_dir(tmp_path, "") == tmp_path / "smoke" / "unnamed"
