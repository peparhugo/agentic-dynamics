"""Async WebSocket notification server.

The client id is the client's ephemeral TCP source port.  The operating
system assigns that port per connection, so there is no second id allocator
to keep in sync with the registry.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed


SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class NotificationServer:
    """Manage WebSocket clients and deliver notification envelopes."""

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: dict[int, Any] = {}
        self.client_registry = self.clients
        self._lock = asyncio.Lock()
        self._server: Any = None

    async def start(self) -> None:
        """Start serving WebSocket connections and the ``/health`` endpoint."""
        self._server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        # port=0 is useful for tests and lets callers discover the chosen port.
        if self._server.sockets:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        """Close the listener and all active client connections."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        async with self._lock:
            connections = list(self.clients.values())
            self.clients.clear()
        await asyncio.gather(*(self._close(connection) for connection in connections))

    @property
    def connected_clients(self) -> int:
        return len(self.clients)

    async def _close(self, connection: Any) -> None:
        try:
            await connection.close()
        except Exception:
            pass

    async def _process_request(self, connection: Any, request: Any) -> Any:
        """Serve health checks through websockets' HTTP handshake hook."""
        path = request.path.split("?", 1)[0]
        if path != "/health":
            return None
        async with self._lock:
            count = len(self.clients)
        body = json.dumps({"connected_clients": count}).encode("utf-8")

        # Response and Headers are stable in supported websockets releases.
        from websockets.http11 import Headers, Response

        headers = Headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        return Response(200, "OK", headers, body)

    async def _handle_connection(self, connection: Any) -> None:
        peer = connection.transport.get_extra_info("peername")
        if not peer or len(peer) < 2:
            await connection.close(code=1011, reason="unable to determine client id")
            return
        client_id = int(peer[1])
        async with self._lock:
            self.clients[client_id] = connection
        try:
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            async with self._lock:
                if self.clients.get(client_id) is connection:
                    self.clients.pop(client_id, None)

    async def _handle_message(self, sender_id: int, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            return

        if message_type == "direct":
            target = payload.get("client_id", payload.get("recipient"))
            try:
                target_id = int(target)
            except (TypeError, ValueError):
                return
            await self.send_to(target_id, message_type, payload)
            return
        await self.broadcast(message_type, payload)

    async def broadcast(
        self,
        message_type: str | dict[str, Any] = "broadcast",
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Send one JSON notification to every currently connected client."""
        if isinstance(message_type, dict):
            envelope = message_type
            message_type = envelope.get("type", "broadcast")
            payload = envelope.get("payload", {})
        if message_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        message = json.dumps({"type": message_type, "payload": payload, "timestamp": _timestamp()})
        async with self._lock:
            connections = list(self.clients.values())
        await asyncio.gather(*(self._send(connection, message) for connection in connections))

    async def send_to(self, client_id: int, message_type: str, payload: dict[str, Any]) -> None:
        if message_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        async with self._lock:
            connection = self.clients.get(client_id)
        if connection is not None:
            message = json.dumps({"type": message_type, "payload": payload, "timestamp": _timestamp()})
            await self._send(connection, message)

    async def _send(self, connection: Any, message: str) -> None:
        try:
            await connection.send(message)
        except ConnectionClosed:
            pass


async def main() -> None:
    server = NotificationServer()
    await server.start()
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
