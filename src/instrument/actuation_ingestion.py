"""Producer-side actuation derivation for the runtime-RAG knowledge base.

Canonical-state round 2 registry's ``actuation`` producer — plan step 6 of
``docs/canonical_state_r2_plan.md``, Delta 3 of ``docs/canonical_state_r2_design.md`` §5.
An ``actuation`` record is a candidate *instruction to act* on a running session (steer,
interrupt, escalate, retry, budget, deadline) — the opposite family from every other
producer in this package, which only ever describes what already happened.

READ THIS BEFORE ADDING A CALL SITE — THAT IS THE WHOLE POINT OF THIS MODULE EXISTING:
:func:`derive_actuation_record` is built and unit-tested so its schema is exercised before
anything in the running system ever calls it. The **one legitimate call site** is the
Control Room's human-gated steer/interrupt handlers (``admin/server.py``'s
``_emit_actuation_record``, review §5.4 — a POST to ``/api/flags/<sid>/steer`` or
``/interrupt`` after the human operator explicitly decided to act), and
:func:`instrument.knowledge_stream.publish_event`'s actuation gate
(``FINOPS_ACTUATION_ARMED``, the ``causes``-must-resolve-to-an-observation lineage check —
see ``knowledge_stream.py``, plan step 7, already landed) independently blocks anything
this function produces from ever reaching the durable stream unarmed. Any OTHER call site
— an automated/agent-driven caller — is legitimate only once a control rule for actuation
exists in a compiled ``ExperimentSpec`` — the same ``requires``/``produces`` gate
``compile_experiment.py`` already enforces for every other policy arm (``AGENTS.md``'s
load-bearing rule, applied to actuation with no bespoke exception).

Schema (design §5a): ``source_type="actuation"``, ``authority=POLICY``,
``evidence_class="[P]"``. ``causes`` (the :class:`~instrument.knowledge.KnowledgeRecord`
field added in plan step 1) is **required** — an actuation with no justifying observation
is rejected here, at construction time, ahead of (not instead of)
``publish_event``'s own transport-level lineage gate; two independent checks for the same
invariant, same "closed by default, checked in more than one place" posture the design
uses throughout.

Identity (design §3, ``actuation`` row): ``source_uri = f"actuation:{actuation_id}"``,
``actuation_id = hash(target_session_id | causes | occurred_at)`` — **one identity per
candidate, not per session**: repeated actuation candidates against the same session are
independent facts, never versions of each other (unlike every other producer's
same-entity-per-cell identity). ``logical_locator = actuation_id``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from .knowledge import (
    Authority,
    KnowledgeRecord,
)
from .knowledge_ingestion import REPOSITORY_ID
from .record_factory import (
    _now_iso,
)
from .record_factory import (
    build_record as build_record_from_parts,
)

# ── Extractor contract constants ────────────────────────────────

EXTRACTOR_VERSION = "actuation/v1"
SOURCE_TYPE = "actuation"
ACL_SCOPE = "public"
REVISION_FALLBACK = "actuation/unrevisioned"

#: The only recognized ``actuation_kind`` values (design §5a). Not validator-enforced here
#: (the ``causes`` requirement is the one hard construction-time check this round adds) —
#: kept as a documented reference set for a future semantic validator (design §5d: "No
#: semantic safety validator... future work, gated by the same measure-before-policy
#: ordering as every other policy arm").
ACTUATION_KINDS = frozenset({"steer", "interrupt", "escalate", "retry", "budget", "deadline"})


# ── Small deterministic helpers (mirror the other *_ingestion modules) ──────


def _actuation_id(target_session_id: str, causes: str, occurred_at: str) -> str:
    """Return a stable identity for one actuation candidate.

    Folds in ``occurred_at`` deliberately (design §3): "one identity per candidate, not
    per session" — two candidates against the same session, justified by the same
    observation, at different times are independent facts, never the same logical entity.
    """
    return hashlib.sha256(
        f"{target_session_id}|{causes}|{occurred_at}".encode("utf-8")
    ).hexdigest()[:16]


# ── Record construction ─────────────────────────────────────────


def derive_actuation_record(
    candidate: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Build an actuation :class:`KnowledgeRecord` from a candidate dict (design §5a's shape).

    ``candidate`` — ``{"actuation_kind", "target_session_id", "target_cell_id",
    "requested_action", "requested_by", "causes"}``. ``causes`` is the ``knowledge_id`` of
    the observation-family record that justifies this candidate; every other key maps
    directly into the record's rendered JSON body (design §5a — no new dataclass field,
    the envelope stays uniform).

    Raises ``ValueError`` when ``causes`` is missing or empty — construction-time
    enforcement of design §5a's "Required (validator-enforced)" clause, ahead of (not
    instead of) ``knowledge_stream.publish_event``'s own transport-level lineage gate
    (which re-checks that ``causes`` actually resolves to a real, indexed observation —
    a check this function cannot perform, since it has no store access and must stay a
    pure, unit-testable construction function).
    """
    causes = str(candidate.get("causes") or "")
    if not causes:
        raise ValueError(
            "actuation candidate has no `causes` — every actuation must cite the "
            "knowledge_id of the observation-family record that justified it"
        )

    target_session_id = str(candidate.get("target_session_id") or "")
    target_cell_id = str(candidate.get("target_cell_id") or "")
    actuation_kind = str(candidate.get("actuation_kind") or "")
    requested_action = candidate.get("requested_action") or {}
    requested_by = str(candidate.get("requested_by") or "")

    ts = _now_iso(now)
    actuation_id = _actuation_id(target_session_id, causes, ts)
    source_uri = f"actuation:{actuation_id}"

    body = {
        "actuation_kind": actuation_kind,
        "target_session_id": target_session_id,
        "target_cell_id": target_cell_id,
        "requested_action": requested_action,
        "requested_by": requested_by,
    }
    text = json.dumps(body, sort_keys=True)

    # Identity + the content-hash back-fill are the shared factory's job (record_factory).
    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=source_uri,
        logical_locator=actuation_id,
        repository_id=repository_id,
        revision=REVISION_FALLBACK,
        authority=Authority.POLICY,
        evidence_class="[P]",
        text=text,
        extra_fields={
            "commit_sha": "",
            "extractor_version": EXTRACTOR_VERSION,
            "causes": causes,
        },
        now=now,
    )
