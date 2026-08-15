"""Integration tests for the Redis pub/sub backbone and SQLite persistence."""

import asyncio
import json

import pytest
import redis
import websockets

from server import NotificationServer

REDIS_DB = 15
REDIS_URL = f"redis://127.0.0.1:6379/{REDIS_DB}"


@pytest.fixture
def redis_url():
    url = REDIS_URL
    client = None
    try:
        client = redis.Redis.from_url(url)
        client.ping()
        client.flushdb()
    except Exception:
        pytest.skip("Redis is not available on 127.0.0.1:6379")
    yield url
    if client is not None:
        try:
            client.flushdb()
            client.close()
        except Exception:
            pass


async def connect_client(server):
    websocket = await websockets.connect(f"ws://{server.host}:{server.port}")
    first = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
    return websocket, first["payload"]["client_id"]


async def http_get(host, port, path="/health"):
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
    writer.write(request.encode("latin-1"))
    await writer.drain()
    response = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()
    header, _, body = response.partition(b"\r\n\r\n")
    status_line = header.split(b"\r\n", 1)[0].decode("latin-1")
    return status_line, json.loads(body.decode("utf-8"))


async def wait_until(predicate, timeout=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


def make_server(redis_url=None, database_url=":memory:"):
    return NotificationServer(
        host="127.0.0.1",
        port=0,
        health_port=0,
        redis_url=redis_url,
        database_url=database_url,
    )


async def test_redis_pubsub_channel_delivery_across_instances(redis_url):
    server_a = await make_server(redis_url=redis_url).start()
    server_b = await make_server(redis_url=redis_url).start()
    try:
        ws, client_id = await connect_client(server_a)
        await ws.send(json.dumps({"type": "subscribe", "channel": "news"}))
        assert await wait_until(
            lambda: client_id in server_a.registry.subscribers("news")
        )

        sent = await server_b.publish_to_channel("news", "broadcast", {"msg": "from-b"})
        assert sent == 0

        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"msg": "from-b"}
        assert msg["timestamp"]
        await ws.close()
    finally:
        await server_a.stop()
        await server_b.stop()


async def test_redis_pubsub_global_broadcast_across_instances(redis_url):
    server_a = await make_server(redis_url=redis_url).start()
    server_b = await make_server(redis_url=redis_url).start()
    try:
        ws_a, id_a = await connect_client(server_a)
        ws_b, id_b = await connect_client(server_b)

        sent = await server_b.broadcast("broadcast", {"hello": "world"})
        assert sent == 1

        msg_a = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=2))
        assert msg_a["type"] == "broadcast"
        assert msg_a["payload"] == {"hello": "world"}

        await ws_a.close()
        await ws_b.close()
    finally:
        await server_a.stop()
        await server_b.stop()


async def test_redis_pubsub_direct_delivery_across_instances(redis_url):
    server_a = await make_server(redis_url=redis_url).start()
    server_b = await make_server(redis_url=redis_url).start()
    try:
        ws, client_id = await connect_client(server_a)

        delivered = await server_b.send_to(client_id, "direct", {"secret": "x"})
        assert delivered is False

        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert msg["type"] == "direct"
        assert msg["payload"] == {"secret": "x"}
        await ws.close()
    finally:
        await server_a.stop()
        await server_b.stop()


async def test_client_connection_state_stored_in_redis(redis_url):
    server = await make_server(redis_url=redis_url).start()
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        ws, client_id = await connect_client(server)
        assert await wait_until(lambda: client.sismember("notif:clients", client_id))

        await ws.send(json.dumps({"type": "subscribe", "channel": "news"}))
        assert await wait_until(
            lambda: client.sismember(f"notif:subs:{client_id}", "news")
        )
        assert client.smembers(f"notif:subs:{client_id}") == {"news"}
        assert client.get(f"notif:client:{client_id}:instance") is not None

        await ws.close()
        assert await wait_until(
            lambda: not client.sismember("notif:clients", client_id)
        )
    finally:
        await server.stop()
        client.close()


async def test_message_persistence_and_history_endpoint(tmp_path):
    db_path = tmp_path / "messages.db"
    server = await make_server(database_url=f"sqlite:///{db_path}").start()
    try:
        await server.broadcast("broadcast", {"hello": "world"})
        await server.publish_to_channel("news", "broadcast", {"x": 1})
        ws, client_id = await connect_client(server)
        await server.send_to(client_id, "direct", {"to": "you"})
        await ws.close()

        status, body = await http_get(
            server.host, server.health_port, "/messages?limit=50&offset=0"
        )
        assert "200 OK" in status
        assert len(body) == 3

        newest, middle, oldest = body[0], body[1], body[2]
        assert newest["type"] == "direct"
        assert newest["channel"] == client_id
        assert newest["payload"] == {"to": "you"}
        assert middle["type"] == "broadcast"
        assert middle["channel"] == "news"
        assert oldest["type"] == "broadcast"
        assert oldest["channel"] == ""
        assert oldest["payload"] == {"hello": "world"}
        for row in body:
            assert set(row.keys()) == {"id", "channel", "type", "payload", "timestamp"}
            assert row["timestamp"]

        status, body = await http_get(
            server.host, server.health_port, "/messages?limit=2&offset=0"
        )
        assert len(body) == 2
        assert body[0]["type"] == "direct"
        assert body[1]["type"] == "broadcast"

        status, body = await http_get(
            server.host, server.health_port, "/messages?limit=2&offset=2"
        )
        assert len(body) == 1
        assert body[0]["type"] == "broadcast"
    finally:
        await server.stop()


async def test_persistence_survives_server_restart(tmp_path):
    db_path = tmp_path / "messages.db"
    database_url = f"sqlite:///{db_path}"

    server = await make_server(database_url=database_url).start()
    await server.broadcast("broadcast", {"a": 1})
    await server.publish_to_channel("news", "broadcast", {"b": 2})
    await server.stop()

    server = await make_server(database_url=database_url).start()
    try:
        status, body = await http_get(server.host, server.health_port, "/messages")
        assert "200 OK" in status
        assert len(body) == 2
        assert body[0]["payload"] == {"b": 2}
        assert body[1]["payload"] == {"a": 1}
    finally:
        await server.stop()


async def test_env_var_configuration(monkeypatch, tmp_path, redis_url):
    db_path = tmp_path / "env.db"
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    server = NotificationServer(host="127.0.0.1", port=0, health_port=0)
    assert server.redis_url == redis_url
    assert server.broker is not None
    await server.start()
    try:
        ws, client_id = await connect_client(server)
        await server.broadcast("broadcast", {"via": "env"})
        status, body = await http_get(server.host, server.health_port, "/messages")
        assert "200 OK" in status
        assert len(body) == 1
        assert body[0]["payload"] == {"via": "env"}
        await ws.close()
    finally:
        await server.stop()
