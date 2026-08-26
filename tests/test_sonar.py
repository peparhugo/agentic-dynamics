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


# ── v2: severity-filtered, change-introduced issue count (cap_2a rerun2 §2 RC1) ──


def test_new_issue_count_pre_existing_blocker_counts_zero():
    blocker = sonar_mod.SonarIssue(rule="python:S1000", severity="BLOCKER", file_path="a.py", line=5)
    assert sonar_mod.new_issue_count([blocker], [blocker]) == 0


def test_new_issue_count_introduced_blocker_counts_one():
    introduced = sonar_mod.SonarIssue(rule="python:S1000", severity="BLOCKER", file_path="b.py", line=7)
    assert sonar_mod.new_issue_count([], [introduced]) == 1


def test_new_issue_count_mixed_pre_existing_and_introduced():
    pre = sonar_mod.SonarIssue(rule="python:S1000", severity="BLOCKER", file_path="a.py", line=5)
    new = sonar_mod.SonarIssue(rule="python:S2000", severity="CRITICAL", file_path="b.py", line=7)
    assert sonar_mod.new_issue_count([pre], [pre, new]) == 1


def test_new_issue_count_identity_is_rule_file_line():
    # A MAJOR finding (python:S1244) at the same file/line is a DIFFERENT identity from a
    # BLOCKER — identity is (rule, file, line), never severity or message alone.
    major = sonar_mod.SonarIssue(rule="python:S1244", severity="MAJOR", file_path="t.py", line=18)
    blocker = sonar_mod.SonarIssue(rule="python:S1000", severity="BLOCKER", file_path="t.py", line=18)
    assert sonar_mod.issue_identity(major) != sonar_mod.issue_identity(blocker)
    # Same identity, different severity label → still "the same" issue (identity ignores severity).
    same = sonar_mod.SonarIssue(rule="python:S1000", severity="CRITICAL", file_path="t.py", line=18)
    assert sonar_mod.issue_identity(blocker) == sonar_mod.issue_identity(same)


def test_fetch_sonar_issues_passes_severities_filter(monkeypatch):
    """The v2 severity filter is SERVER-side: ``fetch_sonar_issues`` must pass
    ``severities=BLOCKER,CRITICAL`` through so a MAJOR-only finding never reaches the diff."""
    import urllib.request

    captured = {}

    class _Resp:
        def read(self):
            return b'{"issues": [], "paging": {"total": 0}}'

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    sonar_mod.fetch_sonar_issues("exp_x", severities="BLOCKER,CRITICAL")
    assert "severities=BLOCKER,CRITICAL" in captured["url"]

    # Without the filter the param is absent (legacy callers unchanged).
    captured.clear()
    sonar_mod.fetch_sonar_issues("exp_x")
    assert "severities=" not in captured["url"]
