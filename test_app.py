import asyncio
import json

import httpx
import pytest
import pytest_asyncio
import websockets

from app import handler, process_request, registry
from websockets.asyncio.server import serve


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def server_url():
    port = _free_port()
    async with serve(handler, "127.0.0.1", port, process_request=process_request) as srv:
        yield f"ws://127.0.0.1:{port}"
    registry._clients.clear()
    registry._channels.clear()
    registry._client_channels.clear()


async def _recv_json(ws):
    raw = await ws.recv()
    return json.loads(raw)


class TestConnection:
    @pytest.mark.asyncio
    async def test_connect_receives_welcome(self, server_url):
        async with websockets.connect(server_url) as ws:
            msg = await _recv_json(ws)
            assert msg["type"] == "system"
            assert msg["payload"]["message"] == "connected"
            assert "client_id" in msg["payload"]

    @pytest.mark.asyncio
    async def test_unique_client_ids(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            m1 = await _recv_json(ws1)
            m2 = await _recv_json(ws2)
            assert m1["payload"]["client_id"] != m2["payload"]["client_id"]

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_disconnect_notifies_others(self, server_url):
        async with websockets.connect(server_url) as ws1:
            w1 = await _recv_json(ws1)
            cid1 = w1["payload"]["client_id"]

            async with websockets.connect(server_url) as ws2:
                await _recv_json(ws2)

            disconnect_msg = await _recv_json(ws1)
            assert disconnect_msg["type"] == "system"
            assert disconnect_msg["payload"]["message"] == "disconnected"
            assert "client_id" in disconnect_msg["payload"]
            assert disconnect_msg["payload"]["client_id"] != cid1


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            payload = {"text": "hello everyone"}
            await ws1.send(
                json.dumps({"type": "broadcast", "payload": payload})
            )

            msg_on_ws2 = await _recv_json(ws2)
            assert msg_on_ws2["type"] == "broadcast"
            assert msg_on_ws2["payload"]["text"] == "hello everyone"

    @pytest.mark.asyncio
    async def test_broadcast_includes_from(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            cid1 = w1["payload"]["client_id"]
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "broadcast", "payload": {"x": 1}})
            )

            msg = await _recv_json(ws2)
            assert msg["payload"]["from"] == cid1


class TestDirect:
    @pytest.mark.asyncio
    async def test_direct_message(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            w2 = await _recv_json(ws2)
            cid1 = w1["payload"]["client_id"]
            cid2 = w2["payload"]["client_id"]

            await ws1.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": cid2, "message": "secret"},
                    }
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == cid1
            assert msg["payload"]["message"] == "secret"

    @pytest.mark.asyncio
    async def test_direct_nonexistent_silent(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": "no-such-id", "message": "hi"},
                    }
                )
            )
            await asyncio.sleep(0.05)


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_count(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["connected_clients"] == 1

    @pytest.mark.asyncio
    async def test_health_zero(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected_clients"] == 0


class TestSystem:
    @pytest.mark.asyncio
    async def test_invalid_json_ignored(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send("not json!!!")
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_message_has_timestamp(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)
            await ws1.send(
                json.dumps({"type": "broadcast", "payload": {"text": "ts"}})
            )
            msg = await _recv_json(ws2)
            assert "timestamp" in msg
            assert isinstance(msg["timestamp"], str)


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_receives_confirmation(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )

            resp = await _recv_json(ws)
            assert resp["type"] == "system"
            assert resp["payload"]["message"] == "subscribed to alerts"
            assert resp["payload"]["channel"] == "alerts"

    @pytest.mark.asyncio
    async def test_unsubscribe_receives_confirmation(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "unsubscribe", "channel": "alerts"})
            )

            resp = await _recv_json(ws)
            assert resp["type"] == "system"
            assert resp["payload"]["message"] == "unsubscribed from alerts"
            assert resp["payload"]["channel"] == "alerts"

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_channel_silent(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps(
                    {"type": "unsubscribe", "channel": "nonexistent"}
                )
            )

            resp = await _recv_json(ws)
            assert resp["type"] == "system"
            assert resp["payload"]["channel"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_subscribe_multiple_channels(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            r1 = await _recv_json(ws)
            assert r1["payload"]["channel"] == "alerts"

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "chat"})
            )
            r2 = await _recv_json(ws)
            assert r2["payload"]["channel"] == "chat"

    @pytest.mark.asyncio
    async def test_subscribe_missing_channel_ignored(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(json.dumps({"type": "subscribe"}))
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_unsubscribe_missing_channel_ignored(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(json.dumps({"type": "unsubscribe"}))
            await asyncio.sleep(0.05)


class TestChannelBroadcast:
    @pytest.mark.asyncio
    async def test_channel_message_reaches_subscribers(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)
            await ws2.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)

            await ws1.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"text": "alert!"},
                    }
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "alert!"

    @pytest.mark.asyncio
    async def test_channel_message_excludes_nonsubscribers(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)

            await ws1.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"text": "alert!"},
                    }
                )
            )

            await _recv_json(ws1)

            try:
                msg = await asyncio.wait_for(ws2.recv(), timeout=0.1)
                assert False, "ws2 should not receive channel message"
            except asyncio.TimeoutError:
                pass

    @pytest.mark.asyncio
    async def test_broadcast_without_channel_still_broadcasts_to_all(
        self, server_url
    ):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps(
                    {"type": "broadcast", "payload": {"text": "to all"}}
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "to all"

    @pytest.mark.asyncio
    async def test_channel_message_to_empty_channel(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "nonexistent",
                        "payload": {"text": "nobody"},
                    }
                )
            )
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_receiving(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)
            await ws2.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)

            await ws2.send(
                json.dumps({"type": "unsubscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)

            await ws1.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"text": "after"},
                    }
                )
            )

            await _recv_json(ws1)

            try:
                msg = await asyncio.wait_for(ws2.recv(), timeout=0.1)
                assert False, "ws2 should not receive after unsubscribing"
            except asyncio.TimeoutError:
                pass

    @pytest.mark.asyncio
    async def test_direct_message_still_works(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            w2 = await _recv_json(ws2)
            cid1 = w1["payload"]["client_id"]
            cid2 = w2["payload"]["client_id"]

            await ws1.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": cid2, "message": "hello"},
                    }
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == cid1
            assert msg["payload"]["message"] == "hello"


class TestChannelsEndpoint:
    @pytest.mark.asyncio
    async def test_channels_list_empty(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/channels")
            assert resp.status_code == 200
            data = resp.json()
            assert data == {}

    @pytest.mark.asyncio
    async def test_channels_list_with_subscribers(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)
            await ws2.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)
            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "chat"})
            )
            await _recv_json(ws1)

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/channels")
                assert resp.status_code == 200
                data = resp.json()
                assert data["alerts"] == 2
                assert data["chat"] == 1

    @pytest.mark.asyncio
    async def test_channels_subscribers_list(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws1:
            w1 = await _recv_json(ws1)
            cid1 = w1["payload"]["client_id"]

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{http_url}/channels/alerts/subscribers"
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["channel"] == "alerts"
                assert data["subscribers"] == [cid1]

    @pytest.mark.asyncio
    async def test_channels_subscribers_nonexistent_channel(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{http_url}/channels/nonexistent/subscribers"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["channel"] == "nonexistent"
            assert data["subscribers"] == []

    @pytest.mark.asyncio
    async def test_channels_cleanup_on_unsubscribe(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws)

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/channels")
                assert resp.json() == {"alerts": 1}

            await ws.send(
                json.dumps({"type": "unsubscribe", "channel": "alerts"})
            )
            await _recv_json(ws)

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/channels")
                assert resp.json() == {}


class TestDisconnectChannelCleanup:
    @pytest.mark.asyncio
    async def test_disconnect_removes_from_channels(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)

            await ws.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws)

        await asyncio.sleep(0.1)

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/channels")
            assert resp.json() == {}

    @pytest.mark.asyncio
    async def test_disconnect_notifies_channel_members(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws1)
            await ws2.send(
                json.dumps({"type": "subscribe", "channel": "alerts"})
            )
            await _recv_json(ws2)

        await asyncio.sleep(0.1)
