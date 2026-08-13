"""Async WebSocket notification server with flat-file persistence."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import unquote, urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.http11 import Response
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed

SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
SUBSCRIPTION_TYPES = {"subscribe", "unsubscribe"}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class FlatFileStore:
    """Persist message history and the current client state without a database."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.history_path = self.data_dir / "messages.jsonl"
        self.clients_path = self.data_dir / "clients.json"
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        await asyncio.to_thread(self.data_dir.mkdir, parents=True, exist_ok=True)
        async with self._lock:
            await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        self.history_path.touch(exist_ok=True)
        if not self.clients_path.exists():
            self._write_clients_sync([])

    async def append_message(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, separators=(",", ":")) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append_sync, line)

    def _append_sync(self, line: str) -> None:
        with self.history_path.open("a", encoding="utf-8") as file:
            file.write(line)
            file.flush()
            os.fsync(file.fileno())

    async def write_clients(self, client_ids: list[str]) -> None:
        async with self._lock:
            await asyncio.to_thread(self._write_clients_sync, client_ids)

    def _write_clients_sync(self, client_ids: list[str]) -> None:
        temporary = self.clients_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"clients": sorted(client_ids)}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.clients_path)


class NotificationServer:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.store = FlatFileStore(data_dir)
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._registry_lock = asyncio.Lock()

    async def initialize(self) -> None:
        await self.store.initialize()
        # Connections cannot survive a process restart, so persisted state starts empty.
        await self.store.write_clients([])

    async def connected_count(self) -> int:
        async with self._registry_lock:
            return len(self._clients)

    async def _register(self, websocket: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        async with self._registry_lock:
            self._clients[client_id] = websocket
            client_ids = list(self._clients)
            await self.store.write_clients(client_ids)
        return client_id

    async def _unregister(self, client_id: str) -> None:
        async with self._registry_lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]
            await self.store.write_clients(list(self._clients))

    async def _subscribe(self, client_id: str, channel: str) -> None:
        async with self._registry_lock:
            self._channels.setdefault(channel, set()).add(client_id)

    async def _unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._registry_lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    async def channel_counts(self) -> list[dict[str, Any]]:
        async with self._registry_lock:
            return [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(self._channels.items())
            ]

    async def channel_subscribers(self, channel: str) -> list[str]:
        async with self._registry_lock:
            return sorted(self._channels.get(channel, set()))

    async def _send(self, websocket: ServerConnection, message: dict[str, Any]) -> None:
        await websocket.send(json.dumps(message, separators=(",", ":")))

    async def _broadcast(
        self, message: dict[str, Any], channel: str | None = None
    ) -> None:
        async with self._registry_lock:
            if channel is None:
                recipients = list(self._clients.values())
            else:
                recipients = [
                    self._clients[client_id]
                    for client_id in self._channels.get(channel, set())
                    if client_id in self._clients
                ]
        if recipients:
            await asyncio.gather(
                *(self._send(websocket, message) for websocket in recipients),
                return_exceptions=True,
            )

    async def _direct(
        self, client_id: str, message: dict[str, Any], channel: str | None = None
    ) -> bool:
        async with self._registry_lock:
            recipient = self._clients.get(client_id)
            if channel is not None and client_id not in self._channels.get(channel, set()):
                recipient = None
        if recipient is None:
            return False
        try:
            await self._send(recipient, message)
        except ConnectionClosed:
            await self._unregister(client_id)
            return False
        return True

    @staticmethod
    def _error(detail: str) -> dict[str, Any]:
        return {"type": "system", "payload": {"error": detail}, "timestamp": timestamp()}

    async def _process(
        self, sender_id: str, sender: ServerConnection, raw: str | bytes
    ) -> None:
        try:
            incoming = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            await self._send(sender, self._error("invalid JSON"))
            return

        if not isinstance(incoming, dict):
            await self._send(sender, self._error("message must be a JSON object"))
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type not in SUPPORTED_TYPES:
            await self._send(sender, self._error("unsupported message type"))
            return
        channel = incoming.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel.strip()):
            await self._send(sender, self._error("channel must be a non-empty string"))
            return
        if message_type in SUBSCRIPTION_TYPES:
            if channel is None:
                await self._send(sender, self._error(f"{message_type} requires channel"))
                return
            if message_type == "subscribe":
                await self._subscribe(sender_id, channel)
            else:
                await self._unsubscribe(sender_id, channel)
            return
        if not isinstance(payload, dict):
            await self._send(sender, self._error("payload must be an object"))
            return

        message = {"type": message_type, "payload": payload, "timestamp": timestamp()}
        if channel is not None:
            message["channel"] = channel
        if message_type == "broadcast":
            await self.store.append_message(message)
            await self._broadcast(message, channel)
            return
        if message_type == "direct":
            recipient_id = payload.get("client_id")
            if not isinstance(recipient_id, str):
                await self._send(sender, self._error("direct payload requires client_id"))
                return
            if not await self._direct(recipient_id, message, channel):
                detail = "client not subscribed" if channel is not None else "client not connected"
                await self._send(sender, self._error(detail))
                return
            await self.store.append_message(message)
            return

        await self.store.append_message(message)
        await self._broadcast(message, channel)

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        client_id = await self._register(websocket)
        connected = {
            "type": "system",
            "payload": {"event": "connected", "client_id": client_id},
            "timestamp": timestamp(),
        }
        await self.store.append_message(connected)
        await self._send(websocket, connected)
        try:
            async for raw in websocket:
                await self._process(client_id, websocket, raw)
        except ConnectionClosed:
            pass
        finally:
            await self._unregister(client_id)

    async def process_request(
        self, connection: ServerConnection, request: Any
    ) -> Response | None:
        path = urlsplit(request.path).path
        if path == "/health":
            response_body: dict[str, Any] = {
                "connected_clients": await self.connected_count()
            }
        elif path == "/channels":
            response_body = {"channels": await self.channel_counts()}
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not encoded_name or "/" in encoded_name:
                return None
            channel = unquote(encoded_name)
            response_body = {
                "channel": channel,
                "subscribers": await self.channel_subscribers(channel),
            }
        else:
            return None
        body = json.dumps(response_body).encode()
        return Response(
            200,
            "OK",
            Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}),
            body,
        )

    @asynccontextmanager
    async def run(self, host: str = "127.0.0.1", port: int = 8765) -> AsyncIterator[Server]:
        await self.initialize()
        async with serve(
            self.websocket_handler,
            host,
            port,
            process_request=self.process_request,
        ) as server:
            yield server


async def main(host: str, port: int, data_dir: str) -> None:
    server = NotificationServer(data_dir)
    async with server.run(host, port):
        print(f"Notification server listening on http://{host}:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    parser.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data"))
    arguments = parser.parse_args()
    try:
        asyncio.run(main(arguments.host, arguments.port, arguments.data_dir))
    except KeyboardInterrupt:
        pass
