import asyncio
import json
import uuid
from datetime import datetime, timezone
from http import HTTPStatus

import websockets
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._subscriptions = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket):
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[websocket] = client_id
        return client_id

    async def unregister(self, websocket):
        async with self._lock:
            return self._clients.pop(websocket, None)

    async def get_all(self):
        async with self._lock:
            return list(self._clients.items())

    async def get_count(self):
        async with self._lock:
            return len(self._clients)

    async def get_client_id(self, websocket):
        async with self._lock:
            return self._clients.get(websocket)

    async def subscribe(self, websocket, channel):
        async with self._lock:
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            self._subscriptions[channel].add(websocket)

    async def unsubscribe(self, websocket, channel):
        async with self._lock:
            if channel in self._subscriptions:
                self._subscriptions[channel].discard(websocket)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]

    async def unsubscribe_all(self, websocket):
        async with self._lock:
            for subs in list(self._subscriptions.values()):
                subs.discard(websocket)
            self._subscriptions = {
                k: v for k, v in self._subscriptions.items() if v
            }

    async def get_channels(self):
        async with self._lock:
            return {
                channel: len(subs)
                for channel, subs in self._subscriptions.items()
            }

    async def get_channel_subscribers(self, channel):
        async with self._lock:
            subs = self._subscriptions.get(channel, set())
            return [self._clients[ws] for ws in subs if ws in self._clients]

    async def get_channel_websockets(self, channel):
        async with self._lock:
            return list(self._subscriptions.get(channel, set()))


registry = ClientRegistry()


def message(type_, payload):
    return json.dumps({
        "type": type_,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def broadcast(message_str, exclude=None):
    clients = await registry.get_all()
    for ws, _ in clients:
        if ws is exclude:
            continue
        try:
            await ws.send(message_str)
        except ConnectionClosed:
            await registry.unsubscribe_all(ws)
            await registry.unregister(ws)


async def broadcast_to_channel(message_str, channel):
    subs = await registry.get_channel_websockets(channel)
    for ws in subs:
        try:
            await ws.send(message_str)
        except ConnectionClosed:
            await registry.unsubscribe_all(ws)
            await registry.unregister(ws)


async def handler(websocket):
    client_id = await registry.register(websocket)

    welcome = message("system", {
        "client_id": client_id,
        "message": "connected",
    })
    await websocket.send(welcome)

    join_msg = message("system", {
        "client_id": client_id,
        "message": "joined",
    })
    await broadcast(join_msg, exclude=websocket)

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})

            if msg_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    await registry.subscribe(websocket, channel)
                continue

            if msg_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    await registry.unsubscribe(websocket, channel)
                continue

            msg = message(msg_type, payload)

            channel = data.get("channel")
            if channel:
                await broadcast_to_channel(msg, channel)
            else:
                await broadcast(msg)
    finally:
        await registry.unsubscribe_all(websocket)
        await registry.unregister(websocket)
        leave_msg = message("system", {
            "client_id": client_id,
            "message": "left",
        })
        await broadcast(leave_msg)


async def process_request(connection, request):
    if request.path == "/health":
        count = await registry.get_count()
        body = json.dumps({"connected_clients": count})
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    if request.path == "/channels":
        channels = await registry.get_channels()
        body = json.dumps(channels)
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
        channel_name = request.path[len("/channels/"):-len("/subscribers")]
        subscribers = await registry.get_channel_subscribers(channel_name)
        body = json.dumps(subscribers)
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    return None


async def main(host="localhost", port=8765):
    async with serve(
        handler,
        host,
        port,
        process_request=process_request,
    ) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
