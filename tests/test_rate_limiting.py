import asyncio
import json

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis, FakeServer
from websockets.asyncio.client import connect

from notification_server import NotificationServer


async def drain_system(ws):
    msg = json.loads(await ws.recv())
    assert msg["type"] == "system"
    return msg


async def connect_client(server):
    ws = await connect(server.ws_url)
    msg = await drain_system(ws)
    assert msg["payload"]["event"] == "connected"
    return ws, msg["payload"]["client_id"]


@pytest_asyncio.fixture
async def limited_server(tmp_path):
    srv = NotificationServer(
        host="127.0.0.1",
        port=0,
        database_url=str(tmp_path / "messages.db"),
        rate_limit=3,
    )
    await srv.start()
    yield srv
    await srv.stop()


@pytest_asyncio.fixture
async def redis_limited_server(tmp_path):
    shared = FakeServer()
    redis = FakeAsyncRedis(server=shared, decode_responses=True)
    srv = NotificationServer(
        host="127.0.0.1",
        port=0,
        redis=redis,
        database_url=str(tmp_path / "messages.db"),
        rate_limit=3,
    )
    await srv.start()
    yield srv
    await srv.stop()
    await redis.aclose()


@pytest.mark.asyncio
async def test_rate_limit_blocks_messages_after_threshold(limited_server):
    ws, client_id = await connect_client(limited_server)

    for n in range(3):
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "broadcast"

    await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"
    assert "rate limit" in msg["payload"]["message"]

    await ws.close()


@pytest.mark.asyncio
async def test_rate_limit_is_enforced_per_client(limited_server):
    for _ in range(3):
        assert await limited_server._check_rate_limit("client-a") is True
    assert await limited_server._check_rate_limit("client-a") is False
    assert await limited_server._check_rate_limit("client-b") is True


@pytest.mark.asyncio
async def test_rate_limit_uses_redis_counters(redis_limited_server):
    ws, client_id = await connect_client(redis_limited_server)

    for n in range(3):
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "broadcast"

    await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    assert msg["type"] == "system"
    assert "rate limit" in msg["payload"]["message"]

    await ws.close()


@pytest.mark.asyncio
async def test_rate_limit_zero_disables_limiting(tmp_path):
    srv = NotificationServer(
        host="127.0.0.1",
        port=0,
        database_url=str(tmp_path / "messages.db"),
        rate_limit=0,
    )
    await srv.start()
    try:
        ws, client_id = await connect_client(srv)
        for n in range(5):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "broadcast"
        await ws.close()
    finally:
        await srv.stop()
