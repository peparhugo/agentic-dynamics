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

    def clear(self):
        with self._lock:
            self._clients.clear()


_registry = ClientRegistry()
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

            if msg_type == "broadcast":
                msg = make_message("broadcast", payload, from_id=client_id)
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
