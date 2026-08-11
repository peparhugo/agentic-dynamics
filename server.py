import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._lock = threading.Lock()

    def add(self, client_id, websocket):
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id):
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id):
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self):
        with self._lock:
            return list(self._clients.items())

    def count(self):
        with self._lock:
            return len(self._clients)


registry = ClientRegistry()


def make_message(msg_type, payload):
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def broadcast(message):
    tasks = []
    for cid, ws in registry.get_all():
        tasks.append(_safe_send(cid, ws, message))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _safe_send(client_id, websocket, message):
    try:
        await websocket.send(message)
    except (ConnectionClosedOK, ConnectionClosedError):
        registry.remove(client_id)
    except Exception:
        registry.remove(client_id)


async def send_direct(recipient_id, message):
    ws = registry.get(recipient_id)
    if ws is None:
        return
    try:
        await ws.send(message)
    except (ConnectionClosedOK, ConnectionClosedError):
        registry.remove(recipient_id)
    except Exception:
        registry.remove(recipient_id)


async def handler(websocket):
    client_id = str(uuid.uuid4())
    registry.add(client_id, websocket)

    try:
        welcome = make_message("system", {
            "message": f"Connected as {client_id}",
            "client_id": client_id
        })
        await websocket.send(welcome)
    except Exception:
        registry.remove(client_id)
        return

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})

            if msg_type == "broadcast":
                broadcast_msg = make_message("broadcast", payload)
                await broadcast(broadcast_msg)
            elif msg_type == "direct":
                recipient = payload.get("recipient")
                if recipient:
                    direct_msg = make_message("direct", {
                        "from": client_id,
                        "message": payload.get("message", "")
                    })
                    await send_direct(recipient, direct_msg)
                    await websocket.send(direct_msg)
    except (ConnectionClosedOK, ConnectionClosedError):
        pass
    except Exception:
        pass
    finally:
        registry.remove(client_id)
        leave_msg = make_message("system", {
            "message": f"Client {client_id} disconnected",
            "client_id": client_id
        })
        await broadcast(leave_msg)


def process_request(connection, request):
    if request.path == "/health":
        count = registry.count()
        response = connection.respond(
            200,
            json.dumps({"clients": count, "status": "ok"}),
        )
        response.headers["Content-Type"] = "application/json"
        return response
    return None


async def main():
    async with serve(handler, "localhost", 8765, process_request=process_request):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
