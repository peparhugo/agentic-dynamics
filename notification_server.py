"""WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, and lets
clients broadcast JSON notifications to every connected peer or send one
directly to another client by ID. Exposes GET /health over plain HTTP on
the same port for a connected-client count.
"""

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

from websockets.asyncio.server import serve, ServerConnection
from websockets.exceptions import ConnectionClosed

MESSAGE_TYPES = {"broadcast", "direct", "system"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict) -> str:
    return json.dumps({"type": msg_type, "payload": payload, "timestamp": now_iso()})


class ClientRegistry:
    """Tracks connected clients behind a lock, protecting registration and
    removal against concurrent access from multiple handler coroutines."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.Lock()

    def add(self, connection: ServerConnection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[ServerConnection]:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


registry = ClientRegistry()


async def broadcast(payload: dict) -> None:
    message = make_message("broadcast", payload)
    for _client_id, connection in registry.snapshot():
        try:
            await connection.send(message)
        except ConnectionClosed:
            pass


async def send_direct(target_id: str, payload: dict) -> bool:
    connection = registry.get(target_id)
    if connection is None:
        return False
    try:
        await connection.send(make_message("direct", payload))
        return True
    except ConnectionClosed:
        return False


async def handle_message(connection: ServerConnection, raw: str) -> None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await connection.send(make_message("system", {"error": "invalid JSON"}))
        return

    if not isinstance(data, dict):
        await connection.send(make_message("system", {"error": "message must be a JSON object"}))
        return

    msg_type = data.get("type")
    payload = data.get("payload", {})

    if msg_type not in MESSAGE_TYPES:
        await connection.send(
            make_message("system", {"error": f"unsupported type: {msg_type!r}"})
        )
        return

    if not isinstance(payload, dict):
        await connection.send(make_message("system", {"error": "payload must be an object"}))
        return

    if msg_type == "broadcast":
        await broadcast(payload)
    elif msg_type == "direct":
        target_id = payload.get("target")
        if not target_id:
            await connection.send(
                make_message("system", {"error": "direct message requires 'target' in payload"})
            )
            return
        delivered = await send_direct(target_id, payload)
        if not delivered:
            await connection.send(
                make_message("system", {"error": f"client {target_id} not connected"})
            )
    elif msg_type == "system":
        await connection.send(make_message("system", {"ack": True}))


async def handler(connection: ServerConnection) -> None:
    client_id = registry.add(connection)
    try:
        await connection.send(make_message("system", {"event": "connected", "client_id": client_id}))
        async for raw in connection:
            await handle_message(connection, raw)
    except ConnectionClosed:
        pass
    finally:
        registry.remove(client_id)


async def process_request(connection: ServerConnection, request):
    if request.path == "/health":
        response = connection.respond(HTTPStatus.OK, "")
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({"connected_clients": registry.count()}).encode()
        return response
    return None


async def main(host: str = "localhost", port: int = 8765) -> None:
    async with serve(handler, host, port, process_request=process_request):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
