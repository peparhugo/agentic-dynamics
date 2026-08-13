import asyncio
import json

import pytest
import pytest_asyncio
import websockets
from websockets.asyncio.client import connect

import notification_server as ns


@pytest_asyncio.fixture(autouse=True)
async def clean_registry():
    ns.registry = ns.ClientRegistry()
    yield
    ns.registry = ns.ClientRegistry()


@pytest_asyncio.fixture
async def server():
    async with ns.serve(ns.handler, "localhost", 0, process_request=ns.process_request) as srv:
        port = srv.sockets[0].getsockname()[1]
        yield f"ws://localhost:{port}"


async def recv_json(ws, msg_type=None):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(raw)
        if msg_type is None or data["type"] == msg_type:
            return data


@pytest.mark.asyncio
async def test_connect_assigns_unique_id(server):
    async with connect(server) as ws1, connect(server) as ws2:
        welcome1 = await recv_json(ws1, "system")
        welcome2 = await recv_json(ws2, "system")
        id1 = welcome1["payload"]["client_id"]
        id2 = welcome2["payload"]["client_id"]
        assert id1 != id2
        assert welcome1["type"] == "system"
        assert "timestamp" in welcome1


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    async with connect(server) as ws1, connect(server) as ws2, connect(server) as ws3:
        await recv_json(ws1, "system")
        await recv_json(ws2, "system")
        await recv_json(ws3, "system")

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello everyone"},
            "timestamp": "ignored-client-side",
        }))

        msg1 = await recv_json(ws1, "broadcast")
        msg2 = await recv_json(ws2, "broadcast")
        msg3 = await recv_json(ws3, "broadcast")

        for msg in (msg1, msg2, msg3):
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello everyone"
            assert "timestamp" in msg


@pytest.mark.asyncio
async def test_direct_message_reaches_only_target(server):
    async with connect(server) as ws1, connect(server) as ws2, connect(server) as ws3:
        welcome1 = await recv_json(ws1, "system")
        await recv_json(ws2, "system")
        welcome3 = await recv_json(ws3, "system")
        target_id = welcome3["payload"]["client_id"]

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": target_id, "text": "just for you"},
        }))

        msg3 = await recv_json(ws3, "direct")
        assert msg3["payload"]["text"] == "just for you"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_direct_message_unknown_target_gets_error(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": "does-not-exist", "text": "hi"},
        }))
        err = await recv_json(ws1, "system")
        assert "not connected" in err["payload"]["error"]


@pytest.mark.asyncio
async def test_unsupported_type_gets_error(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({"type": "bogus", "payload": {}}))
        err = await recv_json(ws1, "system")
        assert "unsupported type" in err["payload"]["error"]


@pytest.mark.asyncio
async def test_invalid_json_gets_error(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send("not json")
        err = await recv_json(ws1, "system")
        assert "invalid JSON" in err["payload"]["error"]


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        assert ns.registry.count() == 1

    for _ in range(50):
        if ns.registry.count() == 0:
            break
        await asyncio.sleep(0.05)
    assert ns.registry.count() == 0


@pytest.mark.asyncio
async def test_health_endpoint_reports_connected_count(server):
    ws_url = server
    http_url = "http://" + ws_url.split("://", 1)[1]

    async with connect(ws_url) as ws1:
        await recv_json(ws1, "system")
        async with connect(ws_url) as ws2:
            await recv_json(ws2, "system")

            reader, writer = await asyncio.open_connection(
                *ws_url.split("://", 1)[1].split(":")
            )
            writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            await writer.drain()
            raw = await reader.read()
            writer.close()

            header_blob, _, body = raw.partition(b"\r\n\r\n")
            assert b"200" in header_blob.splitlines()[0]
            data = json.loads(body.decode())
            assert data["connected_clients"] == 2


@pytest.mark.asyncio
async def test_registry_add_remove_and_snapshot():
    registry = ns.ClientRegistry()

    class FakeConn:
        pass

    c1, c2 = FakeConn(), FakeConn()
    id1 = registry.add(c1)
    id2 = registry.add(c2)
    assert id1 != id2
    assert registry.count() == 2
    assert dict(registry.snapshot()) == {id1: c1, id2: c2}

    registry.remove(id1)
    assert registry.count() == 1
    assert registry.get(id1) is None
    assert registry.get(id2) is c2
