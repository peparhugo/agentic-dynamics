import asyncio
import json
import os
import socket
import tempfile

import pytest
import pytest_asyncio
import redis.asyncio as redis
from websockets.asyncio.client import connect as ws_connect

from app import ClientRegistry, MessageStore, RedisMessageBus, start_server


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _ws_url(port: int) -> str:
    return f"ws://127.0.0.1:{port}"


async def _http_get(port: int, path: str) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        request = f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=5)
        parts = raw.decode().split("\r\n\r\n", 1)
        body = parts[1] if len(parts) > 1 else ""
        return json.loads(body)
    finally:
        writer.close()


async def _recv_json(ws) -> dict:
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    return json.loads(raw)


async def _drain_welcome_and_joins(wss: list) -> list[dict]:
    n = len(wss)
    welcomes = []
    for i, ws in enumerate(wss):
        msgs_to_drain = n - i
        for j in range(msgs_to_drain):
            msg = await _recv_json(ws)
            if j == 0:
                welcomes.append(msg)
    return welcomes


REDIS_URL = "redis://localhost:6379"


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _syncio(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _flush_redis():
    r = redis.from_url(REDIS_URL)
    try:
        await r.flushdb()
    finally:
        await r.close()


@pytest_asyncio.fixture
async def redis_clean():
    await _flush_redis()
    yield
    await _flush_redis()


@pytest_asyncio.fixture
async def server_with_redis(redis_clean, temp_db):
    ws_port = _find_free_port()
    http_port = _find_free_port()

    store = MessageStore(temp_db)
    await store.connect()

    reg = ClientRegistry()
    reg.set_store(store)

    bus = RedisMessageBus(REDIS_URL, reg, store)
    await bus.connect()
    reg.set_bus(bus)

    ws_server, http_server = await start_server(
        ws_host="127.0.0.1", ws_port=ws_port,
        http_host="127.0.0.1", http_port=http_port,
        reg=reg,
    )

    yield {
        "ws_port": ws_port,
        "http_port": http_port,
        "store": store,
        "registry": reg,
        "bus": bus,
    }

    ws_server.close()
    http_server.close()
    await ws_server.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    await bus.close()
    await store.close()


@pytest_asyncio.fixture
async def two_servers(redis_clean, temp_db):
    store1 = MessageStore(temp_db)
    await store1.connect()

    reg1 = ClientRegistry()
    reg1.set_store(store1)
    bus1 = RedisMessageBus(REDIS_URL, reg1, store1)
    await bus1.connect()
    reg1.set_bus(bus1)

    ws_port1 = _find_free_port()
    http_port1 = _find_free_port()
    ws1, http1 = await start_server(
        ws_host="127.0.0.1", ws_port=ws_port1,
        http_host="127.0.0.1", http_port=http_port1,
        reg=reg1,
    )

    store2 = MessageStore(temp_db)
    await store2.connect()

    reg2 = ClientRegistry()
    reg2.set_store(store2)
    bus2 = RedisMessageBus(REDIS_URL, reg2, store2)
    await bus2.connect()
    reg2.set_bus(bus2)

    ws_port2 = _find_free_port()
    http_port2 = _find_free_port()
    ws2, http2 = await start_server(
        ws_host="127.0.0.1", ws_port=ws_port2,
        http_host="127.0.0.1", http_port=http_port2,
        reg=reg2,
    )

    yield {
        "s1": {"ws_port": ws_port1, "http_port": http_port1},
        "s2": {"ws_port": ws_port2, "http_port": http_port2},
    }

    for srv in [ws1, ws2]:
        srv.close()
    for srv in [http1, http2]:
        srv.close()
    for srv in [ws1, ws2]:
        await srv.wait_closed()
    for srv in [http1, http2]:
        await srv.wait_closed()
    await bus1.close()
    await bus2.close()
    await store1.close()
    await store2.close()


# ── Redis pub/sub integration tests ──


@pytest.mark.asyncio
async def test_redis_client_connects_and_receives_id(server_with_redis):
    async with ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws:
        data = await _recv_json(ws)
        assert data["type"] == "system"
        assert "client_id" in data["payload"]
        assert data["payload"].get("connected") is True


@pytest.mark.asyncio
async def test_redis_broadcast(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws3,
    ):
        await _drain_welcome_and_joins([ws1, ws2, ws3])

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"msg": "hello_redis"}}))

        msg2 = await _recv_json(ws2)
        msg3 = await _recv_json(ws3)

        assert msg2["type"] == "broadcast"
        assert msg2["payload"] == {"msg": "hello_redis"}
        assert msg3["type"] == "broadcast"
        assert msg3["payload"] == {"msg": "hello_redis"}


@pytest.mark.asyncio
async def test_redis_direct_message(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
    ):
        welcomes = await _drain_welcome_and_joins([ws1, ws2])
        target = welcomes[0]["payload"]["client_id"]

        await ws2.send(json.dumps({
            "type": "direct",
            "target": target,
            "payload": {"private": True},
        }))

        msg = await _recv_json(ws1)
        assert msg["type"] == "direct"
        assert msg["payload"] == {"private": True}


@pytest.mark.asyncio
async def test_redis_channel_message(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws3,
    ):
        await _drain_welcome_and_joins([ws1, ws2, ws3])

        await ws1.send(json.dumps({"type": "subscribe", "channel": "redischan"}))
        await ws3.send(json.dumps({"type": "subscribe", "channel": "redischan"}))
        await asyncio.sleep(0.15)

        await ws2.send(json.dumps({
            "type": "broadcast",
            "channel": "redischan",
            "payload": {"msg": "channel_redis"},
        }))

        msg1 = await _recv_json(ws1)
        assert msg1["channel"] == "redischan"
        assert msg1["payload"] == {"msg": "channel_redis"}

        msg3 = await _recv_json(ws3)
        assert msg3["channel"] == "redischan"
        assert msg3["payload"] == {"msg": "channel_redis"}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.5)


@pytest.mark.asyncio
async def test_redis_persists_client_state(server_with_redis):
    r = redis.from_url(REDIS_URL)
    try:
        async with ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws:
            welcome = await _recv_json(ws)
            client_id = welcome["payload"]["client_id"]

            await asyncio.sleep(0.1)

            clients = await r.hgetall("clients")
            assert any(cid.decode() == client_id for cid in clients)

            await ws.send(json.dumps({"type": "subscribe", "channel": "persist_chan"}))
            await asyncio.sleep(0.1)

            subs = await r.smembers("sub:persist_chan")
            assert any(s.decode() == client_id for s in subs)

        await asyncio.sleep(0.1)
        clients = await r.hgetall("clients")
        assert not any(cid.decode() == client_id for cid in clients)
    finally:
        await r.close()


# ── Cross-server Redis pub/sub integration tests ──


@pytest.mark.asyncio
async def test_cross_server_broadcast(two_servers):
    s1 = two_servers["s1"]
    s2 = two_servers["s2"]

    async with (
        ws_connect(await _ws_url(s1["ws_port"])) as ws_sender,
        ws_connect(await _ws_url(s2["ws_port"])) as ws_receiver,
    ):
        await _recv_json(ws_sender)
        await _recv_json(ws_receiver)

        await ws_sender.send(json.dumps({"type": "broadcast", "payload": {"cross": "server"}}))

        msg = await _recv_json(ws_receiver)
        assert msg["payload"] == {"cross": "server"}


@pytest.mark.asyncio
async def test_cross_server_channel_message(two_servers):
    s1 = two_servers["s1"]
    s2 = two_servers["s2"]

    async with (
        ws_connect(await _ws_url(s1["ws_port"])) as ws_sub,
        ws_connect(await _ws_url(s2["ws_port"])) as ws_sender,
    ):
        await _recv_json(ws_sub)
        await _recv_json(ws_sender)

        await ws_sub.send(json.dumps({"type": "subscribe", "channel": "cross_ch"}))
        await asyncio.sleep(0.15)

        await ws_sender.send(json.dumps({
            "type": "broadcast",
            "channel": "cross_ch",
            "payload": {"cross": "channel"},
        }))

        msg = await _recv_json(ws_sub)
        assert msg["payload"] == {"cross": "channel"}


@pytest.mark.asyncio
async def test_cross_server_direct_message(two_servers):
    s1 = two_servers["s1"]
    s2 = two_servers["s2"]

    async with (
        ws_connect(await _ws_url(s1["ws_port"])) as ws_target,
        ws_connect(await _ws_url(s2["ws_port"])) as ws_sender,
    ):
        w1 = await _recv_json(ws_target)
        await _recv_json(ws_sender)
        target_id = w1["payload"]["client_id"]

        await ws_sender.send(json.dumps({
            "type": "direct",
            "target": target_id,
            "payload": {"cross": "direct"},
        }))

        msg = await _recv_json(ws_target)
        assert msg["payload"] == {"cross": "direct"}


@pytest.mark.asyncio
async def test_cross_server_multiple_messages(two_servers):
    s1 = two_servers["s1"]
    s2 = two_servers["s2"]

    async with (
        ws_connect(await _ws_url(s1["ws_port"])) as ws1,
        ws_connect(await _ws_url(s2["ws_port"])) as ws2,
    ):
        await _recv_json(ws1)
        await _recv_json(ws2)

        for i in range(5):
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"seq": i}}))

        received = []
        for _ in range(5):
            received.append(await _recv_json(ws2))

        seqs = [m["payload"]["seq"] for m in received]
        assert sorted(seqs) == [0, 1, 2, 3, 4]


# ── Message persistence tests ──


@pytest.mark.asyncio
async def test_messages_persisted_to_sqlite(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"msg": "persisted"}}))
        await _recv_json(ws2)

    await asyncio.sleep(0.2)

    result = await _http_get(server_with_redis["http_port"], "/messages?limit=50&offset=0")
    broadcast_msgs = [m for m in result if m["type"] == "broadcast"]
    assert len(broadcast_msgs) >= 1
    broadcast_payloads = [m["payload"] for m in broadcast_msgs]
    assert {"msg": "persisted"} in broadcast_payloads


@pytest.mark.asyncio
async def test_messages_endpoint_pagination(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        for i in range(15):
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
            await _recv_json(ws2)

    await asyncio.sleep(0.2)

    page1 = await _http_get(server_with_redis["http_port"], "/messages?limit=5&offset=0")
    page2 = await _http_get(server_with_redis["http_port"], "/messages?limit=5&offset=5")

    broadcast_p1 = [m for m in page1 if m["type"] == "broadcast"]
    broadcast_p2 = [m for m in page2 if m["type"] == "broadcast"]

    assert len(broadcast_p1) <= 5
    assert len(broadcast_p2) <= 5
    p1_ids = {m["id"] for m in broadcast_p1}
    p2_ids = {m["id"] for m in broadcast_p2}
    assert p1_ids.isdisjoint(p2_ids)


@pytest.mark.asyncio
async def test_messages_endpoint_default_limit(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"x": 42}}))
        await _recv_json(ws2)

    await asyncio.sleep(0.2)

    result = await _http_get(server_with_redis["http_port"], "/messages")
    broadcast_msgs = [m for m in result if m["type"] == "broadcast"]
    assert len(broadcast_msgs) >= 1


@pytest.mark.asyncio
async def test_messages_store_channel_field(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send(json.dumps({"type": "subscribe", "channel": "store_chan"}))
        await asyncio.sleep(0.05)

        await ws2.send(json.dumps({
            "type": "broadcast",
            "channel": "store_chan",
            "payload": {"stored": True},
        }))
        await _recv_json(ws1)

    await asyncio.sleep(0.2)

    result = await _http_get(server_with_redis["http_port"], "/messages?limit=100&offset=0")
    channel_msgs = [m for m in result if m["channel"] == "store_chan"]
    assert len(channel_msgs) >= 1
    assert channel_msgs[0]["payload"] == {"stored": True}
    assert channel_msgs[0]["type"] == "broadcast"


@pytest.mark.asyncio
async def test_messages_persist_direct(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
    ):
        welcomes = await _drain_welcome_and_joins([ws1, ws2])
        target = welcomes[0]["payload"]["client_id"]

        await ws2.send(json.dumps({
            "type": "direct",
            "target": target,
            "payload": {"dm": True},
        }))
        await _recv_json(ws1)

    await asyncio.sleep(0.2)

    result = await _http_get(server_with_redis["http_port"], "/messages?limit=100&offset=0")
    direct_msgs = [m for m in result if m["type"] == "direct"]
    assert len(direct_msgs) >= 1
    assert direct_msgs[0]["payload"] == {"dm": True}


@pytest.mark.asyncio
async def test_messages_all_have_required_fields(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send(json.dumps({
            "type": "custom_type",
            "payload": {"custom": "data", "nested": {"a": 1}},
        }))
        await _recv_json(ws2)

    await asyncio.sleep(0.2)

    result = await _http_get(server_with_redis["http_port"], "/messages?limit=100&offset=0")
    custom_msgs = [m for m in result if m["type"] == "custom_type"]
    assert len(custom_msgs) >= 1
    msg = custom_msgs[0]
    assert "id" in msg
    assert "channel" in msg
    assert "type" in msg
    assert "payload" in msg
    assert "timestamp" in msg
    assert isinstance(msg["id"], int)
    assert isinstance(msg["payload"], dict)


@pytest.mark.asyncio
async def test_messages_empty_without_activity(server_with_redis):
    result = await _http_get(server_with_redis["http_port"], "/messages")
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_to_all_subscribers(server_with_redis):
    async with (
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws1,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws2,
        ws_connect(await _ws_url(server_with_redis["ws_port"])) as ws3,
    ):
        awaits = await _drain_welcome_and_joins([ws1, ws2, ws3])

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"to": "everyone"}}))

        msgs = [await _recv_json(ws2), await _recv_json(ws3)]
        for m in msgs:
            assert m["payload"] == {"to": "everyone"}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.5)
