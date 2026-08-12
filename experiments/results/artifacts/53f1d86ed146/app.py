"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import asyncio
import json
import threading
import uuid

import websockets
from transports import BaseTransport, WebSocketTransport

try:
    import redis
except ImportError:  # pragma: no cover - redis is an optional runtime dependency
    redis = None

app = Flask(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL", os.environ.get("DATABASE", "todos.db"))
# Retain the old name for callers that imported the seed application's setting.
DATABASE = DATABASE_URL
REDIS_CHANNEL = "notification_messages"


def _rate_limit() -> int:
    """Read the limit at use time so deployments can configure it by environment."""
    try:
        return max(0, int(os.environ.get("RATE_LIMIT", "100")))
    except ValueError:
        return 100


def _message_ttl_days() -> int:
    try:
        return max(0, int(os.environ.get("MESSAGE_TTL_DAYS", "7")))
    except ValueError:
        return 7


def _database_path() -> str:
    """Convert the supported SQLite URL forms to a filesystem path."""
    if DATABASE_URL.startswith("sqlite:///"):
        return DATABASE_URL[10:]
    if DATABASE_URL.startswith("sqlite://"):
        return DATABASE_URL[9:]
    return DATABASE_URL


class RedisBroker:
    """Small Redis pub/sub adapter, with an unavailable-broker fallback."""

    def __init__(self, url=REDIS_URL):
        self.url = url
        self.client = None
        self.pubsub = None
        self._thread = None
        self._stopping = threading.Event()

    def connect(self) -> bool:
        if self.client is not None:
            return True
        if redis is None:
            return False
        try:
            client = redis.Redis.from_url(self.url, decode_responses=True,
                                          socket_connect_timeout=0.2,
                                          socket_timeout=0.2)
            client.ping()
            self.client = client
            return True
        except Exception:
            self.client = None
            return False

    def publish(self, message: str) -> bool:
        if not self.connect():
            return False
        try:
            self.client.publish(REDIS_CHANNEL, message)
            return True
        except Exception:
            self.client = None
            return False

    def allow_message(self, client_id: str, limit: int | None = None) -> bool | None:
        """Increment a per-client fixed one-minute Redis counter.

        ``None`` means Redis is unavailable; callers can retain local operation in
        that case. Redis itself remains the source of truth whenever connected.
        """
        if not self.connect():
            return None
        limit = _rate_limit() if limit is None else limit
        if limit == 0:
            return False
        key = f"notification:rate:{client_id}"
        try:
            count = self.client.incr(key)
            if count == 1:
                self.client.expire(key, 60)
            return count <= limit
        except Exception:
            self.client = None
            return None

    def remember_client(self, client_id: str) -> None:
        if self.connect():
            try:
                self.client.hset("notification:clients", client_id, "connected")
            except Exception:
                pass

    def forget_client(self, client_id: str) -> None:
        if self.client is not None:
            try:
                self.client.hdel("notification:clients", client_id)
                self.client.delete(f"notification:subscriptions:{client_id}")
            except Exception:
                pass

    def remember_subscription(self, client_id: str, channel: str) -> None:
        if self.connect():
            try:
                self.client.sadd(f"notification:subscriptions:{client_id}", channel)
            except Exception:
                pass

    def forget_subscription(self, client_id: str, channel: str) -> None:
        if self.client is not None:
            try:
                self.client.srem(f"notification:subscriptions:{client_id}", channel)
            except Exception:
                pass

    def start(self, callback) -> bool:
        if not self.connect() or self._thread is not None:
            return self._thread is not None
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(REDIS_CHANNEL)
        self._stopping.clear()

        def listen():
            try:
                for item in self.pubsub.listen():
                    if self._stopping.is_set():
                        break
                    if item.get("type") == "message":
                        callback(item["data"])
            except Exception:
                pass

        self._thread = threading.Thread(target=listen, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stopping.set()
        if self.pubsub is not None:
            try:
                self.pubsub.close()
            except Exception:
                pass
        self.pubsub = None
        self._thread = None


class NotificationServer:
    """Notification service independent of the client transport."""

    def __init__(self, broker=None, transport=None):
        self.clients = {}
        self.channels = {}
        self._clients_lock = threading.RLock()
        self._server = None
        self.broker = broker or RedisBroker()
        self._loop = None
        self._origin = str(uuid.uuid4())
        self.transport = transport or self._configured_transport()
        self._cleanup_task = None

    @staticmethod
    def _configured_transport():
        transport_name = os.environ.get("TRANSPORT", "websocket").strip().lower()
        if transport_name in {"websocket", "ws"}:
            return WebSocketTransport()
        raise ValueError(f"Unsupported transport: {transport_name}")

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    def register(self, websocket) -> str:
        client_id = str(uuid.uuid4())
        with self._clients_lock:
            self.clients[client_id] = websocket
        self.transport.on_connect(client_id, websocket)
        self.broker.remember_client(client_id)
        return client_id

    def unregister(self, client_id: str) -> None:
        with self._clients_lock:
            self.clients.pop(client_id, None)
            for channel in list(self.channels):
                self.channels[channel].discard(client_id)
                if not self.channels[channel]:
                    del self.channels[channel]
        self.transport.on_disconnect(client_id)
        self.broker.forget_client(client_id)

    def subscribe(self, client_id: str, channel: str) -> bool:
        if not isinstance(channel, str) or not channel.strip():
            return False
        channel = channel.strip()
        with self._clients_lock:
            if client_id not in self.clients:
                return False
            self.channels.setdefault(channel, set()).add(client_id)
        self.broker.remember_subscription(client_id, channel)
        return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        if not isinstance(channel, str) or not channel.strip():
            return False
        channel = channel.strip()
        with self._clients_lock:
            subscribers = self.channels.get(channel)
            if subscribers is None:
                return False
            removed = client_id in subscribers
            subscribers.discard(client_id)
            if not subscribers:
                del self.channels[channel]
        self.broker.forget_subscription(client_id, channel)
        return removed

    def channel_subscribers(self, channel: str) -> list[str]:
        with self._clients_lock:
            return sorted(self.channels.get(channel, set()))

    def channel_counts(self) -> dict[str, int]:
        with self._clients_lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in sorted(self.channels.items())
            }

    @staticmethod
    def _message(message_type: str, payload: dict, channel=None, recipient=None, origin=None) -> str:
        message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if channel:
            message["channel"] = channel
        if recipient:
            message["recipient"] = recipient
        if origin:
            message["origin"] = origin
        return json.dumps(message)

    @staticmethod
    def _persist_message(message: str) -> None:
        try:
            item = json.loads(message)
            payload = item.get("payload", {})
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                    (item.get("channel"), item.get("type"), json.dumps(payload), item.get("timestamp")),
                )
                conn.commit()
        except (sqlite3.Error, TypeError, json.JSONDecodeError):
            pass

    async def _deliver(self, message: str, channel: str | None = None,
                       recipient: str | None = None) -> None:
        with self._clients_lock:
            if recipient:
                client = self.clients.get(recipient)
                clients = [(recipient, client)] if client is not None else []
            elif not isinstance(channel, str) or not channel.strip():
                clients = list(self.clients.items())
            else:
                channel = channel.strip()
                subscriber_ids = self.channels.get(channel, set())
                clients = [
                    (client_id, self.clients[client_id])
                    for client_id in subscriber_ids
                    if client_id in self.clients
                ]
        failed = await self.transport.broadcast(message, [client_id for client_id, _ in clients])
        for client_id in failed or []:
            if client_id in self.clients:
                self.unregister(client_id)

    def _on_broker_message(self, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            if message.get("origin") == self._origin:
                return
            loop = self._loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._deliver(raw_message, message.get("channel"), message.get("recipient")), loop
                )
        except (TypeError, json.JSONDecodeError):
            return

    async def broadcast(
        self, payload: dict, message_type: str = "broadcast", channel: str | None = None
    ) -> None:
        if channel is None:
            channel = payload.get("channel")
        message = self._message(message_type, payload, channel=channel, origin=self._origin)
        self._persist_message(message)
        self.broker.publish(message)
        await self._deliver(message, channel)

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        with self._clients_lock:
            websocket = self.clients.get(client_id)
        if websocket is None:
            return False
        message = self._message("direct", payload, recipient=client_id, origin=self._origin)
        self._persist_message(message)
        self.broker.publish(message)
        delivered = await self.transport.send_message(client_id, message)
        if not delivered:
            self.unregister(client_id)
        return delivered

    async def websocket_handler(self, websocket, path=None):
        handler = getattr(self.transport, "handle_connection", None)
        if handler is None:
            raise RuntimeError("The configured transport does not support WebSocket connections")
        await handler(websocket, self)

    def allow_message(self, client_id: str) -> bool:
        allowed = self.broker.allow_message(client_id, _rate_limit()) \
            if hasattr(self.broker, "allow_message") else True
        return allowed is not False

    async def send_error(self, client_id: str, message: str) -> None:
        error = json.dumps({"type": "error", "error": message})
        await self.transport.send_message(client_id, error)

    async def _cleanup_messages(self):
        while True:
            cutoff = (datetime.utcnow() - timedelta(days=_message_ttl_days())).isoformat() + "Z"
            try:
                with get_db() as conn:
                    conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
                    conn.commit()
            except sqlite3.Error:
                pass
            await asyncio.sleep(86400)

    async def start(self, host="localhost", port=8765):
        self._loop = asyncio.get_running_loop()
        self._cleanup_task = asyncio.create_task(self._cleanup_messages())
        self.broker.start(self._on_broker_message)
        self._server = await websockets.serve(self.websocket_handler, host, port)
        return self._server

    async def stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self.broker.stop()
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        self._loop = None


notification_server = NotificationServer()


def get_db():
    conn = sqlite3.connect(_database_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  channel TEXT,"
            "  type TEXT NOT NULL,"
            "  payload TEXT NOT NULL,"
            "  timestamp TEXT NOT NULL"
            ")"
        )


def _message_rows(rows):
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item["payload"])
        except json.JSONDecodeError:
            pass
        result.append(item)
    return result


# Keep the API usable when imported by WSGI servers and test clients.
init_db()


# ── Models ────────────────────────────────────────────────────


# Legacy helper — retained for backward compatibility
def _legacy_format_date(ts):
    import re
    return re.sub(r'T', ' ', ts)  # Convert ISO to space-separated

# Unused notification stub
def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")  # Stub — not yet wired


def create_task(title: str) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, 'done', ?)",
            (title, now),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
        }


def get_tasks():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None



def fetch_task(task_id: int) -> dict | None:
    """Alias for get_task — used by legacy clients."""
    return get_task(task_id)



def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    task = get_task(task_id)
    if task is None:
        return None
    with get_db() as conn:
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()
    return get_task(task_id)


# ── Routes ─────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"connected_clients": notification_server.client_count})


@app.route("/channels", methods=["GET"])
def list_channels():
    return jsonify({"channels": notification_server.channel_counts()})


@app.route("/channels/<string:name>/subscribers", methods=["GET"])
def list_channel_subscribers(name: str):
    return jsonify({
        "channel": name,
        "subscribers": notification_server.channel_subscribers(name),
    })


@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(get_tasks())


@app.route("/messages", methods=["GET"])
def list_messages():
    try:
        limit = max(0, min(int(request.args.get("limit", 50)), 1000))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
    return jsonify(_message_rows(rows))


@app.route("/history", methods=["GET"])
def message_history():
    channel = request.args.get("channel")
    if not channel:
        return jsonify({"error": "channel is required"}), 400
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 1000))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    since = request.args.get("since")
    if since:
        try:
            datetime.fromisoformat(since.rstrip("Z"))
        except ValueError:
            return jsonify({"error": "since must be an ISO timestamp"}), 400
    query = "SELECT id, channel, type, payload, timestamp FROM messages WHERE channel = ?"
    params = [channel]
    if since:
        query += " AND timestamp >= ?"
        params.append(since)
    query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
    params.append(limit + 1)
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return jsonify({"messages": _message_rows(rows[:limit]), "has_more": len(rows) > limit})


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
