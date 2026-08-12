"""Message envelope helpers for the notification server.

Every message (inbound or outbound) is a JSON object with the shape::

    {"type": str, "payload": dict, "timestamp": str}

An optional ``"channel"`` field may be attached to route channel messages::

    {"type": str, "payload": dict, "timestamp": str, "channel": str}

Supported types are ``"broadcast"``, ``"direct"``, ``"system"``,
``"subscribe"`` and ``"unsubscribe"``.
"""

import json
from datetime import datetime, timezone
from typing import Any

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(
    type_: str,
    payload: dict,
    timestamp: str | None = None,
    channel: str | None = None,
) -> str:
    """Serialize a message envelope to a JSON string."""
    if type_ not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {type_!r}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    if channel is not None:
        if not isinstance(channel, str) or not channel:
            raise ValueError("channel must be a non-empty string")
    envelope: dict[str, Any] = {
        "type": type_,
        "payload": payload,
        "timestamp": timestamp or now_iso(),
    }
    if channel is not None:
        envelope["channel"] = channel
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

    channel = data.get("channel")
    if channel is not None and (not isinstance(channel, str) or not channel):
        raise ValueError("message channel must be a non-empty string")

    return data
