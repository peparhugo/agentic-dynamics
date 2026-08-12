import asyncio

import aiohttp
import pytest

import app


@pytest.mark.asyncio
async def test_history_filters_by_channel_and_is_chronological(http_url, running_server):
    await running_server.broadcast({"c": "global"})
    await running_server.broadcast({"a": 1}, channel="alerts")
    await running_server.broadcast({"b": 2}, channel="alerts")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/history?channel=alerts") as response:
            assert response.status == 200
            body = await response.json()
            assert body["channel"] == "alerts"
            assert body["has_more"] is False
            messages = body["messages"]
            assert [m["payload"] for m in messages] == [{"a": 1}, {"b": 2}]
            for message in messages:
                assert message["channel"] == "alerts"
                assert message["type"] == "broadcast"
                assert set(message.keys()) == {"id", "channel", "type", "payload", "timestamp"}
            assert messages[0]["id"] < messages[1]["id"]


@pytest.mark.asyncio
async def test_history_since_filters_by_time_range(http_url, running_server):
    await running_server.broadcast({"first": True})
    await running_server.broadcast({"second": True})
    since = app.utcnow_iso()
    await running_server.broadcast({"third": True})

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/history?channel=global&since={since}") as response:
            assert response.status == 200
            body = await response.json()
            assert body["has_more"] is False
            assert [m["payload"] for m in body["messages"]] == [{"third": True}]


@pytest.mark.asyncio
async def test_history_since_accepts_z_suffix(http_url, running_server):
    await running_server.broadcast({"before": True})
    await running_server.broadcast({"after": True})
    since = "2000-01-01T00:00:00Z"

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/history?channel=global&since={since}") as response:
            assert response.status == 200
            body = await response.json()
            assert [m["payload"] for m in body["messages"]] == [{"before": True}, {"after": True}]


@pytest.mark.asyncio
async def test_history_pagination_has_more(http_url, running_server):
    for i in range(5):
        await running_server.broadcast({"i": i}, channel="alerts")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/history?channel=alerts&limit=2&offset=0") as response:
            assert response.status == 200
            body = await response.json()
            assert body["has_more"] is True
            assert body["limit"] == 2
            assert body["offset"] == 0
            assert [m["payload"] for m in body["messages"]] == [{"i": 0}, {"i": 1}]

        async with session.get(f"{http_url}/history?channel=alerts&limit=2&offset=2") as response:
            body = await response.json()
            assert body["has_more"] is True
            assert [m["payload"] for m in body["messages"]] == [{"i": 2}, {"i": 3}]

        async with session.get(f"{http_url}/history?channel=alerts&limit=2&offset=4") as response:
            body = await response.json()
            assert body["has_more"] is False
            assert [m["payload"] for m in body["messages"]] == [{"i": 4}]


@pytest.mark.asyncio
async def test_history_without_channel_returns_all_channels(http_url, running_server):
    await running_server.broadcast({"global": True})
    await running_server.broadcast({"ch": True}, channel="x")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/history") as response:
            assert response.status == 200
            body = await response.json()
            assert body["channel"] is None
            assert len(body["messages"]) == 2
            assert [m["payload"] for m in body["messages"]] == [{"global": True}, {"ch": True}]


@pytest.mark.asyncio
async def test_history_empty_channel_returns_empty_list(http_url, running_server):
    await running_server.broadcast({"nope": True}, channel="other")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/history?channel=missing") as response:
            assert response.status == 200
            body = await response.json()
            assert body["messages"] == []
            assert body["has_more"] is False


@pytest.mark.asyncio
async def test_history_persists_direct_and_system_messages(ws_url, http_url, running_server):
    import json
    import websockets

    from conftest import recv_message

    async with websockets.connect(ws_url) as ws:
        client_id = (await recv_message(ws))["payload"]["client_id"]
        await running_server.send_direct(client_id, {"note": "x"})
        await recv_message(ws)
        await running_server.broadcast({"alert": 1}, channel="alerts")
        await asyncio.sleep(0.1)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/history") as response:
            body = await response.json()
            types = {m["type"] for m in body["messages"]}
            assert "direct" in types
            assert "broadcast" in types
            direct = next(m for m in body["messages"] if m["type"] == "direct")
            assert direct["payload"] == {"note": "x"}
            assert direct["channel"] == "direct"
