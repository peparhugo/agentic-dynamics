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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

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


def message_ttl_days() -> int:
    """Return the message retention window in days from ``MESSAGE_TTL_DAYS``."""
    return int(os.environ.get("MESSAGE_TTL_DAYS", "7"))


def rate_limit_value() -> int:
    """Return the per-client per-minute message limit from ``RATE_LIMIT``."""
    return int(os.environ.get("RATE_LIMIT", "100"))


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp into a tz-aware UTC ``datetime``.

    Handles ``Z`` suffixes and naive timestamps (assumed UTC). Returns None
    when the value cannot be parsed.
    """
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_iso(value: Optional[str]) -> Optional[str]:
    """Normalize an ISO-8601 timestamp to UTC ``isoformat()`` or None."""
    dt = _parse_iso(value)
    return dt.isoformat() if dt is not None else None


def _ts_before(timestamp: str, cutoff: datetime) -> bool:
    """Return True when ``timestamp`` parses and is older than ``cutoff``."""
    dt = _parse_iso(timestamp)
    return dt is not None and dt < cutoff


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

    @staticmethod
    def _decode(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row into a dict with ``payload`` JSON-parsed."""
        message = dict(row)
        try:
            message["payload"] = json.loads(message["payload"])
        except (TypeError, ValueError):
            pass
        return message

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
        return [self._decode(row) for row in rows]

    def query_history(
        self,
        channel: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Return messages for ``channel`` from ``since`` in chronological order.

        Filters on an exact channel name when ``channel`` is given and only
        returns messages with ``timestamp >= since`` when ``since`` is given.
        Returns ``(messages, has_more)`` where ``has_more`` tells the caller
        whether another page of results is available for pagination.
        """
        clauses: List[str] = []
        params: List[Any] = []
        if channel is not None:
            clauses.append("channel = ?")
            params.append(channel)
        since_iso = _normalize_iso(since)
        if since_iso is not None:
            clauses.append("timestamp >= ?")
            params.append(since_iso)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, channel, type, payload, timestamp FROM messages"
                    f"{where} ORDER BY id ASC LIMIT ? OFFSET ?",
                    (*params, int(limit) + 1, int(offset)),
                ).fetchall()
        has_more = len(rows) > int(limit)
        return [self._decode(row) for row in rows[: int(limit)]], has_more

    def cleanup_expired(self, ttl_days: Optional[int] = None) -> int:
        """Delete messages older than ``ttl_days`` (default ``MESSAGE_TTL_DAYS``).

        Returns the number of messages removed.
        """
        ttl_days = int(
            ttl_days if ttl_days is not None else message_ttl_days()
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT id, timestamp FROM messages").fetchall()
                expired = [
                    row["id"] for row in rows if _ts_before(row["timestamp"], cutoff)
                ]
                for message_id in expired:
                    conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
                conn.commit()
                return len(expired)

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


class RateLimiter:
    """Redis-backed per-client message rate limiter.

    Every client is allowed ``limit`` messages per ``window`` seconds. The
    count is stored in Redis under a per-client key so the limit is enforced
    consistently across every server instance sharing the same broker
    channel. Callers use :meth:`check` for each inbound client message and
    return an error to the client when it returns False.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        limit: Optional[int] = None,
        window: int = 60,
        namespace: str = "notif",
    ):
        self._redis = redis.Redis.from_url(url or redis_url())
        self.limit = int(limit if limit is not None else rate_limit_value())
        self.window = int(window)
        self.namespace = namespace

    def _key(self, client_id: str) -> str:
        return f"{self.namespace}:rate:{client_id}"

    def check(self, client_id: str) -> bool:
        """Record one message from ``client_id`` and return True when allowed."""
        key = self._key(client_id)
        count = int(self._redis.incr(key))
        if count == 1:
            self._redis.expire(key, self.window)
        return count <= self.limit

    def reset(self, client_id: str) -> None:
        """Clear the counter for ``client_id`` (mainly for tests)."""
        self._redis.delete(self._key(client_id))


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
