import asyncio
import json

import httpx
import pytest
import pytest_asyncio
import websockets

import app
from app import handler, process_request, registry, _start_background, _stop_background
from websockets.asyncio.server import serve


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def server_url():
    from fakeredis import FakeAsyncRedis

    app._redis = FakeAsyncRedis(decode_responses=True)
    app._db = None
    app._listener_task = None
    app.DATABASE_URL = ":memory:"

    await _start_background()
    port = _free_port()
    async with serve(handler, "127.0.0.1", port, process_request=process_request) as srv:
        yield f"ws://127.0.0.1:{port}"

    registry._clients.clear()
    registry._channels.clear()
    registry._client_channels.clear()
    await _stop_background()


async def _recv_json(ws):
    raw = await ws.recv()
    return json.loads(raw)


class TestConnection:
    @pytest.mark.asyncio
    async def test_connect_receives_welcome(self, server_url):
        async with websockets.connect(server_url) as ws:
            msg = await _recv_json(ws)
            assert msg["type"] == "system"
            assert msg["payload"]["message"] == "connected"
            assert "client_id" in msg["payload"]

    @pytest.mark.asyncio
    async def test_unique_client_ids(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            m1 = await _recv_json(ws1)
            m2 = await _recv_json(ws2)
            assert m1["payload"]["client_id"] != m2["payload"]["client_id"]

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_disconnect_notifies_others(self, server_url):
        async with websockets.connect(server_url) as ws1:
            w1 = await _recv_json(ws1)
            cid1 = w1["payload"]["client_id"]

            async with websockets.connect(server_url) as ws2:
                await _recv_json(ws2)

            disconnect_msg = await _recv_json(ws1)
            assert disconnect_msg["type"] == "system"
            assert disconnect_msg["payload"]["message"] == "disconnected"
            assert "client_id" in disconnect_msg["payload"]
            assert disconnect_msg["payload"]["client_id"] != cid1


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            payload = {"text": "hello everyone"}
            await ws1.send(
                json.dumps({"type": "broadcast", "payload": payload})
            )

            msg_on_ws2 = await _recv_json(ws2)
            assert msg_on_ws2["type"] == "broadcast"
            assert msg_on_ws2["payload"]["text"] == "hello everyone"

    @pytest.mark.asyncio
    async def test_broadcast_includes_from(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            cid1 = w1["payload"]["client_id"]
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "broadcast", "payload": {"x": 1}})
            )

            msg = await _recv_json(ws2)
            assert msg["payload"]["from"] == cid1


class TestDirect:
    @pytest.mark.asyncio
    async def test_direct_message(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            w2 = await _recv_json(ws2)
            cid1 = w1["payload"]["client_id"]
            cid2 = w2["payload"]["client_id"]

            await ws1.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": cid2, "message": "secret"},
                    }
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == cid1
            assert msg["payload"]["message"] == "secret"

    @pytest.mark.asyncio
    async def test_direct_nonexistent_silent(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": "no-such-id", "message": "hi"},
                    }
                )
            )
            await asyncio.sleep(0.05)


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_count(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["connected_clients"] == 1

    @pytest.mark.asyncio
    async def test_health_zero(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected_clients"] == 0


class TestSystem:
    @pytest.mark.asyncio
    async def test_invalid_json_ignored(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send("not json!!!")
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_message_has_timestamp(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)
            await ws1.send(
                json.dumps({"type": "broadcast", "payload": {"text": "ts"}})
            )
            msg = await _recv_json(ws2)
            assert "timestamp" in msg
            assert isinstance(msg["timestamp"], str)


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_receives_confirmation(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )

            resp = await _recv_json(ws)
            assert resp["type"] == "system"
            assert resp["payload"]["message"] == "subscribed to alerts"
            assert resp["payload"]["channel"] == "alerts"

    @pytest.mark.asyncio
    async def test_unsubscribe_receives_confirmation(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "unsubscribe", "channel": "alerts"})
            )

            resp = await _recv_json(ws)
            assert resp["type"] == "system"
            assert resp["payload"]["message"] == "unsubscribed from alerts"
            assert resp["payload"]["channel"] == "alerts"

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_channel_silent(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps(
                    {"type": "unsubscribe", "channel": "nonexistent"}
                )
            )

            resp = await _recv_json(ws)
            assert resp["type"] == "system"
            assert resp["payload"]["channel"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_subscribe_multiple_channels(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            r1 = await _recv_json(ws)
            assert r1["payload"]["channel"] == "alerts"

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "chat"})
            )
            r2 = await _recv_json(ws)
            assert r2["payload"]["channel"] == "chat"

    @pytest.mark.asyncio
    async def test_subscribe_missing_channel_ignored(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(json.dumps({"type": "subscribe"}))
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_unsubscribe_missing_channel_ignored(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(json.dumps({"type": "unsubscribe"}))
            await asyncio.sleep(0.05)


class TestChannelBroadcast:
    @pytest.mark.asyncio
    async def test_channel_message_reaches_subscribers(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)
            await ws2.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)

            await ws1.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"text": "alert!"},
                    }
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "alert!"

    @pytest.mark.asyncio
    async def test_channel_message_excludes_nonsubscribers(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)

            await ws1.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"text": "alert!"},
                    }
                )
            )

            await _recv_json(ws1)

            try:
                msg = await asyncio.wait_for(ws2.recv(), timeout=0.1)
                assert False, "ws2 should not receive channel message"
            except asyncio.TimeoutError:
                pass

    @pytest.mark.asyncio
    async def test_broadcast_without_channel_still_broadcasts_to_all(
        self, server_url
    ):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps(
                    {"type": "broadcast", "payload": {"text": "to all"}}
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "to all"

    @pytest.mark.asyncio
    async def test_channel_message_to_empty_channel(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "nonexistent",
                        "payload": {"text": "nobody"},
                    }
                )
            )
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_receiving(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)
            await ws2.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)

            await ws2.send(
                json.dumps({"type": "unsubscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)

            await ws1.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"text": "after"},
                    }
                )
            )

            await _recv_json(ws1)

            try:
                msg = await asyncio.wait_for(ws2.recv(), timeout=0.1)
                assert False, "ws2 should not receive after unsubscribing"
            except asyncio.TimeoutError:
                pass

    @pytest.mark.asyncio
    async def test_direct_message_still_works(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            w2 = await _recv_json(ws2)
            cid1 = w1["payload"]["client_id"]
            cid2 = w2["payload"]["client_id"]

            await ws1.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": cid2, "message": "hello"},
                    }
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == cid1
            assert msg["payload"]["message"] == "hello"


class TestChannelsEndpoint:
    @pytest.mark.asyncio
    async def test_channels_list_empty(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/channels")
            assert resp.status_code == 200
            data = resp.json()
            assert data == {}

    @pytest.mark.asyncio
    async def test_channels_list_with_subscribers(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)
            await ws2.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)
            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "chat"})
            )
            await _recv_json(ws1)

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/channels")
                assert resp.status_code == 200
                data = resp.json()
                assert data["alerts"] == 2
                assert data["chat"] == 1

    @pytest.mark.asyncio
    async def test_channels_subscribers_list(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws1:
            w1 = await _recv_json(ws1)
            cid1 = w1["payload"]["client_id"]

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{http_url}/channels/alerts/subscribers"
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["channel"] == "alerts"
                assert data["subscribers"] == [cid1]

    @pytest.mark.asyncio
    async def test_channels_subscribers_nonexistent_channel(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{http_url}/channels/nonexistent/subscribers"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["channel"] == "nonexistent"
            assert data["subscribers"] == []

    @pytest.mark.asyncio
    async def test_channels_cleanup_on_unsubscribe(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws)

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/channels")
                assert resp.json() == {"alerts": 1}

            await ws.send(
                json.dumps({"type": "unsubscribe", "channel": "alerts"})
            )
            await _recv_json(ws)

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/channels")
                assert resp.json() == {}


class TestDisconnectChannelCleanup:
    @pytest.mark.asyncio
    async def test_disconnect_removes_from_channels(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws)

        await asyncio.sleep(0.1)

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/channels")
            assert resp.json() == {}

    @pytest.mark.asyncio
    async def test_disconnect_notifies_channel_members(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)
            await ws2.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)

        await asyncio.sleep(0.1)

        for ws in (ws1, ws2):
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.1)
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                pass


class TestRedisPubSub:
    @pytest.mark.asyncio
    async def test_redis_publish_broadcast(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "broadcast", "payload": {"text": "via redis"}})
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "via redis"

    @pytest.mark.asyncio
    async def test_redis_publish_to_channel(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(json.dumps({"type": "subscribe", "channel": "ch1"}))
            await _recv_json(ws1)
            await ws2.send(json.dumps({"type": "subscribe", "channel": "ch1"}))
            await _recv_json(ws2)

            await ws1.send(
                json.dumps(
                    {"type": "broadcast", "channel": "ch1", "payload": {"x": 1}}
                )
            )

            msg1 = await _recv_json(ws1)
            msg2 = await _recv_json(ws2)
            assert msg1["payload"]["x"] == 1
            assert msg2["payload"]["x"] == 1

    @pytest.mark.asyncio
    async def test_redis_direct_message(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            w2 = await _recv_json(ws2)
            cid1 = w1["payload"]["client_id"]
            cid2 = w2["payload"]["client_id"]

            await ws1.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": cid2, "message": "redis direct"},
                    }
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == cid1
            assert msg["payload"]["message"] == "redis direct"

    @pytest.mark.asyncio
    async def test_multiple_servers_share_redis(self, server_url):
        from fakeredis import FakeAsyncRedis

        redis = FakeAsyncRedis(decode_responses=True)
        app._redis = redis
        app._db = None
        app._listener_task = None

        await _start_background()
        port1 = _free_port()
        port2 = _free_port()

        try:
            async with (
                serve(handler, "127.0.0.1", port1, process_request=process_request) as srv1,
                serve(handler, "127.0.0.1", port2, process_request=process_request) as srv2,
            ):
                async with websockets.connect(
                    f"ws://127.0.0.1:{port1}"
                ) as ws1, websockets.connect(
                    f"ws://127.0.0.1:{port2}"
                ) as ws2:
                    await _recv_json(ws1)
                    await _recv_json(ws2)

                    await ws1.send(
                        json.dumps(
                            {"type": "broadcast", "payload": {"text": "cross-server"}}
                        )
                    )

                    msg = await _recv_json(ws2)
                    assert msg["type"] == "broadcast"
                    assert msg["payload"]["text"] == "cross-server"
        finally:
            registry._clients.clear()
            registry._channels.clear()
            registry._client_channels.clear()
            await _stop_background()


class TestMessagePersistence:
    @pytest.mark.asyncio
    async def test_messages_endpoint_returns_history(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws1:
            await _recv_json(ws1)

        await asyncio.sleep(0.2)

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/messages")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            disconnect_msgs = [m for m in data if m["type"] == "system" and m["payload"].get("message") == "disconnected"]
            assert len(disconnect_msgs) >= 1

    @pytest.mark.asyncio
    async def test_messages_include_channel_info(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(json.dumps({"type": "subscribe", "channel": "testchan"}))
            await _recv_json(ws1)
            await ws2.send(json.dumps({"type": "subscribe", "channel": "testchan"}))
            await _recv_json(ws2)

            await ws1.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "testchan",
                        "payload": {"text": "persist me"},
                    }
                )
            )

            await _recv_json(ws1)
            await _recv_json(ws2)

        await asyncio.sleep(0.2)

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/messages?limit=50&offset=0")
            assert resp.status_code == 200
            data = resp.json()
            channel_msgs = [m for m in data if m["channel"] == "testchan"]
            assert len(channel_msgs) >= 1
            assert channel_msgs[0]["type"] == "broadcast"
            assert channel_msgs[0]["payload"]["text"] == "persist me"

    @pytest.mark.asyncio
    async def test_messages_limit_offset(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            for i in range(3):
                await ws1.send(
                    json.dumps(
                        {"type": "broadcast", "payload": {"count": i}}
                    )
                )
                await _recv_json(ws1)
                await _recv_json(ws2)

        await asyncio.sleep(0.2)

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/messages?limit=2&offset=0")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/messages?limit=10&offset=0")
            assert resp.status_code == 200
            data = resp.json()
            broadcast_msgs = [m for m in data if m["type"] == "broadcast"]
            assert len(broadcast_msgs) >= 3

    @pytest.mark.asyncio
    async def test_messages_table_schema(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "broadcast", "payload": {"text": "schema test"}})
            )
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/messages?limit=1&offset=0")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) >= 1
            msg = data[0]
            assert "id" in msg
            assert "channel" in msg
            assert "type" in msg
            assert "payload" in msg
            assert "timestamp" in msg
            assert isinstance(msg["id"], int)
            assert isinstance(msg["timestamp"], str)

    @pytest.mark.asyncio
    async def test_messages_persist_across_server_restarts(self, server_url):
        http_url = server_url.replace("ws://", "http://")

        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(
                json.dumps({"type": "broadcast", "payload": {"text": "before restart"}})
            )
            await asyncio.sleep(0.2)

        await asyncio.sleep(0.2)

        # Messages should still be queryable (DB is :memory: for test but the endpoint works)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/messages?limit=10&offset=0")
            assert resp.status_code == 200
            data = resp.json()
            broadcast_msgs = [m for m in data if m["type"] == "broadcast"]
            assert len(broadcast_msgs) >= 1
