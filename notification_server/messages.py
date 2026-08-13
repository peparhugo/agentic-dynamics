"""JSON notification message parsing and construction.

Every message on the wire is `{type: str, payload: dict, timestamp: str}`
with `type` restricted to 'broadcast', 'direct', or 'system'.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

VALID_TYPES = {"broadcast", "direct", "system"}


class InvalidMessage(ValueError):
    """Raised when a client sends something that doesn't match the message format."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_message(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidMessage(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise InvalidMessage("message must be a JSON object")

    msg_type = data.get("type")
    if msg_type not in VALID_TYPES:
        raise InvalidMessage(
            f"unsupported type {msg_type!r}; expected one of {sorted(VALID_TYPES)}"
        )

    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise InvalidMessage("payload must be an object")

    timestamp = data.get("timestamp") or now_iso()
    if not isinstance(timestamp, str):
        raise InvalidMessage("timestamp must be a string")

    return {"type": msg_type, "payload": payload, "timestamp": timestamp}


def make_message(msg_type: str, payload: dict[str, Any], **extra: Any) -> dict[str, Any]:
    if msg_type not in VALID_TYPES:
        raise InvalidMessage(f"unsupported type {msg_type!r}")
    message: dict[str, Any] = {"type": msg_type, "payload": payload, "timestamp": now_iso()}
    message.update(extra)
    return message


def error_message(text: str) -> dict[str, Any]:
    return make_message("system", {"event": "error", "message": text})


def dumps(message: dict[str, Any]) -> str:
    return json.dumps(message)
