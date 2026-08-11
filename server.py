import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from aiohttp import web
from websockets.asyncio.server import serve


class ClientRegistry:
    def __init__(self):
        self._clients: dict[str, object] = {}
        self._lock = threading.Lock()

    def add(self, websocket) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def get_all(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())


registry = ClientRegistry()


def make_message(msg_type: str, payload: dict) -> str:
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def broadcast_message(message: str) -> None:
    for client_id, ws in registry.get_all():
        try:
            await ws.send(message)
        except Exception:
            pass


async def ws_handler(websocket):
    client_id = registry.add(websocket)
    welcome = make_message("system", {
        "message": "connected",
        "client_id": client_id,
    })
    await websocket.send(welcome)

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})

            outbound = make_message(msg_type, payload)
            await broadcast_message(outbound)
    finally:
        registry.remove(client_id)


async def health(request):
    return web.json_response({"clients": registry.count()})


async def main():
    ws_server = await serve(
        ws_handler,
        "127.0.0.1",
        8765,
    )

    app = web.Application()
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8766)
    await site.start()

    try:
        await asyncio.Future()
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
