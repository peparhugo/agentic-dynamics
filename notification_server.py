"""Async WebSocket notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from urllib.parse import unquote

from websockets.asyncio.server import Server, ServerConnection, serve


MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> dict[str, Any]:
    """Build a message with the wire format used by the server."""
    result = {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if channel is not None:
        result["channel"] = channel
    return result


class NotificationServer:
    """Manage WebSocket clients and serve their current count over HTTP."""

    def __init__(self, websocket_host: str = "127.0.0.1", websocket_port: int = 8765,
                 http_host: str | None = None, http_port: int = 8080) -> None:
        self.websocket_host = websocket_host
        self.websocket_port = websocket_port
        self.http_host = http_host or websocket_host
        self.http_port = http_port
        self.clients: dict[str, ServerConnection] = {}
        self.channels: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self._clients_lock = threading.RLock()
        self._websocket_server: Server | None = None
        self._http_server: asyncio.AbstractServer | None = None

    @property
    def connected_clients(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    async def start(self) -> "NotificationServer":
        self._websocket_server = await serve(
            self._handle_websocket, self.websocket_host, self.websocket_port
        )
        self._http_server = await asyncio.start_server(
            self._handle_http, self.http_host, self.http_port
        )
        self.websocket_port = self._websocket_server.sockets[0].getsockname()[1]
        self.http_port = self._http_server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None
        with self._clients_lock:
            self.clients.clear()
            self.channels.clear()
            self._client_channels.clear()

    async def broadcast(self, payload: dict[str, Any], message_type: str = "broadcast",
                        channel: str | None = None) -> None:
        if message_type not in MESSAGE_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        wire_message = json.dumps(message(message_type, payload, channel))
        with self._clients_lock:
            if channel is None:
                connections = list(self.clients.values())
            else:
                subscriber_ids = self.channels.get(channel, set())
                connections = [self.clients[client_id] for client_id in subscriber_ids
                               if client_id in self.clients]
        if connections:
            await asyncio.gather(*(client.send(wire_message) for client in connections),
                                 return_exceptions=True)

    def _set_subscription(self, client_id: str, channel: str, subscribed: bool) -> None:
        with self._clients_lock:
            client_channels = self._client_channels.setdefault(client_id, set())
            if subscribed:
                client_channels.add(channel)
                self.channels.setdefault(channel, set()).add(client_id)
            else:
                client_channels.discard(channel)
                subscribers = self.channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        self.channels.pop(channel, None)

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        with self._clients_lock:
            client = self.clients.get(client_id)
        if client is None:
            return False
        try:
            await client.send(json.dumps(message("direct", payload)))
        except Exception:
            return False
        return True

    async def _handle_websocket(self, websocket: ServerConnection) -> None:
        client_id = str(uuid4())
        with self._clients_lock:
            self.clients[client_id] = websocket
            self._client_channels[client_id] = set()
        try:
            await websocket.send(json.dumps(message("system", {"client_id": client_id})))
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        except Exception:
            pass
        finally:
            with self._clients_lock:
                self.clients.pop(client_id, None)
                subscribed_channels = self._client_channels.pop(client_id, set())
                for channel in subscribed_channels:
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(client_id)
                        if not subscribers:
                            self.channels.pop(channel, None)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            incoming = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(incoming, dict):
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type in {"subscribe", "unsubscribe"} and payload is None:
            payload = {}
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            return
        channel = incoming.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if channel is not None and not isinstance(channel, str):
            return
        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str) or not channel:
                return
            self._set_subscription(sender_id, channel, message_type == "subscribe")
            return
        if message_type == "direct":
            target_id = payload.get("client_id")
            if isinstance(target_id, str):
                direct_payload = {key: value for key, value in payload.items() if key != "client_id"}
                await self.send_direct(target_id, direct_payload)
            return
        await self.broadcast(payload, message_type, channel)

    def _channel_listing(self) -> list[dict[str, Any]]:
        with self._clients_lock:
            return [{"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self.channels.items())]

    def _channel_subscribers(self, channel: str) -> list[str] | None:
        with self._clients_lock:
            if channel not in self.channels:
                return None
            return sorted(self.channels[channel])

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("ascii", "ignore").strip()
            method, path, *_ = request_line.split()
            if method == "GET" and path == "/health":
                body = json.dumps({"connected_clients": self.connected_clients}).encode()
                status = "200 OK"
            elif method == "GET" and path == "/channels":
                body = json.dumps({"channels": self._channel_listing()}).encode()
                status = "200 OK"
            elif method == "GET" and path.startswith("/channels/") and path.endswith("/subscribers"):
                channel = unquote(path[len("/channels/"):-len("/subscribers")])
                subscribers = self._channel_subscribers(channel)
                if subscribers is None:
                    body = json.dumps({"error": "channel not found"}).encode()
                    status = "404 Not Found"
                else:
                    body = json.dumps({"channel": channel, "subscribers": subscribers}).encode()
                    status = "200 OK"
            else:
                body = json.dumps({"error": "not found"}).encode()
                status = "404 Not Found"
            headers = (f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                       f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode()
            writer.write(headers + body)
            await writer.drain()
        except (ValueError, UnicodeError):
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def serve_forever(self) -> None:
        if self._websocket_server is None or self._http_server is None:
            await self.start()
        await asyncio.Future()

    def run(self) -> None:
        asyncio.run(self.serve_forever())


def create_server() -> NotificationServer:
    return NotificationServer()
