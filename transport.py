"""
Pluggable transport layer for the notification server.

This module re-exports the transport primitives that live in
``notification_server`` so transports can be imported from a single
dedicated location:

    from transport import BaseTransport, WebSocketTransport, get_transport

To add a new transport mechanism (SSE, polling, raw TCP, ...) implement
:class:`BaseTransport` and register the class in ``TRANSPORTS`` via
``get_transport``; the core notification logic needs no changes.
"""

from notification_server import (
    BaseTransport,
    TRANSPORTS,
    TransportConnectionClosed,
    TransportError,
    WebSocketTransport,
    get_transport,
)

__all__ = [
    "BaseTransport",
    "TRANSPORTS",
    "TransportConnectionClosed",
    "TransportError",
    "WebSocketTransport",
    "get_transport",
]
