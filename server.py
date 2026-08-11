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

from broker import RedisBroker
from store import MessageStore


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

    def get_client_subscriptions(self, client_id: str) -> list[str]:
        with self._lock:
            return list(self._subscriptions.get(client_id, set()))

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


registry = ClientRegistry()
broker = RedisBroker()
store = MessageStore()


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


async def _publish_and_persist(msg_type: str, payload: dict, exclude_id: str | None = None,
                               channel: str | None = None, target: str | None = None) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    redis_msg = json.dumps({
        "_msg_id": str(uuid.uuid4()),
        "_origin_server": broker.server_id,
        "_exclude_id": exclude_id,
        "type": msg_type,
        "channel": channel,
        "target": target,
        "payload": payload,
        "timestamp": timestamp,
    })
    await broker.publish("messages", redis_msg)
    await store.save_message(channel, msg_type, payload, timestamp)


async def _deliver_from_redis(channel_name: str, data: str) -> None:
    message = json.loads(data)
    origin_server = message.get("_origin_server")

    if origin_server == broker.server_id:
        return

    msg_type = message["type"]
    channel = message.get("channel")
    target = message.get("target")
    payload = message["payload"]
    timestamp = message["timestamp"]
    exclude_id = message.get("_exclude_id")

    msg_str = json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": timestamp,
    })

    await store.save_message(channel, msg_type, payload, timestamp)

    clients = registry.get_all()

    if target:
        ws = clients.get(target)
        if ws:
            try:
                await ws.send(msg_str)
            except ConnectionClosed:
                registry.remove(target)
    elif channel:
        target_ids = registry.get_subscribers(channel)
        for cid in target_ids:
            if cid == exclude_id:
                continue
            ws = clients.get(cid)
            if ws is None:
                continue
            try:
                await ws.send(msg_str)
            except ConnectionClosed:
                registry.remove(cid)
    else:
        for cid, ws in clients.items():
            if cid == exclude_id:
                continue
            try:
                await ws.send(msg_str)
            except ConnectionClosed:
                registry.remove(cid)


async def handler(websocket: ServerConnection) -> None:
    client_id = str(uuid.uuid4())
    registry.add(client_id, websocket)

    try:
        asyncio.create_task(broker.register_client(client_id, broker.server_id))

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
                asyncio.create_task(_publish_and_persist(
                    "broadcast", payload, exclude_id=client_id, channel=channel))

            elif msg_type == "direct":
                target_id = data.get("target")
                if target_id:
                    target_ws = registry.get(target_id)
                    if target_ws:
                        try:
                            await target_ws.send(_make_message("direct", payload))
                        except ConnectionClosed:
                            registry.remove(target_id)
                    asyncio.create_task(_publish_and_persist(
                        "direct", payload, target=target_id))

            elif msg_type == "subscribe":
                ch = data.get("channel")
                if ch:
                    registry.subscribe(client_id, ch)
                    channels = registry.get_client_subscriptions(client_id)
                    asyncio.create_task(broker.set_client_subscriptions(client_id, channels))

            elif msg_type == "unsubscribe":
                ch = data.get("channel")
                if ch:
                    registry.unsubscribe(client_id, ch)
                    channels = registry.get_client_subscriptions(client_id)
                    asyncio.create_task(broker.set_client_subscriptions(client_id, channels))

    finally:
        registry.remove(client_id)
        asyncio.create_task(broker.deregister_client(client_id))
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


async def messages_handler(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", 50))
    offset = int(request.query.get("offset", 0))
    messages = await store.get_messages(limit, offset)
    return web.json_response({"messages": messages})


async def main(host: str = "127.0.0.1", ws_port: int = 8765, http_port: int = 8080) -> None:
    await broker.connect()
    await store.connect()
    await broker.subscribe("messages")

    ws_server = await serve(handler, host, ws_port)

    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/channels", channels_handler)
    app.router.add_get("/channels/{name}/subscribers", channel_subscribers_handler)
    app.router.add_get("/messages", messages_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, http_port)
    await site.start()

    listen_task = asyncio.create_task(broker.listen(_deliver_from_redis))

    try:
        await asyncio.Future()
    finally:
        listen_task.cancel()
        try:
            await listen_task
        except (asyncio.CancelledError, Exception):
            pass
        ws_server.close()
        await ws_server.wait_closed()
        await runner.cleanup()
        await broker.close()
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
