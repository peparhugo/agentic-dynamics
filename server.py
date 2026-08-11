import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


class ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients = {}

    def add(self, client_id, websocket):
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)

    def get_count(self):
        with self._lock:
            return len(self._clients)

    def get_all_websockets(self):
        with self._lock:
            return list(self._clients.values())

    def get_client(self, client_id):
        with self._lock:
            return self._clients.get(client_id)

    def clear(self):
        with self._lock:
            self._clients.clear()


registry = ClientRegistry()


def make_message(msg_type, payload):
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def handler(websocket):
    client_id = str(uuid.uuid4())
    registry.add(client_id, websocket)
    try:
        await websocket.send(make_message("system", {
            "message": f"Connected as {client_id}",
            "client_id": client_id,
        }))

        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "broadcast":
                msg = make_message("broadcast", payload)
                for ws in registry.get_all_websockets():
                    try:
                        await ws.send(msg)
                    except ConnectionClosed:
                        pass
            elif msg_type == "direct":
                target_id = payload.get("target")
                target_ws = registry.get_client(target_id)
                if target_ws:
                    msg = make_message("direct", payload)
                    try:
                        await target_ws.send(msg)
                    except ConnectionClosed:
                        pass
    finally:
        registry.remove(client_id)


async def health_handler(reader, writer):
    while True:
        line = await reader.readline()
        if not line or line in (b"\r\n", b"\n"):
            break

    count = registry.get_count()
    body = json.dumps({"clients_connected": count}).encode()
    writer.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n"
        b"\r\n"
        + body
    )
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def start(ws_host="127.0.0.1", ws_port=8765, http_host="127.0.0.1", http_port=8080):
    ws_server = await serve(handler, ws_host, ws_port)
    http_server = await asyncio.start_server(health_handler, http_host, http_port)
    return ws_server, http_server


async def main():
    ws_server, http_server = await start()
    print(f"WebSocket server on ws://127.0.0.1:8765")
    print(f"Health endpoint on http://127.0.0.1:8080/health")
    await asyncio.gather(
        ws_server.wait_closed(),
        http_server.serve_forever(),
    )


if __name__ == "__main__":
    asyncio.run(main())
