"""
Message backbone and persistence for the notification server.

This module provides two interchangeable backbones that carry messages
between server instances:

- ``RedisBroker``: the production backbone. Servers publish events to a
  single Redis pub/sub channel and every server instance (including the
  publisher) consumes that channel and delivers to its own local clients.
  Subscription/connection state is kept in Redis so it survives server
  restarts and is shared by every instance connected to the same Redis.
- ``LocalBroker``: an in-process fallback used when no ``REDIS_URL`` is
  configured. Delivery happens directly inside the publishing server so the
  server keeps its historical in-memory behaviour.

``MessageStore`` persists every distributed message to SQLite for history,
exposed through the REST endpoint ``GET /messages``.

Configuration is read from environment variables:

- ``REDIS_URL``      - connection URL for the Redis broker
                        (default: ``redis://localhost:6379/0``).
- ``DATABASE_URL``   - SQLite path for message history
                        (default: ``notifications.db``).
- ``MESSAGE_TTL_DAYS`` - messages older than this many days are cleaned up
                        by the background task at server startup
                        (default: 7).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_DATABASE_URL = "notifications.db"

FANOUT_CHANNEL = "notifications:fanout"
KEY_PREFIX = "notifications:"

CLIENTS_KEY = KEY_PREFIX + "clients"
COUNTER_KEY = KEY_PREFIX + "counter"


def _normalize_since(value: str) -> str:
    """Normalise a since timestamp into the server's canonical UTC format.

    Naive timestamps are assumed to be UTC. A value without microseconds
    (``...+00:00``) sorts before any ``....xxxxxx+00:00`` in the same second,
    so string comparison with stored timestamps stays correct.
    """
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _sqlite_path(url: str) -> str:
    """Normalise a DATABASE_URL value into a plain SQLite file path."""
    url = (url or "").strip() or DEFAULT_DATABASE_URL
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite:"):
        return url[len("sqlite:"):]
    return url


class MessageStore:
    """SQLite persistence for message history."""

    def __init__(self, path: str | None = None) -> None:
        self.path = _sqlite_path(path or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL)

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT,"
                "  type TEXT NOT NULL,"
                "  payload TEXT NOT NULL,"
                "  timestamp TEXT NOT NULL"
                ")"
            )
            await db.commit()

    async def store(self, message: dict, channel: str | None = None) -> int:
        """Insert a message and return its row id."""
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "INSERT INTO messages (channel, type, payload, timestamp)"
                " VALUES (?, ?, ?, ?)",
                (
                    channel,
                    message["type"],
                    json.dumps(message.get("payload") or {}),
                    message["timestamp"],
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return stored messages, newest first, paginated by limit/offset."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT id, channel, type, payload, timestamp"
                " FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }

    async def history(
        self,
        channel: str | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Return messages for a channel/time range in chronological order.

        ``channel`` filters by channel (None matches every channel). ``since``
        is an ISO-8601 timestamp; messages at or after it are returned.
        Paginated by ``limit``/``offset`` with a ``has_more`` flag.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if channel is not None:
            clauses.append("channel = ?")
            params.append(channel)
        if since:
            clauses.append("timestamp >= ?")
            params.append(_normalize_since(since))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                f"SELECT id, channel, type, payload, timestamp"
                f" FROM messages {where} ORDER BY id ASC LIMIT ? OFFSET ?",
                (*params, limit + 1, offset),
            )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "messages": [self._row_to_dict(row) for row in rows],
            "has_more": has_more,
        }

    async def cleanup(self, ttl_days: int = 7) -> int:
        """Delete messages older than ``ttl_days`` days; return rows removed."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff,)
            )
            await db.commit()
            return cursor.rowcount

    async def close(self) -> None:
        return None


class Broker:
    """Common interface implemented by all message backbones."""

    #: whether subscription/connection state is shared with other instances.
    remote_state = False
    #: whether the broker needs a background consumer task to receive events.
    consumable = False

    def __init__(self) -> None:
        self.server = None

    async def next_client_id(self) -> str:
        raise NotImplementedError

    async def register_client(self, client_id: str) -> None:
        raise NotImplementedError

    async def unregister_client(self, client_id: str) -> None:
        raise NotImplementedError

    async def subscribe(self, client_id: str, channel: str) -> None:
        raise NotImplementedError

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        raise NotImplementedError

    async def channel_subscribers(self, channel: str) -> list[str]:
        raise NotImplementedError

    async def subscribed_channels(self, client_id: str) -> list[str]:
        raise NotImplementedError

    async def channel_names(self) -> list[str]:
        raise NotImplementedError

    async def active_client_ids(self) -> list[str]:
        raise NotImplementedError

    async def publish(self, event: dict) -> None:
        raise NotImplementedError

    async def consume(self, deliver) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class LocalBroker(Broker):
    """In-process backbone: state and delivery live in the owning server."""

    def __init__(self) -> None:
        super().__init__()
        self._counter = 0

    async def next_client_id(self) -> str:
        self._counter += 1
        return str(self._counter)

    async def register_client(self, client_id: str) -> None:
        return None

    async def unregister_client(self, client_id: str) -> None:
        return None

    async def subscribe(self, client_id: str, channel: str) -> None:
        return None

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        return None

    async def channel_subscribers(self, channel: str) -> list[str]:
        return sorted(self.server._local_channels.get(channel, set()))

    async def subscribed_channels(self, client_id: str) -> list[str]:
        return sorted(self.server._client_channels.get(client_id, set()))

    async def channel_names(self) -> list[str]:
        return list(self.server._local_channels)

    async def active_client_ids(self) -> list[str]:
        return list(self.server._clients)

    async def publish(self, event: dict) -> None:
        await self.server._deliver_event(event)

    async def consume(self, deliver) -> None:
        return None

    async def close(self) -> None:
        return None


class RedisBroker(Broker):
    """Redis pub/sub backbone shared by every server instance."""

    remote_state = True
    consumable = True

    def __init__(
        self,
        client=None,
        url: str | None = None,
        server=None,
        fanout_channel: str = FANOUT_CHANNEL,
        key_prefix: str = KEY_PREFIX,
    ) -> None:
        super().__init__()
        self._fanout = fanout_channel
        self._prefix = key_prefix
        if client is not None:
            self._redis = client
        elif server is not None:
            import fakeredis.aioredis

            self._redis = fakeredis.aioredis.FakeRedis(
                server=server, decode_responses=True
            )
        else:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(
                url or os.environ.get("REDIS_URL") or DEFAULT_REDIS_URL,
                decode_responses=True,
            )
        self._pubsub = None

    # ── key helpers ────────────────────────────────────────────

    def _subs_key(self, channel: str) -> str:
        return f"{self._prefix}subs:{channel}"

    def _channels_key(self, client_id: str) -> str:
        return f"{self._prefix}channels:{client_id}"

    def _decode(self, value):
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return value

    # ── state API ──────────────────────────────────────────────

    async def next_client_id(self) -> str:
        value = await self._redis.incr(COUNTER_KEY)
        return str(value)

    async def register_client(self, client_id: str) -> None:
        await self._redis.sadd(CLIENTS_KEY, client_id)

    async def unregister_client(self, client_id: str) -> None:
        await self._redis.srem(CLIENTS_KEY, client_id)
        await self._redis.delete(self._channels_key(client_id))
        async for key in self._redis.scan_iter(match=f"{self._prefix}subs:*"):
            await self._redis.srem(self._decode(key), client_id)

    async def subscribe(self, client_id: str, channel: str) -> None:
        await self._redis.sadd(self._subs_key(channel), client_id)
        await self._redis.sadd(self._channels_key(client_id), channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        await self._redis.srem(self._subs_key(channel), client_id)
        await self._redis.srem(self._channels_key(client_id), channel)

    async def channel_subscribers(self, channel: str) -> list[str]:
        members = await self._redis.smembers(self._subs_key(channel))
        return sorted(self._decode(m) for m in members)

    async def subscribed_channels(self, client_id: str) -> list[str]:
        members = await self._redis.smembers(self._channels_key(client_id))
        return sorted(self._decode(m) for m in members)

    async def channel_names(self) -> list[str]:
        names = []
        async for key in self._redis.scan_iter(match=f"{self._prefix}subs:*"):
            key = self._decode(key)
            names.append(key[len(f"{self._prefix}subs:"):])
        return names

    async def active_client_ids(self) -> list[str]:
        members = await self._redis.smembers(CLIENTS_KEY)
        return [self._decode(m) for m in members]

    # ── pub/sub ────────────────────────────────────────────────

    async def publish(self, event: dict) -> None:
        await self._redis.publish(self._fanout, json.dumps(event))

    async def consume(self, deliver) -> None:
        """Consume the fanout channel and hand events to ``deliver``."""
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(self._fanout)
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    event = json.loads(self._decode(message.get("data")))
                except (TypeError, ValueError):
                    continue
                try:
                    await deliver(event)
                except Exception:
                    continue
        finally:
            try:
                await self._pubsub.unsubscribe(self._fanout)
            except Exception:
                pass
            try:
                await self._pubsub.aclose()
            except Exception:
                pass

    async def close(self) -> None:
        try:
            await self._redis.aclose()
        except Exception:
            pass


def default_backbone() -> Broker:
    """Build the backbone configured by the ``REDIS_URL`` environment var."""
    url = (os.environ.get("REDIS_URL") or "").strip()
    if url:
        return RedisBroker(url=url)
    return LocalBroker()
