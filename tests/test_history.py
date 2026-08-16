import asyncio
import json
from datetime import datetime, timedelta, timezone

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


async def subscribe(ws, channel):
    await ws.send(json.dumps({"type": "subscribe", "channel": channel}))
    ack = json.loads(await ws.recv())
    assert ack["type"] == "system"
    assert ack["payload"]["event"] == "subscribed"


async def get_history(server, **params):
    url = f"http://{server.host}:{server.port}/history"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            return resp.status, await resp.json()


@pytest_asyncio.fixture
async def server(tmp_path):
    srv = NotificationServer(
        host="127.0.0.1", port=0, database_url=str(tmp_path / "messages.db")
    )
    await srv.start()
    yield srv
    await srv.stop()


@pytest.mark.asyncio
async def test_history_returns_channel_messages_chronologically(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await subscribe(ws_a, "alerts")

    for n in (1, 2, 3):
        await ws_b.send(
            json.dumps(
                {"type": "broadcast", "channel": "alerts", "payload": {"n": n}}
            )
        )
        await asyncio.wait_for(ws_a.recv(), timeout=5)

    status, body = await get_history(server, channel="alerts")
    assert status == 200
    assert body["has_more"] is False
    assert [m["payload"]["n"] for m in body["messages"]] == [1, 2, 3]
    assert [m["channel"] for m in body["messages"]] == ["alerts"] * 3

    timestamps = [m["timestamp"] for m in body["messages"]]
    assert timestamps == sorted(timestamps)

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_history_filters_by_channel(server):
    ws, client_id = await connect_client(server)

    await subscribe(ws, "alerts")
    await subscribe(ws, "other")

    await ws.send(
        json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"n": 1}})
    )
    await ws.recv()
    await ws.send(
        json.dumps({"type": "broadcast", "channel": "other", "payload": {"n": 2}})
    )
    await ws.recv()

    status, body = await get_history(server, channel="alerts")
    assert status == 200
    assert len(body["messages"]) == 1
    assert body["messages"][0]["payload"]["n"] == 1
    assert body["messages"][0]["channel"] == "alerts"

    await ws.close()


@pytest.mark.asyncio
async def test_history_pagination_has_more(server):
    ws, client_id = await connect_client(server)

    await subscribe(ws, "alerts")
    for n in range(5):
        await ws.send(
            json.dumps(
                {"type": "broadcast", "channel": "alerts", "payload": {"n": n}}
            )
        )
        await asyncio.wait_for(ws.recv(), timeout=5)

    status, body = await get_history(server, channel="alerts", limit=3)
    assert status == 200
    assert body["has_more"] is True
    assert [m["payload"]["n"] for m in body["messages"]] == [0, 1, 2]

    status, body = await get_history(server, channel="alerts", limit=10)
    assert body["has_more"] is False
    assert len(body["messages"]) == 5

    await ws.close()


@pytest.mark.asyncio
async def test_history_filters_by_since_timestamp(server):
    ws, client_id = await connect_client(server)

    await subscribe(ws, "alerts")
    await ws.send(
        json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"n": 1}})
    )
    await asyncio.wait_for(ws.recv(), timeout=5)

    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    status, body = await get_history(
        server, channel="alerts", since=future.isoformat()
    )
    assert status == 200
    assert body["messages"] == []

    past = datetime.now(timezone.utc) - timedelta(hours=1)
    status, body = await get_history(
        server, channel="alerts", since=past.isoformat()
    )
    assert status == 200
    assert len(body["messages"]) == 1
    assert body["messages"][0]["payload"]["n"] == 1

    await ws.close()


@pytest.mark.asyncio
async def test_history_without_channel_returns_all_messages(server):
    ws, client_id = await connect_client(server)

    await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
    await asyncio.wait_for(ws.recv(), timeout=5)

    status, body = await get_history(server)
    assert status == 200
    assert len(body["messages"]) == 1
    assert body["messages"][0]["payload"]["n"] == 1
    assert body["messages"][0]["channel"] is None

    await ws.close()
