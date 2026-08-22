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
from agentic_dynamics.knowledge.spec_ingestion import registry_head

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


def fact_fingerprint(record: KnowledgeRecord) -> str:
    """Return the sha256 of a fact record's body — the "has the fact changed?" key.

    Because ``fact_text`` never mentions the predecessor ``fact_id``, this is invariant to the
    record's position in the supersession chain — the property the convergence guard depends on.
    """
    return hashlib.sha256(record.text.encode("utf-8")).hexdigest()


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
    2. Look up the entity's current head in ``registry_index.jsonl``.
    3. **No head** → first version: emit as-is (``operation="upsert"``).
    4. **Head whose content fingerprint matches** → the fact has not moved: emit nothing.
    5. **Head whose fingerprint differs** (or predates the annotation) → rebuild with
       ``supersedes=<head knowledge_id>``, giving ``generate_manifest.py`` the link it needs to
       derive ``current`` vs ``superseded``.

    No LLM, no writes: emission is the producer's job (``scripts/kb_produce_facts.py``).
    """
    records: list[KnowledgeRecord] = []
    for fact in facts:
        candidate = build_fact_record(fact)
        head = registry_head(
            candidate.entity_id, registry_path=registry_path, reason_prefix=REASON_PREFIX
        )
        if head is None:
            records.append(candidate)  # first version of this entity
            continue
        if head.fingerprint and head.fingerprint == fact_fingerprint(candidate):
            continue  # unchanged since the last registration — nothing to say
        if head.knowledge_id == candidate.knowledge_id:
            continue  # byte-identical first version already registered
        records.append(build_fact_record(fact, supersedes=head.knowledge_id))
    return records
