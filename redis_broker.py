"""Redis pub/sub message backbone for the notification server.

The server publishes every outbound message to a Redis channel; every server
instance shares the same Redis, subscribes to the channels its local clients
care about, and delivers what it receives to those local clients. Client
connection state (who is connected, which channels they subscribed to) is also
kept in Redis so it survives a server restart.
"""

import asyncio
import json
import logging

from redis.asyncio import from_url

log = logging.getLogger(__name__)

DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"

# ── channel / key naming ─────────────────────────────────────

BROADCAST_CHANNEL = "notif:broadcast"
CHANNEL_PUBSUB_PREFIX = "notif:chan:"
CLIENT_PUBSUB_PREFIX = "notif:client:"
CLIENT_STATE_TTL_SECONDS = 86400


def channel_pubsub_channel(channel: str) -> str:
    """Redis pub/sub channel used to distribute messages for a named channel."""
    return f"{CHANNEL_PUBSUB_PREFIX}{channel}"


def client_pubsub_channel(client_id: str) -> str:
    """Redis pub/sub channel used to deliver direct messages to a client."""
    return f"{CLIENT_PUBSUB_PREFIX}{client_id}"


def clients_set_key() -> str:
    """Redis set holding the IDs of all known (connected) clients."""
    return "notif:clients"


def client_state_key(client_id: str) -> str:
    """Redis key holding a client's persisted connection state."""
    return f"notif:state:{client_id}"


def channel_subs_key(channel: str) -> str:
    """Redis set holding the client IDs subscribed to a named channel."""
    return f"notif:subs:{channel}"


def client_channels_key(client_id: str) -> str:
    """Redis set holding the channels a client is subscribed to."""
    return f"notif:channels:{client_id}"


def channel_pubsub_keys() -> tuple[str, str]:
    """(match pattern, prefix length) for scanning channel subscription sets."""
    return "notif:subs:*", len("notif:subs:")


def _decode(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


class RedisBackbone:
    """Redis pub/sub backbone with Redis-backed client state."""

    def __init__(self, redis_client=None, redis_url: str | None = None) -> None:
        self._redis = redis_client
        self._redis_url = redis_url or DEFAULT_REDIS_URL
        self._owns_client = redis_client is None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._dispatch = None
        self._channel_refs: dict[str, int] = {}

    # ── lifecycle ─────────────────────────────────────────────

    async def start(self, dispatch) -> "RedisBackbone":
        """Open the pub/sub connection and start the listener task.

        ``dispatch`` is an async callable ``(channel, message_dict) -> None``
        invoked for every message received on a subscribed channel.
        """
        if self._redis is None:
            self._redis = from_url(self._redis_url, decode_responses=True)
            self._owns_client = True
        self._dispatch = dispatch
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(BROADCAST_CHANNEL)
        self._channel_refs = {BROADCAST_CHANNEL: 1}
        self._listener_task = asyncio.create_task(self._listen())
        return self

    async def stop(self) -> None:
        """Stop the listener and close pub/sub + client connections."""
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._owns_client and self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def _listen(self) -> None:
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "message":
                    continue
                channel = _decode(message.get("channel"))
                data = message.get("data")
                try:
                    payload = json.loads(_decode(data))
                except (TypeError, ValueError):
                    continue
                if self._dispatch is not None:
                    await self._dispatch(channel, payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Redis pub/sub listener failed")

    # ── publishing ────────────────────────────────────────────

    async def publish_broadcast(self, message: dict) -> None:
        """Publish a message to every server instance."""
        await self._publish(BROADCAST_CHANNEL, message)

    async def publish_channel(self, channel: str, message: dict) -> None:
        """Publish a message to subscribers of a named channel."""
        await self._publish(channel_pubsub_channel(channel), message)

    async def publish_client(self, client_id: str, message: dict) -> None:
        """Publish a message destined for a single client by ID."""
        await self._publish(client_pubsub_channel(client_id), message)

    async def _publish(self, channel: str, message: dict) -> None:
        await self._redis.publish(channel, json.dumps(message))

    # ── pub/sub subscription management ───────────────────────

    async def ensure_subscribed(self, channel: str) -> None:
        """Subscribe the listener to a channel, reference-counted."""
        key = channel_pubsub_channel(channel)
        self._channel_refs[key] = self._channel_refs.get(key, 0) + 1
        if self._channel_refs[key] == 1:
            await self._pubsub.subscribe(key)

    async def ensure_unsubscribed(self, channel: str) -> None:
        """Release one reference on a channel subscription."""
        key = channel_pubsub_channel(channel)
        if key not in self._channel_refs:
            return
        self._channel_refs[key] -= 1
        if self._channel_refs[key] <= 0:
            self._channel_refs.pop(key, None)
            await self._pubsub.unsubscribe(key)

    async def ensure_client_channel(self, client_id: str) -> None:
        """Subscribe the listener to a client's direct-message channel."""
        await self._pubsub.subscribe(client_pubsub_channel(client_id))

    # ── client connection state ───────────────────────────────

    async def store_client_state(self, client_id: str, state: dict) -> None:
        """Persist a client's connection state in Redis with a TTL."""
        await self._redis.set(
            client_state_key(client_id),
            json.dumps(state),
            ex=CLIENT_STATE_TTL_SECONDS,
        )
        await self._redis.sadd(clients_set_key(), client_id)

    async def get_client_state(self, client_id: str) -> dict | None:
        """Return a client's persisted state, or None if unknown."""
        raw = await self._redis.get(client_state_key(client_id))
        if raw is None:
            return None
        try:
            return json.loads(_decode(raw))
        except (TypeError, ValueError):
            return None

    async def known_client_ids(self) -> list[str]:
        """Return all client IDs currently recorded in Redis."""
        return [_decode(x) for x in await self._redis.smembers(clients_set_key())]

    async def remove_client_state(self, client_id: str) -> None:
        """Remove all persisted state for a client."""
        await self._redis.delete(client_state_key(client_id))
        await self._redis.srem(clients_set_key(), client_id)

    async def add_channel_subscriber(self, channel: str, client_id: str) -> None:
        """Record that a client subscribed to a channel."""
        await self._redis.sadd(channel_subs_key(channel), client_id)
        await self._redis.sadd(client_channels_key(client_id), channel)

    async def remove_channel_subscriber(self, channel: str, client_id: str) -> None:
        """Record that a client unsubscribed from a channel."""
        await self._redis.srem(channel_subs_key(channel), client_id)
        await self._redis.srem(client_channels_key(client_id), channel)

    async def load_channel_subscriptions(self) -> dict[str, set[str]]:
        """Load {channel: {client_id, ...}} from Redis."""
        subscriptions: dict[str, set[str]] = {}
        match, prefix_len = channel_pubsub_keys()
        async for raw_key in self._redis.scan_iter(match=match):
            key = _decode(raw_key)
            channel = key[prefix_len:]
            members = {
                _decode(x)
                for x in await self._redis.smembers(key)
            }
            if members:
                subscriptions[channel] = members
        return subscriptions
