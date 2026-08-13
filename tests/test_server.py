import asyncio
import json
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
import websockets

from notification_server.server import NotificationServer


@pytest.fixture
async def running_server():
    app = NotificationServer()
    server = await websockets.serve(
        app.handler, "localhost", 0, process_request=app.process_request
    )
    port = server.sockets[0].getsockname()[1]
    try:
        yield app, f"ws://localhost:{port}", f"http://localhost:{port}"
    finally:
        server.close()
        await server.wait_closed()
        await app.close()


@pytest.fixture
async def rate_limited_server():
    app = NotificationServer(rate_limit=3)
    server = await websockets.serve(
        app.handler, "localhost", 0, process_request=app.process_request
    )
    port = server.sockets[0].getsockname()[1]
    try:
        yield app, f"ws://localhost:{port}", f"http://localhost:{port}"
    finally:
        server.close()
        await server.wait_closed()
        await app.close()


async def _connected(client):
    msg = json.loads(await client.recv())
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "connected"
    return msg["payload"]["client_id"]


async def test_connect_assigns_unique_id_and_cleans_up_on_disconnect(running_server):
    app, ws_url, _ = running_server
    async with websockets.connect(ws_url) as client:
        client_id = await _connected(client)
        assert client_id
        assert await app.registry.count() == 1
    await asyncio.sleep(0.05)
    assert await app.registry.count() == 0


async def test_two_clients_get_different_ids(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as c1, websockets.connect(ws_url) as c2:
        id1 = await _connected(c1)
        id2 = await _connected(c2)
        assert id1 != id2


async def test_broadcast_reaches_all_clients(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as c1, websockets.connect(ws_url) as c2:
        c1_id = await _connected(c1)
        await _connected(c2)

        # c1 sees the "client_joined" system event triggered by c2's connect
        join_evt = json.loads(await c1.recv())
        assert join_evt["type"] == "system"
        assert join_evt["payload"]["event"] == "client_joined"

        await c1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello everyone"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))

        msg_on_c1 = json.loads(await c1.recv())
        msg_on_c2 = json.loads(await c2.recv())
        assert msg_on_c1 == msg_on_c2
        assert msg_on_c1["type"] == "broadcast"
        assert msg_on_c1["payload"]["text"] == "hello everyone"
        assert msg_on_c1["payload"]["from"] == c1_id


async def test_direct_message_reaches_only_target(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as c1, websockets.connect(ws_url) as c2, \
            websockets.connect(ws_url) as c3:
        c1_id = await _connected(c1)
        c2_id = await _connected(c2)
        await _connected(c3)

        # drain "client_joined" events seen by earlier connections
        await c1.recv()  # c2 joined
        await c1.recv()  # c3 joined
        await c2.recv()  # c3 joined

        await c1.send(json.dumps({
            "type": "direct",
            "payload": {"target": c2_id, "text": "psst"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))

        direct_msg = json.loads(await c2.recv())
        assert direct_msg["type"] == "direct"
        assert direct_msg["payload"]["text"] == "psst"
        assert direct_msg["payload"]["from"] == c1_id

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(c3.recv(), timeout=0.2)


async def test_direct_message_unknown_target_gets_error(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as c1:
        await _connected(c1)
        await c1.send(json.dumps({
            "type": "direct",
            "payload": {"target": "no-such-client", "text": "hi"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        err = json.loads(await c1.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_disconnect_notifies_remaining_clients(running_server):
    app, ws_url, _ = running_server
    async with websockets.connect(ws_url) as c1:
        await _connected(c1)
        async with websockets.connect(ws_url) as c2:
            c2_id = await _connected(c2)
            await c1.recv()  # client_joined for c2

        left_evt = json.loads(await c1.recv())
        assert left_evt["type"] == "system"
        assert left_evt["payload"]["event"] == "client_left"
        assert left_evt["payload"]["client_id"] == c2_id

    await asyncio.sleep(0.05)
    assert await app.registry.count() == 0


async def test_invalid_message_gets_system_error(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as client:
        await _connected(client)
        await client.send("not valid json")
        err = json.loads(await client.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_client_sending_system_message_gets_rejected(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as client:
        await _connected(client)
        await client.send(json.dumps({
            "type": "system",
            "payload": {"event": "fake"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        err = json.loads(await client.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_subscribe_confirms_and_updates_channels_endpoint(running_server):
    _, ws_url, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch(path):
        with urlopen(f"{http_url}{path}", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    async with websockets.connect(ws_url) as client:
        client_id = await _connected(client)
        await client.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        ack = json.loads(await client.recv())
        assert ack["type"] == "system"
        assert ack["payload"]["event"] == "subscribed"
        assert ack["payload"]["channel"] == "alerts"
        assert ack["payload"]["client_id"] == client_id

        status, body = await loop.run_in_executor(None, fetch, "/channels")
        assert status == 200
        assert body == {"channels": [{"name": "alerts", "subscribers": 1}]}

        status, body = await loop.run_in_executor(None, fetch, "/channels/alerts/subscribers")
        assert status == 200
        assert body == {"channel": "alerts", "subscribers": [client_id]}


async def test_unsubscribe_confirms_and_removes_from_channel(running_server):
    _, ws_url, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch(path):
        with urlopen(f"{http_url}{path}", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    async with websockets.connect(ws_url) as client:
        await _connected(client)
        await client.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await client.recv()  # subscribed ack

        await client.send(json.dumps({
            "type": "unsubscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        ack = json.loads(await client.recv())
        assert ack["type"] == "system"
        assert ack["payload"]["event"] == "unsubscribed"
        assert ack["payload"]["channel"] == "alerts"

        status, body = await loop.run_in_executor(None, fetch, "/channels")
        assert status == 200
        assert body == {"channels": []}


async def test_subscribe_without_channel_gets_error(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as client:
        await _connected(client)
        await client.send(json.dumps({
            "type": "subscribe",
            "payload": {},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        err = json.loads(await client.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_channel_message_reaches_only_subscribers(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as c1, websockets.connect(ws_url) as c2, \
            websockets.connect(ws_url) as c3:
        c1_id = await _connected(c1)
        await _connected(c2)
        await _connected(c3)

        # drain "client_joined" events seen by earlier connections
        await c1.recv()  # c2 joined
        await c1.recv()  # c3 joined
        await c2.recv()  # c3 joined

        await c1.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await c1.recv()  # subscribed ack

        await c2.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await c2.recv()  # subscribed ack

        await c1.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "fire!"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))

        msg_on_c1 = json.loads(await c1.recv())
        msg_on_c2 = json.loads(await c2.recv())
        assert msg_on_c1 == msg_on_c2
        assert msg_on_c1["payload"]["channel"] == "alerts"
        assert msg_on_c1["payload"]["text"] == "fire!"
        assert msg_on_c1["payload"]["from"] == c1_id

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(c3.recv(), timeout=0.2)


async def test_broadcast_without_channel_still_reaches_everyone(running_server):
    _, ws_url, _ = running_server
    async with websockets.connect(ws_url) as c1, websockets.connect(ws_url) as c2:
        await _connected(c1)
        await _connected(c2)
        await c1.recv()  # client_joined for c2

        await c1.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await c1.recv()  # subscribed ack

        await c1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "no channel here"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))

        msg_on_c1 = json.loads(await c1.recv())
        msg_on_c2 = json.loads(await c2.recv())
        assert msg_on_c1 == msg_on_c2
        assert msg_on_c1["payload"]["text"] == "no channel here"


async def test_disconnect_removes_client_from_channels(running_server):
    app, ws_url, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch(path):
        with urlopen(f"{http_url}{path}", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    async with websockets.connect(ws_url) as client:
        await _connected(client)
        await client.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await client.recv()  # subscribed ack

    await asyncio.sleep(0.05)
    status, body = await loop.run_in_executor(None, fetch, "/channels")
    assert status == 200
    assert body == {"channels": []}


async def test_channels_endpoint_empty_when_no_subscriptions(running_server):
    _, _, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch():
        with urlopen(f"{http_url}/channels", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    status, body = await loop.run_in_executor(None, fetch)
    assert status == 200
    assert body == {"channels": []}


async def test_subscribers_endpoint_empty_for_unknown_channel(running_server):
    _, _, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch():
        with urlopen(f"{http_url}/channels/does-not-exist/subscribers", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    status, body = await loop.run_in_executor(None, fetch)
    assert status == 200
    assert body == {"channel": "does-not-exist", "subscribers": []}


async def test_messages_within_rate_limit_are_processed_normally(rate_limited_server):
    _, ws_url, _ = rate_limited_server
    async with websockets.connect(ws_url) as client:
        await _connected(client)
        for i in range(3):
            await client.send(json.dumps({
                "type": "broadcast",
                "payload": {"seq": i},
                "timestamp": "2026-08-13T00:00:00+00:00",
            }))
            echoed = json.loads(await client.recv())
            assert echoed["type"] == "broadcast"
            assert echoed["payload"]["seq"] == i


async def test_exceeding_rate_limit_returns_error_without_disconnecting(rate_limited_server):
    _, ws_url, _ = rate_limited_server
    async with websockets.connect(ws_url) as client:
        await _connected(client)
        for _ in range(3):
            await client.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "ok"},
                "timestamp": "2026-08-13T00:00:00+00:00",
            }))
            await client.recv()

        await client.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "one too many"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        err = json.loads(await client.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"
        assert "rate limit" in err["payload"]["detail"]

        # connection stays open and usable — the message is rejected, not dropped
        await client.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        # still over the limit, so this is rejected too rather than silently ignored,
        # proving the connection is still alive and usable after the earlier rejection
        err2 = json.loads(await client.recv())
        assert err2["payload"]["event"] == "error"


async def test_rate_limit_is_tracked_independently_per_client(rate_limited_server):
    _, ws_url, _ = rate_limited_server
    async with websockets.connect(ws_url) as c1, websockets.connect(ws_url) as c2:
        await _connected(c1)
        await _connected(c2)
        await c1.recv()  # client_joined for c2

        for _ in range(3):
            await c1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "from c1"},
                "timestamp": "2026-08-13T00:00:00+00:00",
            }))
            await c1.recv()
            await c2.recv()

        # c1 is now rate-limited...
        await c1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "over limit"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        err = json.loads(await c1.recv())
        assert err["payload"]["event"] == "error"

        # ...but c2's own budget is untouched
        await c2.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "from c2"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        ok = json.loads(await c2.recv())
        assert ok["type"] == "broadcast"
        assert ok["payload"]["text"] == "from c2"


async def test_history_endpoint_requires_channel(running_server):
    _, _, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch():
        try:
            urlopen(f"{http_url}/history", timeout=2)
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    status, body = await loop.run_in_executor(None, fetch)
    assert status == 400
    assert "error" in body


async def test_history_endpoint_returns_channel_messages_in_chronological_order(running_server):
    _, ws_url, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch(path):
        with urlopen(f"{http_url}{path}", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    async with websockets.connect(ws_url) as client:
        await _connected(client)
        await client.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await client.recv()  # subscribed ack

        for i in range(3):
            await client.send(json.dumps({
                "type": "broadcast",
                "payload": {"channel": "alerts", "seq": i},
                "timestamp": f"2026-08-13T00:00:0{i}+00:00",
            }))
            await client.recv()

        status, body = await loop.run_in_executor(None, fetch, "/history?channel=alerts")
        assert status == 200
        assert body["channel"] == "alerts"
        assert body["has_more"] is False
        assert [m["payload"]["seq"] for m in body["messages"]] == [0, 1, 2]


async def test_history_endpoint_filters_by_since(running_server):
    _, ws_url, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch(path):
        with urlopen(f"{http_url}{path}", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    async with websockets.connect(ws_url) as client:
        await _connected(client)
        for i in range(3):
            await client.send(json.dumps({
                "type": "broadcast",
                "payload": {"channel": "alerts", "seq": i},
                "timestamp": f"2026-08-13T00:00:0{i}+00:00",
            }))
            await client.recv()

        status, body = await loop.run_in_executor(
            None, fetch, "/history?channel=alerts&since=2026-08-13T00:00:00%2B00:00"
        )
        assert status == 200
        assert [m["payload"]["seq"] for m in body["messages"]] == [1, 2]


async def test_history_endpoint_paginates_with_has_more(running_server):
    _, ws_url, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch(path):
        with urlopen(f"{http_url}{path}", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    async with websockets.connect(ws_url) as client:
        await _connected(client)
        for i in range(3):
            await client.send(json.dumps({
                "type": "broadcast",
                "payload": {"channel": "alerts", "seq": i},
                "timestamp": f"2026-08-13T00:00:0{i}+00:00",
            }))
            await client.recv()

        status, body = await loop.run_in_executor(None, fetch, "/history?channel=alerts&limit=2")
        assert status == 200
        assert body["limit"] == 2
        assert body["has_more"] is True
        assert [m["payload"]["seq"] for m in body["messages"]] == [0, 1]

        status, body = await loop.run_in_executor(
            None, fetch, "/history?channel=alerts&since=2026-08-13T00:00:01%2B00:00&limit=2"
        )
        assert status == 200
        assert body["has_more"] is False
        assert [m["payload"]["seq"] for m in body["messages"]] == [2]


async def test_history_endpoint_only_returns_matching_channel(running_server):
    _, ws_url, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch(path):
        with urlopen(f"{http_url}{path}", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    async with websockets.connect(ws_url) as client:
        await _connected(client)
        await client.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "alert msg"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await client.recv()
        await client.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "chat", "text": "chat msg"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await client.recv()

        status, body = await loop.run_in_executor(None, fetch, "/history?channel=alerts")
        assert status == 200
        assert len(body["messages"]) == 1
        assert body["messages"][0]["payload"]["text"] == "alert msg"


async def test_rate_limit_is_configurable_via_env_var(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "5")
    app = NotificationServer()
    try:
        assert app.rate_limiter.limit == 5
    finally:
        await app.close()


async def test_message_ttl_is_configurable_via_env_var(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    app = NotificationServer()
    try:
        assert app.message_ttl_days == 3
    finally:
        await app.close()


async def test_expired_messages_are_cleaned_up_on_startup(tmp_path):
    from notification_server.store import MessageStore

    db_path = str(tmp_path / "history.db")
    seed_store = MessageStore(db_path)
    seed_store.save_message("broadcast", {"text": "ancient"}, "2000-01-01T00:00:00+00:00", channel="alerts")
    seed_store.save_message("broadcast", {"text": "fresh"}, "2026-08-13T00:00:00+00:00", channel="alerts")
    seed_store.close()

    app = NotificationServer(db_path=db_path, message_ttl_days=7)
    try:
        await app.start()
        await asyncio.sleep(0.05)
        messages, _ = app.store.get_history(channel="alerts")
        assert [m["payload"]["text"] for m in messages] == ["fresh"]
    finally:
        await app.close()


async def test_health_endpoint_reports_connected_client_count(running_server):
    _, ws_url, http_url = running_server
    loop = asyncio.get_running_loop()

    def fetch():
        with urlopen(f"{http_url}/health", timeout=2) as resp:
            return resp.status, json.loads(resp.read())

    status, body = await loop.run_in_executor(None, fetch)
    assert status == 200
    assert body == {"connected_clients": 0}

    async with websockets.connect(ws_url) as client:
        await _connected(client)
        status, body = await loop.run_in_executor(None, fetch)
        assert status == 200
        assert body == {"connected_clients": 1}
