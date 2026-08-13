import asyncio
import json
from urllib.request import urlopen

import pytest
import fakeredis.aioredis
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import ClientRegistry, MessageStore, NotificationServer, RedisBackbone


@pytest.fixture
async def running_server():
    notification_server = NotificationServer(ClientRegistry())
    async with serve(
        notification_server.websocket_handler,
        "127.0.0.1",
        0,
        process_request=notification_server.process_request,
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield notification_server, port


async def receive(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


async def get_json(url):
    response = await asyncio.to_thread(urlopen, url)
    with response:
        return response.status, json.loads(response.read())


@pytest.mark.asyncio
async def test_connect_assigns_unique_ids_and_health_reports_count(running_server):
    server, port = running_server
    async with connect(f"ws://127.0.0.1:{port}/ws") as first, connect(
        f"ws://127.0.0.1:{port}/ws"
    ) as second:
        first_welcome, second_welcome = await receive(first), await receive(second)
        assert first_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
        assert server.registry.count == 2

        response = await asyncio.to_thread(urlopen, f"http://127.0.0.1:{port}/health")
        with response:
            assert response.status == 200
            assert json.loads(response.read()) == {"connected_clients": 2}


@pytest.mark.asyncio
async def test_broadcast_reaches_every_client(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}/ws") as first, connect(
        f"ws://127.0.0.1:{port}/ws"
    ) as second:
        await receive(first)
        await receive(second)
        outgoing = {
            "type": "broadcast",
            "payload": {"text": "hello"},
            "timestamp": "2026-01-01T00:00:00Z",
        }
        await first.send(json.dumps(outgoing))
        assert await receive(first) == outgoing
        assert await receive(second) == outgoing


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}/ws") as sender, connect(
        f"ws://127.0.0.1:{port}/ws"
    ) as recipient:
        await receive(sender)
        recipient_id = (await receive(recipient))["payload"]["client_id"]
        outgoing = {
            "type": "direct",
            "payload": {"target_id": recipient_id, "text": "private"},
            "timestamp": "2026-01-01T00:00:00Z",
        }
        await sender.send(json.dumps(outgoing))
        assert await receive(recipient) == outgoing
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_disconnect_removes_client(running_server):
    server, port = running_server
    websocket = await connect(f"ws://127.0.0.1:{port}/ws")
    await receive(websocket)
    assert server.registry.count == 1
    await websocket.close()
    for _ in range(20):
        if server.registry.count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.registry.count == 0


@pytest.mark.asyncio
async def test_invalid_message_returns_formatted_system_error(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}/ws") as websocket:
        await receive(websocket)
        await websocket.send("not JSON")
        error = await receive(websocket)
        assert set(error) == {"type", "payload", "timestamp"}
        assert error["type"] == "system"
        assert "error" in error["payload"]
        assert isinstance(error["timestamp"], str)


@pytest.mark.asyncio
async def test_channel_message_only_reaches_subscribers(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}/ws") as sender, connect(
        f"ws://127.0.0.1:{port}/ws"
    ) as alerts_client, connect(f"ws://127.0.0.1:{port}/ws") as chat_client:
        await receive(sender)
        await receive(alerts_client)
        await receive(chat_client)
        await alerts_client.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await chat_client.send(json.dumps({"type": "subscribe", "channel": "chat"}))

        outgoing = {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "warning"},
            "timestamp": "2026-01-01T00:00:00Z",
        }
        await sender.send(json.dumps(outgoing))
        assert await receive(alerts_client) == outgoing
        for websocket in (sender, chat_client):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(websocket.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_client_can_subscribe_to_multiple_channels_and_unsubscribe(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}/ws") as sender, connect(
        f"ws://127.0.0.1:{port}/ws"
    ) as recipient:
        await receive(sender)
        await receive(recipient)
        for channel in ("alerts", "system"):
            await recipient.send(json.dumps({"type": "subscribe", "channel": channel}))

        system_message = {
            "type": "system",
            "channel": "system",
            "payload": {"text": "maintenance"},
            "timestamp": "2026-01-01T00:00:00Z",
        }
        await sender.send(json.dumps(system_message))
        assert await receive(recipient) == system_message

        await recipient.send(json.dumps({"type": "unsubscribe", "channel": "alerts"}))
        await sender.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"text": "ignored"},
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(recipient.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_channel_rest_endpoints_report_active_subscribers(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}/ws") as first, connect(
        f"ws://127.0.0.1:{port}/ws"
    ) as second:
        first_id = (await receive(first))["payload"]["client_id"]
        second_id = (await receive(second))["payload"]["client_id"]
        await first.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "channel": "chat"}))

        status, channels = await get_json(f"http://127.0.0.1:{port}/channels")
        assert status == 200
        assert channels == {
            "channels": [
                {"name": "alerts", "subscriber_count": 2},
                {"name": "chat", "subscriber_count": 1},
            ]
        }
        status, subscribers = await get_json(
            f"http://127.0.0.1:{port}/channels/alerts/subscribers"
        )
        assert status == 200
        assert subscribers == {
            "channel": "alerts",
            "subscribers": sorted([first_id, second_id]),
        }


@pytest.mark.asyncio
async def test_disconnect_removes_inactive_channels(running_server):
    _, port = running_server
    websocket = await connect(f"ws://127.0.0.1:{port}/ws")
    await receive(websocket)
    await websocket.send(json.dumps({"type": "subscribe", "channel": "temporary"}))
    assert (await get_json(f"http://127.0.0.1:{port}/channels"))[1]["channels"]

    await websocket.close()
    for _ in range(20):
        if not (await get_json(f"http://127.0.0.1:{port}/channels"))[1]["channels"]:
            break
        await asyncio.sleep(0.01)
    assert (await get_json(f"http://127.0.0.1:{port}/channels"))[1] == {"channels": []}


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances(tmp_path):
    fake_server = fakeredis.FakeServer()
    backbones = [
        RedisBackbone(
            fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True)
        )
        for _ in range(2)
    ]
    servers = [
        NotificationServer(
            ClientRegistry(),
            backbone,
            MessageStore(str(tmp_path / f"messages-{index}.db")),
        )
        for index, backbone in enumerate(backbones)
    ]
    await asyncio.gather(*(server.start() for server in servers))
    try:
        async with serve(
            servers[0].websocket_handler,
            "127.0.0.1",
            0,
            process_request=servers[0].process_request,
        ) as first_listener, serve(
            servers[1].websocket_handler,
            "127.0.0.1",
            0,
            process_request=servers[1].process_request,
        ) as second_listener:
            first_port = first_listener.sockets[0].getsockname()[1]
            second_port = second_listener.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{first_port}/ws") as sender, connect(
                f"ws://127.0.0.1:{second_port}/ws"
            ) as recipient:
                sender_id = (await receive(sender))["payload"]["client_id"]
                recipient_id = (await receive(recipient))["payload"]["client_id"]
                assert await backbones[0].client.smembers("notifications:clients") == {
                    sender_id,
                    recipient_id,
                }

                outgoing = {
                    "type": "direct",
                    "payload": {"target_id": recipient_id, "text": "cross-instance"},
                    "timestamp": "2026-01-01T00:00:00Z",
                }
                await sender.send(json.dumps(outgoing))
                assert await receive(recipient) == outgoing
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(sender.recv(), timeout=0.05)
    finally:
        await asyncio.gather(*(backbone.close() for backbone in backbones))


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path):
    store = MessageStore(f"sqlite:///{tmp_path / 'history.db'}")
    notification_server = NotificationServer(ClientRegistry(), store=store)
    async with serve(
        notification_server.websocket_handler,
        "127.0.0.1",
        0,
        process_request=notification_server.process_request,
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}/ws") as websocket:
            await receive(websocket)
            await websocket.send(
                json.dumps({"type": "subscribe", "channel": "history"})
            )
            for text in ("first", "second"):
                await websocket.send(
                    json.dumps(
                        {
                            "type": "broadcast",
                            "channel": "history",
                            "payload": {"text": text},
                            "timestamp": f"2026-01-0{1 if text == 'first' else 2}T00:00:00Z",
                        }
                    )
                )
                await receive(websocket)

        status, body = await get_json(
            f"http://127.0.0.1:{port}/messages?limit=1&offset=1"
        )
        assert status == 200
        assert body == {
            "messages": [
                {
                    "id": 1,
                    "channel": "history",
                    "type": "broadcast",
                    "payload": {"text": "first"},
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ]
        }

    reopened = MessageStore(f"sqlite:///{tmp_path / 'history.db'}")
    assert len(await reopened.list(50, 0)) == 2
