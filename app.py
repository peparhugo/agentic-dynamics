"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})


def make_message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> dict[str, Any]:
    """Create a message in the server's wire format."""
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    if not isinstance(payload, dict):
        raise TypeError("payload must be an object")
    message = {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if channel is not None:
        message["channel"] = channel
    return message


class ClientRegistry:
    """Concurrency-safe mapping of client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def add(self, websocket: ServerConnection) -> str:
        client_id = str(uuid4())
        async with self._lock:
            self._clients[client_id] = websocket
        return client_id

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def snapshot(self) -> list[tuple[str, ServerConnection]]:
        async with self._lock:
            return list(self._clients.items())

    async def get(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            if client_id not in self._clients:
                raise ValueError("client is not connected")
            self._channels.setdefault(channel, set()).add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    async def channel_snapshot(self, channel: str) -> list[tuple[str, ServerConnection]]:
        async with self._lock:
            return [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]

    async def channels(self) -> dict[str, int]:
        async with self._lock:
            return {name: len(subscribers) for name, subscribers in sorted(self._channels.items())}

    async def subscribers(self, channel: str) -> list[str]:
        async with self._lock:
            return sorted(self._channels.get(channel, set()))

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        async with self._lock:
            return client_id in self._channels.get(channel, set())


class NotificationServer:
    """Manage WebSocket clients and route notification messages."""

    def __init__(self) -> None:
        self.clients = ClientRegistry()

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        client_id = await self.clients.add(websocket)
        await websocket.send(
            json.dumps(make_message("system", {"event": "connected", "client_id": client_id}))
        )

        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, websocket, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await self.clients.remove(client_id)

    async def _handle_message(
        self, client_id: str, websocket: ServerConnection, raw_message: str | bytes
    ) -> None:
        try:
            message = json.loads(raw_message)
            self._validate_message(message)
            message_type = message["type"]
            channel = message.get("channel")

            if message_type == "broadcast":
                await self.broadcast(
                    make_message("broadcast", message["payload"], channel), channel
                )
            elif message_type == "direct":
                await self._send_direct(message["payload"], channel)
            elif message_type == "subscribe":
                await self.clients.subscribe(client_id, channel)
            elif message_type == "unsubscribe":
                await self.clients.unsubscribe(client_id, channel)
            else:
                raise ValueError("clients cannot send system messages")
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            await websocket.send(
                json.dumps(make_message("system", {"event": "error", "message": str(error)}))
            )

    @staticmethod
    def _validate_message(message: Any) -> None:
        if not isinstance(message, dict):
            raise TypeError("message must be an object")
        required_fields = {"type", "payload", "timestamp"}
        extra_fields = set(message) - required_fields
        if not required_fields.issubset(message) or not extra_fields <= {"channel"}:
            raise ValueError("message must contain type, payload, and timestamp, with optional channel")
        if message["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message["payload"], dict):
            raise TypeError("payload must be an object")
        if not isinstance(message["timestamp"], str):
            raise TypeError("timestamp must be a string")
        channel = message.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel.strip()):
            raise ValueError("channel must be a non-empty string")
        if message["type"] in {"subscribe", "unsubscribe"} and channel is None:
            raise ValueError(f'{message["type"]} messages require a channel')

    async def broadcast(self, message: dict[str, Any], channel: str | None = None) -> None:
        """Send a message to every client, or to one channel's subscribers."""
        if channel is None:
            channel = message.get("channel")
        encoded = json.dumps(message)
        clients = (
            await self.clients.snapshot()
            if channel is None
            else await self.clients.channel_snapshot(channel)
        )
        if not clients:
            return

        results = await asyncio.gather(
            *(websocket.send(encoded) for _, websocket in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, Exception):
                await self.clients.remove(client_id)

    async def _send_direct(self, payload: dict[str, Any], channel: str | None = None) -> None:
        recipient_id = payload.get("client_id")
        if not isinstance(recipient_id, str):
            raise ValueError("direct payload requires client_id")
        recipient = await self.clients.get(recipient_id)
        if recipient is None:
            raise ValueError("direct recipient is not connected")
        if channel is not None and not await self.clients.is_subscribed(recipient_id, channel):
            return
        await recipient.send(json.dumps(make_message("direct", payload, channel)))

    async def health_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        status = "404 Not Found"
        body: dict[str, Any] = {"error": "not found"}
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            parts = request_line.decode("ascii", errors="replace").strip().split()
            if len(parts) == 3 and parts[0] == "GET":
                path = urlsplit(parts[1]).path
                if path == "/health":
                    status = "200 OK"
                    body = {"connected_clients": await self.clients.count()}
                elif path == "/channels":
                    status = "200 OK"
                    body = {"channels": await self.clients.channels()}
                elif path.startswith("/channels/") and path.endswith("/subscribers"):
                    encoded_name = path[len("/channels/") : -len("/subscribers")].strip("/")
                    if encoded_name:
                        channel = unquote(encoded_name)
                        status = "200 OK"
                        body = {
                            "channel": channel,
                            "subscribers": await self.clients.subscribers(channel),
                        }

            encoded = json.dumps(body).encode()
            writer.write(
                f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(encoded)}\r\nConnection: close\r\n\r\n".encode()
                + encoded
            )
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            LOGGER.debug("Health client disconnected before receiving a response")
        finally:
            writer.close()
            await writer.wait_closed()


async def run_server(host: str, websocket_port: int, health_port: int) -> None:
    notification_server = NotificationServer()
    websocket_server: Server
    async with serve(notification_server.websocket_handler, host, websocket_port) as websocket_server:
        health_server = await asyncio.start_server(
            notification_server.health_handler, host, health_port
        )
        LOGGER.info(
            "WebSocket server listening on %s:%d; health endpoint on %s:%d",
            host,
            websocket_port,
            host,
            health_port,
        )
        async with health_server:
            await websocket_server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--health-port", type=int, default=8080)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server(args.host, args.port, args.health_port))


if __name__ == "__main__":
    main()
