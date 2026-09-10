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


def test_gap_scan_flags_a_commit_day_without_a_decision_or_close(tmp_path, monkeypatch):
    """A commit-day with no decision AND no close is a gap; a closed day is not."""
    import subprocess

    repo = tmp_path
    _kb(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "r@x"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "r"], cwd=repo, check=True)
    (repo / "f").write_text("1")
    subprocess.run(["git", "add", "f"], cwd=repo, check=True)
    env = {"GIT_AUTHOR_DATE": "2026-09-04T12:00:00", "GIT_COMMITTER_DATE": "2026-09-04T12:00:00"}
    subprocess.run(
        ["git", "commit", "-q", "-m", "covered day"],
        cwd=repo,
        check=True,
        env={**__import__("os").environ, **env},
    )
    (repo / "f").write_text("2")
    subprocess.run(["git", "add", "f"], cwd=repo, check=True)
    env2 = {"GIT_AUTHOR_DATE": "2026-09-09T12:00:00", "GIT_COMMITTER_DATE": "2026-09-09T12:00:00"}
    subprocess.run(
        ["git", "commit", "-q", "-m", "unrecorded day"],
        cwd=repo,
        check=True,
        env={**__import__("os").environ, **env2},
    )
    # A close for 09-04 only; 09-09 has no decision/close.
    _close(_kb(tmp_path), "c" * 64, "session close 2026-09-04 (covered)")
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    monkeypatch.setattr(rs, "LOOKBACK_DAYS", 30)
    report = rs.scan()
    assert "2026-09-09" in report["gap_days"]
    assert "2026-09-04" not in report["gap_days"]
