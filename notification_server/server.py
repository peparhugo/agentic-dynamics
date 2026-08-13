"""WebSocket-based notification server.

- Accepts WebSocket connections and assigns each client a unique ID.
- Broadcasts messages to all connected clients, or routes a message to one
  specific client ("direct"), or emits server-originated "system" messages.
- Cleans up the client registry on disconnect.
- Exposes GET /health (plain HTTP, served via the websockets handshake hook)
  returning the number of currently connected clients.
- Persists an audit trail of every event to a flat JSON-Lines file — no
  database is used anywhere in this service.
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

import websockets
from websockets.datastructures import Headers
from websockets.http11 import Response

from .messages import MessageError, encode, make_message, now_iso, parse_client_message
from .registry import ClientRegistry
from .storage import FlatFileStorage

logger = logging.getLogger("notification_server")

DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "events.jsonl"


class NotificationServer:
    def __init__(self, host="localhost", port=8765, storage_path=DEFAULT_DATA_PATH):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self.storage = FlatFileStorage(storage_path)
        self._server = None

    # ── connection lifecycle ────────────────────────────────────

    async def handler(self, websocket):
        client_id = self.registry.add(websocket)
        self.storage.append_event(
            {"event": "connect", "client_id": client_id, "timestamp": now_iso()}
        )
        try:
            welcome = make_message("system", {"event": "connected", "client_id": client_id})
            await websocket.send(encode(welcome))
            async for raw in websocket:
                await self._dispatch(client_id, websocket, raw)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            self.storage.append_event(
                {"event": "disconnect", "client_id": client_id, "timestamp": now_iso()}
            )

    async def _dispatch(self, client_id, websocket, raw):
        try:
            data = parse_client_message(raw)
        except MessageError as exc:
            error = make_message("system", {"event": "error", "detail": str(exc)})
            await self._safe_send(websocket, encode(error))
            return

        msg_type = data["type"]
        payload = data["payload"]
        self.storage.append_event(
            {
                "event": "message",
                "type": msg_type,
                "from": client_id,
                "payload": payload,
                "timestamp": now_iso(),
            }
        )

        if msg_type == "broadcast":
            await self.broadcast(payload, sender_id=client_id)
        elif msg_type == "direct":
            target_id = payload.get("target_id")
            content = payload.get("content", {})
            delivered = await self.send_direct(target_id, content, sender_id=client_id)
            if not delivered:
                error = make_message(
                    "system", {"event": "error", "detail": f"unknown target_id: {target_id!r}"}
                )
                await self._safe_send(websocket, encode(error))
        elif msg_type == "system":
            ack = make_message("system", {"event": "ack"})
            await self._safe_send(websocket, encode(ack))

    # ── message delivery ────────────────────────────────────────

    async def broadcast(self, payload, sender_id=None):
        body = dict(payload)
        if sender_id is not None:
            body.setdefault("sender_id", sender_id)
        message = make_message("broadcast", body)
        data = encode(message)
        clients = self.registry.all()
        if clients:
            await asyncio.gather(*(self._safe_send(ws, data) for ws in clients.values()))
        return message

    async def send_direct(self, target_id, content, sender_id=None) -> bool:
        websocket = self.registry.get(target_id)
        if websocket is None:
            return False
        message = make_message(
            "direct", {"content": content, "sender_id": sender_id, "target_id": target_id}
        )
        await self._safe_send(websocket, encode(message))
        return True

    async def send_system(self, target_id, payload) -> bool:
        websocket = self.registry.get(target_id)
        if websocket is None:
            return False
        message = make_message("system", payload)
        await self._safe_send(websocket, encode(message))
        return True

    @staticmethod
    async def _safe_send(websocket, data):
        try:
            await websocket.send(data)
        except websockets.exceptions.ConnectionClosed:
            pass

    # ── REST: GET /health ───────────────────────────────────────

    def process_request(self, connection, request):
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.registry.count()}).encode()
            headers = Headers(
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ]
            )
            return Response(200, "OK", headers, body)
        return None

    # ── run/serve ────────────────────────────────────────────────

    async def start(self):
        self._server = await websockets.serve(
            self.handler,
            self.host,
            self.port,
            process_request=self.process_request,
        )
        logger.info("notification server listening on ws://%s:%s", self.host, self.port)
        return self._server

    async def stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def serve_forever(self):
        await self.start()
        await self._server.wait_closed()


def main():
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    server = NotificationServer(host=args.host, port=args.port, storage_path=args.data)
    asyncio.run(server.serve_forever())


if __name__ == "__main__":
    main()
