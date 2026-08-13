"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote, urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
CONTROL_TYPES = {"subscribe", "unsubscribe"}


def timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> str:
    data = {"type": message_type, "payload": payload, "timestamp": timestamp()}
    if channel is not None:
        data["channel"] = channel
    return json.dumps(data, separators=(",", ":"))


class ClientRegistry:
    """A registry safe to inspect or mutate from any thread."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, websocket: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._subscriptions):
                subscribers = self._subscriptions[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._subscriptions[channel]

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self, channel: str | None = None) -> list[ServerConnection]:
        with self._lock:
            if channel is not None:
                return [
                    self._clients[client_id]
                    for client_id in self._subscriptions.get(channel, set())
                    if client_id in self._clients
                ]
            return list(self._clients.values())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._subscriptions[channel]

    def is_subscribed(self, client_id: str, channel: str) -> bool:
        with self._lock:
            return client_id in self._subscriptions.get(channel, set())

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(self._subscriptions.items())
            ]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._subscriptions.get(channel, set()))

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients = ClientRegistry()
        self._server: Server | None = None

    async def _send(self, websocket: ServerConnection, data: str) -> None:
        try:
            await websocket.send(data)
        except Exception:
            # The connection handler owns registry cleanup.
            return

    async def broadcast(self, data: str, channel: str | None = None) -> None:
        recipients = self.clients.snapshot(channel)
        if recipients:
            await asyncio.gather(*(self._send(client, data) for client in recipients))

    async def process_message(
        self, client_id: str, websocket: ServerConnection, raw: str | bytes
    ) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await websocket.send(message("system", {"error": "invalid JSON"}))
            return

        if not isinstance(data, dict):
            await websocket.send(message("system", {"error": "message must be an object"}))
            return

        message_type = data.get("type")
        payload = data.get("payload")
        if message_type not in SUPPORTED_TYPES:
            await websocket.send(
                message("system", {"error": "type must be supported and payload must be an object"})
            )
            return

        channel = data.get("channel")
        if channel is None and message_type in CONTROL_TYPES and isinstance(payload, dict):
            channel = payload.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel.strip()):
            await websocket.send(message("system", {"error": "channel must be a non-empty string"}))
            return

        if message_type in CONTROL_TYPES:
            if channel is None:
                await websocket.send(
                    message("system", {"error": "channel must be a non-empty string"})
                )
                return
            if message_type == "subscribe":
                self.clients.subscribe(client_id, channel)
            else:
                self.clients.unsubscribe(client_id, channel)
            return

        if not isinstance(payload, dict):
            await websocket.send(
                message("system", {"error": "type must be supported and payload must be an object"})
            )
            return

        outgoing = message(message_type, payload, channel)
        if message_type == "direct":
            target_id = payload.get("target_id")
            target = self.clients.get(target_id) if isinstance(target_id, str) else None
            if target is None:
                await websocket.send(message("system", {"error": "target client not found"}))
                return
            if channel is not None and not self.clients.is_subscribed(target_id, channel):
                return
            await self._send(target, outgoing)
        else:
            await self.broadcast(outgoing, channel)

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = self.clients.add(websocket)
        try:
            await websocket.send(message("system", {"event": "connected", "client_id": client_id}))
            async for raw in websocket:
                await self.process_message(client_id, websocket, raw)
        finally:
            self.clients.remove(client_id)

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        del connection
        path = urlsplit(request.path).path
        if path == "/health":
            response_data: dict[str, Any] = {"connected_clients": self.clients.count}
        elif path == "/channels":
            response_data = {"channels": self.clients.channels()}
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not encoded_name or "/" in encoded_name:
                return None
            channel = unquote(encoded_name)
            response_data = {
                "channel": channel,
                "subscribers": self.clients.subscribers(channel),
            }
        else:
            return None

        body = json.dumps(response_data).encode("utf-8")
        headers = Headers(
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Connection", "close"),
            ]
        )
        return Response(HTTPStatus.OK, "OK", headers, body)

    async def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("server is already running")
        self._server = await serve(
            self.handler,
            self.host,
            self.port,
            process_request=self.process_request,
        )
        sockets = self._server.sockets
        if sockets:
            self.port = sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def run_forever(self) -> None:
        await self.start()
        assert self._server is not None
        await self._server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        asyncio.run(NotificationServer(args.host, args.port).run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
