"""Async WebSocket notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from websockets.asyncio.server import ServerConnection, serve


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": message_type, "payload": payload, "timestamp": _timestamp()}


class ClientRegistry:
    """A client registry safe to access from event-loop and worker threads."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}

    def add(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._subscriptions):
                subscribers = self._subscriptions[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._subscriptions[channel]

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._subscriptions[channel]

    def channel_snapshot(self) -> dict[str, list[str]]:
        with self._lock:
            return {
                channel: sorted(client_ids)
                for channel, client_ids in self._subscriptions.items()
                if client_ids
            }

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict[str, ServerConnection]:
        with self._lock:
            return dict(self._clients)

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    """Run the WebSocket and HTTP health services on the current event loop."""

    def __init__(self, host: str = "127.0.0.1", websocket_port: int = 8765,
                 health_port: int = 8080) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.health_port = health_port
        self.clients = ClientRegistry()
        self._websocket_server = None
        self._http_runner: web.AppRunner | None = None
        self._health_site: web.TCPSite | None = None

    async def start(self) -> "NotificationServer":
        self._websocket_server = await serve(
            self._handle_connection, self.host, self.websocket_port
        )
        websocket_socket = self._websocket_server.sockets[0]
        self.websocket_port = websocket_socket.getsockname()[1]

        app = web.Application()
        app.router.add_get("/health", self._health)
        app.router.add_get("/channels", self._channels)
        app.router.add_get("/channels/{name}/subscribers", self._channel_subscribers)
        self._http_runner = web.AppRunner(app)
        await self._http_runner.setup()
        self._health_site = web.TCPSite(
            self._http_runner, self.host, self.health_port
        )
        await self._health_site.start()
        if self._health_site._server and self._health_site._server.sockets:
            self.health_port = self._health_site._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        if self._http_runner is not None:
            await self._http_runner.cleanup()
            self._http_runner = None

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"connected_clients": len(self.clients)})

    async def _channels(self, request: web.Request) -> web.Response:
        channels = self.clients.channel_snapshot()
        return web.json_response({
            "channels": [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(channels.items())
            ]
        })

    async def _channel_subscribers(self, request: web.Request) -> web.Response:
        channel = request.match_info["name"]
        subscribers = self.clients.channel_snapshot().get(channel, [])
        return web.json_response({"subscribers": subscribers})

    async def _handle_connection(self, connection: ServerConnection) -> None:
        client_id = self.clients.add(connection)
        try:
            await connection.send(json.dumps(_message("system", {
                "event": "connected", "client_id": client_id
            })))
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            self.clients.remove(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            incoming = json.loads(raw_message)
            message_type = incoming.get("type")
            payload = incoming.get("payload")
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError("type must be supported and payload must be an object")
            channel = payload.get("channel")
            if message_type in {"subscribe", "unsubscribe"} and not self._valid_channel(channel):
                raise ValueError("subscription messages require payload.channel")
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            await self._send_to(sender_id, _message("system", {"error": str(exc)}))
            return

        if message_type == "subscribe":
            self.clients.subscribe(sender_id, channel)
            return
        if message_type == "unsubscribe":
            self.clients.unsubscribe(sender_id, channel)
            return

        outgoing = _message(message_type, payload)
        if self._valid_channel(payload.get("channel")):
            await self._broadcast_channel(payload["channel"], outgoing)
        elif message_type == "direct":
            recipient_id = payload.get("recipient_id", payload.get("client_id"))
            if not isinstance(recipient_id, str):
                await self._send_to(sender_id, _message("system", {
                    "error": "direct messages require payload.recipient_id"
                }))
                return
            await self._send_connection(self.clients.get(recipient_id), outgoing)
        else:
            await self._broadcast(outgoing)

    @staticmethod
    def _valid_channel(channel: Any) -> bool:
        return isinstance(channel, str) and bool(channel.strip())

    async def _broadcast_channel(self, channel: str, message: dict[str, Any]) -> None:
        subscribers = self.clients.channel_snapshot().get(channel, [])
        await asyncio.gather(*(
            self._send_connection(self.clients.get(client_id), message)
            for client_id in subscribers
        ))

    async def _broadcast(self, message: dict[str, Any]) -> None:
        await asyncio.gather(*(
            self._send_connection(connection, message)
            for connection in self.clients.snapshot().values()
        ))

    async def _send_to(self, client_id: str, message: dict[str, Any]) -> None:
        await self._send_connection(self.clients.get(client_id), message)

    async def _send_connection(self, connection: ServerConnection | None,
                                message: dict[str, Any]) -> None:
        if connection is not None:
            try:
                await connection.send(json.dumps(message))
            except Exception:
                # A connection can close between taking the registry snapshot and send.
                pass

    async def run_forever(self) -> None:
        await self.start()
        try:
            await asyncio.Future()
        finally:
            await self.stop()


async def main() -> None:
    server = NotificationServer()
    await server.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
