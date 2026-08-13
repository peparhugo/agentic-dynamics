"""WebSocket transport: the original (and default) delivery mechanism."""

import asyncio

import websockets

from .base import BaseTransport


class WebSocketTransport(BaseTransport):
    def __init__(self):
        super().__init__()
        self._server = None

    async def start(self, host, port, http_handler=None):
        self._server = await websockets.serve(
            self._connection_handler,
            host,
            port,
            process_request=http_handler,
        )
        return self._server

    async def stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _connection_handler(self, websocket):
        client_id = await self.on_connect(websocket)
        try:
            async for raw in websocket:
                if self.on_client_message is not None:
                    await self.on_client_message(client_id, raw)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)

    async def send_message(self, client_id, data) -> bool:
        websocket = self.registry.get(client_id)
        if websocket is None:
            return False
        return await self._safe_send(websocket, data)

    async def broadcast(self, client_ids, data) -> None:
        sockets = [self.registry.get(cid) for cid in client_ids]
        sockets = [ws for ws in sockets if ws is not None]
        if sockets:
            await asyncio.gather(*(self._safe_send(ws, data) for ws in sockets))

    @staticmethod
    async def _safe_send(websocket, data) -> bool:
        try:
            await websocket.send(data)
            return True
        except websockets.exceptions.ConnectionClosed:
            return False
