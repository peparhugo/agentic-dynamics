"""Thread-safe registry of connected WebSocket clients."""
from __future__ import annotations

import threading
from typing import Any


class ClientRegistry:
    """Maps client_id -> connection object, safe to touch from multiple threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[str, Any] = {}

    def add(self, client_id: str, connection: Any) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def connections(self) -> list[Any]:
        with self._lock:
            return list(self._clients.values())

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._clients.keys())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def __contains__(self, client_id: str) -> bool:
        with self._lock:
            return client_id in self._clients
