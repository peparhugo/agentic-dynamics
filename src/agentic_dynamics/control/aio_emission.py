"""AIO permanence-decision emission (Wave-3 a5) — the AIO is observable, never a silent authority.

The AIO Control Agent (``agent_config/agents/aio-control.md``) is the controller's delegated
hands. Every permanence verb it routes — a promote request, a publish request, an approval —
flows through a *verified command* (``scripts/promote.py``, ``scripts/publish_release.py``),
and a5's contract is that the decision and the act are **emitted** at that call site: an
observation record (via :mod:`observation_ingestion`) for the decision, and — for the
permanence act itself — an actuation record (via
:func:`actuation_ingestion.derive_actuation_record`) whose ``causes`` links back to the
observation that justified it. This module is that emission seam.

This is the **first permanence-decision actuation caller**. The canonical-state round-2 audit
(pinned in ``docs/reviews/authoring_product_aio_preregistration.md``, D-2) found that
``derive_actuation_record`` already had two pre-spec call sites — the Control Room's
human-gated steer/interrupt emit (``apps/control_room/services/supervisor.py``) and the
shadow-decision recorder (``control/rules.py``) — but that **no promote/publish/approval
decision anywhere emitted an actuation record**: the AIO, the agent that routes permanence,
was itself unobservable. This module closes that residual. Every function here either *derives*
(a pure construction over the two producers, unit-testable with no store) or *publishes*
(best-effort over the knowledge stream), so the call sites stay mechanical and an emission
failure can never block the permanence act it describes.

Decision vocabulary (the dict every call site constructs)::

    {
        "verb": "promote" | "publish" | "approve",   # the permanence verb being routed
        "run_id": str,                               # the run the candidate came from
        "candidate_sha": str,                        # the tree the act targets
        "operator": str,                             # whose name the act carries
        "status": str,                               # observation status (requested/approved/...)
        "why": str,                                  # free-text reason (optional)
        "requested_action": dict,                    # actuation detail (optional)
    }

Both producers' contracts are UNCHANGED (a5's scope fence): the observation is derived through
``observation_ingestion.derive_observation_record``'s supervisor-verdict shape (``run_id`` maps
to ``cell_id``/``subject_id``, the verb+status ride in ``subject_status``, the candidate sha +
operator ride in the verdict's ``why`` text) and the actuation through
``derive_actuation_record``'s candidate shape (``causes`` is the one hard construction-time
requirement, and this module supplies it from the very observation it just derived).

Best-effort is a load-bearing property, not an afterthought: ``publish`` swallows a downed
stream and a rejected record alike (logging a warning), so the emission seam can never hold a
promotion or a release hostage. ``emit_decision`` / ``emit_act`` return the derived record(s)
regardless, so a call site that wants to log what *would* have been emitted still can.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from agentic_dynamics.control.actuation_ingestion import derive_actuation_record
from agentic_dynamics.control.observation_ingestion import derive_observation_record
from agentic_dynamics.knowledge.knowledge import KnowledgeRecord
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID

logger = logging.getLogger(__name__)

#: The permanence verbs the AIO routes. A closed set on purpose: an actuation with a typo'd
#: verb would be an untyped permanence act — worse than no record. (The actuation producer's own
#: ``ACTUATION_KINDS`` reference set is deliberately not consulted here: it documents the
#: session-steer vocabulary from canonical-state round 2 and is not validator-enforced, while a5
#: adds the permanence family — ``promote``/``publish``/``approve`` — as first-class verbs.)
PERMANENCE_VERBS = frozenset({"promote", "publish", "approve"})

#: The emitted-by marker for observation records (the ``[model]`` slot in the producer's text).
#: The AIO is the emitter; the human operator's name travels in the decision's ``operator``.
EMITTER = "aio"

#: Fallback operator name when a call site carries none (``--operator`` absent). The verified
#: commands *should* record the operator, but a missing name must never silence the emission.
DEFAULT_OPERATOR = "unknown"


def _verb(decision: dict[str, Any]) -> str:
    verb = str(decision.get("verb") or "").strip()
    if verb not in PERMANENCE_VERBS:
        raise ValueError(
            f"aio decision has unknown verb {verb!r} — expected one of "
            f"{sorted(PERMANENCE_VERBS)}"
        )
    return verb


def _run_id(decision: dict[str, Any]) -> str:
    """The decision's subject identity, with a candidate_sha fallback for store-less callers.

    The observation producer refuses an empty ``cell_id`` (a verdict with no subject cannot be
    registered), so a decision that carries no ``run_id`` falls back to a candidate-derived
    identity rather than failing the emission.
    """
    run_id = str(decision.get("run_id") or "").strip()
    if run_id:
        return run_id
    candidate_sha = str(decision.get("candidate_sha") or "").strip()
    verb = str(decision.get("verb") or "act").strip()
    return f"{verb}:{candidate_sha[:12] or 'unknown'}"


def _candidate_text(decision: dict[str, Any]) -> str:
    """The human-readable candidate/operator context folded into the observation's ``why``.

    The observation producer's extra surface is fixed (``subject_id``/``subject_status`` only —
    a5 does not change its contract), so the candidate sha and the operator name travel in the
    ``why`` text, where a reader and a test can both find them. A decision that carries no
    operator is recorded with the ``unknown`` fallback so the observation is never silent about
    whose name the act would carry.
    """
    parts = []
    candidate_sha = str(decision.get("candidate_sha") or "").strip()
    operator = str(decision.get("operator") or "").strip() or DEFAULT_OPERATOR
    if candidate_sha:
        parts.append(f"candidate {candidate_sha}")
    if operator:
        parts.append(f"operator {operator}")
    why = str(decision.get("why") or "").strip()
    if why:
        parts.append(why)
    return "; ".join(parts)


# ── Pure derivation (no store — the unit-testable half) ──────────────────────


def build_observation(
    decision: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive the ``source_type=observation`` record for ONE AIO permanence decision.

    The decision's observation is the justifying fact the later actuation cites. It is derived
    through :func:`observation_ingestion.derive_observation_record` with the producer's own
    verdict shape: ``run_id`` becomes the ``cell_id``/``subject_id`` (the record's subject is
    the run the candidate came from), ``subject_status`` is ``"<verb>:<status>"``, and the
    candidate sha + operator name ride in the ``why`` text. Raises ``ValueError`` for an
    unknown verb or an empty candidate (a permanence decision with no candidate is not one).
    """
    verb = _verb(decision)
    run_id = _run_id(decision)
    candidate_sha = str(decision.get("candidate_sha") or "").strip()
    if not candidate_sha:
        raise ValueError("aio decision has no candidate_sha — a permanence act without a "
                         "candidate tree cannot be registered")
    status = str(decision.get("status") or "requested").strip()
    detail = _candidate_text(decision)

    return derive_observation_record(
        {
            "cell_id": run_id,
            "status": f"{verb}:{status}",
            "why": detail,
            "model": EMITTER,
        },
        repository_id=repository_id,
        now=now,
    )


def build_actuation(
    decision: dict[str, Any],
    *,
    causes: str,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive the ``source_type=actuation`` record for ONE AIO permanence act.

    ``causes`` is the ``knowledge_id`` of the decision's observation record (from
    :func:`build_observation`) — the one hard construction-time requirement of
    :func:`actuation_ingestion.derive_actuation_record`, and the link that makes the AIO's
    permanence auditable ("why did the system act": the observation that justified it, resolved
    through the same lineage gate the stream enforces at publish time). The record body carries
    the verb, the run identity, and a ``requested_action`` dict naming the candidate (plus any
    call-site outcome detail, e.g. the pushed sha or the receipt id).
    """
    verb = _verb(decision)
    run_id = _run_id(decision)
    operator = str(decision.get("operator") or "").strip() or DEFAULT_OPERATOR
    requested_action = dict(decision.get("requested_action") or {})
    requested_action.setdefault("verb", verb)
    candidate_sha = str(decision.get("candidate_sha") or "").strip()
    if candidate_sha:
        requested_action.setdefault("candidate_sha", candidate_sha)

    return derive_actuation_record(
        {
            "actuation_kind": verb,
            "target_session_id": run_id,
            "target_cell_id": run_id,
            "requested_action": requested_action,
            "requested_by": operator,
            "causes": causes,
        },
        repository_id=repository_id,
        now=now,
    )


# ── Best-effort publication (the swallow-everything half) ────────────────────


def publish(
    records: list[KnowledgeRecord],
    *,
    connect_fn: Callable[..., Any] | None = None,
) -> list[str]:
    """Publish derived records onto the knowledge stream, BEST-EFFORT.

    Every record is published with ``authorized=True`` (the verified command IS the authorized
    writer — the permanence act it describes is operator-signed) and ``armed=True`` (actuation
    records describing real, executed permanence acts are the deliberate actuation surface; the
    flag is inert for observation-family records). Passing ``source_type=record.source_type``
    lets ``publish_event`` route each record through the correct gate and index the observation
    so a later actuation's ``causes`` resolves (the lineage check reads that index).

    A downed stream or a rejected record is logged and skipped, NEVER raised: a failed emit is
    a warning, never a blocked promotion (a5). Returns the entry ids ``publish_event`` accepted,
    in input order — a caller can compare the length against ``len(records)`` to know what did
    not land.
    """
    from agentic_dynamics.knowledge import knowledge_stream as ks
    from agentic_dynamics.knowledge.knowledge_ingestion import record_to_event

    connect = connect_fn or ks.connect
    try:
        r = connect()
    except Exception as exc:  # noqa: BLE001 - best-effort by contract
        logger.warning(
            "aio emission: knowledge stream unreachable (%s: %s) — %d record(s) not "
            "published; proceeding (best-effort, never a blocked permanence act)",
            type(exc).__name__, exc, len(records),
        )
        return []

    entry_ids: list[str] = []
    for record in records:
        try:
            entry_ids.append(
                ks.publish_event(
                    r,
                    record_to_event(record),
                    authorized=True,
                    armed=True,
                    source_type=record.source_type,
                )
            )
        except Exception as exc:  # noqa: BLE001 - best-effort by contract
            logger.warning(
                "aio emission: publish failed for %s (%s: %s); proceeding (best-effort)",
                record.knowledge_id, type(exc).__name__, exc,
            )
    return entry_ids


# ── The call-site API ────────────────────────────────────────────────────────


def emit_decision(
    decision: dict[str, Any],
    *,
    connect_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Build + best-effort publish the observation of ONE AIO permanence decision.

    Returns ``{"observation": KnowledgeRecord, "entry_ids": [...]}``. The observation is
    returned even when publication failed (empty ``entry_ids``), so the call site can cite its
    ``knowledge_id`` as the actuation's ``causes`` regardless of the stream's health.
    """
    observation = build_observation(decision)
    entry_ids = publish([observation], connect_fn=connect_fn)
    return {"observation": observation, "entry_ids": entry_ids}


def emit_act(
    decision: dict[str, Any],
    *,
    causes: str,
    connect_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Build + best-effort publish the actuation of ONE AIO permanence act.

    ``causes`` is the ``knowledge_id`` of the observation that justified the act (the value
    ``emit_decision`` returned). Returns ``{"actuation": KnowledgeRecord, "entry_ids": [...]}``.
    """
    actuation = build_actuation(decision, causes=causes)
    entry_ids = publish([actuation], connect_fn=connect_fn)
    return {"actuation": actuation, "entry_ids": entry_ids}
