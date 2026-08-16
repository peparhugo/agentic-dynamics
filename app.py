"""Async WebSocket notification server with an HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import threading
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

SUPPORTED_TYPES = frozenset(
    {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
)


def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a message in the public wire format."""
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": utc_timestamp(),
    }


class ClientRegistry:
    """Thread-safe mapping of client IDs to WebSocket connections.

    Network operations use snapshots, so the lock is never held across an
    await and callers from other threads can still inspect or update state.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            return list(self._clients.items())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_snapshot(self, channel: str) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            return [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in sorted(self._channels.items())
            }

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def is_subscribed(self, client_id: str, channel: str) -> bool:
        with self._lock:
            return client_id in self._channels.get(channel, set())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    """Manage WebSocket clients and route notification messages."""

    def __init__(self, registry: ClientRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Serve REST endpoints before the WebSocket upgrade."""
        path = request.path.partition("?")[0]
        if path == "/health":
            body = json.dumps({"connected_clients": len(self.registry)})
        elif path == "/channels":
            body = json.dumps({"channels": self.registry.channels()})
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")]
            if not encoded_name or "/" in encoded_name:
                return None
            channel = unquote(encoded_name)
            body = json.dumps(
                {"channel": channel, "subscribers": self.registry.subscribers(channel)}
            )
        else:
            return None

        response = connection.respond(HTTPStatus.OK, body)
        del response.headers["Content-Type"]
        response.headers["Content-Type"] = "application/json"
        return response

    async def handler(self, connection: ServerConnection) -> None:
        client_id = self.registry.add(connection)
        try:
            await self._send(
                connection,
                make_message(
                    "system",
                    {"event": "connected", "client_id": client_id},
                ),
            )
            async for raw_message in connection:
                await self.handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        sender = self.registry.get(sender_id)
        if sender is None:
            return

        try:
            message = self._parse_message(raw_message)
        except ValueError as exc:
            await self._send_error(sender, str(exc))
            return

        message_type = message["type"]
        if message_type == "subscribe":
            self.registry.subscribe(sender_id, message["channel"])
        elif message_type == "unsubscribe":
            self.registry.unsubscribe(sender_id, message["channel"])
        elif message_type == "direct":
            await self._send_direct(sender, message)
        else:
            await self.broadcast(message, message.get("channel"))

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> dict[str, Any]:
        if isinstance(raw_message, bytes):
            try:
                raw_message = raw_message.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("message must be UTF-8 JSON") from exc

        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("message must be valid JSON") from exc

        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        required_fields = {"type", "payload", "timestamp"}
        if not required_fields.issubset(message) or not set(message).issubset(
            required_fields | {"channel"}
        ):
            raise ValueError(
                "message must contain type, payload, and timestamp, with optional channel"
            )
        if not isinstance(message["type"], str) or message["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message["payload"], dict):
            raise ValueError("payload must be a JSON object")
        if not isinstance(message["timestamp"], str):
            raise ValueError("timestamp must be a string")
        channel = message.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError("channel must be a non-empty string")
        if message["type"] in {"subscribe", "unsubscribe"} and channel is None:
            raise ValueError(f'{message["type"]} requires channel')
        return message

    async def _send_direct(
        self, sender: ServerConnection, message: dict[str, Any]
    ) -> None:
        payload = message["payload"]
        target_id = payload.get("client_id") or payload.get("target_id")
        if not isinstance(target_id, str) or not target_id:
            await self._send_error(sender, "direct payload requires client_id")
            return

        target = self.registry.get(target_id)
        if target is None:
            await self._send_error(sender, "target client is not connected")
            return
        channel = message.get("channel")
        if channel is not None and not self.registry.is_subscribed(target_id, channel):
            await self._send_error(sender, "target client is not subscribed to channel")
            return
        try:
            await self._send(target, message)
        except ConnectionClosed:
            self.registry.remove(target_id)
            await self._send_error(sender, "target client is not connected")

    async def broadcast(
        self, message: dict[str, Any], channel: str | None = None
    ) -> None:
        """Send a message to all clients, or only a channel's subscribers."""
        clients = (
            self.registry.snapshot()
            if channel is None
            else self.registry.channel_snapshot(channel)
        )
        results = await asyncio.gather(
            *(self._send(connection, message) for _, connection in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results, strict=True):
            if isinstance(result, ConnectionClosed):
                self.registry.remove(client_id)

    @staticmethod
    async def _send(connection: ServerConnection, message: dict[str, Any]) -> None:
        await connection.send(json.dumps(message, separators=(",", ":")))

    async def _send_error(self, connection: ServerConnection, detail: str) -> None:
        try:
            await self._send(
                connection,
                make_message("system", {"event": "error", "detail": detail}),
            )
        except ConnectionClosed:
            pass


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run until SIGINT or SIGTERM is received."""
    notifications = NotificationServer()
    stop = asyncio.get_running_loop().create_future()

    def request_stop() -> None:
        if not stop.done():
            stop.set_result(None)

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(signum, request_stop)
        except NotImplementedError:
            pass

    async with serve(
        notifications.handler,
        host,
        port,
        process_request=notifications.process_request,
    ):
        await stop


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    asyncio.run(run(args.host, args.port))


if __name__ == "__main__":
    main()
