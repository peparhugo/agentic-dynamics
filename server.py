import asyncio
import json
import uuid
import threading
from datetime import datetime, timezone

import websockets
from websockets import ServerConnection
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from aiohttp import web


class ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}

    def add(self, client_id: str, ws: ServerConnection) -> None:
        with self._lock:
            self._clients[client_id] = ws

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            self._subscriptions.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self) -> dict[str, ServerConnection]:
        with self._lock:
            return dict(self._clients)

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id not in self._clients:
                return
            self._subscriptions.setdefault(client_id, set()).add(channel)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subs = self._subscriptions.get(client_id)
            if subs:
                subs.discard(channel)
                if not subs:
                    self._subscriptions.pop(client_id, None)

    def get_channels(self) -> dict[str, int]:
        channels: dict[str, int] = {}
        with self._lock:
            for subs in self._subscriptions.values():
                for ch in subs:
                    channels[ch] = channels.get(ch, 0) + 1
        return channels

    def get_subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return [cid for cid, subs in self._subscriptions.items() if channel in subs]

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


registry = ClientRegistry()


def _make_message(msg_type: str, payload: dict) -> str:
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _broadcast(msg_type: str, payload: dict, exclude_id: str | None = None, channel: str | None = None) -> None:
    msg = _make_message(msg_type, payload)
    clients = registry.get_all()
    if channel:
        target_ids = registry.get_subscribers(channel)
    else:
        target_ids = list(clients.keys())
    for cid in target_ids:
        if cid == exclude_id:
            continue
        ws = clients.get(cid)
        if ws is None:
            continue
        try:
            await ws.send(msg)
        except ConnectionClosed:
            registry.remove(cid)


async def handler(websocket: ServerConnection) -> None:
    client_id = str(uuid.uuid4())
    registry.add(client_id, websocket)

    try:
        await websocket.send(_make_message("system", {
            "client_id": client_id,
            "message": "Connected",
        }))

        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "broadcast":
                channel = data.get("channel")
                await _broadcast("broadcast", payload, exclude_id=client_id, channel=channel)

            elif msg_type == "direct":
                target_id = data.get("target")
                if target_id:
                    target_ws = registry.get(target_id)
                    if target_ws:
                        try:
                            await target_ws.send(_make_message("direct", payload))
                        except ConnectionClosed:
                            registry.remove(target_id)

            elif msg_type == "subscribe":
                ch = data.get("channel")
                if ch:
                    registry.subscribe(client_id, ch)

            elif msg_type == "unsubscribe":
                ch = data.get("channel")
                if ch:
                    registry.unsubscribe(client_id, ch)

    finally:
        registry.remove(client_id)
        await _broadcast("system", {
            "client_id": client_id,
            "message": "Disconnected",
        })


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"clients": registry.count})


async def channels_handler(request: web.Request) -> web.Response:
    return web.json_response({"channels": registry.get_channels()})


async def channel_subscribers_handler(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    subscribers = registry.get_subscribers(name)
    return web.json_response({"channel": name, "subscribers": subscribers})


async def main(host: str = "127.0.0.1", ws_port: int = 8765, http_port: int = 8080) -> None:
    ws_server = await serve(handler, host, ws_port)

    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/channels", channels_handler)
    app.router.add_get("/channels/{name}/subscribers", channel_subscribers_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, http_port)
    await site.start()

    try:
        await asyncio.Future()
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
