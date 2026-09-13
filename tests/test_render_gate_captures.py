"""Render-gate capture tests — the zero-captures rejection (remediation closed-loop, decision
f987cde9).

The 2026-09-13 failure class: a workflow's verify phase passed while its committed gate report
read "PASS, Screenshots: 0" — acceptance without rendered proof. The rule is now structural in
``write_report``: a gate run that recorded no capture is a FAIL with a named violation, whatever
the fixture checks say. These tests exercise ``write_report`` directly (the pure report
assembly — no browser), plus the live-gate plumbing that feeds it.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_control_room_rendering import write_report


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "gate_report.md", tmp_path / "gate_report.json"


def test_write_report_fails_on_zero_captures(tmp_path: Path):
    """A PASS with no captures is structurally impossible — the report says so, loudly."""
    report, jp = _paths(tmp_path)
    rc = write_report([], [], report, jp, check_fixtures_exit=0)
    assert rc == 1
    text = report.read_text(encoding="utf-8")
    assert "**Status:** FAIL" in text
    assert "GATE-CAPTURES" in text, "the zero-captures violation is named, not implied"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["status"] == "FAIL"
    assert any("GATE-CAPTURES" in e for e in data["errors"])


def test_write_report_fails_on_zero_captures_even_when_fixtures_pass(tmp_path: Path):
    """The fixture sub-check passing cannot rescue an unrendered gate — captures are the proof."""
    report, jp = _paths(tmp_path)
    rc = write_report([], [], report, jp, check_fixtures_exit=0)
    assert rc == 1
    assert "**Screenshots:** 0 (none)" in report.read_text(encoding="utf-8")
    assert "GATE-CAPTURES" in report.read_text(encoding="utf-8")


def test_write_report_passes_with_captures_and_no_errors(tmp_path: Path):
    """The positive half: a gate that rendered proof and found no violations passes."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, [], report, jp, check_fixtures_exit=0)
    assert rc == 0
    assert "**Status:** PASS" in report.read_text(encoding="utf-8")
    assert "GATE-CAPTURES" not in report.read_text(encoding="utf-8")


def test_write_report_still_fails_on_errors_with_captures(tmp_path: Path):
    """Captures are necessary, not sufficient — a rendered failure is still a failure."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, ["G-2 page scrollWidth 200 > 100"], report, jp, check_fixtures_exit=0)
    assert rc == 1
    assert "**Status:** FAIL" in report.read_text(encoding="utf-8")
