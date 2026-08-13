import asyncio
import json

import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer, RedisBackbone, make_message
from tests.test_app import health_request, receive_json, send_message


@pytest.fixture
def fake_redis_server():
    return fakeredis.FakeServer()


def redis_backbone(fake_server):
    return RedisBackbone(fakeredis.aioredis.FakeRedis(server=fake_server))


async def test_redis_pubsub_delivers_between_server_instances(fake_redis_server, tmp_path):
    first = NotificationServer(redis_backbone(fake_redis_server), str(tmp_path / "first.db"))
    second = NotificationServer(redis_backbone(fake_redis_server), str(tmp_path / "second.db"))
    await first.start()
    await second.start()
    try:
        async with serve(first.websocket_handler, "127.0.0.1", 0) as first_ws_server, serve(
            second.websocket_handler, "127.0.0.1", 0
        ) as second_ws_server:
            first_port = first_ws_server.sockets[0].getsockname()[1]
            second_port = second_ws_server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{first_port}") as sender, connect(
                f"ws://127.0.0.1:{second_port}"
            ) as receiver:
                await receive_json(sender)
                await receive_json(receiver)

                await send_message(receiver, "subscribe", channel="alerts")
                await send_message(sender, "broadcast", {"text": "shared"}, "alerts")

                delivered = await receive_json(receiver)
                assert delivered["payload"] == {"text": "shared"}
                assert delivered["channel"] == "alerts"
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(sender.recv(), timeout=0.05)
                assert await first.clients.count() == 2
                assert await first.clients.channels() == {"alerts": 1}
    finally:
        await first.close()
        await second.close()


async def test_messages_persist_across_restart_and_support_pagination(tmp_path):
    database = tmp_path / "messages.sqlite"
    first = NotificationServer(database_url=f"sqlite:///{database}")
    await first.broadcast(make_message("broadcast", {"sequence": 1}, "news"))
    await first.broadcast(make_message("broadcast", {"sequence": 2}, "news"))
    await first.close()

    second = NotificationServer(database_url=f"sqlite:///{database}")
    http_server = await asyncio.start_server(second.health_handler, "127.0.0.1", 0)
    port = http_server.sockets[0].getsockname()[1]
    try:
        async with http_server:
            header, body = await health_request(port, "/messages?limit=1&offset=1")
        assert "200 OK" in header
        assert len(body) == 1
        assert body[0]["id"] == 1
        assert body[0]["channel"] == "news"
        assert body[0]["type"] == "broadcast"
        assert body[0]["payload"] == {"sequence": 1}
        assert isinstance(body[0]["timestamp"], str)
    finally:
        await second.close()


async def test_redis_connection_state_is_visible_to_new_server(fake_redis_server, tmp_path):
    first_backbone = redis_backbone(fake_redis_server)
    await first_backbone.add_client("persisted-client")
    await first_backbone.subscribe_client("persisted-client", "updates")

    restarted = NotificationServer(
        redis_backbone(fake_redis_server), str(tmp_path / "restarted.db")
    )
    try:
        assert await restarted.clients.count() == 1
        assert await restarted.clients.subscribers("updates") == ["persisted-client"]
    finally:
        await restarted.close()
        await first_backbone.remove_client("persisted-client")
        await first_backbone.close()
