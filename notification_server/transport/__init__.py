"""Pluggable transport layer for the notification server.

New transports register themselves in `TRANSPORTS` below and become
selectable via the `TRANSPORT` env var (or an explicit name passed to
`create_transport`) -- no changes to NotificationServer required.
"""

from __future__ import annotations

import os

from notification_server.transport.base import BaseTransport
from notification_server.transport.websocket import WebSocketTransport

DEFAULT_TRANSPORT = "websocket"

TRANSPORTS: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
}


def create_transport(name: str | None = None) -> BaseTransport:
    """Instantiate the transport named by `name`, falling back to the
    TRANSPORT env var and then to the WebSocket transport."""
    key = (name or os.environ.get("TRANSPORT") or DEFAULT_TRANSPORT).lower()
    try:
        transport_cls = TRANSPORTS[key]
    except KeyError:
        known = ", ".join(sorted(TRANSPORTS))
        raise ValueError(f"unknown transport {key!r} (known transports: {known})") from None
    return transport_cls()


__all__ = ["BaseTransport", "WebSocketTransport", "create_transport", "TRANSPORTS", "DEFAULT_TRANSPORT"]
