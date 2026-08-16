"""Transport-agnostic notification server.

Clients connect over a pluggable :term:`transport` (WebSocket by default),
are assigned a unique ID, and can exchange JSON messages. The core
notification logic knows nothing about the wire protocol — it interacts with
clients exclusively through a :class:`BaseTransport` implementation. The
server also exposes a small REST API (``GET /health``, ``GET /channels``,
``GET /messages``).

Message distribution is backed by Redis pub/sub when ``REDIS_URL`` (or an
explicit ``redis`` client) is configured. In that mode:

* The server publishes an envelope to a shared Redis pub/sub channel.
* A worker coroutine subscribes to that channel and delivers messages to the
  locally connected clients.
* Client connection state (which instance owns a client and which channels a
  client is subscribed to) is stored in Redis so it survives restarts and is
  visible across multiple server instances.

Without Redis, the server falls back to the original in-process delivery
behavior, preserving backwards compatibility.

All messages are persisted to SQLite for history and exposed via
``GET /messages``.
"""

import asyncio
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, unquote

from websockets.datastructures import Headers
from websockets.http11 import Response

from transport import BaseTransport, WebSocketTransport

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")

# The single Redis pub/sub channel used as the message backbone.
REDIS_CHANNEL = "notifications"

# Redis key templates for client connection state.
KEY_CLIENT_INSTANCE = "notif:client:{client_id}"
KEY_CHANNEL_SUBS = "notif:subs:{channel}"
KEY_CLIENT_SUBS = "notif:client_subs:{client_id}"
KEY_RATE_LIMIT = "notif:ratelimit:{client_id}"

# Registry of available transports, keyed by the name used in the
# ``TRANSPORT`` environment variable. New transports register themselves here
# without any change to the core notification logic.
_TRANSPORT_REGISTRY: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
    "ws": WebSocketTransport,
}


def register_transport(name: str, transport_cls: type[BaseTransport]) -> None:
    """Register a transport implementation under ``name``."""
    _TRANSPORT_REGISTRY[name] = transport_cls


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _resolve_db_path(url: str) -> str:
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url


class NotificationServer:
    """An asyncio notification server with a pluggable transport.

    The client registry lives inside the transport; the server tracks
    subscriptions and message state. Because asyncio runs all coroutines and
    callbacks on a single event loop, every read and write happens on that
    loop, so no locking is required.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        redis: Any = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._subscriptions: dict[str, set[str]] = {}
        self.instance_id = uuid.uuid4().hex

        self._rate_limit = (
            rate_limit if rate_limit is not None else _env_int("RATE_LIMIT", 100)
        )
        self._rate_window_seconds = 60
        self._rate_counters: dict[str, list[float]] = {}

        self._message_ttl_days = (
            message_ttl_days
            if message_ttl_days is not None
            else _env_int("MESSAGE_TTL_DAYS", 7)
        )
        self._cleanup_interval_seconds = 3600
        self._cleanup_task: asyncio.Task | None = None

        self._redis = redis
        self._owns_redis = False
        if self._redis is None:
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(redis_url, decode_responses=True)
                self._owns_redis = True

        self._pubsub = None
        self._worker_task: asyncio.Task | None = None
        self._redis_ready = asyncio.Event()

        self._database_url = database_url or os.environ.get(
            "DATABASE_URL", "messages.db"
        )
        self._db_path = _resolve_db_path(self._database_url)
        self._init_db()

        self.transport = transport if transport is not None else self._make_transport()

    def _make_transport(self) -> BaseTransport:
        name = os.environ.get("TRANSPORT", "websocket").strip().lower()
        transport_cls = _TRANSPORT_REGISTRY.get(name)
        if transport_cls is None:
            raise ValueError(f"Unknown transport: {name!r}")
        return transport_cls(self, self.host, self.port)

    # ── Persistence ───────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _persist_message(self, message: dict[str, Any]) -> None:
        channel = message.get("channel")
        mtype = message.get("type")
        payload = json.dumps(message.get("payload", {}))
        timestamp = message.get("timestamp") or utc_now_iso()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (channel, mtype, payload, timestamp),
            )
            conn.commit()

    def _query_messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload"])
            except (TypeError, ValueError):
                pass
            result.append(item)
        return result

    def _query_history(
        self,
        channel: str | None,
        since: str | None,
        limit: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return messages for ``channel`` newer than ``since``, oldest first.

        Returns a ``(messages, has_more)`` tuple. ``has_more`` is True when
        there are more matching messages than ``limit``.
        """
        where: list[str] = []
        params: list[Any] = []
        if channel:
            where.append("channel = ?")
            params.append(channel)

        sql = "SELECT id, channel, type, payload, timestamp FROM messages"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id ASC"

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()

        since_dt = _parse_timestamp(since)
        messages: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            ts_dt = _parse_timestamp(item.get("timestamp"))
            if since_dt is not None and (ts_dt is None or ts_dt < since_dt):
                continue
            try:
                item["payload"] = json.loads(item["payload"])
            except (TypeError, ValueError):
                pass
            messages.append(item)

        has_more = len(messages) > limit
        return messages[:limit], has_more

    # ── Registry (delegated to the transport) ─────────────────────

    @property
    def client_count(self) -> int:
        return self.transport.client_count

    def client_ids(self) -> list[str]:
        return self.transport.client_ids()

    def has_client(self, client_id: str) -> bool:
        return self.transport.has_client(client_id)

    async def _drop_client(self, client_id: str) -> None:
        await self.transport.on_disconnect(client_id)
        for name in list(self._subscriptions):
            members = self._subscriptions[name]
            members.discard(client_id)
            if not members:
                self._subscriptions.pop(name, None)
        if self._redis is not None:
            try:
                subs = await self._redis.smembers(
                    KEY_CLIENT_SUBS.format(client_id=client_id)
                )
                for channel in subs:
                    await self._redis.srem(
                        KEY_CHANNEL_SUBS.format(channel=channel), client_id
                    )
                await self._redis.delete(
                    KEY_CLIENT_SUBS.format(client_id=client_id)
                )
                await self._redis.delete(
                    KEY_CLIENT_INSTANCE.format(client_id=client_id)
                )
            except Exception:
                pass

    # ── Channels ──────────────────────────────────────────────────

    async def subscribe(self, client_id: str, channel: str) -> bool:
        if not self.has_client(client_id):
            return False
        self._subscriptions.setdefault(channel, set()).add(client_id)
        if self._redis is not None:
            await self._redis.sadd(KEY_CHANNEL_SUBS.format(channel=channel), client_id)
            await self._redis.sadd(KEY_CLIENT_SUBS.format(client_id=client_id), channel)
        return True

    async def unsubscribe(self, client_id: str, channel: str) -> bool:
        members = self._subscriptions.get(channel)
        if members is None:
            return False
        members.discard(client_id)
        if not members:
            self._subscriptions.pop(channel, None)
        if self._redis is not None:
            await self._redis.srem(KEY_CHANNEL_SUBS.format(channel=channel), client_id)
            await self._redis.srem(KEY_CLIENT_SUBS.format(client_id=client_id), channel)
        return True

    def channel_names(self) -> list[str]:
        return sorted(self._subscriptions.keys())

    def channel_subscribers(self, channel: str) -> list[str]:
        return sorted(self._subscriptions.get(channel, set()))

    def channel_count(self, channel: str) -> int:
        return len(self._subscriptions.get(channel, set()))

    def channels(self) -> list[dict[str, Any]]:
        return [
            {"name": name, "subscribers": len(self._subscriptions[name])}
            for name in sorted(self._subscriptions)
            if self._subscriptions[name]
        ]

    # ── Rate limiting ─────────────────────────────────────────────

    def _check_rate_limit_local(self, client_id: str) -> bool:
        now = time.monotonic()
        stamps = self._rate_counters.setdefault(client_id, [])
        stamps[:] = [t for t in stamps if now - t < self._rate_window_seconds]
        stamps.append(now)
        return len(stamps) <= self._rate_limit

    async def _check_rate_limit(self, client_id: str) -> bool:
        if self._rate_limit <= 0:
            return True
        if self._redis is not None:
            key = KEY_RATE_LIMIT.format(client_id=client_id)
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, self._rate_window_seconds)
                return count <= self._rate_limit
            except Exception:
                pass
        return self._check_rate_limit_local(client_id)

    # ── Message expiry ────────────────────────────────────────────

    def _cleanup_expired_messages(self) -> int:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self._message_ttl_days)
        ).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff,)
            )
            conn.commit()
            return cursor.rowcount

    async def _cleanup_worker(self) -> None:
        while True:
            try:
                self._cleanup_expired_messages()
            except Exception:
                pass
            await asyncio.sleep(self._cleanup_interval_seconds)

    # ── Message helpers ───────────────────────────────────────────

    @staticmethod
    def make_message(mtype: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"type": mtype, "payload": payload, "timestamp": utc_now_iso()}

    @staticmethod
    def encode(message: dict[str, Any]) -> str:
        return json.dumps(message)

    # ── Sending ───────────────────────────────────────────────────

    async def send_to(self, client_id: str, message: dict[str, Any]) -> bool:
        if not self.transport.has_client(client_id):
            return False
        try:
            return await self.transport.send_message(client_id, self.encode(message))
        except Exception:
            await self._drop_client(client_id)
            return False

    async def _channel_local(self, channel: str, message: dict[str, Any]) -> int:
        data = self.encode(message)
        members = list(self._subscriptions.get(channel, set()))
        delivered = 0
        for client_id in members:
            if not self.transport.has_client(client_id):
                await self._drop_client(client_id)
                continue
            try:
                if await self.transport.send_message(client_id, data):
                    delivered += 1
            except Exception:
                await self._drop_client(client_id)
        return delivered

    async def _broadcast_local(self, message: dict[str, Any]) -> int:
        return await self.transport.broadcast(self.encode(message))

    async def send_to_channel(self, channel: str, message: dict[str, Any]) -> int:
        self._persist_message(message)
        if self._redis is not None:
            await self._publish({"kind": "channel", "channel": channel, "message": message})
            return 0
        return await self._channel_local(channel, message)

    async def broadcast(self, message: dict[str, Any]) -> int:
        self._persist_message(message)
        if self._redis is not None:
            await self._publish({"kind": "broadcast", "message": message})
            return 0
        return await self._broadcast_local(message)

    async def _publish(self, envelope: dict[str, Any]) -> None:
        await self._redis.publish(REDIS_CHANNEL, json.dumps(envelope))

    async def _deliver(self, envelope: dict[str, Any]) -> None:
        kind = envelope.get("kind")
        message = envelope.get("message") or {}
        if kind == "broadcast":
            await self._broadcast_local(message)
        elif kind == "channel":
            await self._channel_local(envelope.get("channel"), message)
        elif kind == "direct":
            if envelope.get("instance") == self.instance_id:
                await self.send_to(envelope.get("target"), message)

    async def _redis_worker(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(REDIS_CHANNEL)
        self._redis_ready.set()
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(msg["data"])
                except (TypeError, ValueError):
                    continue
                await self._deliver(envelope)
        finally:
            try:
                await pubsub.aclose()
            except Exception:
                pass

    # ── Transport callbacks ───────────────────────────────────────

    async def on_client_connected(self, client_id: str) -> None:
        if self._redis is not None:
            try:
                await self._redis.set(
                    KEY_CLIENT_INSTANCE.format(client_id=client_id), self.instance_id
                )
            except Exception:
                pass
        await self.send_to(
            client_id,
            self.make_message(
                "system", {"event": "connected", "client_id": client_id}
            ),
        )

    async def on_client_message(self, client_id: str, raw: str | bytes) -> None:
        await self._route(client_id, raw)

    async def on_client_disconnected(self, client_id: str) -> None:
        await self._drop_client(client_id)
        await self.broadcast(
            self.make_message(
                "system", {"event": "disconnected", "client_id": client_id}
            )
        )

    async def _route(self, client_id: str, raw: str | bytes) -> None:
        if not await self._check_rate_limit(client_id):
            await self.send_to(
                client_id,
                self.make_message(
                    "system",
                    {"event": "error", "message": "rate limit exceeded"},
                ),
            )
            return

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            await self.send_to(
                client_id,
                self.make_message(
                    "system", {"event": "error", "message": "invalid JSON"}
                ),
            )
            return

        if not isinstance(data, dict):
            await self.send_to(
                client_id,
                self.make_message(
                    "system", {"event": "error", "message": "message must be an object"}
                ),
            )
            return

        mtype = data.get("type")
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        channel = data.get("channel")
        if not isinstance(channel, str) and "channel" in payload:
            channel = payload.get("channel")

        if mtype == "subscribe":
            if not channel:
                await self.send_to(
                    client_id,
                    self.make_message(
                        "system",
                        {"event": "error", "message": "subscribe requires a channel"},
                    ),
                )
                return
            await self.subscribe(client_id, channel)
            await self.send_to(
                client_id,
                self.make_message("system", {"event": "subscribed", "channel": channel}),
            )
        elif mtype == "unsubscribe":
            if not channel:
                await self.send_to(
                    client_id,
                    self.make_message(
                        "system",
                        {"event": "error", "message": "unsubscribe requires a channel"},
                    ),
                )
                return
            await self.unsubscribe(client_id, channel)
            await self.send_to(
                client_id,
                self.make_message(
                    "system", {"event": "unsubscribed", "channel": channel}
                ),
            )
        elif mtype == "broadcast":
            message = self.make_message("broadcast", dict(payload))
            if channel:
                message["channel"] = channel
                await self.send_to_channel(channel, message)
            else:
                await self.broadcast(message)
        elif mtype == "direct":
            target = payload.get("target")
            if not target:
                await self.send_to(
                    client_id,
                    self.make_message(
                        "system",
                        {"event": "error", "message": "direct message requires a target"},
                    ),
                )
                return
            out_payload = dict(payload)
            out_payload["sender"] = client_id
            message = self.make_message("direct", out_payload)
            self._persist_message(message)
            if self._redis is not None:
                instance = await self._redis.get(
                    KEY_CLIENT_INSTANCE.format(client_id=target)
                )
                if not instance:
                    await self.send_to(
                        client_id,
                        self.make_message(
                            "system",
                            {
                                "event": "error",
                                "message": "target not found",
                                "target": target,
                            },
                        ),
                    )
                    return
                await self._publish(
                    {
                        "kind": "direct",
                        "instance": instance,
                        "target": target,
                        "message": message,
                    }
                )
            else:
                delivered = await self.send_to(target, message)
                if not delivered:
                    await self.send_to(
                        client_id,
                        self.make_message(
                            "system",
                            {
                                "event": "error",
                                "message": "target not found",
                                "target": target,
                            },
                        ),
                    )
        else:
            await self.send_to(
                client_id,
                self.make_message(
                    "system",
                    {"event": "error", "message": f"unsupported type: {mtype!r}"},
                ),
            )

    # ── REST endpoints (via the WebSocket handshake hook) ──────────

    async def process_request(
        self, connection: Any, request: Any
    ) -> Response | None:
        full_path = request.path
        path = full_path.split("?", 1)[0]
        query = parse_qs(full_path.partition("?")[2])

        if path == "/health":
            body = json.dumps(
                {"status": "ok", "clients": self.client_count}
            ).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        if path == "/channels":
            body = json.dumps({"channels": self.channels()}).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        if path == "/messages":
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
            body = json.dumps(
                {"messages": self._query_messages(limit, offset)}
            ).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        if path == "/history":
            channel = query.get("channel", [None])[0]
            since = query.get("since", [None])[0]
            try:
                limit = int(query.get("limit", ["50"])[0])
            except (TypeError, ValueError):
                limit = 50
            limit = max(1, min(limit, 1000))
            messages, has_more = self._query_history(channel, since, limit)
            body = json.dumps(
                {"messages": messages, "has_more": has_more}
            ).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")])
            if not name or name not in self._subscriptions:
                body = json.dumps({"error": "channel not found"}).encode("utf-8")
                headers = Headers({"Content-Type": "application/json"})
                return Response(404, "Not Found", headers, body)
            body = json.dumps(
                {"channel": name, "subscribers": self.channel_subscribers(name)}
            ).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        return None

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        if self._redis is not None:
            self._worker_task = asyncio.create_task(self._redis_worker())
            await self._redis_ready.wait()
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        await self.transport.start()
        self.host = self.transport.host
        self.port = self.transport.port

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        if self.transport is not None:
            await self.transport.stop()
        if self._owns_redis and self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    async def run_forever(self) -> None:
        await self.start()
        try:
            await self.transport.serve_forever()
        finally:
            await self.stop()

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        return f"http://{self.host}:{self.port}/health"

    @property
    def channels_url(self) -> str:
        return f"http://{self.host}:{self.port}/channels"

    @property
    def messages_url(self) -> str:
        return f"http://{self.host}:{self.port}/messages"


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = NotificationServer(host=host, port=port)
    asyncio.run(server.run_forever())


if __name__ == "__main__":
    main()
