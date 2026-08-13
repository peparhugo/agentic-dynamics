"""Pluggable transport interface for the notification server.

`NotificationServer` (in `ws_server.py`) implements message routing —
broadcast, direct, subscribe/unsubscribe — entirely in terms of this
interface. It never imports a specific network library or touches a raw
connection object directly; it only calls `BaseTransport` methods and
iterates `receive()`. That's what lets a new transport (SSE, long-polling,
raw TCP, ...) be added by writing one `BaseTransport` subclass, with zero
changes to the routing logic.

A "connection" is an opaque object as far as the core server and this
interface are concerned — the registry stores whatever a transport hands it
in `serve()`'s handler callback, and passes it back to `send_message` /
`broadcast` / `receive` unchanged. Only the concrete transport subclass
knows what it actually is (a `websockets` connection, an SSE response
stream, a raw socket, ...).
"""
from __future__ import annotations

import abc
from typing import Any, AsyncIterator, Awaitable, Callable

ConnectionHandler = Callable[[Any], Awaitable[None]]


class BaseTransport(abc.ABC):
    """Base class for pluggable notification-server transports."""

    @abc.abstractmethod
    async def on_connect(self, connection: Any) -> None:
        """Run transport-specific setup right after a connection is accepted."""

    @abc.abstractmethod
    async def on_disconnect(self, connection: Any) -> None:
        """Run transport-specific teardown once a connection goes away."""

    @abc.abstractmethod
    async def send_message(self, connection: Any, message: dict) -> None:
        """Send a single JSON-serializable message to one connection.

        Must swallow errors caused by the connection already being closed —
        callers treat a send to a dead connection as a no-op, not a failure.
        """

    @abc.abstractmethod
    async def broadcast(self, connections: list, message: dict) -> None:
        """Send a message to many connections concurrently."""

    @abc.abstractmethod
    def receive(self, connection: Any) -> AsyncIterator[str]:
        """Yield raw messages received on `connection` until it closes."""

    @abc.abstractmethod
    def serve(self, handler: ConnectionHandler, host: str, port: int):
        """Start listening for connections, invoking `handler(connection)` per connection.

        Returns whatever the underlying transport's server-lifecycle object
        is (started/stopped via `await`, async-context-manager, `.close()`
        + `.wait_closed()`, or similar) — `NotificationServer.serve()`
        passes this straight through to its caller.
        """
