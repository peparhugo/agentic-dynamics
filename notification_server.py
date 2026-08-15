"""
WebSocket-based notification server backed by Redis pub/sub and SQLite.

Features
--------
- Accept WebSocket connections and assign each client a globally-unique ID.
- Distribute messages through Redis pub/sub channels (the shared backbone):
  the server publishes; a subscriber "worker" on every instance delivers.
- Broadcast a message to all connected clients.
- Deliver a "direct" message to a single client by ID.
- Support named channels: clients subscribe/unsubscribe dynamically and
  messages carrying a ``channel`` field are delivered only to subscribers.
- Remove clients cleanly on disconnect.
- Persist every application message in SQLite for history.
- Expose ``GET /health`` returning the number of connected clients.
- Expose ``GET /channels`` and ``GET /channels/{name}/subscribers``.
- Expose ``GET /messages?limit=50&offset=0`` returning persisted history.

Configuration
-------------
- ``REDIS_URL``     — Redis broker connection string.  When unset, an
  in-process fakeredis instance is used.
- ``DATABASE_URL``  — SQLite path for message history (default ``messages.db``).

Message format
--------------
Every application message is a JSON object::

    {"type": str, "payload": dict, "timestamp": str}

Supported ``type`` values: ``broadcast``, ``direct``, ``system``,
``subscribe``, ``unsubscribe``.

Wire format
-----------
The ``websockets`` library base64-encodes every frame on the wire.  We follow
that contract explicitly: every outgoing JSON message is base64-encoded before
it is sent and every incoming frame is base64-decoded before it is parsed as
JSON.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import parse_qs, unquote, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from broker import (
    BROADCAST_CHANNEL,
    CHANNEL_PREFIX,
    DIRECT_PREFIX,
    SUBSCRIBE_PATTERN,
    MessageBroker,
)
from store import MessageStore


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_message(message: Dict[str, Any]) -> str:
    """Serialize a message to the on-the-wire base64 string."""
    raw = json.dumps(message).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def decode_message(raw: str) -> Dict[str, Any]:
    """Parse a base64 on-the-wire string back into a message dict."""
    data = base64.b64decode(raw.encode("ascii"))
    return json.loads(data.decode("utf-8"))


class ClientRegistry:
    """Thread-safe registry of connected clients and their subscriptions."""

    def __init__(self) -> None:
        self._clients: Dict[int, ServerConnection] = {}
        self._channels: Dict[str, set] = {}
        self._lock = threading.Lock()
        self._counter = itertools.count(1)

    def register(self, websocket: ServerConnection, client_id: int | None = None) -> int:
        with self._lock:
            if client_id is None:
                client_id = next(self._counter)
            self._clients[client_id] = websocket
            return client_id

    def unregister(self, client_id: int) -> ServerConnection | None:
        with self._lock:
            connection = self._clients.pop(client_id, None)
            for members in self._channels.values():
                members.discard(client_id)
            for name in [n for n, m in self._channels.items() if not m]:
                del self._channels[name]
            return connection

    def get(self, client_id: int) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def snapshot(self) -> Dict[int, ServerConnection]:
        with self._lock:
            return dict(self._clients)

    # ── Subscriptions ──────────────────────────────────────────

    def subscribe(self, client_id: int, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: int, channel: str) -> None:
        with self._lock:
            members = self._channels.get(channel)
            if members is not None:
                members.discard(client_id)
                if not members:
                    del self._channels[channel]

    def subscribers(self, channel: str) -> List[int]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def channels(self) -> Dict[str, int]:
        with self._lock:
            return {name: len(members) for name, members in self._channels.items()}


class NotificationServer:
    """Asyncio WebSocket notification server with a Redis pub/sub backbone."""

    def __init__(
        self,
        broker: MessageBroker | None = None,
        store: MessageStore | None = None,
        redis_url: str | None = None,
        database_url: str | None = None,
    ) -> None:
        self.clients = ClientRegistry()
        self.instance_id = uuid.uuid4().hex
        self.broker = broker if broker is not None else MessageBroker(redis_url=redis_url)
        self.store = store if store is not None else MessageStore(database_url)
        self._server = None
        self._subscriber_task = None

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self._server = await serve(
            self._handle_connection,
            host,
            port,
            process_request=self._process_request,
        )
        self._subscriber_task = asyncio.create_task(self._subscriber_loop())

    async def stop(self) -> None:
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except (asyncio.CancelledError, Exception):
                pass
            self._subscriber_task = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def port(self) -> int | None:
        if self._server is None or not self._server.sockets:
            return None
        return self._server.sockets[0].getsockname()[1]

    # ── Redis worker (subscriber) ─────────────────────────────

    async def _subscriber_loop(self) -> None:
        ps = self.broker.pubsub()
        await ps.psubscribe(SUBSCRIBE_PATTERN)
        try:
            async for message in ps.listen():
                if message["type"] != "pmessage":
                    continue
                channel = message["channel"]
                try:
                    outgoing = json.loads(message["data"])
                except (ValueError, TypeError):
                    continue
                await self._route(channel, outgoing)
        finally:
            try:
                await ps.aclose()
            except Exception:
                pass

    async def _route(self, channel: str, message: Dict[str, Any]) -> None:
        if channel == BROADCAST_CHANNEL:
            await self.broadcast(message)
        elif channel.startswith(CHANNEL_PREFIX):
            name = channel[len(CHANNEL_PREFIX):]
            await self.send_to_channel(name, message)
        elif channel.startswith(DIRECT_PREFIX):
            try:
                target = int(channel[len(DIRECT_PREFIX):])
            except ValueError:
                return
            await self._deliver_to_client(target, message)

    # ── HTTP handler ──────────────────────────────────────────

    def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        parts = urlsplit(request.path)
        path = parts.path
        json_headers = Headers([("Content-Type", "application/json")])

        if path == "/health":
            body = json.dumps({"connected_clients": self.clients.count()}).encode("utf-8")
            return Response(200, "OK", json_headers, body)

        if path == "/channels":
            body = json.dumps({"channels": self.clients.channels()}).encode("utf-8")
            return Response(200, "OK", json_headers, body)

        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/"):-len("/subscribers")])
            body = json.dumps(
                {"channel": name, "subscribers": self.clients.subscribers(name)}
            ).encode("utf-8")
            return Response(200, "OK", json_headers, body)

        if path == "/messages":
            query = parse_qs(parts.query)
            limit = query.get("limit", ["50"])[0]
            offset = query.get("offset", ["0"])[0]
            messages = self.store.query(limit=limit, offset=offset)
            body = json.dumps({"messages": messages}).encode("utf-8")
            return Response(200, "OK", json_headers, body)

        return None

    # ── WebSocket handler ──────────────────────────────────────

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        client_id = await self.broker.next_client_id()
        self.clients.register(websocket, client_id)
        await self.broker.register_client(client_id, self.instance_id)
        try:
            await websocket.send(
                encode_message(
                    {
                        "type": "system",
                        "payload": {"client_id": client_id, "message": "connected"},
                        "timestamp": utcnow(),
                    }
                )
            )
            async for raw in websocket:
                try:
                    message = decode_message(raw)
                except (ValueError, TypeError):
                    continue
                await self._handle_message(client_id, message)
        finally:
            self.clients.unregister(client_id)
            await self.broker.unregister_client(client_id)

    async def _handle_message(self, sender_id: int, message: Dict[str, Any]) -> None:
        mtype = message.get("type")
        payload = message.get("payload") or {}
        timestamp = message.get("timestamp") or utcnow()

        if mtype == "subscribe":
            channel = payload.get("channel") or message.get("channel")
            if channel:
                self.clients.subscribe(sender_id, channel)
                await self.broker.subscribe_client(sender_id, channel)
            return

        if mtype == "unsubscribe":
            channel = payload.get("channel") or message.get("channel")
            if channel:
                self.clients.unsubscribe(sender_id, channel)
                await self.broker.unsubscribe_client(sender_id, channel)
            return

        if mtype == "broadcast":
            outgoing = {"type": "broadcast", "payload": payload, "timestamp": timestamp}
            outgoing["payload"]["sender_id"] = sender_id
            channel = message.get("channel")
            if channel:
                outgoing["channel"] = channel
                await self._publish_and_store(CHANNEL_PREFIX + channel, outgoing)
            else:
                await self._publish_and_store(BROADCAST_CHANNEL, outgoing)
        elif mtype == "direct":
            target = payload.get("client_id")
            if target is None:
                return
            outgoing = {"type": "direct", "payload": payload, "timestamp": timestamp}
            outgoing["payload"]["sender_id"] = sender_id
            await self._publish_and_store(DIRECT_PREFIX + str(target), outgoing)

    async def _publish_and_store(self, redis_channel: str, message: Dict[str, Any]) -> None:
        self.store.save(message)
        await self.broker.publish(redis_channel, json.dumps(message))

    # ── Local delivery (invoked by the worker) ────────────────

    async def broadcast(self, message: Dict[str, Any]) -> None:
        encoded = encode_message(message)
        for websocket in self.clients.snapshot().values():
            try:
                await websocket.send(encoded)
            except Exception:
                continue

    async def send_to_channel(self, channel: str, message: Dict[str, Any]) -> None:
        encoded = encode_message(message)
        for client_id in self.clients.subscribers(channel):
            websocket = self.clients.get(client_id)
            if websocket is None:
                continue
            try:
                await websocket.send(encoded)
            except Exception:
                continue

    async def _deliver_to_client(self, client_id: int, message: Dict[str, Any]) -> None:
        websocket = self.clients.get(client_id)
        if websocket is None:
            return
        try:
            await websocket.send(encode_message(message))
        except Exception:
            pass


async def main() -> None:
    server = NotificationServer()
    await server.start(host="127.0.0.1", port=8765)
    print(f"notification server listening on ws://127.0.0.1:{server.port}")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
