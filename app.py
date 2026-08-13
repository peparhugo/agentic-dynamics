"""Async WebSocket notification server."""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote

import websockets
from websockets.exceptions import ConnectionClosed

SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


class ClientRegistry:
    """Thread-safe mapping of client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, Any]]:
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

    def channel_snapshot(self, channel: str) -> list[tuple[str, Any]]:
        with self._lock:
            subscriber_ids = self._channels.get(channel, set())
            return [
                (client_id, self._clients[client_id])
                for client_id in subscriber_ids
                if client_id in self._clients
            ]

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in sorted(self._channels.items())
                if subscribers
            }

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    def __init__(self) -> None:
        self.clients = ClientRegistry()

    @staticmethod
    def message(
        message_type: str,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> dict[str, Any]:
        message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return message

    async def send(
        self,
        websocket: Any,
        message_type: str,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        await websocket.send(json.dumps(self.message(message_type, payload, channel)))

    async def broadcast(
        self,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        clients = (
            self.clients.snapshot()
            if channel is None
            else self.clients.channel_snapshot(channel)
        )
        if not clients:
            return
        results = await asyncio.gather(
            *(
                self.send(websocket, "broadcast", payload, channel)
                for _, websocket in clients
            ),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, ConnectionClosed):
                self.clients.remove(client_id)

    async def direct(self, recipient_id: str, payload: dict[str, Any]) -> bool:
        recipient = self.clients.get(recipient_id)
        if recipient is None:
            return False
        try:
            await self.send(recipient, "direct", payload)
        except ConnectionClosed:
            self.clients.remove(recipient_id)
            return False
        return True

    async def handle_message(self, websocket: Any, client_id: str, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self.send(websocket, "system", {"error": "invalid JSON"})
            return

        if not isinstance(message, dict):
            await self.send(websocket, "system", {"error": "message must be an object"})
            return
        message_type = message.get("type")
        payload = message.get("payload")
        channel = message.get("channel")
        if message_type not in SUPPORTED_TYPES or (
            message_type not in {"subscribe", "unsubscribe"}
            and not isinstance(payload, dict)
        ):
            await self.send(
                websocket,
                "system",
                {"error": "message requires a supported type and object payload"},
            )
            return

        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str) or not channel:
                await self.send(
                    websocket,
                    "system",
                    {"error": f"{message_type} requires a non-empty channel"},
                )
            elif message_type == "subscribe":
                self.clients.subscribe(client_id, channel)
            else:
                self.clients.unsubscribe(client_id, channel)
            return

        if channel is not None and (not isinstance(channel, str) or not channel):
            await self.send(
                websocket,
                "system",
                {"error": "channel must be a non-empty string"},
            )
            return

        if message_type == "broadcast":
            await self.broadcast(payload, channel)
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            content = payload.get("message")
            if not isinstance(recipient_id, str) or not isinstance(content, dict):
                await self.send(
                    websocket,
                    "system",
                    {"error": "direct payload requires client_id and message object"},
                )
            elif not await self.direct(recipient_id, content):
                await self.send(websocket, "system", {"error": "client not found"})
        else:
            await self.send(
                websocket,
                "system",
                {"error": "system messages are generated by the server"},
            )

    async def handler(self, websocket: Any) -> None:
        client_id = self.clients.add(websocket)
        try:
            await self.send(websocket, "system", {"client_id": client_id})
            async for raw in websocket:
                await self.handle_message(websocket, client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            self.clients.remove(client_id)

    async def process_request(self, path: str, request_headers: Any) -> Any:
        if path == "/health":
            response = {"connected_clients": self.clients.count}
        elif path == "/channels":
            response = {"channels": self.clients.channels()}
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not encoded_name:
                return None
            channel = unquote(encoded_name)
            response = {
                "channel": channel,
                "subscribers": self.clients.subscribers(channel),
            }
        else:
            return None
        body = json.dumps(response).encode("utf-8")
        return (
            HTTPStatus.OK,
            [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
            body,
        )


async def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer()
    async with websockets.serve(
        server.handler,
        host,
        port,
        process_request=server.process_request,
    ):
        await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    asyncio.run(serve(args.host, args.port))


if __name__ == "__main__":
    main()
