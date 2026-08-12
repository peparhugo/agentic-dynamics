"""Thread-safe registry of connected WebSocket clients."""

import itertools
import threading
from typing import Iterator

from websockets.asyncio.server import ServerConnection


class ClientRegistry:
    """Maps unique client IDs to live WebSocket connections.

    All access is guarded by a ``threading.Lock`` so the registry can be read
    and written from the asyncio event loop as well as from other threads
    (for example a blocking HTTP health check).
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def register(self, connection: ServerConnection) -> str:
        """Store a connection and return its newly assigned unique ID."""
        client_id = f"client-{next(self._ids)}"
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def unregister(self, client_id: str) -> None:
        """Remove a client by ID; a missing ID is a no-op."""
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        """Return the connection for a client ID, or ``None`` if absent."""
        with self._lock:
            return self._clients.get(client_id)

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
