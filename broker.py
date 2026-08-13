"""Redis pub/sub message backbone shared by notification server instances.

Every routed message is published to a Redis channel. Each server instance
subscribes to the backbone pattern and delivers messages to its own connected
clients, so multiple server instances can share a single Redis broker.

Redis key layout (all prefixed with ``notifications``):

* Pub/sub channels:
  * ``notifications:broadcast``     — messages for every client.
  * ``notifications:channel:<name>``— messages for channel ``<name>``.
  * ``notifications:direct:<id>``   — messages for client ``<id>``.

* State keys:
  * ``notifications:channels``                       — SET of active channels.
  * ``notifications:sub:<channel>``                  — SET of subscribed clients.
  * ``notifications:client_channels:<client_id>``    — SET of channels a client
    subscribes to.
  * ``notifications:client:<client_id>``             — JSON connection state.
  * ``notifications:ratelimit:<client_id>``          — INCR counter for the
    per-client message rate limit window.
  * ``notifications:id_counter``                     — INCR for client ids.

The connection is configured through the ``REDIS_URL`` environment variable.
When it is unset (or starts with ``fakeredis://``) an in-memory fakeredis
client is used so the server works without a running Redis.
"""

from __future__ import annotations

import os

import redis.asyncio as aioredis

try:
    import fakeredis
except ImportError:  # pragma: no cover
    fakeredis = None

KEY_PREFIX = "notifications"

# Pub/sub channels.
BROADCAST_CHANNEL = f"{KEY_PREFIX}:broadcast"
CHANNEL_PREFIX = f"{KEY_PREFIX}:channel:"
DIRECT_PREFIX = f"{KEY_PREFIX}:direct:"

# Pattern every worker subscribes to.
SUBSCRIBE_PATTERN = f"{KEY_PREFIX}:*"

# State keys.
CHANNELS_KEY = f"{KEY_PREFIX}:channels"
SUB_KEY_PREFIX = f"{KEY_PREFIX}:sub:"
CLIENT_CHANNELS_PREFIX = f"{KEY_PREFIX}:client_channels:"
CLIENT_STATE_PREFIX = f"{KEY_PREFIX}:client:"
RATE_LIMIT_PREFIX = f"{KEY_PREFIX}:ratelimit:"
ID_COUNTER_KEY = f"{KEY_PREFIX}:id_counter"

DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"


def channel_redis_channel(channel: str) -> str:
    """Return the Redis pub/sub channel used for a named channel."""
    return f"{CHANNEL_PREFIX}{channel}"


def direct_redis_channel(client_id: str) -> str:
    """Return the Redis pub/sub channel used for a direct message target."""
    return f"{DIRECT_PREFIX}{client_id}"


def sub_key(channel: str) -> str:
    """Return the Redis SET key holding a channel's subscribers."""
    return f"{SUB_KEY_PREFIX}{channel}"


def client_channels_key(client_id: str) -> str:
    """Return the Redis SET key holding a client's subscriptions."""
    return f"{CLIENT_CHANNELS_PREFIX}{client_id}"


def client_state_key(client_id: str) -> str:
    """Return the Redis key holding a client's connection state."""
    return f"{CLIENT_STATE_PREFIX}{client_id}"


def rate_limit_key(client_id: str) -> str:
    """Return the Redis key holding a client's rate-limit counter."""
    return f"{RATE_LIMIT_PREFIX}{client_id}"


def decode(value: bytes | str) -> str:
    """Decode a bytes value returned by Redis into a string."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def create_redis_client(url: str | None = None):
    """Create an async Redis client.

    Honors the ``REDIS_URL`` environment variable. Falls back to an in-memory
    fakeredis client when ``REDIS_URL`` is unset or starts with ``fakeredis://``.
    """
    url = (url or os.environ.get("REDIS_URL") or "").strip()
    if fakeredis is not None:
        if not url or url.startswith("fakeredis://"):
            return fakeredis.FakeAsyncRedis()
    if url:
        return aioredis.Redis.from_url(url)
    return aioredis.Redis.from_url(DEFAULT_REDIS_URL)
