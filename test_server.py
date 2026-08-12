import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from unittest import mock

import fakeredis.aioredis
import pytest
import pytest_asyncio
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from server import channels, message_store, registry, start

WS_HOST = "127.0.0.1"
HTTP_HOST = "127.0.0.1"


def _fake_redis_from_url(url, **kwargs):
    return fakeredis.aioredis.FakeRedis()


@pytest_asyncio.fixture
async def server(tmp_path):
    db_path = str(tmp_path / "messages.db")
    ws_server, http_server, subscriber_task, cleanup_task = await start(
        WS_HOST, 0, HTTP_HOST, 0, database_url=db_path,
    )
    ws_port = ws_server.sockets[0].getsockname()[1]
    http_port = http_server.sockets[0].getsockname()[1]
    yield ws_port, http_port
    ws_server.close()
    await ws_server.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    subscriber_task.cancel()
    cleanup_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    registry.clear()
    channels.clear()
    message_store.clear()


@pytest_asyncio.fixture
async def server_with_redis(tmp_path):
    db_path = str(tmp_path / "messages_redis.db")
    with mock.patch("server.redis.from_url", _fake_redis_from_url):
        ws_server, http_server, subscriber_task, cleanup_task = await start(
            WS_HOST, 0, HTTP_HOST, 0,
            redis_url="redis://localhost:6379",
            database_url=db_path,
        )
    ws_port = ws_server.sockets[0].getsockname()[1]
    http_port = http_server.sockets[0].getsockname()[1]
    yield ws_port, http_port
    ws_server.close()
    await ws_server.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    subscriber_task.cancel()
    cleanup_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    registry.clear()
    channels.clear()
    message_store.clear()


@pytest.mark.asyncio
async def test_connect_and_welcome(server):
    ws_port, _ = server
    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=2)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert "client_id" in msg["payload"]
        assert "timestamp" in msg


@pytest.mark.asyncio
async def test_health_no_clients(server):
    _, http_port = server
    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /health HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert data["clients_connected"] == 0


@pytest.mark.asyncio
async def test_health_with_clients(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1:
        await ws1.recv()
        async with connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
            await ws2.recv()

            reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
            request = f"GET /health HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            raw = await asyncio.wait_for(reader.read(), timeout=2)
            writer.close()
            await writer.wait_closed()

            body = raw.split(b"\r\n\r\n", 1)[1]
            data = json.loads(body.decode())
            assert data["clients_connected"] == 2


@pytest.mark.asyncio
async def test_broadcast(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        welcome1 = json.loads(await ws1.recv())
        welcome2 = json.loads(await ws2.recv())
        assert welcome1["type"] == "system"
        assert welcome2["type"] == "system"

        payload = {"message": "hello everyone"}
        await ws1.send(json.dumps({"type": "broadcast", "payload": payload}))

        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))

        assert msg1["type"] == "broadcast"
        assert msg1["payload"] == payload
        assert "timestamp" in msg1

        assert msg2["type"] == "broadcast"
        assert msg2["payload"] == payload
        assert "timestamp" in msg2


@pytest.mark.asyncio
async def test_direct_message(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        welcome1 = json.loads(await ws1.recv())
        welcome2 = json.loads(await ws2.recv())
        client2_id = welcome2["payload"]["client_id"]

        payload = {"target": client2_id, "message": "secret"}
        await ws1.send(json.dumps({"type": "direct", "payload": payload}))

        msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
        assert msg["type"] == "direct"
        assert msg["payload"]["message"] == "secret"
        assert msg["payload"]["target"] == client2_id

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_direct_to_nonexistent(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        welcome = json.loads(await ws.recv())

        payload = {"target": "nonexistent-id", "message": "ghost"}
        await ws.send(json.dumps({"type": "direct", "payload": payload}))

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1:
        await ws1.recv()
        async with connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
            await ws2.recv()
            async with connect(f"ws://{WS_HOST}:{ws_port}") as ws3:
                await ws3.recv()

            await asyncio.sleep(0.1)

            reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
            request = f"GET /health HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            raw = await asyncio.wait_for(reader.read(), timeout=2)
            writer.close()
            await writer.wait_closed()

            body = raw.split(b"\r\n\r\n", 1)[1]
            data = json.loads(body.decode())
            assert data["clients_connected"] == 2


@pytest.mark.asyncio
async def test_disconnected_client_not_broadcasted(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws3:

        await ws1.recv()
        await ws2.recv()
        await ws3.recv()

        await ws2.close()

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"test": 1}}))
        await asyncio.wait_for(ws1.recv(), timeout=2)
        await asyncio.wait_for(ws3.recv(), timeout=2)

        with pytest.raises(ConnectionClosed):
            await asyncio.wait_for(ws2.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_invalid_json_ignored(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        await ws1.send("not json at all")
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"msg": "after bad"}}))

        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
        assert msg1["payload"] == {"msg": "after bad"}

        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
        assert msg2["payload"] == {"msg": "after bad"}


@pytest.mark.asyncio
async def test_unknown_message_type_ignored(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "unknown_type", "payload": {}}))

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_multiple_broadcasts(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        for i in range(3):
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"seq": i}}))
            m1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
            m2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert m1["payload"]["seq"] == i
            assert m2["payload"]["seq"] == i


@pytest.mark.asyncio
async def test_broadcast_with_empty_payload(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "broadcast", "payload": {}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {}


@pytest.mark.asyncio
async def test_subscribe_to_channel(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
        request = f"GET /channels HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=2)
        writer.close()
        await writer.wait_closed()

        body = raw.split(b"\r\n\r\n", 1)[1]
        data = json.loads(body.decode())
        assert data["alerts"] == 1


@pytest.mark.asyncio
async def test_unsubscribe_from_channel(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
        request = f"GET /channels HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=2)
        writer.close()
        await writer.wait_closed()

        body = raw.split(b"\r\n\r\n", 1)[1]
        data = json.loads(body.decode())
        assert "alerts" not in data


@pytest.mark.asyncio
async def test_channel_message_delivery(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        payload = {"message": "alert!"}
        await ws2.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": payload}))

        msg = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
        assert msg["type"] == "broadcast"
        assert msg["payload"] == payload


@pytest.mark.asyncio
async def test_channel_message_not_received_by_nonsubscribers(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        await ws2.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"test": 1}}))
        await asyncio.wait_for(ws1.recv(), timeout=2)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_multiple_channels(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "system"}}))
        await asyncio.sleep(0.1)

        reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
        request = f"GET /channels HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=2)
        writer.close()
        await writer.wait_closed()

        body = raw.split(b"\r\n\r\n", 1)[1]
        data = json.loads(body.decode())
        assert data["alerts"] == 1
        assert data["system"] == 1


@pytest.mark.asyncio
async def test_channel_broadcast_without_channel_still_works(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        payload = {"message": "global"}
        await ws1.send(json.dumps({"type": "broadcast", "payload": payload}))

        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
        assert msg1["payload"] == payload
        assert msg2["payload"] == payload


@pytest.mark.asyncio
async def test_disconnect_removes_from_channels(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /channels HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert "alerts" not in data


@pytest.mark.asyncio
async def test_rest_channels_endpoint(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
        await ws1.recv()
        await ws2.recv()
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await asyncio.sleep(0.1)

        reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
        request = f"GET /channels HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=2)
        writer.close()
        await writer.wait_closed()

        body = raw.split(b"\r\n\r\n", 1)[1]
        data = json.loads(body.decode())
        assert data["alerts"] == 2
        assert data["chat"] == 1


@pytest.mark.asyncio
async def test_rest_channel_subscribers_endpoint(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
        welcome1 = json.loads(await ws1.recv())
        welcome2 = json.loads(await ws2.recv())
        client1_id = welcome1["payload"]["client_id"]
        client2_id = welcome2["payload"]["client_id"]

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
        request = f"GET /channels/alerts/subscribers HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=2)
        writer.close()
        await writer.wait_closed()

        body = raw.split(b"\r\n\r\n", 1)[1]
        data = json.loads(body.decode())
        assert client1_id in data
        assert client2_id in data
        assert len(data) == 2


# --- Persistence tests ---


@pytest.mark.asyncio
async def test_messages_persisted_in_sqlite(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()

        payload = {"message": "hello"}
        await ws.send(json.dumps({"type": "broadcast", "payload": payload}))
        await asyncio.wait_for(ws.recv(), timeout=2)

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /messages?limit=10&offset=0 HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    messages = json.loads(body.decode())
    assert len(messages) >= 1
    assert messages[0]["type"] == "broadcast"
    assert messages[0]["payload"] == payload


@pytest.mark.asyncio
async def test_messages_endpoint_with_limit_offset(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()

        for i in range(5):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"seq": i}}))
            await asyncio.wait_for(ws.recv(), timeout=2)

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /messages?limit=3&offset=0 HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    messages = json.loads(body.decode())
    assert len(messages) == 3

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /messages?limit=3&offset=2 HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    messages = json.loads(body.decode())
    assert len(messages) == 3


@pytest.mark.asyncio
async def test_messages_persist_direct_messages(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        welcome1 = json.loads(await ws1.recv())
        welcome2 = json.loads(await ws2.recv())
        client2_id = welcome2["payload"]["client_id"]

        payload = {"target": client2_id, "message": "direct msg"}
        await ws1.send(json.dumps({"type": "direct", "payload": payload}))
        await asyncio.wait_for(ws2.recv(), timeout=2)

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /messages HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    messages = json.loads(body.decode())
    assert len(messages) >= 1
    found = False
    for m in messages:
        if m["type"] == "direct" and m["payload"].get("message") == "direct msg":
            found = True
            break
    assert found, "Direct message not found in /messages"


@pytest.mark.asyncio
async def test_messages_endpoint_defaults(server):
    ws_port, http_port = server

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /messages HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    messages = json.loads(body.decode())
    assert isinstance(messages, list)


@pytest.mark.asyncio
async def test_channel_field_in_persisted_message(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        await ws2.send(json.dumps({"type": "broadcast", "channel": "alerts",
                                    "payload": {"alert": "test"}}))
        await asyncio.wait_for(ws1.recv(), timeout=2)

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /messages HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    messages = json.loads(body.decode())
    alert_msgs = [m for m in messages if m["payload"].get("alert") == "test"]
    assert len(alert_msgs) == 1
    assert alert_msgs[0]["channel"] == "alerts"


# --- Redis integration tests ---


@pytest.mark.asyncio
async def test_redis_pubsub_broadcast_delivery(server_with_redis):
    """Broadcasts go through Redis and are delivered to subscribers."""
    ws_port, _ = server_with_redis

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        payload = {"message": "redis test"}
        await ws1.send(json.dumps({"type": "broadcast", "payload": payload}))

        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))

        assert msg1["type"] == "broadcast"
        assert msg1["payload"] == payload
        assert msg2["type"] == "broadcast"
        assert msg2["payload"] == payload


@pytest.mark.asyncio
async def test_redis_pubsub_channel_broadcast(server_with_redis):
    """Channel broadcasts go through Redis pub/sub."""
    ws_port, _ = server_with_redis

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "notifications"}}))
        await asyncio.sleep(0.1)

        payload = {"alert": "important"}
        await ws2.send(json.dumps({
            "type": "broadcast",
            "channel": "notifications",
            "payload": payload,
        }))

        msg = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
        assert msg["type"] == "broadcast"
        assert msg["payload"] == payload


@pytest.mark.asyncio
async def test_redis_pubsub_direct_message(server_with_redis):
    """Direct messages go through Redis pub/sub."""
    ws_port, _ = server_with_redis

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        welcome1 = json.loads(await ws1.recv())
        welcome2 = json.loads(await ws2.recv())
        client2_id = welcome2["payload"]["client_id"]

        payload = {"target": client2_id, "message": "redis direct"}
        await ws1.send(json.dumps({"type": "direct", "payload": payload}))

        msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
        assert msg["type"] == "direct"
        assert msg["payload"]["message"] == "redis direct"


@pytest.mark.asyncio
async def test_redis_client_state_survives_connection(server_with_redis):
    """Client subscribe state is stored in Redis."""
    from server import redis_client as _redis_client
    ws_port, _ = server_with_redis

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()

        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "persistent"}}))
        await asyncio.sleep(0.2)

        subscribers = await _redis_client.smembers("channel:persistent:subscribers")
        assert len(subscribers) > 0


@pytest.mark.asyncio
async def test_redis_unsubscribe_clears_state(server_with_redis):
    """Unsubscribe removes client from Redis channel set."""
    from server import redis_client as _redis_client
    ws_port, _ = server_with_redis

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()

        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "temp"}}))
        await asyncio.sleep(0.1)

        subscribers = await _redis_client.smembers("channel:temp:subscribers")
        assert len(subscribers) == 1

        await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "temp"}}))
        await asyncio.sleep(0.1)

        subscribers = await _redis_client.smembers("channel:temp:subscribers")
        assert len(subscribers) == 0


@pytest.mark.asyncio
async def test_redis_disconnect_clears_client_state(server_with_redis):
    """Disconnect removes client state from Redis."""
    from server import redis_client as _redis_client
    ws_port, _ = server_with_redis

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "discon"}}))
        await asyncio.sleep(0.1)

        exists = await _redis_client.exists("client:test")
        client_keys = [k async for k in _redis_client.scan_iter("client:*")]
        assert len(client_keys) > 0

    await asyncio.sleep(0.1)
    client_keys = [k async for k in _redis_client.scan_iter("client:*")]
    assert len(client_keys) == 0


@pytest.mark.asyncio
async def test_messages_persistence_with_redis(server_with_redis):
    """Messages are persisted in SQLite even with Redis enabled."""
    ws_port, http_port = server_with_redis

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()

        for i in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
            await asyncio.wait_for(ws.recv(), timeout=2)

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /messages?limit=10 HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    messages = json.loads(body.decode())
    assert len(messages) >= 3


@pytest.mark.asyncio
async def test_redis_no_duplicate_delivery(server_with_redis):
    """Messages delivered directly should not be double-delivered via Redis subscriber."""
    ws_port, _ = server_with_redis

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()

        await ws.send(json.dumps({"type": "broadcast", "payload": {"single": True}}))
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert first["payload"] == {"single": True}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=0.5)


# --- Rate limiting tests ---


@pytest.mark.asyncio
async def test_rate_limit_exceeded(tmp_path):
    """Client receives error after exceeding rate limit."""
    db_path = str(tmp_path / "messages_rl.db")
    ws_server, http_server, subscriber_task, cleanup_task = await start(
        WS_HOST, 0, HTTP_HOST, 0, database_url=db_path, rate_limit=3,
    )
    ws_port = ws_server.sockets[0].getsockname()[1]

    try:
        async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
            await ws.recv()

            for i in range(3):
                await ws.send(json.dumps({"type": "broadcast", "payload": {"seq": i}}))
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                assert msg["type"] == "broadcast"

            await ws.send(json.dumps({"type": "broadcast", "payload": {"seq": 99}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert msg["type"] == "error"
            assert msg["payload"]["code"] == "rate_limit_exceeded"
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        http_server.close()
        await http_server.wait_closed()
        subscriber_task.cancel()
        cleanup_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        registry.clear()
        channels.clear()
        message_store.clear()


@pytest.mark.asyncio
async def test_rate_limit_allows_until_limit(tmp_path):
    """Client can send up to limit without error."""
    db_path = str(tmp_path / "messages_rl2.db")
    ws_server, http_server, subscriber_task, cleanup_task = await start(
        WS_HOST, 0, HTTP_HOST, 0, database_url=db_path, rate_limit=5,
    )
    ws_port = ws_server.sockets[0].getsockname()[1]

    try:
        async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
            await ws.recv()

            for i in range(5):
                await ws.send(json.dumps({"type": "broadcast", "payload": {"seq": i}}))
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                assert msg["type"] == "broadcast"
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        http_server.close()
        await http_server.wait_closed()
        subscriber_task.cancel()
        cleanup_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        registry.clear()
        channels.clear()
        message_store.clear()


@pytest.mark.asyncio
async def test_rate_limit_per_client_independent(tmp_path):
    """Rate limits are tracked independently per client."""
    db_path = str(tmp_path / "messages_rl3.db")
    ws_server, http_server, subscriber_task, cleanup_task = await start(
        WS_HOST, 0, HTTP_HOST, 0, database_url=db_path, rate_limit=2,
    )
    ws_port = ws_server.sockets[0].getsockname()[1]

    try:
        async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
                connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({"type": "broadcast", "payload": {"seq": 1}}))
            await asyncio.wait_for(ws1.recv(), timeout=2)

            await ws2.send(json.dumps({"type": "broadcast", "payload": {"seq": 2}}))
            await asyncio.wait_for(ws2.recv(), timeout=2)
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        http_server.close()
        await http_server.wait_closed()
        subscriber_task.cancel()
        cleanup_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        registry.clear()
        channels.clear()
        message_store.clear()


# --- History endpoint tests ---


@pytest.mark.asyncio
async def test_history_endpoint_with_channel(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0.1)

        payload = {"alert": "test"}
        await ws2.send(json.dumps({
            "type": "broadcast", "channel": "alerts", "payload": payload,
        }))
        await asyncio.wait_for(ws1.recv(), timeout=2)

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /history?channel=alerts HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert "messages" in data
    assert "has_more" in data
    assert data["has_more"] is False
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["channel"] == "alerts"
    assert data["messages"][0]["payload"] == payload


@pytest.mark.asyncio
async def test_history_endpoint_chronological_order(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "seq"}}))
        await asyncio.sleep(0.2)

        for i in range(3):
            await ws2.send(json.dumps({
                "type": "broadcast", "channel": "seq", "payload": {"n": i},
            }))
            msg = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
            assert msg["payload"]["n"] == i

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /history?channel=seq HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert len(data["messages"]) == 3
    ids = [m["id"] for m in data["messages"]]
    assert ids == sorted(ids)


@pytest.mark.asyncio
async def test_history_endpoint_pagination_has_more(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "page"}}))
        await asyncio.sleep(0.2)

        for i in range(5):
            await ws2.send(json.dumps({
                "type": "broadcast", "channel": "page", "payload": {"n": i},
            }))
            msg = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
            assert msg["payload"]["n"] == i

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /history?channel=page&limit=3 HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert len(data["messages"]) == 3
    assert data["has_more"] is True


@pytest.mark.asyncio
async def test_history_endpoint_with_since(server):
    ws_port, http_port = server
    before_send = None

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "since"}}))
        await asyncio.sleep(0.1)

        for i in range(3):
            await ws2.send(json.dumps({
                "type": "broadcast", "channel": "since", "payload": {"n": i},
            }))
            msg = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
            if i == 1:
                before_send = msg["timestamp"]

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /history?channel=since&since={before_send} HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert len(data["messages"]) >= 1
    for m in data["messages"]:
        assert m["timestamp"] >= before_send


@pytest.mark.asyncio
async def test_history_missing_channel_returns_error(server):
    _, http_port = server

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /history HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert "error" in data


@pytest.mark.asyncio
async def test_history_global_channel_messages(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()

        payload = {"message": "hello"}
        await ws.send(json.dumps({"type": "broadcast", "payload": payload}))
        await asyncio.wait_for(ws.recv(), timeout=2)

    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /history?channel=global HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["channel"] == "global"
    assert data["messages"][0]["payload"] == payload


# --- Message cleanup tests ---


@pytest.mark.asyncio
async def test_message_cleanup_removes_old_messages(tmp_path):
    """Cleanup deletes messages older than TTL."""
    from datetime import timedelta
    from server import MessageStore
    import server as srv

    db_path = str(tmp_path / "cleanup.db")
    store = MessageStore(db_path)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    store.store("alerts", "broadcast", {"old": True}, cutoff)

    recent = datetime.now(timezone.utc).isoformat()
    store.store("alerts", "broadcast", {"old": False}, recent)

    assert len(store.get_messages(limit=100)) == 2

    store.delete_older_than(
        (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    )

    remaining = store.get_messages(limit=100)
    assert len(remaining) == 1
    assert remaining[0]["payload"]["old"] is False


@pytest.mark.asyncio
async def test_cleanup_background_task_runs(tmp_path):
    """Server starts cleanup background task."""
    db_path = str(tmp_path / "cleanup_bg.db")
    ws_server, http_server, subscriber_task, cleanup_task = await start(
        WS_HOST, 0, HTTP_HOST, 0, database_url=db_path, message_ttl_days=7,
    )

    assert not cleanup_task.done()

    ws_server.close()
    await ws_server.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    subscriber_task.cancel()
    cleanup_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    registry.clear()
    channels.clear()
    message_store.clear()
