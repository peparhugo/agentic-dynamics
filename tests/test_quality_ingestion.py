"""Tests for code-quality ingestion (quality_ingestion).

Covers the extractor contract constants, one-record-per-available-signal derivation, the
per-signal authority/evidence class (SonarQube/LSP → ``MEASURED``/``[M]``, entropy →
``DERIVED``/``[C]``), the one-line finding text, ``source_type=report``, graceful degradation
(absent tool → skipped-with-note, never fabricated), identity derivation, the reused
artifact/event round-trip, and the injected revision.
"""

import hashlib
import tempfile
from pathlib import Path

from agentic_dynamics.knowledge import quality_ingestion as qi
from agentic_dynamics.knowledge.knowledge import Authority, compute_knowledge_id
from agentic_dynamics.knowledge.knowledge_ingestion import extract_record, record_to_artifact, record_to_event
from agentic_dynamics.core.language import _PROFILES
from agentic_dynamics.measurement.lsp_diagnostics import LSPReport
from agentic_dynamics.measurement.sonar import SonarMetrics

REPO = "test-repo"
REVISION = "abc1234"


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
                           maintainability_rating="C")
    for k, v in overrides.items():
        setattr(metrics, k, v)
    return metrics


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
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION
        )

    assert set(_records_by_signal(records)) == {"sonar", "lsp", "entropy"}
    assert all(rec.source_type == "report" for rec in records)


def test_authority_and_evidence_class_per_signal(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: _analyzed_sonar())
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
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        records = qi.derive_quality_records(
            root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION
        )

    by = _records_by_signal(records)
    assert by["sonar"].text == f"{root.name}: 3 bugs, 12 smells, maintainability C"
    assert by["lsp"].text == "pyright: 2 errors, 3 warnings, 5 diagnostics"
    assert "composite entropy" in by["entropy"].text


# ── Graceful degradation ────────────────────────────────────────


def test_absent_sonar_and_lsp_skipped_not_fabricated(monkeypatch):
    monkeypatch.setattr(
        qi, "run_sonar_analysis", lambda path: SonarMetrics(analyzed=False, error="sonar-scanner not on PATH")
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

    # Only entropy survives; sonar and lsp are skipped, never fabricated.
    assert set(_records_by_signal(records)) == {"entropy"}
    assert len(records) == 1
    assert any("sonar" in n and "skipped" in n for n in notes)
    assert any("lsp" in n and "skipped" in n for n in notes)
    assert not any("entropy" in n for n in notes)  # entropy is always available


def test_empty_codebase_skips_everything(monkeypatch):
    monkeypatch.setattr(
        qi, "run_sonar_analysis", lambda path: SonarMetrics(analyzed=False, error="worktree not found")
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


# ── Identity / provenance ───────────────────────────────────────


def test_revision_is_injected_head_sha(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: _analyzed_sonar())
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
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: _analyzed_sonar())
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
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        records = qi.derive_quality_records(
            _write_codebase(Path(d)), profile=_PROFILES["python"],
            repository_id=REPO, revision=REVISION,
        )

    assert all(rec.language == "python" for rec in records)


# ── Reused artifact/event round-trip ────────────────────────────


def test_artifact_round_trip_preserves_quality_record(monkeypatch):
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: _analyzed_sonar())
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
    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: SonarMetrics(analyzed=False, error="offline"))
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

    monkeypatch.setattr(qi, "run_sonar_analysis", lambda path: _analyzed_sonar())
    monkeypatch.setattr(qi, "run_diagnostics", lambda path, profile: _available_lsp())

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        a = qi.derive_quality_records(root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION,
                                      now=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc))
        b = qi.derive_quality_records(root, profile=_PROFILES["python"], repository_id=REPO, revision=REVISION,
                                      now=datetime(2026, 8, 16, 9, 30, 0, tzinfo=timezone.utc))
    assert [r.knowledge_id for r in a] == [r.knowledge_id for r in b]
    assert [r.content_hash for r in a] == [r.content_hash for r in b]
