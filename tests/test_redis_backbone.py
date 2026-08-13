"""Integration tests for the Redis pub/sub backbone and SQLite persistence."""

import asyncio
import json

import fakeredis.aioredis
import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from server import BUS_CHANNEL, CLIENTS_KEY, NotificationServer


async def http_get(host: str, port: int, path: str) -> str:
    """Issue a minimal HTTP/1.1 GET and return the raw response text."""
    reader, writer = await asyncio.open_connection(host, port)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    writer.write(request.encode("ascii"))
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    return raw.decode("utf-8", "replace")


def parse_json(raw: str) -> dict:
    status_line, _, body = raw.partition("\r\n\r\n")
    assert status_line.split(" ")[1] == "200", status_line
    return json.loads(body)


async def recv_json(ws):
    return json.loads(await ws.recv())


async def subscribe(ws, channel):
    await ws.send(
        json.dumps({"type": "subscribe", "payload": {"channel": channel}})
    )
    return await recv_json(ws)


@pytest.fixture
def shared_redis():
    """A fake Redis server shared by every broker in a test."""
    return fakeredis.FakeServer()


def make_server(shared_redis, **kwargs):
    client = fakeredis.aioredis.FakeRedis(server=shared_redis)
    return NotificationServer(port=0, redis_client=client, **kwargs)


async def start_servers(shared_redis, count=1):
    servers = [make_server(shared_redis) for _ in range(count)]
    for srv in servers:
        await srv.start()
    return servers


async def stop_servers(servers):
    for srv in servers:
        await srv.stop()


async def uri(srv):
    return f"ws://{srv.host}:{srv.bound_port}"


# ── Redis pub/sub backbone ─────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_broadcast_reaches_clients_on_other_instances(shared_redis):
    srv_a, srv_b = await start_servers(shared_redis, count=2)
    try:
        async with connect(await uri(srv_a)) as a, connect(await uri(srv_b)) as b:
            await recv_json(a)
            await recv_json(b)
            await subscribe(b, "alerts")

            await a.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"message": "cross-instance"},
                    }
                )
            )
            received = await asyncio.wait_for(recv_json(b), timeout=2)
            assert received["type"] == "broadcast"
            assert received["channel"] == "alerts"
            assert received["payload"]["message"] == "cross-instance"
    finally:
        await stop_servers([srv_a, srv_b])


@pytest.mark.asyncio
async def test_redis_broadcast_also_delivers_locally(shared_redis):
    srv_a = (await start_servers(shared_redis))[0]
    try:
        async with connect(await uri(srv_a)) as a:
            await recv_json(a)
            await subscribe(a, "alerts")
            await a.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"message": "local"},
                    }
                )
            )
            received = await asyncio.wait_for(recv_json(a), timeout=2)
            assert received["payload"]["message"] == "local"
    finally:
        await stop_servers([srv_a])


@pytest.mark.asyncio
async def test_redis_broadcast_is_published_on_bus(shared_redis):
    srv = (await start_servers(shared_redis))[0]
    spy = fakeredis.aioredis.FakeRedis(server=shared_redis)
    pubsub = spy.pubsub()
    await pubsub.subscribe(BUS_CHANNEL)
    try:
        async with connect(await uri(srv)) as a:
            await recv_json(a)
            await a.send(json.dumps({"type": "broadcast", "payload": {"n": 42}}))
            raw = await asyncio.wait_for(pubsub.get_message(timeout=2), timeout=2)
            raw = await asyncio.wait_for(pubsub.get_message(timeout=2), timeout=2)
            assert raw["type"] == "message"
            envelope = json.loads(raw["data"])
            assert envelope["kind"] == "broadcast"
            assert envelope["message"]["type"] == "broadcast"
            assert envelope["message"]["payload"] == {"n": 42}
    finally:
        await pubsub.close()
        await stop_servers([srv])


@pytest.mark.asyncio
async def test_redis_direct_delivers_across_instances(shared_redis):
    srv_a, srv_b = await start_servers(shared_redis, count=2)
    try:
        async with connect(await uri(srv_a)) as a, connect(await uri(srv_b)) as b:
            msg_a = await recv_json(a)
            msg_b = await recv_json(b)
            id_b = msg_b["payload"]["client_id"]

            await a.send(
                json.dumps(
                    {"type": "direct", "payload": {"to": id_b, "message": "hi"}}
                )
            )
            received = await asyncio.wait_for(recv_json(b), timeout=2)
            assert received["type"] == "direct"
            assert received["payload"]["message"] == "hi"
    finally:
        await stop_servers([srv_a, srv_b])


# ── Client connection state in Redis ───────────────────────────


@pytest.mark.asyncio
async def test_redis_client_state_tracks_connections(shared_redis):
    srv = (await start_servers(shared_redis))[0]
    observer = fakeredis.aioredis.FakeRedis(server=shared_redis)
    try:
        async with connect(await uri(srv)) as a:
            msg = await recv_json(a)
            client_id = msg["payload"]["client_id"]
            state = await srv.broker.client_state()
            assert client_id in state
        await asyncio.sleep(0.1)
        state = await srv.broker.client_state()
        assert client_id not in state
    finally:
        await stop_servers([srv])


@pytest.mark.asyncio
async def test_redis_client_state_survives_server_restart(shared_redis):
    srv = (await start_servers(shared_redis))[0]
    await srv.broker.set_client(
        "client-99", json.dumps({"connected_at": "2026-01-01T00:00:00+00:00"})
    )
    await srv.stop()

    srv2 = make_server(shared_redis)
    await srv2.start()
    try:
        observer = fakeredis.aioredis.FakeRedis(server=shared_redis)
        state = await observer.hgetall(CLIENTS_KEY)
        assert b"client-99" in state
    finally:
        await srv2.stop()


# ── Message persistence ────────────────────────────────────────


@pytest.mark.asyncio
async def test_messages_persisted_to_sqlite(tmp_path):
    srv = NotificationServer(
        port=0, database_url=f"sqlite:///{tmp_path / 'history.db'}"
    )
    await srv.start()
    try:
        async with connect(f"ws://{srv.host}:{srv.bound_port}") as a:
            await recv_json(a)
            await subscribe(a, "alerts")
            await a.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"message": "stored"},
                    }
                )
            )
            await asyncio.wait_for(recv_json(a), timeout=2)

        raw = await http_get(srv.host, srv.bound_port, "/messages?limit=50&offset=0")
        body = parse_json(raw)
        types = {m["type"] for m in body["messages"]}
        assert "broadcast" in types
        stored = next(
            m for m in body["messages"] if m["type"] == "broadcast"
        )
        assert stored["channel"] == "alerts"
        assert stored["payload"] == {"message": "stored"}
        assert "timestamp" in stored
        assert "id" in stored
        assert body["total"] >= 1
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_messages_endpoint_pagination(tmp_path):
    srv = NotificationServer(
        port=0, database_url=f"sqlite:///{tmp_path / 'history.db'}"
    )
    await srv.start()
    try:
        for i in range(5):
            await srv.broadcast({"i": i})
        raw = await http_get(
            srv.host, srv.bound_port, "/messages?limit=2&offset=1"
        )
        body = parse_json(raw)
        assert body["limit"] == 2
        assert body["offset"] == 1
        assert len(body["messages"]) == 2
        assert body["total"] == 5
        assert [m["payload"]["i"] for m in body["messages"]] == [3, 2]
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_messages_survive_server_restart(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'history.db'}"
    srv = NotificationServer(port=0, database_url=db_url)
    await srv.start()
    await srv.broadcast({"message": "before-restart"})
    await srv.stop()

    srv2 = NotificationServer(port=0, database_url=db_url)
    await srv2.start()
    try:
        raw = await http_get(srv2.host, srv2.bound_port, "/messages")
        body = parse_json(raw)
        assert any(
            m["type"] == "broadcast"
            and m["payload"] == {"message": "before-restart"}
            for m in body["messages"]
        )
    finally:
        await srv2.stop()


@pytest.mark.asyncio
async def test_messages_endpoint_defaults(shared_redis):
    srv = (await start_servers(shared_redis))[0]
    try:
        raw = await http_get(srv.host, srv.bound_port, "/messages")
        body = parse_json(raw)
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert isinstance(body["messages"], list)
    finally:
        await stop_servers([srv])
