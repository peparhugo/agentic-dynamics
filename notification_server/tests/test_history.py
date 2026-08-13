"""Tests for the GET /history channel/time-range message history endpoint."""

import asyncio
import json
import urllib.request

import pytest
import websockets

from notification_server.server import NotificationServer


def ws_uri(srv: NotificationServer) -> str:
    return f"ws://localhost:{srv.bound_port}"


def history_url(srv: NotificationServer, **params) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"http://localhost:{srv.bound_port}/history?{query}"


async def recv_json(websocket) -> dict:
    return json.loads(await websocket.recv())


async def get_json(url: str) -> tuple:
    def _fetch():
        try:
            with urllib.request.urlopen(url) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    return await asyncio.to_thread(_fetch)


async def send_channel_broadcast(ws, channel: str, text: str) -> dict:
    await ws.send(json.dumps({"type": "broadcast", "payload": {"channel": channel, "text": text}}))
    return await recv_json(ws)


@pytest.mark.asyncio
async def test_history_requires_channel_param(server):
    status, body = await get_json(f"http://localhost:{server.bound_port}/history")
    assert status == 400
    assert "error" in body


@pytest.mark.asyncio
async def test_history_returns_messages_for_channel_only(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await send_channel_broadcast(ws, "alerts", "alert one")
        await send_channel_broadcast(ws, "chat", "chat one")
        await send_channel_broadcast(ws, "alerts", "alert two")

    status, body = await get_json(history_url(server, channel="alerts"))
    assert status == 200
    assert body["channel"] == "alerts"
    texts = [m["payload"]["text"] for m in body["messages"]]
    assert texts == ["alert one", "alert two"]


@pytest.mark.asyncio
async def test_history_is_chronological_ascending(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        for i in range(4):
            await send_channel_broadcast(ws, "alerts", f"msg {i}")

    status, body = await get_json(history_url(server, channel="alerts"))
    assert status == 200
    texts = [m["payload"]["text"] for m in body["messages"]]
    assert texts == ["msg 0", "msg 1", "msg 2", "msg 3"]


@pytest.mark.asyncio
async def test_history_excludes_direct_messages(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        await recv_json(ws1)
        welcome2 = await recv_json(ws2)
        target_id = welcome2["payload"]["client_id"]

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": target_id, "text": "psst"},
        }))
        await recv_json(ws2)

        await send_channel_broadcast(ws1, "alerts", "public alert")

    status, body = await get_json(history_url(server, channel="alerts"))
    assert status == 200
    assert len(body["messages"]) == 1
    assert body["messages"][0]["payload"]["text"] == "public alert"


@pytest.mark.asyncio
async def test_history_filters_by_since(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await send_channel_broadcast(ws, "alerts", "old message")

    status, body = await get_json(history_url(server, channel="alerts"))
    cutoff = body["messages"][0]["timestamp"]

    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await send_channel_broadcast(ws, "alerts", "new message")

    status, body = await get_json(history_url(server, channel="alerts", since=cutoff))
    assert status == 200
    texts = [m["payload"]["text"] for m in body["messages"]]
    assert "new message" in texts
    # `since` is inclusive of the cutoff timestamp itself
    assert "old message" in texts


@pytest.mark.asyncio
async def test_history_since_excludes_messages_strictly_before_it(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await send_channel_broadcast(ws, "alerts", "before")

    status, body = await get_json(history_url(server, channel="alerts"))
    before_ts = body["messages"][0]["timestamp"]

    # Advance well past "before"'s timestamp.
    from datetime import datetime, timedelta, timezone
    future = (datetime.fromisoformat(before_ts) + timedelta(days=1)).isoformat()

    status, body = await get_json(history_url(server, channel="alerts", since=future))
    assert status == 200
    assert body["messages"] == []


@pytest.mark.asyncio
async def test_history_invalid_since_returns_400(server):
    status, body = await get_json(history_url(server, channel="alerts", since="not-a-timestamp"))
    assert status == 400
    assert "error" in body


@pytest.mark.asyncio
async def test_history_pagination_has_more(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        for i in range(5):
            await send_channel_broadcast(ws, "alerts", f"msg {i}")

    status, body = await get_json(history_url(server, channel="alerts", limit=2))
    assert status == 200
    assert len(body["messages"]) == 2
    assert body["has_more"] is True
    assert [m["payload"]["text"] for m in body["messages"]] == ["msg 0", "msg 1"]

    status, body = await get_json(history_url(server, channel="alerts", limit=2, offset=4))
    assert status == 200
    assert len(body["messages"]) == 1
    assert body["has_more"] is False
    assert body["messages"][0]["payload"]["text"] == "msg 4"


@pytest.mark.asyncio
async def test_history_defaults_to_limit_50(server):
    status, body = await get_json(history_url(server, channel="alerts"))
    assert status == 200
    assert body["messages"] == []
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["has_more"] is False


@pytest.mark.asyncio
async def test_history_unknown_channel_returns_empty(server):
    status, body = await get_json(history_url(server, channel="ghost-channel"))
    assert status == 200
    assert body["messages"] == []
    assert body["has_more"] is False
