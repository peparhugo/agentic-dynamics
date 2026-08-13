"""
WebSocket-based notification server.

Core features:
- Accept WebSocket connections from clients.
- Assign each client a unique ID on connect.
- Broadcast a message to ALL connected clients.
- Channel-based subscriptions: clients subscribe to named channels and receive
  only the messages routed to those channels.
- Handle client disconnect (clean removal, including channel memberships).
- REST endpoints: GET /health, GET /channels, GET /channels/{name}/subscribers,
  GET /messages.

Redis pub/sub backbone:
- When a RedisBackend is configured (REDIS_URL env var) every relayed message
  is published to a shared Redis channel.  Each server instance runs a worker
  that subscribes to that channel and delivers messages to its locally
  connected clients, so multiple server instances can share the same backbone.
- Client connection state (connected client ids, channel memberships) is
  mirrored into Redis and therefore survives server restarts.

Persistence:
- When a MessageStore is configured (DATABASE_URL env var) every relayed
  message is stored in SQLite and can be fetched via GET /messages.

Message format (all messages are JSON):
    {"type": str, "payload": dict, "timestamp": str}
Supported types: "broadcast", "direct", "subscribe", "unsubscribe", "system".

Protocol (client -> server):
- {"type": "broadcast", "payload": {...}}    -> relayed to every connected client.
- {"type": "broadcast", "channel": "name", "payload": {...}} -> relayed only to
  subscribers of the named channel (channel may also live inside payload).
- {"type": "direct", "target_id": "...", "payload": {...}} -> delivered to one client.
- {"type": "subscribe", "channel": "name"}   -> subscribe sender to a channel.
- {"type": "unsubscribe", "channel": "name"} -> unsubscribe sender from a channel.
- {"type": "system", ...}                    -> ignored (server-only).

Protocol (server -> client):
- On connect, the new client receives:
    {"type": "system", "payload": {"event": "connect", "client_id": "...",
     "connected_clients": N}, "timestamp": "..."}
- On disconnect, every remaining client receives a matching "disconnect" event.
- Errors are delivered back to the offending client as a "system" error event.

Uses the `websockets` library (asyncio implementation) and a lock-guarded
client registry that is safe to use across asyncio tasks/threads.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from message_store import MessageStore
from redis_backend import RedisBackend


def now_iso() -> str:
    """Current UTC time as an ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a message conforming to the shared JSON schema."""
    return {"type": msg_type, "payload": payload, "timestamp": now_iso()}


class ClientRegistry:
    """
    Thread-safe registry mapping unique client IDs to websocket connections.

    Access is guarded by an asyncio.Lock so concurrent handlers (and external
    threads using the same event loop) never observe partial state.

    When a RedisBackend is provided the connection state (client ids and
    channel memberships) is mirrored into Redis so it survives restarts and
    is shared across server instances.  The live websocket objects always stay
    in memory (they cannot be stored in Redis).
    """

    def __init__(
        self,
        backend: RedisBackend | None = None,
        server_id: str | None = None,
    ) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self.backend = backend
        self.server_id = server_id or uuid.uuid4().hex

    async def add(self, client_id: str, websocket: ServerConnection) -> None:
        async with self._lock:
            self._clients[client_id] = websocket
        if self.backend is not None:
            await self.backend.register_client(client_id, self.server_id)

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)
        if self.backend is not None:
            await self.backend.add_channel_member(client_id, channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            members = self._channels.get(channel)
            if members is not None:
                members.discard(client_id)
                if not members:
                    del self._channels[channel]
        if self.backend is not None:
            await self.backend.remove_channel_member(client_id, channel)

    async def channel_members(self, channel: str) -> set[str]:
        async with self._lock:
            return set(self._channels.get(channel, set()))

    async def channels_snapshot(self) -> dict[str, set[str]]:
        async with self._lock:
            return {ch: set(members) for ch, members in self._channels.items()}

    async def remove_from_all_channels(self, client_id: str) -> None:
        async with self._lock:
            for channel in list(self._channels.keys()):
                members = self._channels[channel]
                members.discard(client_id)
                if not members:
                    del self._channels[channel]
        if self.backend is not None:
            for channel in await self.backend.global_channels():
                await self.backend.remove_channel_member(client_id, channel)

    async def remove(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            removed = self._clients.pop(client_id, None)
        if removed is not None and self.backend is not None:
            await self.backend.unregister_client(client_id)
        return removed

    async def get(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def contains(self, client_id: str) -> bool:
        async with self._lock:
            return client_id in self._clients

    async def global_contains(self, client_id: str) -> bool:
        """Whether *client_id* is known anywhere (local or another instance)."""
        if self.backend is not None:
            return await self.backend.client_exists(client_id)
        return await self.contains(client_id)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def ids(self) -> list[str]:
        async with self._lock:
            return list(self._clients.keys())

    async def snapshot(self) -> dict[str, ServerConnection]:
        async with self._lock:
            return dict(self._clients)


class NotificationServer:
    """Handles websocket sessions, message dispatch and the REST endpoints."""

    def __init__(
        self,
        registry: ClientRegistry | None = None,
        backend: RedisBackend | None = None,
        store: MessageStore | None = None,
        server_id: str | None = None,
    ) -> None:
        self.server_id = server_id or uuid.uuid4().hex
        self.backend = backend
        self.store = store
        self.registry = registry or ClientRegistry(
            backend=backend, server_id=self.server_id
        )
        self._next_id = 0
        self._id_lock = asyncio.Lock()
        self._broker_task: asyncio.Task | None = None
        self._pubsub = None

    # ── Redis backbone lifecycle ────────────────────────────────────

    async def start_backend(self) -> None:
        """Subscribe the local worker to the Redis backbone."""
        if self.backend is None:
            return
        self._pubsub = self.backend.pubsub()
        await self._pubsub.subscribe(self.backend.messages_channel)
        self._broker_task = asyncio.create_task(self._broker_loop())

    async def stop_backend(self) -> None:
        """Stop the local Redis worker."""
        if self._broker_task is not None:
            self._broker_task.cancel()
            try:
                await self._broker_task
            except asyncio.CancelledError:
                pass
            self._broker_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe()
            except Exception:
                pass
            await self._pubsub.close()
            self._pubsub = None

    async def _broker_loop(self) -> None:
        while True:
            try:
                async for raw in self._pubsub.listen():
                    if raw["type"] != "message":
                        continue
                    try:
                        envelope = json.loads(raw["data"])
                    except (json.JSONDecodeError, TypeError):
                        continue
                    await self._handle_broker_envelope(envelope)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(0.05)

    async def _handle_broker_envelope(self, envelope: dict) -> None:
        kind = envelope.get("kind")
        message = envelope.get("message")
        if kind == "broadcast":
            await self._broadcast_local(message)
        elif kind == "channel":
            await self._deliver_to_channel_local(envelope.get("channel"), message)
        elif kind == "direct":
            await self._deliver_direct_local(envelope.get("target_id"), message)

    # ── Session lifecycle ───────────────────────────────────────────

    async def _assign_id(self) -> str:
        if self.backend is not None:
            return await self.backend.next_client_id()
        async with self._id_lock:
            self._next_id += 1
            return str(self._next_id)

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Session handler: register, notify, relay messages, clean up."""
        client_id = await self._assign_id()
        await self.registry.add(client_id, websocket)
        try:
            await self._send_connect_notice(client_id, websocket)
            async for raw in websocket:
                await self._dispatch(client_id, websocket, raw)
        except ConnectionClosed:
            pass
        finally:
            await self._shutdown_client(client_id)

    async def _send_connect_notice(self, client_id: str, websocket) -> None:
        count = await self.registry.count()
        message = build_message(
            "system",
            {"event": "connect", "client_id": client_id, "connected_clients": count},
        )
        try:
            await websocket.send(json.dumps(message))
        except ConnectionClosed:
            pass

    async def _shutdown_client(self, client_id: str) -> None:
        removed = await self.registry.remove(client_id)
        if removed is None:
            return
        await self.registry.remove_from_all_channels(client_id)
        count = await self.registry.count()
        message = build_message(
            "system",
            {"event": "disconnect", "client_id": client_id, "connected_clients": count},
        )
        await self.broadcast(message)

    # ── Message dispatch ────────────────────────────────────────────

    async def _persist(self, channel: str, message: dict) -> None:
        if self.store is None:
            return
        try:
            await self.store.record(
                channel, message["type"], message["payload"], message["timestamp"]
            )
        except Exception:
            pass

    async def _dispatch(self, sender_id: str, websocket, raw) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(
                sender_id, "invalid JSON message", target_id=None
            )
            return

        if not isinstance(data, dict):
            await self._send_error(sender_id, "message must be a JSON object")
            return

        msg_type = data.get("type")
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            await self._send_error(sender_id, "payload must be a JSON object")
            return

        if msg_type == "broadcast":
            channel = data.get("channel")
            if not isinstance(channel, str) or not channel.strip():
                channel = payload.get("channel")
            if isinstance(channel, str) and channel.strip():
                channel = channel.strip()
                message = build_message("broadcast", payload)
                await self._persist(channel, message)
                await self._broadcast_to_channel(channel, message)
            else:
                message = build_message("broadcast", payload)
                await self._persist("", message)
                await self.broadcast(message)
        elif msg_type == "direct":
            target_id = data.get("target_id") or payload.get("target_id")
            await self._send_direct(sender_id, target_id, payload)
        elif msg_type == "subscribe":
            await self._subscribe(sender_id, data, payload)
        elif msg_type == "unsubscribe":
            await self._unsubscribe(sender_id, data, payload)
        elif msg_type == "system":
            # System messages are generated by the server only.
            pass
        else:
            await self._send_error(sender_id, f"unsupported message type: {msg_type!r}")

    async def _subscribe(self, sender_id: str, data: dict, payload: dict) -> None:
        channel = data.get("channel") or payload.get("channel")
        if not isinstance(channel, str) or not channel.strip():
            await self._send_error(
                sender_id, "subscribe requires a non-empty channel name"
            )
            return
        await self.registry.subscribe(sender_id, channel.strip())

    async def _unsubscribe(self, sender_id: str, data: dict, payload: dict) -> None:
        channel = data.get("channel") or payload.get("channel")
        if not isinstance(channel, str) or not channel.strip():
            await self._send_error(
                sender_id, "unsubscribe requires a non-empty channel name"
            )
            return
        await self.registry.unsubscribe(sender_id, channel.strip())

    async def _send_direct(self, sender_id: str, target_id, payload: dict) -> None:
        if not isinstance(target_id, str) or not target_id:
            await self._send_error(sender_id, "direct message requires a target_id")
            return
        if not await self.registry.global_contains(target_id):
            await self._send_error(
                sender_id, "target not found", target_id=target_id
            )
            return
        message = build_message("direct", payload)
        await self._persist("", message)
        if self.backend is not None:
            await self.backend.publish(
                {"kind": "direct", "target_id": target_id, "message": message}
            )
            return
        await self._deliver_direct_local(target_id, message)

    async def _send_error(self, sender_id: str, message: str, target_id=None) -> None:
        payload = {"event": "error", "message": message}
        if target_id is not None:
            payload["target_id"] = target_id
        ws = await self.registry.get(sender_id)
        if ws is None:
            return
        try:
            await ws.send(json.dumps(build_message("system", payload)))
        except ConnectionClosed:
            await self.registry.remove(sender_id)

    # ── Outgoing ────────────────────────────────────────────────────

    async def broadcast(self, message: dict, exclude: set[str] | None = None) -> int:
        """Route a broadcast: via Redis when a backbone is present, else local."""
        if self.backend is not None:
            await self.backend.publish({"kind": "broadcast", "message": message})
            return 0
        return await self._broadcast_local(message, exclude)

    async def _broadcast_local(self, message: dict, exclude: set[str] | None = None) -> int:
        """Send *message* to every locally connected client. Returns count delivered."""
        exclude = exclude or set()
        encoded = json.dumps(message)
        delivered = 0
        for client_id, websocket in (await self.registry.snapshot()).items():
            if client_id in exclude:
                continue
            try:
                await websocket.send(encoded)
                delivered += 1
            except ConnectionClosed:
                await self.registry.remove(client_id)
        return delivered

    async def _broadcast_to_channel(self, channel: str, message: dict) -> int:
        """Route a channel message: via Redis when a backbone is present, else local."""
        if self.backend is not None:
            await self.backend.publish(
                {"kind": "channel", "channel": channel, "message": message}
            )
            return 0
        return await self._deliver_to_channel_local(channel, message)

    async def _deliver_to_channel_local(self, channel: str, message: dict) -> int:
        """Send *message* to locally connected subscribers of *channel*."""
        encoded = json.dumps(message)
        delivered = 0
        for client_id in await self.registry.channel_members(channel):
            websocket = await self.registry.get(client_id)
            if websocket is None:
                await self.registry.unsubscribe(client_id, channel)
                continue
            try:
                await websocket.send(encoded)
                delivered += 1
            except ConnectionClosed:
                await self.registry.remove(client_id)
                await self.registry.unsubscribe(client_id, channel)
        return delivered

    async def _deliver_direct_local(self, target_id: str, message: dict) -> int:
        """Deliver *message* to the local websocket for *target_id*."""
        ws = await self.registry.get(target_id)
        if ws is None:
            return 0
        try:
            await ws.send(json.dumps(message))
            return 1
        except ConnectionClosed:
            await self.registry.remove(target_id)
            return 0

    # ── REST endpoints ──────────────────────────────────────────────

    async def _json_response(self, status: int, body: dict) -> Response:
        encoded = json.dumps(body).encode("utf-8")
        headers = Headers(
            {"Content-Type": "application/json", "Content-Length": str(len(encoded))}
        )
        return Response(status, "OK", headers, encoded)

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Intercept plain HTTP requests for the REST endpoints."""
        parsed = urlparse(request.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/health":
            count = await self.registry.count()
            return await self._json_response(
                200, {"status": "ok", "connected_clients": count}
            )
        if path == "/channels" or path == "/channels/":
            channels = await self.registry.channels_snapshot()
            return await self._json_response(
                200,
                {
                    "channels": [
                        {
                            "name": name,
                            "subscriber_count": len(members),
                            "subscribers": sorted(members),
                        }
                        for name, members in sorted(channels.items())
                    ]
                },
            )
        if path.startswith("/channels/"):
            segments = [seg for seg in path[len("/channels/"):].split("/") if seg]
            if not segments:
                return await self.process_request(connection, request)
            name = segments[0]
            members = await self.registry.channel_members(name)
            return await self._json_response(
                200,
                {"channel": name, "subscribers": sorted(members)},
            )
        if path == "/messages":
            if self.store is None:
                return await self._json_response(200, {"messages": [], "total": 0})
            try:
                limit = int(query.get("limit", ["50"])[0])
            except (TypeError, ValueError):
                limit = 50
            try:
                offset = int(query.get("offset", ["0"])[0])
            except (TypeError, ValueError):
                offset = 0
            limit = max(0, min(limit, 1000))
            offset = max(0, offset)
            messages = await self.store.list_messages(limit=limit, offset=offset)
            total = await self.store.count()
            return await self._json_response(
                200, {"messages": messages, "total": total}
            )
        return None


class NotificationApp:
    """Wraps a websockets server bound to a host/port for easy (test) control."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        notifier: NotificationServer | None = None,
        backend: RedisBackend | None = None,
        store: MessageStore | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.backend = backend
        self.store = store
        self.notifier = notifier or NotificationServer(backend=backend, store=store)
        self.server = None

    async def start(self) -> "NotificationApp":
        if self.backend is not None:
            await self.notifier.start_backend()
        self.server = await serve(
            self.notifier.handle_client,
            self.host,
            self.port,
            process_request=self.notifier.process_request,
        )
        if self.port == 0:
            self.port = self.server.sockets[0].getsockname()[1]
        return self

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        if self.backend is not None:
            await self.notifier.stop_backend()


async def main(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Entry point: run the notification server until interrupted."""
    backend = None
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        backend = RedisBackend(redis_url)
        await backend.connect()

    store = None
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        store = MessageStore(database_url)
        await store.connect()

    notifier = NotificationServer(backend=backend, store=store)
    try:
        if backend is not None:
            await notifier.start_backend()
        async with serve(
            notifier.handle_client,
            host,
            port,
            process_request=notifier.process_request,
        ) as server:
            await server.serve_forever()
    finally:
        if backend is not None:
            await notifier.stop_backend()
            await backend.close()
        if store is not None:
            await store.close()


if __name__ == "__main__":
    asyncio.run(main())
