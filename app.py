import asyncio
import json
import uuid
from datetime import datetime, timezone

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


class ClientRegistry:
    def __init__(self):
        self._clients: dict[str, object] = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket) -> str:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = websocket
        return client_id

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def broadcast(self, message: str, *, exclude: str | None = None) -> None:
        disconnected: list[str] = []
        async with self._lock:
            clients = list(self._clients.items())
        for cid, ws in clients:
            if cid == exclude:
                continue
            try:
                await ws.send(message)
            except (ConnectionClosed, OSError):
                disconnected.append(cid)
        for cid in disconnected:
            await self.unregister(cid)

    async def send_to(self, target_id: str, message: str) -> bool:
        async with self._lock:
            ws = self._clients.get(target_id)
        if ws is None:
            return False
        try:
            await ws.send(message)
            return True
        except (ConnectionClosed, OSError):
            await self.unregister(target_id)
            return False

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def has_client(self, client_id: str) -> bool:
        async with self._lock:
            return client_id in self._clients


registry = ClientRegistry()


def _make_message(msg_type: str, payload: dict) -> str:
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _send_ws(ws, message: str):
    return ws.send(message)


async def ws_handler(websocket) -> None:
    client_id = await registry.register(websocket)

    welcome = _make_message("system", {"client_id": client_id, "connected": True, "message": "Welcome"})
    await _send_ws(websocket, welcome)

    join_notice = _make_message("system", {"client_id": client_id, "event": "connected"})
    await registry.broadcast(join_notice, exclude=client_id)

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})

            outbound = _make_message(msg_type, payload)

            if msg_type == "direct":
                target = data.get("target")
                if target:
                    await registry.send_to(target, outbound)
            elif msg_type == "broadcast":
                await registry.broadcast(outbound, exclude=client_id)
            else:
                await registry.broadcast(outbound, exclude=None)
    except ConnectionClosed:
        pass
    finally:
        await registry.unregister(client_id)
        leave_notice = _make_message("system", {"client_id": client_id, "event": "disconnected"})
        await registry.broadcast(leave_notice, exclude=None)


async def http_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=10)
        line = raw.decode().strip()
        if not line:
            writer.close()
            return

        parts = line.split()
        if len(parts) < 2:
            writer.close()
            return

        method, path = parts[0], parts[1]

        if method == "GET" and path == "/health":
            body = json.dumps({"connected_clients": await registry.count()})
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{body}"
            )
        else:
            body = json.dumps({"error": "not found"})
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{body}"
            )

        writer.write(response.encode())
        await writer.drain()
    except (asyncio.TimeoutError, OSError):
        pass
    finally:
        writer.close()


async def start_server(ws_host: str = "localhost", ws_port: int = 8765,
                       http_host: str = "localhost", http_port: int = 8080) -> tuple:
    ws_server = await serve(ws_handler, ws_host, ws_port)
    http_server = await asyncio.start_server(http_handler, http_host, http_port)
    return ws_server, http_server


async def main() -> None:
    ws_server, http_server = await start_server()
    async with ws_server, http_server:
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
