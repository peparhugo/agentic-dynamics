"""WebSocket-based notification server.

A minimal async notification server built on the ``websockets`` library
(not Flask-SocketIO). Each connected client is assigned a unique ID on
connect. Clients may send messages to trigger broadcasts or direct
delivery. Every message is framed as JSON:

    {"type": str, "payload": dict, "timestamp": str}

Supported message types: ``broadcast``, ``direct``, ``system``,
``subscribe``, ``unsubscribe``.

Clients may subscribe to named channels (e.g. ``alerts``, ``system``,
``chat``). A message that carries a ``channel`` field is delivered only to
the clients subscribed to that channel; a message without one is broadcast
to every connected client.

REST endpoints: ``GET /health`` reports the number of connected clients,
``GET /channels`` lists active channels with subscriber counts, and
``GET /channels/{name}/subscribers`` lists a channel's subscriber IDs.

The client registry is shared between the asyncio WebSocket handlers and
a background OS thread running the HTTP health server, so it is guarded
with a ``threading.Lock`` (not ``asyncio.Lock``) to be truly thread-safe.
"""

import asyncio
import http.server
import json
import threading
import uuid
from datetime import datetime, timezone

import websockets

WS_HOST = "127.0.0.1"
WS_PORT = 8765
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8080

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def utcnow_iso() -> str:
    """Current UTC timestamp in ISO 8601 string form."""
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a well-formed notification message."""
    if msg_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    return {"type": msg_type, "payload": payload, "timestamp": utcnow_iso()}


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients.

    asyncio runs each coroutine on its own OS thread by default, so the
    registry is guarded with a ``threading.Lock`` (not ``asyncio.Lock``)
    to be truly thread-safe across threads. The lock also protects the
    registry from the background HTTP health-server thread.
    """

    def __init__(self) -> None:
        self._clients: dict[str, object] = {}
        self._channels: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def add(self, ws: object) -> str:
        """Register a connection and return its unique client id."""
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = ws
        return client_id

    def remove(self, client_id: str) -> None:
        """Remove a client id if present (idempotent)."""
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in self._client_channels.pop(client_id, ()):
                subscribers = self._channels.get(channel)
                if subscribers:
                    subscribers.discard(client_id)
                    if not subscribers:
                        del self._channels[channel]

    def get(self, client_id: str):
        """Return the connection for a client id, or ``None``."""
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict:
        """Return a copy of the current client map."""
        with self._lock:
            return dict(self._clients)

    @property
    def count(self) -> int:
        """Number of connected clients."""
        with self._lock:
            return len(self._clients)

    def subscribe(self, client_id: str, channel: str) -> bool:
        """Subscribe ``client_id`` to ``channel``.

        Returns ``True`` if the client exists and is now subscribed.
        Subscribing twice to the same channel is idempotent.
        """
        if self.get(client_id) is None:
            return False
        with self._lock:
            self._client_channels.setdefault(client_id, set()).add(channel)
            self._channels.setdefault(channel, set()).add(client_id)
        return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        """Unsubscribe ``client_id`` from ``channel``.

        Returns ``True`` if the client was subscribed, ``False`` otherwise.
        """
        with self._lock:
            subscribed = self._client_channels.get(client_id)
            if not subscribed or channel not in subscribed:
                return False
            subscribed.discard(channel)
            subscribers = self._channels.get(channel)
            if subscribers:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]
            return True

    def channels(self) -> dict:
        """Return a snapshot of ``{channel: {client_id, ...}}`` for active channels."""
        with self._lock:
            return {channel: set(ids) for channel, ids in self._channels.items() if ids}

    def channel_subscribers(self, channel: str) -> set:
        """Return a snapshot of the subscriber ids for ``channel`` (possibly empty)."""
        with self._lock:
            subscribers = self._channels.get(channel)
            return set(subscribers) if subscribers else set()

    async def broadcast_to_channel(self, channel: str, message: dict) -> int:
        """Send ``message`` to every client subscribed to ``channel``.

        Returns the number of clients that successfully received it.
        Failing connections are removed cleanly.
        """
        sent = 0
        dead = []
        for client_id in self.channel_subscribers(channel):
            ws = self.get(client_id)
            if ws is None:
                dead.append(client_id)
                continue
            try:
                await ws.send(json.dumps(message))
                sent += 1
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.remove(client_id)
        return sent

    async def broadcast(self, message: dict) -> int:
        """Send ``message`` to every connected client.

        Returns the number of clients that successfully received it.
        Failing connections are removed cleanly.
        """
        sent = 0
        dead = []
        for client_id, ws in self.snapshot().items():
            try:
                await ws.send(json.dumps(message))
                sent += 1
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.remove(client_id)
        return sent

    async def send_to(self, client_id: str, message: dict) -> bool:
        """Send ``message`` to one client. ``False`` if unknown/dead."""
        ws = self.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send(json.dumps(message))
            return True
        except Exception:
            self.remove(client_id)
            return False


async def ws_handler(ws, registry: ClientRegistry) -> None:
    """Handle a single WebSocket connection lifecycle."""
    client_id = registry.add(ws)
    try:
        welcome = build_message(
            "system", {"event": "connected", "client_id": client_id}
        )
        await ws.send(json.dumps(welcome))
        async for raw in ws:
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                await ws.send(
                    json.dumps(build_message("system", {"error": "invalid JSON"}))
                )
                continue
            if not isinstance(data, dict):
                await ws.send(
                    json.dumps(
                        build_message("system", {"error": "message must be a JSON object"})
                    )
                )
                continue
            msg_type = data.get("type")
            payload = data.get("payload") or {}
            channel = None
            if isinstance(payload, dict):
                channel = payload.get("channel") or data.get("channel")
            else:
                channel = data.get("channel")
            if not isinstance(channel, str):
                channel = None
            if msg_type == "broadcast":
                message = build_message("broadcast", payload)
                if channel:
                    message = dict(message, channel=channel)
                    await registry.broadcast_to_channel(channel, message)
                else:
                    await registry.broadcast(message)
            elif msg_type == "subscribe":
                if not channel:
                    await ws.send(
                        json.dumps(
                            build_message(
                                "system",
                                {"error": "subscribe message requires a channel"},
                            )
                        )
                    )
                    continue
                registry.subscribe(client_id, channel)
                await ws.send(
                    json.dumps(
                        build_message(
                            "system", {"event": "subscribed", "channel": channel}
                        )
                    )
                )
            elif msg_type == "unsubscribe":
                if not channel:
                    await ws.send(
                        json.dumps(
                            build_message(
                                "system",
                                {"error": "unsubscribe message requires a channel"},
                            )
                        )
                    )
                    continue
                registry.unsubscribe(client_id, channel)
                await ws.send(
                    json.dumps(
                        build_message(
                            "system", {"event": "unsubscribed", "channel": channel}
                        )
                    )
                )
            elif msg_type == "direct":
                target = payload.get("to")
                if not target:
                    await ws.send(
                        json.dumps(
                            build_message(
                                "system", {"error": "direct message missing payload.to"}
                            )
                        )
                    )
                    continue
                message = build_message("direct", payload)
                if not await registry.send_to(target, message):
                    await ws.send(
                        json.dumps(
                            build_message(
                                "system", {"error": f"no client with id {target}"}
                            )
                        )
                    )
            elif msg_type == "system":
                await ws.send(
                    json.dumps(build_message("system", {"echo": payload}))
                )
            else:
                await ws.send(
                    json.dumps(
                        build_message(
                            "system",
                            {"error": f"unsupported message type: {msg_type!r}"},
                        )
                    )
                )
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        registry.remove(client_id)


class HealthHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler exposing the connected client count at ``/health``."""

    registry = None

    def do_GET(self):
        path = self.path.rstrip("/") or "/"
        if path == "/health":
            body = json.dumps({"status": "ok", "clients": self.registry.count})
            self.send_json(200, body)
        elif path == "/channels":
            channels = self.registry.channels()
            payload = {
                "channels": [
                    {"name": name, "subscribers": len(subscribers)}
                    for name, subscribers in sorted(channels.items())
                ]
            }
            self.send_json(200, json.dumps(payload))
        elif path.startswith("/channels/"):
            name = path[len("/channels/"):]
            if name.endswith("/subscribers"):
                name = name[: -len("/subscribers")]
            subscribers = sorted(self.registry.channel_subscribers(name))
            self.send_json(
                200,
                json.dumps({"channel": name, "subscribers": subscribers}),
            )
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):
        pass


def start_health_server(registry, host: str = HTTP_HOST, port: int = HTTP_PORT):
    """Start the ``/health`` HTTP server on a background OS thread."""
    handler = type("BoundHealthHandler", (HealthHandler,), {"registry": registry})
    httpd = http.server.ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


async def make_server(
    ws_host: str = WS_HOST,
    ws_port: int = 0,
    http_host: str = HTTP_HOST,
    http_port: int = 0,
) -> dict:
    """Create a running notification server for programmatic use/tests.

    Returns a dict with the shared ``registry`` plus the actual bound
    ports (the default port ``0`` means "pick a free port").
    """
    registry = ClientRegistry()
    httpd = start_health_server(registry, host=http_host, port=http_port)
    ws_server = await websockets.serve(
        lambda ws: ws_handler(ws, registry), ws_host, ws_port
    )
    return {
        "registry": registry,
        "httpd": httpd,
        "ws_server": ws_server,
        "ws_port": ws_server.sockets[0].getsockname()[1],
        "http_port": httpd.server_address[1],
    }


async def main() -> None:
    """Run the notification server forever."""
    server = await make_server(ws_port=WS_PORT, http_port=HTTP_PORT)
    print(f"WebSocket server listening on ws://{WS_HOST}:{server['ws_port']}")
    print(f"Health endpoint on http://{HTTP_HOST}:{server['http_port']}/health")
    try:
        await asyncio.Future()
    finally:
        server["ws_server"].close()
        await server["ws_server"].wait_closed()
        server["httpd"].shutdown()
        server["httpd"].server_close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
