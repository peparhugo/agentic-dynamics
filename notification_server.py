"""
WebSocket-based notification server.

Core features:
- Accept WebSocket connections from clients.
- Assign each client a unique ID on connect.
- Broadcast a message to ALL connected clients.
- Handle client disconnect (clean removal).
- REST endpoint GET /health returning the connected client count.

Message format (all messages are JSON):
    {"type": str, "payload": dict, "timestamp": str}
Supported types: "broadcast", "direct", "system".

Protocol (client -> server):
- {"type": "broadcast", "payload": {...}}    -> relayed to every connected client.
- {"type": "direct", "target_id": "...", "payload": {...}} -> delivered to one client.
- {"type": "system", ...}                    -> ignored (server-only).

Protocol (server -> client):
- On connect, the new client receives:
    {"type": "system", "payload": {"event": "connect", "client_id": "...",
     "connected_clients": N}, "timestamp": "..."}
- On disconnect, every remaining client receives a matching "disconnect" event.
- Errors are delivered back to the offending client as a "system" error event.

Uses the `websockets` library (asyncio implementation) and a lock-guarded
client registry that is safe to use across asyncio tasks/threads.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


def now_iso() -> str:
    """Current UTC time as an ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a message conforming to the shared JSON schema."""
    return {"type": msg_type, "payload": payload, "timestamp": now_iso()}


class ClientRegistry:
    """
    Thread-safe registry mapping unique client IDs to websocket connections.

    Access is guarded by an asyncio.Lock so concurrent handlers (and external
    threads using the same event loop) never observe partial state.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    async def add(self, client_id: str, websocket: ServerConnection) -> None:
        async with self._lock:
            self._clients[client_id] = websocket

    async def remove(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            return self._clients.pop(client_id, None)

    async def get(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def contains(self, client_id: str) -> bool:
        async with self._lock:
            return client_id in self._clients

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def ids(self) -> list[str]:
        async with self._lock:
            return list(self._clients.keys())

    async def snapshot(self) -> dict[str, ServerConnection]:
        async with self._lock:
            return dict(self._clients)


class NotificationServer:
    """Handles websocket sessions, message dispatch and the /health endpoint."""

    def __init__(self, registry: ClientRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()
        self._next_id = 0
        self._id_lock = asyncio.Lock()

    # ── Lifecycle ────────────────────────────────────────────────────

    async def _assign_id(self) -> str:
        async with self._id_lock:
            self._next_id += 1
            return str(self._next_id)

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Session handler: register, notify, relay messages, clean up."""
        client_id = await self._assign_id()
        await self.registry.add(client_id, websocket)
        try:
            await self._send_connect_notice(client_id, websocket)
            async for raw in websocket:
                await self._dispatch(client_id, websocket, raw)
        except ConnectionClosed:
            pass
        finally:
            await self._shutdown_client(client_id)

    async def _send_connect_notice(self, client_id: str, websocket) -> None:
        count = await self.registry.count()
        message = build_message(
            "system",
            {"event": "connect", "client_id": client_id, "connected_clients": count},
        )
        try:
            await websocket.send(json.dumps(message))
        except ConnectionClosed:
            pass

    async def _shutdown_client(self, client_id: str) -> None:
        removed = await self.registry.remove(client_id)
        if removed is None:
            return
        count = await self.registry.count()
        message = build_message(
            "system",
            {"event": "disconnect", "client_id": client_id, "connected_clients": count},
        )
        await self.broadcast(message)

    # ── Message dispatch ────────────────────────────────────────────

    async def _dispatch(self, sender_id: str, websocket, raw) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(
                sender_id, "invalid JSON message", target_id=None
            )
            return

        if not isinstance(data, dict):
            await self._send_error(sender_id, "message must be a JSON object")
            return

        msg_type = data.get("type")
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            await self._send_error(sender_id, "payload must be a JSON object")
            return

        if msg_type == "broadcast":
            await self.broadcast(build_message("broadcast", payload))
        elif msg_type == "direct":
            target_id = data.get("target_id") or payload.get("target_id")
            await self._send_direct(sender_id, target_id, payload)
        elif msg_type == "system":
            # System messages are generated by the server only.
            pass
        else:
            await self._send_error(sender_id, f"unsupported message type: {msg_type!r}")

    async def _send_direct(self, sender_id: str, target_id, payload: dict) -> None:
        if not isinstance(target_id, str) or not target_id:
            await self._send_error(sender_id, "direct message requires a target_id")
            return
        if not await self.registry.contains(target_id):
            await self._send_error(
                sender_id, "target not found", target_id=target_id
            )
            return
        message = build_message("direct", payload)
        ws = await self.registry.get(target_id)
        try:
            await ws.send(json.dumps(message))
        except ConnectionClosed:
            await self.registry.remove(target_id)

    async def _send_error(self, sender_id: str, message: str, target_id=None) -> None:
        payload = {"event": "error", "message": message}
        if target_id is not None:
            payload["target_id"] = target_id
        ws = await self.registry.get(sender_id)
        if ws is None:
            return
        try:
            await ws.send(json.dumps(build_message("system", payload)))
        except ConnectionClosed:
            await self.registry.remove(sender_id)

    # ── Outgoing ────────────────────────────────────────────────────

    async def broadcast(self, message: dict, exclude: set[str] | None = None) -> int:
        """Send *message* to every connected client. Returns count delivered."""
        exclude = exclude or set()
        encoded = json.dumps(message)
        delivered = 0
        for client_id, websocket in (await self.registry.snapshot()).items():
            if client_id in exclude:
                continue
            try:
                await websocket.send(encoded)
                delivered += 1
            except ConnectionClosed:
                await self.registry.remove(client_id)
        return delivered

    # ── REST endpoint ───────────────────────────────────────────────

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Intercept plain HTTP requests; GET /health reports client count."""
        if request.path.split("?")[0] == "/health":
            count = await self.registry.count()
            body = json.dumps(
                {"status": "ok", "connected_clients": count}
            ).encode("utf-8")
            headers = Headers(
                {"Content-Type": "application/json", "Content-Length": str(len(body))}
            )
            return Response(200, "OK", headers, body)
        return None


class NotificationApp:
    """Wraps a websockets server bound to a host/port for easy (test) control."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        notifier: NotificationServer | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.notifier = notifier or NotificationServer()
        self.server = None

    async def start(self) -> "NotificationApp":
        self.server = await serve(
            self.notifier.handle_client,
            self.host,
            self.port,
            process_request=self.notifier.process_request,
        )
        if self.port == 0:
            self.port = self.server.sockets[0].getsockname()[1]
        return self

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None


async def main(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Entry point: run the notification server until interrupted."""
    notifier = NotificationServer()
    async with serve(
        notifier.handle_client,
        host,
        port,
        process_request=notifier.process_request,
    ) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
