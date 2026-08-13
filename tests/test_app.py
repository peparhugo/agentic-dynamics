import asyncio
import json
import urllib.request

import pytest
from fakeredis import FakeServer
from fakeredis.aioredis import FakeRedis
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def running_server(tmp_path):
    notification_server = NotificationServer(
        tmp_path, redis_client=FakeRedis(server=FakeServer(), decode_responses=True)
    )
    async with notification_server.run(port=0) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield notification_server, port, tmp_path


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


async def assert_receives_nothing(websocket):
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(websocket.recv(), timeout=0.05)


async def test_connect_assigns_unique_ids_and_persists_state(running_server):
    server, port, data_dir = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)

        assert first_message["type"] == "system"
        assert first_message["payload"]["event"] == "connected"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert await server.connected_count() == 2
        persisted = json.loads((data_dir / "clients.json").read_text())
        assert sorted(persisted["clients"]) == sorted(
            [first_message["payload"]["client_id"], second_message["payload"]["client_id"]]
        )


async def test_broadcast_reaches_every_connected_client(running_server):
    _, port, data_dir = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

        first_received = await receive_json(first)
        second_received = await receive_json(second)
        assert first_received == second_received
        assert first_received["type"] == "broadcast"
        assert first_received["payload"] == {"text": "hello"}
        assert isinstance(first_received["timestamp"], str)

    history = [json.loads(line) for line in (data_dir / "messages.jsonl").read_text().splitlines()]
    assert any(message["type"] == "broadcast" for message in history)


async def test_direct_message_only_reaches_target(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as sender, connect(
        f"ws://127.0.0.1:{port}"
    ) as recipient:
        await receive_json(sender)
        recipient_id = (await receive_json(recipient))["payload"]["client_id"]
        await sender.send(
            json.dumps(
                {"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}}
            )
        )

        message = await receive_json(recipient)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "private"
        await assert_receives_nothing(sender)


async def test_invalid_messages_return_system_errors(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send("not-json")
        response = await receive_json(websocket)
        assert response["type"] == "system"
        assert response["payload"] == {"error": "invalid JSON"}


async def test_disconnect_removes_and_persists_client(running_server):
    server, port, data_dir = running_server
    websocket = await connect(f"ws://127.0.0.1:{port}")
    await receive_json(websocket)
    await websocket.close()

    for _ in range(20):
        if await server.connected_count() == 0:
            break
        await asyncio.sleep(0.01)
    assert await server.connected_count() == 0
    assert json.loads((data_dir / "clients.json").read_text()) == {"clients": []}


async def test_health_reports_connected_count(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)

        def request_health():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
                return response.status, json.load(response)

        status, body = await asyncio.to_thread(request_health)
        assert status == 200
        assert body == {"connected_clients": 1}


async def test_channel_message_only_reaches_subscribers(running_server):
    _, port, data_dir = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second, connect(f"ws://127.0.0.1:{port}") as third:
        await receive_json(first)
        await receive_json(second)
        await receive_json(third)
        await first.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.01)

        await third.send(
            json.dumps(
                {"type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}}
            )
        )

        first_received = await receive_json(first)
        second_received = await receive_json(second)
        assert first_received == second_received
        assert first_received["channel"] == "alerts"
        assert first_received["payload"] == {"text": "warning"}
        await assert_receives_nothing(third)

    history = [json.loads(line) for line in (data_dir / "messages.jsonl").read_text().splitlines()]
    assert any(message.get("channel") == "alerts" for message in history)


async def test_unsubscribe_and_disconnect_remove_active_channels(running_server):
    server, port, _ = running_server
    first = await connect(f"ws://127.0.0.1:{port}")
    second = await connect(f"ws://127.0.0.1:{port}")
    first_id = (await receive_json(first))["payload"]["client_id"]
    second_id = (await receive_json(second))["payload"]["client_id"]
    await first.send(json.dumps({"type": "subscribe", "channel": "chat"}))
    await second.send(json.dumps({"type": "subscribe", "channel": "chat"}))
    await asyncio.sleep(0.01)

    assert await server.channel_subscribers("chat") == sorted([first_id, second_id])
    await first.send(json.dumps({"type": "unsubscribe", "channel": "chat"}))
    await asyncio.sleep(0.01)
    assert await server.channel_subscribers("chat") == [second_id]

    await second.close()
    for _ in range(20):
        if not await server.channel_counts():
            break
        await asyncio.sleep(0.01)
    assert await server.channel_counts() == []
    await first.close()


async def test_client_can_subscribe_to_multiple_channels(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as subscriber, connect(
        f"ws://127.0.0.1:{port}"
    ) as publisher:
        await receive_json(subscriber)
        await receive_json(publisher)
        await subscriber.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await subscriber.send(json.dumps({"type": "subscribe", "channel": "system"}))
        await asyncio.sleep(0.01)

        for channel in ("alerts", "system"):
            await publisher.send(
                json.dumps({"type": "broadcast", "channel": channel, "payload": {}})
            )
            assert (await receive_json(subscriber))["channel"] == channel
        await assert_receives_nothing(publisher)


async def test_channel_endpoints_report_subscriptions(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        client_id = (await receive_json(websocket))["payload"]["client_id"]
        await websocket.send(json.dumps({"type": "subscribe", "channel": "team chat"}))
        await asyncio.sleep(0.01)

        def get_json(path):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as response:
                return response.status, json.load(response)

        status, channels = await asyncio.to_thread(get_json, "/channels")
        assert status == 200
        assert channels == {
            "channels": [{"name": "team chat", "subscriber_count": 1}]
        }

        status, subscribers = await asyncio.to_thread(
            get_json, "/channels/team%20chat/subscribers"
        )
        assert status == 200
        assert subscribers == {"channel": "team chat", "subscribers": [client_id]}


async def test_invalid_channel_control_messages_return_errors(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send(json.dumps({"type": "subscribe"}))
        assert (await receive_json(websocket))["payload"] == {
            "error": "subscribe requires channel"
        }
        await websocket.send(json.dumps({"type": "unsubscribe", "channel": ""}))
        assert (await receive_json(websocket))["payload"] == {
            "error": "channel must be a non-empty string"
        }


async def test_redis_pubsub_delivers_between_server_instances(tmp_path):
    fake_server = FakeServer()
    first_server = NotificationServer(
        tmp_path / "first",
        redis_client=FakeRedis(server=fake_server, decode_responses=True),
    )
    second_server = NotificationServer(
        tmp_path / "second",
        redis_client=FakeRedis(server=fake_server, decode_responses=True),
    )
    async with first_server.run(port=0) as first_http, second_server.run(
        port=0
    ) as second_http:
        first_port = first_http.sockets[0].getsockname()[1]
        second_port = second_http.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{first_port}") as publisher, connect(
            f"ws://127.0.0.1:{second_port}"
        ) as subscriber:
            await receive_json(publisher)
            await receive_json(subscriber)
            await publisher.send(
                json.dumps({"type": "broadcast", "payload": {"text": "shared"}})
            )

            assert (await receive_json(publisher))["payload"] == {"text": "shared"}
            assert (await receive_json(subscriber))["payload"] == {"text": "shared"}
            assert await first_server.connected_count() == 2
            assert await second_server.connected_count() == 2


async def test_messages_endpoint_reads_sqlite_history(running_server):
    _, port, data_dir = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send(json.dumps({"type": "subscribe", "channel": "news"}))
        await websocket.send(
            json.dumps(
                {"type": "broadcast", "channel": "news", "payload": {"number": 1}}
            )
        )
        await receive_json(websocket)

        def request_messages():
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/messages?limit=1&offset=1"
            ) as response:
                return response.status, json.load(response)

        status, body = await asyncio.to_thread(request_messages)

    assert status == 200
    assert body["messages"] == [
        {
            "id": 2,
            "channel": "news",
            "type": "broadcast",
            "payload": {"number": 1},
            "timestamp": body["messages"][0]["timestamp"],
        }
    ]
    assert (data_dir / "messages.db").exists()


async def test_database_url_selects_sqlite_path(tmp_path, monkeypatch):
    database_path = tmp_path / "configured" / "history.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    server = NotificationServer(
        tmp_path / "data",
        redis_client=FakeRedis(server=FakeServer(), decode_responses=True),
    )
    async with server.run(port=0):
        assert database_path.exists()
