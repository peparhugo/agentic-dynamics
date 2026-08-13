"""Tests for per-client rate limiting on inbound messages."""

import asyncio
import json

import pytest
import websockets

from notification_server.server import NotificationServer


def ws_uri(srv: NotificationServer) -> str:
    return f"ws://localhost:{srv.bound_port}"


async def recv_json(websocket) -> dict:
    return json.loads(await websocket.recv())


async def send_broadcast(ws, text: str) -> None:
    await ws.send(json.dumps({"type": "broadcast", "payload": {"text": text}}))


@pytest.mark.asyncio
async def test_messages_within_limit_are_not_rate_limited(make_server):
    srv = await make_server(rate_limit=5)
    async with websockets.connect(ws_uri(srv)) as ws:
        await recv_json(ws)
        for i in range(5):
            await send_broadcast(ws, f"msg {i}")
            reply = await recv_json(ws)
            assert reply["type"] == "broadcast"
            assert reply["payload"]["text"] == f"msg {i}"


@pytest.mark.asyncio
async def test_exceeding_limit_returns_error_instead_of_dropping_connection(make_server):
    srv = await make_server(rate_limit=3)
    async with websockets.connect(ws_uri(srv)) as ws:
        await recv_json(ws)
        for i in range(3):
            await send_broadcast(ws, f"msg {i}")
            await recv_json(ws)

        # The 4th message within the window is rejected with an error --
        # the connection itself must stay open and usable.
        await send_broadcast(ws, "one too many")
        reply = await recv_json(ws)
        assert reply["type"] == "system"
        assert "rate limit" in reply["payload"]["error"].lower()

        # Connection survives the rejection; a fresh ping/pong-style
        # round trip (subscribe) still works.
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        ack = await recv_json(ws)
        assert ack["type"] == "system"


@pytest.mark.asyncio
async def test_rate_limited_message_is_not_processed(make_server):
    """The rejected message must not be broadcast/persisted -- it's refused
    outright, not merely delayed."""
    srv = await make_server(rate_limit=1)
    async with websockets.connect(ws_uri(srv)) as ws1, websockets.connect(ws_uri(srv)) as ws2:
        await recv_json(ws1)
        await recv_json(ws2)

        await send_broadcast(ws1, "first")
        await recv_json(ws1)
        await recv_json(ws2)

        await send_broadcast(ws1, "second - should be blocked")
        error = await recv_json(ws1)
        assert error["type"] == "system"
        assert "error" in error["payload"]

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_rate_limit_is_tracked_per_client(make_server):
    srv = await make_server(rate_limit=1)
    async with websockets.connect(ws_uri(srv)) as ws1, websockets.connect(ws_uri(srv)) as ws2:
        await recv_json(ws1)
        await recv_json(ws2)

        await send_broadcast(ws1, "from client 1")
        await recv_json(ws1)
        await recv_json(ws2)

        # client 1 is now over budget, but client 2 has used none of its own
        await send_broadcast(ws2, "from client 2")
        reply1 = await recv_json(ws1)
        reply2 = await recv_json(ws2)
        assert reply1["payload"]["text"] == "from client 2"
        assert reply2["payload"]["text"] == "from client 2"


@pytest.mark.asyncio
async def test_rate_limit_defaults_to_100(make_server):
    srv = await make_server()
    assert srv.rate_limit == 100


@pytest.mark.asyncio
async def test_rate_limit_configurable_via_constructor(make_server):
    srv = await make_server(rate_limit=7)
    assert srv.rate_limit == 7


@pytest.mark.asyncio
async def test_rate_limit_configurable_via_env_var(make_server, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "42")
    srv = await make_server()
    assert srv.rate_limit == 42
