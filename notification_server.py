"""
WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, and
supports broadcasting JSON messages to every connected client. A plain
GET /health request (handled on the same port, before the WebSocket
handshake) reports the number of currently connected clients.

Every client registry mutation happens inside a coroutine running on the
single asyncio event loop driving this server (connection handlers,
broadcast, health check). No background thread ever touches the
registry, so the usual asyncio single-thread guarantee applies and a
plain dict is safe here. That guarantee does NOT generalize to "dict
access is always safe even from other threads" -- a dict mutated from a
real OS thread while the event loop reads it would still need a lock or
another handoff mechanism. It applies only because this design keeps all
registry access on the loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import websockets
from websockets.asyncio.server import serve

logger = logging.getLogger("notification_server")

MESSAGE_TYPES = {"broadcast", "direct", "system"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Client:
    client_id: str
    connection: "websockets.asyncio.server.ServerConnection"


class ClientRegistry:
    """Tracks connected clients.

    All access happens from coroutines scheduled on the single asyncio
    event loop that runs this server (connect/disconnect handlers,
    broadcast, and the /health request handler). Because nothing outside
    that event loop ever touches `_clients`, plain dict reads/writes are
    safe without a lock. If a caller ever needed to mutate this registry
    from a separate OS thread, that guarantee would no longer hold and
    an asyncio.Lock (or a thread-safe handoff via
    call_soon_threadsafe) would be required.
    """

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}

    def add(self, client: Client) -> None:
        self._clients[client.client_id] = client

    def remove(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[Client]:
        return self._clients.get(client_id)

    def all(self) -> list[Client]:
        return list(self._clients.values())

    def count(self) -> int:
        return len(self._clients)


def make_message(msg_type: str, payload: dict, timestamp: Optional[str] = None) -> dict:
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {msg_type}")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": timestamp or utc_now_iso(),
    }


class NotificationServer:
    def __init__(self) -> None:
        self.registry = ClientRegistry()

    async def handler(self, connection) -> None:
        client_id = str(uuid.uuid4())
        client = Client(client_id=client_id, connection=connection)
        self.registry.add(client)
        logger.info("client connected: %s", client_id)
        try:
            await connection.send(json.dumps(make_message(
                "system",
                {"event": "connected", "client_id": client_id},
            )))
            async for raw_message in connection:
                await self._handle_incoming(client, raw_message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            logger.info("client disconnected: %s", client_id)

    async def _handle_incoming(self, client: Client, raw_message: str) -> None:
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            await client.connection.send(json.dumps(make_message(
                "system", {"error": "invalid JSON"},
            )))
            return

        msg_type = data.get("type")
        payload = data.get("payload", {})

        if msg_type == "broadcast":
            await self.broadcast(payload, sender_id=client.client_id)
        elif msg_type == "direct":
            target_id = payload.get("target_id")
            await self.send_direct(target_id, payload.get("message", {}), sender_id=client.client_id)
        else:
            await client.connection.send(json.dumps(make_message(
                "system", {"error": f"unsupported message type: {msg_type}"},
            )))

    async def broadcast(self, payload: dict, sender_id: Optional[str] = None) -> int:
        message = json.dumps(make_message("broadcast", {**payload, **({"sender_id": sender_id} if sender_id else {})}))
        clients = self.registry.all()
        sent = 0
        for client in clients:
            try:
                await client.connection.send(message)
                sent += 1
            except websockets.exceptions.ConnectionClosed:
                continue
        return sent

    async def send_direct(self, target_id: Optional[str], payload: dict, sender_id: Optional[str] = None) -> bool:
        client = self.registry.get(target_id) if target_id else None
        if client is None:
            return False
        message = json.dumps(make_message("direct", {**payload, **({"sender_id": sender_id} if sender_id else {})}))
        try:
            await client.connection.send(message)
            return True
        except websockets.exceptions.ConnectionClosed:
            return False

    def process_request(self, connection, request):
        """Serve GET /health as a plain HTTP response before the
        WebSocket handshake; let every other path continue as a normal
        upgrade attempt."""
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.registry.count()})
            response = connection.respond(HTTPStatus.OK, body)
            response.headers["Content-Type"] = "application/json"
            return response
        return None


def create_server(host: str = "127.0.0.1", port: int = 8765):
    server_state = NotificationServer()
    ws_server = serve(
        server_state.handler,
        host,
        port,
        process_request=server_state.process_request,
    )
    return ws_server, server_state


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ws_server, _ = create_server()
    async with ws_server:
        logger.info("notification server listening")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
