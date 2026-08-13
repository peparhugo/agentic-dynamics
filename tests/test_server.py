import asyncio
import json
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
