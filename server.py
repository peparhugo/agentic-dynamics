"""
WebSocket-based notification server backed by Redis pub/sub and SQLite.

Features:
- Accepts WebSocket connections and assigns each client a unique ID.
- Broadcasts a message to ALL connected clients.
- Routes direct messages to a single target client.
- Sends system messages (e.g. the assigned client id) to clients.
- Handles client disconnect with clean registry removal.
- Exposes a REST endpoint GET /health reporting the connected client count.
- Supports channel-based subscriptions: clients subscribe/unsubscribe to
  named channels and messages carrying a 'channel' field are delivered only
  to that channel's subscribers. Messages without a channel broadcast to all.
- Exposes REST endpoints GET /channels and GET /channels/{name}/subscribers.

Redis pub/sub backbone:
- Every routed message is published to a Redis pub/sub channel. Each server
  instance subscribes to the backbone and delivers messages to its own
  connected clients, so multiple server instances can share the same broker.
- Client connection state and channel subscriptions are stored in Redis, so
  they survive server restarts and are visible to every instance.

Persistence:
- Every routed message is stored in SQLite (messages table) for history.
- REST endpoint GET /messages?limit=50&offset=0 returns stored messages.

All messages use the JSON envelope:
    {"type": str, "payload": dict, "timestamp": str}

Supported message types: 'broadcast', 'direct', 'system', 'subscribe',
'unsubscribe'.

Tech: websockets library, asyncio, Redis pub/sub, SQLite.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

import broker
from broker import (
    BROADCAST_CHANNEL,
    CHANNELS_KEY,
    CHANNEL_PREFIX,
    DIRECT_PREFIX,
    SUBSCRIBE_PATTERN,
    channel_redis_channel,
    client_channels_key,
    client_state_key,
    create_redis_client,
    decode,
    direct_redis_channel,
    sub_key,
)
from storage import MessageStore

logger = logging.getLogger("notification_server")


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a message using the canonical JSON envelope."""
    return {"type": msg_type, "payload": payload, "timestamp": utc_now()}


def serialize(message: dict) -> str:
    """Serialize a message envelope to JSON text."""
    return json.dumps(message)


class ClientRegistry:
    """
    Thread-safe registry of connected WebSocket clients.

    Maps a unique client id to its websocket. Access is guarded by an
    asyncio.Lock so concurrent tasks can safely add/remove/query clients.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    async def add(self, client_id: str, websocket: ServerConnection) -> None:
        async with self._lock:
            self._clients[client_id] = websocket

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def get(self, client_id: str) -> Optional[ServerConnection]:
        async with self._lock:
            return self._clients.get(client_id)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def snapshot(self) -> dict[str, ServerConnection]:
        async with self._lock:
            return dict(self._clients)


async def _safe_close(obj: Any) -> None:
    """Close a redis/asyncio or fakeredis object regardless of its close API."""
    close = getattr(obj, "aclose", None) or getattr(obj, "close", None)
    if close is None:
        return
    result = close()
    if asyncio.iscoroutine(result):
        await result


class NotificationServer:
    """
    WebSocket notification server with an embedded REST /health endpoint.

    The /health endpoint is served by the same listener through
    websockets' ``process_request`` hook, so a single asyncio event loop
    handles both WebSocket and plain HTTP traffic.

    Message distribution uses a Redis pub/sub backbone: messages are published
    to Redis channels and delivered to the connected clients of every server
    instance that subscribes to the backbone. Connection state, client ids and
    channel subscriptions live in Redis, so they survive server restarts and
    are shared between multiple instances using the same Redis.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        redis_client: Any = None,
        database_url: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self.instance_id = secrets.token_hex(8)
        self.redis = redis_client if redis_client is not None else create_redis_client()
        self._owns_redis = redis_client is None
        self.store = MessageStore(database_url)
        self._server: Optional[Server] = None
        self._id_counter = 0
        self._id_lock = asyncio.Lock()
        self._pubsub = None
        self._listener_task: Optional[asyncio.Task] = None

    # ── Client id allocation ──────────────────────────────────────

    async def _next_id(self) -> str:
        """Allocate a globally unique client id using Redis INCR."""
        try:
            n = await self.redis.incr(broker.ID_COUNTER_KEY)
            return f"client-{n}"
        except Exception:
            async with self._id_lock:
                self._id_counter += 1
                return f"client-{self._id_counter}"

    # ── Client connection state ───────────────────────────────────

    async def _set_client_state(self, client_id: str) -> None:
        state = {
            "client_id": client_id,
            "connected": True,
            "connected_at": utc_now(),
            "server": self.instance_id,
        }
        await self.redis.set(client_state_key(client_id), json.dumps(state))

    async def _clear_client_state(self, client_id: str) -> None:
        await self.redis.delete(client_state_key(client_id))

    async def client_state(self, client_id: str) -> Optional[dict]:
        """Return the Redis-backed connection state for a client, if any."""
        raw = await self.redis.get(client_state_key(client_id))
        if raw is None:
            return None
        try:
            return json.loads(decode(raw))
        except (ValueError, TypeError):
            return None

    # ── Channel subscriptions ─────────────────────────────────────

    async def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a named channel (stored in Redis)."""
        if not isinstance(channel, str) or not channel:
            return
        async with self.redis.pipeline() as pipe:
            pipe.sadd(sub_key(channel), client_id)
            pipe.sadd(CHANNELS_KEY, channel)
            pipe.sadd(client_channels_key(client_id), channel)
            await pipe.execute()

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a named channel."""
        if not isinstance(channel, str) or not channel:
            return
        await self.redis.srem(sub_key(channel), client_id)
        await self.redis.srem(client_channels_key(client_id), channel)
        await self._prune_channel(channel)

    async def channel_subscribers(self, channel: str) -> set[str]:
        """Return the set of client ids subscribed to a channel (may be empty)."""
        members = await self.redis.smembers(sub_key(channel))
        return {decode(m) for m in members}

    async def channel_counts(self) -> dict[str, int]:
        """Return a mapping of active channel name to subscriber count."""
        names = await self.redis.smembers(CHANNELS_KEY)
        counts: dict[str, int] = {}
        for name in names:
            name = decode(name)
            counts[name] = await self.redis.scard(sub_key(name))
        return counts

    async def _prune_channel(self, channel: str) -> None:
        """Drop a channel from the active-channel set when it is empty."""
        if await self.redis.scard(sub_key(channel)) == 0:
            await self.redis.srem(CHANNELS_KEY, channel)

    async def _remove_client_channels(self, client_id: str) -> None:
        """Remove a client from every channel, dropping channels left empty."""
        channels = await self.redis.smembers(client_channels_key(client_id))
        for channel in channels:
            channel = decode(channel)
            await self.redis.srem(sub_key(channel), client_id)
            await self._prune_channel(channel)
        await self.redis.delete(client_channels_key(client_id))

    # ── Sending helpers ───────────────────────────────────────────

    async def _send(self, websocket: ServerConnection, message: dict) -> bool:
        """Send a message envelope to a single websocket.

        Returns True on success and False if the connection is gone.
        """
        try:
            await websocket.send(serialize(message))
            return True
        except (ConnectionClosed, ConnectionError, OSError):
            return False

    async def _broadcast_local(self, message: dict) -> int:
        """Deliver a message envelope to every locally connected client."""
        delivered = 0
        for client_id, websocket in (await self.registry.snapshot()).items():
            if await self._send(websocket, message):
                delivered += 1
            else:
                await self.registry.remove(client_id)
        return delivered

    async def _send_to_local_channel(self, channel: str, message: dict) -> int:
        """Deliver a message envelope to local clients subscribed to a channel."""
        snapshot = await self.registry.snapshot()
        delivered = 0
        for raw_id in await self.channel_subscribers(channel):
            client_id = decode(raw_id)
            websocket = snapshot.get(client_id)
            if websocket is None:
                continue
            if await self._send(websocket, message):
                delivered += 1
            else:
                await self.registry.remove(client_id)
        return delivered

    async def _send_direct_local(self, client_id: str, message: dict) -> int:
        """Deliver a message envelope to a single local client."""
        websocket = await self.registry.get(client_id)
        if websocket is None:
            return 0
        if not await self._send(websocket, message):
            await self.registry.remove(client_id)
            return 0
        return 1

    async def _deliver_local(self, redis_channel: str, message: dict) -> int:
        """Deliver a message to local clients based on the Redis channel."""
        if redis_channel == BROADCAST_CHANNEL:
            return await self._broadcast_local(message)
        if redis_channel.startswith(CHANNEL_PREFIX):
            channel = redis_channel[len(CHANNEL_PREFIX):]
            return await self._send_to_local_channel(channel, message)
        if redis_channel.startswith(DIRECT_PREFIX):
            target = redis_channel[len(DIRECT_PREFIX):]
            return await self._send_direct_local(target, message)
        return 0

    async def _publish(self, redis_channel: str, message: dict, deliver_local: bool) -> int:
        """Publish a message to the Redis backbone.

        Each worker subscribes to the backbone pattern, so every instance
        (including this one) receives the published message. The origin marker
        lets workers skip their own messages when local delivery was already
        performed synchronously.

        Returns the number of local clients delivered to when local delivery
        was requested.
        """
        wrapper = {"origin": self.instance_id, "message": message}
        await self.redis.publish(redis_channel, json.dumps(wrapper))
        if deliver_local:
            return await self._deliver_local(redis_channel, message)
        return 0

    def _channel_for_redis_channel(self, redis_channel: str) -> str:
        if redis_channel.startswith(CHANNEL_PREFIX):
            return redis_channel[len(CHANNEL_PREFIX):]
        return ""

    async def broadcast(self, message: dict) -> None:
        """Publish a message envelope to every connected client."""
        self.store.add(
            "", message.get("type", ""), message.get("payload", {}), message.get("timestamp", utc_now())
        )
        await self._publish(BROADCAST_CHANNEL, message, deliver_local=True)

    async def send_direct(self, client_id: str, message: dict) -> bool:
        """Deliver a message envelope to a single client.

        Returns True if the target was found (locally or on another instance)
        and the message was routed, otherwise False.
        """
        if await self.registry.get(client_id) is not None:
            self.store.add(
                "", message.get("type", ""), message.get("payload", {}), message.get("timestamp", utc_now())
            )
            await self._publish(direct_redis_channel(client_id), message, deliver_local=True)
            return True
        if await self.redis.exists(client_state_key(client_id)):
            self.store.add(
                "", message.get("type", ""), message.get("payload", {}), message.get("timestamp", utc_now())
            )
            await self._publish(direct_redis_channel(client_id), message, deliver_local=False)
            return True
        return False

    async def send_to_channel(self, channel: str, message: dict) -> int:
        """Deliver a message envelope to every subscriber of a channel.

        Returns the number of local clients the message was sent to.
        """
        self.store.add(
            channel, message.get("type", ""), message.get("payload", {}), message.get("timestamp", utc_now())
        )
        return await self._publish(channel_redis_channel(channel), message, deliver_local=True)

    @property
    async def client_count(self) -> int:
        return await self.registry.count()

    # ── Redis backbone listener ───────────────────────────────────

    async def _redis_listener(self) -> None:
        """Consume messages from the Redis backbone and deliver locally."""
        try:
            while True:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.1
                )
                if message is None:
                    continue
                if message["type"] not in ("message", "pmessage"):
                    continue
                redis_channel = decode(message["channel"])
                data = decode(message["data"])
                try:
                    wrapper = json.loads(data)
                except (ValueError, TypeError):
                    continue
                if not isinstance(wrapper, dict):
                    continue
                if wrapper.get("origin") == self.instance_id:
                    continue
                envelope = wrapper.get("message")
                if not isinstance(envelope, dict):
                    continue
                self.store.add(
                    self._channel_for_redis_channel(redis_channel),
                    envelope.get("type", ""),
                    envelope.get("payload", {}),
                    envelope.get("timestamp", utc_now()),
                )
                await self._deliver_local(redis_channel, envelope)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("redis backbone listener error")

    async def _start_redis_listener(self) -> None:
        self._pubsub = self.redis.pubsub()
        await self._pubsub.psubscribe(SUBSCRIBE_PATTERN)
        self._listener_task = asyncio.create_task(self._redis_listener())

    # ── Inbound client messages ───────────────────────────────────

    async def _handle_client_message(self, client_id: str, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            await self.send_direct(
                client_id, build_message("system", {"error": "invalid json"})
            )
            return

        msg_type = data.get("type")
        payload = data.get("payload")
        if not isinstance(msg_type, str):
            await self.send_direct(
                client_id, build_message("system", {"error": "malformed message"})
            )
            return
        if not isinstance(payload, dict):
            if msg_type in ("subscribe", "unsubscribe"):
                payload = {}
            else:
                await self.send_direct(
                    client_id,
                    build_message("system", {"error": "malformed message"}),
                )
                return

        if msg_type == "subscribe":
            channel = self._resolve_channel(data, payload)
            if channel is None:
                await self.send_direct(
                    client_id,
                    build_message(
                        "system", {"error": "subscribe requires a 'channel'"}
                    ),
                )
                return
            await self.subscribe(client_id, channel)
        elif msg_type == "unsubscribe":
            channel = self._resolve_channel(data, payload)
            if channel is None:
                await self.send_direct(
                    client_id,
                    build_message(
                        "system", {"error": "unsubscribe requires a 'channel'"}
                    ),
                )
                return
            await self.unsubscribe(client_id, channel)
        elif msg_type == "broadcast":
            channel = self._resolve_channel(data, payload)
            if channel is not None:
                await self.send_to_channel(channel, build_message("broadcast", payload))
            else:
                await self.broadcast(build_message("broadcast", payload))
        elif msg_type == "direct":
            target = payload.get("target")
            if not isinstance(target, str) or not target:
                await self.send_direct(
                    client_id,
                    build_message(
                        "system", {"error": "direct message requires a 'target'"}
                    ),
                )
                return
            await self.send_direct(target, build_message("direct", payload))
        elif msg_type == "system":
            # System messages are server-generated; ignore client attempts.
            return
        else:
            await self.send_direct(
                client_id,
                build_message("system", {"error": f"unknown type: {msg_type}"}),
            )

    @staticmethod
    def _resolve_channel(data: dict, payload: dict) -> Optional[str]:
        """Extract a channel name from a message, top-level or payload."""
        channel = data.get("channel")
        if isinstance(channel, str) and channel:
            return channel
        channel = payload.get("channel")
        if isinstance(channel, str) and channel:
            return channel
        return None

    # ── Per-connection handler ────────────────────────────────────

    async def handler(self, websocket: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        client_id = await self._next_id()
        await self.registry.add(client_id, websocket)
        await self._set_client_state(client_id)
        logger.info("client %s connected", client_id)
        try:
            await self._send(
                websocket,
                build_message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw in websocket:
                await self._handle_client_message(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.registry.remove(client_id)
            await self._remove_client_channels(client_id)
            await self._clear_client_state(client_id)
            logger.info("client %s disconnected", client_id)

    # ── REST endpoints ────────────────────────────────────────────

    def _json_response(
        self, body: dict, status: int = 200, reason: str = "OK"
    ) -> Response:
        encoded = json.dumps(body).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(encoded)),
            }
        )
        return Response(status, reason, headers, encoded)

    @staticmethod
    def _clean_path(request: Request) -> str:
        return urlparse(request.path).path

    @staticmethod
    def _query_params(request: Request) -> dict[str, list[str]]:
        return parse_qs(urlparse(request.path).query)

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Optional[Response]:
        path = self._clean_path(request)
        if path == "/health":
            return self._json_response(
                {"status": "ok", "clients": await self.registry.count()}
            )
        if path == "/channels":
            return self._json_response({"channels": await self.channel_counts()})
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")])
            if name not in await self.channel_counts():
                return self._json_response(
                    {"error": "channel not found"}, status=404, reason="Not Found"
                )
            subscribers = sorted(await self.channel_subscribers(name))
            return self._json_response(
                {"channel": name, "subscribers": subscribers}
            )
        if path == "/messages":
            params = self._query_params(request)
            limit = int(params.get("limit", ["50"])[0])
            offset = int(params.get("offset", ["0"])[0])
            messages = self.store.list(limit=limit, offset=offset)
            return self._json_response(
                {
                    "messages": messages,
                    "total": self.store.count(),
                    "limit": limit,
                    "offset": offset,
                }
            )
        return None

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Bind the listener and start accepting connections."""
        if self._server is not None:
            return
        self._server = await serve(
            self.handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        self.port = self.bound_port
        await self._start_redis_listener()

    @property
    def bound_port(self) -> int:
        if self._server is not None and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self.port

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.bound_port}"

    async def close(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except (asyncio.CancelledError, Exception):
                pass
            self._listener_task = None
        if self._pubsub is not None:
            try:
                await _safe_close(self._pubsub)
            except Exception:
                pass
            self._pubsub = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._owns_redis:
            try:
                await _safe_close(self.redis)
            except Exception:
                pass
        self.store.close()


async def _run(host: str, port: int) -> None:
    server = NotificationServer(host, port)
    await server.start()
    print(f"Notification server listening on {server.url}")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    asyncio.run(_run(host, port))


if __name__ == "__main__":
    main()
