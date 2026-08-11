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
        self._channels = {}
        self._client_channels = {}
        self._lock = threading.Lock()

    def add(self, websocket):
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)
            channels = self._client_channels.pop(client_id, set())
            for ch in channels:
                if ch in self._channels:
                    self._channels[ch].discard(client_id)
                    if not self._channels[ch]:
                        del self._channels[ch]

    def subscribe(self, client_id, channel):
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)
            if client_id not in self._client_channels:
                self._client_channels[client_id] = set()
            self._client_channels[client_id].add(channel)

    def unsubscribe(self, client_id, channel):
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]
            if client_id in self._client_channels:
                self._client_channels[client_id].discard(channel)
                if not self._client_channels[client_id]:
                    del self._client_channels[client_id]

    @property
    def count(self):
        with self._lock:
            return len(self._clients)

    def get_all(self):
        with self._lock:
            return dict(self._clients)

    def get_subscribers(self, channel):
        with self._lock:
            return set(self._channels.get(channel, set()))

    def get_channels(self):
        with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}


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


async def _broadcast_to_channel(channel, message):
    message_str = json.dumps(message)
    subscribers = registry.get_subscribers(channel)
    clients = registry.get_all()
    tasks = []
    for cid in subscribers:
        ws = clients.get(cid)
        if ws is not None:
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

            if msg_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    registry.subscribe(client_id, channel)
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "system",
                                "payload": {
                                    "message": f"subscribed to {channel}",
                                    "channel": channel,
                                },
                                "timestamp": timestamp,
                            }
                        )
                    )
            elif msg_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    registry.unsubscribe(client_id, channel)
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "system",
                                "payload": {
                                    "message": f"unsubscribed from {channel}",
                                    "channel": channel,
                                },
                                "timestamp": timestamp,
                            }
                        )
                    )
            elif msg_type == "direct":
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
                channel = data.get("channel")
                message = {
                    "type": msg_type,
                    "payload": {"from": client_id, **payload},
                    "timestamp": timestamp,
                }
                if channel:
                    await _broadcast_to_channel(channel, message)
                else:
                    await _broadcast(message)
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

    if request.path == "/channels":
        body = json.dumps(registry.get_channels()).encode()
        headers = Headers({"Content-Type": "application/json"})
        return Response(200, "OK", headers, body)

    if request.path.startswith("/channels/"):
        parts = request.path.split("/")
        if len(parts) >= 4 and parts[3] == "subscribers":
            channel_name = parts[2]
            subscribers = registry.get_subscribers(channel_name)
            body = json.dumps(
                {"channel": channel_name, "subscribers": list(subscribers)}
            ).encode()
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
