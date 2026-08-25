"""Tests for the evidence prereq gate SCRIPT (scripts/evidence_prereq_gate.py).

These tests exercise the script's exit-code logic against controlled state — they do NOT
depend on the repo's live prereq state, and they are always safe to collect (unlike the
gate itself, which must never be a collected test).
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run_gate(monkeypatch, *, merged: list[str], verdicts: dict[str, str], story_ok: bool) -> int:
    """Run the gate script against a fake state (via monkeypatched modules)."""
    import importlib

    gate = importlib.import_module("scripts.evidence_prereq_gate")
    results = Path(REPO) / "experiments" / "results" / "workflows"

    def fake_last_ledger(spec: str):
        if spec not in merged and spec != "cap_story_bridge":
            return None
        return {"git_sha": "a" * 40, "ok": True if spec != "cap_story_bridge" or story_ok else False}

    monkeypatch.setattr(gate, "_last_ledger", fake_last_ledger)
    monkeypatch.setattr(gate, "_git", lambda *a: (0, ""))
    return gate.main()


BRANCHES = [
    "cap_e2_cascade_run",
    "cap_pattern_minting",
    "cap_story_bridge",
    "cap_test_runner_wiring",
]


def _verdicts_by_filename() -> dict[str, str]:
    return {
        "cap_e2_e3_review": "## Verdict: PASS",
        "cap_pattern_minting_review": "## Verdict: PASS with 1 mandatory fix",
        "cap_story_bridge_review": "## Verdict: PASS, clean sweep",
        "cap_test_runner_wiring_review": "## Verdict: PASS",
    }


def test_gate_passes_when_all_prereqs_met(monkeypatch):
    verdicts = _verdicts_by_filename()
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: verdicts.get(self.stem, ""))
    assert _run_gate(monkeypatch, merged=BRANCHES, verdicts=verdicts, story_ok=True) == 0


def test_gate_fails_when_verdict_is_fail(monkeypatch):
    verdicts = _verdicts_by_filename()
    verdicts["cap_e2_e3_review"] = "## Verdict: FAIL"
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: verdicts.get(self.stem, ""))
    assert _run_gate(monkeypatch, merged=BRANCHES, verdicts=verdicts, story_ok=True) == 1


def test_gate_fails_when_story_bridge_not_ok(monkeypatch):
    verdicts = _verdicts_by_filename()
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: verdicts.get(self.stem, ""))
    assert _run_gate(monkeypatch, merged=BRANCHES, verdicts=verdicts, story_ok=False) == 1
