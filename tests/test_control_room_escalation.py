"""Tests for the P9 ``escalation`` projection (step 7, d3 §5 P9).

Pins: with no cascade armed the projection says so explicitly and never invents events; the
E_x table is served from the published data and labeled [C]/[X]; the human-escalation counter
(G-29) is MEASURED from recorded human-attributed escalation events when they exist, and a named
unknown otherwise — never a fabricated rate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.escalation import (  # noqa: E402
    SCHEMA,
    build_escalation_cascade,
    load_escalation_attempts,
    load_human_escalation_events,
)

_NOW = "2026-09-12T12:00:00+00:00"


def _attempt(spec, model, frm=None, to=None, reason=None, cost=1.0):
    return {
        "spec_name": spec,
        "model": model,
        "escalation_from": frm,
        "escalation_to": to,
        "escalation_reason": reason,
        "cost_usd": cost,
    }


def test_no_events_is_reported_not_zero_risk():
    attempts = [_attempt("s", "m/one"), _attempt("s", "m/two")]
    payload = build_escalation_cascade(attempts, now=_NOW)
    assert payload["schema"] == SCHEMA
    assert payload["events"] == []
    assert payload["armed"] is False
    assert "G-27" in payload["armed_note"]
    assert payload["rate_by_tier"]["m/one"] == {"attempts": 1, "events": 0}


def test_recorded_events_are_served_and_arm_the_surface():
    attempts = [
        _attempt("s", "m/one"),
        _attempt("s", "m/two", frm="m/one", to="m/two", reason="retry_escalation", cost=0.25),
    ]
    payload = build_escalation_cascade(attempts, now=_NOW)
    assert payload["armed"] is True
    assert payload["events"] == [
        {"from": "m/one", "to": "m/two", "reason": "retry_escalation", "model": "m/two", "cost_usd": 0.25}
    ]
    assert payload["rate_by_tier"]["m/two"] == {"attempts": 1, "events": 1}


def test_runner_vocabulary_maps_retry_reason_to_the_event_reason(tmp_path):
    """The runner's AttemptRecord carries the WHY as ``retry_reason`` (the schema declares only
    escalation_from/to) — the projection must read THAT, not an undeclared ``escalation_reason``."""
    spec_dir = tmp_path / "workflows" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "run.json").write_text(
        json.dumps(
            {
                "spec_name": "spec",
                "attempts": [
                    {
                        "model": "m/one",
                        "escalation_from": None,
                        "escalation_to": None,
                        "retry_reason": "",
                    },
                    {
                        "model": "m/two",
                        "escalation_from": "m/one",
                        "escalation_to": None,
                        "retry_reason": "escalation",
                        "cost_usd": 1.0,
                    },
                ],
            }
        )
    )
    rows, _ = load_escalation_attempts(tmp_path / "workflows")
    payload = build_escalation_cascade(rows, now=_NOW)
    assert payload["armed"] is True
    assert payload["events"][0]["reason"] == "escalation"
    assert payload["events"][0]["cost_usd"] == 1.0


def test_spec_filter_narrows_the_population():
    attempts = [
        _attempt("a", "m/one", frm="m/one", to="m/two"),
        _attempt("b", "m/three"),
    ]
    payload = build_escalation_cascade(attempts, spec="a", now=_NOW)
    assert [e["to"] for e in payload["events"]] == ["m/two"]
    assert list(payload["rate_by_tier"]) == ["m/one", "m/two"]


def test_e_x_is_labeled_from_the_published_measurement():
    verdict = {
        "baseline_cost_usd": 0.008949,
        "per_model": [{"model": "openai/gpt-5.6-sol", "E_x": 11.4671, "fix_cost_usd": 0.102619}],
    }
    payload = build_escalation_cascade([], published={"verdicts": {"escalation": verdict}}, now=_NOW)
    e_x = payload["e_x"]
    assert e_x["state"] == "published"
    assert e_x["class"] == "[C]/[X]"
    assert e_x["per_model"][0]["E_x"] == 11.4671
    assert "data.js verdicts.escalation" in e_x["source"]


def test_absent_published_data_leaves_e_x_unknown():
    payload = build_escalation_cascade([], published=None, now=_NOW)
    assert payload["e_x"]["state"] == "unknown"
    assert payload["e_x"]["class"] == "[C]/[X]"
    assert payload["human_rate"]["state"] == "unknown"
    assert payload["human_rate"]["gap"] == "G-29"


def test_loader_reads_escalation_fields(tmp_path):
    spec_dir = tmp_path / "workflows" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "run.json").write_text(
        json.dumps(
            {
                "spec_name": "spec",
                "attempts": [
                    {"model": "m/one", "escalation_from": None, "escalation_to": None},
                    {"model": "m/two", "escalation_from": "m/one", "escalation_to": "m/two"},
                ],
            }
        )
    )
    rows, n_ledgers = load_escalation_attempts(tmp_path / "workflows")
    assert n_ledgers == 1
    assert len(rows) == 2
    assert rows[1]["escalation_to"] == "m/two"
    assert load_escalation_attempts(tmp_path / "nope") == ([], 0)


# ── G-29: the human-escalation counter, measured when recorded ───────────────────────────────


def _write_escalation_record(
    artifact_dir: Path, *, actor: str, what: str = "escalate to a human"
) -> None:
    """Write ONE real ``category=escalate`` decision artifact through the real producer."""
    from agentic_dynamics.knowledge import decision_ingestion as di
    from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact

    artifact_dir.mkdir(parents=True, exist_ok=True)
    record = di.build_decision_record(
        {
            "what": what,
            "why": "the model ladder was exhausted",
            "alternatives": [],
            "category": "escalate",
            "decided_at": "2026-09-12T11:00:00+00:00",
            "actor": actor,
        }
    )
    (artifact_dir / f"{record.knowledge_id}.json").write_bytes(record_to_artifact(record))


def test_human_rate_is_measured_from_recorded_human_events():
    attempts = [_attempt("s", "m/one") for _ in range(4)]
    human = [{"actor": "peparhugo", "what": "escalate to a human"}]
    payload = build_escalation_cascade(attempts, human_events=human, now=_NOW)
    rate = payload["human_rate"]
    assert rate["state"] == "measured"
    assert rate["class"] == "[M]"
    assert rate["events"] == 1
    assert rate["attempts"] == 4
    assert rate["rate"] == 0.25
    assert "human actor" in rate["source"]


def test_human_events_without_attempts_keep_the_rate_unknown():
    """Coverage before ratio: a non-zero numerator over a zero denominator is not a rate."""
    human = [{"actor": "peparhugo", "what": "escalate to a human"}]
    payload = build_escalation_cascade([], human_events=human, now=_NOW)
    rate = payload["human_rate"]
    assert rate["state"] == "unknown"
    assert rate["gap"] == "G-29"
    assert rate["events"] == 1
    assert rate["attempts"] == 0
    assert "zero denominator" in rate["reason"]


def test_human_rate_without_recorded_events_stays_a_named_unknown():
    payload = build_escalation_cascade([_attempt("s", "m/one")], now=_NOW)
    rate = payload["human_rate"]
    assert rate["state"] == "unknown"
    assert rate["gap"] == "G-29"
    assert "no recorded human-escalation events" in rate["reason"]


def test_loader_counts_only_human_attributed_escalation_records(tmp_path):
    artifact_dir = tmp_path / "kb"
    _write_escalation_record(artifact_dir, actor="peparhugo")
    _write_escalation_record(artifact_dir, actor="aio", what="aio-recorded escalation")
    # a record under a DIFFERENT category is not an escalation event at all
    from agentic_dynamics.knowledge import decision_ingestion as di
    from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact

    other = di.build_decision_record(
        {
            "what": "park the fleet",
            "why": "",
            "alternatives": [],
            "category": "park",
            "decided_at": "2026-09-12T11:30:00+00:00",
            "actor": "peparhugo",
        }
    )
    (artifact_dir / f"{other.knowledge_id}.json").write_bytes(record_to_artifact(other))

    events, warnings = load_human_escalation_events(artifact_dir)
    assert warnings == []
    assert [event["actor"] for event in events] == ["peparhugo"]
    assert load_human_escalation_events(tmp_path / "nope") == ([], [])
