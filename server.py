import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._channels = {}
        self._lock = threading.Lock()

    def add(self, client_id, websocket):
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)
            empty_channels = []
            for channel, subscribers in self._channels.items():
                subscribers.discard(client_id)
                if not subscribers:
                    empty_channels.append(channel)
            for channel in empty_channels:
                del self._channels[channel]

    def get(self, client_id):
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self):
        with self._lock:
            return list(self._clients.items())

    def count(self):
        with self._lock:
            return len(self._clients)

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

    def get_channel_subscribers(self, channel):
        with self._lock:
            return list(self._channels.get(channel, set()))

    def get_channel_info(self):
        with self._lock:
            return {name: len(subscribers) for name, subscribers in self._channels.items()}

    def get_clients_for_channel(self, channel):
        with self._lock:
            return self._channels.get(channel, set())


registry = ClientRegistry()


def make_message(msg_type, payload):
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def broadcast(message):
    tasks = []
    for cid, ws in registry.get_all():
        tasks.append(_safe_send(cid, ws, message))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def broadcast_to_clients(client_ids, message):
    tasks = []
    for cid in client_ids:
        ws = registry.get(cid)
        if ws is not None:
            tasks.append(_safe_send(cid, ws, message))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _safe_send(client_id, websocket, message):
    try:
        await websocket.send(message)
    except (ConnectionClosedOK, ConnectionClosedError):
        registry.remove(client_id)
    except Exception:
        registry.remove(client_id)


async def send_direct(recipient_id, message):
    ws = registry.get(recipient_id)
    if ws is None:
        return
    try:
        await ws.send(message)
    except (ConnectionClosedOK, ConnectionClosedError):
        registry.remove(recipient_id)
    except Exception:
        registry.remove(recipient_id)


async def handler(websocket):
    client_id = str(uuid.uuid4())
    registry.add(client_id, websocket)

    try:
        welcome = make_message("system", {
            "message": f"Connected as {client_id}",
            "client_id": client_id
        })
        await websocket.send(welcome)
    except Exception:
        registry.remove(client_id)
        return

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})

            if msg_type == "subscribe":
                channel = payload.get("channel", "")
                if channel:
                    registry.subscribe(client_id, channel)
                    confirm = make_message("system", {
                        "message": f"Subscribed to {channel}",
                        "channel": channel,
                        "client_id": client_id
                    })
                    await websocket.send(confirm)
            elif msg_type == "unsubscribe":
                channel = payload.get("channel", "")
                if channel:
                    registry.unsubscribe(client_id, channel)
                    confirm = make_message("system", {
                        "message": f"Unsubscribed from {channel}",
                        "channel": channel,
                        "client_id": client_id
                    })
                    await websocket.send(confirm)
            elif msg_type == "broadcast":
                channel = payload.get("channel")
                if channel:
                    broadcast_msg = make_message("broadcast", payload)
                    client_ids = registry.get_clients_for_channel(channel)
                    await broadcast_to_clients(client_ids, broadcast_msg)
                else:
                    broadcast_msg = make_message("broadcast", payload)
                    await broadcast(broadcast_msg)
            elif msg_type == "direct":
                recipient = payload.get("recipient")
                if recipient:
                    direct_msg = make_message("direct", {
                        "from": client_id,
                        "message": payload.get("message", "")
                    })
                    await send_direct(recipient, direct_msg)
                    await websocket.send(direct_msg)
    except (ConnectionClosedOK, ConnectionClosedError):
        pass
    except Exception:
        pass
    finally:
        registry.remove(client_id)
        leave_msg = make_message("system", {
            "message": f"Client {client_id} disconnected",
            "client_id": client_id
        })
        await broadcast(leave_msg)


def process_request(connection, request):
    if request.path == "/health":
        count = registry.count()
        response = connection.respond(
            200,
            json.dumps({"clients": count, "status": "ok"}),
        )
        response.headers["Content-Type"] = "application/json"
        return response
    if request.path == "/channels":
        info = registry.get_channel_info()
        response = connection.respond(
            200,
            json.dumps(info),
        )
        response.headers["Content-Type"] = "application/json"
        return response
    if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
        channel = request.path[len("/channels/"):-len("/subscribers")]
        if channel:
            subscribers = registry.get_channel_subscribers(channel)
            response = connection.respond(
                200,
                json.dumps(subscribers),
            )
            response.headers["Content-Type"] = "application/json"
            return response
    return None


async def main():
    async with serve(handler, "localhost", 8765, process_request=process_request):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
