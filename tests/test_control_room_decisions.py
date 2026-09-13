"""Tests for the P11 ``decision_ledger`` (projection + route) and the G-26 cap-raise writer.

Pins, in the room's honesty vocabulary:

* recorded decisions are ordered newest-first and carry the record's own attribution
  (``decided_at`` / ``actor`` / ``artifact`` / ``run_id`` / ``candidate_sha``);
* the ``category`` filter is an exact match (an unknown category is an honest empty, not an
  error);
* a P0 act (a promotion / an approval) whose decision half is absent renders in ``missing`` —
  never assumed present;
* the route is registered GET-only and passes its filter through;
* a cap change records its ``cap_raise`` decision at the moment of the act (G-26), and a no-op
  re-install records nothing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from flask import Flask  # noqa: E402

from agentic_dynamics.control.control_db import ControlDB, RunState  # noqa: E402
from agentic_dynamics.control.projections import decision_ledger as dl  # noqa: E402
from agentic_dynamics.core.admission_context import ADMISSION_REQUIRED_ENV  # noqa: E402
from agentic_dynamics.experiment.experiment_spec import load_spec  # noqa: E402
from agentic_dynamics.knowledge import decision_ingestion as di  # noqa: E402
from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact  # noqa: E402
from apps.control_room.routes import decisions as route_decisions  # noqa: E402

_NOW = "2026-09-12T12:00:00+00:00"
_SPEC = _ROOT / "workflows" / "repository" / "control_room_portal.yaml"


def _seed_decision(
    artifact_dir: Path,
    *,
    category: str,
    what: str,
    actor: str,
    decided_at: str,
    **bindings: str,
) -> str:
    """Write ONE real decision artifact through the real producer (id + bytes round trip)."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    record = di.build_decision_record(
        {
            "what": what,
            "why": "",
            "alternatives": [],
            "category": category,
            "decided_at": decided_at,
            "actor": actor,
            **bindings,
        }
    )
    (artifact_dir / f"{record.knowledge_id}.json").write_bytes(record_to_artifact(record))
    return record.knowledge_id


def _db(tmp_path) -> ControlDB:
    return ControlDB.open(tmp_path / "control.db")


def test_decisions_are_ordered_newest_first_and_carry_their_attribution(tmp_path):
    artifact_dir = tmp_path / "kb"
    _seed_decision(
        artifact_dir,
        category="one_way_door",
        what="adopt the monorepo",
        actor="peparhugo",
        decided_at="2026-09-11T10:00:00+00:00",
    )
    newest_id = _seed_decision(
        artifact_dir,
        category="cap_raise",
        what="raise the campaign cap",
        actor="operator",
        decided_at="2026-09-12T10:00:00+00:00",
        run_id="run-1",
        candidate_sha="a" * 40,
    )
    records, warnings = dl.load_decision_records(artifact_dir=artifact_dir)
    assert warnings == []
    assert len(records) == 2

    with _db(tmp_path) as db:
        epoch = db.control_epoch()
        payload = dl.build_decision_ledger(
            db, records, now=_NOW, source={"decision_artifact_dir": str(artifact_dir)}
        )

    assert payload["schema"] == "decision-ledger/v1"
    assert payload["generated_at"] == _NOW
    assert payload["control_epoch"] == epoch
    assert [row["category"] for row in payload["decisions"]] == ["cap_raise", "one_way_door"]
    newest = payload["decisions"][0]
    assert newest["knowledge_id"] == newest_id
    assert newest["decided_at"] == "2026-09-12T10:00:00+00:00"
    assert newest["actor"] == "operator"
    assert newest["run_id"] == "run-1"
    assert newest["candidate_sha"] == "a" * 40
    assert newest["artifact"].endswith(f"{newest_id}.json")
    # the unbound record stays honestly unbound (no invented run/candidate).
    assert payload["decisions"][1]["run_id"] is None
    assert payload["decisions"][1]["candidate_sha"] is None
    assert payload["missing"] == []
    assert payload["counts"] == {"decisions": 2, "missing": 0}


def test_category_filter_is_exact_and_an_unknown_category_is_an_honest_empty(tmp_path):
    artifact_dir = tmp_path / "kb"
    _seed_decision(
        artifact_dir,
        category="one_way_door",
        what="adopt the monorepo",
        actor="peparhugo",
        decided_at="2026-09-11T10:00:00+00:00",
    )
    _seed_decision(
        artifact_dir,
        category="cap_raise",
        what="raise the campaign cap",
        actor="operator",
        decided_at="2026-09-12T10:00:00+00:00",
    )
    records, _ = dl.load_decision_records(artifact_dir=artifact_dir)
    with _db(tmp_path) as db:
        filtered = dl.build_decision_ledger(db, records, category="cap_raise", now=_NOW)
        unknown = dl.build_decision_ledger(db, records, category="not_a_category", now=_NOW)

    assert [row["category"] for row in filtered["decisions"]] == ["cap_raise"]
    assert filtered["category"] == "cap_raise"
    assert unknown["decisions"] == []
    assert unknown["missing"] == []
    assert unknown["counts"] == {"decisions": 0, "missing": 0}


def test_absent_decision_record_is_shown_as_missing_never_assumed(tmp_path):
    """A promotion/approval WITHOUT its decision half lands in ``missing``; a paired one does not."""
    artifact_dir = tmp_path / "kb"
    with _db(tmp_path) as db:
        run = db.create_run(
            spec_name="flow", model="m", state=RunState.RUNNING, reason="start",
            candidate_sha="b" * 40,
        )
        # a promotion whose promote decision record was never written (the KB was down)
        db.record_promotion(
            run.run_id, candidate_sha="b" * 40, base_sha="0" * 40, squash_sha="1" * 40,
            by="peparhugo",
        )
        # a legacy approval with no decision half + a typed approval with one
        db.record_approval(
            run.run_id, gate_id="g1", candidate_sha="b" * 40, operator="peparhugo",
            purpose="checkpoint",
        )
        db.record_approval(
            run.run_id, gate_id="g2", candidate_sha="b" * 40, operator="peparhugo",
            purpose="tree_reuse",
            decision_json=json.dumps({"purpose": "tree_reuse", "status": "approved"}),
        )
        # a promotion WITH its promote decision record — paired, so NOT missing
        db.record_promotion(
            run.run_id, candidate_sha="c" * 40, base_sha="0" * 40, squash_sha="2" * 40,
            by="peparhugo",
        )
        _seed_decision(
            artifact_dir,
            category="promote",
            what="promote flow",
            actor="verified_command",
            decided_at="2026-09-12T09:00:00+00:00",
            run_id=run.run_id,
            candidate_sha="c" * 40,
        )
        records, _ = dl.load_decision_records(artifact_dir=artifact_dir)
        payload = dl.build_decision_ledger(db, records, now=_NOW)

    missing = payload["missing"]
    assert any(
        row["source"] == "control_db.promotions"
        and row["candidate_sha"] == "b" * 40
        and row["category"] == "promote"
        and "no promote decision record" in row["reason"]
        for row in missing
    )
    assert any(
        row["source"] == "control_db.approvals"
        and row["category"] == "checkpoint"
        and "no decision record for this approval" in row["reason"]
        for row in missing
    )
    # the typed approval is a recorded decision row, not a missing one
    assert any(
        row["source"] == "control_db.approvals" and row["category"] == "tree_reuse"
        for row in payload["decisions"]
    )
    # the paired promotion is not reported missing (its decision record answers for it)
    assert not any(row["candidate_sha"] == "c" * 40 for row in missing)
    assert payload["counts"]["missing"] == 2


def test_record_half_is_served_when_the_control_plane_is_unreadable(tmp_path):
    artifact_dir = tmp_path / "kb"
    _seed_decision(
        artifact_dir,
        category="cap_raise",
        what="raise the campaign cap",
        actor="operator",
        decided_at="2026-09-12T10:00:00+00:00",
    )
    records, _ = dl.load_decision_records(artifact_dir=artifact_dir)
    payload = dl.build_decision_ledger(None, records, now=_NOW)
    assert payload["control_epoch"] is None
    assert len(payload["decisions"]) == 1
    assert payload["missing"] == []


class _FakeServices:
    """The route's injected context: records the filter it received, serves a fixed payload."""

    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def decisions(self, category=None):
        self.calls.append(category)
        return {
            "schema": "decision-ledger/v1",
            "category": category,
            "decisions": [],
            "missing": [],
        }, 200


def test_route_is_get_only_and_passes_the_category_filter(monkeypatch):
    services = _FakeServices()
    monkeypatch.setattr(route_decisions, "_services", services)
    app = Flask(__name__)
    route_decisions.register(app, services)

    methods = {
        rule.rule: rule.methods
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/")
    }
    assert methods.keys() == {"/api/decisions"}
    assert methods["/api/decisions"] == {"GET", "HEAD", "OPTIONS"}

    client = app.test_client()
    assert client.get("/api/decisions?category=cap_raise").get_json()["category"] == "cap_raise"
    assert client.get("/api/decisions").get_json()["category"] is None
    assert services.calls == ["cap_raise", None]


def test_cap_change_records_a_decision_at_the_moment_of_the_act(monkeypatch):
    """G-26: installing a NEW campaign cap writes one ``cap_raise`` decision per changed cap."""
    from agentic_dynamics.control.lease_registry import LeaseRegistry
    from scripts import run_workflow as rw

    try:
        from tests.test_lease_registry import Clock, FakeRedis
    except ImportError:  # pragma: no cover - direct-run path
        from test_lease_registry import Clock, FakeRedis

    registry = LeaseRegistry(FakeRedis(), now_fn=Clock())
    monkeypatch.setattr(
        "agentic_dynamics.control.lease_registry.LeaseRegistry.from_env",
        classmethod(lambda cls, **kwargs: registry),
    )
    recorded: list[dict] = []
    monkeypatch.setattr(rw, "_record_cap_decision", recorded.append)
    args = SimpleNamespace(
        no_admission=False,
        campaign_budget_usd=25.0,
        campaign_concurrency=3,
        workdir="/tmp/wt_room_w3_decisions",
    )

    with patch.dict(os.environ, {ADMISSION_REQUIRED_ENV: "1"}):
        gate = rw._build_phase_admission(load_spec(_SPEC), args)
    assert gate is not None
    assert [row["category"] for row in recorded] == ["cap_raise", "cap_raise"]
    budget, concurrency = recorded
    assert budget["actor"] == "operator"
    assert "budget cap" in budget["what"] and "25.0" in budget["what"]
    assert "unset ->" in budget["what"]  # the scope had never been capped
    assert budget["decided_at"]
    assert "concurrency cap" in concurrency["what"] and "3.0" in concurrency["what"]

    # a NO-OP re-install (same values) is not a change: nothing is recorded.
    with patch.dict(os.environ, {ADMISSION_REQUIRED_ENV: "1"}):
        rw._build_phase_admission(load_spec(_SPEC), args)
    assert len(recorded) == 2

    # an actual RAISE records the previous value in the new decision.
    raised = SimpleNamespace(
        no_admission=False,
        campaign_budget_usd=50.0,
        campaign_concurrency=None,
        workdir="/tmp/wt_room_w3_decisions",
    )
    with patch.dict(os.environ, {ADMISSION_REQUIRED_ENV: "1"}):
        rw._build_phase_admission(load_spec(_SPEC), raised)
    assert len(recorded) == 3
    assert "25.0 -> 50.0" in recorded[-1]["what"]


def test_cap_decision_round_trips_into_the_ledger(tmp_path):
    """G-26 -> P11: the cap decision the seam writes is the record the ledger serves."""
    from scripts import run_workflow as rw

    def _unreachable():
        raise ConnectionError("no KB stream in this test")

    result = di.record_decision(
        rw._cap_change_decision("flow", "budget", None, 25.0),
        artifact_dir=tmp_path / "kb",
        connect_fn=_unreachable,
    )
    # the durable artifact lands even with the stream down (degraded, never lost).
    assert result.status == "degraded"
    assert result.artifact_path.is_file()

    records, warnings = dl.load_decision_records(artifact_dir=tmp_path / "kb")
    assert warnings == []
    with _db(tmp_path) as db:
        payload = dl.build_decision_ledger(db, records, category="cap_raise", now=_NOW)
    assert len(payload["decisions"]) == 1
    row = payload["decisions"][0]
    assert row["category"] == "cap_raise"
    assert row["actor"] == "operator"
    assert row["knowledge_id"] == result.record.knowledge_id
    assert "25.0" in row["what"]
    assert payload["missing"] == []
