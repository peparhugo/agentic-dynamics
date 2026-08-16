import asyncio
import json

import pytest
import websockets
from websockets.asyncio.client import connect

from notification_server import (
    Client,
    ClientRegistry,
    NotificationServer,
    create_server,
    make_message,
)


# ── Unit tests: ClientRegistry / make_message ─────────────────────

def test_registry_add_and_count():
    registry = ClientRegistry()
    registry.add(Client(client_id="a", connection=object()))
    registry.add(Client(client_id="b", connection=object()))
    assert registry.count() == 2


def test_registry_remove():
    registry = ClientRegistry()
    registry.add(Client(client_id="a", connection=object()))
    registry.remove("a")
    assert registry.count() == 0
    assert registry.get("a") is None


def test_registry_remove_missing_is_noop():
    registry = ClientRegistry()
    registry.remove("does-not-exist")
    assert registry.count() == 0


def test_registry_ids_are_unique_per_add():
    registry = ClientRegistry()
    ids = set()
    for i in range(50):
        cid = f"client-{i}"
        registry.add(Client(client_id=cid, connection=object()))
        ids.add(cid)
    assert registry.count() == 50
    assert len(ids) == 50


def test_make_message_valid_types():
    for t in ("broadcast", "direct", "system"):
        msg = make_message(t, {"foo": "bar"})
        assert msg["type"] == t
        assert msg["payload"] == {"foo": "bar"}
        assert "timestamp" in msg


def test_make_message_rejects_unsupported_type():
    with pytest.raises(ValueError):
        make_message("not-a-type", {})


# ── Integration tests: real server + real client connections ──────

@pytest.fixture
async def running_server():
    ws_server, state = create_server(host="127.0.0.1", port=0)
    server = await ws_server
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"ws://127.0.0.1:{port}", state
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_connect_assigns_unique_id(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "connected"
        assert "client_id" in msg["payload"]
        assert state.registry.count() == 1


@pytest.mark.asyncio
async def test_two_clients_get_different_ids(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
        raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
        id1 = json.loads(raw1)["payload"]["client_id"]
        id2 = json.loads(raw2)["payload"]["client_id"]
        assert id1 != id2
        assert state.registry.count() == 2


@pytest.mark.asyncio
async def test_disconnect_removes_client(running_server):
    uri, state = running_server
    ws = await connect(uri)
    await asyncio.wait_for(ws.recv(), timeout=5)
    assert state.registry.count() == 1
    await ws.close()
    await asyncio.sleep(0.2)
    assert state.registry.count() == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2, connect(uri) as ws3:
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await asyncio.wait_for(ws2.recv(), timeout=5)
        await asyncio.wait_for(ws3.recv(), timeout=5)

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello everyone"},
            "timestamp": "2026-08-16T00:00:00+00:00",
        }))

        for ws in (ws1, ws2, ws3):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello everyone"


@pytest.mark.asyncio
async def test_broadcast_skips_disconnected_clients(running_server):
    uri, state = running_server
    ws1 = await connect(uri)
    ws2 = await connect(uri)
    await asyncio.wait_for(ws1.recv(), timeout=5)
    await asyncio.wait_for(ws2.recv(), timeout=5)

    await ws2.close()
    await asyncio.sleep(0.2)
    assert state.registry.count() == 1

    sent = await state.broadcast({"text": "still here"})
    assert sent == 1

    raw = await asyncio.wait_for(ws1.recv(), timeout=5)
    msg = json.loads(raw)
    assert msg["payload"]["text"] == "still here"
    await ws1.close()


@pytest.mark.asyncio
async def test_direct_message_reaches_only_target(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
        target_id = json.loads(raw1)["payload"]["client_id"]
        await asyncio.wait_for(ws2.recv(), timeout=5)

        await ws2.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": target_id, "message": {"text": "psst"}},
        }))

        raw = await asyncio.wait_for(ws1.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "direct"
        assert msg["payload"]["text"] == "psst"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_invalid_json_gets_system_error(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send("not json{{{")
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]


@pytest.mark.asyncio
async def test_unsupported_message_type_gets_system_error(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "bogus", "payload": {}}))
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]


def _get_health(host_port: str) -> tuple[int, dict]:
    # http.client is blocking; the caller must run this off the event
    # loop (e.g. via asyncio.to_thread) so it doesn't stall the very
    # loop the server needs to accept the connection on.
    import http.client

    conn = http.client.HTTPConnection(host_port, timeout=5)
    try:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        body = json.loads(resp.read())
        return resp.status, body
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_health_endpoint_reports_client_count(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")

    status, body = await asyncio.to_thread(_get_health, host_port)
    assert status == 200
    assert body["connected_clients"] == 0

    async with connect(uri):
        await asyncio.sleep(0.1)
        status, body = await asyncio.to_thread(_get_health, host_port)
        assert status == 200
        assert body["connected_clients"] == 1
