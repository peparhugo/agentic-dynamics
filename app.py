"""Async WebSocket notification server with an HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote, urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "subscribe", "unsubscribe", "system"}


def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(
    message_type: str,
    payload: dict[str, Any],
    channel: str | None = None,
) -> dict[str, Any]:
    outgoing = {
        "type": message_type,
        "payload": payload,
        "timestamp": utc_timestamp(),
    }
    if channel is not None:
        outgoing["channel"] = channel
    return outgoing


@dataclass(frozen=True)
class Client:
    id: str
    connection: ServerConnection


class ClientRegistry:
    """A thread-safe registry of connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, connection: ServerConnection) -> Client:
        client = Client(str(uuid.uuid4()), connection)
        with self._lock:
            self._clients[client.id] = client
        return client

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in tuple(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> Client | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> tuple[Client, ...]:
        with self._lock:
            return tuple(self._clients.values())

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

    def channel_snapshot(self, channel: str) -> tuple[Client, ...]:
        with self._lock:
            return tuple(
                self._clients[client_id]
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            )

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {
                name: len(subscribers)
                for name, subscribers in sorted(self._channels.items())
            }

    def subscriber_ids(self, channel: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._channels.get(channel, set())))

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    def __init__(self) -> None:
        self.clients = ClientRegistry()

    async def handle_connection(self, connection: ServerConnection) -> None:
        client = self.clients.add(connection)
        await self._send(
            client,
            message("system", {"event": "connected", "client_id": client.id}),
        )

        try:
            async for raw_message in connection:
                await self._handle_message(client, raw_message)
        except ConnectionClosed:
            pass
        finally:
            self.clients.remove(client.id)

    async def _handle_message(self, sender: Client, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._error(sender, "messages must be UTF-8 JSON text")
            return

        try:
            incoming = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            await self._error(sender, "invalid JSON")
            return

        error = self._validation_error(incoming)
        if error:
            await self._error(sender, error)
            return

        message_type = incoming["type"]
        payload = incoming["payload"]
        channel = incoming.get("channel")
        if message_type == "broadcast":
            await self.broadcast(message("broadcast", payload, channel), channel)
        elif message_type == "direct":
            await self._direct(sender, payload, channel)
        elif message_type == "subscribe":
            self.clients.subscribe(sender.id, channel)
        elif message_type == "unsubscribe":
            self.clients.unsubscribe(sender.id, channel)
        else:
            await self._error(sender, "clients cannot send system messages")

    @staticmethod
    def _validation_error(incoming: Any) -> str | None:
        if not isinstance(incoming, dict):
            return "message must be a JSON object"
        if not isinstance(incoming.get("type"), str):
            return "type must be a string"
        if incoming["type"] not in SUPPORTED_TYPES:
            return "unsupported message type"
        if not isinstance(incoming.get("payload"), dict):
            return "payload must be an object"
        if "timestamp" not in incoming or not isinstance(incoming["timestamp"], str):
            return "timestamp must be a string"
        if "channel" in incoming and (
            not isinstance(incoming["channel"], str) or not incoming["channel"]
        ):
            return "channel must be a non-empty string"
        if incoming["type"] in {"subscribe", "unsubscribe"} and "channel" not in incoming:
            return f'{incoming["type"]} requires channel'
        return None

    async def _direct(
        self,
        sender: Client,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        target_id = payload.get("client_id")
        if not isinstance(target_id, str) or not target_id:
            await self._error(sender, "direct payload requires client_id")
            return

        target = self.clients.get(target_id)
        if target is None:
            await self._error(sender, "target client is not connected")
            return
        if channel is not None and target not in self.clients.channel_snapshot(channel):
            await self._error(sender, "target client is not subscribed to channel")
            return

        direct_payload = {key: value for key, value in payload.items() if key != "client_id"}
        direct_payload["sender_id"] = sender.id
        if not await self._send(target, message("direct", direct_payload, channel)):
            await self._error(sender, "target client is not connected")

    async def broadcast(
        self,
        outgoing: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        clients = (
            self.clients.snapshot()
            if channel is None
            else self.clients.channel_snapshot(channel)
        )
        if clients:
            await asyncio.gather(*(self._send(client, outgoing) for client in clients))

    async def _error(self, client: Client, detail: str) -> None:
        await self._send(client, message("system", {"event": "error", "detail": detail}))

    async def _send(self, client: Client, outgoing: dict[str, Any]) -> bool:
        try:
            await client.connection.send(json.dumps(outgoing))
            return True
        except ConnectionClosed:
            self.clients.remove(client.id)
            return False

    def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        path = urlsplit(request.path).path
        if path == "/health":
            return self._json_response(
                connection, {"connected_clients": len(self.clients)}
            )
        if path == "/channels":
            channels = [
                {"name": name, "subscriber_count": count}
                for name, count in self.clients.channels().items()
            ]
            return self._json_response(connection, {"channels": channels})
        prefix, separator, encoded_name = path.partition("/channels/")
        if not prefix and separator and encoded_name.endswith("/subscribers"):
            encoded_name = encoded_name[: -len("/subscribers")]
            if encoded_name:
                name = unquote(encoded_name)
                return self._json_response(
                    connection,
                    {
                        "channel": name,
                        "subscribers": list(self.clients.subscriber_ids(name)),
                    },
                )
        if request.headers.get("Upgrade", "").lower() != "websocket":
            return connection.respond(HTTPStatus.NOT_FOUND, "Not Found\n")
        return None

    @staticmethod
    def _json_response(
        connection: ServerConnection, body: dict[str, Any]
    ) -> Response:
        response = connection.respond(HTTPStatus.OK, json.dumps(body) + "\n")
        del response.headers["Content-Type"]
        response.headers["Content-Type"] = "application/json"
        return response

    def start(self, host: str = "127.0.0.1", port: int = 8765) -> Server:
        """Create a server context manager for use with ``async with``."""
        return serve(
            self.handle_connection,
            host,
            port,
            process_request=self.process_request,
        )


async def run(host: str, port: int) -> None:
    notification_server = NotificationServer()
    async with notification_server.start(host, port):
        print(f"Notification server listening on {host}:{port}")
        await asyncio.get_running_loop().create_future()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
