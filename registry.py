"""Thread-safe registry of connected WebSocket clients.

Maps a unique ``client_id`` to the client's WebSocket connection object and
tracks which named channels each client is subscribed to.

The asyncio event loop runs on a single thread by default, so in the common
case all registry access happens inside that loop and no locking would be
required. However, asyncio may occasionally dispatch callbacks on worker
threads, so every operation is still guarded by a :class:`threading.Lock`.
"""

import threading
from typing import Dict, List, Set, Tuple


class ClientRegistry:
    """Holds ``client_id -> websocket`` mappings under a single lock."""

    def __init__(self):
        self._clients = {}
        self._channels: Dict[str, Set[str]] = {}
        self._client_channels: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, websocket) -> None:
        """Register ``websocket`` under ``client_id``."""
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> bool:
        """Remove ``client_id`` and its channel memberships.

        Return True if ``client_id`` was present.
        """
        with self._lock:
            present = client_id in self._clients
            self._clients.pop(client_id, None)
            for channel in self._client_channels.pop(client_id, set()):
                members = self._channels.get(channel)
                if members is not None:
                    members.discard(client_id)
                    if not members:
                        del self._channels[channel]
            return present

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

    def subscribe(self, client_id: str, channel: str) -> bool:
        """Subscribe ``client_id`` to ``channel``.

        Returns False when ``client_id`` is not a connected client.
        """
        with self._lock:
            if client_id not in self._clients:
                return False
            self._channels.setdefault(channel, set()).add(client_id)
            self._client_channels.setdefault(client_id, set()).add(channel)
            return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        """Unsubscribe ``client_id`` from ``channel``.

        Returns False when ``client_id`` was not subscribed to ``channel``.
        """
        with self._lock:
            members = self._channels.get(channel)
            if members is None or client_id not in members:
                return False
            members.discard(client_id)
            if not members:
                del self._channels[channel]
            self._client_channels.get(client_id, set()).discard(channel)
            return True

    def channels(self) -> Dict[str, int]:
        """Return a snapshot mapping channel name -> subscriber count."""
        with self._lock:
            return {name: len(members) for name, members in self._channels.items()}

    def subscribers(self, channel: str) -> List[str]:
        """Return a sorted snapshot of client ids subscribed to ``channel``."""
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def connections_for_channel(self, channel: str) -> list:
        """Return a snapshot of connections subscribed to ``channel``."""
        with self._lock:
            return [
                self._clients[cid]
                for cid in self._channels.get(channel, set())
                if cid in self._clients
            ]

    def channels_of(self, client_id: str) -> Set[str]:
        """Return a snapshot of the channels ``client_id`` is subscribed to."""
        with self._lock:
            return set(self._client_channels.get(client_id, set()))
