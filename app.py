import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

import websockets
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response


class ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients: dict[str, websockets.ServerConnection] = {}

    def register(self, client_id: str, websocket: websockets.ServerConnection):
        with self._lock:
            self._clients[client_id] = websocket

    def unregister(self, client_id: str):
        with self._lock:
            self._clients.pop(client_id, None)

    def get_all(self):
        with self._lock:
            return list(self._clients.items())

    @property
    def count(self):
        with self._lock:
            return len(self._clients)


registry = ClientRegistry()


async def handler(websocket):
    client_id = str(uuid.uuid4())
    registry.register(client_id, websocket)
    try:
        welcome = json.dumps({
            "type": "system",
            "payload": {"client_id": client_id, "event": "connected"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await websocket.send(welcome)

        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")

            if msg_type == "broadcast":
                await _handle_broadcast(data)
            elif msg_type == "direct":
                await _handle_direct(data)
            elif msg_type == "system":
                await _handle_system(data, websocket)
    finally:
        registry.unregister(client_id)


async def _handle_broadcast(data):
    message = json.dumps({
        "type": "broadcast",
        "payload": data.get("payload", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    for client_id, ws in registry.get_all():
        try:
            await ws.send(message)
        except websockets.exceptions.ConnectionClosedOK:
            registry.unregister(client_id)
        except websockets.exceptions.ConnectionClosedError:
            registry.unregister(client_id)


async def _handle_direct(data):
    target_id = data.get("payload", {}).get("target_id")
    if not target_id:
        return
    message = json.dumps({
        "type": "direct",
        "payload": data.get("payload", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    for client_id, ws in registry.get_all():
        if client_id == target_id:
            try:
                await ws.send(message)
            except (websockets.exceptions.ConnectionClosedOK,
                    websockets.exceptions.ConnectionClosedError):
                registry.unregister(client_id)
            return


async def _handle_system(data, websocket):
    message = json.dumps({
        "type": "system",
        "payload": data.get("payload", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    try:
        await websocket.send(message)
    except (websockets.exceptions.ConnectionClosedOK,
            websockets.exceptions.ConnectionClosedError):
        pass


async def process_request(connection, request):
    if request.path == "/health":
        count = registry.count
        body = json.dumps({"clients_connected": count}).encode()
        return Response(
            200,
            "OK",
            Headers({"Content-Type": "application/json"}),
            body,
        )


async def main(host="127.0.0.1", port=8765):
    async with serve(handler, host, port, process_request=process_request):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
