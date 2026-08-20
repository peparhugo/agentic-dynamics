"""Supervisor-flag service — read, review, authorize, and actuate retained flags.

Extracted from ``server.py`` (refactor-repair Debt-1). The flag read/authorize/actuation logic
lives here as pure-ish functions that access the shared server context (Redis, the flags file,
the clock) through ``server.*`` so a test's monkeypatch of ``server._redis`` / ``server.
SUPERVISOR_FLAGS_FILE`` keeps working unchanged.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Response, jsonify

from agentic_dynamics.control.supervisor import (
    SUPERVISOR_FLAGS_KEY,
    SUPERVISOR_FLAGS_MAX,
    SUPERVISOR_SESSION_CELLS_KEY,
    normalize_flag,
    parse_mapping,
)
from apps.control_room import server


def _read_flag_tail(path: Path) -> tuple[list[str] | None, str | None]:
    """Read a bounded newest-first tail from the append-only JSONL audit file."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - server.SUPERVISOR_FILE_TAIL_BYTES)
            handle.seek(start)
            raw = handle.read(server.SUPERVISOR_FILE_TAIL_BYTES)
    except FileNotFoundError:
        return None, "supervisor flag fallback file is not present"
    except OSError as error:
        return None, f"supervisor flag fallback is unreadable: {error}"

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if start > 0 and lines:
        # The first item may begin in the middle of a JSON record.
        lines = lines[1:]
    return list(reversed(lines[-SUPERVISOR_FLAGS_MAX:])), None

def _mapping_is_stale(mapping: dict[str, str]) -> bool:
    """Return whether an exact mapping has exceeded the active window."""
    activity = mapping.get("last_activity_at")
    if not activity:
        return False
    try:
        observed = datetime.fromisoformat(activity.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - observed).total_seconds() > server.SUPERVISOR_ACTIVE_WINDOW_SECONDS

def _review_for_flag(redis_client, flag: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    """Resolve current exact mapping first, then an immutable flag snapshot."""
    current = None
    if redis_client is not None:
        try:
            current = parse_mapping(
                redis_client.hget(SUPERVISOR_SESSION_CELLS_KEY, flag["session_id"])
            )
        except Exception as error:
            warnings.append(f"session mapping unavailable: {error}")

    if current and current["session_id"] == flag["session_id"]:
        return {
            "state": "stale" if _mapping_is_stale(current) else "mapped",
            "cell_id": current["cell_id"],
            "source": current["source"],
            "mapped_at": current["mapped_at"],
            "last_activity_at": current.get("last_activity_at"),
        }

    snapshot = parse_mapping(flag.get("review")) or parse_mapping(flag.get("mapping"))
    if snapshot and snapshot["session_id"] != flag["session_id"]:
        snapshot = None
    if snapshot:
        return {
            "state": "snapshot",
            "cell_id": snapshot["cell_id"],
            "source": snapshot["source"],
            "mapped_at": snapshot["mapped_at"],
            "last_activity_at": snapshot.get("last_activity_at"),
        }
    return {"state": "unavailable", "cell_id": None, "source": None, "mapped_at": None}

def _load_supervisor_flags(limit: int) -> tuple[dict[str, Any], int]:
    """Load, validate, deduplicate, and enrich retained supervisor flags."""
    warnings: list[str] = []
    redis_client = None
    redis_readable = False
    file_readable = False
    raw_records: list[str] = []
    source = "none"
    try:
        redis_client = server._redis()
        raw_records = redis_client.lrange(SUPERVISOR_FLAGS_KEY, 0, SUPERVISOR_FLAGS_MAX - 1)
        redis_readable = True
        if raw_records:
            source = "redis"
    except Exception as error:
        warnings.append(f"supervisor Redis unavailable: {error}")

    if not raw_records:
        file_records, file_warning = _read_flag_tail(server.SUPERVISOR_FLAGS_FILE)
        if file_records is not None:
            file_readable = True
            raw_records = file_records
            if raw_records or not redis_readable:
                source = "file"
        elif file_warning:
            warnings.append(file_warning)

    flags: list[dict[str, Any]] = []
    seen_sessions: set[str] = set()
    malformed = 0
    for raw in raw_records:
        try:
            decoded = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            malformed += 1
            continue
        flag = normalize_flag(decoded)
        if flag is None:
            malformed += 1
            continue
        if flag["session_id"] in seen_sessions:
            continue
        seen_sessions.add(flag["session_id"])
        review = _review_for_flag(redis_client, flag, warnings)
        flag["review"] = {key: value for key, value in review.items() if key != "last_activity_at"}
        flag["last_activity_at"] = review.get("last_activity_at") or flag.get("last_activity_at")
        flags.append(flag)
        if len(flags) >= limit:
            break
    if malformed:
        warnings.append(f"skipped {malformed} malformed supervisor flag record(s)")

    if source == "file":
        degraded = True
    elif source == "redis":
        degraded = False
    else:
        degraded = not redis_readable
    unavailable = not redis_readable and not file_readable
    envelope = {
        "generated_at": server._utc_now(),
        "source": source,
        "degraded": degraded,
        "warnings": list(dict.fromkeys(warnings)),
        "flags": flags,
    }
    return envelope, 503 if unavailable else 200

def _authorize_supervisor_action(
    session_id: str,
    cell_id: str,
) -> tuple[dict[str, Any] | None, tuple[Response, int] | None]:
    """Revalidate retained ownership and exact stream mapping at side-effect time."""
    envelope, status = _load_supervisor_flags(SUPERVISOR_FLAGS_MAX)
    if status == 503:
        return None, (jsonify({"error": "supervisor control state unavailable"}), 503)
    flag = next((item for item in envelope["flags"] if item["session_id"] == session_id), None)
    if flag is None:
        return None, (jsonify({"error": "retained supervisor flag not found"}), 404)
    review = flag.get("review") or {}
    mapped_cell = review.get("cell_id")
    if review.get("state") == "unavailable" or not mapped_cell:
        return None, (jsonify({"error": "supervisor session mapping not found"}), 404)
    if cell_id != mapped_cell:
        return None, (jsonify({"error": "supervisor session mapping changed"}), 409)
    return flag, None

def _emit_actuation_record(
    flag: dict[str, Any],
    *,
    actuation_kind: str,
    target_cell_id: str,
    requested_action: dict[str, Any] | None = None,
) -> None:
    """Best-effort emit one actuation record justifying a human intervention.

    This is the first (and, so far, only) actuation call site — the Control Room's
    steer/interrupt handlers (review §5.4). It runs AFTER the side effect already
    succeeded and is deliberately best-effort: a KB-plane outage (the DB-2 change
    stream) must never block the steer/interrupt that already happened, so every
    failure is swallowed. ``causes`` is the ``knowledge_id`` of the flag's
    observation-family record (derived via ``observation_ingestion``), so the
    registry's one-hop "why did the system act" lookup resolves end-to-end.
    """
    try:
        from agentic_dynamics.control.actuation_ingestion import derive_actuation_record
        from agentic_dynamics.control.observation_ingestion import derive_flag_record
        from agentic_dynamics.knowledge import knowledge_stream as ks
        from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID, record_to_event

        # The flag is the justifying observation: derive its canonical knowledge_id
        # so ``causes`` points at the exact record ``supervise.py`` emitted for it.
        flag_record = derive_flag_record(flag, repository_id=REPOSITORY_ID)
        record = derive_actuation_record(
            {
                "actuation_kind": actuation_kind,
                "target_session_id": str(flag.get("session_id") or ""),
                "target_cell_id": target_cell_id,
                "requested_action": requested_action or {},
                "requested_by": "control_room",
                "causes": flag_record.knowledge_id,
            },
            repository_id=REPOSITORY_ID,
        )
        redis_client = ks.connect()
        # ``authorized=True`` (the human POST is the write authorization) and
        # ``armed=True`` (this is the deliberate human actuation surface) are passed
        # as explicit keyword args rather than mutating the FINOPS_* env flags —
        # env mutation would race across Flask's threaded request handlers.
        ks.publish_event(
            redis_client,
            record_to_event(record),
            authorized=True,
            armed=True,
            source_type=record.source_type,
        )
    except Exception:
        # Best-effort: a KB outage must never block the steer/interrupt.
        pass
