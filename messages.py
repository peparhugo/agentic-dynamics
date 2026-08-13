"""Message envelope helpers shared by the notification server and transports.

All messages use the JSON envelope:

    {"type": str, "payload": dict, "timestamp": str}

Supported message types: 'broadcast', 'direct', 'system', 'subscribe',
'unsubscribe'.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a message using the canonical JSON envelope."""
    return {"type": msg_type, "payload": payload, "timestamp": utc_now()}


def serialize(message: dict) -> str:
    """Serialize a message envelope to JSON text."""
    return json.dumps(message)
