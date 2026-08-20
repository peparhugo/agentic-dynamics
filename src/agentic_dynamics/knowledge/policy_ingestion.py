"""Producer-side policy ingestion for the runtime-RAG knowledge base.

This module is the *policy* ingestion path — the fourth and highest-authority derivation
path feeding the KB, alongside the finding (:mod:`instrument.knowledge_ingestion`), code
(:mod:`instrument.code_ingestion`), and quality (:mod:`instrument.quality_ingestion`) paths.
It emits the pinned policy surface — ``AGENTS.md``, ``conventions/*.yaml``,
``experiments/definitions/*.yaml`` + ``workflows/**/*.yaml``, and the mental-model files — as ``POLICY``-authority records.

Design: ``workflows/repository/rag_knowledge_sources.yaml`` phase ``policy``. ``Authority.POLICY``
is the top trust tier (``POLICY > SOURCE > MEASURED > DERIVED > ADVISORY``); per
``knowledge.py`` it is "read directly from the current checkout and *never* probabilistically
retrieved, so retrieved text can never displace it."

**Load-bearing retrieval implication (do not violate):** these records are indexed for
*DISCOVERABILITY* and *citation* only — never as RRF fusion candidates. The prompt-constructor
and retrieval layers treat policy as pinned surface read straight from the checkout, so a
policy record's presence in the KB must not open a path for a probabilistic hit to displace the
authoritative copy. The record still flows through the SAME pointer contract as every other
source type (so a consumer can cite and audit it), but its authority ordering guarantees it can
never be overridden by generated material.

Contract (do NOT invent a second one): ``record_to_artifact`` serializes a policy record to its
durable per-record JSON (``content_hash = sha256(artifact)``) and ``extract_record`` reconstructs
it — identical to the finding/code/quality paths. ``record_to_event`` emits the pointer-only
event pointing at ``file://experiments/results/kb/<knowledge_id>.json``.

Determinism: the repo revision (git HEAD sha) is **injected** and folded into every
``knowledge_id``; ``text`` is a pure function of the file's first meaningful block (a truncated
leading excerpt — never the whole file). Timestamps are injectable via ``now`` for tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from agentic_dynamics.knowledge.knowledge import (
    Authority,
    KnowledgeRecord,
)
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
from agentic_dynamics.knowledge.record_factory import build_record as build_record_from_parts

# ── Extractor contract constants ────────────────────────────────

#: The extractor generation for policy records. ``knowledge_id`` folds this in, so bumping it
#: yields a new id for the *same* policy artifact (a new extractor must never silently
#: overwrite the previous one's identity). Literal on purpose, mirroring the other ingestion
#: paths.
EXTRACTOR_VERSION = "policy/v1"

#: ``source_type`` recorded on every policy record — the schema's taxonomy is
#: ``finding | code | report | policy``; this is the ``policy`` arm.
SOURCE_TYPE = "policy"

#: Default ACL scope. Repository policy is public corpus data (read from the public checkout).
ACL_SCOPE = "public"

#: Max characters of the first meaningful block carried in ``text``. The record must be a
#: citation aid (a leading excerpt), not a full-file mirror — the authoritative copy is the
#: checkout, and retrieval must never substitute a truncated excerpt for it.
MAX_BLOCK_CHARS = 1000


# ── First-meaningful-block extraction ───────────────────────────


def _is_comment_line(stripped: str, *, yaml_like: bool) -> bool:
    """Return True when ``stripped`` is a comment rather than content.

    HTML comments (``<!-- … -->``) are comments in any markup/YAML file. A leading ``#`` is a
    comment only in YAML (``# heading`` is *meaningful* markdown, so it is not skipped).
    """
    return stripped.startswith("<!--") or (yaml_like and stripped.startswith("#"))


def _first_meaningful_block(
    text: str, *, yaml_like: bool = False, max_chars: int = MAX_BLOCK_CHARS
) -> str:
    """Return the file's first meaningful content block — a leading excerpt, never the whole file.

    The block is the first contiguous run of non-blank, non-comment lines, after (a) any YAML
    frontmatter (``---`` … ``---``) and (b) any leading comment-only lines are skipped. It ends at
    the first blank line. The result is truncated to ``max_chars`` with a trailing ``…`` when cut,
    so a large policy file is represented by its opening content, not mirrored.
    """
    lines = text.splitlines()
    block: list[str] = []
    started = False
    in_frontmatter = False

    for idx, line in enumerate(lines):
        stripped = line.strip()

        # YAML frontmatter: a leading ``---`` fence opens it; the next ``---``/``...`` closes it.
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped in ("---", "..."):
                in_frontmatter = False
            continue

        if not stripped:
            # A blank line ends the first block (or is skipped before it has begun).
            if started:
                break
            continue

        if _is_comment_line(stripped, yaml_like=yaml_like):
            # Comment lines are skipped whether before or within the block.
            continue

        block.append(line.rstrip())
        started = True

    joined = "\n".join(block).strip()
    if len(joined) > max_chars:
        return joined[:max_chars].rstrip() + "…"
    return joined


# ── Policy-surface discovery ────────────────────────────────────


def discover_policy_paths(repo_root: Path = Path(".")) -> list[Path]:
    """Return the canonical pinned policy surface (existing files), deterministically sorted.

    The surface is the set of authoritative repository-policy artifacts: ``AGENTS.md``, the
    convention rules (``conventions/*.yaml``), the experiment specs (``experiments/definitions/*.yaml`` + ``workflows/**/*.yaml``),
    and the mental-model files (both the ``.opencode`` source and its ``.claude`` port). Only
    files that actually exist on disk are returned, and each path is resolved relative to
    ``repo_root`` so the resulting record locators are stable across checkouts.
    """
    candidates: list[Path] = [
        repo_root / "AGENTS.md",
        repo_root / ".opencode" / "instructions" / "mental-model.md",
        repo_root / ".claude" / "rules" / "mental-model.md",
    ]
    # The split spec layout (design §4): genuine experiment definitions + every workflow spec.
    candidates.extend(sorted((repo_root / "conventions").glob("*.yaml")))
    candidates.extend(sorted((repo_root / "experiments" / "definitions").glob("*.yaml")))
    candidates.extend(sorted((repo_root / "workflows").rglob("*.yaml")))
    return [p for p in candidates if p.is_file()]


def _locator(path: Path, repo_root: Path | None) -> str:
    """Return a stable logical locator: the path relative to ``repo_root`` when possible."""
    if repo_root is not None:
        try:
            return str(path.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            return str(path)
    return str(path)


# ── Record construction ─────────────────────────────────────────


def build_policy_record(
    locator: str,
    text: str,
    *,
    repository_id: str = REPOSITORY_ID,
    revision: str,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=policy`` :class:`KnowledgeRecord` from a policy artifact.

    Identity follows the canonical contract (identical to the code/quality paths):

    * ``entity_id`` — ``sha256(repository_id | source_uri | logical_locator)``, with
      ``source_uri = file://<locator>``. One record per file, so the locator alone is the
      disambiguator (no symbol fragment).
    * ``content_hash`` — ``sha256(record_to_artifact(record))``, the sha256 of the durable
      per-record JSON artifact.
    * ``knowledge_id`` — ``sha256(entity_id | revision | content_hash | extractor_version)``.

    ``authority`` is ``POLICY`` (the top trust tier — pinned repository policy) and
    ``evidence_class`` is ``"[P]"`` (policy/prior). ``commit_sha`` stores the injected
    ``revision`` (git HEAD sha), also folded into ``knowledge_id``.
    """
    source_uri = f"file://{locator}"

    # Identity + the content-hash back-fill are the shared factory's job (record_factory).
    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=source_uri,
        logical_locator=locator,
        repository_id=repository_id,
        revision=revision,
        authority=Authority.POLICY,
        evidence_class="[P]",
        text=text,
        extra_fields={
            "extractor_version": EXTRACTOR_VERSION,
        },
        now=now,
    )


# ── The public derivation entry point ───────────────────────────


def derive_policy_records(
    policy_paths: Iterable[str | Path],
    *,
    repository_id: str = REPOSITORY_ID,
    revision: str,
    repo_root: Path | None = None,
    now: datetime | None = None,
) -> list[KnowledgeRecord]:
    """Derive one ``authority=POLICY`` record per policy artifact, in input order.

    For each existing, readable path, reads the file and emits one record whose ``text`` is the
    file's first meaningful block (a truncated leading excerpt — never the whole file), whose
    ``logical_locator`` is the file path, and whose ``source_revision`` is the injected git HEAD
    sha. Missing or unreadable paths are skipped gracefully (no record, no exception) — the
    surface is whatever actually exists on disk.

    ``revision`` and (optionally) ``repo_root`` are **injected** for determinism and testability;
    ``now`` pins timestamps. Pass :func:`discover_policy_paths`'s output to ingest the canonical
    pinned policy surface. No LLM is involved.
    """
    records: list[KnowledgeRecord] = []
    for raw in policy_paths:
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        locator = _locator(path, repo_root)
        block = _first_meaningful_block(
            text, yaml_like=path.suffix in (".yaml", ".yml")
        )
        records.append(
            build_policy_record(
                locator,
                block,
                repository_id=repository_id,
                revision=revision,
                now=now,
            )
        )
    return records
