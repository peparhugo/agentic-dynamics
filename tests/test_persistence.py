import asyncio
import json

import aiohttp
import pytest
import pytest_asyncio
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
async def plain_server(tmp_path):
    db = str(tmp_path / "messages.db")
    srv = NotificationServer(
        host="127.0.0.1", port=0, database_url=db
    )
    await srv.start()
    yield srv
    await srv.stop()


@pytest.mark.asyncio
async def test_message_persisted_without_redis(plain_server):
    ws, client_id = await connect_client(plain_server)

    await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    await asyncio.wait_for(ws.recv(), timeout=5)

    async with aiohttp.ClientSession() as session:
        async with session.get(plain_server.messages_url) as resp:
            assert resp.status == 200
            body = await resp.json()

    assert len(body["messages"]) == 1
    message = body["messages"][0]
    assert message["type"] == "broadcast"
    assert message["payload"] == {"text": "hello"}
    assert message["channel"] is None

    await ws.close()


@pytest.mark.asyncio
async def test_channel_message_persisted_with_channel(plain_server):
    ws_a, id_a = await connect_client(plain_server)

    await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await drain_system(ws_a)

    await ws_a.send(
        json.dumps(
            {"type": "broadcast", "channel": "alerts", "payload": {"text": "x"}}
        )
    )
    await asyncio.wait_for(ws_a.recv(), timeout=5)

    async with aiohttp.ClientSession() as session:
        async with session.get(plain_server.messages_url) as resp:
            body = await resp.json()

    assert body["messages"][0]["channel"] == "alerts"

    await ws_a.close()
