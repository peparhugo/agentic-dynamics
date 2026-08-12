"""Message envelope helpers for the notification server.

Every message (inbound or outbound) is a JSON object with the shape::

    {"type": str, "payload": dict, "timestamp": str}

Supported types are ``"broadcast"``, ``"direct"`` and ``"system"``.
"""

import json
from datetime import datetime, timezone
from typing import Any

SUPPORTED_TYPES = ("broadcast", "direct", "system")


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(type_: str, payload: dict, timestamp: str | None = None) -> str:
    """Serialize a message envelope to a JSON string."""
    if type_ not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {type_!r}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    envelope: dict[str, Any] = {
        "type": type_,
        "payload": payload,
        "timestamp": timestamp or now_iso(),
    }
    return json.dumps(envelope)


def parse_message(raw: str) -> dict:
    """Parse and validate an incoming JSON message, returning its envelope."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid JSON message") from exc

    if not isinstance(data, dict):
        raise ValueError("message must be a JSON object")

    msg_type = data.get("type")
    if msg_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")

    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("message payload must be an object")

    if not isinstance(data.get("timestamp"), str):
        raise ValueError("message timestamp must be a string")

    return data
