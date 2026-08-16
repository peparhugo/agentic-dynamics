"""WebSocket-based notification server built on the ``websockets`` library.

Clients connect over WebSocket, are assigned a unique ID, and can exchange
JSON messages. The server also exposes a small REST API (``GET /health``,
``GET /channels``, ``GET /messages``) served through the WebSocket handshake
hook.

Message distribution is backed by Redis pub/sub when ``REDIS_URL`` (or an
explicit ``redis`` client) is configured. In that mode:

* The server publishes an envelope to a shared Redis pub/sub channel.
* A worker coroutine subscribes to that channel and delivers messages to the
  locally connected WebSocket clients.
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
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")

# The single Redis pub/sub channel used as the message backbone.
REDIS_CHANNEL = "notifications"

# Redis key templates for client connection state.
KEY_CLIENT_INSTANCE = "notif:client:{client_id}"
KEY_CHANNEL_SUBS = "notif:subs:{channel}"
KEY_CLIENT_SUBS = "notif:client_subs:{client_id}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_db_path(url: str) -> str:
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url


class NotificationServer:
    """An asyncio WebSocket notification server.

    The client registry is a plain :class:`dict`. Because asyncio runs all
    coroutines and callbacks on a single event loop, every read and write to
    the registry happens on that loop, so no locking is required.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        redis: Any = None,
        database_url: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._server = None
        self.instance_id = uuid.uuid4().hex

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

    # ── Registry ──────────────────────────────────────────────────

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def client_ids(self) -> list[str]:
        return list(self._clients.keys())

    def has_client(self, client_id: str) -> bool:
        return client_id in self._clients

    async def _drop_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
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

    # ── Message helpers ───────────────────────────────────────────

    @staticmethod
    def make_message(mtype: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"type": mtype, "payload": payload, "timestamp": utc_now_iso()}

    @staticmethod
    def encode(message: dict[str, Any]) -> str:
        return json.dumps(message)

    # ── Sending ───────────────────────────────────────────────────

    async def send_to(self, client_id: str, message: dict[str, Any]) -> bool:
        ws = self._clients.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send(self.encode(message))
            return True
        except Exception:
            await self._drop_client(client_id)
            return False

    async def _channel_local(self, channel: str, message: dict[str, Any]) -> int:
        data = self.encode(message)
        members = list(self._subscriptions.get(channel, set()))
        delivered = 0
        for client_id in members:
            ws = self._clients.get(client_id)
            if ws is None:
                await self._drop_client(client_id)
                continue
            try:
                await ws.send(data)
                delivered += 1
            except Exception:
                await self._drop_client(client_id)
        return delivered

    async def _broadcast_local(self, message: dict[str, Any]) -> int:
        data = self.encode(message)
        stale: list[str] = []
        for client_id, ws in list(self._clients.items()):
            try:
                await ws.send(data)
            except Exception:
                stale.append(client_id)
        for client_id in stale:
            await self._drop_client(client_id)
        return len(self._clients)

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

    # ── Connection handling ───────────────────────────────────────

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        self._clients[client_id] = websocket
        if self._redis is not None:
            try:
                await self._redis.set(
                    KEY_CLIENT_INSTANCE.format(client_id=client_id), self.instance_id
                )
            except Exception:
                pass
        try:
            await self.send_to(
                client_id,
                self.make_message(
                    "system", {"event": "connected", "client_id": client_id}
                ),
            )
            async for raw in websocket:
                await self._route(websocket, client_id, raw)
        finally:
            await self._drop_client(client_id)
            await self.broadcast(
                self.make_message(
                    "system", {"event": "disconnected", "client_id": client_id}
                )
            )

    async def _route(
        self, websocket: ServerConnection, client_id: str, raw: str | bytes
    ) -> None:
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
        self, connection: ServerConnection, request: Any
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
        self._server = await serve(
            self.handler,
            self.host,
            self.port,
            process_request=self.process_request,
        )
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._owns_redis and self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    async def run_forever(self) -> None:
        await self.start()
        try:
            await self._server.serve_forever()
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
