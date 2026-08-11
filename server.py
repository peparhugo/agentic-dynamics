import asyncio
import json
import uuid
import threading
from datetime import datetime, timezone

import websockets
from websockets import ServerConnection
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from aiohttp import web


class ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients: dict[str, ServerConnection] = {}

    def add(self, client_id: str, ws: ServerConnection) -> None:
        with self._lock:
            self._clients[client_id] = ws

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self) -> dict[str, ServerConnection]:
        with self._lock:
            return dict(self._clients)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


registry = ClientRegistry()


def _make_message(msg_type: str, payload: dict) -> str:
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _broadcast(msg_type: str, payload: dict, exclude_id: str | None = None) -> None:
    msg = _make_message(msg_type, payload)
    clients = registry.get_all()
    for cid, ws in clients.items():
        if cid == exclude_id:
            continue
        try:
            await ws.send(msg)
        except ConnectionClosed:
            registry.remove(cid)


async def handler(websocket: ServerConnection) -> None:
    client_id = str(uuid.uuid4())
    registry.add(client_id, websocket)

    try:
        await websocket.send(_make_message("system", {
            "client_id": client_id,
            "message": "Connected",
        }))

        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "broadcast":
                await _broadcast("broadcast", payload, exclude_id=client_id)

            elif msg_type == "direct":
                target_id = data.get("target")
                if target_id:
                    target_ws = registry.get(target_id)
                    if target_ws:
                        try:
                            await target_ws.send(_make_message("direct", payload))
                        except ConnectionClosed:
                            registry.remove(target_id)

    finally:
        registry.remove(client_id)
        await _broadcast("system", {
            "client_id": client_id,
            "message": "Disconnected",
        })


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"clients": registry.count})


async def main(host: str = "127.0.0.1", ws_port: int = 8765, http_port: int = 8080) -> None:
    ws_server = await serve(handler, host, ws_port)

    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, http_port)
    await site.start()

    try:
        await asyncio.Future()
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
