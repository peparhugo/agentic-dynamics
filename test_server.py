import os
import tempfile

_temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="test_chat_")
_temp_db_path = _temp_db.name
_temp_db.close()
os.environ["DATABASE_URL"] = _temp_db_path

import asyncio
import json
import sqlite3
import time

import pytest
import websockets
from aiohttp import ClientSession

from server import (
    DATABASE_URL,
    _channels,
    _db_lock,
    _registry,
    get_messages,
    start_server,
)

HOST = "127.0.0.1"
WS_PORT = 18765
HTTP_PORT = 18080


def _clear_messages_table():
    with _db_lock:
        conn = sqlite3.connect(DATABASE_URL)
        conn.execute("DELETE FROM messages")
        conn.commit()
        conn.close()


@pytest.fixture(autouse=True)
def reset_registry():
    _registry.clear()
    _channels.clear()
    _clear_messages_table()
    yield
    _registry.clear()
    _channels.clear()
    _clear_messages_table()


@pytest.fixture(scope="module")
def server():
    t1, t2 = start_server(HOST, WS_PORT, HTTP_PORT)
    time.sleep(0.3)
    yield
    # Daemon threads, nothing to explicitly stop


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_zero_when_no_clients(self, server):
        async with ClientSession() as session:
            async with session.get(f"http://{HOST}:{HTTP_PORT}/health") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["clients"] == 0

    @pytest.mark.asyncio
    async def test_health_reflects_connected_clients(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
            await ws1.recv()
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
                await ws2.recv()
                await asyncio.sleep(0.1)
                async with ClientSession() as session:
                    async with session.get(f"http://{HOST}:{HTTP_PORT}/health") as resp:
                        data = await resp.json()
                        assert data["clients"] == 2


class TestClientConnection:
    @pytest.mark.asyncio
    async def test_connect_receives_welcome_message(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            raw = await ws.recv()
            data = json.loads(raw)
            assert data["type"] == "system"
            assert "client_id" in data["payload"]
            assert data["payload"]["message"] == "Connected"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_connect_assigns_unique_ids(self, server):
        ids = set()
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
            d1 = json.loads(await ws1.recv())
            ids.add(d1["payload"]["client_id"])
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
                d2 = json.loads(await ws2.recv())
                ids.add(d2["payload"]["client_id"])
        assert len(ids) == 2

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            await ws.recv()
            assert _registry.count() == 1
        await asyncio.sleep(0.2)
        assert _registry.count() == 0


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_all(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "hello all"}
            }))

            msg2_raw = await asyncio.wait_for(ws2.recv(), timeout=2)
            msg2 = json.loads(msg2_raw)
            assert msg2["type"] == "broadcast"
            assert msg2["payload"]["text"] == "hello all"

    @pytest.mark.asyncio
    async def test_broadcast_sender_does_not_receive_own_message(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            d1 = json.loads(await ws1.recv())
            sender_id = d1["payload"]["client_id"]
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "hello"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert msg["from"] == sender_id


class TestDirectMessage:
    @pytest.mark.asyncio
    async def test_direct_message_delivers_to_target(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws3:
            d1 = json.loads(await ws1.recv())
            d2 = json.loads(await ws2.recv())
            d3 = json.loads(await ws3.recv())

            target_id = d2["payload"]["client_id"]

            await ws1.send(json.dumps({
                "type": "direct",
                "payload": {"target": target_id, "text": "secret"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert msg["type"] == "direct"
            assert msg["payload"]["text"] == "secret"
            assert msg["from"] == d1["payload"]["client_id"]

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws3.recv(), timeout=0.5)


class TestDisconnectNotification:
    @pytest.mark.asyncio
    async def test_disconnect_notifies_remaining_clients(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
            d1 = json.loads(await ws1.recv())
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
                d2 = json.loads(await ws2.recv())
                # Close ws2
                await ws2.close()
                await asyncio.sleep(0.2)
                # ws1 should receive disconnect notification for ws2's client_id
                notify = json.loads(await asyncio.wait_for(ws1.recv(), timeout=3))
                assert notify["type"] == "system"
                assert notify["payload"]["message"] == "Disconnected"
                assert notify["payload"]["client_id"] == d2["payload"]["client_id"]


class TestMessageFormat:
    @pytest.mark.asyncio
    async def test_message_has_required_fields(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "check format"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert "type" in msg
            assert "payload" in msg
            assert "timestamp" in msg
            assert msg["type"] == "broadcast"

    @pytest.mark.asyncio
    async def test_invalid_json_is_gracefully_ignored(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send("not json")

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws2.recv(), timeout=0.5)


class TestThreadSafety:
    @pytest.mark.asyncio
    async def test_concurrent_connections(self, server):
        async def connect_and_send():
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
                await ws.recv()
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"text": "concurrent"}
                }))

        tasks = [asyncio.create_task(connect_and_send()) for _ in range(10)]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.2)
        assert _registry.count() == 0


class TestSystemMessage:
    @pytest.mark.asyncio
    async def test_system_message_on_connect(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            msg = json.loads(await ws.recv())
            assert msg["type"] == "system"
            assert msg["payload"]["message"] == "Connected"


class TestChannelsEndpoint:
    @pytest.mark.asyncio
    async def test_channels_returns_empty_when_no_subscriptions(self, server):
        async with ClientSession() as session:
            async with session.get(f"http://{HOST}:{HTTP_PORT}/channels") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data == {}

    @pytest.mark.asyncio
    async def test_channels_returns_active_channels(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await ws2.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await ws2.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "chat"}
            }))
            await asyncio.sleep(0.1)

            async with ClientSession() as session:
                async with session.get(f"http://{HOST}:{HTTP_PORT}/channels") as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data == {"alerts": 2, "chat": 1}

    @pytest.mark.asyncio
    async def test_channels_removes_channel_when_no_subscribers(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "temp"}
            }))
            await asyncio.sleep(0.1)
            await ws.send(json.dumps({
                "type": "unsubscribe",
                "payload": {"channel": "temp"}
            }))
            await asyncio.sleep(0.1)

            async with ClientSession() as session:
                async with session.get(f"http://{HOST}:{HTTP_PORT}/channels") as resp:
                    data = await resp.json()
                    assert "temp" not in data


class TestChannelSubscribersEndpoint:
    @pytest.mark.asyncio
    async def test_channel_subscribers_lists_ids(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            d1 = json.loads(await ws1.recv())
            d2 = json.loads(await ws2.recv())
            cid1 = d1["payload"]["client_id"]
            cid2 = d2["payload"]["client_id"]

            await ws1.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await ws2.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)

            async with ClientSession() as session:
                async with session.get(f"http://{HOST}:{HTTP_PORT}/channels/alerts/subscribers") as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert set(data) == {cid1, cid2}

    @pytest.mark.asyncio
    async def test_channel_subscribers_unknown_channel_returns_empty(self, server):
        async with ClientSession() as session:
            async with session.get(f"http://{HOST}:{HTTP_PORT}/channels/nonexistent/subscribers") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data == []


class TestChannelSubscription:
    @pytest.mark.asyncio
    async def test_subscribe_adds_to_channel(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)
            assert "alerts" in _channels.list_channels()

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_from_channel(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)
            assert "alerts" in _channels.list_channels()

            await ws.send(json.dumps({
                "type": "unsubscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)
            assert "alerts" not in _channels.list_channels()

    @pytest.mark.asyncio
    async def test_client_can_subscribe_to_multiple_channels(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "chat"}
            }))
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)

            channels = _channels.list_channels()
            assert channels.get("chat") == 1
            assert channels.get("alerts") == 1

    @pytest.mark.asyncio
    async def test_disconnect_unsubscribes_from_all_channels(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "chat"}
            }))
            await asyncio.sleep(0.1)
            assert "alerts" in _channels.list_channels()
            assert "chat" in _channels.list_channels()

        await asyncio.sleep(0.3)
        assert "alerts" not in _channels.list_channels()
        assert "chat" not in _channels.list_channels()


class TestChannelBroadcast:
    @pytest.mark.asyncio
    async def test_channel_message_only_delivers_to_subscribers(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws3:
            await ws1.recv()
            await ws2.recv()
            await ws3.recv()

            await ws1.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await ws2.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)

            await ws1.send(json.dumps({
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": "alert!"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "alert!"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws3.recv(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_no_channel_messages_still_broadcast_to_all(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "everyone"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert msg["payload"]["text"] == "everyone"

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_receiving_channel_messages(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws2.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)

            await ws1.send(json.dumps({
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": "msg1"}
            }))
            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert msg["payload"]["text"] == "msg1"

            await ws2.send(json.dumps({
                "type": "unsubscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)

            await ws1.send(json.dumps({
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": "msg2"}
            }))

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws2.recv(), timeout=0.5)


class TestMessagePersistence:
    @pytest.mark.asyncio
    async def test_messages_endpoint_returns_empty_when_no_messages(self, server):
        async with ClientSession() as session:
            async with session.get(
                f"http://{HOST}:{HTTP_PORT}/messages?limit=50&offset=0"
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data == []

    @pytest.mark.asyncio
    async def test_broadcast_message_is_persisted(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "persist me"}
            }))
            await asyncio.wait_for(ws2.recv(), timeout=2)
            await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get(
                f"http://{HOST}:{HTTP_PORT}/messages?limit=50&offset=0"
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert len(data) >= 1
                msg = data[0]
                assert msg["type"] == "broadcast"
                assert msg["payload"] == {"text": "persist me"}
                assert "id" in msg
                assert "timestamp" in msg

    @pytest.mark.asyncio
    async def test_channel_message_is_persisted_with_channel(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws2.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"}
            }))
            await asyncio.sleep(0.1)

            await ws1.send(json.dumps({
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": "channel msg"}
            }))
            await asyncio.wait_for(ws2.recv(), timeout=2)
            await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get(
                f"http://{HOST}:{HTTP_PORT}/messages?limit=50&offset=0"
            ) as resp:
                data = await resp.json()
                assert len(data) >= 1
                channel_msgs = [m for m in data if m["payload"].get("text") == "channel msg"]
                assert len(channel_msgs) >= 1
                assert channel_msgs[0]["channel"] == "alerts"
                assert channel_msgs[0]["type"] == "broadcast"

    @pytest.mark.asyncio
    async def test_direct_message_is_persisted(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            d1 = json.loads(await ws1.recv())
            d2 = json.loads(await ws2.recv())
            target_id = d2["payload"]["client_id"]

            await ws1.send(json.dumps({
                "type": "direct",
                "payload": {"target": target_id, "text": "direct persist"}
            }))
            await asyncio.wait_for(ws2.recv(), timeout=2)
            await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get(
                f"http://{HOST}:{HTTP_PORT}/messages?limit=50&offset=0"
            ) as resp:
                data = await resp.json()
                direct_msgs = [m for m in data if m["payload"].get("text") == "direct persist"]
                assert len(direct_msgs) >= 1
                assert direct_msgs[0]["type"] == "direct"

    @pytest.mark.asyncio
    async def test_messages_endpoint_respects_limit(self, server):
        async def send_and_consume(text):
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws_send, \
                       websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws_recv:
                await ws_send.recv()
                await ws_recv.recv()
                await ws_send.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"text": text}
                }))
                await asyncio.wait_for(ws_recv.recv(), timeout=2)
                await asyncio.sleep(0.1)

        for i in range(5):
            await send_and_consume(f"msg-{i}")

        async with ClientSession() as session:
            async with session.get(
                f"http://{HOST}:{HTTP_PORT}/messages?limit=3&offset=0"
            ) as resp:
                data = await resp.json()
                assert len(data) == 3

    @pytest.mark.asyncio
    async def test_messages_endpoint_respects_offset(self, server):
        async def send_and_consume(text):
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws_send, \
                       websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws_recv:
                await ws_send.recv()
                await ws_recv.recv()
                await ws_send.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"text": text}
                }))
                await asyncio.wait_for(ws_recv.recv(), timeout=2)
                await asyncio.sleep(0.1)

        for i in range(5):
            await send_and_consume(f"offset-{i}")

        async with ClientSession() as session:
            async with session.get(
                f"http://{HOST}:{HTTP_PORT}/messages?limit=50&offset=0"
            ) as resp:
                all_data = await resp.json()
            async with session.get(
                f"http://{HOST}:{HTTP_PORT}/messages?limit=50&offset=2"
            ) as resp:
                offset_data = await resp.json()
            assert len(offset_data) == len(all_data) - 2
