"""Message schema and validation for the notification server."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

VALID_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


class MessageValidationError(ValueError):
    """Raised when an incoming message does not match the expected schema."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Message:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)
    channel: str | None = None

    @classmethod
    def from_json(cls, raw: str) -> "Message":
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise MessageValidationError(f"invalid JSON: {exc}") from exc
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Any) -> "Message":
        if not isinstance(data, dict):
            raise MessageValidationError("message must be a JSON object")

        msg_type = data.get("type")
        if msg_type not in VALID_TYPES:
            raise MessageValidationError(
                f"'type' must be one of {sorted(VALID_TYPES)}, got {msg_type!r}"
            )

        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            raise MessageValidationError("'payload' must be an object")

        timestamp = data.get("timestamp") or utc_now_iso()
        if not isinstance(timestamp, str):
            raise MessageValidationError("'timestamp' must be a string")

        channel = data.get("channel")
        if channel is not None and not isinstance(channel, str):
            raise MessageValidationError("'channel' must be a string")

        return cls(type=msg_type, payload=payload, timestamp=timestamp, channel=channel)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type, "payload": self.payload, "timestamp": self.timestamp}
        if self.channel is not None:
            data["channel"] = self.channel
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
