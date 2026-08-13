import asyncio
import json

import pytest
import websockets

from notification_server.ws_server import NotificationServer


@pytest.fixture
async def running_server():
    server_wrapper = NotificationServer()
    ws_server = await server_wrapper.serve("localhost", 0)
    port = ws_server.sockets[0].getsockname()[1]
    yield server_wrapper, f"ws://localhost:{port}"
    ws_server.close()
    await ws_server.wait_closed()


async def test_connect_assigns_unique_client_id(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
        msg1 = json.loads(await ws1.recv())
        msg2 = json.loads(await ws2.recv())
        assert msg1["type"] == "system"
        assert msg1["payload"]["event"] == "connected"
        id1 = msg1["payload"]["client_id"]
        id2 = msg2["payload"]["client_id"]
        assert id1 != id2
        assert server.registry.count() == 2


async def test_broadcast_reaches_all_clients(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
        await ws1.recv()
        await ws2.recv()
        await ws1.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "payload": {"text": "hello everyone"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )
        got1 = json.loads(await ws1.recv())
        got2 = json.loads(await ws2.recv())
        assert got1["type"] == "broadcast"
        assert got1["payload"]["text"] == "hello everyone"
        assert got2["payload"]["text"] == "hello everyone"


async def test_direct_message_reaches_only_target(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2, websockets.connect(
        uri
    ) as ws3:
        await ws1.recv()
        await ws2.recv()
        m3 = json.loads(await ws3.recv())
        target_id = m3["payload"]["client_id"]

        await ws1.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": target_id, "text": "psst"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )

        got3 = json.loads(await ws3.recv())
        assert got3["type"] == "direct"
        assert got3["payload"]["text"] == "psst"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.2)


async def test_direct_message_to_unknown_target_gets_error(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws1:
        await ws1.recv()
        await ws1.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": "does-not-exist", "text": "hi"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )
        err = json.loads(await ws1.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_disconnect_removes_client(running_server):
    server, uri = running_server
    ws = await websockets.connect(uri)
    await ws.recv()
    assert server.registry.count() == 1
    await ws.close()
    await asyncio.sleep(0.2)
    assert server.registry.count() == 0


async def test_invalid_json_gets_error_response(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws:
        await ws.recv()
        await ws.send("not json")
        err = json.loads(await ws.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_unsupported_type_gets_error_response(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "bogus", "payload": {}, "timestamp": "x"}))
        err = json.loads(await ws.recv())
        assert err["payload"]["event"] == "error"


async def test_client_sending_system_type_is_rejected(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "system", "payload": {"event": "x"}, "timestamp": "x"}))
        err = json.loads(await ws.recv())
        assert err["type"] == "system"
        assert "reserved" in err["payload"]["message"]


async def test_health_count_reflects_multiple_connect_and_disconnect(running_server):
    server, uri = running_server
    ws_a = await websockets.connect(uri)
    await ws_a.recv()
    ws_b = await websockets.connect(uri)
    await ws_b.recv()
    assert server.registry.count() == 2
    await ws_a.close()
    await asyncio.sleep(0.2)
    assert server.registry.count() == 1
    await ws_b.close()
    await asyncio.sleep(0.2)
    assert server.registry.count() == 0
