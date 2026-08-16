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
import re
import urllib.parse
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


class ChannelRegistry:
    """Tracks channel subscriptions as channel name -> set of client IDs.

    Like ClientRegistry, every mutation happens from a coroutine running on
    the single event loop that drives this server, so a plain dict of sets
    is safe without a lock.
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}

    def subscribe(self, channel: str, client_id: str) -> None:
        self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, channel: str, client_id: str) -> None:
        subscribers = self._channels.get(channel)
        if subscribers is None:
            return
        subscribers.discard(client_id)
        if not subscribers:
            del self._channels[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        for channel in list(self._channels.keys()):
            self.unsubscribe(channel, client_id)

    def subscribers(self, channel: str) -> list[str]:
        return sorted(self._channels.get(channel, set()))

    def channels(self) -> dict[str, int]:
        return {name: len(subscribers) for name, subscribers in self._channels.items()}


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
        self.channels = ChannelRegistry()

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
            self.channels.unsubscribe_all(client_id)
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
        elif msg_type == "subscribe":
            await self._handle_subscribe(client, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client, payload)
        else:
            await client.connection.send(json.dumps(make_message(
                "system", {"error": f"unsupported message type: {msg_type}"},
            )))

    async def _handle_subscribe(self, client: "Client", payload: dict) -> None:
        channel = payload.get("channel")
        if not channel:
            await client.connection.send(json.dumps(make_message(
                "system", {"error": "channel is required"},
            )))
            return
        self.channels.subscribe(channel, client.client_id)
        await client.connection.send(json.dumps(make_message(
            "system", {"event": "subscribed", "channel": channel},
        )))

    async def _handle_unsubscribe(self, client: "Client", payload: dict) -> None:
        channel = payload.get("channel")
        if not channel:
            await client.connection.send(json.dumps(make_message(
                "system", {"error": "channel is required"},
            )))
            return
        self.channels.unsubscribe(channel, client.client_id)
        await client.connection.send(json.dumps(make_message(
            "system", {"event": "unsubscribed", "channel": channel},
        )))

    async def broadcast(self, payload: dict, sender_id: Optional[str] = None) -> int:
        message = json.dumps(make_message("broadcast", {**payload, **({"sender_id": sender_id} if sender_id else {})}))
        channel = payload.get("channel")
        if channel:
            clients = [
                c for c in (self.registry.get(cid) for cid in self.channels.subscribers(channel))
                if c is not None
            ]
        else:
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
        """Serve GET /health, /channels, and /channels/{name}/subscribers as
        plain HTTP responses before the WebSocket handshake; let every other
        path continue as a normal upgrade attempt."""
        path = request.path.split("?", 1)[0]

        if path == "/health":
            body = json.dumps({"connected_clients": self.registry.count()})
            return self._json_response(connection, body)

        if path == "/channels":
            body = json.dumps({"channels": self.channels.channels()})
            return self._json_response(connection, body)

        match = re.fullmatch(r"/channels/([^/]+)/subscribers", path)
        if match:
            channel = urllib.parse.unquote(match.group(1))
            body = json.dumps({
                "channel": channel,
                "subscribers": self.channels.subscribers(channel),
            })
            return self._json_response(connection, body)

        return None

    @staticmethod
    def _json_response(connection, body: str):
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response


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
