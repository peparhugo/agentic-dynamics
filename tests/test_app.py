import asyncio

import httpx
import pytest
import pytest_asyncio
import websockets

from app import create_server, decode_message, encode_message


@pytest_asyncio.fixture
async def server():
    app, serve_coro = create_server("127.0.0.1", 0)
    srv = await serve_coro
    port = srv.sockets[0].getsockname()[1]
    yield app, port
    srv.close()
    await srv.wait_closed()


async def connect_client(port):
    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
    hello = decode_message(await ws.recv())
    return ws, hello


async def get_health(port):
    async with httpx.AsyncClient() as client:
        return await client.get(f"http://127.0.0.1:{port}/health")


async def test_health_initial_zero(server):
    _, port = server
    resp = await get_health(port)
    assert resp.status_code == 200
    assert resp.json() == {"connected_clients": 0}


async def test_connect_assigns_unique_id(server):
    _, port = server
    ws1, hello1 = await connect_client(port)
    ws2, hello2 = await connect_client(port)
    assert hello1["type"] == "system"
    assert hello1["payload"]["event"] == "connected"
    assert hello2["type"] == "system"
    assert hello2["payload"]["event"] == "connected"
    assert hello1["payload"]["id"] != hello2["payload"]["id"]
    await ws1.close()
    await ws2.close()


async def test_health_reflects_clients(server):
    _, port = server
    ws1, _ = await connect_client(port)
    ws2, _ = await connect_client(port)
    resp = await get_health(port)
    assert resp.json() == {"connected_clients": 2}
    await ws1.close()
    await ws2.close()


async def test_broadcast_reaches_all(server):
    _, port = server
    ws1, _ = await connect_client(port)
    ws2, _ = await connect_client(port)
    await ws1.send(
        encode_message(
            {
                "type": "broadcast",
                "payload": {"text": "hello"},
                "timestamp": "2024-01-01T00:00:00+00:00",
            }
        )
    )
    r1 = decode_message(await asyncio.wait_for(ws1.recv(), timeout=5))
    r2 = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
    assert r1["type"] == "broadcast"
    assert r1["payload"]["text"] == "hello"
    assert r2["type"] == "broadcast"
    assert r2["payload"]["text"] == "hello"
    await ws1.close()
    await ws2.close()


async def test_direct_reaches_target_only(server):
    _, port = server
    ws1, _ = await connect_client(port)
    ws2, hello2 = await connect_client(port)
    target_id = hello2["payload"]["id"]
    await ws1.send(
        encode_message(
            {"type": "direct", "payload": {"to": target_id, "text": "psst"}}
        )
    )
    r2 = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
    assert r2["type"] == "direct"
    assert r2["payload"]["text"] == "psst"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws1.recv(), timeout=0.5)
    await ws1.close()
    await ws2.close()


async def test_disconnect_removes_client(server):
    _, port = server
    ws1, hello1 = await connect_client(port)
    ws2, _ = await connect_client(port)
    assert (await get_health(port)).json() == {"connected_clients": 2}
    await ws1.close()
    d = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
    assert d["type"] == "system"
    assert d["payload"]["event"] == "disconnected"
    assert d["payload"]["id"] == hello1["payload"]["id"]
    assert (await get_health(port)).json() == {"connected_clients": 1}
    await ws2.close()
