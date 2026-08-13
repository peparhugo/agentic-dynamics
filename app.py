"""Async WebSocket notification server with an HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": message_type, "payload": payload, "timestamp": timestamp()}


@dataclass(slots=True)
class Client:
    websocket: ServerConnection
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ClientRegistry:
    """Thread-safe client and channel subscription state."""

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, websocket: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = Client(websocket)
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            empty_channels = []
            for channel, subscribers in self._channels.items():
                subscribers.discard(client_id)
                if not subscribers:
                    empty_channels.append(channel)
            for channel in empty_channels:
                del self._channels[channel]

    def get(self, client_id: str) -> Client | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, Client]]:
        with self._lock:
            return list(self._clients.items())

    def subscribe(self, client_id: str, channel: str) -> bool:
        with self._lock:
            if client_id not in self._clients:
                return False
            self._channels.setdefault(channel, set()).add(client_id)
            return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return False
            was_subscribed = client_id in subscribers
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]
            return was_subscribed

    def channel_snapshot(self, channel: str) -> list[tuple[str, Client]]:
        with self._lock:
            return [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(self._channels.items())
            ]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    def __init__(self, registry: ClientRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()

    async def _send(self, client: Client, data: dict[str, Any]) -> bool:
        try:
            async with client.send_lock:
                await client.websocket.send(json.dumps(data))
            return True
        except ConnectionClosed:
            return False

    async def send_to(self, client_id: str, data: dict[str, Any]) -> bool:
        client = self.registry.get(client_id)
        if client is None:
            return False
        if await self._send(client, data):
            return True
        self.registry.remove(client_id)
        return False

    async def broadcast(self, data: dict[str, Any]) -> None:
        channel = data.get("channel")
        clients = (
            self.registry.channel_snapshot(channel)
            if isinstance(channel, str)
            else self.registry.snapshot()
        )
        results = await asyncio.gather(
            *(self._send(client, data) for _, client in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results, strict=True):
            if result is not True:
                self.registry.remove(client_id)

    async def _error(self, client_id: str, detail: str) -> None:
        await self.send_to(client_id, message("system", {"error": detail}))

    async def handle_message(self, client_id: str, raw_message: str | bytes) -> None:
        try:
            data = json.loads(raw_message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self._error(client_id, "message must be valid JSON")
            return

        if not isinstance(data, dict):
            await self._error(client_id, "message must be a JSON object")
            return

        message_type = data.get("type")
        payload = data.get("payload")
        incoming_timestamp = data.get("timestamp")
        channel = data.get("channel")
        if message_type not in SUPPORTED_TYPES:
            await self._error(client_id, "unsupported message type")
            return
        if "channel" in data and (not isinstance(channel, str) or not channel):
            await self._error(client_id, "channel must be a non-empty string")
            return
        if message_type in {"subscribe", "unsubscribe"}:
            if channel is None:
                await self._error(client_id, f"{message_type} messages require a channel")
                return
            if message_type == "subscribe":
                self.registry.subscribe(client_id, channel)
            else:
                self.registry.unsubscribe(client_id, channel)
            return

        if not isinstance(payload, dict):
            await self._error(client_id, "payload must be an object")
            return
        if not isinstance(incoming_timestamp, str):
            await self._error(client_id, "timestamp must be a string")
            return

        outgoing = {
            "type": message_type,
            "payload": payload,
            "timestamp": incoming_timestamp,
        }
        if channel is not None:
            outgoing["channel"] = channel
        if message_type in {"broadcast", "system"}:
            await self.broadcast(outgoing)
            return

        target_id = payload.get("target_id")
        if not isinstance(target_id, str) or not target_id:
            await self._error(client_id, "direct messages require payload.target_id")
            return
        if channel is not None and target_id not in {
            subscriber_id for subscriber_id, _ in self.registry.channel_snapshot(channel)
        }:
            await self._error(client_id, "target client is not subscribed to channel")
            return
        if not await self.send_to(target_id, outgoing):
            await self._error(client_id, "target client is not connected")

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        client_id = self.registry.add(websocket)
        try:
            await self.send_to(
                client_id,
                message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw_message in websocket:
                await self.handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)

    async def process_request(
        self, _connection: ServerConnection, request: Request
    ) -> Response | None:
        path = request.path.partition("?")[0]
        if path == "/health":
            return self._json_response(
                HTTPStatus.OK, {"connected_clients": self.registry.count}
            )
        if path == "/channels":
            return self._json_response(
                HTTPStatus.OK, {"channels": self.registry.channels()}
            )
        prefix, suffix = "/channels/", "/subscribers"
        if path.startswith(prefix) and path.endswith(suffix):
            channel = unquote(path[len(prefix) : -len(suffix)])
            if channel and "/" not in channel:
                return self._json_response(
                    HTTPStatus.OK,
                    {
                        "channel": channel,
                        "subscribers": self.registry.subscribers(channel),
                    },
                )
        if path not in {"/", "/ws"}:
            return self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})
        return None

    @staticmethod
    def _json_response(status: HTTPStatus, data: dict[str, Any]) -> Response:
        body = json.dumps(data, separators=(",", ":")).encode()
        return Response(
            status,
            status.phrase,
            Headers(
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ]
            ),
            body,
        )


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    notification_server = NotificationServer()
    async with serve(
        notification_server.websocket_handler,
        host,
        port,
        process_request=notification_server.process_request,
    ):
        await asyncio.get_running_loop().create_future()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8765")))
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
