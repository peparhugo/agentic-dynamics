import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Response


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._lock = threading.Lock()

    def add(self, websocket):
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)

    @property
    def count(self):
        with self._lock:
            return len(self._clients)

    def get_all(self):
        with self._lock:
            return dict(self._clients)


registry = ClientRegistry()


def _make_timestamp():
    return datetime.now(timezone.utc).isoformat()


async def _broadcast(message):
    message_str = json.dumps(message)
    clients = registry.get_all()
    tasks = []
    for ws in clients.values():
        tasks.append(asyncio.create_task(ws.send(message_str)))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _send_direct(target_id, message):
    clients = registry.get_all()
    ws = clients.get(target_id)
    if ws is None:
        return
    try:
        await ws.send(json.dumps(message))
    except Exception:
        pass


async def handler(websocket):
    client_id = registry.add(websocket)
    try:
        welcome = {
            "type": "system",
            "payload": {"client_id": client_id, "message": "connected"},
            "timestamp": _make_timestamp(),
        }
        await websocket.send(json.dumps(welcome))

        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})
            timestamp = _make_timestamp()

            if msg_type == "direct":
                target = payload.get("target")
                if target is not None:
                    await _send_direct(
                        target,
                        {
                            "type": "direct",
                            "payload": {
                                "from": client_id,
                                "message": payload.get("message", {}),
                            },
                            "timestamp": timestamp,
                        },
                    )
            else:
                await _broadcast(
                    {
                        "type": msg_type,
                        "payload": {"from": client_id, **payload},
                        "timestamp": timestamp,
                    }
                )
    except ConnectionClosed:
        pass
    finally:
        registry.remove(client_id)
        await _broadcast(
            {
                "type": "system",
                "payload": {"client_id": client_id, "message": "disconnected"},
                "timestamp": _make_timestamp(),
            }
        )


async def process_request(connection, request):
    if request.path == "/health":
        body = json.dumps({"connected_clients": registry.count}).encode()
        headers = Headers({"Content-Type": "application/json"})
        return Response(200, "OK", headers, body)
    return None


async def start_server(host="0.0.0.0", port=8765):
    async with serve(
        handler,
        host,
        port,
        process_request=process_request,
    ) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(start_server())
