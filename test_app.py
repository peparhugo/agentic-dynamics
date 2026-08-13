import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
import fakeredis.aioredis
from websockets.asyncio.client import connect

import app


@pytest_asyncio.fixture
async def ws_server():
    server = app.NotificationServer()
    ws = await app.start_ws_server(server)
    httpd = app.start_health_server(server.registry)
    ws_port = ws.sockets[0].getsockname()[1]
    health_port = httpd.server_address[1]
    yield {
        "server": server,
        "ws": ws,
        "httpd": httpd,
        "ws_url": f"ws://127.0.0.1:{ws_port}",
        "health_url": f"http://127.0.0.1:{health_port}",
    }
    ws.close()
    app.stop_health_server(httpd)


@pytest_asyncio.fixture
async def client(ws_server):
    ws = await connect(ws_server["ws_url"])
    greeting = json.loads(await ws.recv())
    yield ws, greeting["payload"]["client_id"]
    await ws.close()


async def recv_message(ws):
    return json.loads(await ws.recv())


async def test_connect_assigns_unique_ids(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    g1 = await recv_message(ws1)
    g2 = await recv_message(ws2)
    assert g1["type"] == "system"
    assert g2["type"] == "system"
    id1 = g1["payload"]["client_id"]
    id2 = g2["payload"]["client_id"]
    assert id1 != id2
    assert len(ws_server["server"].registry) == 2
    await ws1.close()
    await ws2.close()


async def test_broadcast_reaches_all_connected_clients(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    await recv_message(ws1)
    await recv_message(ws2)

    await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    m1 = await recv_message(ws1)
    m2 = await recv_message(ws2)
    assert m1["type"] == "broadcast"
    assert m1["payload"] == {"text": "hello"}
    assert m2["type"] == "broadcast"
    assert m2["payload"] == {"text": "hello"}
    assert "timestamp" in m1
    await ws1.close()
    await ws2.close()


async def test_direct_message_routes_to_target_client(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    g1 = await recv_message(ws1)
    g2 = await recv_message(ws2)
    id2 = g2["payload"]["client_id"]

    await ws1.send(
        json.dumps({"type": "direct", "payload": {"client_id": id2, "text": "psst"}})
    )
    m2 = await recv_message(ws2)
    assert m2["type"] == "direct"
    assert m2["payload"] == {"client_id": id2, "text": "psst"}
    await ws1.close()
    await ws2.close()


async def test_direct_message_to_unknown_client_reports_error(ws_server, client):
    ws, _ = client
    await ws.send(
        json.dumps({"type": "direct", "payload": {"client_id": "nope", "text": "hi"}})
    )
    err = await recv_message(ws)
    assert err["type"] == "system"
    assert err["payload"]["action"] == "error"


async def test_system_health_returns_client_count(ws_server, client):
    ws, _ = client
    await ws.send(json.dumps({"type": "system", "payload": {"action": "health"}}))
    resp = await recv_message(ws)
    assert resp["type"] == "system"
    assert resp["payload"]["action"] == "health"
    assert resp["payload"]["client_count"] == 1


async def test_disconnect_removes_client_cleanly(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    await recv_message(ws1)
    ws2 = await connect(ws_server["ws_url"])
    await recv_message(ws2)
    assert len(ws_server["server"].registry) == 2

    await ws1.close()
    await asyncio_gather_till_count(ws_server["server"].registry, 1)
    assert len(ws_server["server"].registry) == 1
    await ws2.close()


async def asyncio_gather_till_count(registry, expected):
    import asyncio

    for _ in range(50):
        if len(registry) == expected:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"registry did not reach {expected} clients")


def test_http_health_endpoint_returns_client_count(ws_server):
    import urllib.request

    with urllib.request.urlopen(ws_server["health_url"] + "/health") as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
        assert body == {"client_count": 0}


async def test_subscribe_acknowledges_subscription(ws_server, client):
    ws, _ = client
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    ack = await recv_message(ws)
    assert ack["type"] == "system"
    assert ack["payload"]["action"] == "subscribed"
    assert ack["payload"]["channel"] == "alerts"


async def test_subscribe_without_channel_reports_error(ws_server, client):
    ws, _ = client
    await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
    err = await recv_message(ws)
    assert err["type"] == "system"
    assert err["payload"]["action"] == "error"


async def test_channel_message_delivered_only_to_subscribers(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    ws3 = await connect(ws_server["ws_url"])
    await recv_message(ws1)
    await recv_message(ws2)
    await recv_message(ws3)

    await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws1)
    await recv_message(ws2)

    await ws1.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "hi"}}))
    m1 = await recv_message(ws1)
    m2 = await recv_message(ws2)
    assert m1["type"] == "broadcast"
    assert m1["payload"] == {"channel": "alerts", "text": "hi"}
    assert m2["type"] == "broadcast"
    assert m2["payload"] == {"channel": "alerts", "text": "hi"}
    await ws1.close()
    await ws2.close()
    await ws3.close()


async def test_unsubscribed_client_does_not_receive_channel_message(ws_server):
    ws_sub = await connect(ws_server["ws_url"])
    ws_not = await connect(ws_server["ws_url"])
    await recv_message(ws_sub)
    await recv_message(ws_not)

    await ws_sub.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws_sub)

    await ws_sub.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "hi"}}))
    m = await recv_message(ws_sub)
    assert m["payload"]["text"] == "hi"
    assert not await _poll_no_message(ws_not)
    await ws_sub.close()
    await ws_not.close()


async def test_unsubscribe_stops_channel_delivery(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    await recv_message(ws1)
    await recv_message(ws2)

    await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws1)
    await recv_message(ws2)

    await ws2.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
    ack = await recv_message(ws2)
    assert ack["payload"]["action"] == "unsubscribed"

    await ws1.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "hi"}}))
    m1 = await recv_message(ws1)
    assert m1["payload"]["text"] == "hi"
    assert not await _poll_no_message(ws2)
    await ws1.close()
    await ws2.close()


async def test_client_can_subscribe_to_multiple_channels(ws_server):
    ws = await connect(ws_server["ws_url"])
    await recv_message(ws)
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws)
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
    await recv_message(ws)

    await ws.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "a"}}))
    await ws.send(json.dumps({"type": "broadcast", "payload": {"channel": "chat", "text": "c"}}))
    assert (await recv_message(ws))["payload"]["text"] == "a"
    assert (await recv_message(ws))["payload"]["text"] == "c"
    await ws.close()


async def test_broadcast_without_channel_reaches_everyone(ws_server):
    ws_sub = await connect(ws_server["ws_url"])
    ws_not = await connect(ws_server["ws_url"])
    await recv_message(ws_sub)
    await recv_message(ws_not)

    await ws_sub.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws_sub)

    await ws_sub.send(json.dumps({"type": "broadcast", "payload": {"text": "all"}}))
    m1 = await recv_message(ws_sub)
    m2 = await recv_message(ws_not)
    assert m1["payload"] == {"text": "all"}
    assert m2["payload"] == {"text": "all"}
    await ws_sub.close()
    await ws_not.close()


async def _poll_no_message(ws):
    import asyncio

    for _ in range(10):
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.05)
            return True
        except asyncio.TimeoutError:
            continue
    return False


def test_http_channels_endpoint_empty(ws_server):
    import urllib.request

    with urllib.request.urlopen(ws_server["health_url"] + "/channels") as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
        assert body == {"channels": {}}


async def test_http_channels_lists_subscriber_counts(ws_server):
    import urllib.request

    ws = await connect(ws_server["ws_url"])
    await recv_message(ws)
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws)

    with urllib.request.urlopen(ws_server["health_url"] + "/channels") as resp:
        body = json.loads(resp.read())
    assert body["channels"]["alerts"] == 1
    await ws.close()


async def test_http_channels_subscribers_endpoint(ws_server):
    import urllib.request

    ws = await connect(ws_server["ws_url"])
    greeting = await recv_message(ws)
    client_id = greeting["payload"]["client_id"]
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws)

    with urllib.request.urlopen(ws_server["health_url"] + "/channels/alerts/subscribers") as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
    assert body["channel"] == "alerts"
    assert body["subscribers"] == [client_id]
    await ws.close()


@pytest_asyncio.fixture
async def two_instances(tmp_path):
    fake_server = fakeredis.FakeServer()
    db = str(tmp_path / "history.db")

    def make_server():
        return app.NotificationServer(
            redis_client=fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True),
            database_url=db,
        )

    server1 = make_server()
    server2 = make_server()
    await server1.start_backend()
    await server2.start_backend()
    ws1 = await app.start_ws_server(server1)
    ws2 = await app.start_ws_server(server2)
    httpd1 = app.start_health_server(server1)
    httpd2 = app.start_health_server(server2)
    yield {
        "fake_server": fake_server,
        "server1": server1,
        "server2": server2,
        "redis": server1.redis,
        "url1": f"ws://127.0.0.1:{ws1.sockets[0].getsockname()[1]}",
        "url2": f"ws://127.0.0.1:{ws2.sockets[0].getsockname()[1]}",
    }
    await server1.stop_backend()
    await server2.stop_backend()
    ws1.close()
    ws2.close()
    app.stop_health_server(httpd1)
    app.stop_health_server(httpd2)


async def test_redis_pubsub_channel_broadcast_across_instances(two_instances):
    ws_a = await connect(two_instances["url1"])
    ws_b = await connect(two_instances["url2"])
    await recv_message(ws_a)
    await recv_message(ws_b)

    await ws_a.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await ws_b.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws_a)
    await recv_message(ws_b)

    await ws_a.send(
        json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "multi"}})
    )
    m_a = await recv_message(ws_a)
    m_b = await recv_message(ws_b)
    assert m_a["type"] == "broadcast"
    assert m_a["payload"] == {"channel": "alerts", "text": "multi"}
    assert m_b["type"] == "broadcast"
    assert m_b["payload"] == {"channel": "alerts", "text": "multi"}

    persisted = two_instances["server1"].store.list(50, 0)
    assert len(persisted) == 1
    assert persisted[0]["type"] == "broadcast"
    assert persisted[0]["channel"] == "alerts"
    assert persisted[0]["payload"] == {"channel": "alerts", "text": "multi"}
    await ws_a.close()
    await ws_b.close()


async def test_redis_pubsub_global_broadcast_across_instances(two_instances):
    ws_a = await connect(two_instances["url1"])
    ws_b = await connect(two_instances["url2"])
    await recv_message(ws_a)
    await recv_message(ws_b)

    await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "all"}}))
    m_a = await recv_message(ws_a)
    m_b = await recv_message(ws_b)
    assert m_a["type"] == "broadcast"
    assert m_a["payload"] == {"text": "all"}
    assert m_b["type"] == "broadcast"
    assert m_b["payload"] == {"text": "all"}
    await ws_a.close()
    await ws_b.close()


async def test_redis_pubsub_direct_across_instances(two_instances):
    ws_a = await connect(two_instances["url1"])
    ws_b = await connect(two_instances["url2"])
    await recv_message(ws_a)
    g_b = await recv_message(ws_b)
    id_b = g_b["payload"]["client_id"]

    await ws_a.send(
        json.dumps({"type": "direct", "payload": {"client_id": id_b, "text": "psst"}})
    )
    m_b = await recv_message(ws_b)
    assert m_b["type"] == "direct"
    assert m_b["payload"] == {"client_id": id_b, "text": "psst"}
    await ws_a.close()
    await ws_b.close()


async def test_redis_client_state_persists_across_restart(two_instances):
    ws = await connect(two_instances["url1"])
    greeting = await recv_message(ws)
    client_id = greeting["payload"]["client_id"]
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws)

    state = await two_instances["redis"].hgetall(f"notifications:client:{client_id}")
    assert state["status"] == "connected"
    assert json.loads(state["channels"]) == ["alerts"]

    await ws.close()
    await asyncio_gather_till_count(two_instances["server1"].registry, 0)
    state = await two_instances["redis"].hgetall(f"notifications:client:{client_id}")
    assert state["status"] == "disconnected"

    reader = fakeredis.aioredis.FakeRedis(server=two_instances["fake_server"], decode_responses=True)
    state = await reader.hgetall(f"notifications:client:{client_id}")
    assert state["status"] == "disconnected"
    assert json.loads(state["channels"]) == ["alerts"]
    await reader.close()


async def test_messages_persistence_and_rest_endpoint(tmp_path):
    import urllib.request

    db = str(tmp_path / "history.db")
    server = app.NotificationServer(database_url=db)
    await server.start_backend()
    ws = await app.start_ws_server(server)
    httpd = app.start_health_server(server)
    health_url = f"http://127.0.0.1:{httpd.server_address[1]}"
    ws_url = f"ws://127.0.0.1:{ws.sockets[0].getsockname()[1]}"

    cws = await connect(ws_url)
    await recv_message(cws)
    await cws.send(json.dumps({"type": "broadcast", "payload": {"text": "first"}}))
    await recv_message(cws)
    await cws.send(json.dumps({"type": "subscribe", "payload": {"channel": "news"}}))
    await recv_message(cws)
    await cws.send(
        json.dumps({"type": "broadcast", "payload": {"channel": "news", "text": "second"}})
    )
    await recv_message(cws)

    with urllib.request.urlopen(health_url + "/messages") as resp:
        body = json.loads(resp.read())
    messages = body["messages"]
    assert len(messages) == 2
    assert {"id", "channel", "type", "payload", "timestamp"}.issubset(messages[0])
    assert messages[0]["type"] == "broadcast"
    assert messages[0]["channel"] is None
    assert messages[0]["payload"] == {"text": "first"}
    assert messages[1]["channel"] == "news"
    assert messages[1]["payload"] == {"channel": "news", "text": "second"}

    with urllib.request.urlopen(health_url + "/messages?limit=1&offset=1") as resp:
        body = json.loads(resp.read())
    assert len(body["messages"]) == 1
    assert body["messages"][0]["payload"] == {"channel": "news", "text": "second"}

    with urllib.request.urlopen(health_url + "/messages?limit=0&offset=0") as resp:
        body = json.loads(resp.read())
    assert body["messages"] == []

    await cws.close()
    ws.close()
    app.stop_health_server(httpd)
    await server.stop_backend()


async def test_redis_client_state_saved_without_backend_is_noop(ws_server, client):
    ws, client_id = client
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws)
    assert ws_server["server"].store.list(50, 0) == []


@pytest_asyncio.fixture
async def redis_server(tmp_path):
    """A server with a fake Redis backend and an HTTP listener."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db = str(tmp_path / "history.db")
    server = app.NotificationServer(redis_client=fake, database_url=db)
    await server.start_backend()
    ws = await app.start_ws_server(server)
    httpd = app.start_health_server(server)
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    ws_url = f"ws://127.0.0.1:{ws.sockets[0].getsockname()[1]}"
    yield {
        "server": server,
        "redis": fake,
        "ws": ws,
        "httpd": httpd,
        "health_url": url,
        "ws_url": ws_url,
    }
    ws.close()
    app.stop_health_server(httpd)
    await server.stop_backend()
    await fake.close()


async def test_rate_limit_allows_messages_under_limit(redis_server):
    cws = await connect(redis_server["ws_url"])
    greeting = await recv_message(cws)
    client_id = greeting["payload"]["client_id"]

    await cws.send(json.dumps({"type": "broadcast", "payload": {"text": "ok"}}))
    resp = await recv_message(cws)
    assert resp["type"] == "broadcast"
    assert resp["payload"] == {"text": "ok"}

    window = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    key = f"notifications:ratelimit:{client_id}:{window}"
    assert await redis_server["redis"].get(key) == "1"
    await cws.close()


async def test_rate_limit_returns_error_when_exceeded():
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    server = app.NotificationServer(redis_client=fake, rate_limit=3)
    await server.start_backend()
    ws = await app.start_ws_server(server)
    ws_url = f"ws://127.0.0.1:{ws.sockets[0].getsockname()[1]}"

    cws = await connect(ws_url)
    greeting = await recv_message(cws)
    client_id = greeting["payload"]["client_id"]

    for i in range(3):
        await cws.send(json.dumps({"type": "broadcast", "payload": {"text": f"m{i}"}}))
        resp = await recv_message(cws)
        assert resp["type"] == "broadcast"

    await cws.send(json.dumps({"type": "broadcast", "payload": {"text": "boom"}}))
    err = await recv_message(cws)
    assert err["type"] == "system"
    assert err["payload"]["action"] == "error"
    assert "rate limit" in err["payload"]["message"].lower()

    window = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    key = f"notifications:ratelimit:{client_id}:{window}"
    assert await fake.get(key) == "4"

    await cws.close()
    ws.close()
    await server.stop_backend()
    await fake.close()


async def test_rate_limit_without_redis_is_noop(ws_server, client):
    ws, _ = client
    for i in range(3):
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": f"m{i}"}}))
        resp = await recv_message(ws)
        assert resp["type"] == "broadcast"
    assert ws_server["server"].store.list(50, 0) == []


async def test_history_returns_channel_messages_chronologically(redis_server):
    cws = await connect(redis_server["ws_url"])
    await recv_message(cws)
    await cws.send(json.dumps({"type": "subscribe", "payload": {"channel": "news"}}))
    await recv_message(cws)
    for text in ["alpha", "beta", "gamma"]:
        await cws.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "news", "text": text}})
        )
        await recv_message(cws)
    await cws.send(json.dumps({"type": "broadcast", "payload": {"text": "global"}}))
    await recv_message(cws)

    with urllib.request.urlopen(redis_server["health_url"] + "/history?channel=news&limit=50") as resp:
        body = json.loads(resp.read())
    assert body["channel"] == "news"
    assert body["has_more"] is False
    texts = [m["payload"]["text"] for m in body["messages"]]
    assert texts == ["alpha", "beta", "gamma"]
    assert all(m["channel"] == "news" for m in body["messages"])
    timestamps = [m["timestamp"] for m in body["messages"]]
    assert timestamps == sorted(timestamps)
    await cws.close()


async def test_history_pagination_and_since(redis_server):
    cws = await connect(redis_server["ws_url"])
    await recv_message(cws)
    await cws.send(json.dumps({"type": "subscribe", "payload": {"channel": "news"}}))
    await recv_message(cws)
    for text in ["a", "b", "c"]:
        await cws.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "news", "text": text}})
        )
        await recv_message(cws)

    page_url = redis_server["health_url"] + "/history?channel=news&limit=2"
    with urllib.request.urlopen(page_url) as resp:
        page1 = json.loads(resp.read())
    assert page1["has_more"] is True
    assert len(page1["messages"]) == 2
    assert [m["payload"]["text"] for m in page1["messages"]] == ["a", "b"]

    since = urllib.parse.quote(page1["messages"][-1]["timestamp"])
    with urllib.request.urlopen(
        redis_server["health_url"] + f"/history?channel=news&since={since}&limit=2"
    ) as resp:
        page2 = json.loads(resp.read())
    assert page2["has_more"] is False
    assert [m["payload"]["text"] for m in page2["messages"]] == ["c"]
    await cws.close()


async def test_history_since_filter_excludes_earlier_messages(redis_server):
    cws = await connect(redis_server["ws_url"])
    await recv_message(cws)
    await cws.send(json.dumps({"type": "subscribe", "payload": {"channel": "news"}}))
    await recv_message(cws)
    for text in ["a", "b", "c"]:
        await cws.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "news", "text": text}})
        )
        await recv_message(cws)

    marker = redis_server["server"].store.list(50, 0)[1]["timestamp"]
    since = urllib.parse.quote(marker)
    with urllib.request.urlopen(
        redis_server["health_url"] + f"/history?channel=news&since={since}"
    ) as resp:
        body = json.loads(resp.read())
    assert [m["payload"]["text"] for m in body["messages"]] == ["c"]
    assert body["has_more"] is False
    await cws.close()


async def test_history_missing_channel_returns_400(redis_server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(redis_server["health_url"] + "/history")
    assert exc.value.code == 400


async def test_history_invalid_since_returns_400(redis_server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(redis_server["health_url"] + "/history?channel=news&since=not-a-date")
    assert exc.value.code == 400


async def test_history_unknown_channel_is_empty(redis_server):
    with urllib.request.urlopen(redis_server["health_url"] + "/history?channel=nope&limit=5") as resp:
        body = json.loads(resp.read())
    assert body["messages"] == []
    assert body["has_more"] is False


async def test_message_expiry_removes_old_messages(tmp_path):
    db = str(tmp_path / "expiry.db")
    server = app.NotificationServer(database_url=db, message_ttl_days=7)
    await server.start_backend()

    now = datetime.now(timezone.utc)
    server.store.add("news", "broadcast", {"text": "old"}, (now - timedelta(days=8)).isoformat())
    server.store.add("news", "broadcast", {"text": "older"}, (now - timedelta(days=30)).isoformat())
    server.store.add("news", "broadcast", {"text": "new"}, now.isoformat())

    removed = await server.expire_old_messages()
    assert removed == 2
    remaining = server.store.list(100, 0)
    assert [m["payload"]["text"] for m in remaining] == ["new"]
    await server.stop_backend()


async def test_message_expiry_background_task_runs_on_startup(tmp_path):
    db = str(tmp_path / "expiry2.db")
    server = app.NotificationServer(database_url=db, message_ttl_days=7)
    server.store.open()
    now = datetime.now(timezone.utc)
    server.store.add("news", "broadcast", {"text": "old"}, (now - timedelta(days=8)).isoformat())
    server.store.add("news", "broadcast", {"text": "new"}, now.isoformat())

    await server.start_backend()
    for _ in range(50):
        remaining = server.store.list(100, 0)
        if len(remaining) == 1 and remaining[0]["payload"]["text"] == "new":
            break
        await asyncio.sleep(0.05)
    remaining = server.store.list(100, 0)
    assert [m["payload"]["text"] for m in remaining] == ["new"]
    await server.stop_backend()
