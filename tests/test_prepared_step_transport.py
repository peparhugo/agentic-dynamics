"""Step 3b: the child side of the prepared-step transport.

The child consumes the parent's exact step — never a re-derivation from the spec — and refuses
(never repairs) a missing, malformed, or tampered transport: a prompt that does not hash to the
carried ``prompt_sha256`` means the instruction changed in transit, and executing it would let
the recorded parent decision and the actual run disagree.
"""

from __future__ import annotations

import json

import pytest

from agentic_dynamics.runtime.executor import StepRequest, load_prepared_step


def _request(**kwargs) -> StepRequest:
    base = dict(
        phase_name="p1",
        phase_kind="agent",
        prompt="parent prompt",
        model="m",
        goal="g",
        spec_name="t",
        workdir="/tmp/wt",
        attempt=2,
    )
    base.update(kwargs)
    return StepRequest(**base)


def test_prepared_dict_carries_the_prompt_hash_and_attempt():
    prepared = _request().to_prepared_dict()
    assert prepared["schema"] == "prepared-step/v1"
    assert prepared["prompt_sha256"] == _request().prompt_sha256
    assert prepared["attempt"] == 2
    assert prepared["phase_name"] == "p1"


def test_child_loads_and_verifies(tmp_path):
    path = tmp_path / "p1.a2.json"
    path.write_text(json.dumps(_request().to_prepared_dict()), encoding="utf-8")

    loaded = load_prepared_step(path)

    assert loaded["prompt"] == "parent prompt"
    assert loaded["phase_name"] == "p1"
    assert loaded["attempt"] == 2


def test_child_refuses_a_changed_prompt(tmp_path):
    payload = _request().to_prepared_dict()
    payload["prompt"] = "tampered"
    path = tmp_path / "p.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        load_prepared_step(path)


def test_child_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_prepared_step(tmp_path / "absent.json")


def test_child_refuses_a_foreign_document(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"schema": "something-else"}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a prepared-step/v1"):
        load_prepared_step(path)
