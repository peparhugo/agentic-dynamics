"""Producer-side code-quality derivation for the runtime-RAG knowledge base.

This module is the *quality* ingestion path — the third derivation path feeding the KB,
alongside the measured-finding path (:mod:`instrument.knowledge_ingestion`) and the code path
(:mod:`instrument.code_ingestion`). Where those turn a results row into a ``MEASURED`` finding
or a source symbol into a ``SOURCE`` record, this one turns three *quality* signals —
SonarQube, LSP diagnostics, and architectural entropy — into ``report`` records.

Design: ``workflows/repository/rag_knowledge_sources.yaml`` phase ``quality``. The schema already
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
``status=unavailable`` and that signal is *skipped with a note*; a fetch-first analysis whose
revision cannot be confirmed to match the current one is REFUSED — a record carrying
``sonar_analysis_status: stale-refused`` is emitted (never a current-commit stamp). When no
LSP binary is installed, ``run_diagnostics`` returns ``available=False`` and that signal is
*skipped with a note* — mirroring ``lsp_diagnostics.available_tools()``'s fallback. Entropy is
pure in-memory computation, so it emits whenever a language is detected. Skipped signals are
appended to the optional ``notes`` out-parameter (never raised, never fabricated).

Contract (do NOT invent a second one): ``record_to_artifact`` serializes a quality record to its
durable per-record JSON (``content_hash = sha256(artifact)``) and ``extract_record`` reconstructs
it — identical to the code and finding paths. ``record_to_event`` emits the pointer-only event
pointing at ``file://experiments/results/kb/<knowledge_id>.json``.

Determinism: the repo revision (git HEAD sha) is **injected** and folded into every
``knowledge_id``; derivation is otherwise a pure function of the tool outputs. Timestamps are
injectable via ``now`` for tests.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_dynamics.measurement.entropy import EntropyProfile, compute_entropy
from agentic_dynamics.knowledge.knowledge import (
    Authority,
    KnowledgeRecord,
)
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
from agentic_dynamics.core.language import (
    LanguageProfile,
    _should_skip,
    build_code_snapshot,
    detect_language,
    smallest_containing_symbol,
)
from agentic_dynamics.measurement.lsp_diagnostics import LSPDiagnostic, LSPReport, run_diagnostics
from agentic_dynamics.knowledge.record_factory import build_record as build_record_from_parts
from agentic_dynamics.measurement.sonar import (
    SONAR_PASSWORD_DEFAULT,
    SONAR_STATUS_AVAILABLE,
    SONAR_STATUS_STALE_REFUSED,
    SONAR_URL_DEFAULT,
    SONAR_USER_DEFAULT,
    SonarMetrics,
    SonarIssue,
    fetch_sonar_issues,
    run_sonar_analysis,
)

# ── Extractor contract constants ────────────────────────────────

#: The extractor generation for quality records. ``knowledge_id`` folds this in, so bumping it
#: yields a new id for the *same* signal (a new quality extractor must never silently overwrite
#: the previous one's identity). Literal on purpose, mirroring ``code_ingestion.EXTRACTOR_VERSION``.
EXTRACTOR_VERSION = "quality/v1"

#: ``source_type`` recorded on every quality record — the schema's source-type taxonomy is
#: ``finding | code | report | policy``; this is the ``report`` arm.
SOURCE_TYPE = "report"

#: The extractor generation for ISSUE-LEVEL quality records (design §5.4). Distinct from
#: ``EXTRACTOR_VERSION`` so per-issue records get their own id space (never collide with the
#: per-signal summary records). Literal on purpose.
ISSUE_EXTRACTOR_VERSION = "quality-issues/v1"

#: Default ACL scope. Quality reports are public corpus data.
ACL_SCOPE = "public"

#: The three quality signals. Each is a URI fragment on the record's ``source_uri`` so the
#: three records for one codebase get distinct ``entity_id``s (they share the same
#: ``logical_locator``).
SIGNAL_SONAR = "sonar"
SIGNAL_LSP = "lsp"
SIGNAL_ENTROPY = "entropy"

#: Issue-level record signals (design §5.4): one record per Sonar issue / per LSP diagnostic.
#: The ``signal`` fragment on ``source_uri`` carries a per-issue discriminator so each issue
#: record gets a distinct ``entity_id``.
SIGNAL_SONAR_ISSUE = "sonar-issue"
SIGNAL_LSP_DIAGNOSTIC = "lsp-diagnostic"

#: Measured LSP analyzer-status enum (design §5.4 / hard rule 6): the durable availability
#: probe records ``unavailable`` with zero dependent counts when pyright cannot run.
LSP_STATUS_AVAILABLE = "available"
LSP_STATUS_UNAVAILABLE = "unavailable"


# ── Small deterministic helpers (mirror code_ingestion) ─────────


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
    """Render the SonarQube record text as a TYPED JSON payload.

    Per design finding 7, the structured analyzer fields (``tool_version``, ``config_hash``,
    ``analyzed_sha``, ``coverage``) ride as a typed JSON payload inside ``text`` — the
    ``record_factory`` surface is unchanged, no ad hoc schema. ``sonar_analysis_status`` is
    the measured status enum (``available`` / ``stale-refused``); a ``stale-refused`` payload
    carries the true ``analyzed_sha`` (or ``""`` when the server did not record it) — never
    the current commit. ``summary`` keeps the human one-liner.
    """
    payload = {
        "kind": "sonar-quality/v1",
        "summary": (
            f"{_codebase_name(codebase_path)}: {sonar.bugs} bugs, "
            f"{sonar.code_smells} smells, maintainability {sonar.maintainability_rating or '—'}"
        ),
        "sonar_analysis_status": sonar.status,
        "tool_version": sonar.tool_version,
        "config_hash": sonar.config_hash,
        "analyzed_sha": sonar.analyzed_sha,
        "coverage": sonar.coverage,
    }
    return json.dumps(payload, sort_keys=True)


def _lsp_text(lsp: LSPReport) -> str:
    """Render the LSP record text as a TYPED JSON payload (design finding 7).

    Carries ``lsp_analysis_status`` (the measured enum) + the aggregate counts. Dependent
    counts are OMITTED when the analyzer did not run (the durable unavailable probe has none).
    """
    payload: dict[str, Any] = {
        "kind": "lsp-quality/v1",
        "tool": lsp.tool,
        "lsp_analysis_status": LSP_STATUS_AVAILABLE if lsp.available else LSP_STATUS_UNAVAILABLE,
    }
    if lsp.available:
        payload["summary"] = (
            f"{lsp.tool}: {lsp.errors} errors, {lsp.warnings} warnings, "
            f"{lsp.total_diagnostics} diagnostics"
        )
        payload["total_diagnostics"] = lsp.total_diagnostics
        payload["errors"] = lsp.errors
        payload["warnings"] = lsp.warnings
    return json.dumps(payload, sort_keys=True)


def _sonar_issue_text(issue: SonarIssue, sonar: SonarMetrics, linked_symbol: str) -> str:
    """Render a Sonar issue record's text as a TYPED JSON payload (design §5.4)."""
    payload: dict[str, Any] = {
        "kind": "sonar-issue/v1",
        "file": issue.file_path,
        "line": issue.line,
        "rule": issue.rule,
        "severity": issue.severity,
        "message": issue.message,
        "remediation_effort": issue.effort,
        "sonar_analysis_status": sonar.status,
        "analyzed_sha": sonar.analyzed_sha,
        "linked_symbol": linked_symbol,
    }
    return json.dumps(payload, sort_keys=True)


def _lsp_diag_text(diag: LSPDiagnostic, lsp: LSPReport, linked_symbol: str) -> str:
    """Render an LSP diagnostic record's text as a TYPED JSON payload (design §5.4)."""
    payload: dict[str, Any] = {
        "kind": "lsp-diagnostic/v1",
        "tool": lsp.tool,
        "file": diag.file,
        "line": diag.line,
        "column": diag.column,
        "rule": diag.code,
        "severity": diag.severity,
        "message": diag.message,
        "lsp_analysis_status": LSP_STATUS_AVAILABLE,
        "linked_symbol": linked_symbol,
    }
    return json.dumps(payload, sort_keys=True)


def _lsp_unavailable_text(lsp: LSPReport) -> str:
    """Render the durable LSP availability-probe record's text (design §5.4).

    ``lsp_analysis_status: unavailable`` with zero dependent counts — the analyzer did not
    run, so no counts are claimed (never None-as-zero, never fabricated).
    """
    return json.dumps(
        {
            "kind": "lsp-quality/v1",
            "tool": lsp.tool,
            "lsp_analysis_status": LSP_STATUS_UNAVAILABLE,
        },
        sort_keys=True,
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
    source_uri = f"file://{logical_locator}#{signal}"

    # Identity + the content-hash back-fill are the shared factory's job (record_factory).
    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=source_uri,
        logical_locator=logical_locator,
        repository_id=repository_id,
        revision=revision,
        authority=authority,
        evidence_class=evidence_class,
        text=text,
        extra_fields={
            "extractor_version": EXTRACTOR_VERSION,
            "language": language,
        },
        now=now,
    )


def build_issue_record(
    *,
    signal: str,
    logical_locator: str,
    language: str,
    text: str,
    linked_symbol: str,
    repository_id: str = REPOSITORY_ID,
    revision: str,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE issue-level ``source_type=report`` record (design §5.4).

    Identity mirrors ``build_quality_record`` but with ``ISSUE_EXTRACTOR_VERSION`` and a
    per-issue ``signal`` fragment (so each issue record gets a distinct ``entity_id``) plus the
    linked symbol in ``symbols`` (smallest containing symbol; ``""`` when none — never
    invented).
    """
    source_uri = f"file://{logical_locator}#{signal}"
    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=source_uri,
        logical_locator=logical_locator,
        repository_id=repository_id,
        revision=revision,
        authority=Authority.MEASURED,
        evidence_class="[M]",
        text=text,
        extra_fields={
            "extractor_version": ISSUE_EXTRACTOR_VERSION,
            "language": language,
            "symbols": [linked_symbol] if linked_symbol else [],
        },
        now=now,
    )


# ── Issue→symbol linking helpers ────────────────────────────────


def _read_source_files(codebase_path: Path, lang_profile: LanguageProfile) -> dict[str, bytes]:
    """Read ``codebase_path``'s source files as ``{relative_path: bytes}`` (deterministic)."""
    extensions = set(lang_profile.extensions)
    files: dict[str, bytes] = {}
    for file_path in sorted(codebase_path.rglob("*")):
        if file_path.is_dir() or _should_skip(file_path) or file_path.suffix not in extensions:
            continue
        try:
            files[str(file_path.relative_to(codebase_path))] = file_path.read_bytes()
        except (OSError, UnicodeDecodeError):
            continue
    return files


def _snapshot_for(
    codebase_path: Path, lang_profile: LanguageProfile | None, revision: str, cache: dict
) -> Any | None:
    """Build (once) the typed CodeSnapshot used to link issues to symbols (design §5.4)."""
    if "snapshot" not in cache and lang_profile is not None:
        cache["snapshot"] = build_code_snapshot(
            _read_source_files(codebase_path, lang_profile),
            revision=revision,
            profile=lang_profile,
        )
    return cache.get("snapshot")


def _normalize_rel(file_path: str, codebase_path: Path) -> str:
    """Normalize an analyzer file path to the repo-relative path the snapshot keys on."""
    p = Path(file_path.replace("\\", "/"))
    if not p.is_absolute():
        return str(p)
    try:
        return str(p.resolve().relative_to(Path(codebase_path).resolve()))
    except ValueError:
        return str(p)


def _link_symbol(snapshot: Any | None, file_path: str, line: int) -> str:
    """The smallest containing symbol's qualified name, or ``""`` when none (never invented)."""
    if snapshot is None or line <= 0:
        return ""
    sym = smallest_containing_symbol(snapshot, file_path, line)
    return sym.qualified_name if sym is not None else ""


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
    """Derive ``source_type=report`` quality records: summary + issue-level (design §5.4).

    Runs three signals in order — SonarQube (``run_sonar_analysis`` + ``fetch_sonar_issues``),
    LSP (``run_diagnostics``), entropy (``compute_entropy``) — and emits:

    * SonarQube summary → ``MEASURED`` / ``[M]``; when available, ONE issue-level record per
      Sonar issue (file/line/rule/severity/message/remediation_effort, linked to the smallest
      containing symbol). A fetched analysis whose revision cannot be confirmed to match
      ``revision`` is REFUSED (``sonar_analysis_status: stale-refused``, never a current-commit
      stamp). Unavailable (no server/scanner) → skipped with a note, never fabricated.
    * LSP summary → ``MEASURED`` / ``[M]``; when the tool runs, ONE issue-level record per
      diagnostic (file/line/rule/severity/message, symbol-linked). When a real tool is selected
      but cannot run, the availability probe is DURABLE: a status record carrying
      ``lsp_analysis_status: unavailable`` with zero dependent counts (never None-as-zero).
    * Entropy → ``DERIVED`` / ``[C]`` (pure in-memory; emitted whenever a language is detected).

    ``revision`` (the git HEAD sha) is folded into the Sonar project key (revision-scoped) and
    ``codebase_path`` are **injected** for determinism and testability; ``now`` pins
    timestamps. ``notes`` is an optional out-parameter: every skipped signal appends one
    human-readable line there (the caller passes ``notes=[]`` to collect them). The function
    never raises on an absent tool, never fabricates a metric, and never invents a symbol link.
    """
    if notes is None:
        notes = []
    records: list[KnowledgeRecord] = []

    lang_profile = _resolve_profile(profile, codebase_path)
    language = lang_profile.name if lang_profile else ""
    locator = str(codebase_path)
    snapshot_cache: dict[str, Any] = {}

    # 1. SonarQube — an instrument measurement; REFUSED (never a current-commit stamp) when a
    #    fetched analysis's revision cannot be confirmed to match the current one (design §5.2),
    #    and skipped with a note (never fabricated) when the server/scanner is unavailable.
    sonar = run_sonar_analysis(str(codebase_path), revision=revision)
    if sonar.status == SONAR_STATUS_AVAILABLE:
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
        # Issue-level records (design §5.4): one record per Sonar issue, linked to the
        # smallest containing symbol. Absent issues stay absent.
        issues = fetch_sonar_issues(
            sonar.project_key,
            sonar_url=SONAR_URL_DEFAULT,
            sonar_user=SONAR_USER_DEFAULT,
            sonar_password=SONAR_PASSWORD_DEFAULT,
        )
        snapshot = _snapshot_for(codebase_path, lang_profile, revision, snapshot_cache)
        for issue in issues:
            rel = _normalize_rel(issue.file_path, codebase_path)
            linked = _link_symbol(snapshot, rel, issue.line)
            issue = SonarIssue(**{**issue.to_dict(), "file_path": rel})
            records.append(
                build_issue_record(
                    signal=f"{SIGNAL_SONAR_ISSUE}/{rel}:{issue.line}:{issue.rule}",
                    logical_locator=locator,
                    language=language,
                    text=_sonar_issue_text(issue, sonar, linked),
                    linked_symbol=linked,
                    repository_id=repository_id,
                    revision=revision,
                    now=now,
                )
            )
    elif sonar.status == SONAR_STATUS_STALE_REFUSED:
        # The status fact IS the information: a stale-fetched analysis, refused. The record
        # carries sonar_analysis_status: stale-refused + the true analyzed_sha, never a
        # current-commit stamp. Dependent counts are omitted — never None-as-zero.
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
        notes.append(
            f"sonar: stale-refused — analysis revision {sonar.analyzed_sha or '(unrecorded)'} "
            f"does not match current {revision}; refused, never stamped"
        )
    else:
        notes.append(f"sonar: skipped — {sonar.error or 'not analyzed'}")

    # 2. LSP diagnostics — another instrument measurement. When the tool runs, one summary
    #    record + one record per diagnostic (issue-level, design §5.4). When a real tool is
    #    selected but cannot run, the availability probe is DURABLE: a status record with
    #    lsp_analysis_status: unavailable and zero dependent counts (never None-as-zero).
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
        snapshot = _snapshot_for(codebase_path, lang_profile, revision, snapshot_cache)
        for i, diag in enumerate(lsp.diagnostics):
            rel = _normalize_rel(diag.file, codebase_path)
            linked = _link_symbol(snapshot, rel, diag.line)
            diag = LSPDiagnostic(
                severity=diag.severity, message=diag.message, file=rel,
                line=diag.line, column=diag.column, code=diag.code,
            )
            records.append(
                build_issue_record(
                    signal=f"{SIGNAL_LSP_DIAGNOSTIC}/{rel}:{diag.line}:{i}:{diag.code}",
                    logical_locator=locator,
                    language=language,
                    text=_lsp_diag_text(diag, lsp, linked),
                    linked_symbol=linked,
                    repository_id=repository_id,
                    revision=revision,
                    now=now,
                )
            )
    elif lsp.tool != "unknown" and lang_profile is not None:
        records.append(
            build_quality_record(
                signal=SIGNAL_LSP,
                logical_locator=locator,
                language=language,
                text=_lsp_unavailable_text(lsp),
                authority=Authority.MEASURED,
                evidence_class="[M]",
                repository_id=repository_id,
                revision=revision,
                now=now,
            )
        )
        notes.append(
            f"lsp: unavailable — tool {lsp.tool!r} (durable probe; zero dependent counts)"
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
