import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

from aiohttp import web
from websockets.asyncio.server import serve


class ClientRegistry:
    def __init__(self):
        self._clients: dict[str, object] = {}
        self._lock = threading.Lock()

    def add(self, websocket) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def get_all(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())

    def get_ws(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)


class ChannelManager:
    def __init__(self):
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        with self._lock:
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_channels(self) -> dict[str, int]:
        with self._lock:
            return {name: len(subscribers) for name, subscribers in self._channels.items()}

    def get_subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return list(self._channels.get(channel, set()))

    def reset(self) -> None:
        with self._lock:
            self._channels.clear()


registry = ClientRegistry()
channel_manager = ChannelManager()


def make_message(msg_type: str, payload: dict) -> str:
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def broadcast_message(message: str) -> None:
    for client_id, ws in registry.get_all():
        try:
            await ws.send(message)
        except Exception:
            pass


async def send_to_clients(client_ids: list[str], message: str) -> None:
    for client_id in client_ids:
        ws = registry.get_ws(client_id)
        if ws is not None:
            try:
                await ws.send(message)
            except Exception:
                pass


async def ws_handler(websocket):
    client_id = registry.add(websocket)
    welcome = make_message("system", {
        "message": "connected",
        "client_id": client_id,
    })
    await websocket.send(welcome)

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")

            if msg_type == "subscribe":
                channel = data.get("channel", "")
                if channel:
                    channel_manager.subscribe(client_id, channel)
                    ack = make_message("subscribe", {
                        "channel": channel,
                        "client_id": client_id,
                        "status": "subscribed",
                    })
                    await websocket.send(ack)
            elif msg_type == "unsubscribe":
                channel = data.get("channel", "")
                if channel:
                    channel_manager.unsubscribe(client_id, channel)
                    ack = make_message("unsubscribe", {
                        "channel": channel,
                        "client_id": client_id,
                        "status": "unsubscribed",
                    })
                    await websocket.send(ack)
            else:
                payload = data.get("payload", {})
                channel = data.get("channel")

                outbound = make_message(msg_type, payload)
                if channel:
                    subscribers = channel_manager.get_subscribers(channel)
                    await send_to_clients(subscribers, outbound)
                else:
                    await broadcast_message(outbound)
    finally:
        registry.remove(client_id)
        channel_manager.unsubscribe_all(client_id)


async def health(request):
    return web.json_response({"clients": registry.count()})


async def channels_list(request):
    return web.json_response(channel_manager.get_channels())


async def channel_subscribers(request):
    name = request.match_info.get("name", "")
    subscribers = channel_manager.get_subscribers(name)
    return web.json_response({"channel": name, "subscribers": subscribers})


async def main():
    ws_server = await serve(
        ws_handler,
        "127.0.0.1",
        8765,
    )

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/channels", channels_list)
    app.router.add_get("/channels/{name}/subscribers", channel_subscribers)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8766)
    await site.start()

    try:
        await asyncio.Future()
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
