"""Producer-side fact ingestion: ``CanonicalFact`` → ``KnowledgeRecord`` → the durable stream.

This is the *fact* half of the Context Abstraction Plane's persistence (design §3.3 / §4.3). A
reducer emits :class:`~agentic_dynamics.control.facts.CanonicalFact` objects; this module maps
them onto the EXISTING knowledge pipe — ``record_factory.build_record`` →
``record_to_artifact`` → ``record_to_event`` → ``knowledge_stream.publish_event`` — so a fact is
persisted exactly like every other knowledge record, as ``source_type="fact"``, and nothing new
is transported (hard rule 2).

The two invariants that make this more than a rename:

* **``fact_id`` IS the record's ``knowledge_id``.** The reducer emits facts with an empty
  ``fact_id``; ``build_fact_record`` runs them through the shared factory, and the factory's
  ``knowledge_id`` (``sha256(entity_id | source_revision | content_hash | reducer_version)``,
  with the canonical payload in ``text``) *is* the fact's immutable version id. Because the value
  lives inside the hashed payload, changing a value changes the id — supersession for free
  (design §3.3).
* **The supersede decision is the registry's, not the reducer's.** ``derive_fact_records``
  reuses ``spec_ingestion.registry_head`` (with the fact-plane's ``fact-content=`` fingerprint
  annotation) to decide, per ``fact_entity_id``, whether the new fact is a first version, an
  unchanged re-derivation (emit nothing — the convergence guard), or a genuine change that links
  its predecessor (``supersedes``). The same append-only registry + ``generate_manifest``
  compaction that already resolve ``spec`` lineage resolve ``fact`` lineage — no new machinery.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_dynamics.control.facts import (
    CanonicalFact,
    fact_logical_locator,
    fact_source_uri,
)
from agentic_dynamics.core.paths import REGISTRY_INDEX_PATH
from agentic_dynamics.knowledge.knowledge import KnowledgeEvent, KnowledgeRecord
from agentic_dynamics.knowledge.knowledge_ingestion import record_to_event
from agentic_dynamics.knowledge.record_factory import (
    build_record as build_record_from_parts,
)
from agentic_dynamics.knowledge.spec_ingestion import RegistryHead, registry_head

#: ``source_type`` recorded on every fact record — the ONE additive row registered in
#: ``knowledge.SOURCE_TYPES`` (design §3.3). Observation family: a fact states what IS, never
#: an instruction to act.
SOURCE_TYPE = "fact"

#: Prefix of the ``reason`` annotation a fact record's pointer event carries, so the NEXT
#: producer run can read the content fingerprint back off the registry line and decide whether
#: the fact actually changed (the same mechanism as ``spec_ingestion.REASON_PREFIX``).
REASON_PREFIX = "fact-content="


def fact_payload(fact: CanonicalFact) -> dict[str, Any]:
    """Return the fact's canonical JSON payload (design §3.3's ``text`` content)."""
    return {
        "abstraction_level": fact.abstraction_level,
        "evidence_ids": list(fact.evidence_ids),
        "expires_at": fact.expires_at,
        "inputs_digest": fact.inputs_digest,
        "predicate": fact.predicate,
        "reducer_version": fact.reducer_version,
        "scope_path": fact.scope_path,
        "subject_id": fact.subject_id,
        "subject_type": fact.subject_type,
        "unit": fact.unit,
        "value": fact.value,
        "value_type": fact.value_type,
    }


def fact_text(fact: CanonicalFact) -> str:
    """Render the canonical payload — deterministic (sorted keys), independent of the
    supersession chain (``supersedes`` is NOT part of the payload), so the fingerprint below can
    answer "did the fact change?" without being perturbed by its own position in the chain."""
    return json.dumps(fact_payload(fact), sort_keys=True)


#: ``fact_payload`` keys that carry PROVENANCE — which run/evidence produced this value — rather
#: than the value itself. Excluded from :func:`fact_fingerprint` (CAP I0-I3 repair: "content
#: identity" must never be confused with "run identity"). Since r1 populated ``evidence_ids`` with
#: a real, run-specific citation (``kb_produce_facts._run_evidence``), two runs of the SAME job
#: cell that happen to measure the SAME value now carry DIFFERENT ``evidence_ids`` (they cite
#: different run artifacts) and therefore a different ``inputs_digest`` (which folds
#: ``evidence_ids`` in, see ``facts.recompute_inputs_digest``). If the fingerprint hashed those
#: fields, every re-run — even one that changes nothing — would look like "the fact changed" and
#: spuriously supersede, defeating the convergence guard. The fields stay on the PERSISTED record
#: (``fact_payload``/``record.text``/``knowledge_id`` — the immutable VERSION identity still
#: differs per run, which is correct: each derivation IS a distinct artifact) — only the
#: supersession-worthiness *decision* ignores them.
_PROVENANCE_KEYS = frozenset({"evidence_ids", "inputs_digest"})


def fact_fingerprint(record: KnowledgeRecord) -> str:
    """Return the sha256 of a fact record's DECLARATIVE content — the "has the VALUE changed?" key.

    Deliberately narrower than ``record.text``: provenance fields (``_PROVENANCE_KEYS``) are
    stripped before hashing, so re-confirming an unchanged value from a NEW run's evidence
    fingerprints identically to the run that first measured it (content identity), even though
    their ``knowledge_id``s differ (run identity — see ``_PROVENANCE_KEYS``' docstring). Because
    the remaining payload never mentions the predecessor ``fact_id`` either, this stays invariant
    to the record's position in the supersession chain — the property the convergence guard
    depends on.
    """
    payload = json.loads(record.text)
    content = {k: v for k, v in payload.items() if k not in _PROVENANCE_KEYS}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()


def build_fact_record(
    fact: CanonicalFact,
    *,
    supersedes: str | None = None,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Map one :class:`CanonicalFact` onto a ``source_type="fact"`` :class:`KnowledgeRecord`.

    The mapping is design §3.3's table: ``source_uri``/``logical_locator`` are the fact locators,
    ``extractor_version`` is the ``reducer_version`` (the reducer IS the extractor),
    ``authority``/``evidence_class`` come from the fact's own epistemic mapping, the validity
    window travels on the record, and the canonical payload is ``text``. The record's
    ``knowledge_id`` — computed by the shared factory — is the fact's ``fact_id``.
    """
    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=fact_source_uri(fact.scope_type, fact.scope_id, fact.predicate),
        logical_locator=fact_logical_locator(fact.subject_type, fact.subject_id, fact.predicate),
        repository_id=fact.repository_id,
        revision=fact.source_revision,
        authority=fact.authority,
        evidence_class=fact.evidence_class,
        text=fact_text(fact),
        entity_id=fact.fact_entity_id,
        extra_fields={
            "extractor_version": fact.reducer_version,
            "supersedes": supersedes,
            "observed_at": fact.observed_at,
            "valid_from": fact.valid_from,
            "valid_to": fact.valid_to,
        },
        now=now,
    )


def fact_operation(record: KnowledgeRecord) -> str:
    """Return the pointer event's ``operation``: ``supersede`` when the record links a
    predecessor, else ``upsert`` (the same rule as ``spec_ingestion.spec_operation``)."""
    return "supersede" if record.supersedes else "upsert"


def fact_reason(record: KnowledgeRecord) -> str:
    """Return the ``reason`` annotation carried on the pointer event (the fingerprint the NEXT
    producer run reads back off the registry line)."""
    return f"{REASON_PREFIX}{fact_fingerprint(record)}"


def fact_event(record: KnowledgeRecord, *, now: datetime | None = None) -> KnowledgeEvent:
    """Build the pointer-only event for a fact record, with operation + reason filled in."""
    return record_to_event(
        record, operation=fact_operation(record), reason=fact_reason(record), now=now
    )


def finalize_fact(fact: CanonicalFact, record: KnowledgeRecord) -> CanonicalFact:
    """Attach the fact's real ``fact_id`` (= the record's ``knowledge_id``) to a provisional fact.

    The reducer emits facts with ``fact_id=""``; this is the one place that closes the loop, so a
    caller (or a test) can hand the finalized fact to ``facts.verify_chain``.
    """
    return replace(fact, fact_id=record.knowledge_id)


def derive_fact_records(
    facts: list[CanonicalFact] | tuple[CanonicalFact, ...],
    *,
    registry_path: Path | str = REGISTRY_INDEX_PATH,
) -> list[KnowledgeRecord]:
    """Derive one ``source_type="fact"`` record per fact whose value needs registering.

    Mirrors ``spec_ingestion.derive_spec_records`` exactly, per ``fact_entity_id``:

    1. Build the record with no predecessor link.
    2. Look up the entity's current head — first in THIS batch (see below), else in
       ``registry_index.jsonl``.
    3. **No head** → first version: emit as-is (``operation="upsert"``).
    4. **Head whose content fingerprint matches** → the fact has not moved: emit nothing.
    5. **Head whose fingerprint differs** (or predates the annotation) → rebuild with
       ``supersedes=<head knowledge_id>``, giving ``generate_manifest.py`` the link it needs to
       derive ``current`` vs ``superseded``.

    **In-batch chaining (CAP I0-I3 repair):** a single call can carry MULTIPLE facts that share
    one ``fact_entity_id`` — e.g. ``job_facts/v1`` emits a current-per-cell fact per run, and a
    batch may cover several runs of the same cell. The on-disk registry has not been written yet
    mid-batch, so reading ONLY ``registry_head`` would have every such fact see the same stale
    (or absent) disk head and independently decide "first version"/"supersedes X" — producing two
    unlinked "current" rows for one slot (a ``conflicted`` fact, per ``facts.fact_state``) instead
    of a clean chain. ``pending_head`` tracks each entity's head as this loop mutates it, so facts
    are threaded against one another oldest-first — the LAST fact processed for an entity is the
    one that ends up current.

    **Out-of-order-evidence guard (CAP I0-I3 adversarial repair, r4, attack vector "out-of-order
    evidence").** "Oldest-first" must be true regardless of the ORDER ``facts`` arrives in — a
    caller building evidence out of order (or a future caller that skips
    ``kb_produce_facts.load_run_jsons``'s own oldest-first sort) must not silently make an OLDER
    observation the registered "current" value merely because it happened to be processed last.
    This function is therefore the single place that GUARANTEES the ordering property, not merely
    a beneficiary of a well-behaved caller: ``facts`` is stably sorted by ``observed_at`` ascending
    before chaining, so "last processed" and "most recently observed" always coincide. A stable
    sort preserves the caller's relative order for facts that tie on ``observed_at`` (including the
    common case of a single fact per entity, where sorting is a no-op).

    No LLM, no writes: emission is the producer's job (``scripts/kb_produce_facts.py``).
    """
    records: list[KnowledgeRecord] = []
    pending_head: dict[str, RegistryHead] = {}
    for fact in sorted(facts, key=lambda f: f.observed_at):
        candidate = build_fact_record(fact)
        head = pending_head.get(candidate.entity_id)
        if head is None:
            head = registry_head(
                candidate.entity_id, registry_path=registry_path, reason_prefix=REASON_PREFIX
            )
        if head is None:
            pending_head[candidate.entity_id] = RegistryHead(
                candidate.knowledge_id, fact_fingerprint(candidate)
            )
            records.append(candidate)  # first version of this entity
            continue
        if head.fingerprint and head.fingerprint == fact_fingerprint(candidate):
            pending_head[candidate.entity_id] = head
            continue  # unchanged since the last registration — nothing to say
        if head.knowledge_id == candidate.knowledge_id:
            pending_head[candidate.entity_id] = head
            continue  # byte-identical first version already registered
        linked = build_fact_record(fact, supersedes=head.knowledge_id)
        pending_head[candidate.entity_id] = RegistryHead(
            linked.knowledge_id, fact_fingerprint(linked)
        )
        records.append(linked)
    return records
