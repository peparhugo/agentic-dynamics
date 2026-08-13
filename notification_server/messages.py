"""JSON message envelope shared by every message on the wire.

Every message is: {"type": str, "payload": dict, "timestamp": str}
"""

import json
from datetime import datetime, timezone

SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict) -> dict:
    if msg_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {msg_type}")
    return {"type": msg_type, "payload": payload, "timestamp": now_iso()}


def encode(message: dict) -> str:
    return json.dumps(message)


class MessageError(Exception):
    pass


def parse_client_message(raw: str) -> dict:
    """Parse and validate a raw client message. Raises MessageError on failure."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MessageError("invalid_json") from exc

    if not isinstance(data, dict):
        raise MessageError("message must be a JSON object")

    msg_type = data.get("type")
    if msg_type not in SUPPORTED_TYPES:
        raise MessageError(f"unsupported type: {msg_type!r}")

    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise MessageError("payload must be an object")

    return {"type": msg_type, "payload": payload}
