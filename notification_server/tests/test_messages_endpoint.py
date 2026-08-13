import asyncio
import json
import urllib.request

import pytest_asyncio
import websockets

from notification_server.server import NotificationServer


@pytest_asyncio.fixture
async def running_server(tmp_path):
    server = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'messages.db'}",
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


def get_json(port, path):
    with urllib.request.urlopen(f"http://localhost:{port}{path}") as resp:
        return resp.status, json.loads(resp.read())


async def test_broadcast_message_is_persisted_to_sqlite(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "hi there"}}))
        await ws.recv()
    finally:
        await ws.close()

    stored = server.messages.list_messages()
    assert len(stored) == 1
    assert stored[0]["type"] == "broadcast"
    assert stored[0]["payload"]["text"] == "hi there"


async def test_messages_endpoint_returns_persisted_history(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        for i in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
            await ws.recv()
    finally:
        await ws.close()

    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(None, get_json, port, "/messages")
    assert status == 200
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert [m["payload"]["n"] for m in body["messages"]] == [2, 1, 0]


async def test_messages_endpoint_honors_limit_and_offset(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        for i in range(5):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
            await ws.recv()
    finally:
        await ws.close()

    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, get_json, port, "/messages?limit=2&offset=1"
    )
    assert status == 200
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert [m["payload"]["n"] for m in body["messages"]] == [3, 2]


async def test_messages_endpoint_empty_when_no_messages_sent(running_server):
    server, port = running_server
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(None, get_json, port, "/messages")
    assert status == 200
    assert body["messages"] == []


async def test_direct_and_system_messages_are_also_persisted(running_server):
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
        await ws2.recv()
        await ws1.send(json.dumps({"type": "system", "payload": {"note": "ping"}}))
        await ws1.recv()
    finally:
        await ws1.close()
        await ws2.close()

    stored_types = {m["type"] for m in server.messages.list_messages()}
    assert stored_types == {"direct", "system"}
