"""Canonical identity + authority contract for the runtime-RAG knowledge base.

Storage-neutral trust and identity primitives. The knowledge base is a set of
disposable search views over authoritative artifacts (the git checkout plus
immutable result / review / test / session artifacts). Every indexed unit carries
two immutable sha256 identities so the *same* value is the Chroma document id, the
Neo4j node key, the Redis stream payload key, the citation key, and the
retrieval-ledger evidence id::

    entity_id    = sha256(repository_id | source_uri | logical_locator)
    knowledge_id = sha256(entity_id | source_revision | content_hash | extractor_version)

``entity_id`` identifies a *logical* item — a file, symbol, document section,
experiment cell, or session episode. ``knowledge_id`` identifies one immutable
*extracted version*: a modified symbol gets a new ``knowledge_id`` while its
``entity_id`` stays stable, so versions can be linked (``SUPERSEDES``) and filtered
to the current version. This resolves the existing Chroma ``_step_`` vs Neo4j ``_s``
identity mismatch.

Authority is *ordinal* (trust ranking), not a blended relevance feature. ``POLICY``
is pinned system/repository policy — ``AGENTS.md``, active repository instructions,
system constraints — read directly from the current checkout and *never*
probabilistically retrieved, so retrieved text can never displace it. An
``ADVISORY`` item (review, agent episode) can never override ``POLICY`` or
``SOURCE`` in a constructed prompt.

Design: ``code_reviews/2026-08-15_rag-knowledge-base-proposal-review.md`` §7 (Sol's
identity + authority contract) and the companion ``docs/rag_design.md`` §1.3 / §4.2.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

# ── Contract constants ──────────────────────────────────────────

#: Versioned event contract. Consumers reject events carrying an unknown
#: ``schema_version`` instead of guessing at their shape.
SCHEMA_VERSION = "kb/v1"

#: Allowed ``KnowledgeEvent.operation`` values. ``supersede`` links a new version to
#: its predecessor; ``upsert`` writes a fresh unit; ``delete`` tombstones one.
OPERATIONS = frozenset({"upsert", "supersede", "delete"})

#: Provenance evidence classes a ``KnowledgeRecord`` may carry. Matches the
#: repo-wide evidence tags (``[M]`` measured, ``[C]`` computed, ``[H]`` heuristic,
#: ``[P]`` policy/prior, ``[X]`` external).
EVIDENCE_CLASSES = frozenset({"[M]", "[C]", "[H]", "[P]", "[X]"})

#: Canonical separator joining the components of an identity. A literal ``|`` per the
#: design contract; components are identifiers/hashes that do not contain ``|``.
_SEP = "|"


# ── Authority ───────────────────────────────────────────────────


class Authority(IntEnum):
    """Ordinal trust ranking for a knowledge unit.

    Ordered highest-authority first::

        POLICY > SOURCE > MEASURED > DERIVED > ADVISORY

    * ``POLICY``   — pinned system/repository policy (``AGENTS.md``, active
      repository instructions, system constraints). Read directly from the checkout;
      never probabilistically retrieved.
    * ``SOURCE``   — current source: code, active specifications, current config.
      Authoritative for repository behavior and outranks all generated material.
    * ``MEASURED`` — independently measured artifacts (test results, raw attempt
      measurements). Supports an outcome claim while preserving provenance.
    * ``DERIVED``  — analysis or report generated from measurements. Retains its
      evidence class; repetition cannot promote it to policy.
    * ``ADVISORY`` — reviews, agent episodes, generated summaries. Useful as a lead
      or precedent, but cannot override current source or policy.
    """

    ADVISORY = 1
    DERIVED = 2
    MEASURED = 3
    SOURCE = 4
    POLICY = 5


# ── Message family + the single source_type vocabulary (canonical-state round 2, design §4) ──
#
# `source_type` + `operation` stay the *only* discriminators a consumer needs — the
# observation-vs-actuation split is expressed as a pure classification function, not a schema
# fork or a third envelope shape. `SOURCE_TYPES` is the single source of truth for the type
# field: one table owns every producer's `source_type` together with its nominal authority /
# evidence class and its message family, so `message_family()` no longer has to paper over a
# silently-unregistered type (the pre-R2 `OBSERVATION_TYPES` list omitted the round-1 producer
# types `finding`/`code`/`report`/`policy` and classified them "observation" only by accident
# of the default). `ACTUATION_TYPES` remains a *derived* single-member allowlist, not a denylist
# carved out of `OBSERVATION_TYPES`: a brand-new `source_type` introduced later defaults to
# "observation" (the safe family) unless someone explicitly registers it with
# `message_family="actuation"` *and* threads it through the publish_event gate
# (knowledge_stream.py). This "closed by default" posture mirrors the gate itself.


@dataclass(frozen=True)
class SourceTypeSpec:
    """One entry in the :data:`SOURCE_TYPES` vocabulary.

    Carries the *nominal* provenance for a ``source_type`` — the message family
    (``"observation"`` vs ``"actuation"``) plus the authority / evidence class its primary
    producer path emits. The authority/evidence-class columns are documentation + a sanity
    anchor, not a validator: a couple of types are context-dependent (``report`` can also be
    ``DERIVED``/``[C]`` from the entropy arm, and ``ledger_attempt``/``meta_session`` split on
    the session title), which each producer's own derivation decides at construction time.
    """

    message_family: str  # "observation" | "actuation"
    authority: Authority
    evidence_class: str  # [M] [C] [H] [P] [X]


#: The single source-type vocabulary. Every producer's ``source_type`` is registered here with
#: its message family and nominal authority/evidence class; ``message_family()``,
#: :data:`OBSERVATION_TYPES`/:data:`ACTUATION_TYPES`, and ``scripts/registry.py``'s
#: ``--record-type`` choices all derive from this one table (R2 — one owner, not three).
SOURCE_TYPES: dict[str, SourceTypeSpec] = {
    # round-1 producer types (finding/code/report/policy — previously omitted from
    # OBSERVATION_TYPES and classified "observation" only by the default).
    "finding": SourceTypeSpec("observation", Authority.MEASURED, "[M]"),
    "code": SourceTypeSpec("observation", Authority.SOURCE, "[C]"),
    "report": SourceTypeSpec("observation", Authority.MEASURED, "[M]"),  # entropy arm: DERIVED/[C]
    "policy": SourceTypeSpec("observation", Authority.POLICY, "[P]"),
    # canonical-state round 2 types (design §2's table).
    "story": SourceTypeSpec("observation", Authority.MEASURED, "[M]"),
    "review": SourceTypeSpec("observation", Authority.ADVISORY, "[H]"),
    "ledger_job": SourceTypeSpec("observation", Authority.MEASURED, "[M]"),
    "ledger_attempt": SourceTypeSpec("observation", Authority.MEASURED, "[M]"),
    "observation": SourceTypeSpec("observation", Authority.ADVISORY, "[H]"),
    "flag": SourceTypeSpec("observation", Authority.ADVISORY, "[H]"),
    "meta_session": SourceTypeSpec("observation", Authority.ADVISORY, "[H]"),
    # Spec-lifecycle addition: the experiment spec *document* and its derived lifecycle
    # (status / supersedes chain / last run). POLICY authority + "[P]" for the same reason
    # `policy` carries them — a spec is authored, pinned repository policy, read from the
    # checkout, not a measurement. It is emphatically an OBSERVATION: a spec record states
    # what a spec IS and where its lifecycle stands; it never instructs anything to act.
    # Distinct from the `policy` source_type, which carries the spec YAML's leading *text*
    # excerpt for citation — this one carries the lifecycle, keyed one record per spec.
    "spec": SourceTypeSpec("observation", Authority.POLICY, "[P]"),
    # Context Abstraction Plane I0 (context_abstraction_design.md §3.3): the ONE additive row
    # — registration, not redesign. A fact states what IS, never an instruction to act, so it
    # is an OBSERVATION. The nominal authority/evidence-class columns here are documentation
    # only (the SourceTypeSpec docstring says so explicitly): each fact's real values come from
    # the CAP epistemic mapping (§3.4) at construction time, since a fact may be derived,
    # declared, measured, or advisory depending on its reducer.
    "fact": SourceTypeSpec("observation", Authority.DERIVED, "[C]"),
    # Delta 3: the single actuation-family member.
    "actuation": SourceTypeSpec("actuation", Authority.POLICY, "[P]"),
}

#: source_type values that represent a fact ABOUT the system (what happened / was
#: observed) — never an instruction to act on it. Derived from :data:`SOURCE_TYPES`.
OBSERVATION_TYPES = frozenset(
    name for name, spec in SOURCE_TYPES.items() if spec.message_family == "observation"
)

#: source_type values that represent a candidate INSTRUCTION to act (steer, interrupt,
#: escalate, retry, budget, deadline). See docs/canonical_state_r2_design.md §5 — building
#: and unit-testing this family does not, by itself, authorize anything to fire; that is
#: gated separately (knowledge_stream.publish_event's `armed` check). Derived from
#: :data:`SOURCE_TYPES`.
ACTUATION_TYPES = frozenset(
    name for name, spec in SOURCE_TYPES.items() if spec.message_family == "actuation"
)


def message_family(source_type: str) -> str:
    """Classify a record/event's family from ``source_type`` alone.

    Adds no envelope field — the whole point of this function existing is that
    "source_type + operation are the only discriminators" stays true after the
    observation-vs-actuation split lands, not just before it. A registered ``source_type``
    returns its :data:`SOURCE_TYPES` family; any ``source_type`` not registered here —
    including one invented in the future — classifies as ``"observation"``, the safe default.
    See ``docs/canonical_state_r2_design.md`` §4 for the full rationale.
    """
    spec = SOURCE_TYPES.get(source_type)
    if spec is not None:
        return spec.message_family
    return "observation"


# ── Canonical identity + hashing helpers ────────────────────────


def _sha256(*parts: str) -> str:
    """Join ``parts`` with the canonical separator and return the sha256 hex digest."""
    return hashlib.sha256(_SEP.join(parts).encode("utf-8")).hexdigest()


def compute_entity_id(repository_id: str, source_uri: str, logical_locator: str) -> str:
    """Compute the stable logical-entity identity.

    ``entity_id = sha256(repository_id | source_uri | logical_locator)``. The same
    three inputs always yield the same identity, so two ingestion call sites that
    point at the same logical item converge on one id regardless of who computes it.
    """
    return _sha256(repository_id, source_uri, logical_locator)


def compute_knowledge_id(
    entity_id: str, source_revision: str, content_hash: str, extractor_version: str
) -> str:
    """Compute the immutable extracted-version identity.

    ``knowledge_id = sha256(entity_id | source_revision | content_hash | extractor_version)``.
    Any change to the revision, content, or extractor — but not to the logical
    identity — yields a new ``knowledge_id`` while ``entity_id`` stays stable.
    """
    return _sha256(entity_id, source_revision, content_hash, extractor_version)


def compute_content_hash(content: str) -> str:
    """Return the sha256 hex digest of raw source ``content``.

    Consumers recompute this from the authoritative artifact and compare it to the
    event's ``content_hash`` to reject corrupt or silently changed payloads.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _coerce_authority(value: Any) -> Authority:
    """Accept an ``Authority``, its int value, or its (case-insensitive) name."""
    if isinstance(value, Authority):
        return value
    if isinstance(value, int):
        return Authority(value)
    return Authority[str(value).upper()]


# ── The two frozen record types ─────────────────────────────────


@dataclass(frozen=True)
class KnowledgeEvent:
    """A source *pointer*, never the body.

    Appended to the change stream after an authoritative artifact is durably written
    or a workflow commit succeeds. Carries only pointers + hashes so consumers read
    the artifact, verify ``content_hash``, and run the versioned extractor — keeping
    the stream small and making a replay use the same source bytes as the initial
    indexing pass. Deliberately has **no** ``text``/``body`` field.
    """

    knowledge_id: str  # Idempotent key shared by every store.
    entity_id: str  # Stable logical entity across revisions.
    operation: str  # upsert | supersede | delete.
    source_uri: str  # Durable artifact or repository locator.
    source_revision: str  # Commit SHA, artifact hash, or result version.
    content_hash: str  # Lets consumers reject corrupt or changed payloads.
    occurred_at: str  # Producer timestamp used to measure end-to-end lag.
    schema_version: str  # Reject unknown contracts instead of guessing.
    event_id: str = ""  # Tracing id; NOT the idempotence key (that is knowledge_id).
    # Round 2 addition (canonical-state design §1): mirrors KnowledgeRecord.causes onto the
    # event envelope itself, so a consumer (or the publish_event lineage gate, see
    # knowledge_stream.py) can reject a malformed actuation event without first materializing
    # the record. Trailing default, same backward-compatibility argument as event_id above.
    causes: str = ""
    # Round 1 addition (canonical-state design §1): the tombstone / supersession reason. Required
    # non-empty when operation == "delete" (a tombstone must say why) and when "supersede" resolves
    # a content conflict; also reused as a caveat annotation on a recovered-from-git "upsert".
    reason: str = ""
    # Record-fidelity addition (BUG-1): the record's OWN observation timestamp — the cell's run
    # timestamp when the producer's entry stamped one, else the producer's now. Carried on the
    # pointer (not the artifact, which blanks it to keep ``content_hash`` stable across
    # re-derivations) so ``extract_record`` can reattach the real measurement time instead of the
    # producer wall-clock (``occurred_at``, which stays the end-to-end-lag clock). Trailing
    # default (empty = absent) so a pre-existing serialized event without the key still parses.
    observed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (no body — pointers only)."""
        return {
            "knowledge_id": self.knowledge_id,
            "entity_id": self.entity_id,
            "operation": self.operation,
            "source_uri": self.source_uri,
            "source_revision": self.source_revision,
            "content_hash": self.content_hash,
            "occurred_at": self.occurred_at,
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "causes": self.causes,
            "reason": self.reason,
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeEvent:
        """Reconstruct an event from a serialized dict."""
        return cls(
            knowledge_id=d["knowledge_id"],
            entity_id=d["entity_id"],
            operation=d["operation"],
            source_uri=d["source_uri"],
            source_revision=d["source_revision"],
            content_hash=d["content_hash"],
            occurred_at=d["occurred_at"],
            schema_version=d["schema_version"],
            event_id=d.get("event_id", ""),
            causes=d.get("causes", ""),
            reason=d.get("reason", ""),
            observed_at=d.get("observed_at", ""),
        )


@dataclass(frozen=True)
class KnowledgeRecord:
    """One immutable extracted knowledge unit: the full searchable record.

    Carries the body (``text``) and all provenance/validity metadata an index needs.
    ``commit_sha`` is the ``source_revision`` for code sources; ``source_revision``
    itself is not stored here because it is already folded into ``knowledge_id`` and
    represented by ``commit_sha`` for repository-backed units.
    """

    knowledge_id: str
    entity_id: str
    source_uri: str
    source_type: str  # code | spec | test | review | report | episode | policy | ...
    logical_locator: str  # file path, symbol, section, cell, or episode locator.
    repository_id: str
    branch: str
    worktree_id: str
    commit_sha: str
    content_hash: str
    extractor_version: str
    embedding_version: str
    authority: Authority
    valid_from: str
    valid_to: str | None  # None = currently valid (no known expiration).
    observed_at: str
    indexed_at: str
    acl_scope: str
    contains_sensitive_data: bool
    text: str
    token_count: int
    language: str
    symbols: list[str]
    outcome_id: str
    test_executed_success: bool | None  # None = not independently verified.
    evidence_class: str  # [M] [C] [H] [P] [X].
    confidence: float | None = None            # [H] execution-confidence; None = unmeasured.
    perturbation_strength: float | None = None # [M] strength axis (0.0 = baseline); None = unmeasured.
    # Round 2 addition (canonical-state design §1): the knowledge_id of the OBSERVATION-family
    # record that justified this record's existence. Cross-entity (unlike a same-entity
    # supersession chain) — populated only on source_type == "actuation" records; None
    # everywhere else. Trailing default so every pre-existing serialized artifact still parses
    # via from_dict()'s .get()-based construction (missing key -> None, never a TypeError).
    causes: str | None = None
    # Round 1 addition (canonical-state design §1): predecessor knowledge_id for the SAME
    # entity_id — the supersession chain link. Set only on a NEW version, never back-written onto
    # the predecessor (immutability). None for a first version. Index layers derive effective
    # valid_to from the successor's valid_from; this field is what makes that join possible.
    supersedes: str | None = None
    # Record-fidelity addition (BUG-4 / restructure R5): the structured subject this record
    # describes — for an observation record, the cell it assessed; for a flag, the session it
    # flagged. Replaces the consumer's text-split heuristic so producer prose can change freely
    # without silently breaking the flag auto-clear rule. Trailing defaults (empty = not a
    # subject-carrying record) so every pre-existing serialized artifact still parses via
    # ``from_dict()``'s ``.get()``-based construction (missing key -> empty, never a TypeError).
    subject_id: str = ""
    subject_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict, encoding ``authority`` as its enum name."""
        return {
            "knowledge_id": self.knowledge_id,
            "entity_id": self.entity_id,
            "source_uri": self.source_uri,
            "source_type": self.source_type,
            "logical_locator": self.logical_locator,
            "repository_id": self.repository_id,
            "branch": self.branch,
            "worktree_id": self.worktree_id,
            "commit_sha": self.commit_sha,
            "content_hash": self.content_hash,
            "extractor_version": self.extractor_version,
            "embedding_version": self.embedding_version,
            "authority": self.authority.name,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "observed_at": self.observed_at,
            "indexed_at": self.indexed_at,
            "acl_scope": self.acl_scope,
            "contains_sensitive_data": self.contains_sensitive_data,
            "text": self.text,
            "token_count": self.token_count,
            "language": self.language,
            "symbols": list(self.symbols),
            "outcome_id": self.outcome_id,
            "test_executed_success": self.test_executed_success,
            "evidence_class": self.evidence_class,
            "confidence": self.confidence,
            "perturbation_strength": self.perturbation_strength,
            "causes": self.causes,
            "supersedes": self.supersedes,
            "subject_id": self.subject_id,
            "subject_status": self.subject_status,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeRecord:
        """Reconstruct a record from a serialized dict."""
        return cls(
            knowledge_id=d["knowledge_id"],
            entity_id=d["entity_id"],
            source_uri=d["source_uri"],
            source_type=d["source_type"],
            logical_locator=d["logical_locator"],
            repository_id=d["repository_id"],
            branch=d["branch"],
            worktree_id=d["worktree_id"],
            commit_sha=d["commit_sha"],
            content_hash=d["content_hash"],
            extractor_version=d["extractor_version"],
            embedding_version=d["embedding_version"],
            authority=_coerce_authority(d["authority"]),
            valid_from=d["valid_from"],
            valid_to=d.get("valid_to"),
            observed_at=d["observed_at"],
            indexed_at=d["indexed_at"],
            acl_scope=d["acl_scope"],
            contains_sensitive_data=d["contains_sensitive_data"],
            text=d["text"],
            token_count=d["token_count"],
            language=d["language"],
            symbols=list(d.get("symbols", []) or []),
            outcome_id=d["outcome_id"],
            test_executed_success=d.get("test_executed_success"),
            evidence_class=d["evidence_class"],
            confidence=d.get("confidence"),
            perturbation_strength=d.get("perturbation_strength"),
            causes=d.get("causes"),
            supersedes=d.get("supersedes"),
            subject_id=d.get("subject_id", ""),
            subject_status=d.get("subject_status", ""),
        )
