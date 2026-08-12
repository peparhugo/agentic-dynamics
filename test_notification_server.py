"""Tests for the WebSocket notification server."""

import asyncio
import json
from datetime import datetime

import httpx
import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from registry import ClientRegistry
from server import NotificationServer, make_message


def ws_uri(server: NotificationServer) -> str:
    return f"ws://127.0.0.1:{server.port}"


def http_uri(server: NotificationServer) -> str:
    return f"http://127.0.0.1:{server.port}"


async def wait_for(predicate, timeout: float = 2.0) -> bool:
    """Poll ``predicate`` until it returns truthy or the timeout elapses."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.02)
    return False


@pytest_asyncio.fixture
async def server():
    srv = NotificationServer(port=0)
    await srv.start()
    yield srv
    await srv.stop()


# ── client registry unit tests ──────────────────────────────────────────


def test_registry_add_get_remove():
    reg = ClientRegistry()
    fake = object()
    reg.add("client-1", fake)
    assert reg.get("client-1") is fake
    assert reg.count() == 1
    assert reg.ids() == ["client-1"]
    assert reg.remove("client-1") is True
    assert reg.remove("client-1") is False
    assert reg.count() == 0
    assert reg.get("client-1") is None


def test_registry_snapshot_isolation():
    reg = ClientRegistry()
    reg.add("a", object())
    reg.add("b", object())
    snapshot = reg.items()
    reg.remove("a")
    assert len(snapshot) == 2
    assert len(reg.items()) == 1


# ── message format unit tests ───────────────────────────────────────────


def test_make_message_format():
    msg = make_message("system", {"foo": 1})
    assert set(msg.keys()) == {"type", "payload", "timestamp"}
    assert msg["type"] == "system"
    assert msg["payload"] == {"foo": 1}
    assert isinstance(msg["timestamp"], str)
    datetime.fromisoformat(msg["timestamp"])


# ── connection / id assignment ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_assigns_unique_id(server):
    async with connect(ws_uri(server)) as ws1:
        w1 = json.loads(await ws1.recv())
        async with connect(ws_uri(server)) as ws2:
            w2 = json.loads(await ws2.recv())

            assert w1["type"] == "system"
            assert w2["type"] == "system"

            id1 = w1["payload"]["client_id"]
            id2 = w2["payload"]["client_id"]
            assert isinstance(id1, str) and id1
            assert isinstance(id2, str) and id2
            assert id1 != id2


@pytest.mark.asyncio
async def test_connection_registered_in_registry(server):
    async with connect(ws_uri(server)) as ws:
        welcome = json.loads(await ws.recv())
        client_id = welcome["payload"]["client_id"]
        assert client_id in server.registry.ids()
        assert server.registry.count() == 1


# ── health endpoint ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_returns_zero_when_empty(server):
    async with httpx.AsyncClient() as http:
        r = await http.get(f"{http_uri(server)}/health")
        assert r.status_code == 200
        assert r.headers["Content-Type"] == "application/json"
        assert r.json() == {"connected_clients": 0}


@pytest.mark.asyncio
async def test_health_returns_connected_count(server):
    async with connect(ws_uri(server)) as ws1:
        await ws1.recv()
        async with connect(ws_uri(server)) as ws2:
            await ws2.recv()
            async with connect(ws_uri(server)) as ws3:
                await ws3.recv()
                async with httpx.AsyncClient() as http:
                    r = await http.get(f"{http_uri(server)}/health")
                    assert r.status_code == 200
                    assert r.json() == {"connected_clients": 3}


# ── broadcast ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    clients = []
    try:
        for _ in range(3):
            ws = await connect(ws_uri(server))
            await ws.recv()  # consume welcome
            clients.append(ws)

        server.broadcast({"text": "hello everyone"})

        for ws in clients:
            msg = json.loads(await ws.recv())
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"text": "hello everyone"}
            datetime.fromisoformat(msg["timestamp"])
    finally:
        for ws in clients:
            await ws.close()


@pytest.mark.asyncio
async def test_client_initiated_broadcast(server):
    async with connect(ws_uri(server)) as a:
        await a.recv()
        async with connect(ws_uri(server)) as b:
            await b.recv()

            await a.send(
                json.dumps({"type": "broadcast", "payload": {"from": "a"}})
            )

            msg = json.loads(await b.recv())
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"from": "a"}


# ── direct messaging ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(server):
    async with connect(ws_uri(server)) as a:
        wa = json.loads(await a.recv())
        async with connect(ws_uri(server)) as b:
            wb = json.loads(await b.recv())
            target = wa["payload"]["client_id"]

            sent = await server.direct(target, {"text": "secret"})
            assert sent is True

            msg_a = json.loads(await a.recv())
            assert msg_a["type"] == "direct"
            assert msg_a["payload"] == {"text": "secret"}

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(b.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_direct_to_unknown_client_returns_false(server):
    sent = await server.direct("does-not-exist", {"text": "nope"})
    assert sent is False


# ── disconnect cleanup ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    ws = await connect(ws_uri(server))
    await ws.recv()
    assert server.registry.count() == 1

    await ws.close()

    assert await wait_for(lambda: server.registry.count() == 0)
    async with httpx.AsyncClient() as http:
        r = await http.get(f"{http_uri(server)}/health")
        assert r.json() == {"connected_clients": 0}


@pytest.mark.asyncio
async def test_broadcast_skips_disconnected_client(server):
    ws1 = await connect(ws_uri(server))
    await ws1.recv()
    ws2 = await connect(ws_uri(server))
    await ws2.recv()

    await ws1.close()
    assert await wait_for(lambda: server.registry.count() == 1)

    server.broadcast({"text": "only survivors"})

    msg = json.loads(await ws2.recv())
    assert msg["payload"] == {"text": "only survivors"}
    await ws2.close()


@pytest.mark.asyncio
async def test_health_decreases_after_multiple_disconnects(server):
    clients = []
    try:
        for _ in range(3):
            ws = await connect(ws_uri(server))
            await ws.recv()
            clients.append(ws)

        await clients[0].close()
        assert await wait_for(lambda: server.registry.count() == 2)

        await clients[1].close()
        assert await wait_for(lambda: server.registry.count() == 1)

        async with httpx.AsyncClient() as http:
            r = await http.get(f"{http_uri(server)}/health")
            assert r.json() == {"connected_clients": 1}
    finally:
        for ws in clients:
            await ws.close()
