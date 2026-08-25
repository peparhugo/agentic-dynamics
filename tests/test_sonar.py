"""Tests for Sonar revision identity (design §5.2 — e1 of cap_evidence_integrity).

Covers the revision-scoped project key, the stale-refusal path (a fetch-first analysis whose
revision cannot be confirmed to match the requested one is REFUSED, never a current-commit
stamp), the typed analyzer metadata (analyzed_sha / tool_version / config_hash / coverage),
and the legacy no-revision behavior (unchanged fetch-first, status available).
"""

import tempfile
from pathlib import Path

from agentic_dynamics.measurement import sonar as sonar_mod
from agentic_dynamics.measurement.sonar import (
    SONAR_STATUS_AVAILABLE,
    SONAR_STATUS_STALE_REFUSED,
    SONAR_STATUS_UNAVAILABLE,
    SonarMetrics,
    run_sonar_analysis,
)


def _clear_cache():
    sonar_mod._SONAR_CACHE.clear()


def _worktree(tmp_path: Path) -> Path:
    wt = tmp_path / "exp_src"
    wt.mkdir()
    (wt / "math_utils.py").write_text("def add(a, b):\n    return a + b\n")
    return wt


def _analyzed(**overrides) -> SonarMetrics:
    metrics = SonarMetrics(project_key="exp_src", analyzed=True, bugs=3, code_smells=12,
                           status=SONAR_STATUS_AVAILABLE)
    for k, v in overrides.items():
        setattr(metrics, k, v)
    return metrics


# ── Revision-scoped project key ─────────────────────────────────


def test_revision_scopes_project_key_when_no_explicit_key(monkeypatch, tmp_path):
    _clear_cache()
    wt = _worktree(tmp_path)
    monkeypatch.setattr(sonar_mod, "_fetch_once", lambda *a, **k: None)
    monkeypatch.setattr(sonar_mod, "_find_sonar_scanner", lambda: None)

    result = run_sonar_analysis(str(wt), revision="0123456789abcdef")
    assert result.project_key == "exp_src_0123456789ab"


def test_fetch_first_available_when_key_is_revision_scoped(monkeypatch, tmp_path):
    _clear_cache()
    wt = _worktree(tmp_path)
    existing = _analyzed()
    monkeypatch.setattr(sonar_mod, "_fetch_once", lambda *a, **k: existing)
    monkeypatch.setattr(sonar_mod, "_fetch_analyzed_revision", lambda *a, **k: "")

    result = run_sonar_analysis(str(wt), revision="0123456789abcdef")
    assert result.status == SONAR_STATUS_AVAILABLE
    assert result.analyzed_sha == "0123456789abcdef"


# ── Stale-refusal (fail-closed) ─────────────────────────────────


def test_stale_refused_when_legacy_key_cannot_confirm_revision(monkeypatch, tmp_path):
    _clear_cache()
    wt = _worktree(tmp_path)
    existing = _analyzed(project_key="exp_src")
    monkeypatch.setattr(sonar_mod, "_fetch_once", lambda *a, **k: existing)
    # SCM disabled -> the server recorded no revision: confirms nothing.
    monkeypatch.setattr(sonar_mod, "_fetch_analyzed_revision", lambda *a, **k: "")

    result = run_sonar_analysis(str(wt), project_key="exp_src", revision="0123456789abcdef")
    assert result.status == SONAR_STATUS_STALE_REFUSED
    # The measures are real but the record never claims the current commit.
    assert result.analyzed_sha == ""
    assert result.analyzed


def test_stale_refused_when_captured_revision_mismatches(monkeypatch, tmp_path):
    _clear_cache()
    wt = _worktree(tmp_path)
    existing = _analyzed(project_key="exp_src")
    monkeypatch.setattr(sonar_mod, "_fetch_once", lambda *a, **k: existing)
    monkeypatch.setattr(sonar_mod, "_fetch_analyzed_revision", lambda *a, **k: "deadbeef0000")

    result = run_sonar_analysis(str(wt), project_key="exp_src", revision="0123456789abcdef")
    assert result.status == SONAR_STATUS_STALE_REFUSED
    assert result.analyzed_sha == "deadbeef0000"


def test_available_when_captured_revision_matches(monkeypatch, tmp_path):
    _clear_cache()
    wt = _worktree(tmp_path)
    existing = _analyzed(project_key="exp_src")
    monkeypatch.setattr(sonar_mod, "_fetch_once", lambda *a, **k: existing)
    monkeypatch.setattr(sonar_mod, "_fetch_analyzed_revision", lambda *a, **k: "0123456789abcdef")

    result = run_sonar_analysis(str(wt), project_key="exp_src", revision="0123456789abcdef")
    assert result.status == SONAR_STATUS_AVAILABLE


def test_legacy_no_revision_keeps_available_fetch_first(monkeypatch, tmp_path):
    _clear_cache()
    wt = _worktree(tmp_path)
    existing = _analyzed(project_key="exp_src")
    monkeypatch.setattr(sonar_mod, "_fetch_once", lambda *a, **k: existing)
    monkeypatch.setattr(sonar_mod, "_fetch_analyzed_revision", lambda *a, **k: "")

    result = run_sonar_analysis(str(wt), project_key="exp_src")
    assert result.status == SONAR_STATUS_AVAILABLE


# ── Fresh scan stamps the scanned revision + config ─────────────


def test_fresh_scan_stamps_revision_and_config(monkeypatch, tmp_path):
    _clear_cache()
    wt = _worktree(tmp_path)
    monkeypatch.setattr(sonar_mod, "_fetch_once", lambda *a, **k: None)
    monkeypatch.setattr(sonar_mod, "_find_sonar_scanner", lambda: "/bin/true")
    monkeypatch.setattr(sonar_mod, "_scanner_version", lambda: "7.0.2.5100")
    monkeypatch.setattr(sonar_mod, "_fetch_measures", lambda *a, **k: _analyzed())

    result = run_sonar_analysis(str(wt), revision="0123456789abcdef")
    assert result.status == SONAR_STATUS_AVAILABLE
    assert result.analyzed_sha == "0123456789abcdef"
    assert result.tool_version == "7.0.2.5100"
    assert len(result.config_hash) == 64
    assert (wt / "sonar-project.properties").exists() is False  # cleaned up


# ── Availability / parsing ──────────────────────────────────────


def test_unavailable_when_no_scanner_and_no_cached_analysis(monkeypatch, tmp_path):
    _clear_cache()
    wt = _worktree(tmp_path)
    monkeypatch.setattr(sonar_mod, "_fetch_once", lambda *a, **k: None)
    monkeypatch.setattr(sonar_mod, "_find_sonar_scanner", lambda: None)

    result = run_sonar_analysis(str(wt), revision="0123456789abcdef")
    assert result.status == SONAR_STATUS_UNAVAILABLE
    assert not result.analyzed


def test_parse_measures_includes_coverage():
    metrics = sonar_mod._parse_measures("exp_src", {"coverage": "82.4", "bugs": "2"})
    assert metrics.coverage == 82.4
    assert metrics.bugs == 2
