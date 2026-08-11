import asyncio
import json
import socket
import threading
import uuid
from datetime import datetime, timezone

from aiohttp import web
from websockets.sync.server import ServerConnection, ServerProtocol


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._lock = threading.Lock()

    def add(self, client_id, ws):
        with self._lock:
            self._clients[client_id] = ws

    def remove(self, client_id):
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id):
        with self._lock:
            return self._clients.get(client_id)

    def count(self):
        with self._lock:
            return len(self._clients)

    def all_items(self):
        with self._lock:
            return list(self._clients.items())

    def item_ids(self):
        with self._lock:
            return list(self._clients.keys())

    def clear(self):
        with self._lock:
            self._clients.clear()


class ChannelManager:
    def __init__(self):
        self._channels = {}
        self._lock = threading.Lock()

    def subscribe(self, client_id, channel):
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def unsubscribe(self, client_id, channel):
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def unsubscribe_all(self, client_id):
        with self._lock:
            for channel in list(self._channels.keys()):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_subscribers(self, channel):
        with self._lock:
            subscribers = self._channels.get(channel, set())
            return list(subscribers)

    def list_channels(self):
        with self._lock:
            return {name: len(subscribers) for name, subscribers in self._channels.items()}

    def clear(self):
        with self._lock:
            self._channels.clear()


_registry = ClientRegistry()
_channels = ChannelManager()
_send_lock = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type, payload, from_id=None):
    msg = {"type": msg_type, "payload": payload, "timestamp": now_iso()}
    if from_id:
        msg["from"] = from_id
    return json.dumps(msg)


def handle_client(conn):
    client_id = str(uuid.uuid4())
    protocol = ServerProtocol()
    ws = None
    try:
        ws = ServerConnection(conn, protocol)
        ws.handshake()
        _registry.add(client_id, ws)

        ws.send(make_message("system", {"client_id": client_id, "message": "Connected"}))

        for raw_message in ws:
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})

            if msg_type == "subscribe":
                channel = payload.get("channel")
                if channel:
                    _channels.subscribe(client_id, channel)

            elif msg_type == "unsubscribe":
                channel = payload.get("channel")
                if channel:
                    _channels.unsubscribe(client_id, channel)

            elif msg_type == "broadcast":
                msg = make_message("broadcast", payload, from_id=client_id)
                channel = data.get("channel")
                if channel:
                    subscriber_ids = _channels.get_subscribers(channel)
                    with _send_lock:
                        for cid in subscriber_ids:
                            cws = _registry.get(cid)
                            if cws:
                                try:
                                    cws.send(msg)
                                except Exception:
                                    _registry.remove(cid)
                else:
                    with _send_lock:
                        for cid, cws in _registry.all_items():
                            try:
                                cws.send(msg)
                            except Exception:
                                _registry.remove(cid)

            elif msg_type == "direct":
                target = payload.get("target")
                if target:
                    msg = make_message("direct", payload, from_id=client_id)
                    with _send_lock:
                        target_ws = _registry.get(target)
                        if target_ws:
                            try:
                                target_ws.send(msg)
                            except Exception:
                                _registry.remove(target)

    except Exception:
        pass
    finally:
        _channels.unsubscribe_all(client_id)
        _registry.remove(client_id)
        disc_msg = make_message("system", {"client_id": client_id, "message": "Disconnected"})
        with _send_lock:
            for cid, cws in _registry.all_items():
                try:
                    cws.send(disc_msg)
                except Exception:
                    _registry.remove(cid)
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


async def health_handler(request):
    return web.json_response({"clients": _registry.count()})


async def channels_handler(request):
    return web.json_response(_channels.list_channels())


async def channel_subscribers_handler(request):
    channel_name = request.match_info["name"]
    subscribers = _channels.get_subscribers(channel_name)
    return web.json_response(subscribers)


def run_ws_acceptor(host, port):
    sock = socket.create_server((host, port), reuse_port=True)
    sock.listen()

    def accept_loop():
        try:
            while True:
                conn, addr = sock.accept()
                thread = threading.Thread(target=handle_client, args=(conn,), daemon=True)
                thread.start()
        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

    accept_thread = threading.Thread(target=accept_loop, name="ws-acceptor", daemon=True)
    accept_thread.start()
    return accept_thread


def start_server(host="0.0.0.0", ws_port=8765, http_port=8080):
    ws_thread = run_ws_acceptor(host, ws_port)

    async def run_http():
        app = web.Application()
        app.router.add_get("/health", health_handler)
        app.router.add_get("/channels", channels_handler)
        app.router.add_get("/channels/{name}/subscribers", channel_subscribers_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, http_port)
        await site.start()
        await asyncio.Future()

    def run_http_thread():
        asyncio.run(run_http())

    http_thread = threading.Thread(target=run_http_thread, name="http-server", daemon=True)
    http_thread.start()

    return ws_thread, http_thread


if __name__ == "__main__":
    start_server()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
