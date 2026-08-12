import asyncio
import json
import shutil
import socket

import pytest
import pytest_asyncio
import websockets

from notification_server import NotificationServer, make_message


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def http_health(server: NotificationServer) -> dict:
    port = server._http_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


async def http_get(server: NotificationServer, path: str) -> dict:
    port = server._http_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


async def http_get_with_status(server: NotificationServer, path: str) -> tuple[int, dict]:
    port = server._http_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    status = int(response.split(b" ", 2)[1])
    return status, json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(websocket_port=0, http_port=0)
    await instance.start()
    yield instance
    await instance.stop()


def websocket_url(server: NotificationServer) -> str:
    port = server._websocket_server.sockets[0].getsockname()[1]
    return f"ws://127.0.0.1:{port}"


@pytest.mark.asyncio
async def test_assigns_unique_ids_and_health_counts_clients(server):
    first = await websockets.connect(websocket_url(server))
    second = await websockets.connect(websocket_url(server))
    first_message = json.loads(await first.recv())
    second_message = json.loads(await second.recv())

    assert first_message["type"] == "system"
    assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
    assert (await http_health(server))["connected_clients"] == 2

    await first.close()
    await asyncio.sleep(0)
    assert (await http_health(server))["connected_clients"] == 1
    await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_every_client(server):
    first = await websockets.connect(websocket_url(server))
    second = await websockets.connect(websocket_url(server))
    await first.recv()
    await second.recv()

    await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    messages = [json.loads(await client.recv()) for client in (first, second)]
    assert all(message["type"] == "broadcast" for message in messages)
    assert all(message["payload"] == {"text": "hello"} for message in messages)
    assert all(isinstance(message["timestamp"], str) for message in messages)
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_message_targets_client(server):
    first = await websockets.connect(websocket_url(server))
    second = await websockets.connect(websocket_url(server))
    first_id = json.loads(await first.recv())["payload"]["client_id"]
    second_id = json.loads(await second.recv())["payload"]["client_id"]

    await first.send(json.dumps({
        "type": "direct",
        "payload": {"client_id": second_id, "text": "private"},
    }))
    message = json.loads(await second.recv())
    assert message["type"] == "direct"
    assert message["payload"]["text"] == "private"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(first.recv(), timeout=0.05)
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path):
    server = NotificationServer(
        websocket_port=0, http_port=0,
        database_url=f"sqlite:///{tmp_path / 'messages.sqlite'}",
    )
    await server.start()
    try:
        client = await websockets.connect(websocket_url(server))
        await client.recv()
        await client.send(json.dumps({"type": "broadcast", "payload": {"text": "saved"}}))
        await client.recv()

        status, result = await http_get_with_status(server, "/messages?limit=1&offset=0")
        assert status == 200
        assert result["messages"][0]["type"] == "broadcast"
        assert result["messages"][0]["payload"] == {"text": "saved"}
        await client.close()
    finally:
        await server.stop()


@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("redis-server") is None, reason="redis-server is not installed")
async def test_redis_backbone_delivers_between_server_instances(tmp_path):
    redis_port = free_port()
    process = await asyncio.create_subprocess_exec(
        "redis-server", "--save", "", "--appendonly", "no", "--port", str(redis_port),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    first = second = None
    try:
        await asyncio.sleep(0.1)
        redis_url = f"redis://127.0.0.1:{redis_port}/0"
        first = NotificationServer(websocket_port=0, http_port=0, redis_url=redis_url,
                                   database_url=f"sqlite:///{tmp_path / 'first.db'}")
        second = NotificationServer(websocket_port=0, http_port=0, redis_url=redis_url,
                                    database_url=f"sqlite:///{tmp_path / 'second.db'}")
        await first.start()
        await second.start()
        first_client = await websockets.connect(websocket_url(first))
        second_client = await websockets.connect(websocket_url(second))
        await first_client.recv()
        await second_client.recv()
        await first_client.send(json.dumps({"type": "broadcast", "payload": {"shared": True}}))
        assert json.loads(await first_client.recv())["payload"] == {"shared": True}
        assert json.loads(await second_client.recv())["payload"] == {"shared": True}
        await first_client.close()
        await second_client.close()
    finally:
        if first is not None:
            await first.stop()
        if second is not None:
            await second.stop()
        process.terminate()
        await process.wait()


@pytest.mark.asyncio
async def test_channel_subscriptions_route_messages_and_are_listed(server):
    first = await websockets.connect(websocket_url(server))
    second = await websockets.connect(websocket_url(server))
    first_id = json.loads(await first.recv())["payload"]["client_id"]
    second_id = json.loads(await second.recv())["payload"]["client_id"]

    await first.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await first.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
    await second.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    assert (await http_get(server, "/channels"))["channels"] == {"alerts": 2, "chat": 1}
    assert set((await http_get(server, "/channels/alerts/subscribers"))["subscribers"]) == {
        first_id, second_id
    }

    await first.send(json.dumps({
        "type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}
    }))
    assert json.loads(await first.recv())["payload"]["text"] == "warning"
    assert json.loads(await second.recv())["payload"]["text"] == "warning"

    await first.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
    await second.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"n": 1}}))
    assert json.loads(await second.recv())["payload"]["n"] == 1
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(first.recv(), timeout=0.05)

    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_rate_limit_returns_an_error(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "2")
    server = NotificationServer(websocket_port=0, http_port=0)
    await server.start()
    try:
        client = await websockets.connect(websocket_url(server))
        await client.recv()
        for value in (1, 2):
            await client.send(json.dumps({"type": "broadcast", "payload": {"n": value}}))
            assert json.loads(await client.recv())["payload"] == {"n": value}
        await client.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
        error = json.loads(await client.recv())
        assert error["type"] == "system"
        assert error["payload"]["error"] == "rate limit exceeded"
        await client.close()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_history_filters_since_and_paginates_chronologically(tmp_path):
    server = NotificationServer(
        websocket_port=0, http_port=0,
        database_url=f"sqlite:///{tmp_path / 'history.sqlite'}",
    )
    await server.start()
    try:
        for index, timestamp in enumerate((
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
            "2026-01-03T00:00:00+00:00",
        )):
            await server._save_message({
                "type": "broadcast", "channel": "alerts", "payload": {"n": index},
                "timestamp": timestamp,
            })
        await server._save_message({
            "type": "broadcast", "channel": "other", "payload": {},
            "timestamp": "2026-01-02T00:00:00+00:00",
        })

        status, result = await http_get_with_status(
            server, "/history?channel=alerts&since=2026-01-02T00:00:00%2B00:00&limit=1"
        )
        assert status == 200
        assert [message["payload"]["n"] for message in result["messages"]] == [1]
        assert result["has_more"] is True

        status, result = await http_get_with_status(server, "/history?channel=alerts&limit=5")
        assert status == 200
        assert [message["payload"]["n"] for message in result["messages"]] == [0, 1, 2]
        assert result["has_more"] is False
    finally:
        await server.stop()


def test_make_message_rejects_invalid_type():
    with pytest.raises(ValueError):
        make_message("unknown", {})
