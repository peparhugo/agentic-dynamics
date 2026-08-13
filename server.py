"""WebSocket notification server.

An asyncio-based server (built on the ``websockets`` library) that:

* accepts WebSocket connections and assigns each client a unique id,
* broadcasts messages to every connected client,
* delivers direct messages to a single client,
* tracks connections in a thread-safe registry,
* supports named channels that clients can subscribe/unsubscribe to,
* routes every message through a Redis pub/sub backbone so multiple
  server instances can share the same delivery network,
* mirrors client connection state into Redis so it survives restarts,
* persists every message to a SQLite history database,
* exposes ``GET /health``, ``GET /channels``,
  ``GET /channels/{name}/subscribers`` and ``GET /messages`` as plain
  HTTP endpoints.

Message format
--------------
Every message is JSON: ``{"type": str, "payload": dict, "timestamp": str}``
Supported ``type`` values:

* ``"broadcast"``   - delivered to every connected client, or to the
  subscribers of a named channel when the message carries a ``channel``
  field (either top-level or inside ``payload``),
* ``"direct"``      - delivered to a single client,
* ``"subscribe"``   - subscribe the sender to a named ``channel``,
* ``"unsubscribe"`` - unsubscribe the sender from a named ``channel``,
* ``"system"``      - server lifecycle notices (e.g. the connect welcome).

Configuration
-------------
* ``REDIS_URL``    - broker connection URL (default ``redis://localhost:6379/0``)
* ``DATABASE_URL`` - SQLite database path (default ``messages.db``)
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

import websockets
from websockets.asyncio.server import Server, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Request, Response

from broker import ConnectionState, MessageBroker, MessageStore
from registry import ClientRegistry


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a message dict following the required wire format."""
    return {"type": msg_type, "payload": payload, "timestamp": utc_now_iso()}


def dumps_message(msg_type: str, payload: Dict[str, Any]) -> str:
    """Serialize a message dict to JSON for sending."""
    return json.dumps(make_message(msg_type, payload))


class NotificationServer:
    """WebSocket notification server with a REST health endpoint."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        broker: Optional[MessageBroker] = None,
        store: Optional[MessageStore] = None,
        channel: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        if broker is None:
            broker = MessageBroker(channel=channel or f"notifications:{uuid.uuid4().hex}")
        self.broker = broker
        self.store = store or MessageStore()
        self.state = ConnectionState(namespace=f"notif:{self.broker.channel}")
        self.instance_id = str(uuid.uuid4())
        self._ws_server: Optional[Server] = None

    # ── lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> "NotificationServer":
        """Start serving WebSocket connections, HTTP endpoints and the broker."""
        self._ws_server = await serve(
            self.handle_connection,
            self.host,
            self.port,
            process_request=self.process_request,
        )
        if self._ws_server.sockets:
            self.port = self._ws_server.sockets[0].getsockname()[1]
        await self.broker.start(self._on_broker_message)
        return self

    async def stop(self) -> None:
        """Shut the server down and wait for all handlers to finish."""
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None
        await self.broker.stop()

    # ── websocket handling ───────────────────────────────────────────────

    async def handle_connection(self, connection) -> None:
        """Assign a unique id and keep the client alive until it disconnects."""
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, connection)
        self.state.register(client_id)
        self._restore_membership(client_id)
        try:
            message = make_message(
                "system",
                {
                    "message": "connected",
                    "client_id": client_id,
                    "connected_clients": self.registry.count(),
                },
            )
            await connection.send(json.dumps(message))
            self.store.store_message(
                None, "system", message["payload"], message["timestamp"]
            )
            async for raw in connection:
                await self._on_message(connection, client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            self.state.unregister(client_id)

    async def _on_message(self, connection, client_id: str, raw: str) -> None:
        """Handle an inbound client message (broadcast / direct / channel requests)."""
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        msg_type = data.get("type")
        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        if msg_type == "broadcast":
            self.broadcast(payload, channel=self._channel_from(data, payload))
        elif msg_type == "direct":
            target = data.get("target")
            if target:
                await self.direct(target, payload)
        elif msg_type == "subscribe":
            channel = self._channel_from(data, payload)
            if channel:
                self.subscribe(client_id, channel)
        elif msg_type == "unsubscribe":
            channel = self._channel_from(data, payload)
            if channel:
                self.unsubscribe(client_id, channel)

    @staticmethod
    def _channel_from(data: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]:
        """Extract a channel name from a message, top-level or in ``payload``."""
        channel = data.get("channel")
        if channel is None and isinstance(payload, dict):
            channel = payload.get("channel")
        return channel

    # ── messaging API ────────────────────────────────────────────────────

    def broadcast(
        self,
        payload: Dict[str, Any],
        channel: Optional[str] = None,
    ) -> None:
        """Send a ``"broadcast"`` message to clients.

        When ``channel`` is given (or present as a ``"channel"`` key inside
        ``payload``) the message is delivered only to the subscribers of that
        channel. Otherwise it goes to every connected client.

        The message is published to the Redis backbone and persisted to the
        history database; delivery to local clients happens in the broker
        subscriber task so every instance behaves identically.
        """
        if channel is None and isinstance(payload, dict):
            channel = payload.get("channel")
        message = make_message("broadcast", payload)
        envelope = self._envelope(
            "broadcast", channel=channel, payload=payload, timestamp=message["timestamp"]
        )
        self._persist_envelope(envelope)
        self.broker.publish(envelope)

    async def direct(self, client_id: str, payload: Dict[str, Any]) -> bool:
        """Send a ``"direct"`` message to one client.

        The message is published to the Redis backbone so any instance
        holding the client can deliver it. Returns True when the client is
        connected to this instance, False otherwise.
        """
        local = self.registry.get(client_id) is not None
        message = make_message("direct", payload)
        envelope = self._envelope(
            "direct",
            channel=None,
            payload=payload,
            target=client_id,
            timestamp=message["timestamp"],
        )
        self._persist_envelope(envelope)
        self.broker.publish(envelope)
        return local

    def _envelope(
        self,
        msg_type: str,
        channel: Optional[str],
        payload: Dict[str, Any],
        target: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build the wire envelope published to the Redis backbone."""
        return {
            "type": msg_type,
            "channel": channel,
            "target": target,
            "payload": payload,
            "timestamp": timestamp or utc_now_iso(),
            "sender": self.instance_id,
        }

    def _persist_envelope(self, envelope: Dict[str, Any]) -> None:
        self.store.store_message(
            envelope.get("channel"),
            envelope.get("type"),
            envelope.get("payload") or {},
            envelope.get("timestamp"),
        )

    async def _on_broker_message(self, envelope: Dict[str, Any]) -> None:
        """Deliver an envelope received from the Redis backbone locally."""
        msg_type = envelope.get("type")
        payload = envelope.get("payload") or {}
        if msg_type == "broadcast":
            channel = envelope.get("channel")
            if channel:
                targets = self.registry.connections_for_channel(channel)
            else:
                targets = self.registry.connections()
            if targets:
                websockets.broadcast(targets, dumps_message("broadcast", payload))
        elif msg_type == "direct":
            target = envelope.get("target")
            if target:
                connection = self.registry.get(target)
                if connection is not None:
                    try:
                        await self._send(connection, "direct", payload)
                    except ConnectionClosed:
                        pass

    # ── channel API ──────────────────────────────────────────────────────

    def subscribe(self, client_id: str, channel: str) -> bool:
        """Subscribe ``client_id`` to ``channel``.

        Returns False when ``client_id`` is not a connected client.
        """
        ok = self.registry.subscribe(client_id, channel)
        if ok:
            self.state.subscribe(client_id, channel)
        return ok

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        """Unsubscribe ``client_id`` from ``channel``.

        Returns False when ``client_id`` was not subscribed to ``channel``.
        """
        ok = self.registry.unsubscribe(client_id, channel)
        if ok:
            self.state.unsubscribe(client_id, channel)
        return ok

    def channels(self) -> Dict[str, int]:
        """Return a mapping of channel name -> subscriber count."""
        return self.registry.channels()

    def subscribers(self, channel: str) -> list:
        """Return the ids of clients subscribed to ``channel``."""
        return self.registry.subscribers(channel)

    # ── connection state (Redis) ─────────────────────────────────────────

    def _restore_membership(self, client_id: str) -> None:
        """Re-apply Redis-persisted channel memberships for ``client_id``."""
        for channel in self.state.channels_of(client_id):
            self.registry.subscribe(client_id, channel)

    def restore_state(self) -> Dict[str, List[str]]:
        """Re-hydrate in-memory channel membership from Redis state.

        Returns a mapping of ``client_id`` -> restored channel list for every
        currently registered client that had persisted memberships.
        """
        restored: Dict[str, List[str]] = {}
        for client_id in self.registry.ids():
            channels = self.state.channels_of(client_id)
            for channel in channels:
                self.registry.subscribe(client_id, channel)
            if channels:
                restored[client_id] = sorted(channels)
        return restored

    async def _send(self, connection, msg_type: str, payload: Dict[str, Any]) -> None:
        await connection.send(dumps_message(msg_type, payload))

    # ── REST endpoints ───────────────────────────────────────────────────

    async def process_request(self, connection, request: Request) -> Optional[Response]:
        """Serve HTTP endpoints; everything else is treated as WebSocket."""
        parts = urlsplit(request.path)
        path = parts.path
        query = parse_qs(parts.query)
        if path == "/health":
            body = json.dumps(
                {"connected_clients": self.registry.count()}
            ).encode("utf-8")
        elif path == "/channels":
            body = json.dumps(
                {"channels": self.registry.channels()}
            ).encode("utf-8")
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            name = path[len("/channels/") : -len("/subscribers")]
            if not name:
                return None
            body = json.dumps(
                {"channel": name, "subscribers": self.registry.subscribers(name)}
            ).encode("utf-8")
        elif path == "/messages":
            try:
                limit = int(query.get("limit", ["50"])[0])
            except (TypeError, ValueError):
                limit = 50
            try:
                offset = int(query.get("offset", ["0"])[0])
            except (TypeError, ValueError):
                offset = 0
            limit = max(0, min(limit, 500))
            offset = max(0, offset)
            body = json.dumps(
                {"messages": self.store.list_messages(limit=limit, offset=offset)}
            ).encode("utf-8")
        else:
            return None
        headers = Headers(
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ]
        )
        return Response(200, "OK", headers, body)


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the notification server until interrupted."""
    server = NotificationServer(
        host=host, port=port, channel=MessageBroker.DEFAULT_CHANNEL
    )

    async def _run() -> None:
        await server.start()
        print(f"notification server listening on ws://{server.host}:{server.port}")
        try:
            await asyncio.Future()
        finally:
            await server.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
