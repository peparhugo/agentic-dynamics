"""WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, and lets
clients broadcast JSON notifications to every connected peer or send one
directly to another client by ID. Clients may also subscribe to named
channels; broadcast messages that carry a 'channel' field are delivered
only to that channel's subscribers. Exposes GET /health, GET /channels,
and GET /channels/{name}/subscribers over plain HTTP on the same port.
"""

import asyncio
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

from websockets.asyncio.server import serve, ServerConnection
from websockets.exceptions import ConnectionClosed

MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}

CHANNEL_SUBSCRIBERS_PATH = re.compile(r"^/channels/([^/]+)/subscribers$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict) -> str:
    return json.dumps({"type": msg_type, "payload": payload, "timestamp": now_iso()})


class ClientRegistry:
    """Tracks connected clients behind a lock, protecting registration and
    removal against concurrent access from multiple handler coroutines."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.Lock()

    def add(self, connection: ServerConnection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[ServerConnection]:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class ChannelRegistry:
    """Tracks channel subscriptions behind a lock, mapping each channel name
    to the set of client IDs currently subscribed to it."""

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def remove_client(self, client_id: str) -> None:
        with self._lock:
            for channel in list(self._channels.keys()):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def channel_counts(self) -> dict[str, int]:
        with self._lock:
            return {name: len(ids) for name, ids in self._channels.items()}


registry = ClientRegistry()
channels = ChannelRegistry()


async def broadcast(payload: dict) -> None:
    message = make_message("broadcast", payload)
    channel = payload.get("channel")
    if channel:
        targets = [(cid, registry.get(cid)) for cid in channels.subscribers(channel)]
    else:
        targets = registry.snapshot()
    for _client_id, connection in targets:
        if connection is None:
            continue
        try:
            await connection.send(message)
        except ConnectionClosed:
            pass


async def send_direct(target_id: str, payload: dict) -> bool:
    connection = registry.get(target_id)
    if connection is None:
        return False
    try:
        await connection.send(make_message("direct", payload))
        return True
    except ConnectionClosed:
        return False


async def handle_message(connection: ServerConnection, client_id: str, raw: str) -> None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await connection.send(make_message("system", {"error": "invalid JSON"}))
        return

    if not isinstance(data, dict):
        await connection.send(make_message("system", {"error": "message must be a JSON object"}))
        return

    msg_type = data.get("type")
    payload = data.get("payload", {})

    if msg_type not in MESSAGE_TYPES:
        await connection.send(
            make_message("system", {"error": f"unsupported type: {msg_type!r}"})
        )
        return

    if not isinstance(payload, dict):
        await connection.send(make_message("system", {"error": "payload must be an object"}))
        return

    if msg_type == "broadcast":
        await broadcast(payload)
    elif msg_type == "direct":
        target_id = payload.get("target")
        if not target_id:
            await connection.send(
                make_message("system", {"error": "direct message requires 'target' in payload"})
            )
            return
        delivered = await send_direct(target_id, payload)
        if not delivered:
            await connection.send(
                make_message("system", {"error": f"client {target_id} not connected"})
            )
    elif msg_type == "system":
        await connection.send(make_message("system", {"ack": True}))
    elif msg_type == "subscribe":
        channel = payload.get("channel")
        if not channel:
            await connection.send(
                make_message("system", {"error": "subscribe requires 'channel' in payload"})
            )
            return
        channels.subscribe(client_id, channel)
        await connection.send(make_message("system", {"event": "subscribed", "channel": channel}))
    elif msg_type == "unsubscribe":
        channel = payload.get("channel")
        if not channel:
            await connection.send(
                make_message("system", {"error": "unsubscribe requires 'channel' in payload"})
            )
            return
        channels.unsubscribe(client_id, channel)
        await connection.send(make_message("system", {"event": "unsubscribed", "channel": channel}))


async def handler(connection: ServerConnection) -> None:
    client_id = registry.add(connection)
    try:
        await connection.send(make_message("system", {"event": "connected", "client_id": client_id}))
        async for raw in connection:
            await handle_message(connection, client_id, raw)
    except ConnectionClosed:
        pass
    finally:
        registry.remove(client_id)
        channels.remove_client(client_id)


async def process_request(connection: ServerConnection, request):
    if request.path == "/health":
        response = connection.respond(HTTPStatus.OK, "")
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({"connected_clients": registry.count()}).encode()
        return response

    if request.path == "/channels":
        response = connection.respond(HTTPStatus.OK, "")
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({
            "channels": [
                {"name": name, "subscribers": count}
                for name, count in sorted(channels.channel_counts().items())
            ]
        }).encode()
        return response

    match = CHANNEL_SUBSCRIBERS_PATH.match(request.path)
    if match:
        channel_name = match.group(1)
        response = connection.respond(HTTPStatus.OK, "")
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({
            "channel": channel_name,
            "subscribers": channels.subscribers(channel_name),
        }).encode()
        return response

    return None


async def main(host: str = "localhost", port: int = 8765) -> None:
    async with serve(handler, host, port, process_request=process_request):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
