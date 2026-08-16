"""Producer-side code-structure derivation for the runtime-RAG knowledge base.

This module is the *code* ingestion path — the second derivation path feeding the KB,
alongside the measured-finding path in :mod:`instrument.knowledge_ingestion`. Where that
module turns a ``_results_summary.json`` cell into a ``MEASURED`` finding, this one turns
source files into ``SOURCE``-authority code records: one record per function and per class,
each carrying its symbol name, a short signature summary (name + parameters + docstring
head — never the full body), its language, and the file path it lives in.

Design: ``experiments/specs/rag_knowledge_sources.yaml`` phase ``code``. The schema already
anticipates this — ``KnowledgeRecord.source_type`` includes ``"code"`` and the ``language`` /
``symbols`` fields exist for exactly this purpose — but the corpus was code-blind:
``graph.load_codebase_graph`` had zero callers and code structure never reached the KB. This
module (a) derives the code records and (b) wires ``load_codebase_graph`` back into the run
path via :func:`ingest_codebase_graph`.

Contract (do NOT invent a second one): the fixed artifact/event contract from
``knowledge_ingestion`` is reused verbatim — :func:`knowledge_ingestion.record_to_artifact`
serializes a code record to its durable per-record JSON (``content_hash = sha256(artifact)``),
:func:`knowledge_ingestion.record_to_event` emits the pointer-only event, and
:func:`knowledge_ingestion.extract_record` reconstructs it on the consumer side. A code record
therefore round-trips *identically* to a finding: the pointer points at
``file://experiments/results/kb/<knowledge_id>.json`` and its ``content_hash`` covers those
exact bytes. The only thing that differs is the record's own ``source_uri`` (the aggregate
source locator — here the source file, with a ``#symbol`` fragment) and its
``source_type``/``authority``/``evidence_class``.

Determinism: derivation is pure tree-sitter over the checkout — no LLM, no wall-clock
dependence in the identity. The repo root and revision (git HEAD sha) are **injected**, so the
same checkout + revision always yields the same ``knowledge_id`` (idempotent producer, same as
the finding path). Timestamps are injectable via ``now`` for tests.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .codebase_graph import build_graph
from .knowledge import (
    Authority,
    KnowledgeRecord,
    compute_entity_id,
    compute_knowledge_id,
)
from .knowledge_ingestion import (
    REPOSITORY_ID,
    record_to_artifact,
)
from .language import (
    _PROFILES,
    CodebaseAST,
    LanguageProfile,
    _should_skip,
    detect_language,
    get_parser,
)

if TYPE_CHECKING:
    from .graph import Neo4jClient

# ── Extractor contract constants ────────────────────────────────

#: The extractor generation for code records. ``knowledge_id`` folds this in, so bumping it
#: yields a new id for the *same* symbol (a new code extractor must never silently overwrite
#: the previous one's identity). Literal on purpose — stability is the point, mirroring
#: ``knowledge_ingestion.EXTRACTOR_VERSION``.
EXTRACTOR_VERSION = "code/v1"

#: ``source_type`` recorded on every code record. The schema's source-type taxonomy is
#: ``finding | code | report | policy``; this is the ``code`` arm.
SOURCE_TYPE = "code"

#: Default ACL scope. Source code is repository corpus data; the producer can scope narrower,
#: but derivation has no per-symbol scoping.
ACL_SCOPE = "public"

#: tree-sitter node types that carry a symbol *name* across grammars. Used as a fallback when
#: ``child_by_field_name("name")`` returns ``None`` (e.g. Go ``type_declaration`` nests the
#: identifier under a ``type_spec`` rather than exposing a ``name`` field).
_NAME_NODE_TYPES = ("identifier", "type_identifier", "field_identifier")


# ── Small deterministic helpers (mirror knowledge_ingestion) ────


def _now_iso(now: datetime | None = None) -> str:
    """Return ``now`` (or the current UTC instant) as an ISO-8601 timestamp.

    Injectable so tests can pin timestamps; production always uses the real clock.
    """
    return (now or datetime.now(timezone.utc)).isoformat()


def _sha256_bytes(data: bytes) -> str:
    """Return the sha256 hex digest of raw bytes (the artifact-hash primitive).

    ``compute_content_hash`` in :mod:`instrument.knowledge` hashes *str*; the durable artifact
    is bytes, so this byte-level hash is what ``content_hash`` must equal.
    """
    return hashlib.sha256(data).hexdigest()


# ── Profile resolution ──────────────────────────────────────────


def _resolve_profile(
    profile: LanguageProfile | CodebaseAST | None, repo_root: Path
) -> LanguageProfile | None:
    """Resolve a :class:`LanguageProfile` from the ``profile`` argument.

    A :class:`LanguageProfile` is returned as-is. A :class:`CodebaseAST` contributes only its
    ``language`` name (its lightweight ``ASTNode``s do not carry enough to reconstruct exact
    parameters/docstrings, so files are re-parsed from ``repo_root``); the name resolves back
    to the registry profile, else the codebase is re-detected. ``None`` falls back to
    auto-detection. Returns ``None`` when no supported language can be determined.
    """
    if isinstance(profile, LanguageProfile):
        return profile
    if isinstance(profile, CodebaseAST):
        return _PROFILES.get(profile.language) or detect_language(repo_root)
    return detect_language(repo_root)


# ── Symbol extraction (pure tree-sitter, no LLM) ────────────────


@dataclass(frozen=True)
class _CodeSymbol:
    """One extracted function or class, with just enough to render a signature summary."""

    name: str
    kind: str  # "function" | "class"
    signature: str  # name + parenthesized parameters (classes have none).
    docstring_head: str  # first non-empty docstring line, else "".


def _node_name(node, source_bytes: bytes) -> str:
    """Return a node's symbol name (its ``name`` field, with an identifier fallback)."""
    name_node = node.child_by_field_name("name")
    if name_node is not None and name_node.text:
        return name_node.text.decode()
    # Fallback for grammars that don't expose a ``name`` field on this node type.
    for child in node.children:
        if child.type in _NAME_NODE_TYPES and child.text:
            return child.text.decode()
    return ""


def _params_text(node, source_bytes: bytes) -> str:
    """Return the parenthesized parameter list, or ``""`` when the node has none.

    Every grammar in :mod:`instrument.language` exposes function parameters under the
    ``parameters`` field (the node text already includes the parentheses). Classes have no
    ``parameters`` field, so they get ``""``.
    """
    params = node.child_by_field_name("parameters")
    if params is not None and params.text:
        return params.text.decode()
    return ""


def _first_doc_line(raw: str) -> str:
    """Return the first non-empty line of a docstring, stripped of quotes/whitespace."""
    for line in raw.splitlines():
        line = line.strip().strip('"').strip("'").strip()
        if line:
            return line
    return ""


def _docstring_head(node, source_bytes: bytes) -> str:
    """Return the first non-empty docstring line for a function/class body, else ``""``.

    Best-effort and grammar-agnostic: only the *first* statement of the body is inspected, and
    only if it is a string literal (Python's ``expression_statement`` → ``string`` shape).
    Languages whose docstrings are comments (Go/Rust/TS) simply yield ``""`` — we never invent
    a docstring, and the record stays valid without one.
    """
    body = node.child_by_field_name("body")
    if body is None:
        return ""
    for stmt in body.children:
        if stmt.type == "expression_statement":
            for child in stmt.children:
                if child.type == "string" and child.text:
                    return _first_doc_line(child.text.decode())
        break  # a docstring can only be the first statement; anything else → none.
    return ""


def _symbol_from_node(node, kind: str, source_bytes: bytes) -> _CodeSymbol | None:
    """Build a :class:`_CodeSymbol` from a function/class tree-sitter node, or ``None``.

    The signature is ``name + parameters`` (no full body, no return-type inference — the
    requirement asks for "name + params + docstring head").
    """
    name = _node_name(node, source_bytes)
    if not name:
        return None
    signature = f"{name}{_params_text(node, source_bytes)}"
    return _CodeSymbol(
        name=name,
        kind=kind,
        signature=signature,
        docstring_head=_docstring_head(node, source_bytes),
    )


def _collect_symbols(parser, source_bytes: bytes, profile: LanguageProfile) -> list[_CodeSymbol]:
    """Walk a parse tree and collect one :class:`_CodeSymbol` per function and class.

    A full recursive walk, so a method nested inside a class is collected as its own
    ``function`` record (matching ``parse_codebase``'s ``function_count`` semantics) while the
    class itself is collected as a ``class`` record.
    """
    func_types = set(profile.function_node_types)
    class_types = set(profile.class_node_types)
    symbols: list[_CodeSymbol] = []

    def walk(node) -> None:
        if node.type in func_types:
            sym = _symbol_from_node(node, "function", source_bytes)
            if sym is not None:
                symbols.append(sym)
        elif node.type in class_types:
            sym = _symbol_from_node(node, "class", source_bytes)
            if sym is not None:
                symbols.append(sym)
        for child in node.children:
            walk(child)

    walk(parser.parse(source_bytes).root_node)
    return symbols


# ── Record construction ─────────────────────────────────────────


def _render_text(symbol: _CodeSymbol) -> str:
    """Render the one-line summary: ``signature`` plus the docstring head when present."""
    if symbol.docstring_head:
        return f"{symbol.signature} — {symbol.docstring_head}"
    return symbol.signature


def build_code_record(
    symbol: _CodeSymbol,
    file_path: str,
    language: str,
    *,
    repository_id: str = REPOSITORY_ID,
    revision: str,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=code`` :class:`KnowledgeRecord` from a :class:`_CodeSymbol`.

    Identity follows the canonical contract (identical to the finding path):

    * ``entity_id`` — ``sha256(repository_id | source_uri | logical_locator)``. ``source_uri``
      is ``file://<file_path>#<symbol>`` — the source file with a URI fragment naming the
      symbol, so two symbols in one file (which share the same ``logical_locator``) still get
      distinct entities. ``logical_locator`` stays the plain file path, as the spec requires.
    * ``content_hash`` — ``sha256(record_to_artifact(record))``, the sha256 of the durable
      per-record JSON artifact (the reused contract; not the summary text alone).
    * ``knowledge_id`` — ``sha256(entity_id | revision | content_hash | extractor_version)``;
      a new revision, extractor version, or content yields a new id while ``entity_id`` holds.

    ``authority`` is ``SOURCE`` (current source code is authoritative for repository behavior,
    outranking all generated material) and ``evidence_class`` is ``"[C]"`` (computed — the
    record is derived from the AST, not an independent measurement). ``commit_sha`` stores the
    injected ``revision`` (the git HEAD sha), which is also folded into ``knowledge_id``.
    """
    ts = _now_iso(now)
    source_uri = f"file://{file_path}#{symbol.name}"
    entity_id = compute_entity_id(repository_id, source_uri, file_path)
    text = _render_text(symbol)

    # Build with placeholder derived ids, then serialize + hash, then back-fill — exactly the
    # finding path's ordering. The ids and volatile timestamps must not be part of the bytes
    # ``content_hash`` covers (record_to_artifact blanks all five), so the id is a pure
    # function of the symbol's stable content and the producer is idempotent.
    record = KnowledgeRecord(
        knowledge_id="",  # back-filled below (folds content_hash).
        entity_id=entity_id,
        source_uri=source_uri,
        source_type=SOURCE_TYPE,
        logical_locator=file_path,
        repository_id=repository_id,
        branch="",
        worktree_id="",
        commit_sha=revision,
        content_hash="",  # back-filled below (sha256 of the artifact).
        extractor_version=EXTRACTOR_VERSION,
        embedding_version="",
        authority=Authority.SOURCE,
        valid_from=ts,
        valid_to=None,
        observed_at=ts,
        indexed_at=ts,
        acl_scope=ACL_SCOPE,
        contains_sensitive_data=False,
        text=text,
        token_count=max(1, len(text.split())),
        language=language,
        symbols=[symbol.name],
        outcome_id="",
        test_executed_success=None,
        evidence_class="[C]",
        confidence=None,
        perturbation_strength=None,
    )
    content_hash = _sha256_bytes(record_to_artifact(record))
    knowledge_id = compute_knowledge_id(
        entity_id, revision, content_hash, EXTRACTOR_VERSION
    )
    return replace(record, content_hash=content_hash, knowledge_id=knowledge_id)


# ── The public derivation entry point ───────────────────────────


def derive_code_records(
    profile: LanguageProfile | CodebaseAST | None,
    *,
    repository_id: str = REPOSITORY_ID,
    revision: str,
    repo_root: Path = Path("."),
    now: datetime | None = None,
) -> list[KnowledgeRecord]:
    """Derive one ``source_type=code`` record per function/class in ``repo_root``.

    Walks the repo for source files of the resolved language (deterministic sort order), parses
    each with tree-sitter, and emits one record per function and per class in file order. Each
    record's ``logical_locator`` is the file path, ``symbols`` is ``[<name>]``, ``language`` is
    the profile's name, ``authority`` is ``SOURCE``, and ``text`` is the signature summary
    (name + parameters + docstring head).

    ``revision`` (the git HEAD sha) is **injected** and folded into every ``knowledge_id``;
    ``repo_root`` is injected so derivation is location-independent and testable; ``now`` is
    injectable for timestamp pinning. No LLM is involved. Returns ``[]`` when no supported
    source files are found.
    """
    lang_profile = _resolve_profile(profile, repo_root)
    if lang_profile is None:
        return []

    parser = get_parser(lang_profile.tree_sitter_id)
    extensions = set(lang_profile.extensions)
    records: list[KnowledgeRecord] = []

    for file_path in sorted(repo_root.rglob("*")):
        if file_path.is_dir():
            continue
        if _should_skip(file_path) or file_path.suffix not in extensions:
            continue
        try:
            source = file_path.read_bytes()
        except (OSError, UnicodeDecodeError):
            continue

        rel_path = str(file_path.relative_to(repo_root))
        for symbol in _collect_symbols(parser, source, lang_profile):
            records.append(
                build_code_record(
                    symbol,
                    rel_path,
                    lang_profile.name,
                    repository_id=repository_id,
                    revision=revision,
                    now=now,
                )
            )

    return records


# ── Wiring graph.load_codebase_graph into the run path ──────────


def ingest_codebase_graph(
    client: Neo4jClient,
    repo_root: Path,
    *,
    worktree_name: str,
    profile: LanguageProfile | None = None,
) -> dict[str, int]:
    """Build the import graph and persist ``CodeModule`` nodes via ``load_codebase_graph``.

    This is the wiring that de-orphans ``graph.load_codebase_graph``: previously
    ``codebase_graph.build_graph`` computed the import graph and threw it away (no caller).
    Here we build it, then hand it to the Neo4j client so ``CodeModule`` nodes plus
    ``IMPORTS`` / ``IMPORTED_BY`` edges and ``(ExperimentRun)-[:TOUCHED]->(CodeModule)`` edges
    actually populate — letting retrieval answer "what else touched this module".

    ``client`` is duck-typed (any object exposing ``load_codebase_graph(graph, name)``), so the
    wiring is testable with a store double and never requires a live Neo4j connection.
    """
    graph = build_graph(repo_root, profile)
    return client.load_codebase_graph(graph, worktree_name)
