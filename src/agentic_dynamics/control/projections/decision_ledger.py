"""P11 ``decision_ledger`` — recorded decisions + P0 acts missing their record (d3 §5 P11).

The room's audit surface for consequential decisions: what was decided, when, by whom, and the
artifact that carries the record. Two recorded planes feed it, and neither is re-derived:

* **decision records** — the durable org-root artifacts the decision-record mechanism writes
  (``knowledge/decision_ingestion``, ``scripts/decision_record.py``): the ``cap_raise`` record a
  cap change writes at the moment of the act (G-26) and the ``one_way_door`` record an
  architecture choice writes (G-10). Read through ``scan_decision_records`` — the same read seam
  the record command's DONE_WHEN rests on, never the registry projection (which needs a live
  consumer).
* **P0 acts** — ``approvals`` (a human decision carrying its own ``decision_json`` half) and
  ``promotions`` (the permanence gate's record; the promote command pairs it with a ``promote``
  decision record). An act whose decision half is absent is reported in ``missing`` — the ledger
  never assumes a record exists because an act exists.

The builder is pure given its inputs (the injected control-DB handle + the pre-loaded record
triples) and ``now`` is injected; every list has a fixed deterministic order (newest first, then
category/artifact). Nothing here writes to the control DB, Redis, or the KB.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "decision-ledger/v1"

#: The category the promote command files its decision records under (``scripts/promote.py``) —
#: the ledger uses it to pair a ``promotions`` row with its recorded decision half.
PROMOTE_CATEGORY = "promote"

#: The source discriminator on every row: which recorded plane answered it.
SOURCE_DECISION_RECORD = "decision_record"
SOURCE_APPROVALS = "control_db.approvals"
SOURCE_PROMOTIONS = "control_db.promotions"


def load_decision_records(
    *,
    artifact_dir: Path | None = None,
    repository_id: str | None = None,
) -> tuple[list[tuple[Path, dict[str, Any], dict[str, Any]]], list[str]]:
    """Load every durable decision-record triple ``(path, artifact, payload)`` + anomalies.

    A thin delegate to the decision-ingestion read seam (``scan_decision_records``), so the room
    and the record command read the same artifacts with the same classifier. Unfiltered on
    purpose: the builder applies the category filter AFTER the promotion cross-check, which needs
    the ``promote`` records even when the caller asks for another category. Anomalies (a
    ``decision/v1`` artifact that is not a readable org-root record) come back as ``warnings``.
    """
    from agentic_dynamics.knowledge import decision_ingestion as di

    kwargs: dict[str, Any] = {"artifact_dir": artifact_dir}
    if repository_id is not None:
        kwargs["repository_id"] = repository_id
    return di.scan_decision_records(**kwargs)


def _decision_row(
    path: Path,
    artifact: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """One recorded decision-record row, straight from the record's own fields.

    The durable artifact blanks its derived ``knowledge_id`` (``record_to_artifact`` makes the
    bytes a pure function of the stable content); the write seam's pointer contract names the
    file ``<knowledge_id>.json``, so the filename stem IS the identity the artifact carries.
    """
    return {
        "category": str(payload.get("category") or ""),
        "decided_at": str(payload.get("decided_at") or ""),
        "actor": str(payload.get("actor") or ""),
        "artifact": str(path),
        "run_id": str(payload.get("run_id") or "") or None,
        "candidate_sha": str(payload.get("candidate_sha") or "") or None,
        "what": str(payload.get("what") or ""),
        "knowledge_id": str(artifact.get("knowledge_id") or "") or path.stem,
        "source": SOURCE_DECISION_RECORD,
    }


def _approval_row(approval: Any, decision: dict[str, Any]) -> dict[str, Any]:
    """One recorded approval row: the human act as the approval table recorded it."""
    purpose = str(decision.get("purpose") or getattr(approval, "purpose", "") or "")
    return {
        "category": purpose or "approval",
        "decided_at": str(getattr(approval, "decided_at", "") or ""),
        "actor": str(getattr(approval, "operator", "") or ""),
        "artifact": str(getattr(approval, "artifact_path", "") or ""),
        "run_id": str(getattr(approval, "run_id", "") or "") or None,
        "candidate_sha": str(getattr(approval, "candidate_sha", "") or "") or None,
        "what": f"approve {purpose}" if purpose else "approval",
        "knowledge_id": "",
        "source": SOURCE_APPROVALS,
    }


def _missing_row(
    *,
    category: str,
    decided_at: str,
    actor: str,
    artifact: str,
    run_id: str | None,
    candidate_sha: str | None,
    reason: str,
    source: str,
) -> dict[str, Any]:
    """One P0 act whose decision record is ABSENT — named, never assumed present."""
    return {
        "category": category,
        "decided_at": decided_at,
        "actor": actor,
        "artifact": artifact,
        "run_id": run_id or None,
        "candidate_sha": candidate_sha or None,
        "reason": reason,
        "source": source,
    }


def _order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Newest first; ties broken by category then artifact so the order is byte-stable."""
    return sorted(
        rows,
        key=lambda row: (row.get("decided_at") or "", row.get("category") or "",
                         row.get("artifact") or "", row.get("reason") or ""),
        reverse=True,
    )


def build_decision_ledger(
    db: Any | None,
    records: list[tuple[Path, dict[str, Any], dict[str, Any]]],
    *,
    category: str | None = None,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the decision-ledger payload. Pure given ``db``'s records + the injected record triples.

    ``db`` is the READ-ONLY control database handle (or ``None`` when the plane is unreachable —
    the caller names that in ``degraded``). ``category`` is an exact-match filter applied after
    the promotion cross-check (categories are open by design; an unknown category yields an
    honest empty, never an error).
    """
    decisions: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for triple in records:
        if not isinstance(triple, tuple) or len(triple) != 3:
            continue
        path, artifact, payload = triple
        if not isinstance(payload, dict):
            continue
        decisions.append(
            _decision_row(path, artifact if isinstance(artifact, dict) else {}, payload)
        )

    approvals = list(db.approvals()) if db is not None else []
    promotions = list(db.promotions()) if db is not None else []
    control_epoch = db.control_epoch() if db is not None else None

    for approval in approvals:
        raw = str(getattr(approval, "decision_json", "") or "").strip()
        decision: dict[str, Any] | None = None
        if raw:
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                decision = parsed
        if decision is not None:
            decisions.append(_approval_row(approval, decision))
        else:
            missing.append(
                _missing_row(
                    category=str(getattr(approval, "purpose", "") or "") or "approval",
                    decided_at=str(getattr(approval, "decided_at", "") or ""),
                    actor=str(getattr(approval, "operator", "") or ""),
                    artifact=str(getattr(approval, "artifact_path", "") or ""),
                    run_id=str(getattr(approval, "run_id", "") or ""),
                    candidate_sha=str(getattr(approval, "candidate_sha", "") or ""),
                    reason=(
                        "approval decision record is unreadable"
                        if raw
                        else "no decision record for this approval"
                    ),
                    source=SOURCE_APPROVALS,
                )
            )

    recorded_promotions = {
        (str(row.get("run_id") or ""), str(row.get("candidate_sha") or ""))
        for row in decisions
        if row.get("category") == PROMOTE_CATEGORY
    }
    for promotion in promotions:
        run_id = str(getattr(promotion, "run_id", "") or "")
        candidate_sha = str(getattr(promotion, "candidate_sha", "") or "")
        if (run_id, candidate_sha) in recorded_promotions:
            continue
        missing.append(
            _missing_row(
                category=PROMOTE_CATEGORY,
                decided_at=str(getattr(promotion, "pushed_at", "") or ""),
                actor=str(getattr(promotion, "by", "") or ""),
                artifact="",
                run_id=run_id,
                candidate_sha=candidate_sha,
                reason="no promote decision record for this promotion",
                source=SOURCE_PROMOTIONS,
            )
        )

    if category is not None:
        decisions = [row for row in decisions if row.get("category") == category]
        missing = [row for row in missing if row.get("category") == category]

    decisions = _order(decisions)
    missing = _order(missing)

    return {
        "schema": SCHEMA,
        "generated_at": now,
        "control_epoch": control_epoch,
        "category": category,
        "source": dict(source or {}),
        "counts": {"decisions": len(decisions), "missing": len(missing)},
        "decisions": decisions,
        "missing": missing,
        "degraded": [],
    }
