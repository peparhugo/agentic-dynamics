#!/usr/bin/env python3
"""Mint ONE procedural skill as a pattern-projection record (scope 1, flash-exploration).

The skill is derived by contemplation over the ladder's passing cell designs (frozen evidence
at ``experiments/ladder_evidence/round1/``) and rides the VERIFIED pattern retrieval gate: the
record is a ``pattern/v1`` fact + its projection, so retrieval admits it under
``pattern_projection=True`` exactly like the six reducer-minted patterns. This producer is the
scope-1 derivation seam: no existing producer mints procedural skills, and the pattern
projection guard (``fact_ingestion.build_pattern_projection_record``) requires a pattern fact.

The fact is authored here (not by the reducer), which the pre-registration addendum discloses:
the skill's ``source_experiment`` is the ladder campaign, its ``evidence_ids`` are the 12 cell
records, and its ``validity_window`` is the evidence digest (the same stable-window rule the
reducer uses).

    python3 scripts/kb_produce_skill.py --skill-json experiments/ladder_evidence/round1/skill_candidate.json
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.fact_ingestion import (
    build_fact_record,
    build_pattern_projection_record,
)
from agentic_dynamics.control.facts import (
    CanonicalFact,
    compute_fact_entity_id,
    recompute_inputs_digest,
)
from agentic_dynamics.control.reducers.pattern import (
    _AUTHORITY,
    _EPISTEMIC_STATUS,
    _EVIDENCE_CLASS,
    FACT_PREDICATES,
    PatternPayload,
    _evidence_window,
    _payload_to_json,
)
from agentic_dynamics.control.reducers.pattern import (
    VERSION as PATTERN_REDUCER_VERSION,
)
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR
from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact
from agentic_dynamics.knowledge.knowledge_stream import connect, publish_event

REPOSITORY_ID = "agentic-dynamics"
LEDGER_BASE = "121126dfbcd65a656883e3f3cc81b12e612aeeeb"


def build_skill_fact(skill: dict, *, now: str) -> CanonicalFact:
    """Build the pattern/v1 CanonicalFact for one skill (the reducer's construction shape)."""
    evidence = [str(item) for item in skill["evidence"]]
    payload = PatternPayload(
        claim=str(skill["claim"]),
        population=str(skill["population"]),
        conditions=tuple(str(c) for c in skill.get("conditions", [])),
        support=int(skill["support"]),
        uncertainty=(
            None if skill.get("uncertainty") is None else float(skill["uncertainty"])
        ),
        validity_window=_evidence_window(evidence),
        source_experiment=str(skill["source_experiment"]),
    )
    subject_id = str(skill["subject"])
    spec = FACT_PREDICATES["pattern"]
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=REPOSITORY_ID,
            scope_type="workload",
            scope_id=subject_id,
            predicate="pattern",
            subject_type="workload",
            subject_id=subject_id,
        ),
        fact_id="",
        subject_type="workload",
        subject_id=subject_id,
        predicate="pattern",
        value=_payload_to_json(payload),
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="workload",
        scope_id=subject_id,
        scope_path=f"org:{REPOSITORY_ID}/workload:{subject_id}",
        abstraction_level=spec.abstraction_level,
        epistemic_status=_EPISTEMIC_STATUS,
        authority=_AUTHORITY,
        evidence_class=_EVIDENCE_CLASS,
        observed_at=now,
        valid_from=now,
        valid_to=None,
        expires_at=None,
        reducer="pattern",
        reducer_version=PATTERN_REDUCER_VERSION,
        evidence_ids=tuple(evidence),
        inputs_digest="",
        supersedes=None,
        source_revision=LEDGER_BASE,
        repository_id=REPOSITORY_ID,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skill-json", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    skill = json.loads(Path(args.skill_json).read_text())
    now = datetime.now(timezone.utc).isoformat()
    fact = build_skill_fact(skill, now=now)
    fact_record = build_fact_record(fact)
    projection = build_pattern_projection_record(fact, source_fact_id=fact_record.knowledge_id)

    print(f"skill fact:       {fact_record.knowledge_id}")
    print(f"skill projection: {projection.knowledge_id}")
    print(f"claim: {json.loads(fact.value)['claim'][:140]}…")
    if args.dry_run:
        print("dry-run: nothing emitted")
        return 0

    # Write the immutable artifacts, then publish both pointer events (the kb-registry and
    # kb-chroma consumers project them; the write guard requires the explicit opt-in).
    os.environ["FINOPS_KB_WRITE"] = "1"
    KB_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    r = connect()
    for record in (fact_record, projection):
        artifact = record_to_artifact(record)
        (KB_ARTIFACT_DIR / f"{record.knowledge_id}.json").write_bytes(artifact)
        event = (
            fi.pattern_projection_event(record)
            if record.source_type == fi.PATTERN_SOURCE_TYPE
            else fi.fact_event(record)
        )
        event_id = publish_event(r, event, source_type=record.source_type, authorized=True)
        print(f"emitted {record.source_type:8} {record.knowledge_id} -> event {event_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
