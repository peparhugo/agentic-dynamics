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
        self._lock = threading.Lock()

    def add(self, client_id: str, connection: object) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)

    def all(self) -> list[object]:
        with self._lock:
            return list(self._clients.values())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)
