"""Thread-safe in-memory registry mapping client IDs to WebSocket connections."""

import threading
import uuid


class ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients = {}

    def add(self, websocket, client_id=None) -> str:
        client_id = client_id or str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id):
        with self._lock:
            return self._clients.get(client_id)

    def all(self) -> dict:
        with self._lock:
            return dict(self._clients)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class ChannelRegistry:
    """Thread-safe in-memory registry mapping channel names to the set of
    client IDs subscribed to them."""

    def __init__(self):
        self._lock = threading.Lock()
        self._channels = {}

    def subscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        with self._lock:
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def subscribers(self, channel: str) -> set:
        with self._lock:
            return set(self._channels.get(channel, set()))

    def channels(self) -> dict:
        with self._lock:
            return {name: set(subs) for name, subs in self._channels.items()}
