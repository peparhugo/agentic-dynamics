"""WebSocket-based notification server.

A minimal async notification server built on the ``websockets`` library
(not Flask-SocketIO). Each connected client is assigned a unique ID on
connect. Clients may send messages to trigger broadcasts or direct
delivery. Every message is framed as JSON:

    {"type": str, "payload": dict, "timestamp": str}

Supported message types: ``broadcast``, ``direct``, ``system``.

A REST endpoint ``GET /health`` reports the number of connected clients.

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

SUPPORTED_TYPES = ("broadcast", "direct", "system")


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
            if msg_type == "broadcast":
                message = build_message("broadcast", payload)
                await registry.broadcast(message)
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
        if self.path.rstrip("/") == "/health":
            body = json.dumps(
                {"status": "ok", "clients": self.registry.count}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

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
