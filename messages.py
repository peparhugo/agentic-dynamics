"""Shared message-envelope helpers for the notification server.

Kept separate from notification_server.py and transport.py so both can
import it without creating a circular dependency between the core server
and the pluggable transport layer.
"""

from __future__ import annotations

from datetime import datetime, timezone

MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict, channel: str | None = None) -> dict:
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    message = {"type": msg_type, "payload": payload, "timestamp": utc_timestamp()}
    if channel is not None:
        message["channel"] = channel
    return message
