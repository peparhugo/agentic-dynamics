"""WebSocket notification server with a small HTTP health API."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify
from websockets.asyncio.server import Server, ServerConnection, serve


app = Flask(__name__)

# This is the only lock used for the registry. Never perform socket I/O while
# holding it: a slow client must not block connects, disconnects, or health.
clients_lock = threading.Lock()
clients: dict[str, ServerConnection] = {}

SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": utc_timestamp(),
    }


def encode_message(message: dict[str, Any]) -> str:
    return json.dumps(message, separators=(",", ":"))


def validate_message(value: Any) -> str | None:
    if not isinstance(value, dict):
        return "message must be a JSON object"
    if set(value) != {"type", "payload", "timestamp"}:
        return "message must contain only type, payload, and timestamp"
    if value["type"] not in SUPPORTED_TYPES:
        return "unsupported message type"
    if not isinstance(value["payload"], dict):
        return "payload must be an object"
    if not isinstance(value["timestamp"], str):
        return "timestamp must be a string"
    return None


def client_count() -> int:
    with clients_lock:
        return len(clients)


def _add_client(client_id: str, websocket: ServerConnection) -> None:
    with clients_lock:
        clients[client_id] = websocket


def _remove_client(client_id: str, websocket: ServerConnection) -> None:
    with clients_lock:
        if clients.get(client_id) is websocket:
            del clients[client_id]


def _client_snapshot() -> list[tuple[str, ServerConnection]]:
    with clients_lock:
        return list(clients.items())


async def _send(websocket: ServerConnection, message: dict[str, Any]) -> None:
    await websocket.send(encode_message(message))


async def broadcast(message: dict[str, Any]) -> None:
    """Send a valid message to a lock-protected snapshot of all clients."""
    error = validate_message(message)
    if error:
        raise ValueError(error)

    snapshot = _client_snapshot()
    if not snapshot:
        return

    results = await asyncio.gather(
        *(_send(websocket, message) for _, websocket in snapshot),
        return_exceptions=True,
    )
    for (client_id, websocket), result in zip(snapshot, results):
        if isinstance(result, BaseException):
            _remove_client(client_id, websocket)


async def send_direct(client_id: str, message: dict[str, Any]) -> bool:
    """Send to one client, taking the socket reference under the registry lock."""
    with clients_lock:
        websocket = clients.get(client_id)
    if websocket is None:
        return False
    try:
        await _send(websocket, message)
    except Exception:
        _remove_client(client_id, websocket)
        return False
    return True


async def _send_error(websocket: ServerConnection, detail: str) -> None:
    await _send(websocket, make_message("system", {"error": detail}))


async def websocket_handler(websocket: ServerConnection) -> None:
    client_id = str(uuid.uuid4())
    _add_client(client_id, websocket)
    try:
        await _send(
            websocket,
            make_message("system", {"event": "connected", "client_id": client_id}),
        )
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
            except (json.JSONDecodeError, TypeError):
                await _send_error(websocket, "invalid JSON")
                continue

            error = validate_message(message)
            if error:
                await _send_error(websocket, error)
                continue

            if message["type"] == "broadcast":
                await broadcast(message)
            elif message["type"] == "direct":
                recipient = message["payload"].get("client_id")
                if not isinstance(recipient, str) or not recipient:
                    await _send_error(websocket, "direct payload requires client_id")
                elif not await send_direct(recipient, message):
                    await _send_error(websocket, "client not found")
            else:
                await _send_error(websocket, "system messages are server-only")
    finally:
        _remove_client(client_id, websocket)


@app.get("/health")
def health():
    return jsonify({"connected_clients": client_count()})


class NotificationServer:
    """Run the asyncio WebSocket loop in a dedicated daemon thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.loop: asyncio.AbstractEventLoop | None = None
        self._server: Server | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None

    def start(self, timeout: float = 5.0) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._ready.clear()
        self._startup_error = None
        self._thread = threading.Thread(
            target=self._run,
            name="notification-websocket-loop",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("WebSocket server did not start")
        if self._startup_error is not None:
            raise RuntimeError("WebSocket server failed to start") from self._startup_error

    def _run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def start_server() -> Server:
            return await serve(websocket_handler, self.host, self.port)

        try:
            self._server = self.loop.run_until_complete(start_server())
            sockets = self._server.sockets
            if sockets:
                self.port = sockets[0].getsockname()[1]
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            self.loop.close()
            return

        self._ready.set()
        try:
            self.loop.run_forever()
        finally:
            self._server.close()
            self.loop.run_until_complete(self._server.wait_closed())
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self.loop.close()

    def stop(self, timeout: float = 5.0) -> None:
        if self.loop is None or self._thread is None or not self._thread.is_alive():
            return
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError("WebSocket server did not stop")

    def broadcast(self, payload: dict[str, Any], timeout: float = 5.0) -> None:
        if self.loop is None or not self.loop.is_running():
            raise RuntimeError("WebSocket server is not running")
        future = asyncio.run_coroutine_threadsafe(
            broadcast(make_message("broadcast", payload)), self.loop
        )
        future.result(timeout)


def main() -> None:
    server = NotificationServer()
    server.start()
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        server.stop()


if __name__ == "__main__":
    main()
