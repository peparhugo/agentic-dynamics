"""Tests for ``scripts/recording_sweep.py`` — the deterministic recording-coverage rail.

The rail is the backstop behind the "recording is part of the act" doctrine
(``agent_config/rules.md``): it detects commit-days with no decision/close coverage and close
records that cite a decision artifact that does not exist (a "phantom claim"). The
``aio_controller_postmortem`` p5 replay found the original detector's 64-hex-only regex never
fired on the corpus's real (short-prefix) citation form, so these tests pin the prefix-aware
detector and the gap scan.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import recording_sweep as rs  # noqa: E402


def _kb(tmp_path: Path) -> Path:
    kb = tmp_path / "experiments" / "results" / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    return kb


def _close(kb: Path, stem: str, text: str) -> None:
    (kb / f"{stem}.json").write_text(
        json.dumps({"source_type": "meta_session", "extractor_version": "session/v1", "text": text})
    )


def test_phantom_claim_detected_for_the_short_prefix_form(tmp_path, monkeypatch):
    """The historical citation form — a 10-char prefix — is flagged when no artifact exists."""
    kb = _kb(tmp_path)
    _close(
        kb,
        "a" * 64,
        "session close 2026-09-04 (x): merged 96738e6da, decision record 80f02d3ce5",
    )
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    phantoms = rs._phantom_close_claims()
    assert len(phantoms) == 1
    assert "80f02d3ce5" in phantoms[0]


def test_phantom_claim_clears_when_the_artifact_exists(tmp_path, monkeypatch):
    """The backfilled decision artifact (its stem starts with the cited prefix) clears it."""
    kb = _kb(tmp_path)
    _close(
        kb,
        "a" * 64,
        "session close 2026-09-04 (x): merged 96738e6da, decision record 80f02d3ce5",
    )
    (kb / f"80f02d3ce5{'0' * 54}.json").write_text("{}")
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    assert rs._phantom_close_claims() == []


def test_full_hex_citation_that_matches_is_not_a_phantom(tmp_path, monkeypatch):
    """A full 64-char citation to an existing artifact is the happy path, never a phantom."""
    kb = _kb(tmp_path)
    stem = "b" * 64
    _close(kb, "a" * 64, f"session close 2026-09-04 (x): see decision record {stem}")
    (kb / f"{stem}.json").write_text("{}")
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    assert rs._phantom_close_claims() == []


def _commit(repo: Path, day: str, message: str) -> None:
    """Commit a file onto ``main`` with a fixed author/committer date."""
    import os
    import subprocess

    marker = repo / "f"
    marker.write_text((marker.read_text() if marker.exists() else "") + message + "\n")
    subprocess.run(["git", "add", "f"], cwd=repo, check=True)
    stamp = f"{day}T12:00:00"
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=repo,
        check=True,
        env={**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp},
    )


def _repo(tmp_path: Path) -> Path:
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "r@x"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "r"], cwd=tmp_path, check=True)
    return tmp_path


def test_same_day_close_does_not_cover_its_own_day(tmp_path, monkeypatch):
    """A1: a close dated on day D does NOT cover D's commits — the act being audited.

    This is the re-designed invariant. The original ``day in closed`` check let the close
    written at close-time satisfy its own coverage check (the F-09 self-mask).
    """
    repo = _repo(tmp_path)
    _kb(tmp_path)
    _commit(repo, "2026-09-04", "own-day commit")
    # The only close is for 09-04 itself; it must not cover 09-04.
    _close(_kb(tmp_path), "c" * 64, "session close 2026-09-04 (own-day)")
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    monkeypatch.setattr(rs, "LOOKBACK_DAYS", 3000)
    report = rs.scan()
    assert report["status"] == "measured"
    assert "2026-09-04" in report["gap_days"]


def test_later_close_covers_earlier_days_and_decision_covers_its_own(tmp_path, monkeypatch):
    """A close attests the days it FOLLOWS; a decision covers its own day."""
    repo = _repo(tmp_path)
    _kb(tmp_path)
    _commit(repo, "2026-09-04", "earlier day")
    _commit(repo, "2026-09-09", "later day")
    # A close for the LATER day covers the earlier day; the later day has its own decision.
    _close(_kb(tmp_path), "c" * 64, "session close 2026-09-09 (covers 09-04)")
    decision = {"text": json.dumps({"category": "ops", "decided_at": "2026-09-09T12:00:00+00:00"})}
    (_kb(tmp_path) / ("d" * 64 + ".json")).write_text(json.dumps(decision))
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    monkeypatch.setattr(rs, "LOOKBACK_DAYS", 3000)
    report = rs.scan()
    assert "2026-09-04" not in report["gap_days"]
    assert "2026-09-09" not in report["gap_days"]


def test_scan_is_unmeasured_when_the_runtime_data_root_is_absent(tmp_path, monkeypatch):
    """A7: a source checkout (no experiments/results/kb) measures nothing — never a gap."""
    monkeypatch.setattr(rs, "ROOT", tmp_path)  # no kb dir under it
    report = rs.scan()
    assert report["status"] == "unmeasured"
    assert report["reason"] == "no KB artifact dir on disk"
    assert report["gap_days"] == []


def test_backfill_refuses_an_unmeasured_report(tmp_path, monkeypatch):
    """A7: backfill must refuse to mint a reconstruction from an unmeasured sweep."""
    import pytest

    monkeypatch.setattr(rs, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="unmeasured"):
        rs.backfill(rs.scan())
