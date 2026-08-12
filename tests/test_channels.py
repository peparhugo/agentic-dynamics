"""Tests for channel-based subscriptions in the notification server."""

import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from server import NotificationServer


async def http_get(host: str, port: int, path: str) -> str:
    """Issue a minimal HTTP/1.1 GET and return the raw response text."""
    reader, writer = await asyncio.open_connection(host, port)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    writer.write(request.encode("ascii"))
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    return raw.decode("utf-8", "replace")


def parse_json(raw: str) -> dict:
    status_line, _, body = raw.partition("\r\n\r\n")
    return json.loads(body)


@pytest_asyncio.fixture
async def server():
    srv = NotificationServer(port=0)
    await srv.start()
    yield srv
    await srv.stop()


@pytest_asyncio.fixture
async def base_uri(server):
    return f"ws://{server.host}:{server.bound_port}"


async def recv_json(ws):
    return json.loads(await ws.recv())


async def subscribe(ws, channel):
    await ws.send(
        json.dumps({"type": "subscribe", "payload": {"channel": channel}})
    )
    return await recv_json(ws)


async def unsubscribe(ws, channel):
    await ws.send(
        json.dumps({"type": "unsubscribe", "payload": {"channel": channel}})
    )
    return await recv_json(ws)


@pytest.mark.asyncio
async def test_subscribe_confirms_and_tracks_subscription(server, base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        await subscribe(a, "alerts")
        await subscribe(b, "alerts")
        await subscribe(b, "chat")
        assert server.channels.subscribers("alerts") == {
            "client-1",
            "client-2",
        }
        assert server.channels.subscribers("chat") == {"client-2"}


@pytest.mark.asyncio
async def test_channel_message_only_reaches_subscribers(base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b, connect(
        base_uri
    ) as c:
        await recv_json(a)
        await recv_json(b)
        await recv_json(c)
        await subscribe(a, "alerts")
        await subscribe(b, "alerts")
        await subscribe(c, "chat")

        await a.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"message": "fire"},
                }
            )
        )
        msg_a = await recv_json(a)
        msg_b = await recv_json(b)
        assert msg_a["type"] == "broadcast"
        assert msg_a["channel"] == "alerts"
        assert msg_a["payload"]["message"] == "fire"
        assert msg_b["payload"]["message"] == "fire"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(c.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_server_broadcast_to_channel(server, base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        await subscribe(a, "alerts")
        await subscribe(b, "alerts")

        sent = await server.broadcast({"message": "hi"}, channel="alerts")
        assert sent == 2
        msg_a = await recv_json(a)
        msg_b = await recv_json(b)
        assert msg_a["channel"] == "alerts"
        assert msg_b["payload"] == {"message": "hi"}


@pytest.mark.asyncio
async def test_broadcast_without_channel_still_reaches_all(base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        await subscribe(a, "alerts")

        await a.send(json.dumps({"type": "broadcast", "payload": {"m": 1}}))
        msg_a = await recv_json(a)
        msg_b = await recv_json(b)
        assert "channel" not in msg_a
        assert msg_b["payload"] == {"m": 1}


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery(base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        await subscribe(a, "alerts")
        await subscribe(b, "alerts")
        await unsubscribe(a, "alerts")

        await a.send(
            json.dumps(
                {"type": "broadcast", "channel": "alerts", "payload": {"x": 1}}
            )
        )
        msg_b = await recv_json(b)
        assert msg_b["payload"] == {"x": 1}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(a.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_client_subscribes_to_multiple_channels(server, base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        await subscribe(a, "alerts")
        await subscribe(a, "system")
        await subscribe(b, "alerts")

        assert server.channels.subscribers("alerts") == {"client-1", "client-2"}
        assert server.channels.subscribers("system") == {"client-1"}


@pytest.mark.asyncio
async def test_disconnect_cleans_up_subscriptions(server, base_uri):
    async with connect(base_uri) as a:
        await recv_json(a)
        await subscribe(a, "alerts")
        assert server.channels.subscribers("alerts") == {"client-1"}
    await asyncio.sleep(0.1)
    assert server.channels.subscribers("alerts") == set()
    assert not server.channels.is_active("alerts")


@pytest.mark.asyncio
async def test_subscribe_requires_channel(server, base_uri):
    async with connect(base_uri) as a:
        await recv_json(a)
        await a.send(json.dumps({"type": "subscribe", "payload": {}}))
        error = await recv_json(a)
        assert error["type"] == "system"
        assert "channel" in error["payload"]["error"]


# ── REST endpoints ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_channels_endpoint_lists_active_channels(server, base_uri):
    http_host_port = f"{server.host}:{server.bound_port}"
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        await subscribe(a, "alerts")
        await subscribe(b, "alerts")
        await subscribe(b, "chat")

        raw = await http_get(*http_host_port.split(":"), "/channels")
        body = parse_json(raw)
        channels = body["channels"]
        assert channels == {"alerts": 2, "chat": 1}


@pytest.mark.asyncio
async def test_channels_endpoint_empty_when_no_subscriptions(server, base_uri):
    http_host_port = f"{server.host}:{server.bound_port}"
    raw = await http_get(*http_host_port.split(":"), "/channels")
    body = parse_json(raw)
    assert body["channels"] == {}


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint(server, base_uri):
    http_host_port = f"{server.host}:{server.bound_port}"
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        await subscribe(a, "alerts")
        await subscribe(b, "alerts")

        raw = await http_get(
            *http_host_port.split(":"), "/channels/alerts/subscribers"
        )
        body = parse_json(raw)
        assert body["channel"] == "alerts"
        assert body["subscribers"] == ["client-1", "client-2"]


@pytest.mark.asyncio
async def test_channel_subscribers_unknown_channel_returns_404(server, base_uri):
    http_host_port = f"{server.host}:{server.bound_port}"
    raw = await http_get(
        *http_host_port.split(":"), "/channels/nope/subscribers"
    )
    status_line, _, body = raw.partition("\r\n\r\n")
    assert status_line.split(" ")[1] == "404"
