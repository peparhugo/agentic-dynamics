"""Tests for the spec-status regeneration narrator (kb_finding_layer k5).

``spec_status.refresh_spec_status`` regenerates ``experiments/specs/index.json`` +
``STATUS.md`` from the corpus + run ledgers. A regeneration that SHIFTS derived statuses is an
event a later reader should retrieve, so the regenerator emits ONE finding record narrating the
shift — derived from the actual per-spec diffs (direction counts), never a hand-written summary.

These tests pin the k5 VERIFY contract in both directions:

* (a) a synthetic regeneration that shifts statuses emits a change record whose text names the
  shift direction + count (assert the derived text);
* (b) a regeneration with NO shifts emits nothing;
* (c) the record is rerun-safe — the same regeneration (timestamp + shift signature) derives the
  same ``knowledge_id`` and a re-emit is a no-op;
* (d) a producer failure does not fail the regeneration.

The pure derivation (``diff_statuses`` / ``narrate_regeneration`` / ``shift_signature``) is
tested directly. The regenerator wiring is tested by running ``refresh_spec_status`` twice on a
synthetic repo whose statuses shift between the passes, with the knowledge-plane emit stubbed to
a recorder (so the assertions never touch a live stream), plus a real artifact/registry write
into a ``tmp_path`` root for the rerun-safe no-op.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_dynamics.experiment.spec_status import (
    SpecStatusEntry,
    StatusShift,
    diff_statuses,
    narrate_regeneration,
    refresh_spec_status,
    shift_signature,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Synthetic corpus helpers (a workflow whose status shifts) ───


def _workflow_spec_yaml(name: str, *, phases: list[str]) -> str:
    """A non-repeatable workflow spec whose status derives from run ledgers."""
    lines = [
        f"name: {name}",
        "question: does the workflow run?",
        'version: "0.1"',
        "artifact_kind: workflow",
        "repeatable: false",
        "workflow:",
        "  kind: agent_task",
        "  params:",
        "    language: python",
        "    phases:",
    ]
    for ph in phases:
        lines.append(f"      - name: {ph}")
        lines.append("        kind: agent")
        lines.append(f"        prompt: do {ph}")
    lines.append("factors:")
    lines.append('  - {name: model, levels: [deepseek/deepseek-v4-pro]}')
    lines.append("design: factorial")
    return "\n".join(lines) + "\n"


def _write_ledger(root: Path, spec: str, stem: str, *, ok: bool, phases: list[str]) -> Path:
    run_dir = root / "experiments" / "results" / "workflows" / spec
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{stem}.json"
    payload = {
        "spec_name": spec,
        "ok": ok,
        "model": "deepseek/deepseek-v4-pro",
        "started_at": "2026-09-03T09:00:00+00:00",
        "ended_at": "2026-09-03T10:00:00+00:00",
        "phases": [{"phase": p, "status": "ok" if ok else "failed"} for p in phases],
    }
    path.write_text(json.dumps(payload))
    return path


def _build_corpus(tmp_path: Path, name: str = "ship") -> Path:
    """A synthetic repo whose workflow spec starts runnable (no ledgers)."""
    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    (specs / f"{name}.yaml").write_text(_workflow_spec_yaml(name, phases=["p1", "p2"]))
    return tmp_path


# ── Pure derivation ──────────────────────────────────────────────


def test_narrate_names_shift_direction_and_count():
    """(a) the derived text names the shift direction + count for each direction group."""
    shifts = [
        StatusShift(name="alpha", from_status="failed", to_status="completed"),
        StatusShift(name="beta", from_status="failed", to_status="completed"),
        StatusShift(name="gamma", from_status="completed", to_status="blocked"),
    ]
    text = narrate_regeneration(shifts, generated_at="2026-09-03T00:00:00+00:00")
    # direction + count per group, in descending-count order
    assert text.startswith("spec-index regeneration 2026-09-03T00:00:00+00:00: 3 specs changed (")
    assert "2 failed→completed" in text
    assert "1 completed→blocked" in text


def test_narrate_empty_when_nothing_shifted():
    """(b) no shifts → the narrator has nothing to say."""
    assert narrate_regeneration([], generated_at="2026-09-03T00:00:00+00:00") == ""


def test_diff_statuses_matches_by_name_only_when_status_changes():
    """A spec counts only when it exists in BOTH generations with a different status."""
    previous = [
        {"name": "a", "status": "failed"},
        {"name": "b", "status": "completed"},
        {"name": "gone", "status": "failed"},  # removed: no current status to shift to
    ]

    def entry(name: str, status: str) -> SpecStatusEntry:
        return SpecStatusEntry(name=name, version="0.1", status=status, spec_path="x.yaml")

    current = [
        entry("a", "completed"),  # failed→completed
        entry("b", "completed"),  # unchanged
        entry("fresh", "runnable"),  # new: no previous status to shift from
    ]
    shifts = diff_statuses(previous, current)
    assert shifts == [StatusShift(name="a", from_status="failed", to_status="completed")]


def test_shift_signature_is_deterministic_and_order_sensitive():
    s1 = [StatusShift("a", "failed", "completed"), StatusShift("b", "completed", "blocked")]
    s2 = [StatusShift("b", "completed", "blocked"), StatusShift("a", "failed", "completed")]
    s3 = [StatusShift("a", "failed", "completed"), StatusShift("b", "completed", "runnable")]
    assert shift_signature(s1) == shift_signature(s2)  # sorted — same set, same signature
    assert shift_signature(s1) != shift_signature(s3)  # a different shift → different signature


# ── Regenerator wiring ───────────────────────────────────────────


def _recorder():
    """A mutable capture for the knowledge-plane emit call."""

    def record(shifts, *, text, generated_at, root):
        record.calls.append((list(shifts), text, generated_at, Path(root)))

    record.calls = []
    return record


@pytest.fixture
def armed(monkeypatch):
    """Arm the narrator (conftest disarms FINOPS_EMIT_SELF=0 globally)."""
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)


def test_regeneration_that_shifts_statuses_emits_one_change_record(
    tmp_path: Path, monkeypatch, armed
):
    """(a) end-to-end through the regenerator: two passes that shift a status emit once,
    with the derived text naming direction + count."""
    root = _build_corpus(tmp_path)
    # First regeneration: no previous index, nothing to shift from → nothing emitted.
    report1 = refresh_spec_status(root=root, generated_at="2026-09-03T00:00:00+00:00")
    assert report1.index_path.exists()

    rec = _recorder()
    monkeypatch.setattr(
        "agentic_dynamics.knowledge.spec_ingestion.emit_index_shift", rec
    )

    # Second regeneration: a green run now certifies `ship` → runnable → completed.
    _write_ledger(root, "ship", "20260903T100000Z", ok=True, phases=["p1", "p2"])
    report2 = refresh_spec_status(root=root, generated_at="2026-09-03T11:00:00+00:00")
    assert report2.entry_for("ship").status == "completed"
    assert len(rec.calls) == 1
    shifts, text, generated_at, _root = rec.calls[0]
    assert [(s.name, s.from_status, s.to_status) for s in shifts] == [
        ("ship", "runnable", "completed")
    ]
    assert "1 runnable→completed" in text
    assert "spec-index regeneration 2026-09-03T11:00:00+00:00" in text


def test_regeneration_with_no_shifts_emits_nothing(tmp_path: Path, monkeypatch, armed):
    """(b) identical regenerations → the seam is never invoked."""
    root = _build_corpus(tmp_path)
    refresh_spec_status(root=root, generated_at="2026-09-03T00:00:00+00:00")

    rec = _recorder()
    monkeypatch.setattr(
        "agentic_dynamics.knowledge.spec_ingestion.emit_index_shift", rec
    )

    # Same corpus, same derived statuses → no shift, no call.
    refresh_spec_status(root=root, generated_at="2026-09-03T01:00:00+00:00")
    assert rec.calls == []


def test_producer_failure_does_not_fail_the_regeneration(
    tmp_path: Path, monkeypatch, armed
):
    """(d) an emit exception degrades to a warning; the index is still written."""
    root = _build_corpus(tmp_path)
    refresh_spec_status(root=root, generated_at="2026-09-03T00:00:00+00:00")

    def boom(shifts, *, text, generated_at, root):
        raise RuntimeError("stream down")

    monkeypatch.setattr(
        "agentic_dynamics.knowledge.spec_ingestion.emit_index_shift", boom
    )

    _write_ledger(root, "ship", "20260903T100000Z", ok=True, phases=["p1", "p2"])
    with pytest.warns(UserWarning, match="narrator emit failed"):
        report = refresh_spec_status(root=root, generated_at="2026-09-03T11:00:00+00:00")
    # The regeneration completed: status derived + the index written.
    assert report.entry_for("ship").status == "completed"
    assert report.index_path.exists()


# ── Knowledge-plane record + rerun-safety ────────────────────────


def test_derive_record_is_rerun_safe(tmp_path: Path, monkeypatch):
    """(c) the same regeneration (timestamp + shift signature) derives the SAME
    knowledge_id, and a re-emit against the same root is a no-op.

    The pointer-event publish is best-effort by design; the test stubs the stream connect to
    raise so the emit is exercised without touching a live Redis (the durable artifact +
    registry row are the record, exactly as with a downed stream)."""
    from agentic_dynamics.knowledge import knowledge_stream as ks
    from agentic_dynamics.knowledge import spec_ingestion as si

    monkeypatch.setattr(
        ks, "connect", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("no redis"))
    )

    shifts = [
        StatusShift(name="a", from_status="failed", to_status="completed"),
        StatusShift(name="b", from_status="completed", to_status="blocked"),
    ]
    text = narrate_regeneration(shifts, generated_at="2026-09-03T00:00:00+00:00")
    r1 = si.derive_index_shift_record(shifts, text=text, generated_at="2026-09-03T00:00:00+00:00")
    r2 = si.derive_index_shift_record(shifts, text=text, generated_at="2026-09-03T00:00:00+00:00")
    assert r1.knowledge_id == r2.knowledge_id
    # A different regeneration timestamp → a different record (a distinct event).
    r3 = si.derive_index_shift_record(shifts, text=text, generated_at="2026-09-03T01:00:00+00:00")
    assert r1.knowledge_id != r3.knowledge_id

    # Emit into a tmp root; the second emit is a no-op (one artifact, one registry row).
    root = tmp_path / "repo"
    root.mkdir()
    kid1 = si.emit_index_shift(shifts, text=text, generated_at="2026-09-03T00:00:00+00:00", root=root)
    kid2 = si.emit_index_shift(shifts, text=text, generated_at="2026-09-03T00:00:00+00:00", root=root)
    assert kid1 == kid2 == r1.knowledge_id
    artifact = root / "experiments" / "results" / "kb" / f"{kid1}.json"
    assert artifact.exists()
    rows = [
        json.loads(line)
        for line in (root / "experiments" / "results" / "registry_index.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    ]
    assert len(rows) == 1 and rows[0]["knowledge_id"] == kid1
    # The durable artifact's text names the shift direction + count.
    payload = json.loads(artifact.read_text())
    assert "2 failed→completed" in payload["text"] or "failed→completed" in payload["text"]


def test_regeneration_narrator_is_disarmed_by_default(monkeypatch):
    """The unit suite disarms finding emission (FINOPS_EMIT_SELF=0) so synthetic refreshes
    never touch a live KB."""
    from agentic_dynamics.experiment.spec_status import _narrator_disarmed

    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    assert _narrator_disarmed() is True
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)
    assert _narrator_disarmed() is False
