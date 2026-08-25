"""Tests for code-quality ingestion (quality_ingestion).

Covers the extractor contract constants, one-record-per-available-signal derivation, the
per-signal authority/evidence class (SonarQube/LSP → ``MEASURED``/``[M]``, entropy →
``DERIVED``/``[C]``), the one-line finding text, ``source_type=report``, graceful degradation
(absent tool → skipped-with-note, never fabricated), identity derivation, the reused
artifact/event round-trip, and the injected revision.
"""

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from agentic_dynamics.knowledge import quality_ingestion as qi
from agentic_dynamics.knowledge.knowledge import Authority, compute_knowledge_id
from agentic_dynamics.knowledge.knowledge_ingestion import extract_record, record_to_artifact, record_to_event
from agentic_dynamics.core.language import _PROFILES
from agentic_dynamics.measurement.lsp_diagnostics import LSPDiagnostic, LSPReport
from agentic_dynamics.measurement.sonar import (
    SONAR_STATUS_AVAILABLE,
    SONAR_STATUS_STALE_REFUSED,
    SonarIssue,
    SonarMetrics,
)

REPO = "test-repo"
REVISION = "abc1234"


@pytest.fixture(autouse=True)
def _no_live_sonar_issues(monkeypatch):
    """Keep the summary-focused tests hermetic: no live Sonar issue fetch."""
    monkeypatch.setattr(qi, "fetch_sonar_issues", lambda *a, **k: [])


def _kind(rec):
    """The typed-payload kind of a record's text, or None when the text is not JSON."""
    try:
        return json.loads(rec.text).get("kind")
    except (ValueError, TypeError):
        return None


def _write_codebase(root: Path) -> Path:
    """Write a small Python codebase so entropy has something to measure."""
    (root / "math_utils.py").write_text(
        "import os\n\n"
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n"
        "def subtract(a: int, b: int) -> int:\n"
        "    return a - b\n\n"
        "class Calculator:\n"
        "    def multiply(self, x, y):\n"
        "        return x * y\n"
    )
    return root


def _analyzed_sonar(**overrides) -> SonarMetrics:
    metrics = SonarMetrics(project_key="pkg", analyzed=True, bugs=3, code_smells=12,
                           maintainability_rating="C", status=SONAR_STATUS_AVAILABLE,
                           analyzed_sha=REVISION, coverage=42.0, tool_version="7.0.2.5100")
    for k, v in overrides.items():
        setattr(metrics, k, v)
    return metrics


def _sonar_text_payload(record) -> dict:
    return json.loads(record.text)


def _available_lsp(**overrides) -> LSPReport:
    report = LSPReport(tool="pyright", language="python", available=True,
                       errors=2, warnings=3, total_diagnostics=5)
    for k, v in overrides.items():
        setattr(report, k, v)
    return report


def _records_by_signal(records):
    """Index records by their signal name (the ``source_uri`` URI fragment)."""
    return {rec.source_uri.rsplit("#", 1)[1]: rec for rec in records}


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert qi.EXTRACTOR_VERSION == "quality/v1"
    assert qi.SOURCE_TYPE == "report"
    assert qi.ACL_SCOPE == "public"


# ── One record per available signal ─────────────────────────────


def test_one_record_per_available_signal(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION
        )

    assert set(_records_by_signal(records)) == {"sonar", "lsp", "entropy"}
    assert all(rec.source_type == "report" for rec in records)


def test_authority_and_evidence_class_per_signal(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        records = qi.derive_quality_records(
            _write_codebase(Path(d)), profile=_PROFILES["python"],
            repository_id=REPO, revision=REVISION,
        )

    by = _records_by_signal(records)
    # SonarQube and LSP are instrument measurements → MEASURED / [M].
    assert by["sonar"].authority is Authority.MEASURED
    assert by["sonar"].evidence_class == "[M]"
    assert by["lsp"].authority is Authority.MEASURED
    assert by["lsp"].evidence_class == "[M]"
    # Entropy is a computed index → DERIVED / [C].
    assert by["entropy"].authority is Authority.DERIVED
    assert by["entropy"].evidence_class == "[C]"


def test_one_line_finding_text(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION
        )

    by = _records_by_signal(records)
    # Sonar text is a TYPED JSON payload (finding 7): summary + analyzer structure fields.
    sonar = _sonar_text_payload(by["sonar"])
    assert sonar["kind"] == "sonar-quality/v1"
    assert sonar["summary"] == f"{root.name}: 3 bugs, 12 smells, maintainability C"
    assert sonar["sonar_analysis_status"] == SONAR_STATUS_AVAILABLE
    assert sonar["analyzed_sha"] == REVISION
    assert sonar["tool_version"] == "7.0.2.5100"
    assert sonar["coverage"] == 42.0
    assert "config_hash" in sonar
    lsp = json.loads(by["lsp"].text)
    assert lsp["kind"] == "lsp-quality/v1"
    assert lsp["lsp_analysis_status"] == "available"
    assert lsp["summary"] == "pyright: 2 errors, 3 warnings, 5 diagnostics"
    assert "composite entropy" in by["entropy"].text


# ── Graceful degradation ────────────────────────────────────────


def test_absent_sonar_and_lsp_skipped_not_fabricated(monkeypatch):
    monkeypatch.setattr(
        qi, "run_sonar_analysis",
        lambda path, **kwargs: SonarMetrics(analyzed=False, error="sonar-scanner not on PATH"),
    )
    monkeypatch.setattr(
        qi, "run_diagnostics", lambda path, profile: LSPReport(tool="pyright", language="python", available=False)
    )

    notes: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        records = qi.derive_quality_records(
            _write_codebase(Path(d)), profile=_PROFILES["python"],
            repository_id=REPO, revision=REVISION, notes=notes,
        )

    # Sonar unavailable -> skipped (note), never fabricated. LSP unavailable -> DURABLE
    # availability probe (lsp_analysis_status: unavailable, zero dependent counts).
    by = _records_by_signal(records)
    assert set(by) == {"lsp", "entropy"}
    lsp = json.loads(by["lsp"].text)
    assert lsp["lsp_analysis_status"] == "unavailable"
    assert "total_diagnostics" not in lsp  # zero dependent counts are OMITTED, not zeroed
    assert any("sonar" in n and "skipped" in n for n in notes)
    assert any("lsp" in n and "unavailable" in n for n in notes)
    assert not any("entropy" in n for n in notes)  # entropy is always available


def test_stale_refused_sonar_emits_status_fact_never_current_stamp(monkeypatch):
    stale = SonarMetrics(project_key="exp_src", analyzed=True, bugs=9, code_smells=40,
                         maintainability_rating="D", status=SONAR_STATUS_STALE_REFUSED,
                         analyzed_sha="deadbeef0000")
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: stale)
    monkeypatch.setattr(
        qi, "run_diagnostics", lambda path, profile: LSPReport(tool="pyright", language="python", available=False)
    )

    notes: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION, notes=notes,
        )

    by = _records_by_signal(records)
    assert "sonar" in by
    payload = _sonar_text_payload(by["sonar"])
    assert payload["sonar_analysis_status"] == SONAR_STATUS_STALE_REFUSED
    # The record never claims the current revision was analyzed.
    assert payload["analyzed_sha"] == "deadbeef0000"
    assert payload["analyzed_sha"] != REVISION
    assert any("stale-refused" in n for n in notes)
    # The record itself is keyed to the current revision (that is when the status was
    # evaluated) but the payload never stamps it as analyzed.
    assert by["sonar"].commit_sha == REVISION


def test_empty_codebase_skips_everything(monkeypatch):
    monkeypatch.setattr(
        qi, "run_sonar_analysis", lambda path, **kwargs: SonarMetrics(analyzed=False, error="worktree not found")
    )
    monkeypatch.setattr(
        qi, "run_diagnostics", lambda path, profile: LSPReport(tool="unknown", language="unknown", available=False)
    )

    notes: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "readme.md").write_text("# no code\n")
        records = qi.derive_quality_records(
            root, repository_id=REPO, revision=REVISION, notes=notes,
        )

    assert records == []
    assert len(notes) == 3  # sonar, lsp, and entropy (no language) all noted as skipped


# ── Issue-level records (design §5.4) ───────────────────────────


def test_sonar_issues_emit_one_record_per_issue_with_symbol_link(monkeypatch):
    sonar = SonarMetrics(project_key="exp_src", analyzed=True, status=SONAR_STATUS_AVAILABLE,
                         analyzed_sha=REVISION)
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: sonar)
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: LSPReport(
        tool="pyright", language="python", available=False))
    issues = [
        SonarIssue(key="k1", rule="python:S113", severity="MINOR", message="trailing comma",
                   file_path="math_utils.py", line=3, effort="5min", status="OPEN"),
        SonarIssue(key="k2", rule="python:S300", severity="MAJOR", message="method issue",
                   file_path="math_utils.py", line=11, effort="20min", status="OPEN"),
    ]
    monkeypatch.setattr(qi, "fetch_sonar_issues", lambda *a, **k: issues)

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION
        )

    issue_records = [r for r in records if _kind(r) == "sonar-issue/v1"]
    assert len(issue_records) == 2  # one per issue, never collapsed
    for rec in issue_records:
        payload = json.loads(rec.text)
        assert payload["sonar_analysis_status"] == SONAR_STATUS_AVAILABLE
        assert payload["analyzed_sha"] == REVISION
        assert rec.source_type == "report"
        assert rec.evidence_class == "[M]"
    by_rule = {json.loads(r.text)["rule"]: r for r in issue_records}
    # Smallest containing symbol link: line 3 -> add, line 11 -> Calculator.multiply.
    assert json.loads(by_rule["python:S113"].text)["linked_symbol"] == "add"
    assert by_rule["python:S113"].symbols == ["add"]
    assert json.loads(by_rule["python:S300"].text)["linked_symbol"] == "Calculator.multiply"
    assert by_rule["python:S300"].symbols == ["Calculator.multiply"]


def test_lsp_diagnostics_emit_one_record_per_diagnostic_with_symbol_link(monkeypatch):
    sonar = SonarMetrics(analyzed=False, error="offline")
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: sonar)
    report = LSPReport(tool="pyright", language="python", available=True, errors=2,
                       warnings=0, total_diagnostics=2)
    report.diagnostics = [
        LSPDiagnostic(severity="error", message="bad return", file="math_utils.py",
                      line=3, column=5, code="reportReturnType"),
        LSPDiagnostic(severity="error", message="missing attr", file="math_utils.py",
                      line=11, column=7, code="reportAttributeAccessIssue"),
    ]
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: report)

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION
        )

    diag_records = [r for r in records if _kind(r) == "lsp-diagnostic/v1"]
    assert len(diag_records) == 2  # one per diagnostic, never collapsed
    by_code = {json.loads(r.text)["rule"]: r for r in diag_records}
    assert json.loads(by_code["reportReturnType"].text)["linked_symbol"] == "add"
    assert json.loads(by_code["reportAttributeAccessIssue"].text)["linked_symbol"] == "Calculator.multiply"
    assert json.loads(by_code["reportReturnType"].text)["lsp_analysis_status"] == "available"


def test_no_issues_no_fabrication(monkeypatch):
    """Absent diagnostics/issues stay absent — no empty-file fabrication."""
    sonar = SonarMetrics(project_key="exp_src", analyzed=True, status=SONAR_STATUS_AVAILABLE)
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: sonar)
    report = LSPReport(tool="pyright", language="python", available=True, total_diagnostics=0)
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: report)
    monkeypatch.setattr(qi, "fetch_sonar_issues", lambda *a, **k: [])

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION
        )

    kinds = {_kind(r) for r in records}
    assert "sonar-issue/v1" not in kinds
    assert "lsp-diagnostic/v1" not in kinds


# ── Identity / provenance ───────────────────────────────────────


def test_revision_is_injected_head_sha(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        records = qi.derive_quality_records(
            _write_codebase(Path(d)), profile=_PROFILES["python"],
            repository_id=REPO, revision=REVISION,
        )

    assert all(rec.commit_sha == REVISION for rec in records)
    sonar = _records_by_signal(records)["sonar"]
    assert compute_knowledge_id(sonar.entity_id, REVISION, sonar.content_hash, qi.EXTRACTOR_VERSION) == sonar.knowledge_id


def test_signals_share_locator_but_distinct_entity(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION
        )

    by = _records_by_signal(records)
    assert by["sonar"].logical_locator == by["lsp"].logical_locator == by["entropy"].logical_locator == str(root)
    assert len({by[k].entity_id for k in by}) == 3  # three distinct entities


def test_language_carried_from_profile(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        records = qi.derive_quality_records(
            _write_codebase(Path(d)), profile=_PROFILES["python"],
            repository_id=REPO, revision=REVISION,
        )

    assert all(rec.language == "python" for rec in records)


# ── Reused artifact/event round-trip ────────────────────────────


def test_artifact_round_trip_preserves_quality_record(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        records = qi.derive_quality_records(
            _write_codebase(Path(d)), profile=_PROFILES["python"],
            repository_id=REPO, revision=REVISION,
        )

    record = _records_by_signal(records)["sonar"]
    artifact = record_to_artifact(record)
    event = record_to_event(record)

    assert record.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.content_hash == record.content_hash

    extracted = extract_record(event, artifact)
    assert extracted.source_type == "report"
    assert extracted.authority is Authority.MEASURED
    assert extracted.evidence_class == "[M]"
    assert extracted.logical_locator == record.logical_locator
    assert extracted.text == record.text
    assert extracted.language == "python"
    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash


def test_entropy_round_trip_authority_derived(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: SonarMetrics(analyzed=False, error="offline"))
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: LSPReport(tool="pyright", language="python", available=False))

    with tempfile.TemporaryDirectory() as d:
        records = qi.derive_quality_records(
            _write_codebase(Path(d)), profile=_PROFILES["python"],
            repository_id=REPO, revision=REVISION,
        )

    entropy = _records_by_signal(records)["entropy"]
    extracted = extract_record(record_to_event(entropy), record_to_artifact(entropy))
    assert extracted.authority is Authority.DERIVED
    assert extracted.evidence_class == "[C]"
    assert extracted.symbols == []


# ── Determinism ─────────────────────────────────────────────────


def test_deterministic_across_timestamps(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path, **kwargs: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        a = qi.derive_quality_records(root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION,
                                      now=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc))
        b = qi.derive_quality_records(root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION,
                                      now=datetime(2026, 8, 16, 9, 30, 0, tzinfo=timezone.utc))
    assert [r.knowledge_id for r in a] == [r.knowledge_id for r in b]
    assert [r.content_hash for r in a] == [r.content_hash for r in b]
