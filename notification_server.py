"""WebSocket-based notification server built on the ``websockets`` library.

Clients connect over WebSocket, are assigned a unique ID, and can exchange
JSON messages. The server also exposes a small REST endpoint (``GET /health``)
that reports the number of currently connected clients.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotificationServer:
    """An asyncio WebSocket notification server.

    The client registry is a plain :class:`dict`. Because asyncio runs all
    coroutines and callbacks on a single event loop, every read and write to
    the registry happens on that loop, so no locking is required.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._server = None

    # ── Registry ──────────────────────────────────────────────────

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def client_ids(self) -> list[str]:
        return list(self._clients.keys())

    def has_client(self, client_id: str) -> bool:
        return client_id in self._clients

    def _drop_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        for name in list(self._subscriptions):
            members = self._subscriptions[name]
            members.discard(client_id)
            if not members:
                self._subscriptions.pop(name, None)

    # ── Channels ──────────────────────────────────────────────────

    def subscribe(self, client_id: str, channel: str) -> bool:
        if not self.has_client(client_id):
            return False
        self._subscriptions.setdefault(channel, set()).add(client_id)
        return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        members = self._subscriptions.get(channel)
        if members is None:
            return False
        members.discard(client_id)
        if not members:
            self._subscriptions.pop(channel, None)
        return True

    def channel_names(self) -> list[str]:
        return sorted(self._subscriptions.keys())

    def channel_subscribers(self, channel: str) -> list[str]:
        return sorted(self._subscriptions.get(channel, set()))

    def channel_count(self, channel: str) -> int:
        return len(self._subscriptions.get(channel, set()))

    def channels(self) -> list[dict[str, Any]]:
        return [
            {"name": name, "subscribers": len(self._subscriptions[name])}
            for name in sorted(self._subscriptions)
            if self._subscriptions[name]
        ]

    # ── Message helpers ───────────────────────────────────────────

    @staticmethod
    def make_message(mtype: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"type": mtype, "payload": payload, "timestamp": utc_now_iso()}

    @staticmethod
    def encode(message: dict[str, Any]) -> str:
        return json.dumps(message)

    # ── Sending ───────────────────────────────────────────────────

    async def send_to(self, client_id: str, message: dict[str, Any]) -> bool:
        ws = self._clients.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send(self.encode(message))
            return True
        except Exception:
            self._drop_client(client_id)
            return False

    async def send_to_channel(self, channel: str, message: dict[str, Any]) -> int:
        data = self.encode(message)
        members = list(self._subscriptions.get(channel, set()))
        delivered = 0
        for client_id in members:
            ws = self._clients.get(client_id)
            if ws is None:
                self._drop_client(client_id)
                continue
            try:
                await ws.send(data)
                delivered += 1
            except Exception:
                self._drop_client(client_id)
        return delivered

    async def broadcast(self, message: dict[str, Any]) -> int:
        data = self.encode(message)
        stale: list[str] = []
        for client_id, ws in list(self._clients.items()):
            try:
                await ws.send(data)
            except Exception:
                stale.append(client_id)
        for client_id in stale:
            self._drop_client(client_id)
        return len(self._clients)

    # ── Connection handling ───────────────────────────────────────

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        self._clients[client_id] = websocket
        try:
            await self.send_to(
                client_id,
                self.make_message(
                    "system", {"event": "connected", "client_id": client_id}
                ),
            )
            async for raw in websocket:
                await self._route(websocket, client_id, raw)
        finally:
            self._drop_client(client_id)
            await self.broadcast(
                self.make_message(
                    "system", {"event": "disconnected", "client_id": client_id}
                )
            )

    async def _route(
        self, websocket: ServerConnection, client_id: str, raw: str | bytes
    ) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            await self.send_to(
                client_id,
                self.make_message(
                    "system", {"event": "error", "message": "invalid JSON"}
                ),
            )
            return

        if not isinstance(data, dict):
            await self.send_to(
                client_id,
                self.make_message(
                    "system", {"event": "error", "message": "message must be an object"}
                ),
            )
            return

        mtype = data.get("type")
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        channel = data.get("channel")
        if not isinstance(channel, str) and "channel" in payload:
            channel = payload.get("channel")

        if mtype == "subscribe":
            if not channel:
                await self.send_to(
                    client_id,
                    self.make_message(
                        "system",
                        {"event": "error", "message": "subscribe requires a channel"},
                    ),
                )
                return
            self.subscribe(client_id, channel)
            await self.send_to(
                client_id,
                self.make_message("system", {"event": "subscribed", "channel": channel}),
            )
        elif mtype == "unsubscribe":
            if not channel:
                await self.send_to(
                    client_id,
                    self.make_message(
                        "system",
                        {"event": "error", "message": "unsubscribe requires a channel"},
                    ),
                )
                return
            self.unsubscribe(client_id, channel)
            await self.send_to(
                client_id,
                self.make_message(
                    "system", {"event": "unsubscribed", "channel": channel}
                ),
            )
        elif mtype == "broadcast":
            message = self.make_message("broadcast", dict(payload))
            if channel:
                message["channel"] = channel
                await self.send_to_channel(channel, message)
            else:
                await self.broadcast(message)
        elif mtype == "direct":
            target = payload.get("target")
            if not target:
                await self.send_to(
                    client_id,
                    self.make_message(
                        "system",
                        {"event": "error", "message": "direct message requires a target"},
                    ),
                )
                return
            out_payload = dict(payload)
            out_payload["sender"] = client_id
            message = self.make_message("direct", out_payload)
            delivered = await self.send_to(target, message)
            if not delivered:
                await self.send_to(
                    client_id,
                    self.make_message(
                        "system",
                        {
                            "event": "error",
                            "message": "target not found",
                            "target": target,
                        },
                    ),
                )
        else:
            await self.send_to(
                client_id,
                self.make_message(
                    "system",
                    {"event": "error", "message": f"unsupported type: {mtype!r}"},
                ),
            )

    # ── REST endpoint (via the WebSocket handshake hook) ──────────

    async def process_request(
        self, connection: ServerConnection, request: Any
    ) -> Response | None:
        path = request.path.split("?", 1)[0]
        if path == "/health":
            body = json.dumps(
                {"status": "ok", "clients": self.client_count}
            ).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        if path == "/channels":
            body = json.dumps({"channels": self.channels()}).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")])
            if not name or name not in self._subscriptions:
                body = json.dumps({"error": "channel not found"}).encode("utf-8")
                headers = Headers({"Content-Type": "application/json"})
                return Response(404, "Not Found", headers, body)
            body = json.dumps(
                {"channel": name, "subscribers": self.channel_subscribers(name)}
            ).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        return None

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        self._server = await serve(
            self.handler,
            self.host,
            self.port,
            process_request=self.process_request,
        )
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def run_forever(self) -> None:
        await self.start()
        try:
            await self._server.serve_forever()
        finally:
            await self.stop()

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        return f"http://{self.host}:{self.port}/health"

    @property
    def channels_url(self) -> str:
        return f"http://{self.host}:{self.port}/channels"


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = NotificationServer(host=host, port=port)
    asyncio.run(server.run_forever())


if __name__ == "__main__":
    main()
