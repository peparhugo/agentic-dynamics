"""
WebSocket-based notification server.

Core features:
  * Accept WebSocket connections from clients.
  * Assign each client a unique ID on connect.
  * Broadcast a message to ALL connected clients.
  * Handle client disconnect (clean removal).
  * REST endpoint: GET /health - returns the connected client count.

Message format (JSON):
  {"type": str, "payload": dict, "timestamp": str}

Supported message types: "broadcast", "direct", "system".

All data is persisted in flat files (JSON Lines) - no databases.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

logger = logging.getLogger("notification_server")

BROADCAST = "broadcast"
DIRECT = "direct"
SYSTEM = "system"
MSG_TYPES = (BROADCAST, DIRECT, SYSTEM)

HEALTH_PATH = "/health"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a well-formed notification message dict."""
    return {
        "type": msg_type,
        "payload": dict(payload),
        "timestamp": utc_now_iso(),
    }


class EventLog:
    """Append-only JSON Lines log backed by a flat file.

    Safe to use from multiple threads: each write acquires a lock and
    flushes immediately so data survives process crashes.
    """

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()

    def append(self, event: str, data: dict) -> None:
        if self.path is None:
            return
        record = {
            "event": event,
            "data": data,
            "timestamp": utc_now_iso(),
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
                fh.flush()

    def read(self) -> list[dict]:
        if self.path is None or not self.path.exists():
            return []
        with self._lock:
            with self.path.open("r", encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]


class ClientRegistry:
    """Thread-safe registry mapping unique client IDs to connections."""

    def __init__(self):
        self._clients: dict[str, object] = {}
        self._lock = threading.RLock()

    def register(self, connection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def unregister(self, client_id: str) -> bool:
        with self._lock:
            return self._clients.pop(client_id, None) is not None

    def get(self, client_id: str):
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return dict(self._clients)


class NotificationServer:
    """Async WebSocket notification server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765,
                 log_path: str | Path | None = None):
        self.host = host
        self.requested_port = port
        self.registry = ClientRegistry()
        self.event_log = EventLog(log_path)
        self._server = None

    # -- lifecycle -----------------------------------------------------

    async def start(self) -> "NotificationServer":
        self._server = await serve(
            self.handle_connection,
            self.host,
            self.requested_port,
            process_request=self.process_request,
        )
        return self

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def port(self) -> int:
        if self._server is not None and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self.requested_port

    # -- HTTP ----------------------------------------------------------

    def process_request(self, connection, request):
        """Serve the /health REST endpoint over plain HTTP."""
        path = request.path.split("?", 1)[0]
        if path == HEALTH_PATH:
            body = json.dumps({
                "status": "ok",
                "connected_clients": self.registry.count(),
            }).encode("utf-8")
            return Response(
                status_code=200,
                reason_phrase="OK",
                headers=Headers([("Content-Type", "application/json")]),
                body=body,
            )
        return None

    # -- websocket ------------------------------------------------------

    async def handle_connection(self, connection) -> None:
        client_id = self.registry.register(connection)
        self.event_log.append("connected", {"client_id": client_id})
        try:
            await connection.send(json.dumps(build_message(SYSTEM, {
                "event": "connected",
                "client_id": client_id,
            })))
            async for raw in connection:
                try:
                    message = json.loads(raw)
                except (TypeError, ValueError):
                    self.event_log.append(
                        "invalid_message", {"client_id": client_id}
                    )
                    continue
                if not isinstance(message, dict):
                    continue
                await self._dispatch(client_id, message)
        except ConnectionClosed:
            pass
        finally:
            self.registry.unregister(client_id)
            self.event_log.append("disconnected", {"client_id": client_id})

    async def _dispatch(self, client_id: str, message: dict) -> None:
        msg_type = message.get("type")
        payload = message.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        if msg_type == BROADCAST:
            data = dict(payload)
            data.setdefault("sender", client_id)
            await self.broadcast(data)
        elif msg_type == DIRECT:
            target = payload.get("target")
            await self.send_direct(target, payload)
        elif msg_type == SYSTEM:
            self.event_log.append("system", {
                "client_id": client_id,
                "payload": payload,
            })
        else:
            self.event_log.append("unknown_type", {
                "client_id": client_id,
                "type": str(msg_type),
            })

    async def broadcast(self, payload: dict) -> int:
        """Send a broadcast message to every connected client."""
        message = json.dumps(build_message(BROADCAST, payload))
        sent = 0
        for client_id, conn in list(self.registry.snapshot().items()):
            try:
                await conn.send(message)
                sent += 1
            except ConnectionClosed:
                self.registry.unregister(client_id)
        return sent

    async def send_direct(self, target_id: str, payload: dict) -> bool:
        """Send a direct message to a single client."""
        conn = self.registry.get(target_id)
        if conn is None:
            self.event_log.append("direct_undelivered", {
                "target": target_id,
            })
            return False
        message = json.dumps(build_message(DIRECT, payload))
        try:
            await conn.send(message)
        except ConnectionClosed:
            self.registry.unregister(target_id)
            return False
        return True


def run_server(host: str = "127.0.0.1", port: int = 8765,
               log_path: str | Path | None = None) -> None:
    """Blocking entry point: run the server until interrupted."""

    async def _main() -> None:
        server = NotificationServer(host=host, port=port, log_path=log_path)
        await server.start()
        logger.info("Notification server listening on ws://%s:%s",
                    host, server.port)
        try:
            await asyncio.Future()  # run forever
        finally:
            await server.close()

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server()
