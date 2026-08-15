"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
from datetime import datetime, timezone
import json
import threading
from typing import Any
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response


MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})


class NotificationServer:
    """Maintains WebSocket clients and delivers structured notifications."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        # This also makes count and snapshot reads safe for monitoring threads.
        self._clients_lock = threading.RLock()
        self._server: Server | None = None

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @property
    def port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server is not running")
        return self._server.sockets[0].getsockname()[1]

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        if self._server is not None:
            raise RuntimeError("server is already running")
        self._server = await serve(self._handle_client, host, port, process_request=self._handle_http)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        with self._clients_lock:
            self._clients.clear()
            self._channels.clear()

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send a broadcast message to every currently connected client."""
        await self._send_to_connections(self._channel_connections(payload), "broadcast", payload)

    async def direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        """Send a direct message to one client, returning whether it existed."""
        with self._clients_lock:
            connection = self._clients.get(client_id)
        if connection is None:
            return False
        await self._send_to_connections([connection], "direct", payload)
        return True

    async def system(self, payload: dict[str, Any]) -> None:
        await self._send_to_connections(self._channel_connections(payload), "system", payload)

    async def _handle_client(self, connection: ServerConnection) -> None:
        client_id = str(uuid4())
        with self._clients_lock:
            self._clients[client_id] = connection

        try:
            await self._send_to_connections([connection], "system", {"event": "connected", "client_id": client_id})
            async for raw_message in connection:
                await self._handle_message(connection, client_id, raw_message)
        finally:
            with self._clients_lock:
                self._clients.pop(client_id, None)
                for channel in list(self._channels):
                    self._channels[channel].discard(client_id)
                    if not self._channels[channel]:
                        del self._channels[channel]

    async def _handle_message(
        self, connection: ServerConnection, sender_id: str, raw_message: str | bytes
    ) -> None:
        if isinstance(raw_message, bytes):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "messages must be JSON text"})
            return

        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
            if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError
            channel = self._message_channel(message, payload)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "invalid message format"})
            return

        if channel is not None and "channel" not in payload:
            payload = {**payload, "channel": channel}

        if message_type == "subscribe":
            if channel is None:
                await self._send_to_connections([connection], "system", {"event": "error", "message": "channel is required"})
                return
            self._subscribe(sender_id, channel)
            await self._send_to_connections([connection], "system", {"event": "subscribed", "channel": channel})
        elif message_type == "unsubscribe":
            if channel is None:
                await self._send_to_connections([connection], "system", {"event": "error", "message": "channel is required"})
                return
            self._unsubscribe(sender_id, channel)
            await self._send_to_connections([connection], "system", {"event": "unsubscribed", "channel": channel})
        elif message_type == "broadcast":
            await self.broadcast({"sender_id": sender_id, **payload})
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            if not isinstance(recipient_id, str) or not await self.direct(recipient_id, {"sender_id": sender_id, **payload}):
                await self._send_to_connections([connection], "system", {"event": "error", "message": "unknown client_id"})
        else:
            await self.system({"sender_id": sender_id, **payload})

    async def _handle_http(self, _connection: ServerConnection, request: Any) -> Response | None:
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.client_count}).encode("utf-8")
        elif request.path == "/channels":
            with self._clients_lock:
                channels = [
                    {"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self._channels.items())
                ]
            body = json.dumps({"channels": channels}).encode("utf-8")
        elif request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
            name = request.path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not name:
                return None
            with self._clients_lock:
                subscribers = sorted(self._channels.get(name, set()))
            body = json.dumps({"channel": name, "subscribers": subscribers}).encode("utf-8")
        else:
            return None
        return Response(200, "OK", Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}), body)

    def _connections(self) -> list[ServerConnection]:
        with self._clients_lock:
            return list(self._clients.values())

    def _channel_connections(self, payload: dict[str, Any]) -> list[ServerConnection]:
        channel = payload.get("channel")
        if channel is None:
            return self._connections()
        with self._clients_lock:
            return [self._clients[client_id] for client_id in self._channels.get(channel, set()) if client_id in self._clients]

    @staticmethod
    def _message_channel(message: dict[str, Any], payload: dict[str, Any]) -> str | None:
        top_level_channel = message.get("channel")
        payload_channel = payload.get("channel")
        if top_level_channel is not None and payload_channel is not None and top_level_channel != payload_channel:
            raise ValueError
        channel = top_level_channel if top_level_channel is not None else payload_channel
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError
        return channel

    def _subscribe(self, client_id: str, channel: str) -> None:
        with self._clients_lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def _unsubscribe(self, client_id: str, channel: str) -> None:
        with self._clients_lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    async def _send_to_connections(
        self, connections: list[ServerConnection], message_type: str, payload: dict[str, Any]
    ) -> None:
        message = json.dumps({"type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()})
        results = await asyncio.gather(*(connection.send(message) for connection in connections), return_exceptions=True)
        if any(isinstance(result, Exception) for result in results):
            # A failed send is harmless here; the connection handler removes it on close.
            return


async def main() -> None:
    server = NotificationServer()
    await server.start(host="0.0.0.0", port=8765)
    print("Notification server listening on ws://0.0.0.0:8765")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
