import asyncio
import json
import threading
import urllib.request

import pytest
import websockets

import app

WS_URL = "ws://127.0.0.1"


@pytest.fixture
async def server():
    srv = await app.make_server()
    try:
        yield srv
    finally:
        srv["ws_server"].close()
        await srv["ws_server"].wait_closed()
        srv["httpd"].shutdown()
        srv["httpd"].server_close()


async def connect(port):
    return await websockets.connect(f"{WS_URL}:{port}")


async def recv_json(ws, timeout=5):
    raw = await asyncio.wait_for(ws.recv(), timeout)
    return json.loads(raw)


def http_health(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())


async def wait_for_count(registry, expected, timeout=5):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if registry.count == expected:
            return True
        await asyncio.sleep(0.05)
    return False


async def get_client_id(ws):
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    return msg["payload"]["client_id"]


# ── Message format ───────────────────────────────────────────────

def test_build_message_format():
    msg = app.build_message("broadcast", {"note": "hi"})
    assert set(msg) == {"type", "payload", "timestamp"}
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"note": "hi"}
    assert isinstance(msg["timestamp"], str)


def test_build_message_rejects_unknown_type():
    with pytest.raises(ValueError):
        app.build_message("nope", {})


def test_build_message_rejects_non_dict_payload():
    with pytest.raises(TypeError):
        app.build_message("system", ["not", "a", "dict"])


def test_registry_uses_threading_lock():
    registry = app.ClientRegistry()
    assert type(registry._lock) is type(threading.Lock())


# ── Connect / disconnect ─────────────────────────────────────────

async def test_connect_assigns_unique_id(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    a_id = await get_client_id(ws_a)
    b_id = await get_client_id(ws_b)
    assert a_id and b_id
    assert a_id != b_id
    await ws_a.close()
    await ws_b.close()


async def test_welcome_is_system_message(server):
    ws = await connect(server["ws_port"])
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert "client_id" in msg["payload"]
    assert "timestamp" in msg
    await ws.close()


async def test_disconnect_clean_removal(server):
    registry = server["registry"]
    ws = await connect(server["ws_port"])
    await get_client_id(ws)
    assert registry.count == 1
    await ws.close()
    assert await wait_for_count(registry, 0)


# ── Broadcast ────────────────────────────────────────────────────

async def test_broadcast_reaches_all_clients(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)

    await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    got_a = await recv_json(ws_a)
    got_b = await recv_json(ws_b)

    for got in (got_a, got_b):
        assert set(got) == {"type", "payload", "timestamp"}
        assert got["type"] == "broadcast"
        assert got["payload"] == {"text": "hello"}

    await ws_a.close()
    await ws_b.close()


async def test_broadcast_reaches_only_connected_after_disconnect(server):
    registry = server["registry"]
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)

    await ws_b.close()
    assert await wait_for_count(registry, 1)

    await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "still"}}))
    got_a = await recv_json(ws_a)
    assert got_a["type"] == "broadcast"
    assert got_a["payload"] == {"text": "still"}

    with pytest.raises((asyncio.TimeoutError, websockets.exceptions.ConnectionClosed)):
        await asyncio.wait_for(ws_a.recv(), 0.5)

    await ws_a.close()


# ── Direct ───────────────────────────────────────────────────────

async def test_direct_reaches_only_target(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    a_id = await get_client_id(ws_a)
    b_id = await get_client_id(ws_b)

    await ws_a.send(
        json.dumps({"type": "direct", "payload": {"to": b_id, "text": "psst"}})
    )
    got_b = await recv_json(ws_b)
    assert got_b["type"] == "direct"
    assert got_b["payload"]["to"] == b_id
    assert got_b["payload"]["text"] == "psst"

    with pytest.raises((asyncio.TimeoutError, websockets.exceptions.ConnectionClosed)):
        await asyncio.wait_for(ws_a.recv(), 0.5)

    await ws_a.close()
    await ws_b.close()


async def test_direct_unknown_target_reports_error(server):
    ws = await connect(server["ws_port"])
    await get_client_id(ws)

    await ws.send(
        json.dumps({"type": "direct", "payload": {"to": "does-not-exist", "text": "x"}})
    )
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert "no client" in msg["payload"]["error"]
    await ws.close()


# ── Malformed input ──────────────────────────────────────────────

async def test_unsupported_type_gets_error(server):
    ws = await connect(server["ws_port"])
    await get_client_id(ws)
    await ws.send(json.dumps({"type": "teleport", "payload": {}}))
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert "unsupported" in msg["payload"]["error"]
    await ws.close()


async def test_invalid_json_gets_error(server):
    ws = await connect(server["ws_port"])
    await get_client_id(ws)
    await ws.send("this is not json")
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert msg["payload"]["error"] == "invalid JSON"
    await ws.close()


# ── /health ──────────────────────────────────────────────────────

async def test_health_returns_connected_client_count(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)

    status, body = http_health(server["http_port"])
    assert status == 200
    assert body["status"] == "ok"
    assert body["clients"] == 2

    await ws_b.close()
    assert await wait_for_count(server["registry"], 1)
    _, body = http_health(server["http_port"])
    assert body["clients"] == 1

    await ws_a.close()
    assert await wait_for_count(server["registry"], 0)
    _, body = http_health(server["http_port"])
    assert body["clients"] == 0


def test_health_unknown_path_returns_404(server):
    # Uses a plain HTTP request against the health server via urllib.
    port = server["http_port"]
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
        raise AssertionError("expected HTTP 404")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404


# ── Thread safety ────────────────────────────────────────────────

def test_registry_thread_safety():
    registry = app.ClientRegistry()
    errors = []

    def worker():
        try:
            for _ in range(300):
                cid = registry.add("ws-stub")
                assert registry.get(cid) == "ws-stub"
                assert registry.count >= 1
                registry.remove(cid)
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert registry.count == 0
