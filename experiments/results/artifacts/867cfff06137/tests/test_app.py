import asyncio
import json
from urllib.parse import quote

import pytest
import pytest_asyncio
import websockets
import fakeredis.aioredis

import app
from app import NotificationServer


async def health(port: int) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


async def get_json(port: int, path: str) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest_asyncio.fixture
async def server(unused_tcp_port_factory):
    instance = NotificationServer(
        websocket_port=unused_tcp_port_factory(), health_port=unused_tcp_port_factory()
    )
    await instance.start()
    yield instance
    await instance.stop()


@pytest.mark.asyncio
async def test_connect_assigns_id_and_health_count(server):
    async with websockets.connect(f"ws://127.0.0.1:{server.websocket_port}") as client:
        message = json.loads(await client.recv())
        assert message["type"] == "system"
        assert "client_id" in message["payload"]
        assert server.client_count == 1
        assert (await health(server.health_port))["clients"] == 1
    await asyncio.sleep(0)
    assert server.client_count == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    first = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    second = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    await first.recv()
    await second.recv()
    await server.broadcast({"text": "hello"})
    messages = [json.loads(await client.recv()) for client in (first, second)]
    assert all(message["type"] == "broadcast" for message in messages)
    assert all(message["payload"] == {"text": "hello"} for message in messages)
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_channel_broadcast_only_reaches_subscribers_and_lists_them(server):
    alerts = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    system = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    alerts_id = json.loads(await alerts.recv())["payload"]["client_id"]
    await system.recv()

    await alerts.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await asyncio.sleep(0.05)
    await server.broadcast({"channel": "alerts", "text": "warning"})
    message = json.loads(await alerts.recv())
    assert message["channel"] == "alerts"
    assert message["payload"]["text"] == "warning"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(system.recv(), timeout=0.05)

    assert (await get_json(server.health_port, "/channels")) == {"channels": {"alerts": 1}}
    subscribers = await get_json(server.health_port, "/channels/alerts/subscribers")
    assert subscribers == {"channel": "alerts", "subscribers": [alerts_id]}
    await alerts.close()
    await system.close()


@pytest.mark.asyncio
async def test_subscribe_multiple_channels_and_unsubscribe(server):
    client = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    await client.recv()
    for channel in ("alerts", "chat"):
        await client.send(json.dumps({"type": "subscribe", "channel": channel, "payload": {}}))
    await asyncio.sleep(0.05)

    await server.broadcast({"channel": "chat", "text": "hello"})
    assert json.loads(await client.recv())["payload"]["text"] == "hello"
    await client.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "chat"}}))
    await asyncio.sleep(0.05)
    await server.broadcast({"channel": "chat", "text": "ignored"})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client.recv(), timeout=0.05)
    await client.close()


@pytest.mark.asyncio
async def test_messages_endpoint_returns_persisted_history(server):
    await server.broadcast({"text": "first"}, "events")
    await server.broadcast({"text": "second"})

    messages = await get_json(server.health_port, "/messages?limit=1&offset=0")
    assert len(messages) == 1
    assert messages[0]["type"] == "broadcast"
    assert messages[0]["payload"] == {"text": "second"}
    assert messages[0]["channel"] is None

    messages = await get_json(server.health_port, "/messages?limit=10&offset=1")
    assert messages[0]["payload"] == {"text": "first"}
    assert messages[0]["channel"] == "events"


@pytest.mark.asyncio
async def test_redis_backbone_delivers_between_server_instances(unused_tcp_port_factory, monkeypatch):
    fake_server = fakeredis.FakeServer()

    def fake_from_url(_url, decode_responses=True):
        return fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=decode_responses)

    monkeypatch.setattr(app.redis, "from_url", fake_from_url)
    first = NotificationServer(
        websocket_port=unused_tcp_port_factory(), health_port=unused_tcp_port_factory(),
        redis_url="redis://fake", database_url=":memory:"
    )
    second = NotificationServer(
        websocket_port=unused_tcp_port_factory(), health_port=unused_tcp_port_factory(),
        redis_url="redis://fake", database_url=":memory:"
    )
    await first.start()
    await second.start()
    try:
        client = await websockets.connect(f"ws://127.0.0.1:{second.websocket_port}")
        await client.recv()
        await client.send(json.dumps({"type": "subscribe", "channel": "shared", "payload": {}}))
        await asyncio.sleep(0.05)
        await first.broadcast({"text": "from another instance"}, "shared")
        message = json.loads(await asyncio.wait_for(client.recv(), timeout=1))
        assert message["payload"] == {"text": "from another instance"}
        await client.close()
    finally:
        await first.stop()
        await second.stop()


@pytest.mark.asyncio
async def test_rate_limit_returns_error(monkeypatch, unused_tcp_port_factory):
    monkeypatch.setenv("RATE_LIMIT", "1")
    instance = NotificationServer(
        websocket_port=unused_tcp_port_factory(), health_port=unused_tcp_port_factory()
    )
    await instance.start()
    try:
        client = await websockets.connect(f"ws://127.0.0.1:{instance.websocket_port}")
        await client.recv()
        await client.send(json.dumps({"type": "subscribe", "channel": "one", "payload": {}}))
        await client.send(json.dumps({"type": "subscribe", "channel": "two", "payload": {}}))
        response = json.loads(await client.recv())
        assert response["payload"]["error"] == "rate limit exceeded"
        await client.close()
    finally:
        await instance.stop()


@pytest.mark.asyncio
async def test_history_filters_channel_since_and_paginates(server):
    await server.broadcast({"text": "first"}, "events")
    first_timestamp = server._message_history(1, 0)[0]["timestamp"]
    await server.broadcast({"text": "second"}, "events")
    await server.broadcast({"text": "other"}, "other")

    result = await get_json(
        server.health_port, f"/history?channel=events&since={quote(first_timestamp)}&limit=1"
    )
    assert [message["payload"]["text"] for message in result["messages"]] == ["second"]
    assert result["has_more"] is False
