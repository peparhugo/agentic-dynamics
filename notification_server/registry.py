"""Thread-safe registry of connected WebSocket clients."""

from __future__ import annotations

import threading


class ClientRegistry:
    """Tracks connected clients by their unique client ID.

    Guarded by a plain threading.Lock (rather than an asyncio.Lock) so that
    the registry is safe to read/write from any thread, not just the
    asyncio event loop thread the WebSocket server runs on.
    """

    def __init__(self) -> None:
        self._clients: dict[str, object] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, connection: object) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._subscriptions.keys()):
                self._subscriptions[channel].discard(client_id)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]

    def get(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)

    def all(self) -> list[object]:
        with self._lock:
            return list(self._clients.values())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    # -- channel subscriptions ---------------------------------------

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._subscriptions[channel]

    def channels(self) -> dict[str, int]:
        """Active channel names mapped to their subscriber counts."""
        with self._lock:
            return {channel: len(ids) for channel, ids in self._subscriptions.items()}

    def subscribers(self, channel: str) -> list[str]:
        """Client IDs subscribed to `channel` (empty list if none/unknown)."""
        with self._lock:
            return sorted(self._subscriptions.get(channel, set()))

    def connections_for_channel(self, channel: str) -> list[object]:
        with self._lock:
            ids = self._subscriptions.get(channel, set())
            return [self._clients[cid] for cid in ids if cid in self._clients]
