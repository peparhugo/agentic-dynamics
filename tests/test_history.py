import asyncio
import json
import os
import tempfile

import aiohttp
import pytest
import websockets

from notification_server.messages import Message
from notification_server.persistence import MessageStore


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = MessageStore(path)
    try:
        yield s
    finally:
        s.close()
        os.remove(path)


def test_history_returns_messages_in_chronological_order(store):
    for i in range(3):
        store.save(Message(type="broadcast", payload={"i": i}, timestamp=f"2026-01-01T00:00:0{i}+00:00"))

    result = store.history(limit=50)
    assert [m["payload"]["i"] for m in result["messages"]] == [0, 1, 2]


def test_history_filters_by_channel(store):
    store.save(Message(type="broadcast", payload={"text": "a"}, timestamp="t1", channel="alerts"))
    store.save(Message(type="broadcast", payload={"text": "b"}, timestamp="t2", channel="chat"))
    store.save(Message(type="broadcast", payload={"text": "c"}, timestamp="t3", channel="alerts"))

    result = store.history(channel="alerts", limit=50)
    assert [m["payload"]["text"] for m in result["messages"]] == ["a", "c"]


def test_history_filters_by_since(store):
    store.save(Message(type="broadcast", payload={"text": "old"}, timestamp="2026-01-01T00:00:00+00:00"))
    store.save(Message(type="broadcast", payload={"text": "new"}, timestamp="2026-01-02T00:00:00+00:00"))

    result = store.history(since="2026-01-02T00:00:00+00:00", limit=50)
    assert [m["payload"]["text"] for m in result["messages"]] == ["new"]


def test_history_since_is_inclusive(store):
    store.save(Message(type="broadcast", payload={"text": "exact"}, timestamp="2026-01-02T00:00:00+00:00"))

    result = store.history(since="2026-01-02T00:00:00+00:00", limit=50)
    assert [m["payload"]["text"] for m in result["messages"]] == ["exact"]


def test_history_combines_channel_and_since_filters(store):
    store.save(Message(type="broadcast", payload={"text": "wrong channel"}, timestamp="2026-01-02T00:00:00+00:00", channel="chat"))
    store.save(Message(type="broadcast", payload={"text": "too old"}, timestamp="2026-01-01T00:00:00+00:00", channel="alerts"))
    store.save(Message(type="broadcast", payload={"text": "match"}, timestamp="2026-01-03T00:00:00+00:00", channel="alerts"))

    result = store.history(channel="alerts", since="2026-01-02T00:00:00+00:00", limit=50)
    assert [m["payload"]["text"] for m in result["messages"]] == ["match"]


def test_history_has_more_true_when_more_rows_exist(store):
    for i in range(5):
        store.save(Message(type="broadcast", payload={"i": i}, timestamp=f"t{i}"))

    result = store.history(limit=3)
    assert [m["payload"]["i"] for m in result["messages"]] == [0, 1, 2]
    assert result["has_more"] is True


def test_history_has_more_false_when_all_rows_returned(store):
    for i in range(3):
        store.save(Message(type="broadcast", payload={"i": i}, timestamp=f"t{i}"))

    result = store.history(limit=50)
    assert result["has_more"] is False


def test_history_empty_store_returns_empty_and_no_more(store):
    result = store.history(limit=50)
    assert result == {"messages": [], "has_more": False}


async def recv_json(ws, timeout=2):
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


async def connect_and_get_id(uri):
    ws = await websockets.connect(uri)
    welcome = await recv_json(ws)
    return ws, welcome["payload"]["client_id"]


async def test_history_endpoint_returns_paginated_chronological_results(running_server):
    _, uri, health_url = running_server
    history_url = health_url.replace("/health", "/history")

    ws1, id1 = await connect_and_get_id(uri)
    try:
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1)  # subscribed ack

        for i in range(3):
            await ws1.send(json.dumps({
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"i": i},
            }))
            await recv_json(ws1)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{history_url}?channel=alerts&limit=2") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert [m["payload"]["i"] for m in data["messages"]] == [0, 1]
                assert data["has_more"] is True

        # a fresh session, since this websockets version doesn't reliably
        # keep a plain-HTTP connection alive across back-to-back requests.
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{history_url}?channel=alerts&limit=2&since={data['messages'][1]['timestamp']}") as resp:
                data2 = await resp.json()
                assert data2["messages"][0]["payload"]["i"] == 1
    finally:
        await ws1.close()


async def test_history_endpoint_filters_by_channel(running_server):
    _, uri, health_url = running_server
    history_url = health_url.replace("/health", "/history")

    ws1, _ = await connect_and_get_id(uri)
    try:
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1)  # subscribed ack
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await recv_json(ws1)  # subscribed ack

        await ws1.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "a"}}))
        await recv_json(ws1)
        await ws1.send(json.dumps({"type": "broadcast", "channel": "chat", "payload": {"text": "b"}}))
        await recv_json(ws1)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{history_url}?channel=chat") as resp:
                data = await resp.json()
                assert len(data["messages"]) == 1
                assert data["messages"][0]["payload"]["text"] == "b"
    finally:
        await ws1.close()


async def test_history_endpoint_empty_when_no_messages(running_server):
    _, _, health_url = running_server
    history_url = health_url.replace("/health", "/history")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{history_url}?channel=alerts") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data == {"messages": [], "has_more": False}
