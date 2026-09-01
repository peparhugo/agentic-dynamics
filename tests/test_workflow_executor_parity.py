"""P0-1 parity tests (control-plane stabilization): the parent-child result contract.

The load-bearing guarantee this suite must catch: a child that writes ``ok: false`` (a
failed phase) or ``awaiting: true`` (a designed stop) must NEVER read as success to a
parent — whether by envelope or by exit code. The orchestrator classifies the child by
its result ENVELOPE first (the machine-readable ``WorkflowRunResult.to_dict()`` the
child prints), with the exit code as the secondary signal when no envelope exists.
``returncode == 0`` alone is never trusted: a pre-contract child exits 0 with a failed
or awaiting result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = str(_REPO_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from run_workflow import (  # noqa: E402
    EXIT_AWAITING_APPROVAL,
    EXIT_CANCELLED,
    EXIT_FAILED,
    EXIT_INVALID_REQUEST,
    EXIT_OK,
    classify_child_outcome,
    exit_code_for_result,
    parse_child_envelope,
)

# ── exit_code_for_result: the child's exit code mirrors the run outcome ──────────

def test_exit_code_ok_is_zero():
    result = SimpleNamespace(ok=True, awaiting=False)
    assert exit_code_for_result(result) == EXIT_OK


def test_exit_code_failed_is_twenty():
    result = SimpleNamespace(ok=False, awaiting=False)
    assert exit_code_for_result(result) == EXIT_FAILED


def test_exit_code_awaiting_is_ten_even_though_ok_is_false():
    """A designed stop carries ok:False — the awaiting check must win over the ok check."""
    result = SimpleNamespace(ok=False, awaiting=True)
    assert exit_code_for_result(result) == EXIT_AWAITING_APPROVAL


def test_exit_code_contract_vocabulary_is_stable():
    assert EXIT_OK == 0
    assert EXIT_AWAITING_APPROVAL == 10
    assert EXIT_FAILED == 20
    assert EXIT_INVALID_REQUEST == 30
    assert EXIT_CANCELLED == 40


# ── parse_child_envelope: the child's final JSON document is recoverable ──────────

def test_parse_child_envelope_recovers_final_json_document():
    stdout = (
        "some noise line\n"
        + json.dumps({"ok": False, "state": "failed", "error": "boom"}, indent=2)
    )
    env = parse_child_envelope(stdout)
    assert env is not None
    assert env["ok"] is False
    assert env["error"] == "boom"


def test_parse_child_envelope_ignores_earlier_json_documents():
    earlier = json.dumps({"ok": True, "state": "ok"}, indent=2)
    final = json.dumps({"ok": False, "awaiting": True, "awaiting_reason": "checkpoint"},
                       indent=2)
    env = parse_child_envelope(stdout=f"{earlier}\n{final}")
    assert env is not None
    assert env["awaiting"] is True  # the LAST document wins


def test_parse_child_envelope_none_when_no_envelope():
    assert parse_child_envelope("") is None
    assert parse_child_envelope("no json here") is None


# ── classify_child_outcome: envelope-first, exit-code fallback, never trust rc==0 ──

def test_classify_envelope_failed_even_when_exit_zero():
    """The core false-success case: a pre-contract child exits 0 but its envelope says failed."""
    stdout = json.dumps({"ok": False, "state": "failed", "error": "boom"}, indent=2)
    decision = classify_child_outcome(returncode=EXIT_OK, stdout=stdout)
    assert decision["state"] == "failed"
    assert decision["envelope"]["error"] == "boom"


def test_classify_envelope_awaiting_even_when_exit_zero():
    stdout = json.dumps({"ok": False, "awaiting": True, "awaiting_reason": "checkpoint"},
                        indent=2)
    decision = classify_child_outcome(returncode=EXIT_OK, stdout=stdout)
    assert decision["state"] == "awaiting"
    assert decision["envelope"]["awaiting_reason"] == "checkpoint"


def test_classify_envelope_ok():
    stdout = json.dumps({"ok": True, "state": "ok"}, indent=2)
    decision = classify_child_outcome(returncode=EXIT_OK, stdout=stdout)
    assert decision["state"] == "ok"


def test_classify_exit_code_fallback_when_no_envelope():
    assert classify_child_outcome(returncode=EXIT_FAILED, stdout="")["state"] == "failed"
    assert classify_child_outcome(returncode=EXIT_AWAITING_APPROVAL, stdout="")["state"] == "awaiting"
    assert classify_child_outcome(returncode=EXIT_OK, stdout="")["state"] == "ok"


def test_classify_exit_code_failed_takes_priority_over_envelope_ok():
    """A contract child that exits 20 is failed even if some stale envelope says ok."""
    stdout = json.dumps({"ok": True, "state": "ok"}, indent=2)
    decision = classify_child_outcome(returncode=EXIT_FAILED, stdout=stdout)
    assert decision["state"] == "failed"
