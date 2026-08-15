"""
WebSocket-based notification server built on the `websockets` library.

Features:
- Accepts WebSocket connections from clients.
- Assigns each client a unique ID on connect.
- Broadcasts a message to ALL connected clients.
- Sends direct messages to a specific client.
- Supports named channels: clients subscribe/unsubscribe dynamically
  and channel-scoped messages are delivered only to subscribers.
- Handles client disconnect with clean removal from the registry.
- REST endpoints: GET /health, GET /channels, GET /channels/{name}/subscribers,
  GET /messages.

Message distribution runs over a configurable message backbone (see
`broker.py`):

- When ``REDIS_URL`` is set, the server uses Redis pub/sub. Every message is
  published to a single Redis channel and every server instance subscribed to
  the same Redis receives it and delivers to its local clients, so multiple
  server instances can share the same backbone. Client connection and
  subscription state is mirrored in Redis and survives server restarts.
- Without ``REDIS_URL`` the server falls back to an in-process backbone that
  delivers messages directly, preserving the historical single-instance
  behaviour.

All distributed messages are persisted to SQLite (``DATABASE_URL``) and can be
queried via ``GET /messages?limit=50&offset=0``.

Message format (JSON):
    {type: str, payload: dict, timestamp: str}

Supported types: 'broadcast', 'direct', 'system', 'subscribe', 'unsubscribe'.

Channel routing:
- A message with a top-level 'channel' field (or one inside its payload)
  is delivered only to clients subscribed to that channel.
- A message without a 'channel' field broadcasts to all connected clients.

Thread-safety: asyncio runs everything on a single event loop, so the
client registry needs no locking; plain dict reads/writes are safe by
construction.
"""

import asyncio
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Response

from broker import (
    Broker,
    LocalBroker,
    MessageStore,
    default_backbone,
)

SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
WELCOME_TIMEOUT = 5.0


def make_message(msg_type: str, payload: dict) -> dict:
    """Build a message dict in the canonical wire format."""
    if msg_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class NotificationServer:
    """Async WebSocket notification server with a Redis-backed message backbone."""

    def __init__(self, backbone: Broker | None = None, store: MessageStore | None = None) -> None:
        # client_id -> ServerConnection for connections owned by THIS instance.
        self._clients: dict[str, ServerConnection] = {}
        # channel name -> set of client_ids subscribed to that channel (local mirror).
        self._local_channels: dict[str, set[str]] = {}
        # client_id -> set of channel names the client is subscribed to (local mirror).
        self._client_channels: dict[str, set[str]] = {}
        self._backbone = backbone or default_backbone()
        if isinstance(self._backbone, LocalBroker) and self._backbone.server is None:
            self._backbone.server = self
        self._store = store or MessageStore()
        self._consumer_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def client_ids(self) -> list[str]:
        return list(self._clients)

    @property
    def channel_names(self) -> list[str]:
        return list(self._local_channels)

    # ── Channel subscriptions ─────────────────────────────────

    def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a named channel."""
        if not channel:
            raise ValueError("channel name must be non-empty")
        self._local_channels.setdefault(channel, set()).add(client_id)
        self._client_channels.setdefault(client_id, set()).add(channel)
        if self._backbone.remote_state and self._loop is not None:
            self._background(self._backbone.subscribe(client_id, channel))

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a named channel."""
        subs = self._local_channels.get(channel)
        if subs is None:
            return
        subs.discard(client_id)
        if not subs:
            del self._local_channels[channel]
        own = self._client_channels.get(client_id)
        if own is not None:
            own.discard(channel)
            if not own:
                del self._client_channels[client_id]
        if self._backbone.remote_state and self._loop is not None:
            self._background(self._backbone.unsubscribe(client_id, channel))

    def subscribed_channels(self, client_id: str) -> list[str]:
        """List the channels a client is currently subscribed to."""
        return sorted(self._client_channels.get(client_id, set()))

    def channel_subscribers(self, channel: str) -> list[str]:
        """Return the IDs of clients subscribed to a channel."""
        return sorted(self._local_channels.get(channel, set()))

    def channels_info(self) -> list[dict]:
        """Return info for all active channels: name and subscriber count."""
        return [
            {"name": name, "subscribers": len(subs)}
            for name, subs in sorted(self._local_channels.items())
        ]

    def _drop_client(self, client_id: str) -> None:
        """Remove a client from the registry and all channel subscriptions."""
        self._clients.pop(client_id, None)
        self._client_channels.pop(client_id, None)
        if self._local_channels:
            for name, subs in list(self._local_channels.items()):
                subs.discard(client_id)
                if not subs:
                    del self._local_channels[name]
        if self._backbone.remote_state and self._loop is not None:
            self._background(self._backbone.unregister_client(client_id))

    def _background(self, coro) -> None:
        """Run a fire-and-forget coroutine, swallowing background failures."""

        def _done(task: asyncio.Task) -> None:
            if not task.cancelled():
                task.exception()

        task = self._loop.create_task(coro)
        task.add_done_callback(_done)

    # ── Outbound send helpers ───────────────────────────────────

    async def _send(self, connection: ServerConnection, message: dict) -> None:
        await connection.send(json.dumps(message))

    async def _record(self, message: dict, channel: str | None = None) -> None:
        """Persist a distributed message to the SQLite history store."""
        try:
            await self._store.store(message, channel)
        except Exception:
            pass

    async def _system(
        self,
        connection: ServerConnection,
        event: str,
        error: str | None = None,
    ) -> None:
        """Send (and record) a system message to a single connection."""
        payload = {"event": event}
        if error is not None:
            payload["error"] = error
        message = make_message("system", payload)
        await self._record(message)
        await self._send(connection, message)

    async def _deliver_event(self, event: dict) -> None:
        """Deliver a backbone event to the clients this instance owns."""
        message = event.get("message") or {}
        for client_id in event.get("targets") or []:
            connection = self._clients.get(client_id)
            if connection is None:
                continue
            try:
                await self._send(connection, message)
            except Exception:
                self._drop_client(client_id)

    async def broadcast(self, payload: dict, channel: str | None = None) -> int:
        """Send a 'broadcast' message to clients.

        When ``channel`` is given, the message is delivered only to clients
        subscribed to that channel; otherwise it goes to every connected
        client. Returns the number of clients the message was targeted at.
        """
        message = make_message("broadcast", payload)
        await self._record(message, channel)
        if channel is None:
            targets = await self._backbone.active_client_ids()
            targets = list(set(targets) | set(self._clients))
        else:
            targets = await self._backbone.channel_subscribers(channel)
        event = {
            "message": message,
            "channel": channel,
            "targets": targets,
        }
        await self._backbone.publish(event)
        return len(targets)

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        """Send a 'direct' message to a single client. Returns success."""
        connection = self._clients.get(client_id)
        message = make_message("direct", payload)
        await self._record(message)
        if connection is not None:
            try:
                await self._send(connection, message)
                return True
            except Exception:
                self._clients.pop(client_id, None)
                return False
        known = await self._backbone.active_client_ids()
        if client_id in known:
            await self._backbone.publish(
                {"message": message, "channel": None, "targets": [client_id]}
            )
            return True
        return False

    # ── Connection lifecycle ────────────────────────────────────

    async def handle_connection(self, websocket: ServerConnection) -> None:
        """Per-connection coroutine: register, welcome, serve, clean up."""
        client_id = await self._backbone.next_client_id()
        self._clients[client_id] = websocket
        if self._backbone.remote_state:
            await self._backbone.register_client(client_id)
        try:
            welcome = make_message(
                "system", {"event": "connected", "client_id": client_id}
            )
            await self._record(welcome)
            await self._send(websocket, welcome)
            async for raw in websocket:
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    await self._system(websocket, "error", error="invalid JSON message")
                    continue
                if not isinstance(data, dict) or data.get("type") not in SUPPORTED_TYPES:
                    await self._system(websocket, "error", error="unsupported message")
                    continue
                payload = data.get("payload") or {}
                msg_type = data["type"]
                if msg_type == "broadcast":
                    channel = data.get("channel") or payload.get("channel")
                    await self.broadcast(payload, channel=channel)
                elif msg_type == "subscribe":
                    channel = data.get("channel") or payload.get("channel")
                    if not channel:
                        await self._system(websocket, "error", error="subscribe missing channel")
                    else:
                        self.subscribe(client_id, channel)
                elif msg_type == "unsubscribe":
                    channel = data.get("channel") or payload.get("channel")
                    if not channel:
                        await self._system(websocket, "error", error="unsubscribe missing channel")
                    else:
                        self.unsubscribe(client_id, channel)
                elif msg_type == "direct":
                    target = payload.get("target_id")
                    if target is None:
                        await self._system(
                            websocket, "error", error="direct message missing target_id"
                        )
                    elif not await self.send_direct(target, payload):
                        await self._system(
                            websocket, "error", error=f"unknown client {target!r}"
                        )
        finally:
            # Clean removal regardless of how the connection ended.
            self._drop_client(client_id)

    # ── HTTP (REST) handling ────────────────────────────────────

    def _json_response(self, status: int, data: dict) -> Response:
        body = json.dumps(data).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            }
        )
        return Response(status, "OK" if status == 200 else "Not Found", headers, body)

    async def process_request(self, connection: ServerConnection, request) -> Response | None:
        """Handle plain HTTP requests (e.g. GET /health) before WS upgrade."""
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None

        split = urlsplit(request.path)
        path = split.path
        if path == "/health":
            return self._json_response(
                200, {"clients": self.client_count, "status": "ok"}
            )
        if path == "/channels":
            return self._json_response(
                200, {"channels": self.channels_info()}
            )
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = path[len("/channels/"):-len("/subscribers")]
            return self._json_response(
                200,
                {"channel": name, "subscribers": self.channel_subscribers(name)},
            )
        if path == "/messages":
            query = parse_qs(split.query)
            limit = self._int_query(query, "limit", 50)
            offset = self._int_query(query, "offset", 0)
            messages = await self._store.list(limit, offset)
            return self._json_response(
                200,
                {
                    "messages": messages,
                    "limit": limit,
                    "offset": offset,
                },
            )
        return None

    @staticmethod
    def _int_query(query: dict, key: str, default: int) -> int:
        try:
            return max(int(query.get(key, [str(default)])[0]), 0)
        except (ValueError, TypeError):
            return default

    # ── Lifecycle ───────────────────────────────────────────────

    async def _hydrate(self) -> None:
        """Reload subscription state from the backbone after a restart."""
        if not self._backbone.remote_state:
            return
        for name in await self._backbone.channel_names():
            subs = set(await self._backbone.channel_subscribers(name))
            self._local_channels[name] = subs
            for client_id in subs:
                self._client_channels.setdefault(client_id, set()).add(name)

    async def start(self, host: str = "localhost", port: int = 8765) -> None:
        self._loop = asyncio.get_running_loop()
        await self._store.init()
        await self._hydrate()
        if self._backbone.consumable:
            self._consumer_task = asyncio.create_task(
                self._backbone.consume(self._deliver_event)
            )
        self._server = await serve(
            self.handle_connection,
            host,
            port,
            process_request=self.process_request,
        )

    async def stop(self) -> None:
        self._clients.clear()
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except (asyncio.CancelledError, Exception):
                pass
            self._consumer_task = None
        await self._backbone.close()
        await self._store.close()
        self._server.close()
        await self._server.wait_closed()


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    """Run the notification server until interrupted."""
    server = NotificationServer()
    await server.start(host, port)
    print(f"Notification server listening on ws://{host}:{port}")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
