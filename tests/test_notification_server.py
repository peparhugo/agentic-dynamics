import asyncio
import json

import aiohttp
import pytest
from websockets.asyncio.client import connect


async def drain_system(ws):
    msg = json.loads(await ws.recv())
    assert msg["type"] == "system"
    return msg


async def connect_client(server):
    ws = await connect(server.ws_url)
    msg = await drain_system(ws)
    assert msg["payload"]["event"] == "connected"
    return ws, msg["payload"]["client_id"]


async def get_client_count(server):
    async with aiohttp.ClientSession() as session:
        async with session.get(server.health_url) as resp:
            body = await resp.json()
            return body["clients"]


async def wait_for_client_count(server, expected):
    async def poll():
        while await get_client_count(server) != expected:
            await asyncio.sleep(0.01)

    await asyncio.wait_for(poll(), timeout=5)


@pytest.mark.asyncio
async def test_client_gets_unique_id(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    assert id_a != id_b
    assert server.client_count == 2
    assert server.has_client(id_a)
    assert server.has_client(id_b)
    assert set(server.client_ids()) == {id_a, id_b}

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

    for ws in (ws_a, ws_b):
        msg = json.loads(await ws.recv())
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "hello"}
        assert isinstance(msg["timestamp"], str)
        assert msg["timestamp"]

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_direct_message_routed_to_target(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await ws_a.send(
        json.dumps(
            {"type": "direct", "payload": {"target": id_b, "text": "ping"}}
        )
    )

    msg = json.loads(await ws_b.recv())
    assert msg["type"] == "direct"
    assert msg["payload"]["target"] == id_b
    assert msg["payload"]["sender"] == id_a
    assert msg["payload"]["text"] == "ping"

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_direct_message_to_unknown_target_errors(server):
    ws_a, id_a = await connect_client(server)

    await ws_a.send(
        json.dumps(
            {"type": "direct", "payload": {"target": "no-such-client", "text": "x"}}
        )
    )

    msg = json.loads(await ws_a.recv())
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"

    await ws_a.close()


@pytest.mark.asyncio
async def test_disconnect_removes_client_and_notifies(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)
    assert server.client_count == 2

    await ws_a.close()

    msg = json.loads(await ws_b.recv())
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "disconnected"
    assert msg["payload"]["client_id"] == id_a

    assert server.client_count == 1
    assert not server.has_client(id_a)
    assert server.has_client(id_b)

    await ws_b.close()


@pytest.mark.asyncio
async def test_health_reports_client_count(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    assert await get_client_count(server) == 2

    await ws_a.close()
    await ws_b.close()

    await wait_for_client_count(server, 0)


@pytest.mark.asyncio
async def test_invalid_json_gets_error(server):
    ws, client_id = await connect_client(server)

    await ws.send("this is not json")

    msg = json.loads(await ws.recv())
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"

    await ws.close()


@pytest.mark.asyncio
async def test_message_has_required_fields(server):
    ws, client_id = await connect_client(server)

    await ws.send(json.dumps({"type": "broadcast", "payload": {}}))

    msg = json.loads(await ws.recv())
    assert set(msg.keys()) == {"type", "payload", "timestamp"}
    assert msg["type"] in ("broadcast", "direct", "system")
    assert isinstance(msg["payload"], dict)
    assert isinstance(msg["timestamp"], str)

    await ws.close()
