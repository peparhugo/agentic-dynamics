"""Transport interface for the notification server.

A Transport owns everything specific to one wire protocol: accepting and
tracking client connections, and moving already-serialized message strings
to the right client(s). The core notification logic (message parsing,
channel subscriptions, the Redis/SQLite backbone) never touches a
connection object directly -- it only ever calls through this interface.
That means a new transport (SSE, long-polling, raw TCP, ...) can be added
by implementing BaseTransport, without changing any core logic.
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseTransport(ABC):
    @abstractmethod
    async def on_connect(self, *args, **kwargs) -> str:
        """Register a newly-connected client and return its client_id."""

    @abstractmethod
    async def on_disconnect(self, client_id: str, **kwargs) -> None:
        """Clean up state for a client that has disconnected."""

    @abstractmethod
    async def send_message(self, client_id: str, message: str, **kwargs) -> None:
        """Deliver one already-serialized message to a single client."""

    @abstractmethod
    async def broadcast(self, message: str, channel: Optional[str] = None, **kwargs) -> None:
        """Deliver an already-serialized message to every locally-connected
        client, or -- if channel is given -- only to that channel's
        subscribers."""
