"""Thread-safe client registry for WebSocket connections."""

import uuid
import threading
from typing import Dict, Optional, Any


class ClientRegistry:
    """Manages connected WebSocket clients with thread-safe operations."""

    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._channels: Dict[str, set] = {}
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

    def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a channel."""
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a channel."""
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_channel_subscribers(self, channel: str) -> list:
        """Get list of client IDs subscribed to a channel."""
        with self._lock:
            return list(self._channels.get(channel, set()))

    def get_active_channels(self) -> Dict[str, int]:
        """Get all active channels and their subscriber counts."""
        with self._lock:
            return {channel: len(clients) for channel, clients in self._channels.items()}

    def get_clients_in_channel(self, channel: str) -> Dict[str, Any]:
        """Get all websocket objects for clients in a channel."""
        with self._lock:
            subscriber_ids = self._channels.get(channel, set())
            return {cid: self._clients[cid] for cid in subscriber_ids if cid in self._clients}
