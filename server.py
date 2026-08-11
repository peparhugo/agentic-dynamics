import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._subscriptions = {}
        self._client_channels = {}
        self._lock = threading.Lock()

    def add(self, client_id, websocket):
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)
            if client_id in self._client_channels:
                for channel in list(self._client_channels[client_id]):
                    if channel in self._subscriptions:
                        self._subscriptions[channel].discard(client_id)
                        if not self._subscriptions[channel]:
                            del self._subscriptions[channel]
                del self._client_channels[client_id]

    def count(self):
        with self._lock:
            return len(self._clients)

    def get_all(self):
        with self._lock:
            return dict(self._clients)

    def clear(self):
        with self._lock:
            self._clients.clear()
            self._subscriptions.clear()
            self._client_channels.clear()

    def subscribe(self, client_id, channel):
        with self._lock:
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            self._subscriptions[channel].add(client_id)
            if client_id not in self._client_channels:
                self._client_channels[client_id] = set()
            self._client_channels[client_id].add(channel)

    def unsubscribe(self, client_id, channel):
        with self._lock:
            if channel in self._subscriptions:
                self._subscriptions[channel].discard(client_id)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]
            if client_id in self._client_channels:
                self._client_channels[client_id].discard(channel)
                if not self._client_channels[client_id]:
                    del self._client_channels[client_id]

    def get_subscribers(self, channel):
        with self._lock:
            if channel in self._subscriptions:
                return list(self._subscriptions[channel])
            return []

    def get_channels(self):
        with self._lock:
            return {name: len(subscribers) for name, subscribers in self._subscriptions.items()}

    def get_subscriber_websockets(self, channel):
        with self._lock:
            if channel not in self._subscriptions:
                return {}
            result = {}
            for cid in self._subscriptions[channel]:
                if cid in self._clients:
                    result[cid] = self._clients[cid]
            return result


class NotificationServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()

    async def _handler(self, websocket):
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)
        try:
            welcome = {
                "type": "system",
                "payload": {"client_id": client_id, "message": "Connected"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send(json.dumps(welcome))

            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "broadcast")
                payload = data.get("payload", {})

                if msg_type == "broadcast":
                    notification = {
                        "type": "broadcast",
                        "payload": payload,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "sender": client_id,
                    }
                    channel = data.get("channel")
                    if channel:
                        notification["channel"] = channel
                    await self._broadcast(notification)
                elif msg_type == "direct":
                    target = data.get("target")
                    if target:
                        notification = {
                            "type": "direct",
                            "payload": payload,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "sender": client_id,
                        }
                        await self._send_direct(target, notification)
                elif msg_type == "subscribe":
                    channel = data.get("channel")
                    if channel:
                        self.registry.subscribe(client_id, channel)
                elif msg_type == "unsubscribe":
                    channel = data.get("channel")
                    if channel:
                        self.registry.unsubscribe(client_id, channel)
        finally:
            self.registry.remove(client_id)

    async def _broadcast(self, message):
        channel = message.get("channel")
        if channel:
            clients = self.registry.get_subscriber_websockets(channel)
        else:
            clients = self.registry.get_all()
        message_str = json.dumps(message)
        disconnected = []
        for cid, ws in clients.items():
            try:
                await ws.send(message_str)
            except ConnectionClosed:
                disconnected.append(cid)
        for cid in disconnected:
            self.registry.remove(cid)

    async def _send_direct(self, target_id, message):
        clients = self.registry.get_all()
        ws = clients.get(target_id)
        if ws is not None:
            try:
                await ws.send(json.dumps(message))
            except ConnectionClosed:
                self.registry.remove(target_id)

    def _process_request(self, connection, request):
        if request.path == "/health":
            count = self.registry.count()
            response = connection.respond(200, json.dumps({"clients": count}))
            response.headers["Content-Type"] = "application/json"
            return response
        if request.path == "/channels":
            channels = self.registry.get_channels()
            response = connection.respond(200, json.dumps({"channels": channels}))
            response.headers["Content-Type"] = "application/json"
            return response
        if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
            channel_name = request.path[len("/channels/"):-len("/subscribers")]
            subscribers = self.registry.get_subscribers(channel_name)
            response = connection.respond(200, json.dumps({
                "channel": channel_name,
                "subscribers": subscribers,
            }))
            response.headers["Content-Type"] = "application/json"
            return response
        return None

    def run(self):
        return serve(
            self._handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )


async def main():
    server = NotificationServer()
    async with server.run():
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
