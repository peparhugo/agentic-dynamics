"""
WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, broadcasts
messages to all connected clients, handles clean disconnects, and exposes a
REST endpoint ``GET /health`` returning the connected client count.

Clients can subscribe to named channels (e.g. ``"alerts"``, ``"system"``,
``"chat"``). Messages that carry a ``channel`` field are delivered only to the
clients subscribed to that channel; messages without a channel still broadcast
to all connected clients.

Message format (JSON)::

    {"type": str, "payload": dict, "timestamp": str}

Supported types: ``"broadcast"``, ``"direct"``, ``"system"``, ``"subscribe"``,
``"unsubscribe"``.

REST endpoints::

    GET /health                          connected client count
    GET /channels                        active channels and subscriber counts
    GET /channels/{name}/subscribers     subscriber IDs for a channel
"""

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime, timezone

import websockets
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

MESSAGE_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")

HEALTH_PATH = "/health"
CHANNELS_PATH = "/channels"
WEBSOCKET_PATHS = ("/", "/ws")


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict, timestamp: str | None = None) -> dict:
    """Build a message dict conforming to the canonical message format."""
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": timestamp or now_iso(),
    }


class ClientRegistry:
    """
    Thread-safe registry mapping client IDs to their WebSocket connections.

    All operations are protected by a reentrant lock so the registry can be
    mutated from the asyncio event loop or from plain threads (e.g. the
    synchronous HTTP health check) without corruption.
    """

    def __init__(self) -> None:
        self._clients: dict[str, object] = {}
        self._lock = threading.RLock()

    def add(self, client_id: str, websocket: object) -> None:
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)

    def all(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class ChannelRegistry:
    """
    Thread-safe registry mapping channel names to the set of subscribed client
    IDs. A client may subscribe to any number of channels.
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def subscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            members = self._channels.get(channel)
            if members is None:
                return
            members.discard(client_id)
            if not members:
                self._channels.pop(channel, None)

    def remove_client(self, client_id: str) -> None:
        with self._lock:
            empty = []
            for channel, members in self._channels.items():
                members.discard(client_id)
                if not members:
                    empty.append(channel)
            for channel in empty:
                self._channels.pop(channel, None)

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {name: len(members) for name, members in self._channels.items()}


class NotificationServer:
    """WebSocket notification server built on the ``websockets`` library."""

    def __init__(
        self,
        registry: ClientRegistry | None = None,
        channels: ChannelRegistry | None = None,
    ) -> None:
        self.registry = registry or ClientRegistry()
        self.channels = channels or ChannelRegistry()

    async def handler(self, websocket) -> None:
        """Handle a single WebSocket connection lifecycle."""
        client_id = self._new_client_id()
        self.registry.add(client_id, websocket)
        welcome = make_message(
            "system",
            {"client_id": client_id, "message": "connected"},
        )
        try:
            await websocket.send(json.dumps(welcome))
            async for raw in websocket:
                await self._handle_message(client_id, websocket, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            self.channels.remove_client(client_id)

    def _new_client_id(self) -> str:
        while True:
            candidate = str(uuid.uuid4())
            if self.registry.get(candidate) is None:
                return candidate

    async def _handle_message(self, sender_id: str, websocket, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(websocket, "message must be valid JSON")
            return

        if not isinstance(message, dict):
            await self._send_error(websocket, "message must be a JSON object")
            return

        msg_type = message.get("type")
        payload = message.get("payload")
        timestamp = message.get("timestamp") or now_iso()

        if msg_type not in MESSAGE_TYPES:
            await self._send_error(websocket, f"unsupported message type: {msg_type!r}")
            return
        if not isinstance(payload, dict):
            await self._send_error(websocket, "payload must be an object")
            return

        if msg_type == "subscribe":
            await self._handle_subscribe(sender_id, websocket, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(sender_id, websocket, payload)
        elif msg_type == "broadcast":
            channel = message.get("channel") or payload.get("channel")
            await self.broadcast(msg_type, payload, timestamp, channel)
        elif msg_type == "direct":
            await self._handle_direct(sender_id, websocket, payload, timestamp)
        elif msg_type == "system":
            await websocket.send(
                json.dumps(
                    make_message(
                        "system",
                        {"message": "ack", "echo": payload},
                        timestamp,
                    )
                )
            )

    async def _handle_subscribe(self, sender_id: str, websocket, payload: dict) -> None:
        channel = payload.get("channel")
        if not channel or not isinstance(channel, str):
            await self._send_error(websocket, "subscribe requires payload.channel")
            return
        self.channels.subscribe(channel, sender_id)
        await websocket.send(
            json.dumps(
                make_message(
                    "system",
                    {"message": "subscribed", "channel": channel},
                )
            )
        )

    async def _handle_unsubscribe(self, sender_id: str, websocket, payload: dict) -> None:
        channel = payload.get("channel")
        if not channel or not isinstance(channel, str):
            await self._send_error(websocket, "unsubscribe requires payload.channel")
            return
        self.channels.unsubscribe(channel, sender_id)
        await websocket.send(
            json.dumps(
                make_message(
                    "system",
                    {"message": "unsubscribed", "channel": channel},
                )
            )
        )

    async def _handle_direct(
        self,
        sender_id: str,
        sender_ws,
        payload: dict,
        timestamp: str,
    ) -> None:
        target = payload.get("to")
        if not target:
            await self._send_error(sender_ws, "direct message requires payload.to")
            return
        target_ws = self.registry.get(target)
        if target_ws is None:
            await self._send_error(sender_ws, f"unknown target client: {target}")
            return
        await target_ws.send(json.dumps(make_message("direct", payload, timestamp)))

    async def _send_error(self, websocket, message: str) -> None:
        await websocket.send(
            json.dumps(
                make_message("system", {"message": "error", "error": message})
            )
        )

    async def _deliver(self, msg: str, client_ids: list[str]) -> None:
        dead: list[str] = []
        for client_id in client_ids:
            ws = self.registry.get(client_id)
            if ws is None:
                continue
            try:
                await ws.send(msg)
            except ConnectionClosed:
                dead.append(client_id)
        for client_id in dead:
            self.registry.remove(client_id)
            self.channels.remove_client(client_id)

    async def broadcast(
        self,
        msg_type: str = "broadcast",
        payload: dict | None = None,
        timestamp: str | None = None,
        channel: str | None = None,
    ) -> None:
        """Send a message to every connected client (or channel subscribers)."""
        msg = json.dumps(make_message(msg_type, payload or {}, timestamp))
        if channel:
            await self._deliver(msg, self.channels.subscribers(channel))
            return
        dead: list[str] = []
        for client_id, ws in self.registry.all():
            try:
                await ws.send(msg)
            except ConnectionClosed:
                dead.append(client_id)
        for client_id in dead:
            self.registry.remove(client_id)
            self.channels.remove_client(client_id)

    async def direct(self, target_id: str, payload: dict, timestamp: str | None = None) -> bool:
        """Send a message to a single client. Returns True if delivered."""
        target_ws = self.registry.get(target_id)
        if target_ws is None:
            return False
        await target_ws.send(
            json.dumps(make_message("direct", payload, timestamp))
        )
        return True

    async def process_request(
        self,
        connection,
        request: Request,
    ) -> Response | None:
        """Serve REST endpoints over HTTP; upgrade everything else to WS."""
        if request.path == HEALTH_PATH:
            return self._json_response(
                200,
                {"status": "ok", "connected_clients": self.registry.count()},
            )
        if request.path == CHANNELS_PATH:
            channels = [
                {"name": name, "subscribers": count}
                for name, count in sorted(self.channels.channels().items())
            ]
            return self._json_response(200, {"channels": channels})
        if request.path.startswith(CHANNELS_PATH + "/"):
            return self._handle_channel_detail(request.path)
        if request.path in WEBSOCKET_PATHS:
            return None
        return self._json_response(404, {"error": "not found"})

    def _handle_channel_detail(self, path: str) -> Response:
        parts = path[len(CHANNELS_PATH) + 1:].split("/")
        if len(parts) != 2 or parts[1] != "subscribers":
            return self._json_response(404, {"error": "not found"})
        name = parts[0]
        return self._json_response(
            200,
            {"channel": name, "subscribers": self.channels.subscribers(name)},
        )

    def _json_response(self, status_code: int, body: dict, status_message: str | None = None) -> Response:
        data = json.dumps(body).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(data)),
            }
        )
        if status_message is None:
            status_message = "OK" if status_code == 200 else "Error"
        return Response(status_code, status_message, headers, data)

    async def run(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """Serve until cancelled."""
        async with websockets.serve(
            self.handler,
            host,
            port,
            process_request=self.process_request,
        ):
            await asyncio.Future()


async def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = NotificationServer()
    await server.run(host, port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
