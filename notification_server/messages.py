"""JSON notification message parsing and construction.

Every message on the wire is `{type: str, payload: dict, timestamp: str}`
with `type` restricted to 'broadcast', 'direct', 'system', 'subscribe', or
'unsubscribe'. Messages may carry an optional top-level `channel: str`
field: 'subscribe'/'unsubscribe' use it to name the channel being
(un)subscribed to, and 'broadcast' uses it to scope delivery to that
channel's subscribers instead of every connected client.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

VALID_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


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

    result = {"type": msg_type, "payload": payload, "timestamp": timestamp}

    channel = data.get("channel")
    if channel is not None:
        if not isinstance(channel, str):
            raise InvalidMessage("channel must be a string")
        result["channel"] = channel

    return result


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
