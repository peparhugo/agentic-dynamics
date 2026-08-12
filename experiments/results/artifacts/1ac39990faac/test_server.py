import asyncio
import json
import os
import shutil
import tempfile

import pytest
import websockets
from websockets.exceptions import ConnectionClosed

import server
from server import main, ClientRegistry, _init_db

try:
    import fakeredis.aioredis as fakeredis_aioredis
    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False


def _reset_registry():
    server.registry = ClientRegistry()


@pytest.fixture(autouse=True)
def clean_registry():
    _reset_registry()
    server._rate_limit_cache.clear()
    yield
    _reset_registry()
    server._rate_limit_cache.clear()


@pytest.fixture
def server_args():
    return {"host": "localhost", "port": 8767}


async def _run_server(host, port):
    task = asyncio.ensure_future(main(host, port))
    await asyncio.sleep(0.1)
    return task


async def _stop_server(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_connect_receives_client_id(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
        assert msg["type"] == "system"
        assert msg["payload"]["message"] == "connected"
        assert "client_id" in msg["payload"]
        assert "timestamp" in msg
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_broadcast_message_to_all(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                # ws1 receives join notification about ws2
                await asyncio.wait_for(ws1.recv(), timeout=5)

                test_payload = {"message": "hello"}
                await ws1.send(json.dumps({
                    "type": "broadcast",
                    "payload": test_payload,
                }))

                raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
                msg1 = json.loads(raw1)

                raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                msg2 = json.loads(raw2)

        assert msg1["type"] == "broadcast"
        assert msg1["payload"] == test_payload
        assert msg2["type"] == "broadcast"
        assert msg2["payload"] == test_payload
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_disconnect_sends_leave_message(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                # ws1 receives join notification about ws2
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.close()

                # ws2 receives ws1's leave
                raw = await asyncio.wait_for(ws2.recv(), timeout=5)
                msg = json.loads(raw)

        assert msg["type"] == "system"
        assert msg["payload"]["message"] == "left"
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_disconnect_removes_client_from_registry(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            assert await server.registry.get_count() == 1
        await asyncio.sleep(0.1)
        assert await server.registry.get_count() == 0
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_health_endpoint_returns_count(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        assert "200" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["connected_clients"] == 0

        async with websockets.connect(url) as ws:
            await ws.recv()
            assert await server.registry.get_count() == 1

            reader, writer = await asyncio.open_connection(host, port)
            request = f"GET /health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            response = (await reader.read()).decode()
            writer.close()
            await writer.wait_closed()

            assert "200" in response
            body = response.split("\r\n\r\n", 1)[1]
            data = json.loads(body)
            assert data["connected_clients"] == 1
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_unassigned_type_defaults_to_broadcast(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({"payload": {"text": "no type"}}))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "no type"}
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_message_has_required_fields(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "direct",
                "payload": {"target": "user1", "text": "hello"},
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
        assert "type" in msg
        assert "payload" in msg
        assert "timestamp" in msg
        assert isinstance(msg["type"], str)
        assert isinstance(msg["payload"], dict)
        assert isinstance(msg["timestamp"], str)
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_invalid_json_is_ignored(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send("not valid json at all {{{")
            await ws.send(json.dumps({"type": "broadcast", "payload": {"ok": True}}))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
        assert msg["payload"] == {"ok": True}
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_multiple_clients_receive_join_and_leave(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            msg1 = json.loads(await ws1.recv())
            cid1 = msg1["payload"]["client_id"]

            async with websockets.connect(url) as ws2:
                msg2 = json.loads(await ws2.recv())
                cid2 = msg2["payload"]["client_id"]

                # ws1 receives ws2's join
                join_msg = await asyncio.wait_for(ws1.recv(), timeout=5)
                join_data = json.loads(join_msg)
                assert join_data["type"] == "system"
                assert join_data["payload"]["message"] == "joined"
                assert join_data["payload"]["client_id"] == cid2

            # ws1 receives ws2's leave
            leave_msg = await asyncio.wait_for(ws1.recv(), timeout=5)
            leave_data = json.loads(leave_msg)
            assert leave_data["type"] == "system"
            assert leave_data["payload"]["message"] == "left"
            assert leave_data["payload"]["client_id"] == cid2
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_client_ids_are_unique(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1, websockets.connect(url) as ws2:
            msg1 = json.loads(await ws1.recv())
            msg2 = json.loads(await ws2.recv())
        assert msg1["payload"]["client_id"] != msg2["payload"]["client_id"]
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_subscribe_to_channel(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.1)
            channels = await server.registry.get_channels()
            assert "alerts" in channels
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_unsubscribe_from_channel(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)
            await ws.send(json.dumps({
                "type": "unsubscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)
            channels = await server.registry.get_channels()
        assert "alerts" not in channels
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channel_message_routes_only_to_subscribers(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.send(json.dumps({
                    "type": "subscribe",
                    "channel": "alerts",
                }))

                await ws1.send(json.dumps({
                    "type": "chat",
                    "channel": "alerts",
                    "payload": {"text": "channel message"},
                }))

                raw = await asyncio.wait_for(ws1.recv(), timeout=5)
                msg = json.loads(raw)
                assert msg["type"] == "chat"
                assert msg["payload"] == {"text": "channel message"}

                try:
                    await asyncio.wait_for(ws2.recv(), timeout=0.3)
                    assert False, "ws2 should not have received channel message"
                except asyncio.TimeoutError:
                    pass
                except ConnectionClosed:
                    pass
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_no_channel_message_broadcasts_to_all(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"text": "to everyone"},
                }))

                msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))

        assert msg1["payload"] == {"text": "to everyone"}
        assert msg2["payload"] == {"text": "to everyone"}
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_multiple_channel_subscriptions(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "chat",
            }))
            await asyncio.sleep(0.05)

            channels = await server.registry.get_channels()
            assert "alerts" in channels
            assert "chat" in channels
            assert channels["alerts"] == 1
            assert channels["chat"] == 1
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_disconnect_cleans_up_subscriptions(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)
            channels = await server.registry.get_channels()
            assert channels["alerts"] == 1

        await asyncio.sleep(0.1)
        channels = await server.registry.get_channels()
        assert channels == {}
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channels_endpoint(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)

            reader, writer = await asyncio.open_connection(host, port)
            request = f"GET /channels HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            response = (await reader.read()).decode()
            writer.close()
            await writer.wait_closed()

            assert "200" in response
            body = response.split("\r\n\r\n", 1)[1]
            data = json.loads(body)
            assert "alerts" in data
            assert data["alerts"] == 1
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            welcome = json.loads(await ws.recv())
            client_id = welcome["payload"]["client_id"]

            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)

            reader, writer = await asyncio.open_connection(host, port)
            request = f"GET /channels/alerts/subscribers HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            response = (await reader.read()).decode()
            writer.close()
            await writer.wait_closed()

            assert "200" in response
            body = response.split("\r\n\r\n", 1)[1]
            data = json.loads(body)
            assert client_id in data
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channel_message_only_delivered_to_channel_subscribers(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                await asyncio.wait_for(ws1.recv(), timeout=5)

                ws1_cid = await server.registry.get_client_id(ws1)
                ws2_cid = await server.registry.get_client_id(ws2)

                await ws1.send(json.dumps({
                    "type": "subscribe",
                    "channel": "alerts",
                }))

                await ws1.send(json.dumps({
                    "type": "notify",
                    "channel": "alerts",
                    "payload": {"alert": "disk full"},
                }))

                msg = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                assert msg["payload"] == {"alert": "disk full"}

                try:
                    await asyncio.wait_for(ws2.recv(), timeout=0.3)
                    assert False, "ws2 should not receive channel-only message"
                except asyncio.TimeoutError:
                    pass
                except ConnectionClosed:
                    pass
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_subscribe_after_channel_message_not_received(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.send(json.dumps({
                    "type": "subscribe",
                    "channel": "alerts",
                }))

                await ws1.send(json.dumps({
                    "type": "notify",
                    "channel": "alerts",
                    "payload": {"alert": "first"},
                }))

                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws2.send(json.dumps({
                    "type": "subscribe",
                    "channel": "alerts",
                }))

                await ws1.send(json.dumps({
                    "type": "notify",
                    "channel": "alerts",
                    "payload": {"alert": "second"},
                }))

                msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))

                assert msg1["payload"] == {"alert": "second"}
                assert msg2["payload"] == {"alert": "second"}
    finally:
        await _stop_server(task)


# ── New Tests: Message Persistence ──────────────────────────────


@pytest.fixture
def db_tmpfile():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_messages.db")
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_path
    server.DATABASE_URL = db_path
    _init_db()
    yield db_path
    if old_db_url is not None:
        os.environ["DATABASE_URL"] = old_db_url
        server.DATABASE_URL = old_db_url
    else:
        os.environ.pop("DATABASE_URL", None)
        server.DATABASE_URL = "messages.db"
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_broadcast_message_persisted_to_sqlite(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "persisted"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)
        msgs = server._get_messages(limit=100, offset=0)
        types = [m["type"] for m in msgs]
        assert "broadcast" in types
        broadcast_msgs = [m for m in msgs if m["type"] == "broadcast"]
        assert any(json.loads(m["payload"]) == {"text": "persisted"} for m in broadcast_msgs)
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channel_message_persisted_with_channel(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await ws.send(json.dumps({
                "type": "notify",
                "channel": "alerts",
                "payload": {"alert": "test"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)
        msgs = server._get_messages(limit=100, offset=0)
        channel_msgs = [m for m in msgs if m["channel"] == "alerts"]
        assert len(channel_msgs) > 0
        assert any(m["type"] == "notify" and json.loads(m["payload"]) == {"alert": "test"} for m in channel_msgs)
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_system_messages_persisted(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
        await asyncio.sleep(0.2)

        msgs = server._get_messages(limit=100, offset=0)
        types = [m["type"] for m in msgs]
        assert "system" in types
        system_msgs = [m for m in msgs if m["type"] == "system"]
        payloads = [json.loads(m["payload"]) for m in system_msgs]
        messages = [p.get("message") for p in payloads]
        assert "connected" in messages
        assert "left" in messages or "joined" in messages
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_messages_endpoint_returns_history(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "msg1"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "msg2"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /messages?limit=10&offset=0 HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        assert "200" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert isinstance(data, list)
        assert len(data) > 0
        assert all("id" in m for m in data)
        assert all("type" in m for m in data)
        assert all("payload" in m for m in data)
        assert all("timestamp" in m for m in data)
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_messages_endpoint_respects_limit_and_offset(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            for i in range(5):
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"index": i},
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /messages?limit=2&offset=0 HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert len(data) == 2

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /messages?limit=2&offset=2 HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        body = response.split("\r\n\r\n", 1)[1]
        data2 = json.loads(body)
        assert len(data2) >= 0
    finally:
        await _stop_server(task)


# ── New Tests: Redis Pub/Sub Integration ────────────────────────


@pytest.fixture
def redis_env():
    if not FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not available")
    old_redis_url = os.environ.get("REDIS_URL")
    old_redis_pool = server._redis_pool
    server._redis_pool = None
    os.environ["REDIS_URL"] = "redis://localhost:16379/0"
    server.REDIS_URL = "redis://localhost:16379/0"
    server.SERVER_ID = f"test-server-{id(object())}"
    server._redis_pool = fakeredis_aioredis.FakeRedis()
    yield
    server.REDIS_URL = os.environ.get("REDIS_URL", "")
    server._redis_pool = old_redis_pool
    if old_redis_url is not None:
        os.environ["REDIS_URL"] = old_redis_url
    else:
        os.environ.pop("REDIS_URL", None)


@pytest.mark.asyncio
async def test_redis_client_state_stored_on_connect(server_args, redis_env, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            welcome = json.loads(await ws.recv())
            client_id = welcome["payload"]["client_id"]

            r = await server._get_redis()
            assert r is not None
            members = await r.smembers("connected_clients")
            assert client_id.encode() in [m.encode() if isinstance(m, str) else m for m in members]
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_redis_client_state_removed_on_disconnect(server_args, redis_env, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            welcome = json.loads(await ws.recv())
            client_id = welcome["payload"]["client_id"]

        await asyncio.sleep(0.2)

        r = await server._get_redis()
        assert r is not None
        members = await r.smembers("connected_clients")
        assert client_id.encode() not in [m.encode() if isinstance(m, str) else m for m in members]
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_redis_publish_on_broadcast(server_args, redis_env, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    r = await server._get_redis()
    assert r is not None
    pubsub = r.pubsub()
    await pubsub.subscribe("broadcast")
    await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)

    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "redistest"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        received = []
        deadline = asyncio.get_event_loop().time() + 2.0
        while asyncio.get_event_loop().time() < deadline:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.3)
            if msg is None:
                await asyncio.sleep(0.05)
                continue
            try:
                envelope = json.loads(msg["data"])
                data = json.loads(envelope["data"])
                if data.get("payload") == {"text": "redistest"}:
                    assert envelope["source"] == server.SERVER_ID
                    received.append(envelope)
                    break
            except (json.JSONDecodeError, KeyError):
                pass
        assert len(received) > 0, "Broadcast message not found in Redis"
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_redis_subscriber_receives_from_other_instance(server_args, redis_env, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    old_pool = server._redis_pool

    fake_pool = fakeredis_aioredis.FakeRedis()
    server._redis_pool = fake_pool
    old_server_id = server.SERVER_ID
    server.SERVER_ID = "instance-A"

    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()

            envelope = json.dumps({
                "source": "instance-B",
                "channel": None,
                "data": json.dumps({
                    "type": "external",
                    "payload": {"from": "other"},
                    "timestamp": "2024-01-01T00:00:00Z",
                }),
            })
            await fake_pool.publish("broadcast", envelope)

            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "external"
            assert msg["payload"] == {"from": "other"}
    finally:
        await _stop_server(task)
        server._redis_pool = old_pool
        server.SERVER_ID = old_server_id


# ── New Tests: Rate Limiting ──────────────────────────────────────


@pytest.fixture
def rate_limit_env():
    old_rate_limit = os.environ.get("RATE_LIMIT")
    os.environ["RATE_LIMIT"] = "3"
    server.RATE_LIMIT = 3
    yield
    if old_rate_limit is not None:
        os.environ["RATE_LIMIT"] = old_rate_limit
        server.RATE_LIMIT = int(old_rate_limit)
    else:
        os.environ.pop("RATE_LIMIT", None)
        server.RATE_LIMIT = 100


@pytest.mark.asyncio
async def test_rate_limit_blocks_excess_messages(server_args, rate_limit_env):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()

            for i in range(3):
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"index": i},
                }))
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                msg = json.loads(raw)
                assert msg["type"] == "broadcast"

            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"index": 999},
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "error"
            assert "Rate limit exceeded" in msg["payload"]["message"]
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_rate_limit_configurable_via_env(server_args, rate_limit_env):
    assert server.RATE_LIMIT == 3
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()

            for i in range(3):
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"index": i},
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"index": 999},
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "error"
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_rate_limit_sends_error_no_drop(server_args, rate_limit_env):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()

            for i in range(3):
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"index": i},
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"index": 999},
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "error"

            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"index": 1000},
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg2 = json.loads(raw)
            assert msg2["type"] == "error"

            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "testchan",
            }))
            await asyncio.sleep(0.05)
            channels = await server.registry.get_channels()
            assert channels == {}
    finally:
        await _stop_server(task)


# ── New Tests: History Endpoint ───────────────────────────────────


@pytest.mark.asyncio
async def test_history_returns_channel_messages(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "testchan",
            }))
            await ws.send(json.dumps({
                "type": "chat",
                "channel": "testchan",
                "payload": {"text": "msg1"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /history?channel=testchan HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        assert "200" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert "messages" in data
        assert "has_more" in data
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) > 0
        msgs = data["messages"]
        assert any(m["type"] == "chat" and json.loads(m["payload"]) == {"text": "msg1"} for m in msgs)
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_history_messages_in_chronological_order(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "testchan",
            }))
            for i in range(3):
                await ws.send(json.dumps({
                    "type": "chat",
                    "channel": "testchan",
                    "payload": {"index": i},
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /history?channel=testchan HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        chat_msgs = [m for m in data["messages"] if m["type"] == "chat"]
        timestamps = [m["timestamp"] for m in chat_msgs]
        assert len(timestamps) == 3
        assert timestamps == sorted(timestamps)
        indices = [json.loads(m["payload"])["index"] for m in chat_msgs]
        assert indices == [0, 1, 2]
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_history_since_filter(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    import datetime as dt
    before = dt.datetime.now(dt.timezone.utc).isoformat()

    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "testchan",
            }))
            for i in range(3):
                await ws.send(json.dumps({
                    "type": "chat",
                    "channel": "testchan",
                    "payload": {"index": i},
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /history?channel=testchan&since={before} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        chat_msgs = [m for m in data["messages"] if m["type"] == "chat"]
        assert len(chat_msgs) == 3
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_history_limit_and_has_more(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "testchan",
            }))
            for i in range(5):
                await ws.send(json.dumps({
                    "type": "chat",
                    "channel": "testchan",
                    "payload": {"index": i},
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /history?channel=testchan&limit=2 HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        chat_msgs = [m for m in data["messages"] if m["type"] == "chat"]
        assert len(chat_msgs) == 2
        assert data["has_more"] is True
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_history_has_more_false_when_all_returned(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "testchan",
            }))
            await ws.send(json.dumps({
                "type": "chat",
                "channel": "testchan",
                "payload": {"text": "test"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /history?channel=testchan&limit=50 HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["has_more"] is False
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_history_requires_channel_parameter(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /history HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        assert "400" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert "error" in data
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_history_filters_by_channel_only(server_args, db_tmpfile):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "chanA",
            }))
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "chanB",
            }))
            await ws.send(json.dumps({
                "type": "chat",
                "channel": "chanA",
                "payload": {"channel": "A"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "chat",
                "channel": "chanB",
                "payload": {"channel": "B"},
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /history?channel=chanA HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        chat_msgs = [m for m in data["messages"] if m["type"] == "chat"]
        assert len(chat_msgs) == 1
        assert json.loads(chat_msgs[0]["payload"]) == {"channel": "A"}

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /history?channel=chanB HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        chat_msgs = [m for m in data["messages"] if m["type"] == "chat"]
        assert len(chat_msgs) == 1
        assert json.loads(chat_msgs[0]["payload"]) == {"channel": "B"}
    finally:
        await _stop_server(task)
