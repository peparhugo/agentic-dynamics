"""Shared Redis contracts for human-reviewed supervisor flags.

The module contains observation metadata only. It deliberately has no OpenCode
client dependency, which prevents flag persistence and stream indexing from
crossing the observation-to-control boundary.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

SUPERVISOR_FLAGS_KEY = "supervisor_flags"
SUPERVISOR_FLAGS_MAX = 200
SUPERVISOR_SESSION_CELLS_KEY = "supervisor_session_cells"
MAPPING_STALE_SECONDS = 900
FLAG_FIELDS = ("at", "session_id", "title", "model", "status", "why")


def utc_now() -> str:
    """Return a canonical UTC timestamp suitable for lexical comparisons."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: dict[str, Any]) -> str:
    """Serialize one Redis record deterministically for hashing and replay."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def normalize_flag(value: Any) -> dict[str, Any] | None:
    """Validate a persisted flag while preserving safe additive metadata."""
    if not isinstance(value, dict):
        return None
    if any(field not in value or not isinstance(value[field], str) for field in FLAG_FIELDS):
        return None
    if not value["session_id"].strip() or not value["status"].strip():
        return None

    flag = {field: value[field] for field in FLAG_FIELDS}
    for field in ("last_activity_at", "review", "mapping"):
        if field in value:
            flag[field] = value[field]
    digest_fields = {field: flag[field] for field in FLAG_FIELDS}
    flag["flag_id"] = hashlib.sha256(canonical_json(digest_fields).encode()).hexdigest()[:16]
    return flag


def parse_mapping(value: Any) -> dict[str, str] | None:
    """Return a complete exact session-to-cell mapping or ``None``."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict):
        return None
    required = ("session_id", "cell_id", "source", "mapped_at")
    if any(not isinstance(value.get(field), str) or not value[field] for field in required):
        return None
    mapping = {field: value[field] for field in required}
    activity = value.get("last_activity_at")
    if isinstance(activity, str) and activity:
        mapping["last_activity_at"] = activity
    return mapping


def extract_session_id(event: dict[str, Any] | str, cell_id: str = "") -> str | None:
    """Extract native identity from current, part, or relayed event envelopes."""
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError:
            return None
    if not isinstance(event, dict):
        return None
    containers = [event]
    for key in ("part", "data"):
        nested = event.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
    for container in containers:
        candidate = container.get("sessionID") or container.get("session_id")
        if isinstance(candidate, str) and candidate and candidate != cell_id:
            return candidate
    return None


def _mapping_is_stale(mapping: dict[str, str], observed_at: str) -> bool:
    """Return whether an existing owner has stopped producing recent activity."""
    try:
        previous = datetime.fromisoformat(
            mapping.get("last_activity_at", mapping["mapped_at"]).replace("Z", "+00:00")
        )
        current = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return (current - previous).total_seconds() > MAPPING_STALE_SECONDS


def register_session_mapping(
    redis_client: Any,
    session_id: str,
    cell_id: str,
    *,
    source: str = "publisher_index",
    observed_at: str | None = None,
) -> dict[str, str] | None:
    """Best-effort register one exact mapping with deterministic precedence.

    Direct publishers own their streams and therefore replace relay mappings.
    Relays may refresh their own mapping but never replace a direct publisher.
    Mapping failure cannot break the primary telemetry publication path.
    """
    if not session_id or not cell_id or session_id == cell_id:
        return None
    observed_at = observed_at or utc_now()
    try:
        existing = parse_mapping(redis_client.hget(SUPERVISOR_SESSION_CELLS_KEY, session_id))
        if existing:
            direct_exists = existing["source"] == "publisher_index"
            incoming_relay = source == "supervisor_relay"
            if direct_exists and incoming_relay:
                return existing
            if (
                existing["source"] == source
                and existing["cell_id"] != cell_id
                and not _mapping_is_stale(existing, observed_at)
            ):
                # Equal-priority conflicting claims are ambiguous; retaining the
                # first exact owner is safer than selecting by thread timing.
                return existing
            mapped_at = existing["mapped_at"] if existing["cell_id"] == cell_id else observed_at
            prior_activity = existing.get("last_activity_at", "")
            observed_at = max(prior_activity, observed_at)
        else:
            mapped_at = observed_at
        mapping = {
            "session_id": session_id,
            "cell_id": cell_id,
            "source": source,
            "mapped_at": mapped_at,
            "last_activity_at": observed_at,
        }
        redis_client.hset(
            SUPERVISOR_SESSION_CELLS_KEY,
            session_id,
            canonical_json(mapping),
        )
        return mapping
    except Exception:
        return None


def register_event_mapping(
    redis_client: Any,
    cell_id: str,
    event: dict[str, Any] | str,
    *,
    source: str = "publisher_index",
) -> dict[str, str] | None:
    """Index an event when it carries both a native ID and exact cell ID."""
    session_id = extract_session_id(event, cell_id)
    if not session_id:
        return None
    return register_session_mapping(redis_client, session_id, cell_id, source=source)
