"""Thread-safe registry of connected WebSocket clients."""

import itertools
import threading
from typing import Iterator

from websockets.asyncio.server import ServerConnection


class ClientRegistry:
    """Maps unique client IDs to live WebSocket connections.

    Also tracks which channels each client is subscribed to. Channels are
    named strings (e.g. ``"alerts"``, ``"system"``, ``"chat"``) and a client
    may be subscribed to any number of them at once.

    All access is guarded by a ``threading.Lock`` so the registry can be read
    and written from the asyncio event loop as well as from other threads
    (for example a blocking HTTP health check).
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def register(self, connection: ServerConnection) -> str:
        """Store a connection and return its newly assigned unique ID."""
        client_id = f"client-{next(self._ids)}"
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def unregister(self, client_id: str) -> None:
        """Remove a client by ID; a missing ID is a no-op.

        The client is also dropped from every channel it subscribed to.
        """
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                members = self._channels[channel]
                members.discard(client_id)
                if not members:
                    del self._channels[channel]

    def get(self, client_id: str) -> ServerConnection | None:
        """Return the connection for a client ID, or ``None`` if absent."""
        with self._lock:
            return self._clients.get(client_id)

    def subscribe(self, client_id: str, channel: str) -> None:
        """Add ``client_id`` to the named channel (creating it if needed)."""
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Remove ``client_id`` from the named channel (a no-op if absent)."""
        with self._lock:
            members = self._channels.get(channel)
            if members is None:
                return
            members.discard(client_id)
            if not members:
                del self._channels[channel]

    def channel_members(self, channel: str) -> set[str]:
        """Return a snapshot of the subscriber IDs for a channel."""
        with self._lock:
            return set(self._channels.get(channel, set()))

    def subscriber_count(self, channel: str) -> int:
        """Return the number of subscribers of a channel."""
        with self._lock:
            return len(self._channels.get(channel, set()))

    def channels(self) -> dict[str, int]:
        """Return a mapping of active channel names to subscriber counts."""
        with self._lock:
            return {name: len(members) for name, members in self._channels.items()}

    def is_subscribed(self, client_id: str, channel: str) -> bool:
        """Return whether ``client_id`` is subscribed to ``channel``."""
        with self._lock:
            return client_id in self._channels.get(channel, set())

    def __iter__(self) -> Iterator[tuple[str, ServerConnection]]:
        """Snapshot iteration over (client_id, connection) pairs."""
        with self._lock:
            return iter(list(self._clients.items()))

    def __len__(self) -> int:
        """Return the number of connected clients."""
        with self._lock:
            return len(self._clients)

    def __contains__(self, client_id: str) -> bool:
        with self._lock:
            return client_id in self._clients
