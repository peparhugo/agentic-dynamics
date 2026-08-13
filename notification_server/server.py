"""Notification server, built on a pluggable transport layer.

- Accepts connections through a Transport (see transport/, WebSocketTransport
  by default; select another with the TRANSPORT env var) and assigns each
  client a unique ID.
- Broadcasts messages to all connected clients, or routes a message to one
  specific client ("direct"), or emits server-originated "system" messages.
- Cleans up the client registry on disconnect.
- Exposes GET /health (plain HTTP, served via the websockets handshake hook)
  returning the number of currently connected clients.
- Persists an audit trail of every event to a flat JSON-Lines file, and a
  queryable history of every message to SQLite (GET /messages).
- Uses Redis pub/sub as the message-distribution backbone: every outgoing
  message is published to a shared channel, and a background worker task
  relays messages arriving from other server instances to locally connected
  clients. This lets multiple server processes share one backbone. Client
  connection presence is also mirrored into Redis so it is visible across
  instances and survives an individual server restart.
- Rate-limits each client's incoming messages using Redis counters (shared
  across instances the same way presence is), configurable via RATE_LIMIT.
  Clients over the limit get a "system"/"error" reply, not a silent drop.
- Exposes GET /history?channel=X&since=ISO_TIMESTAMP&limit=50 for paginated,
  chronological per-channel message history (SQLite-backed, has_more flag).
- Runs a background task that purges messages older than MESSAGE_TTL_DAYS
  (default 7) from the SQLite store on a fixed interval, starting at server
  startup.
"""

import argparse
import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from websockets.datastructures import Headers
from websockets.http11 import Response

from .db import DEFAULT_DB_PATH, MessageStore, resolve_database_path, resolve_message_ttl_days
from .messages import (
    MessageError,
    cutoff_iso,
    encode,
    make_message,
    now_iso,
    parse_client_message,
)
from .rate_limit import RateLimiter
from .redis_backend import RedisBackend, make_redis_client
from .registry import ChannelRegistry
from .storage import FlatFileStorage
from .transport import create_transport

logger = logging.getLogger("notification_server")

DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "events.jsonl"
DEFAULT_CLEANUP_INTERVAL_SECONDS = 3600

CHANNEL_SUBSCRIBERS_PATH_RE = re.compile(r"^/channels/([^/]+)/subscribers$")


class NotificationServer:
    def __init__(
        self,
        host="localhost",
        port=8765,
        storage_path=DEFAULT_DATA_PATH,
        database_url=None,
        redis_url=None,
        redis_client=None,
        transport=None,
        rate_limit=None,
        message_ttl_days=None,
        cleanup_interval_seconds=DEFAULT_CLEANUP_INTERVAL_SECONDS,
    ):
        self.host = host
        self.port = port
        self.server_id = str(uuid.uuid4())
        self.transport = transport or create_transport()
        self.registry = self.transport.registry
        self.channels = ChannelRegistry()
        self.storage = FlatFileStorage(storage_path)
        self.messages = MessageStore(resolve_database_path(database_url))
        self._owns_redis_client = redis_client is None
        self.redis = RedisBackend(redis_client or make_redis_client(redis_url))
        self.rate_limiter = RateLimiter(self.redis.client, limit=rate_limit)
        self.message_ttl_days = resolve_message_ttl_days(message_ttl_days)
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._redis_worker_task = None
        self._cleanup_task = None
        self._server = None

    # ── connection lifecycle ────────────────────────────────────
    #
    # These are invoked by the transport as connections come and go. The
    # transport itself knows nothing about notification semantics — it only
    # tracks client_id <-> connection and hands raw messages to us.

    async def _on_client_connect(self, client_id):
        await self.redis.register_client(client_id, self.server_id)
        self.storage.append_event(
            {"event": "connect", "client_id": client_id, "timestamp": now_iso()}
        )
        welcome = make_message("system", {"event": "connected", "client_id": client_id})
        await self.transport.send_message(client_id, encode(welcome))

    async def _on_client_disconnect(self, client_id):
        self.channels.unsubscribe_all(client_id)
        await self.redis.unregister_client(client_id)
        self.storage.append_event(
            {"event": "disconnect", "client_id": client_id, "timestamp": now_iso()}
        )

    async def _on_client_message(self, client_id, raw):
        await self._dispatch(client_id, raw)

    async def _dispatch(self, client_id, raw):
        if not await self.rate_limiter.allow(client_id):
            error = make_message(
                "system", {"event": "error", "detail": "rate_limit_exceeded"}
            )
            await self.transport.send_message(client_id, encode(error))
            return

        try:
            data = parse_client_message(raw)
        except MessageError as exc:
            error = make_message("system", {"event": "error", "detail": str(exc)})
            await self.transport.send_message(client_id, encode(error))
            return

        msg_type = data["type"]
        payload = data["payload"]
        timestamp = now_iso()
        self.storage.append_event(
            {
                "event": "message",
                "type": msg_type,
                "from": client_id,
                "payload": payload,
                "timestamp": timestamp,
            }
        )
        self.messages.save_message(msg_type, payload, timestamp, channel=payload.get("channel"))

        if msg_type == "broadcast":
            await self.broadcast(payload, sender_id=client_id)
        elif msg_type == "direct":
            target_id = payload.get("target_id")
            content = payload.get("content", {})
            delivered = await self.send_direct(target_id, content, sender_id=client_id)
            if not delivered:
                error = make_message(
                    "system", {"event": "error", "detail": f"unknown target_id: {target_id!r}"}
                )
                await self.transport.send_message(client_id, encode(error))
        elif msg_type == "system":
            ack = make_message("system", {"event": "ack"})
            await self.transport.send_message(client_id, encode(ack))
        elif msg_type == "subscribe":
            await self._handle_subscribe(client_id, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client_id, payload)

    async def _handle_subscribe(self, client_id, payload):
        channel = payload.get("channel")
        if not channel:
            error = make_message("system", {"event": "error", "detail": "channel is required"})
            await self.transport.send_message(client_id, encode(error))
            return
        self.channels.subscribe(channel, client_id)
        ack = make_message("system", {"event": "subscribed", "channel": channel})
        await self.transport.send_message(client_id, encode(ack))

    async def _handle_unsubscribe(self, client_id, payload):
        channel = payload.get("channel")
        if not channel:
            error = make_message("system", {"event": "error", "detail": "channel is required"})
            await self.transport.send_message(client_id, encode(error))
            return
        self.channels.unsubscribe(channel, client_id)
        ack = make_message("system", {"event": "unsubscribed", "channel": channel})
        await self.transport.send_message(client_id, encode(ack))

    # ── message delivery ────────────────────────────────────────
    #
    # Delivery to clients connected to *this* process happens directly
    # against the local registry, same as before. Every outgoing message is
    # additionally published to Redis so the worker loop in every other
    # server instance sharing the same backbone can relay it to clients
    # connected there.

    def _local_broadcast_targets(self, channel):
        if channel is not None:
            subscriber_ids = self.channels.subscribers(channel)
            return set(self.registry.all().keys()) & subscriber_ids
        return set(self.registry.all().keys())

    async def broadcast(self, payload, sender_id=None):
        body = dict(payload)
        if sender_id is not None:
            body.setdefault("sender_id", sender_id)
        message = make_message("broadcast", body)
        data = encode(message)
        channel = payload.get("channel")
        client_ids = self._local_broadcast_targets(channel)
        if client_ids:
            await self.transport.broadcast(client_ids, data)
        await self.redis.publish(
            {
                "origin_server_id": self.server_id,
                "kind": "broadcast",
                "channel": channel,
                "message": message,
            }
        )
        return message

    async def send_direct(self, target_id, content, sender_id=None) -> bool:
        message = make_message(
            "direct", {"content": content, "sender_id": sender_id, "target_id": target_id}
        )
        delivered_locally = await self.transport.send_message(target_id, encode(message))
        if delivered_locally:
            await self.redis.publish(
                {
                    "origin_server_id": self.server_id,
                    "kind": "direct",
                    "target_id": target_id,
                    "message": message,
                }
            )
            return True

        remote_server_id = await self.redis.get_client_server(target_id)
        if remote_server_id is None:
            return False
        await self.redis.publish(
            {
                "origin_server_id": self.server_id,
                "kind": "direct",
                "target_id": target_id,
                "message": message,
            }
        )
        return True

    async def send_system(self, target_id, payload) -> bool:
        message = make_message("system", payload)
        return await self.transport.send_message(target_id, encode(message))

    # ── redis worker: relay messages published by other instances ──

    async def _redis_worker_loop(self):
        try:
            async for envelope in self.redis.listen():
                if envelope.get("origin_server_id") == self.server_id:
                    continue
                await self._deliver_remote_envelope(envelope)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("redis worker loop crashed")

    async def _deliver_remote_envelope(self, envelope):
        message = envelope.get("message")
        if message is None:
            return
        data = encode(message)
        kind = envelope.get("kind")
        if kind == "broadcast":
            client_ids = self._local_broadcast_targets(envelope.get("channel"))
            if client_ids:
                await self.transport.broadcast(client_ids, data)
        elif kind == "direct":
            await self.transport.send_message(envelope.get("target_id"), data)

    # ── message expiry: periodically purge messages older than the TTL ──

    async def cleanup_expired_messages(self) -> int:
        return self.messages.delete_older_than(cutoff_iso(self.message_ttl_days))

    async def _cleanup_worker_loop(self):
        try:
            while True:
                try:
                    await self.cleanup_expired_messages()
                except Exception:
                    logger.exception("message cleanup pass failed")
                await asyncio.sleep(self.cleanup_interval_seconds)
        except asyncio.CancelledError:
            raise

    # ── REST: GET /health, /channels, /channels/{name}/subscribers, /messages

    def process_request(self, connection, request):
        parsed = urlsplit(request.path)
        path = parsed.path
        if path == "/health":
            return self._json_response({"connected_clients": self.registry.count()})
        if path == "/channels":
            channels = self.channels.channels()
            data = [
                {"name": name, "subscriber_count": len(subs)}
                for name, subs in sorted(channels.items())
            ]
            return self._json_response({"channels": data})
        if path == "/messages":
            query = parse_qs(parsed.query)
            limit = int(query.get("limit", ["50"])[0])
            offset = int(query.get("offset", ["0"])[0])
            messages = self.messages.list_messages(limit=limit, offset=offset)
            return self._json_response({"messages": messages, "limit": limit, "offset": offset})
        if path == "/history":
            query = parse_qs(parsed.query)
            channel = query.get("channel", [None])[0]
            if not channel:
                return self._json_response({"error": "channel is required"}, status=400)
            since = query.get("since", [None])[0]
            limit = int(query.get("limit", ["50"])[0])
            messages, has_more = self.messages.list_by_channel(channel, since=since, limit=limit)
            return self._json_response(
                {"messages": messages, "has_more": has_more, "limit": limit}
            )
        match = CHANNEL_SUBSCRIBERS_PATH_RE.match(path)
        if match:
            channel = match.group(1)
            subscribers = sorted(self.channels.subscribers(channel))
            return self._json_response({"channel": channel, "subscribers": subscribers})
        return None

    @staticmethod
    def _json_response(payload, status=200):
        body = json.dumps(payload).encode()
        headers = Headers(
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ]
        )
        reason = "OK" if status == 200 else "Bad Request"
        return Response(status, reason, headers, body)

    # ── run/serve ────────────────────────────────────────────────

    async def start(self):
        # Subscribe before accepting connections so no published message can
        # be missed by this instance's worker loop.
        await self.redis.subscribe()
        self._redis_worker_task = asyncio.create_task(self._redis_worker_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_worker_loop())
        self.transport.on_client_connect = self._on_client_connect
        self.transport.on_client_message = self._on_client_message
        self.transport.on_client_disconnect = self._on_client_disconnect
        self._server = await self.transport.start(
            self.host, self.port, http_handler=self.process_request
        )
        logger.info("notification server listening on ws://%s:%s", self.host, self.port)
        return self._server

    async def stop(self):
        if self._server is not None:
            await self.transport.stop()
            self._server = None
        if self._redis_worker_task is not None:
            self._redis_worker_task.cancel()
            try:
                await self._redis_worker_task
            except asyncio.CancelledError:
                pass
            self._redis_worker_task = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        await self.redis.close(close_client=self._owns_redis_client)

    async def serve_forever(self):
        await self.start()
        await self._server.wait_closed()


def main():
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--database-url", default=None, help="defaults to $DATABASE_URL")
    parser.add_argument("--redis-url", default=None, help="defaults to $REDIS_URL")
    parser.add_argument(
        "--rate-limit", type=int, default=None, help="messages/min per client; defaults to $RATE_LIMIT"
    )
    parser.add_argument(
        "--message-ttl-days",
        type=float,
        default=None,
        help="defaults to $MESSAGE_TTL_DAYS",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    server = NotificationServer(
        host=args.host,
        port=args.port,
        storage_path=args.data,
        database_url=args.database_url,
        redis_url=args.redis_url,
        rate_limit=args.rate_limit,
        message_ttl_days=args.message_ttl_days,
    )
    asyncio.run(server.serve_forever())


if __name__ == "__main__":
    main()
