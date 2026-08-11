import asyncio
import json
import os
import socket
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from aiohttp import web
from websockets.sync.server import ServerConnection, ServerProtocol

try:
    import redis as _redis_lib
except ImportError:
    _redis_lib = None

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "chat.db")
BROADCAST_CHANNEL = "chat:message"

_server_id = str(uuid.uuid4())


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

_redis_client = None
_redis_failed = False
_redis_init_lock = threading.Lock()
_redis_ready = threading.Event()
_db_lock = threading.Lock()


def _init_db():
    with _db_lock:
        conn = sqlite3.connect(DATABASE_URL)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()


def _save_message(channel, msg_type, payload, timestamp):
    with _db_lock:
        conn = sqlite3.connect(DATABASE_URL)
        conn.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (channel, msg_type, json.dumps(payload), timestamp),
        )
        conn.commit()
        conn.close()


def get_messages(limit=50, offset=0):
    with _db_lock:
        conn = sqlite3.connect(DATABASE_URL)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        conn.close()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["payload"] = json.loads(d["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
        result.append(d)
    return result


def _get_redis():
    global _redis_client, _redis_failed
    if _redis_lib is None:
        return None
    if _redis_failed:
        return None
    if _redis_client is not None:
        return _redis_client
    with _redis_init_lock:
        if _redis_client is not None:
            return _redis_client
        if _redis_failed:
            return None
        try:
            _redis_client = _redis_lib.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=0.5)
            _redis_client.ping()
        except Exception:
            _redis_failed = True
            return None
    return _redis_client


def _local_deliver(msg_type, payload, sender_id, channel):
    if msg_type == "broadcast":
        msg = make_message("broadcast", payload, from_id=sender_id)
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
            msg = make_message("direct", payload, from_id=sender_id)
            with _send_lock:
                target_ws = _registry.get(target)
                if target_ws:
                    try:
                        target_ws.send(msg)
                    except Exception:
                        _registry.remove(target)


def _redis_subscriber_loop():
    r = _get_redis()
    if r is None:
        _redis_ready.set()
        return
    try:
        pubsub = r.pubsub()
        pubsub.subscribe(BROADCAST_CHANNEL)
        _redis_ready.set()
        for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            if msg.get("channel") != BROADCAST_CHANNEL.encode() if isinstance(msg.get("channel"), bytes) else msg.get("channel") != BROADCAST_CHANNEL:
                continue
            try:
                data = json.loads(msg["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            sender_id = data.get("_sender_id")
            msg_type = data.get("type")
            payload = data.get("payload", {})
            from_id = data.get("from")
            channel = data.get("channel")

            if msg_type == "broadcast":
                wire_msg = make_message("broadcast", payload, from_id=from_id)
                if channel:
                    subscriber_ids = _channels.get_subscribers(channel)
                    with _send_lock:
                        for cid in subscriber_ids:
                            if cid == sender_id:
                                continue
                            cws = _registry.get(cid)
                            if cws:
                                try:
                                    cws.send(wire_msg)
                                except Exception:
                                    _registry.remove(cid)
                else:
                    with _send_lock:
                        for cid, cws in _registry.all_items():
                            if cid == sender_id:
                                continue
                            try:
                                cws.send(wire_msg)
                            except Exception:
                                _registry.remove(cid)
            elif msg_type == "direct":
                target = payload.get("target")
                if target:
                    wire_msg = make_message("direct", payload, from_id=from_id)
                    with _send_lock:
                        target_ws = _registry.get(target)
                        if target_ws:
                            try:
                                target_ws.send(wire_msg)
                            except Exception:
                                _registry.remove(target)
    except Exception:
        pass


def _start_redis_subscriber():
    t = threading.Thread(target=_redis_subscriber_loop, name="redis-subscriber", daemon=True)
    t.start()
    return t


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
    r = _get_redis()
    use_redis = r is not None and _redis_ready.is_set()

    if use_redis:
        try:
            r.hset("chat:clients", client_id, _server_id)
            r.sadd(f"chat:server:{_server_id}:clients", client_id)
        except Exception:
            use_redis = False

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
                    if use_redis:
                        try:
                            r.sadd(f"chat:channel:{_server_id}:{channel}", client_id)
                        except Exception:
                            pass

            elif msg_type == "unsubscribe":
                channel = payload.get("channel")
                if channel:
                    _channels.unsubscribe(client_id, channel)
                    if use_redis:
                        try:
                            r.srem(f"chat:channel:{_server_id}:{channel}", client_id)
                        except Exception:
                            pass

            elif msg_type in ("broadcast", "direct"):
                channel = data.get("channel")
                timestamp = now_iso()

                _save_message(channel, msg_type, payload, timestamp)

                if use_redis:
                    redis_msg = {
                        "type": msg_type,
                        "payload": payload,
                        "from": client_id,
                        "channel": channel,
                        "timestamp": timestamp,
                        "_sender_id": client_id,
                    }
                    try:
                        r.publish(BROADCAST_CHANNEL, json.dumps(redis_msg))
                    except Exception:
                        _local_deliver(msg_type, payload, client_id, channel)
                else:
                    _local_deliver(msg_type, payload, client_id, channel)

    except Exception:
        pass
    finally:
        _channels.unsubscribe_all(client_id)
        _registry.remove(client_id)

        if use_redis:
            try:
                r.hdel("chat:clients", client_id)
                r.srem(f"chat:server:{_server_id}:clients", client_id)
                for ch_name in _channels.list_channels():
                    r.srem(f"chat:channel:{_server_id}:{ch_name}", client_id)
            except Exception:
                pass

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


async def messages_handler(request):
    limit = int(request.query.get("limit", "50"))
    offset = int(request.query.get("offset", "0"))
    messages = get_messages(limit=limit, offset=offset)
    return web.json_response(messages)


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
    _init_db()
    _start_redis_subscriber()

    ws_thread = run_ws_acceptor(host, ws_port)

    async def run_http():
        app = web.Application()
        app.router.add_get("/health", health_handler)
        app.router.add_get("/channels", channels_handler)
        app.router.add_get("/channels/{name}/subscribers", channel_subscribers_handler)
        app.router.add_get("/messages", messages_handler)
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
