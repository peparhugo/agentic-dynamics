import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._lock = threading.Lock()

    def add(self, client_id, websocket):
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)

    def count(self):
        with self._lock:
            return len(self._clients)

    def get_all(self):
        with self._lock:
            return dict(self._clients)

    def clear(self):
        with self._lock:
            self._clients.clear()


class NotificationServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()

    async def _handler(self, websocket):
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)
        try:
            welcome = {
                "type": "system",
                "payload": {"client_id": client_id, "message": "Connected"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send(json.dumps(welcome))

            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "broadcast")
                payload = data.get("payload", {})

                if msg_type == "broadcast":
                    notification = {
                        "type": "broadcast",
                        "payload": payload,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "sender": client_id,
                    }
                    await self._broadcast(notification)
                elif msg_type == "direct":
                    target = data.get("target")
                    if target:
                        notification = {
                            "type": "direct",
                            "payload": payload,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "sender": client_id,
                        }
                        await self._send_direct(target, notification)
        finally:
            self.registry.remove(client_id)

    async def _broadcast(self, message):
        clients = self.registry.get_all()
        message_str = json.dumps(message)
        disconnected = []
        for cid, ws in clients.items():
            try:
                await ws.send(message_str)
            except ConnectionClosed:
                disconnected.append(cid)
        for cid in disconnected:
            self.registry.remove(cid)

    async def _send_direct(self, target_id, message):
        clients = self.registry.get_all()
        ws = clients.get(target_id)
        if ws is not None:
            try:
                await ws.send(json.dumps(message))
            except ConnectionClosed:
                self.registry.remove(target_id)

    def _process_request(self, connection, request):
        if request.path == "/health":
            count = self.registry.count()
            response = connection.respond(200, json.dumps({"clients": count}))
            response.headers["Content-Type"] = "application/json"
            return response
        return None

    def run(self):
        return serve(
            self._handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )


async def main():
    server = NotificationServer()
    async with server.run():
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
