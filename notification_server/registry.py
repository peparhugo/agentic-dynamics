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
