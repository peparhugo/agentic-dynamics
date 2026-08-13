"""Thread-safe registry of connected WebSocket clients."""
from __future__ import annotations

import threading
import uuid
from typing import Any


class ClientRegistry:
    """Maps client IDs to their WebSocket connection objects.

    Guarded by a plain threading.Lock (rather than asyncio.Lock) so the
    registry stays safe to use even if the server is ever driven from
    multiple threads/event loops, not just a single asyncio loop.
    """

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()

    def add(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def all_ids(self) -> list[str]:
        with self._lock:
            return list(self._clients.keys())

    def all_items(self) -> list[tuple[str, Any]]:
        with self._lock:
            return list(self._clients.items())

    def all_clients(self) -> list[Any]:
        with self._lock:
            return list(self._clients.values())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def __contains__(self, client_id: str) -> bool:
        with self._lock:
            return client_id in self._clients
