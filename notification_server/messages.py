"""Message schema helpers for the notification server.

All wire messages are JSON objects: {type: str, payload: dict, timestamp: str}.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

VALID_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


class InvalidMessage(ValueError):
    """Raised when a client sends a malformed or unsupported message."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict[str, Any], timestamp: str | None = None) -> dict:
    if msg_type not in VALID_TYPES:
        raise InvalidMessage(f"unsupported type: {msg_type!r}")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": timestamp or now_iso(),
    }


def encode(message: dict) -> str:
    return json.dumps(message)


def parse_message(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidMessage("message is not valid JSON") from exc

    if not isinstance(data, dict):
        raise InvalidMessage("message must be a JSON object")

    msg_type = data.get("type")
    payload = data.get("payload")
    timestamp = data.get("timestamp")

    if msg_type not in VALID_TYPES:
        raise InvalidMessage(f"unsupported type: {msg_type!r}")
    if not isinstance(payload, dict):
        raise InvalidMessage("payload must be an object")
    if not isinstance(timestamp, str):
        raise InvalidMessage("timestamp must be a string")

    return {"type": msg_type, "payload": payload, "timestamp": timestamp}
