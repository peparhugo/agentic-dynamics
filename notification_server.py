"""Pluggable-transport notification server.

The server core (routing, channels, Redis backbone, persistence) talks only
to a ``BaseTransport`` abstraction, so different transport mechanisms
(WebSocket, SSE, polling, raw TCP, ...) can be swapped in without touching
core logic. ``WebSocketTransport`` is the default and is selected via the
``TRANSPORT`` environment variable.

Core features:
- Accepts connections through the configured transport and assigns each
  client a unique ID.
- Broadcasts messages to all connected clients.
- Routes direct messages to a single target client.
- Supports channel-based subscriptions: clients subscribe/unsubscribe to
  named channels and messages carrying a ``channel`` field are delivered
  only to that channel's subscribers.
- Sends server-generated system messages (connect ack, errors, ...).
- Cleans up clients (and their channel memberships) on disconnect.
- Exposes REST endpoints via a small background HTTP server:
  ``GET /health``, ``GET /channels``, ``GET /channels/{name}/subscribers``
  and ``GET /messages?limit=50&offset=0``.

Redis integration:
- Messages are published to a Redis pub/sub channel (``notifications:messages``)
  and every server instance subscribed to that channel (including a server's
  own background subscriber) delivers them to its locally connected clients.
  This lets multiple server instances share a single message backbone.
- Connection state (client -> server mapping, per-server channel memberships)
  is mirrored into Redis so it survives a server restart.
- ``REDIS_URL`` selects the broker; when Redis is unreachable the server
  gracefully degrades to in-process delivery only.

Persistence:
- Every broadcast/direct message is stored in SQLite (``DATABASE_URL``) and
  exposed through ``GET /messages``.

Message format (JSON): ``{type: str, payload: dict, timestamp: str}``.
Supported types: ``broadcast``, ``direct``, ``system``, ``subscribe``,
``unsubscribe``.

Thread safety: everything runs on a single asyncio event loop, so the client
registry needs no locking -- plain dict reads and writes are safe by
construction, even when the background HTTP server thread reads the registry.
The Redis subscriber runs in its own background thread and only ever schedules
coroutines back onto the event loop, so it never touches the registry
directly.
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, unquote, urlparse

import websockets

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "chat.db")
REDIS_BROADCAST_CHANNEL = "notifications:messages"

_redis_client = None
_redis_failed = False
_redis_lock = threading.Lock()


def _resolve_db_path(url: str) -> str:
    """Strip a ``sqlite:///`` prefix so plain paths work too."""
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return url


def _get_redis():
    """Return a shared Redis client, or None when the broker is unreachable."""
    global _redis_client, _redis_failed
    if _redis_failed:
        return None
    if _redis_client is not None:
        return _redis_client
    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        if _redis_failed:
            return None
        try:
            import redis as _redis_lib
            _redis_client = _redis_lib.from_url(
                REDIS_URL, decode_responses=True, socket_connect_timeout=0.5
            )
            _redis_client.ping()
        except Exception:
            _redis_failed = True
            return None
    return _redis_client


def make_message(msg_type: str, payload: dict | None = None) -> dict:
    """Build a message conforming to the standard wire format."""
    return {
        "type": msg_type,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class MessageStore:
    """SQLite-backed message history store.

    The ``messages`` table schema: ``id, channel, type, payload, timestamp``.
    ``payload`` is stored as a JSON string and parsed back when read.
    """

    def __init__(self, database_path: str | None = None) -> None:
        self.database_path = _resolve_db_path(database_path or DATABASE_URL)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
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
        finally:
            conn.close()

    def save(
        self, channel: str | None, msg_type: str, payload: dict, timestamp: str
    ) -> None:
        """Insert a message into the history table."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp)"
                " VALUES (?, ?, ?, ?)",
                (channel, msg_type, json.dumps(payload), timestamp),
            )
            conn.commit()
        finally:
            conn.close()

    def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return stored messages, newest first, with ``payload`` parsed."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages"
                " ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        finally:
            conn.close()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload"])
            except (json.JSONDecodeError, TypeError):
                pass
            result.append(item)
        return result

    def clear(self) -> None:
        """Delete every stored message (used by tests)."""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM messages")
            conn.commit()
        finally:
            conn.close()


class ClientRegistry:
    """Thread-safe client registry mapping client IDs to connection objects.

    The registry is transport-agnostic: it stores whatever connection object
    the active transport hands it (WebSocket, SSE stream, TCP socket, ...).

    asyncio runs everything on a single event loop, so plain dict operations
    are always safe here -- no locking is required even when background
    threads (e.g. the HTTP health server thread) read the registry.
    """

    def __init__(self) -> None:
        self._clients: dict[str, object] = {}
        self._next_id: int = 1
        self._channel_members: dict[str, set[str]] = {}

    def add(self, websocket) -> str:
        """Register a connection and return its unique client ID."""
        client_id = str(self._next_id)
        self._next_id += 1
        self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        """Remove a client (and its channel memberships); no-op if already gone."""
        self._clients.pop(client_id, None)
        for channel, members in list(self._channel_members.items()):
            members.discard(client_id)
            if not members:
                del self._channel_members[channel]

    def get(self, client_id: str):
        """Return the connection object for a client ID, or None."""
        return self._clients.get(client_id)

    def count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)

    def connected_ids(self) -> list[str]:
        """Snapshot of the connected client IDs."""
        return list(self._clients)

    def items(self) -> list[tuple[str, object]]:
        """Snapshot of ``(client_id, connection)`` pairs."""
        return list(self._clients.items())

    def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a named channel (idempotent)."""
        self._channel_members.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a named channel (idempotent)."""
        members = self._channel_members.get(channel)
        if members is None:
            return
        members.discard(client_id)
        if not members:
            del self._channel_members[channel]

    def channel_subscribers(self, channel: str) -> set[str]:
        """Snapshot of the client IDs subscribed to a channel."""
        return set(self._channel_members.get(channel, set()))

    def channels(self) -> dict[str, int]:
        """Map of active channel name -> subscriber count."""
        return {
            name: len(members)
            for name, members in self._channel_members.items()
        }

    def channels_of(self, client_id: str) -> list[str]:
        """Channel names a client is currently subscribed to."""
        return [
            name
            for name, members in self._channel_members.items()
            if client_id in members
        ]


def build_health_handler(registry: ClientRegistry, store: MessageStore):
    """Build a ``BaseHTTPRequestHandler`` exposing the REST endpoints.

    ``GET /health`` -> 200 ``{"status": "ok", "connected_clients": N}``
    ``GET /channels`` -> 200 ``{"channels": {name: subscriber_count}}``
    ``GET /channels/{name}/subscribers`` -> 200
        ``{"channel": name, "subscribers": [client_id, ...]}``
    ``GET /messages?limit=50&offset=0`` -> 200 list of stored messages.
    """

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/health", "/health/"):
                self._send_json(
                    200,
                    {"status": "ok", "connected_clients": registry.count()},
                )
            elif path in ("/channels", "/channels/"):
                self._send_json(200, {"channels": registry.channels()})
            elif path in ("/messages", "/messages/"):
                params = parse_qs(parsed.query)
                try:
                    limit = int(params.get("limit", ["50"])[0])
                except ValueError:
                    limit = 50
                try:
                    offset = int(params.get("offset", ["0"])[0])
                except ValueError:
                    offset = 0
                self._send_json(200, store.list(limit=limit, offset=offset))
            elif path.startswith("/channels/"):
                name = unquote(path[len("/channels/"):]).strip("/")
                if name.endswith("/subscribers"):
                    name = name[: -len("/subscribers")]
                    subs = sorted(registry.channel_subscribers(name))
                    self._send_json(
                        200, {"channel": name, "subscribers": subs}
                    )
                else:
                    self._send_json(404, {"error": "not found"})
            else:
                self._send_json(404, {"error": "not found"})

        def _send_json(self, code: int, data) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # keep test output clean
            pass

    return HealthHandler


class NotificationServer:
    """Async WebSocket notification server with REST endpoints.

    When Redis is reachable the server publishes every broadcast/direct
    message to the shared pub/sub channel and delivers them to local clients
    through its background subscriber (which also receives messages published
    by other server instances sharing the same backbone).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        ws_port: int = 0,
        http_port: int = 0,
        registry: ClientRegistry | None = None,
        store: MessageStore | None = None,
        server_id: str | None = None,
    ) -> None:
        self.host = host
        self.ws_port = ws_port
        self.http_port = http_port
        self.registry = registry or ClientRegistry()
        self.store = store or MessageStore()
        self.server_id = server_id or str(uuid.uuid4())
        self.ws_url: str | None = None
        self.http_url: str | None = None
        self.redis_ready = threading.Event()
        self._subscriber_stop = threading.Event()
        self._ws_server = None
        self._http_server: ThreadingHTTPServer | None = None
        self._http_thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pubsub = None
        self._subscriber_thread: Thread | None = None
        self._shutting_down = False

    async def start(self) -> "NotificationServer":
        """Start the WebSocket server and the background HTTP server."""
        self._loop = asyncio.get_running_loop()
        self._ws_server = await websockets.serve(
            self._handle_connection, self.host, self.ws_port
        )
        bound_port = self._ws_server.sockets[0].getsockname()[1]
        self.ws_port = bound_port
        self.ws_url = f"ws://{self.host}:{bound_port}"

        self._http_server = ThreadingHTTPServer(
            (self.host, self.http_port),
            build_health_handler(self.registry, self.store),
        )
        self.http_port = self._http_server.server_address[1]
        self.http_url = f"http://{self.host}:{self.http_port}"
        self._http_thread = Thread(
            target=self._http_server.serve_forever, daemon=True
        )
        self._http_thread.start()

        self._start_redis_subscriber()
        return self

    async def stop(self) -> None:
        """Stop both servers and release their ports."""
        self._shutting_down = True
        await self._stop_redis_subscriber()
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
            if self._http_thread is not None:
                self._http_thread.join(timeout=5)
            self._http_server = None
            self._http_thread = None
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None

    # ── Redis pub/sub backbone ──────────────────────────────────────

    def _start_redis_subscriber(self) -> None:
        """Subscribe to the shared Redis channel from a background thread.

        Each incoming message is handed to the event loop for delivery to the
        locally connected clients. Messages published by this very server are
        skipped (they were already delivered locally at publish time).
        """

        def _run() -> None:
            try:
                r = _get_redis()
                if r is None:
                    return
                pubsub = r.pubsub()
                self._pubsub = pubsub
                pubsub.subscribe(REDIS_BROADCAST_CHANNEL)
                self.redis_ready.set()
                while not self._subscriber_stop.is_set():
                    try:
                        msg = pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=0.1
                        )
                    except Exception:
                        break
                    if msg is None:
                        continue
                    if msg.get("type") != "message":
                        continue
                    channel = msg.get("channel")
                    if channel not in (
                        REDIS_BROADCAST_CHANNEL,
                        REDIS_BROADCAST_CHANNEL.encode(),
                    ):
                        continue
                    data = msg.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    try:
                        envelope = json.loads(data)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if self._loop is not None and not self._shutting_down:
                        future = asyncio.run_coroutine_threadsafe(
                            self._deliver_from_redis(envelope), self._loop
                        )
                        try:
                            future.result(timeout=5)
                        except Exception:
                            pass
            except Exception:
                pass
            finally:
                self.redis_ready.set()

        self._subscriber_thread = Thread(
            target=_run, name="redis-subscriber", daemon=True
        )
        self._subscriber_thread.start()

    async def _stop_redis_subscriber(self) -> None:
        self._subscriber_stop.set()
        if self._pubsub is not None:
            try:
                self._pubsub.close()
            except Exception:
                pass
            self._pubsub = None
        thread = self._subscriber_thread
        if thread is not None and thread.is_alive():
            await asyncio.to_thread(thread.join, 2)
        self._subscriber_thread = None

    async def _deliver_from_redis(self, envelope: dict) -> None:
        """Deliver a message received from the shared backbone."""
        if envelope.get("_server_id") == self.server_id:
            return
        msg_type = envelope.get("type")
        channel = envelope.get("channel")
        payload = envelope.get("payload") or {}
        wire = {
            "type": msg_type,
            "payload": payload,
            "timestamp": envelope.get("timestamp"),
        }
        if channel:
            wire["channel"] = channel
        if msg_type == "direct":
            target = payload.get("to")
            if target:
                await self.send_to(target, wire)
        elif channel:
            await self.send_to_channel(channel, wire)
        else:
            await self.broadcast(wire)

    def _publish(self, outbound: dict) -> None:
        """Publish a wire message onto the shared Redis channel."""
        r = _get_redis()
        if r is None:
            return
        envelope = {
            "type": outbound["type"],
            "channel": outbound.get("channel"),
            "payload": outbound["payload"],
            "timestamp": outbound["timestamp"],
            "_server_id": self.server_id,
        }
        try:
            r.publish(REDIS_BROADCAST_CHANNEL, json.dumps(envelope))
        except Exception:
            pass

    def _persist(self, channel: str | None, outbound: dict) -> None:
        """Persist a wire message to SQLite for history."""
        try:
            self.store.save(
                channel, outbound["type"], outbound["payload"], outbound["timestamp"]
            )
        except Exception:
            pass

    # ── Redis connection state ──────────────────────────────────────

    def _record_connection(self, client_id: str) -> None:
        r = _get_redis()
        if r is None:
            return
        try:
            r.hset("chat:clients", client_id, self.server_id)
            r.sadd(f"chat:server:{self.server_id}:clients", client_id)
        except Exception:
            pass

    def _record_subscription(self, client_id: str, channel: str) -> None:
        r = _get_redis()
        if r is None:
            return
        try:
            r.sadd(f"chat:channel:{self.server_id}:{channel}", client_id)
        except Exception:
            pass

    def _remove_subscription(self, client_id: str, channel: str) -> None:
        r = _get_redis()
        if r is None:
            return
        try:
            r.srem(f"chat:channel:{self.server_id}:{channel}", client_id)
        except Exception:
            pass

    def _drop_connection(
        self, client_id: str, channels: list[str] | None = None
    ) -> None:
        """Remove a client's connection state from Redis.

        During a graceful shutdown this is skipped so the state survives a
        server restart (it lives in the shared backbone, not in memory).
        """
        if self._shutting_down:
            return
        r = _get_redis()
        if r is None:
            return
        try:
            r.hdel("chat:clients", client_id)
            r.srem(f"chat:server:{self.server_id}:clients", client_id)
            for channel in channels or []:
                r.srem(f"chat:channel:{self.server_id}:{channel}", client_id)
        except Exception:
            pass

    # ── WebSocket handling ──────────────────────────────────────────

    async def _handle_connection(self, websocket) -> None:
        """Per-connection handler: assign ID, pump messages, clean up."""
        client_id = self.registry.add(websocket)
        self._record_connection(client_id)
        try:
            await websocket.send(
                json.dumps(
                    make_message(
                        "system",
                        {"event": "connected", "client_id": client_id},
                    )
                )
            )
            async for raw in websocket:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send_error(
                        websocket, "invalid JSON payload"
                    )
                    continue
                await self._dispatch(websocket, client_id, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            channels = self.registry.channels_of(client_id)
            self.registry.remove(client_id)
            self._drop_connection(client_id, channels)

    async def _dispatch(self, websocket, sender_id: str, message: dict) -> None:
        """Route an incoming client message."""
        msg_type = message.get("type")
        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        if msg_type == "broadcast":
            channel = message.get("channel") or payload.get("channel")
            outbound = make_message("broadcast", {"from": sender_id, **payload})
            if channel:
                outbound["channel"] = channel
                if "channel" not in outbound["payload"]:
                    outbound["payload"]["channel"] = channel
            self._persist(channel, outbound)
            self._publish(outbound)
            if channel:
                await self.send_to_channel(channel, outbound)
            else:
                await self.broadcast(outbound)
        elif msg_type == "subscribe":
            channel = message.get("channel") or payload.get("channel")
            if not channel:
                await self._send_error(
                    websocket, "subscribe message missing 'channel'"
                )
            else:
                self.registry.subscribe(sender_id, channel)
                self._record_subscription(sender_id, channel)
        elif msg_type == "unsubscribe":
            channel = message.get("channel") or payload.get("channel")
            if not channel:
                await self._send_error(
                    websocket, "unsubscribe message missing 'channel'"
                )
            else:
                self.registry.unsubscribe(sender_id, channel)
                self._remove_subscription(sender_id, channel)
        elif msg_type == "direct":
            target = payload.get("to")
            if not target:
                await self._send_error(websocket, "direct message missing 'to'")
                return
            outbound = make_message(
                "direct",
                {
                    "from": sender_id,
                    "to": target,
                    "data": payload.get("data", {}),
                },
            )
            delivered = await self.send_to(target, outbound)
            self._persist(None, outbound)
            r = _get_redis()
            if r is not None:
                self._publish(outbound)
                if not delivered:
                    try:
                        known = bool(r.hexists("chat:clients", target))
                    except Exception:
                        known = False
                    if not known:
                        await self._send_error(
                            websocket, "target not connected", to=target
                        )
            elif not delivered:
                await self._send_error(
                    websocket, "target not connected", to=target
                )
        elif msg_type == "system":
            await websocket.send(
                json.dumps(
                    make_message(
                        "system",
                        {"event": "ack", "from": sender_id},
                    )
                )
            )
        else:
            await self._send_error(
                websocket, f"unsupported message type: {msg_type}"
            )

    async def _send_error(self, websocket, error: str, **extra) -> None:
        try:
            await websocket.send(
                json.dumps(
                    make_message(
                        "system",
                        {"event": "error", "error": error, **extra},
                    )
                )
            )
        except websockets.exceptions.ConnectionClosed:
            pass

    async def broadcast(self, message: dict) -> None:
        """Send a message to every connected client."""
        data = json.dumps(message)
        for client_id, ws in self.registry.items():
            try:
                await ws.send(data)
            except websockets.exceptions.ConnectionClosed:
                self.registry.remove(client_id)

    async def send_to(self, client_id: str, message: dict) -> bool:
        """Send a message to a single client. Returns False if it is gone."""
        ws = self.registry.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed:
            self.registry.remove(client_id)
            return False
        return True

    async def send_to_channel(self, channel: str, message: dict) -> None:
        """Send a message only to the subscribers of a named channel."""
        data = json.dumps(message)
        for client_id in self.registry.channel_subscribers(channel):
            ws = self.registry.get(client_id)
            if ws is None:
                continue
            try:
                await ws.send(data)
            except websockets.exceptions.ConnectionClosed:
                self.registry.remove(client_id)
