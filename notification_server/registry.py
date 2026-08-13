"""Thread-safe registry of connected WebSocket clients."""
from __future__ import annotations

import threading
from typing import Any


class ClientRegistry:
    """Maps client_id -> connection object, safe to touch from multiple threads.

    Also tracks channel subscriptions: which clients are subscribed to which
    named channels, for routing channel-scoped broadcasts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}

    def add(self, client_id: str, connection: Any) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            channels = self._client_channels.pop(client_id, set())
            for channel in channels:
                subs = self._channels.get(channel)
                if subs is not None:
                    subs.discard(client_id)
                    if not subs:
                        del self._channels[channel]

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

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)
            self._client_channels.setdefault(client_id, set()).add(channel)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subs = self._channels.get(channel)
            if subs is not None:
                subs.discard(client_id)
                if not subs:
                    del self._channels[channel]
            client_chans = self._client_channels.get(client_id)
            if client_chans is not None:
                client_chans.discard(channel)
                if not client_chans:
                    del self._client_channels[client_id]

    def channels(self) -> dict[str, int]:
        """Map of channel name -> subscriber count, for active channels only."""
        with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    def channel_subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def connections_for_channel(self, channel: str) -> list[Any]:
        with self._lock:
            return [
                self._clients[cid]
                for cid in self._channels.get(channel, set())
                if cid in self._clients
            ]
