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
        self._channels: dict[str, set[str]] = {}

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

    def subscribe(self, client_id: str, channel: str):
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def unsubscribe(self, client_id: str, channel: str):
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def unsubscribe_all(self, client_id: str):
        with self._lock:
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_channel_subscribers(self, channel: str):
        with self._lock:
            if channel not in self._channels:
                return []
            result = []
            for cid in list(self._channels[channel]):
                if cid in self._clients:
                    result.append((cid, self._clients[cid]))
                else:
                    self._channels[channel].discard(cid)
            if channel in self._channels and not self._channels[channel]:
                del self._channels[channel]
            return result

    def get_channels(self):
        with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    def get_channel_subscriber_ids(self, channel: str):
        with self._lock:
            if channel not in self._channels:
                return []
            return list(self._channels[channel])


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
            elif msg_type == "subscribe":
                await _handle_subscribe(data, client_id, websocket)
            elif msg_type == "unsubscribe":
                await _handle_unsubscribe(data, client_id, websocket)
    finally:
        registry.unsubscribe_all(client_id)
        registry.unregister(client_id)


async def _handle_broadcast(data):
    channel = data.get("channel")
    message_dict = {
        "type": "broadcast",
        "payload": data.get("payload", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if channel:
        message_dict["channel"] = channel

    message = json.dumps(message_dict)

    if channel:
        targets = registry.get_channel_subscribers(channel)
    else:
        targets = registry.get_all()

    for client_id, ws in targets:
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


async def _handle_subscribe(data, client_id, websocket):
    channel = data.get("channel")
    if not channel:
        return
    registry.subscribe(client_id, channel)
    message = json.dumps({
        "type": "system",
        "payload": {"event": "subscribed", "channel": channel},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    try:
        await websocket.send(message)
    except (websockets.exceptions.ConnectionClosedOK,
            websockets.exceptions.ConnectionClosedError):
        pass


async def _handle_unsubscribe(data, client_id, websocket):
    channel = data.get("channel")
    if not channel:
        return
    registry.unsubscribe(client_id, channel)
    message = json.dumps({
        "type": "system",
        "payload": {"event": "unsubscribed", "channel": channel},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    try:
        await websocket.send(message)
    except (websockets.exceptions.ConnectionClosedOK,
            websockets.exceptions.ConnectionClosedError):
        pass


async def process_request(connection, request):
    path = request.path

    if path == "/health":
        count = registry.count
        body = json.dumps({"clients_connected": count}).encode()
        return Response(
            200,
            "OK",
            Headers({"Content-Type": "application/json"}),
            body,
        )

    if path == "/channels":
        channels = registry.get_channels()
        body = json.dumps(channels).encode()
        return Response(
            200,
            "OK",
            Headers({"Content-Type": "application/json"}),
            body,
        )

    if path.startswith("/channels/") and path.endswith("/subscribers"):
        channel_name = path[len("/channels/"):-len("/subscribers")]
        ids = registry.get_channel_subscriber_ids(channel_name)
        body = json.dumps({"channel": channel_name, "subscribers": ids}).encode()
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
