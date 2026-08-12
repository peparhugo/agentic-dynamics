import asyncio
from abc import ABC, abstractmethod

from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError


class BaseTransport(ABC):
    @abstractmethod
    async def on_connect(self, client_id, connection):
        ...

    @abstractmethod
    async def on_disconnect(self, client_id):
        ...

    @abstractmethod
    async def send_message(self, client_id, message):
        ...

    @abstractmethod
    async def broadcast(self, message):
        ...


class WebSocketTransport(BaseTransport):
    def __init__(self, registry):
        self._registry = registry
        self._connections = {}

    async def on_connect(self, client_id, connection):
        self._connections[client_id] = connection
        self._registry.add(client_id, connection)

    async def on_disconnect(self, client_id):
        self._connections.pop(client_id, None)
        self._registry.remove(client_id)

    async def send_message(self, client_id, message):
        ws = self._connections.get(client_id)
        if ws is None:
            return
        try:
            await ws.send(message)
        except (ConnectionClosedOK, ConnectionClosedError):
            self._connections.pop(client_id, None)
            self._registry.remove(client_id)
        except Exception:
            self._connections.pop(client_id, None)
            self._registry.remove(client_id)

    async def broadcast(self, message):
        tasks = []
        for cid, ws in list(self._connections.items()):
            tasks.append(self._send_to_ws(cid, ws, message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_ws(self, client_id, websocket, message):
        try:
            await websocket.send(message)
        except (ConnectionClosedOK, ConnectionClosedError):
            self._connections.pop(client_id, None)
            self._registry.remove(client_id)
        except Exception:
            self._connections.pop(client_id, None)
            self._registry.remove(client_id)
