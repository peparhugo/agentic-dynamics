import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
import websockets
from fakeredis import aioredis

from app import NotificationHTTPServer, NotificationServer


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages = []

    async def send(self, message: str) -> None:
        self.messages.append(json.loads(message))


async def http_json(server: NotificationServer, request: str) -> tuple[bytes, dict]:
    http_server = await asyncio.start_server(NotificationHTTPServer(server).handler, "127.0.0.1", 0)
    port = http_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"{request}\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    return response, json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_and_health_counts() -> None:
    notification_server = NotificationServer()
    websocket_server = await websockets.serve(
        notification_server.handle_client, "127.0.0.1", 0
    )
    port = websocket_server.sockets[0].getsockname()[1]
    first = await websockets.connect(f"ws://127.0.0.1:{port}")
    second = await websockets.connect(f"ws://127.0.0.1:{port}")
    try:
        first_welcome = json.loads(await first.recv())
        second_welcome = json.loads(await second.recv())
        assert first_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
        assert notification_server.health()["connected_clients"] == 2

        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        for client in (first, second):
            received = json.loads(await client.recv())
            assert received["type"] == "broadcast"
            assert received["payload"] == {"text": "hello"}
            assert "timestamp" in received
    finally:
        await first.close()
        await second.close()
        websocket_server.close()
        await websocket_server.wait_closed()
    assert notification_server.connected_client_count == 0


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target() -> None:
    notification_server = NotificationServer()

    sender = FakeWebSocket()
    target = FakeWebSocket()
    sender_id = notification_server.add_client(sender)
    target_id = notification_server.add_client(target)
    await notification_server.handle_message(
        sender_id,
        json.dumps({"type": "direct", "payload": {"client_id": target_id, "text": "private"}}),
    )
    assert sender.messages == []
    assert target.messages[0]["payload"]["text"] == "private"


@pytest.mark.asyncio
async def test_redis_backbone_delivers_between_server_instances(tmp_path) -> None:
    broker = aioredis.FakeRedis(decode_responses=True)
    first = NotificationServer(redis_client=broker, database_url=str(tmp_path / "first.db"))
    second = NotificationServer(redis_client=broker, database_url=str(tmp_path / "second.db"))
    websocket = FakeWebSocket()
    client_id = second.add_client(websocket)
    try:
        await second.handle_message(client_id, json.dumps({"type": "subscribe", "payload": {"channel": "news"}}))
        await first.handle_message("sender", json.dumps({
            "type": "broadcast", "channel": "news", "payload": {"text": "from another server"}
        }))
        await asyncio.sleep(0.01)
        assert websocket.messages[-1]["payload"] == {"text": "from another server"}
        assert await broker.sismember(f"notifications:client:{client_id}:channels", "news")
    finally:
        await first._backbone.close()
        await second._backbone.close()


@pytest.mark.asyncio
async def test_messages_endpoint_reads_persisted_history(tmp_path) -> None:
    server = NotificationServer(database_url=str(tmp_path / "history.db"))
    client_id = server.add_client(FakeWebSocket())
    await server.handle_message(client_id, json.dumps({"type": "broadcast", "payload": {"n": 1}}))
    http_server = await asyncio.start_server(NotificationHTTPServer(server).handler, "127.0.0.1", 0)
    port = http_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /messages?limit=1&offset=0 HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    body = json.loads(response.split(b"\r\n\r\n", 1)[1])
    assert body["messages"][0]["payload"] == {"n": 1}
    assert body["messages"][0]["type"] == "broadcast"


@pytest.mark.asyncio
async def test_health_endpoint_returns_current_count() -> None:
    notification_server = NotificationServer()
    http_server = await asyncio.start_server(
        NotificationHTTPServer(notification_server).handler, "127.0.0.1", 0
    )
    port = http_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    assert b"200 OK" in response
    assert json.loads(response.split(b"\r\n\r\n", 1)[1]) == {
        "status": "ok",
        "connected_clients": 0,
    }


@pytest.mark.asyncio
async def test_rate_limit_returns_error_and_uses_redis_counter(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT", "2")
    broker = aioredis.FakeRedis(decode_responses=True)
    server = NotificationServer(redis_client=broker)
    websocket = FakeWebSocket()
    client_id = server.add_client(websocket)
    try:
        for number in range(3):
            await server.handle_message(
                client_id, json.dumps({"type": "broadcast", "payload": {"n": number}})
            )
        assert [message["type"] for message in websocket.messages] == ["broadcast", "broadcast", "error"]
        assert websocket.messages[-1]["payload"] == {"error": "rate limit exceeded"}
        rate_keys = [key for key in await broker.keys("notifications:rate:*")]
        assert len(rate_keys) == 1
        assert await broker.get(rate_keys[0]) == "3"
    finally:
        await server._backbone.close()


@pytest.mark.asyncio
async def test_history_filters_channel_since_and_paginates(tmp_path) -> None:
    server = NotificationServer(database_url=str(tmp_path / "history-query.db"))
    client_id = server.add_client(FakeWebSocket())
    await server.handle_message(client_id, json.dumps({
        "type": "broadcast", "channel": "news", "payload": {"n": 1}
    }))
    first_timestamp = server.store.history("news")[0][0]["timestamp"]
    await server.handle_message(client_id, json.dumps({
        "type": "broadcast", "channel": "other", "payload": {"n": 99}
    }))
    await server.handle_message(client_id, json.dumps({
        "type": "broadcast", "channel": "news", "payload": {"n": 2}
    }))

    response, body = await http_json(server, "GET /history?channel=news&since=" + first_timestamp + "&limit=1 HTTP/1.1")
    assert b"200 OK" in response
    assert [message["payload"]["n"] for message in body["messages"]] == [2]
    assert body["has_more"] is False


@pytest.mark.asyncio
async def test_cleanup_removes_messages_older_than_configured_ttl(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "7")
    server = NotificationServer(database_url=str(tmp_path / "expiry.db"))
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat().replace("+00:00", "Z")
    server.store.save("news", "broadcast", {"old": True}, old)
    assert await server.cleanup_expired_messages() == 1
    assert server.store.history("news") == ([], False)
