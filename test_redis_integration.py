import asyncio
import json
import os
import subprocess
import sys

import fakeredis.aioredis as fakeaioredis
import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

import notification_server as ns


@pytest_asyncio.fixture(autouse=True)
async def clean_registry():
    ns.registry = ns.ClientRegistry()
    ns.channels = ns.ChannelRegistry()
    yield
    ns.registry = ns.ClientRegistry()
    ns.channels = ns.ChannelRegistry()


@pytest_asyncio.fixture
async def server():
    async with ns.serve(ns.handler, "localhost", 0, process_request=ns.process_request) as srv:
        port = srv.sockets[0].getsockname()[1]
        yield f"ws://localhost:{port}"


async def recv_json(ws, msg_type=None):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(raw)
        if msg_type is None or data["type"] == msg_type:
            return data


async def http_get(server, path):
    host_port = server.split("://", 1)[1]
    reader, writer = await asyncio.open_connection(*host_port.split(":"))
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    raw = await reader.read()
    writer.close()
    header_blob, _, body = raw.partition(b"\r\n\r\n")
    status_line = header_blob.splitlines()[0].decode()
    return status_line, json.loads(body.decode())


async def wait_until(predicate, timeout=2.0, interval=0.02):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("condition was not met within the timeout")


class FakeConnection:
    """Stand-in for a ServerConnection: records everything sent to it so
    delivery can be asserted without a real websocket."""

    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


# ── Delivery goes through Redis pub/sub ─────────────────────────

@pytest.mark.asyncio
async def test_broadcast_is_delivered_via_redis_worker(server):
    async with connect(server) as ws1, connect(server) as ws2:
        await recv_json(ws1, "system")
        await recv_json(ws2, "system")

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "hi all"}}))

        msg1 = await recv_json(ws1, "broadcast")
        msg2 = await recv_json(ws2, "broadcast")
        assert msg1["payload"]["text"] == "hi all"
        assert msg2["payload"]["text"] == "hi all"


@pytest.mark.asyncio
async def test_direct_message_is_delivered_via_redis_worker(server):
    async with connect(server) as ws1, connect(server) as ws2:
        await recv_json(ws1, "system")
        welcome2 = await recv_json(ws2, "system")
        target_id = welcome2["payload"]["client_id"]

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": target_id, "text": "just for you"},
        }))

        msg2 = await recv_json(ws2, "direct")
        assert msg2["payload"]["text"] == "just for you"


# ── Connected client state mirrored in Redis ─────────────────────

@pytest.mark.asyncio
async def test_connected_client_state_is_mirrored_in_redis(server):
    async with connect(server) as ws1:
        welcome = await recv_json(ws1, "system")
        client_id = welcome["payload"]["client_id"]

        client = await ns.get_redis_client()
        assert await client.sismember(ns.CONNECTED_CLIENTS_KEY, client_id)

    client = await ns.get_redis_client()
    for _ in range(50):
        if not await client.sismember(ns.CONNECTED_CLIENTS_KEY, client_id):
            break
        await asyncio.sleep(0.05)
    assert not await client.sismember(ns.CONNECTED_CLIENTS_KEY, client_id)


@pytest.mark.asyncio
async def test_direct_message_to_unknown_client_checked_against_redis(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": "not-a-real-client", "text": "hi"},
        }))
        err = await recv_json(ws1, "system")
        assert "not connected" in err["payload"]["error"]


# ── SQLite persistence ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broadcast_message_is_persisted_to_sqlite(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "persist me"},
        }))
        await recv_json(ws1, "broadcast")

    status_line, data = await http_get(server, "/messages")
    assert "200" in status_line
    matches = [m for m in data["messages"] if m["payload"].get("text") == "persist me"]
    assert len(matches) == 1
    stored = matches[0]
    assert stored["type"] == "broadcast"
    assert stored["channel"] == "alerts"
    assert set(stored.keys()) == {"id", "channel", "type", "payload", "timestamp"}


@pytest.mark.asyncio
async def test_direct_message_is_persisted_to_sqlite(server):
    async with connect(server) as ws1, connect(server) as ws2:
        await recv_json(ws1, "system")
        welcome2 = await recv_json(ws2, "system")
        target_id = welcome2["payload"]["client_id"]

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": target_id, "text": "direct persist"},
        }))
        await recv_json(ws2, "direct")

    status_line, data = await http_get(server, "/messages")
    assert "200" in status_line
    matches = [m for m in data["messages"] if m["payload"].get("text") == "direct persist"]
    assert len(matches) == 1
    assert matches[0]["type"] == "direct"
    assert matches[0]["channel"] is None


@pytest.mark.asyncio
async def test_messages_endpoint_respects_limit_and_offset(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        for text in ("first", "second", "third"):
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": text}}))
            await recv_json(ws1, "broadcast")

    status_line, page1 = await http_get(server, "/messages?limit=2&offset=0")
    assert "200" in status_line
    assert page1["limit"] == 2
    assert page1["offset"] == 0
    assert len(page1["messages"]) == 2
    # newest first
    assert page1["messages"][0]["payload"]["text"] == "third"
    assert page1["messages"][1]["payload"]["text"] == "second"

    status_line, page2 = await http_get(server, "/messages?limit=2&offset=2")
    assert "200" in status_line
    assert len(page2["messages"]) == 1
    assert page2["messages"][0]["payload"]["text"] == "first"


@pytest.mark.asyncio
async def test_messages_endpoint_defaults_and_bounds(server):
    status_line, data = await http_get(server, "/messages")
    assert "200" in status_line
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert data["messages"] == []

    status_line, data = await http_get(server, "/messages?limit=not-a-number&offset=-5")
    assert "200" in status_line
    assert data["limit"] == 50
    assert data["offset"] == 0


# ── Multiple server instances sharing one Redis backbone ─────────

@pytest.mark.asyncio
async def test_multiple_instances_share_redis_backbone(_isolated_redis_and_db):
    await ns.ensure_started()  # initializes the SQLite schema ns.broadcast() writes to
    fake_server = _isolated_redis_and_db
    reg_a, chans_a = ns.ClientRegistry(), ns.ChannelRegistry()
    reg_b, chans_b = ns.ClientRegistry(), ns.ChannelRegistry()

    client_a = await ns.get_redis_client()
    client_b = fakeaioredis.FakeRedis(server=fake_server, decode_responses=True)

    worker_a = asyncio.create_task(ns.redis_worker(client_a, reg=reg_a, chans=chans_a))
    worker_b = asyncio.create_task(ns.redis_worker(client_b, reg=reg_b, chans=chans_b))
    await asyncio.sleep(0.05)  # let both workers finish SUBSCRIBE

    try:
        conn_b = FakeConnection()
        client_id_b = reg_b.add(conn_b)
        chans_b.subscribe(client_id_b, "alerts")
        await client_b.sadd(ns.CONNECTED_CLIENTS_KEY, client_id_b)

        # Broadcast published from the "instance A" side must still reach
        # the client that is only connected to instance B.
        await ns.broadcast({"channel": "alerts", "text": "cross-instance broadcast"})
        await wait_until(lambda: len(conn_b.sent) == 1)
        delivered = json.loads(conn_b.sent[0])
        assert delivered["payload"]["text"] == "cross-instance broadcast"
        assert reg_a.snapshot() == []  # instance A had no matching local clients

        # Direct message: instance A doesn't have the target locally, but
        # can see (via Redis) that it's connected, and instance B delivers.
        delivered_ok = await ns.send_direct(client_id_b, {"text": "cross-instance direct"})
        assert delivered_ok is True
        await wait_until(lambda: len(conn_b.sent) == 2)
        direct_msg = json.loads(conn_b.sent[1])
        assert direct_msg["payload"]["text"] == "cross-instance direct"
    finally:
        worker_a.cancel()
        worker_b.cancel()
        for w in (worker_a, worker_b):
            try:
                await w
            except asyncio.CancelledError:
                pass
        await client_b.aclose()


# ── Config via env vars ───────────────────────────────────────────

def test_redis_url_and_database_url_are_configurable_via_env():
    env = dict(os.environ)
    env["REDIS_URL"] = "redis://example.invalid:6390/2"
    env["DATABASE_URL"] = "/tmp/custom-notifications-test.db"
    result = subprocess.run(
        [sys.executable, "-c", "import notification_server as ns; print(ns.REDIS_URL); print(ns.DATABASE_URL)"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "redis://example.invalid:6390/2"
    assert lines[1] == "/tmp/custom-notifications-test.db"


def test_redis_url_and_database_url_have_sane_defaults():
    env = {k: v for k, v in os.environ.items() if k not in ("REDIS_URL", "DATABASE_URL")}
    result = subprocess.run(
        [sys.executable, "-c", "import notification_server as ns; print(ns.REDIS_URL); print(ns.DATABASE_URL)"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "redis://localhost:6379/0"
    assert lines[1] == "notifications.db"
