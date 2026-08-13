"""Redis pub/sub message backbone and SQLite message persistence.

The notification server uses Redis pub/sub channels to distribute messages
between server instances. Every routed message is wrapped in an *envelope*
dict and published to the broker channel; each server instance runs a
subscriber task that receives the envelope and delivers it to its local
clients. Because delivery is always driven by the shared Redis channel,
multiple server instances form a single logical backbone.

Client connection state (which clients exist and which channels they are
subscribed to) is mirrored into Redis so it can be re-hydrated after a
server restart, and every routed message is persisted to a SQLite history
database.

Configuration is read from environment variables:

* ``REDIS_URL``    - broker connection URL (default ``redis://localhost:6379/0``)
* ``DATABASE_URL`` - SQLite database path (default ``messages.db``)
"""

import asyncio
import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Set

import redis
from redis.asyncio import Redis as AsyncRedis


def redis_url() -> str:
    """Return the broker connection URL from ``REDIS_URL``."""
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def database_url() -> str:
    """Return the SQLite database URL from ``DATABASE_URL``."""
    return os.environ.get("DATABASE_URL", "messages.db")


def sqlite_path() -> str:
    """Convert ``DATABASE_URL`` to a plain SQLite file path."""
    url = database_url()
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    return url


class MessageStore:
    """SQLite-backed history of every routed message.

    The table schema is ``(id, channel, type, payload, timestamp)`` where
    ``payload`` is stored as JSON text and parsed back on read.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path or sqlite_path()
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS messages ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  channel TEXT,"
                    "  type TEXT,"
                    "  payload TEXT,"
                    "  timestamp TEXT"
                    ")"
                )

    def store_message(
        self,
        channel: Optional[str],
        msg_type: str,
        payload: Dict[str, Any],
        timestamp: str,
    ) -> int:
        """Insert one message into the history table and return its row id."""
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO messages (channel, type, payload, timestamp)"
                    " VALUES (?, ?, ?, ?)",
                    (channel, msg_type, json.dumps(payload), timestamp),
                )
                conn.commit()
                return int(cur.lastrowid)

    def list_messages(
        self, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Return stored messages newest-first, honoring ``limit``/``offset``."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, channel, type, payload, timestamp FROM messages"
                    " ORDER BY id DESC LIMIT ? OFFSET ?",
                    (int(limit), int(offset)),
                ).fetchall()
        messages = []
        for row in rows:
            message = dict(row)
            try:
                message["payload"] = json.loads(message["payload"])
            except (TypeError, ValueError):
                pass
            messages.append(message)
        return messages

    def count(self) -> int:
        """Return the total number of stored messages."""
        with self._lock:
            with self._connect() as conn:
                return int(conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0])


class ConnectionState:
    """Redis-backed record of client connection and channel membership.

    The in-memory :class:`ClientRegistry` remains the fast local source of
    truth for delivery; this store mirrors ``(client_id, channel)``
    membership into Redis so it can be re-hydrated after a server restart.
    """

    def __init__(self, url: Optional[str] = None, namespace: str = "notif"):
        self._redis = redis.Redis.from_url(url or redis_url())
        self.namespace = namespace

    def _clients_key(self) -> str:
        return f"{self.namespace}:clients"

    def _client_channels_key(self, client_id: str) -> str:
        return f"{self.namespace}:client:{client_id}:channels"

    def _channel_key(self, channel: str) -> str:
        return f"{self.namespace}:channel:{channel}"

    def register(self, client_id: str) -> None:
        """Record that ``client_id`` is connected."""
        self._redis.sadd(self._clients_key(), client_id)

    def unregister(self, client_id: str) -> None:
        """Remove ``client_id`` and all of its channel memberships."""
        pipe = self._redis.pipeline()
        pipe.srem(self._clients_key(), client_id)
        for channel in self.channels_of(client_id):
            pipe.srem(self._channel_key(channel), client_id)
        pipe.delete(self._client_channels_key(client_id))
        pipe.execute()

    def subscribe(self, client_id: str, channel: str) -> None:
        """Record that ``client_id`` subscribes to ``channel``."""
        pipe = self._redis.pipeline()
        pipe.sadd(self._channel_key(channel), client_id)
        pipe.sadd(self._client_channels_key(client_id), channel)
        pipe.execute()

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Record that ``client_id`` leaves ``channel``."""
        pipe = self._redis.pipeline()
        pipe.srem(self._channel_key(channel), client_id)
        pipe.srem(self._client_channels_key(client_id), channel)
        pipe.execute()

    def known_clients(self) -> Set[str]:
        """Return the set of client ids recorded in Redis."""
        return {c.decode() for c in self._redis.smembers(self._clients_key())}

    def channels_of(self, client_id: str) -> Set[str]:
        """Return the channels ``client_id`` is subscribed to in Redis."""
        return {
            c.decode()
            for c in self._redis.smembers(self._client_channels_key(client_id))
        }

    def subscribers(self, channel: str) -> List[str]:
        """Return the sorted client ids subscribed to ``channel`` in Redis."""
        return sorted(c.decode() for c in self._redis.smembers(self._channel_key(channel)))


class MessageBroker:
    """Redis pub/sub backbone that fans out envelopes to every server instance."""

    DEFAULT_CHANNEL = "notifications"

    def __init__(self, url: Optional[str] = None, channel: str = DEFAULT_CHANNEL):
        self.url = url or redis_url()
        self.channel = channel
        self._sync = redis.Redis.from_url(self.url)
        self._async = AsyncRedis.from_url(self.url)
        self._task: Optional[asyncio.Task] = None

    def ping(self) -> bool:
        """Return True when the Redis broker is reachable."""
        try:
            return bool(self._sync.ping())
        except redis.RedisError:
            return False

    def publish(self, envelope: Dict[str, Any]) -> None:
        """Publish an envelope dict to the broker channel."""
        self._sync.publish(self.channel, json.dumps(envelope))

    async def start(self, handler) -> None:
        """Subscribe to the broker channel and run ``handler`` per message."""
        pubsub = self._async.pubsub()
        await pubsub.subscribe(self.channel)
        self._task = asyncio.create_task(self._listen(pubsub, handler))

    async def _listen(self, pubsub, handler) -> None:
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(message["data"])
                except (TypeError, ValueError):
                    continue
                if not isinstance(envelope, dict):
                    continue
                try:
                    await handler(envelope)
                except Exception:
                    continue
        finally:
            try:
                await pubsub.close()
            except Exception:
                pass

    async def stop(self) -> None:
        """Stop the subscriber task and close the async connection."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        try:
            await self._async.aclose()
        except Exception:
            pass
