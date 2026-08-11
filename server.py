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


class ChannelManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._channels = {}

    def subscribe(self, client_id, channel):
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def unsubscribe(self, client_id, channel):
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_subscribers(self, channel):
        with self._lock:
            return set(self._channels.get(channel, set()))

    def remove_client(self, client_id):
        with self._lock:
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def list_channels(self):
        with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    def clear(self):
        with self._lock:
            self._channels.clear()


channels = ChannelManager()


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

            if msg_type == "subscribe":
                channel_name = payload.get("channel")
                if channel_name:
                    channels.subscribe(client_id, channel_name)
            elif msg_type == "unsubscribe":
                channel_name = payload.get("channel")
                if channel_name:
                    channels.unsubscribe(client_id, channel_name)
            elif msg_type == "broadcast":
                channel = data.get("channel")
                msg = make_message("broadcast", payload)
                if channel:
                    for sub_id in channels.get_subscribers(channel):
                        sub_ws = registry.get_client(sub_id)
                        if sub_ws:
                            try:
                                await sub_ws.send(msg)
                            except ConnectionClosed:
                                pass
                else:
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
        channels.remove_client(client_id)
        registry.remove(client_id)


async def http_handler(reader, writer):
    request_line = await reader.readline()
    parts = request_line.decode().strip().split()
    if len(parts) < 2:
        writer.close()
        await writer.wait_closed()
        return

    method = parts[0]
    path = parts[1]

    while True:
        line = await reader.readline()
        if not line or line in (b"\r\n", b"\n"):
            break

    body = b""
    status = b"200 OK"

    if path == "/health":
        count = registry.get_count()
        body = json.dumps({"clients_connected": count}).encode()
    elif path == "/channels":
        data = channels.list_channels()
        body = json.dumps(data).encode()
    elif path.startswith("/channels/") and path.endswith("/subscribers"):
        channel_name = path[len("/channels/"):-len("/subscribers")]
        subs = channels.get_subscribers(channel_name)
        body = json.dumps(list(subs)).encode()
    else:
        status = b"404 Not Found"
        body = json.dumps({"error": "not found"}).encode()

    writer.write(
        b"HTTP/1.1 " + status + b"\r\n"
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
    http_server = await asyncio.start_server(http_handler, http_host, http_port)
    return ws_server, http_server


async def main():
    ws_server, http_server = await start()
    print(f"WebSocket server on ws://127.0.0.1:8765")
    print(f"HTTP endpoints on http://127.0.0.1:8080")
    await asyncio.gather(
        ws_server.wait_closed(),
        http_server.serve_forever(),
    )


if __name__ == "__main__":
    asyncio.run(main())
