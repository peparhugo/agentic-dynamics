"""Producer-side code-quality derivation for the runtime-RAG knowledge base.

This module is the *quality* ingestion path — the third derivation path feeding the KB,
alongside the measured-finding path (:mod:`instrument.knowledge_ingestion`) and the code path
(:mod:`instrument.code_ingestion`). Where those turn a results row into a ``MEASURED`` finding
or a source symbol into a ``SOURCE`` record, this one turns three *quality* signals —
SonarQube, LSP diagnostics, and architectural entropy — into ``report`` records.

Design: ``experiments/specs/rag_knowledge_sources.yaml`` phase ``quality``. The schema already
anticipates it (``KnowledgeRecord.source_type`` includes ``"report"``), and ``sonar.py`` /
``lsp_diagnostics.py`` / ``entropy.py`` feed post-hoc analysis but never the KB. This module
derives one record per *available* quality signal and emits it through the SAME pointer
contract the finding and code paths established.

Authority ordering is the load-bearing rule (``knowledge.py``):

* **SonarQube** → ``MEASURED`` / ``[M]`` — the scanner is an instrument measurement, not a
  derived opinion.
* **LSP** → ``MEASURED`` / ``[M]`` — diagnostics come from a language server (another
  instrument), again an independent measurement.
* **Entropy** → ``DERIVED`` / ``[C]`` — a computed index over the AST (Shannon entropy across
  five structural dimensions), so it carries its evidence class but cannot claim ``MEASURED``.

Graceful degradation (never fail the phase, never fabricate a metric): when the SonarQube
server is unreachable or ``sonar-scanner`` is absent, ``run_sonar_analysis`` returns
``analyzed=False`` and that signal is *skipped with a note*; when no LSP binary is installed,
``run_diagnostics`` returns ``available=False`` and that signal is *skipped with a note* —
mirroring ``lsp_diagnostics.available_tools()``'s fallback. Entropy is pure in-memory
computation, so it emits whenever a language is detected. Skipped signals are appended to the
optional ``notes`` out-parameter (never raised, never fabricated).

Contract (do NOT invent a second one): ``record_to_artifact`` serializes a quality record to its
durable per-record JSON (``content_hash = sha256(artifact)``) and ``extract_record`` reconstructs
it — identical to the code and finding paths. ``record_to_event`` emits the pointer-only event
pointing at ``file://experiments/results/kb/<knowledge_id>.json``.

Determinism: the repo revision (git HEAD sha) is **injected** and folded into every
``knowledge_id``; derivation is otherwise a pure function of the tool outputs. Timestamps are
injectable via ``now`` for tests.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .entropy import EntropyProfile, compute_entropy
from .knowledge import (
    Authority,
    KnowledgeRecord,
    compute_entity_id,
    compute_knowledge_id,
)
from .knowledge_ingestion import REPOSITORY_ID, record_to_artifact
from .language import LanguageProfile, detect_language
from .lsp_diagnostics import LSPReport, run_diagnostics
from .sonar import SonarMetrics, run_sonar_analysis

# ── Extractor contract constants ────────────────────────────────

#: The extractor generation for quality records. ``knowledge_id`` folds this in, so bumping it
#: yields a new id for the *same* signal (a new quality extractor must never silently overwrite
#: the previous one's identity). Literal on purpose, mirroring ``code_ingestion.EXTRACTOR_VERSION``.
EXTRACTOR_VERSION = "quality/v1"

#: ``source_type`` recorded on every quality record — the schema's source-type taxonomy is
#: ``finding | code | report | policy``; this is the ``report`` arm.
SOURCE_TYPE = "report"

#: Default ACL scope. Quality reports are public corpus data.
ACL_SCOPE = "public"

#: The three quality signals. Each is a URI fragment on the record's ``source_uri`` so the
#: three records for one codebase get distinct ``entity_id``s (they share the same
#: ``logical_locator``).
SIGNAL_SONAR = "sonar"
SIGNAL_LSP = "lsp"
SIGNAL_ENTROPY = "entropy"


# ── Small deterministic helpers (mirror code_ingestion) ─────────


def _now_iso(now: datetime | None = None) -> str:
    """Return ``now`` (or the current UTC instant) as an ISO-8601 timestamp.

    Injectable so tests can pin timestamps; production always uses the real clock.
    """
    return (now or datetime.now(timezone.utc)).isoformat()


def _sha256_bytes(data: bytes) -> str:
    """Return the sha256 hex digest of raw bytes (the artifact-hash primitive)."""
    return hashlib.sha256(data).hexdigest()


def _resolve_profile(
    profile: LanguageProfile | None, codebase_path: Path
) -> LanguageProfile | None:
    """Resolve the language profile: the caller's ``profile``, else auto-detection."""
    if isinstance(profile, LanguageProfile):
        return profile
    return detect_language(codebase_path)


def _codebase_name(codebase_path: Path) -> str:
    """Return a human-readable name for the codebase (the directory name, else its path)."""
    return codebase_path.name or str(codebase_path)


# ── One-line finding text (a pure function of each signal) ──────


def _sonar_text(sonar: SonarMetrics, codebase_path: Path) -> str:
    """Render the SonarQube one-liner, e.g. ``"pkg: 3 bugs, 12 smells, maintainability C"``."""
    rating = sonar.maintainability_rating or "—"
    return (
        f"{_codebase_name(codebase_path)}: {sonar.bugs} bugs, "
        f"{sonar.code_smells} smells, maintainability {rating}"
    )


def _lsp_text(lsp: LSPReport) -> str:
    """Render the LSP one-liner, e.g. ``"pyright: 2 errors, 3 warnings, 5 diagnostics"``."""
    return (
        f"{lsp.tool}: {lsp.errors} errors, {lsp.warnings} warnings, "
        f"{lsp.total_diagnostics} diagnostics"
    )


def _entropy_text(entropy: EntropyProfile, codebase_path: Path) -> str:
    """Render the entropy one-liner — the composite index plus its five dimensions."""
    return (
        f"{_codebase_name(codebase_path)}: composite entropy {entropy.composite_entropy:.4f} "
        f"(functions {entropy.function_length_entropy:.4f}, modules {entropy.module_size_entropy:.4f}, "
        f"imports {entropy.import_edge_entropy:.4f}, naming {entropy.naming_entropy:.4f}, "
        f"responsibility {entropy.file_responsibility_entropy:.4f})"
    )


# ── Record construction ─────────────────────────────────────────


def build_quality_record(
    *,
    signal: str,
    logical_locator: str,
    language: str,
    text: str,
    authority: Authority,
    evidence_class: str,
    repository_id: str = REPOSITORY_ID,
    revision: str,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=report`` :class:`KnowledgeRecord` from a quality signal.

    Identity follows the canonical contract (identical to the code path):

    * ``entity_id`` — ``sha256(repository_id | source_uri | logical_locator)``. ``source_uri``
      is ``file://<logical_locator>#<signal>`` — the codebase path with a URI fragment naming
      the signal, so SonarQube / LSP / entropy records for the *same* codebase stay distinct.
      ``logical_locator`` is the plain codebase/module path, as the spec requires.
    * ``content_hash`` — ``sha256(record_to_artifact(record))``, the sha256 of the durable
      per-record JSON artifact (the reused contract).
    * ``knowledge_id`` — ``sha256(entity_id | revision | content_hash | extractor_version)``.

    ``authority`` and ``evidence_class`` are signal-specific (passed in): ``MEASURED``/``[M]``
    for instrument measurements (SonarQube, LSP) and ``DERIVED``/``[C]`` for the computed
    entropy index. ``commit_sha`` stores the injected ``revision``.
    """
    ts = _now_iso(now)
    source_uri = f"file://{logical_locator}#{signal}"
    entity_id = compute_entity_id(repository_id, source_uri, logical_locator)

    record = KnowledgeRecord(
        knowledge_id="",  # back-filled below (folds content_hash).
        entity_id=entity_id,
        source_uri=source_uri,
        source_type=SOURCE_TYPE,
        logical_locator=logical_locator,
        repository_id=repository_id,
        branch="",
        worktree_id="",
        commit_sha=revision,
        content_hash="",  # back-filled below (sha256 of the artifact).
        extractor_version=EXTRACTOR_VERSION,
        embedding_version="",
        authority=authority,
        valid_from=ts,
        valid_to=None,
        observed_at=ts,
        indexed_at=ts,
        acl_scope=ACL_SCOPE,
        contains_sensitive_data=False,
        text=text,
        token_count=max(1, len(text.split())),
        language=language,
        symbols=[],  # a quality finding has no symbol table.
        outcome_id="",
        test_executed_success=None,
        evidence_class=evidence_class,
        confidence=None,
        perturbation_strength=None,
    )
    content_hash = _sha256_bytes(record_to_artifact(record))
    knowledge_id = compute_knowledge_id(
        entity_id, revision, content_hash, EXTRACTOR_VERSION
    )
    return replace(record, content_hash=content_hash, knowledge_id=knowledge_id)


# ── The public derivation entry point ───────────────────────────


def derive_quality_records(
    codebase_path: Path,
    *,
    profile: LanguageProfile | None = None,
    repository_id: str = REPOSITORY_ID,
    revision: str,
    now: datetime | None = None,
    notes: list[str] | None = None,
) -> list[KnowledgeRecord]:
    """Derive one ``source_type=report`` record per available quality signal.

    Runs three signals in order — SonarQube (``run_sonar_analysis``), LSP (``run_diagnostics``),
    entropy (``compute_entropy``) — and emits one record per *available* signal:

    * SonarQube → ``MEASURED`` / ``[M]`` (skipped with a note when ``analyzed=False`` — no
      server, no scanner, or a scan error — never fabricated).
    * LSP → ``MEASURED`` / ``[M]`` (skipped with a note when ``available=False`` — no binary
      for the language — mirroring ``available_tools()``).
    * Entropy → ``DERIVED`` / ``[C]`` (pure in-memory; emitted whenever a language is detected).

    ``revision`` (the git HEAD sha) and ``codebase_path`` are **injected** for determinism and
    testability; ``now`` pins timestamps. ``notes`` is an optional out-parameter: every skipped
    signal appends one human-readable line there (the caller passes ``notes=[]`` to collect
    them). The function never raises on an absent tool and never fabricates a metric.
    """
    if notes is None:
        notes = []
    records: list[KnowledgeRecord] = []

    lang_profile = _resolve_profile(profile, codebase_path)
    language = lang_profile.name if lang_profile else ""
    locator = str(codebase_path)

    # 1. SonarQube — an instrument measurement; skip (don't fabricate) when unavailable.
    sonar = run_sonar_analysis(str(codebase_path))
    if sonar.analyzed:
        records.append(
            build_quality_record(
                signal=SIGNAL_SONAR,
                logical_locator=locator,
                language=language,
                text=_sonar_text(sonar, codebase_path),
                authority=Authority.MEASURED,
                evidence_class="[M]",
                repository_id=repository_id,
                revision=revision,
                now=now,
            )
        )
    else:
        notes.append(f"sonar: skipped — {sonar.error or 'not analyzed'}")

    # 2. LSP diagnostics — another instrument measurement; skip when no binary is installed.
    lsp = run_diagnostics(codebase_path, lang_profile)
    if lsp.available:
        records.append(
            build_quality_record(
                signal=SIGNAL_LSP,
                logical_locator=locator,
                language=language,
                text=_lsp_text(lsp),
                authority=Authority.MEASURED,
                evidence_class="[M]",
                repository_id=repository_id,
                revision=revision,
                now=now,
            )
        )
    else:
        notes.append(f"lsp: skipped — tool {lsp.tool!r} unavailable")

    # 3. Entropy — a computed index (always available when a language is detected).
    if lang_profile is not None:
        entropy = compute_entropy(codebase_path, lang_profile)
        records.append(
            build_quality_record(
                signal=SIGNAL_ENTROPY,
                logical_locator=locator,
                language=language,
                text=_entropy_text(entropy, codebase_path),
                authority=Authority.DERIVED,
                evidence_class="[C]",
                repository_id=repository_id,
                revision=revision,
                now=now,
            )
        )
    else:
        notes.append("entropy: skipped — no supported language detected")

    return records
