"""Pluggable transport layer for the notification server.

`BaseTransport` is the seam between `NotificationServer`'s core notification
logic (dispatch, routing, persistence) and the wire protocol clients actually
speak. The core server only ever calls the four methods declared here — it
never touches a socket, an HTTP request, or any other transport-specific
API directly. Adding a new transport (SSE, long-polling, raw TCP, ...) means
writing a new `BaseTransport` subclass and registering it; `NotificationServer`
itself does not change.
"""
from __future__ import annotations

import abc
from typing import Any, Iterable


class BaseTransport(abc.ABC):
    """Base class for pluggable transports.

    `server` is the owning `NotificationServer`. Transports call back into
    it (e.g. `server._dispatch(...)`) to run core notification logic once a
    connection has been accepted and its messages decoded.
    """

    def __init__(self, server: Any) -> None:
        self.server = server

    @abc.abstractmethod
    async def on_connect(self, connection: Any) -> None:
        """Drive a newly accepted `connection` for its entire lifetime.

        Implementations are expected to register the connection with
        `self.server.registry` to obtain a client ID, hand incoming messages
        to `self.server`'s dispatch logic, and call `on_disconnect` once the
        connection closes.
        """

    @abc.abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Release any transport- and registry-level state held for `client_id`."""

    @abc.abstractmethod
    async def send_message(self, client_id: str, message: dict) -> None:
        """Deliver `message` to the single client identified by `client_id`, if still connected."""

    @abc.abstractmethod
    async def broadcast(self, message: dict, *, channel: str | None = None, exclude: Iterable[str] = ()) -> None:
        """Deliver `message` to all connected clients, or only those subscribed to `channel`, except `exclude`."""
