"""Thread-safe registry of connected WebSocket clients.

Maps a unique ``client_id`` to the client's WebSocket connection object.

The asyncio event loop runs on a single thread by default, so in the common
case all registry access happens inside that loop and no locking would be
required. However, asyncio may occasionally dispatch callbacks on worker
threads, so every operation is still guarded by a :class:`threading.Lock`.
"""

import threading
from typing import List, Optional, Tuple


class ClientRegistry:
    """Holds ``client_id -> websocket`` mappings under a single lock."""

    def __init__(self):
        self._clients = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, websocket) -> None:
        """Register ``websocket`` under ``client_id``."""
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> bool:
        """Remove ``client_id``; return True if it was present."""
        with self._lock:
            return self._clients.pop(client_id, None) is not None

    def get(self, client_id: str):
        """Return the connection for ``client_id`` or None."""
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        """Return the number of connected clients."""
        with self._lock:
            return len(self._clients)

    def ids(self) -> List[str]:
        """Return a snapshot of all registered client ids."""
        with self._lock:
            return list(self._clients.keys())

    def connections(self) -> list:
        """Return a snapshot of all registered connections."""
        with self._lock:
            return list(self._clients.values())

    def items(self) -> List[Tuple[str, object]]:
        """Return a snapshot of ``(client_id, websocket)`` pairs."""
        with self._lock:
            return list(self._clients.items())
