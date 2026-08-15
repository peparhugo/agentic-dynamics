"""WebSocket notification server with an HTTP health endpoint."""

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
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def utc_timestamp() -> str:
    """Return an ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a message in the server's wire format."""
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": utc_timestamp(),
    }


class ClientRegistry:
    """A registry safe for access from the event loop and other threads."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, client_id: str, connection: ServerConnection) -> None:
        with self._lock:
            self._clients[client_id] = connection

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

    def snapshot(self) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            return list(self._clients.items())

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

    def channel_snapshot(self, channel: str) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            subscribers = self._subscriptions.get(channel, set())
            return [
                (client_id, connection)
                for client_id, connection in self._clients.items()
                if client_id in subscribers
            ]

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": channel, "subscriber_count": len(subscribers)}
                for channel, subscribers in sorted(self._subscriptions.items())
            ]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._subscriptions.get(channel, set()))

    def is_subscribed(self, client_id: str, channel: str) -> bool:
        with self._lock:
            return client_id in self._subscriptions.get(channel, set())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    """Manage WebSocket clients and route notification messages."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients = ClientRegistry()
        self._server: Server | None = None

    @property
    def connected_count(self) -> int:
        return len(self.clients)

    @property
    def bound_port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server is not running")
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("server is already running")
        self._server = await serve(
            self.handle_connection,
            self.host,
            self.port,
            process_request=self.process_request,
        )

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def __aenter__(self) -> NotificationServer:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

    def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Serve HTTP API requests without a second framework or port."""
        del connection
        path = urlsplit(request.path).path
        if path == "/health":
            return self._json_response({"connected_clients": self.connected_count})
        if path == "/channels":
            return self._json_response({"channels": self.clients.channels()})

        prefix = "/channels/"
        suffix = "/subscribers"
        if path.startswith(prefix) and path.endswith(suffix):
            encoded_name = path[len(prefix) : -len(suffix)]
            if encoded_name and "/" not in encoded_name:
                channel = unquote(encoded_name)
                return self._json_response(
                    {
                        "channel": channel,
                        "subscribers": self.clients.subscribers(channel),
                    }
                )
        return None

    @staticmethod
    def _json_response(payload: dict[str, Any]) -> Response:
        body = json.dumps(payload).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
                "Connection": "close",
            }
        )
        return Response(HTTPStatus.OK, "OK", headers, body)

    async def handle_connection(self, connection: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        self.clients.add(client_id, connection)
        try:
            await self._send(
                connection,
                message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw_message in connection:
                await self.handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            self.clients.remove(client_id)

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        connection = self.clients.get(sender_id)
        if connection is None:
            return

        try:
            incoming = self._parse_message(raw_message)
        except ValueError as exc:
            await self._send(connection, message("system", {"error": str(exc)}))
            return

        message_type = incoming["type"]
        if message_type in {"subscribe", "unsubscribe"}:
            channel = incoming.get("channel", incoming["payload"].get("channel"))
            if not isinstance(channel, str) or not channel:
                await self._send(
                    connection,
                    message("system", {"error": f"{message_type} requires channel"}),
                )
                return
            if message_type == "subscribe":
                self.clients.subscribe(sender_id, channel)
            else:
                self.clients.unsubscribe(sender_id, channel)
            return

        if message_type in {"broadcast", "system"}:
            await self.broadcast(incoming, incoming.get("channel"))
            return

        target_id = incoming["payload"].get("client_id")
        if not isinstance(target_id, str) or not target_id:
            await self._send(
                connection,
                message("system", {"error": "direct payload requires client_id"}),
            )
            return

        target = self.clients.get(target_id)
        if target is None:
            await self._send(
                connection,
                message("system", {"error": "client not connected", "client_id": target_id}),
            )
            return
        channel = incoming.get("channel")
        if channel is not None and not self.clients.is_subscribed(target_id, channel):
            return
        await self._send(target, incoming)

    async def broadcast(
        self, notification: dict[str, Any], channel: str | None = None
    ) -> None:
        """Send a notification to all clients or one channel's subscribers."""
        clients = (
            self.clients.snapshot()
            if channel is None
            else self.clients.channel_snapshot(channel)
        )
        if not clients:
            return

        results = await asyncio.gather(
            *(self._send(connection, notification) for _, connection in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, ConnectionClosed):
                self.clients.remove(client_id)

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> dict[str, Any]:
        try:
            decoded = json.loads(raw_message)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("message must be valid JSON") from exc

        if not isinstance(decoded, dict):
            raise ValueError("message must be a JSON object")
        required_fields = {"type", "payload", "timestamp"}
        if set(decoded) not in (required_fields, required_fields | {"channel"}):
            raise ValueError("message requires type, payload, and timestamp")
        if decoded["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(decoded["payload"], dict):
            raise ValueError("payload must be an object")
        if not isinstance(decoded["timestamp"], str) or not decoded["timestamp"]:
            raise ValueError("timestamp must be a non-empty string")
        if "channel" in decoded and (
            not isinstance(decoded["channel"], str) or not decoded["channel"]
        ):
            raise ValueError("channel must be a non-empty string")
        return decoded

    @staticmethod
    async def _send(
        connection: ServerConnection, notification: dict[str, Any]
    ) -> None:
        await connection.send(json.dumps(notification, separators=(",", ":")))


async def run(host: str, port: int) -> None:
    server = NotificationServer(host, port)
    await server.start()
    assert server._server is not None
    await server._server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
