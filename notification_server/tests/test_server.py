import asyncio
import json
import urllib.request

import pytest
import pytest_asyncio
import websockets

from notification_server.server import NotificationServer


@pytest_asyncio.fixture
async def running_server(tmp_path):
    server = NotificationServer(
        host="localhost", port=0, storage_path=tmp_path / "events.jsonl"
    )
    await server.start()
    port = server._server.sockets[0].getsockname()[1]
    try:
        yield server, port
    finally:
        await server.stop()


async def connect(port):
    ws = await websockets.connect(f"ws://localhost:{port}")
    welcome = json.loads(await ws.recv())
    return ws, welcome


async def test_connect_assigns_unique_client_id(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, welcome2 = await connect(port)
    try:
        assert welcome1["type"] == "system"
        assert welcome1["payload"]["event"] == "connected"
        client_id1 = welcome1["payload"]["client_id"]
        client_id2 = welcome2["payload"]["client_id"]
        assert client_id1 != client_id2
        assert server.registry.count() == 2
    finally:
        await ws1.close()
        await ws2.close()


async def test_disconnect_removes_client(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    assert server.registry.count() == 1
    await ws.close()
    for _ in range(50):
        if server.registry.count() == 0:
            break
        await asyncio.sleep(0.05)
    assert server.registry.count() == 0


async def test_broadcast_reaches_all_connected_clients(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    try:
        await ws1.send(
            json.dumps({"type": "broadcast", "payload": {"text": "hello everyone"}})
        )
        msg1 = json.loads(await ws1.recv())
        msg2 = json.loads(await ws2.recv())
        assert msg1["type"] == "broadcast"
        assert msg1["payload"]["text"] == "hello everyone"
        assert msg2 == msg1
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_reaches_only_target(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, welcome2 = await connect(port)
    try:
        target_id = welcome2["payload"]["client_id"]
        await ws1.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": target_id, "content": {"text": "psst"}},
                }
            )
        )
        msg2 = json.loads(await ws2.recv())
        assert msg2["type"] == "direct"
        assert msg2["payload"]["content"] == {"text": "psst"}
        assert msg2["payload"]["sender_id"] == welcome1["payload"]["client_id"]

        # ws1 should not receive the direct message meant for ws2.
        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws1.recv(), timeout=0.2)
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_to_unknown_target_returns_error(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": "no-such-client", "content": {}},
                }
            )
        )
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_system_message_from_client_is_acknowledged(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "system", "payload": {"note": "ping"}}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "ack"
    finally:
        await ws.close()


async def test_invalid_json_returns_system_error(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send("not valid json")
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_health_endpoint_reports_connected_count(running_server):
    server, port = running_server

    def get_health():
        with urllib.request.urlopen(f"http://localhost:{port}/health") as resp:
            return resp.status, json.loads(resp.read())

    # urlopen is a blocking call; it must run off the event loop thread so
    # the server (running on that same loop) is free to accept and answer it.
    loop = asyncio.get_running_loop()

    status, body = await loop.run_in_executor(None, get_health)
    assert status == 200
    assert body == {"connected_clients": 0}

    ws, _ = await connect(port)
    try:
        status, body = await loop.run_in_executor(None, get_health)
        assert body == {"connected_clients": 1}
    finally:
        await ws.close()


async def test_events_are_persisted_to_flat_file(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "hi"}}))
    await ws.recv()
    await ws.close()
    for _ in range(50):
        events = server.storage.read_events()
        if any(e["event"] == "disconnect" for e in events):
            break
        await asyncio.sleep(0.05)

    events = server.storage.read_events()
    kinds = [e["event"] for e in events]
    assert "connect" in kinds
    assert "message" in kinds
    assert "disconnect" in kinds
