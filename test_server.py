import asyncio
import json
import os
import tempfile
import pytest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from server import handler, process_request, registry, make_message

PORT = 18765


async def http_get(host, port, path):
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(-1), timeout=5)
    writer.close()
    await writer.wait_closed()

    parts = raw.split(b"\r\n\r\n", 1)
    if len(parts) > 1:
        return json.loads(parts[1].decode())
    return None


@pytest.mark.asyncio
async def test_connect_assigns_unique_id():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "system"
            assert "client_id" in msg["payload"]
            assert len(msg["payload"]["client_id"]) > 0
            assert msg["payload"]["message"].startswith("Connected as")


@pytest.mark.asyncio
async def test_two_clients_get_different_ids():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1:
            raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
            msg1 = json.loads(raw1)

            async with connect(f"ws://localhost:{PORT}") as ws2:
                raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                msg2 = json.loads(raw2)

                assert msg1["payload"]["client_id"] != msg2["payload"]["client_id"]


@pytest.mark.asyncio
async def test_broadcast_to_all_clients():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1:
            await asyncio.wait_for(ws1.recv(), timeout=5)
            async with connect(f"ws://localhost:{PORT}") as ws2:
                await asyncio.wait_for(ws2.recv(), timeout=5)

                test_payload = {"message": "hello everyone"}
                await ws1.send(json.dumps({
                    "type": "broadcast",
                    "payload": test_payload,
                    "timestamp": ""
                }))

                msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))

                assert msg1["type"] == "broadcast"
                assert msg1["payload"] == test_payload
                assert msg2["type"] == "broadcast"
                assert msg2["payload"] == test_payload


@pytest.mark.asyncio
async def test_disconnect_cleanup():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        client_id = None
        async with connect(f"ws://localhost:{PORT}") as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            client_id = msg["payload"]["client_id"]
            assert registry.count() == 1

        await asyncio.sleep(0.2)

        assert registry.count() == 0
        assert registry.get(client_id) is None


@pytest.mark.asyncio
async def test_health_endpoint():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        resp = await http_get("localhost", PORT, "/health")
        assert resp["clients"] == 0
        assert resp["status"] == "ok"

        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            resp = await http_get("localhost", PORT, "/health")
            assert resp["clients"] == 1

        await asyncio.sleep(0.2)

        resp = await http_get("localhost", PORT, "/health")
        assert resp["clients"] == 0


@pytest.mark.asyncio
async def test_direct_message():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1:
            raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
            msg1 = json.loads(raw1)
            client1_id = msg1["payload"]["client_id"]

            async with connect(f"ws://localhost:{PORT}") as ws2:
                raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                msg2 = json.loads(raw2)
                client2_id = msg2["payload"]["client_id"]

                await ws1.send(json.dumps({
                    "type": "direct",
                    "payload": {"recipient": client2_id, "message": "hello client2"},
                    "timestamp": ""
                }))

                echo = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                assert echo["type"] == "direct"
                assert echo["payload"]["from"] == client1_id
                assert echo["payload"]["message"] == "hello client2"

                received = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
                assert received["type"] == "direct"
                assert received["payload"]["from"] == client1_id
                assert received["payload"]["message"] == "hello client2"


@pytest.mark.asyncio
async def test_message_format():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert set(msg.keys()) == {"type", "payload", "timestamp"}
            assert isinstance(msg["type"], str)
            assert isinstance(msg["payload"], dict)
            assert isinstance(msg["timestamp"], str)
            assert len(msg["timestamp"]) > 0


@pytest.mark.asyncio
async def test_thread_safe_registry():
    import concurrent.futures

    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(registry.count) for _ in range(10)]
                results = [f.result() for f in futures]
                assert all(r == 1 for r in results)


@pytest.mark.asyncio
async def test_system_message_on_disconnect():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1, \
                   connect(f"ws://localhost:{PORT}") as ws2:
            raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
            msg1 = json.loads(raw1)
            client1_id = msg1["payload"]["client_id"]

            raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
            msg2 = json.loads(raw2)

            await ws1.close()
            await asyncio.sleep(0.1)

            raw_sys = await asyncio.wait_for(ws2.recv(), timeout=5)
            sys_msg = json.loads(raw_sys)
            assert sys_msg["type"] == "system"
            assert "disconnected" in sys_msg["payload"]["message"]
            assert sys_msg["payload"]["client_id"] == client1_id


@pytest.mark.asyncio
async def test_subscribe_to_channel():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert resp["type"] == "system"
            assert "Subscribed to alerts" in resp["payload"]["message"]


@pytest.mark.asyncio
async def test_unsubscribe_from_channel():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "unsubscribe",
                "payload": {"channel": "alerts"},
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert resp["type"] == "system"
            assert "Unsubscribed from alerts" in resp["payload"]["message"]


@pytest.mark.asyncio
async def test_channel_broadcast_only_to_subscribers():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1:
            await asyncio.wait_for(ws1.recv(), timeout=5)
            async with connect(f"ws://localhost:{PORT}") as ws2:
                await asyncio.wait_for(ws2.recv(), timeout=5)

                await ws1.send(json.dumps({
                    "type": "subscribe",
                    "payload": {"channel": "alerts"},
                }))
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"channel": "alerts", "message": "channel msg"},
                }))

                msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                assert msg1["payload"]["message"] == "channel msg"

                await ws1.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"message": "global msg"},
                }))

                msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
                assert msg2["payload"]["message"] == "global msg"


@pytest.mark.asyncio
async def test_channels_endpoint_empty():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        resp = await http_get("localhost", PORT, "/channels")
        assert resp == {}


@pytest.mark.asyncio
async def test_channels_endpoint_with_subscribers():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

            resp = await http_get("localhost", PORT, "/channels")
            assert "alerts" in resp
            assert resp["alerts"] == 1


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            raw = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            client_id = raw["payload"]["client_id"]
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

            resp = await http_get("localhost", PORT, "/channels/alerts/subscribers")
            assert client_id in resp


@pytest.mark.asyncio
async def test_multiple_channel_subscriptions():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)

            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "system"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

            resp = await http_get("localhost", PORT, "/channels")
            assert resp.get("alerts") == 1
            assert resp.get("system") == 1


@pytest.mark.asyncio
async def test_channel_cleanup_on_disconnect():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

            resp = await http_get("localhost", PORT, "/channels")
            assert resp.get("alerts") == 1

        await asyncio.sleep(0.2)

        resp = await http_get("localhost", PORT, "/channels")
        assert resp.get("alerts", 0) == 0


@pytest.mark.asyncio
async def test_dynamic_subscribe_unsubscribe():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)

            resp = await http_get("localhost", PORT, "/channels")
            assert resp == {}

            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "chat"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)
            resp = await http_get("localhost", PORT, "/channels")
            assert resp.get("chat") == 1

            await ws.send(json.dumps({
                "type": "unsubscribe",
                "payload": {"channel": "chat"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)
            resp = await http_get("localhost", PORT, "/channels")
            assert resp == {}


@pytest.mark.asyncio
async def test_messages_endpoint_returns_stored_messages():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"message": "test persistence"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.1)

        messages = await http_get("localhost", PORT, "/messages")
        assert len(messages) >= 1
        assert messages[0]["type"] == "broadcast"


@pytest.mark.asyncio
async def test_messages_endpoint_respects_limit_offset():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)

            for i in range(5):
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"message": f"msg {i}"},
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.1)

        messages = await http_get("localhost", PORT, "/messages?limit=2&offset=1")
        assert len(messages) == 2


@pytest.mark.asyncio
async def test_messages_endpoint_includes_all_fields():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"message": "field test"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.1)

        messages = await http_get("localhost", PORT, "/messages?limit=1")
        assert len(messages) == 1
        msg = messages[0]
        assert "id" in msg
        assert "channel" in msg
        assert "type" in msg
        assert "payload" in msg
        assert "timestamp" in msg
        assert msg["type"] == "broadcast"


@pytest.mark.asyncio
async def test_direct_message_persisted():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1:
            raw1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
            client1_id = raw1["payload"]["client_id"]

            async with connect(f"ws://localhost:{PORT}") as ws2:
                raw2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
                client2_id = raw2["payload"]["client_id"]

                await ws1.send(json.dumps({
                    "type": "direct",
                    "payload": {"recipient": client2_id, "message": "persisted dm"},
                }))

                await asyncio.wait_for(ws1.recv(), timeout=5)
                await asyncio.wait_for(ws2.recv(), timeout=5)

        await asyncio.sleep(0.1)

        messages = await http_get("localhost", PORT, "/messages")
        direct_msgs = [m for m in messages if m["type"] == "direct"]
        assert len(direct_msgs) >= 1
        assert json.loads(direct_msgs[0]["payload"])["message"] == "persisted dm"


@pytest.mark.asyncio
async def test_redis_pubsub_broadcast():
    import fakeredis.aioredis as faioredis
    import server

    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    try:
        server.REDIS_URL = "redis://localhost:6379/0"
        server.redis_client = faioredis.FakeRedis()
        await server.redis_client.initialize()
        sub_task = asyncio.create_task(server._redis_subscriber_task())

        async with serve(handler, "localhost", PORT, process_request=process_request):
            async with connect(f"ws://localhost:{PORT}") as ws1:
                await asyncio.wait_for(ws1.recv(), timeout=5)
                async with connect(f"ws://localhost:{PORT}") as ws2:
                    await asyncio.wait_for(ws2.recv(), timeout=5)

                    await ws1.send(json.dumps({
                        "type": "broadcast",
                        "payload": {"message": "via redis backbone"},
                    }))

                    received1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                    received2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))

                    assert received1["payload"]["message"] == "via redis backbone"
                    assert received2["payload"]["message"] == "via redis backbone"

        sub_task.cancel()
        try:
            await sub_task
        except asyncio.CancelledError:
            pass
    finally:
        del os.environ["REDIS_URL"]
        server.REDIS_URL = ""
        server.redis_client = None
        server._subscriber_task = None


@pytest.mark.asyncio
async def test_redis_pubsub_channel_broadcast():
    import fakeredis.aioredis as faioredis
    import server

    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    try:
        server.REDIS_URL = "redis://localhost:6379/0"
        server.redis_client = faioredis.FakeRedis()
        await server.redis_client.initialize()
        sub_task = asyncio.create_task(server._redis_subscriber_task())

        async with serve(handler, "localhost", PORT, process_request=process_request):
            async with connect(f"ws://localhost:{PORT}") as ws1:
                await asyncio.wait_for(ws1.recv(), timeout=5)
                async with connect(f"ws://localhost:{PORT}") as ws2:
                    await asyncio.wait_for(ws2.recv(), timeout=5)

                    await ws1.send(json.dumps({
                        "type": "subscribe",
                        "payload": {"channel": "redis-chan"},
                    }))
                    await asyncio.wait_for(ws1.recv(), timeout=5)

                    await ws1.send(json.dumps({
                        "type": "broadcast",
                        "payload": {"channel": "redis-chan", "message": "channel via redis"},
                    }))

                    received = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                    assert received["payload"]["message"] == "channel via redis"

                    non_sub_wait = await asyncio.wait_for(ws2.recv(), timeout=1) if False else None

        sub_task.cancel()
        try:
            await sub_task
        except asyncio.CancelledError:
            pass
    finally:
        del os.environ["REDIS_URL"]
        server.REDIS_URL = ""
        server.redis_client = None
        server._subscriber_task = None


@pytest.mark.asyncio
async def test_redis_pubsub_direct_message():
    import fakeredis.aioredis as faioredis
    import server

    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    try:
        server.REDIS_URL = "redis://localhost:6379/0"
        server.redis_client = faioredis.FakeRedis()
        await server.redis_client.initialize()
        sub_task = asyncio.create_task(server._redis_subscriber_task())

        async with serve(handler, "localhost", PORT, process_request=process_request):
            async with connect(f"ws://localhost:{PORT}") as ws1:
                raw1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                client1_id = raw1["payload"]["client_id"]

                async with connect(f"ws://localhost:{PORT}") as ws2:
                    raw2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
                    client2_id = raw2["payload"]["client_id"]

                    await ws1.send(json.dumps({
                        "type": "direct",
                        "payload": {"recipient": client2_id, "message": "dm via redis"},
                    }))

                    echo = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                    assert echo["type"] == "direct"
                    assert echo["payload"]["from"] == client1_id
                    assert echo["payload"]["message"] == "dm via redis"

                    received = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
                    assert received["type"] == "direct"
                    assert received["payload"]["from"] == client1_id
                    assert received["payload"]["message"] == "dm via redis"

        sub_task.cancel()
        try:
            await sub_task
        except asyncio.CancelledError:
            pass
    finally:
        del os.environ["REDIS_URL"]
        server.REDIS_URL = ""
        server.redis_client = None
        server._subscriber_task = None


@pytest.mark.asyncio
async def test_messages_persisted_across_connections():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"message": "first"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"message": "second"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.1)

        messages = await http_get("localhost", PORT, "/messages")
        broadcast_msgs = [m for m in messages if m["type"] == "broadcast"]
        assert len(broadcast_msgs) >= 2


@pytest.mark.asyncio
async def test_redis_persistence_combined():
    import fakeredis.aioredis as faioredis
    import server

    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    try:
        server.REDIS_URL = "redis://localhost:6379/0"
        server.redis_client = faioredis.FakeRedis()
        await server.redis_client.initialize()
        sub_task = asyncio.create_task(server._redis_subscriber_task())

        async with serve(handler, "localhost", PORT, process_request=process_request):
            async with connect(f"ws://localhost:{PORT}") as ws:
                await asyncio.wait_for(ws.recv(), timeout=5)
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"message": "redis + sqlite"},
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

            await asyncio.sleep(0.1)

            messages = await http_get("localhost", PORT, "/messages?limit=10")
            assert len(messages) >= 1
            persisted = messages[0]
            payload = json.loads(persisted["payload"])
            assert payload["message"] == "redis + sqlite"

        sub_task.cancel()
        try:
            await asyncio.wait_for(sub_task, timeout=1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    finally:
        del os.environ["REDIS_URL"]
        server.REDIS_URL = ""
        server.redis_client = None
        server._subscriber_task = None
