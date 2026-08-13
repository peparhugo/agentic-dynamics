"""Thread-safe client registry for WebSocket connections."""

import uuid
import threading
from typing import Dict, Optional, Any


class ClientRegistry:
    """Manages connected WebSocket clients with thread-safe operations."""

    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def register(self, websocket: Any) -> str:
        """Register a new client and return its unique ID."""
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def unregister(self, client_id: str) -> None:
        """Unregister a client by ID."""
        with self._lock:
            self._clients.pop(client_id, None)

    def get_client(self, client_id: str) -> Optional[Any]:
        """Get a specific client by ID."""
        with self._lock:
            return self._clients.get(client_id)

    def get_all_clients(self) -> Dict[str, Any]:
        """Get a snapshot of all connected clients."""
        with self._lock:
            return dict(self._clients)

    def get_client_count(self) -> int:
        """Get count of connected clients."""
        with self._lock:
            return len(self._clients)
