"""Transport selection.

The transport used by NotificationServer is chosen by the TRANSPORT
environment variable (defaults to "websocket"). Add new mechanisms (SSE,
long-polling, raw TCP, ...) by implementing BaseTransport and registering
them in TRANSPORTS — the core notification logic never needs to change.
"""

import os

from .base import BaseTransport
from .websocket_transport import WebSocketTransport

TRANSPORTS = {
    "websocket": WebSocketTransport,
}


def create_transport(name=None) -> BaseTransport:
    name = (name or os.environ.get("TRANSPORT") or "websocket").lower()
    try:
        transport_cls = TRANSPORTS[name]
    except KeyError:
        raise ValueError(
            f"unknown transport: {name!r} (available: {', '.join(sorted(TRANSPORTS))})"
        ) from None
    return transport_cls()


__all__ = ["BaseTransport", "WebSocketTransport", "create_transport", "TRANSPORTS"]
