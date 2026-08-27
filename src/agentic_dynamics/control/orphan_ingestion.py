"""Producer-side orphan derivation for the canonical-state registry.

``cap_runner_hardening2`` §Gap 1's "the orphan record lands on the registry/ledger
(queryable, dated, flagged)" — the registry half of that pair. The durable ledger half is
``scripts/orphan_sweep.py``'s ``experiments/results/orphans/orphans.jsonl`` + the Redis
``orphan_events`` hot list; this module registers the SAME detection as a canonical
``source_type="orphan"`` observation record, structurally parallel to
:mod:`agentic_dynamics.control.observation_ingestion` (``flag``/``observation``).

Epistemic grade: **MEASURED ``[M]``** — deliberately NOT the ADVISORY ``[H]`` a supervisor
verdict carries. The supervisor's ``flag`` is a heuristic judgment of *intent*; an orphan
detection is a deterministic function of the session store's transcript timestamps (parent
last-step vs subagent termination — see ``orphan_sweep.detect_orphans``), i.e. a reading of
measured execution state, not a judgment. It states what IS (a completed/crashed subagent
whose parent went silent) and never instructs anything to act — observation family, and the
actuation gate stays structurally untouched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agentic_dynamics.knowledge.knowledge import (
    Authority,
    KnowledgeRecord,
)
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
from agentic_dynamics.knowledge.record_factory import (
    build_record as build_record_from_parts,
)

EXTRACTOR_VERSION = "orphan/v1"
SOURCE_TYPE_ORPHAN = "orphan"
REVISION_FALLBACK = "orphan/unrevisioned"


def build_orphan_record(
    orphan: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=orphan`` record from one ``OrphanRecord``-as-dict.

    ``orphan`` is the exact dict ``agentic_dynamics.control.orphan_sweep`` serializes to the
    durable ledger (``asdict(OrphanRecord)``): ``{orphan_id, detected_at, parent_session_id,
    parent_title, subagent_session_id, subagent_title, subagent_model, spawn_at,
    terminated_at, terminated_reason, result_available, idle_minutes, ...}``. Raises
    ``ValueError`` when the subagent session id is missing — an orphan with no subject cannot
    be registered.
    """
    subagent = str(orphan.get("subagent_session_id") or "")
    if not subagent:
        raise ValueError("orphan has no subagent_session_id — cannot derive a stable identity")
    parent = str(orphan.get("parent_session_id") or "")
    detected_at = str(orphan.get("detected_at") or "")
    reason = str(orphan.get("terminated_reason") or "unknown")
    result_available = bool(orphan.get("result_available"))
    idle_minutes = orphan.get("idle_minutes")
    oid = str(orphan.get("orphan_id") or "")

    source_uri = f"orphan:{parent}|{subagent}"
    text = (
        f"orphaned delegation: parent {parent} silent after spawn; subagent {subagent} "
        f"{reason}; result_available={result_available}; idle_minutes={idle_minutes}"
    )

    # Structured fields stay within the canonical KnowledgeRecord vocabulary (subject_id /
    # subject_status / observed_at, mirroring the flag producer); the orphan-specific surface
    # (parent, termination reason, result availability, idle window) rides in ``text`` —
    # adding fields to the shared record schema would re-key unrelated producers.
    return build_record_from_parts(
        source_type=SOURCE_TYPE_ORPHAN,
        source_uri=source_uri,
        logical_locator=oid or f"{parent}|{subagent}",
        repository_id=repository_id,
        revision=REVISION_FALLBACK,
        authority=Authority.MEASURED,
        evidence_class="[M]",
        text=text,
        extra_fields={
            "commit_sha": "",
            "extractor_version": EXTRACTOR_VERSION,
            "observed_at": detected_at,
            "subject_id": subagent,
            "subject_status": "orphan",
        },
        now=now,
    )


def derive_orphan_record(
    orphan: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Public entry point — one orphan always yields exactly one record (no batch case)."""
    return build_orphan_record(orphan, repository_id=repository_id, now=now)
