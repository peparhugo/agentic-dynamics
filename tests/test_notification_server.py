"""Tests for the WebSocket notification server."""

import asyncio
import json
import urllib.request

import pytest
import websockets

from notification_server import ClientRegistry, NotificationServer, make_message


def parse(raw) -> dict:
    return json.loads(raw)


async def fetch_health(url: str) -> int:
    def _get() -> dict:
        with urllib.request.urlopen(url + "/health", timeout=5) as resp:
            return json.loads(resp.read())

    return (await asyncio.to_thread(_get))["connected_clients"]


async def wait_health(server: NotificationServer, expected: int, timeout=3.0):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while True:
        count = await fetch_health(server.http_url)
        if count == expected:
            return count
        if loop.time() > deadline:
            raise AssertionError(
                f"health never reached {expected} (last value {count})"
            )
        await asyncio.sleep(0.05)


@pytest.fixture
async def server():
    srv = await NotificationServer().start()
    yield srv
    await srv.stop()


@pytest.fixture
async def client(server):
    ws = await websockets.connect(server.ws_url)
    hello = parse(await ws.recv())
    yield ws, hello["payload"]["client_id"]
    await ws.close()


# ── Message format ─────────────────────────────────────────────────

def test_make_message_format():
    msg = make_message("system", {"x": 1})
    assert set(msg) == {"type", "payload", "timestamp"}
    assert isinstance(msg["type"], str)
    assert isinstance(msg["payload"], dict)
    assert isinstance(msg["timestamp"], str)
    assert msg["payload"] == {"x": 1}


# ── Registry ───────────────────────────────────────────────────────

def test_registry_lifecycle():
    reg = ClientRegistry()
    a, b = object(), object()
    id_a = reg.add(a)
    id_b = reg.add(b)
    assert id_a != id_b
    assert reg.count() == 2
    assert reg.get(id_a) is a
    assert reg.get(id_b) is b
    reg.remove(id_a)
    assert reg.count() == 1
    assert reg.get(id_a) is None
    reg.remove(id_a)  # idempotent
    assert reg.count() == 1
    assert reg.connected_ids() == [id_b]


# ── Connect / assign unique IDs ────────────────────────────────────

async def test_unique_ids_on_connect(server):
    async with websockets.connect(server.ws_url) as a:
        async with websockets.connect(server.ws_url) as b:
            hello_a = parse(await a.recv())
            hello_b = parse(await b.recv())
            assert hello_a["type"] == "system"
            assert hello_b["type"] == "system"
            assert hello_a["payload"]["event"] == "connected"
            assert hello_a["payload"]["client_id"] != hello_b["payload"]["client_id"]
            assert server.registry.count() == 2


async def test_concurrent_connects_get_unique_ids(server):
    async def connect_one():
        async with websockets.connect(server.ws_url) as ws:
            hello = parse(await ws.recv())
            return hello["payload"]["client_id"]

    ids = await asyncio.gather(*[connect_one() for _ in range(25)])
    assert len(ids) == 25
    assert len(set(ids)) == 25


# ── Health endpoint ────────────────────────────────────────────────

async def test_health_counts_connected_clients(server):
    assert await fetch_health(server.http_url) == 0

    ws_a = await websockets.connect(server.ws_url)
    await ws_a.recv()
    ws_b = await websockets.connect(server.ws_url)
    await ws_b.recv()
    assert await fetch_health(server.http_url) == 2

    await ws_b.close()
    await wait_health(server, 1)

    await ws_a.close()
    await wait_health(server, 0)


async def test_health_unknown_path_returns_404(server):
    try:
        urllib.request.urlopen(server.http_url + "/nope", timeout=5)
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    else:
        raise AssertionError("expected HTTPError for unknown path")


# ── Broadcast ──────────────────────────────────────────────────────

async def test_broadcast_reaches_all_clients(server):
    clients = []
    ids = []
    for _ in range(3):
        ws = await websockets.connect(server.ws_url)
        clients.append(ws)
        ids.append(parse(await ws.recv())["payload"]["client_id"])

    await clients[0].send(
        json.dumps(make_message("broadcast", {"text": "hello everyone"}))
    )

    for ws in clients:
        msg = parse(await asyncio.wait_for(ws.recv(), timeout=3))
        assert msg["type"] == "broadcast"
        assert msg["payload"]["text"] == "hello everyone"
        assert msg["payload"]["from"] == ids[0]
        assert isinstance(msg["timestamp"], str)

    for ws in clients:
        await ws.close()


# ── Direct ─────────────────────────────────────────────────────────

async def test_direct_reaches_only_target(client, server):
    sender, sender_id = client
    async with websockets.connect(server.ws_url) as other:
        other_id = parse(await other.recv())["payload"]["client_id"]

        await sender.send(
            json.dumps(make_message("direct", {"to": other_id, "data": {"note": "hi"}}))
        )
        msg = parse(await asyncio.wait_for(other.recv(), timeout=3))
        assert msg["type"] == "direct"
        assert msg["payload"]["from"] == sender_id
        assert msg["payload"]["to"] == other_id
        assert msg["payload"]["data"] == {"note": "hi"}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.2)


async def test_direct_unknown_target_returns_error(client):
    sender, _ = client
    await sender.send(json.dumps(make_message("direct", {"to": "nope", "data": {}})))
    msg = parse(await asyncio.wait_for(sender.recv(), timeout=3))
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"


async def test_direct_missing_target_returns_error(client):
    sender, _ = client
    await sender.send(json.dumps(make_message("direct", {"data": {}})))
    msg = parse(await asyncio.wait_for(sender.recv(), timeout=3))
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"


# ── System / errors ────────────────────────────────────────────────

async def test_client_system_message_gets_ack(client):
    sender, sender_id = client
    await sender.send(json.dumps(make_message("system", {"hello": True})))
    msg = parse(await asyncio.wait_for(sender.recv(), timeout=3))
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "ack"
    assert msg["payload"]["from"] == sender_id


async def test_unsupported_message_type_returns_error(client):
    sender, _ = client
    await sender.send(json.dumps({"type": "teleport", "payload": {}, "timestamp": "t"}))
    msg = parse(await asyncio.wait_for(sender.recv(), timeout=3))
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"
    assert "teleport" in msg["payload"]["error"]


async def test_invalid_json_returns_error(client):
    sender, _ = client
    await sender.send(b"this is definitely not json {")
    msg = parse(await asyncio.wait_for(sender.recv(), timeout=3))
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"


# ── Disconnect ─────────────────────────────────────────────────────

async def test_disconnect_removes_client(server):
    ws = await websockets.connect(server.ws_url)
    await ws.recv()
    assert server.registry.count() == 1
    await ws.close()
    await wait_health(server, 0)
    assert server.registry.count() == 0
