import json

import pytest

from notification_server.messages import (
    InvalidMessage,
    build_message,
    encode,
    parse_message,
)


def test_build_message_has_required_fields():
    msg = build_message("broadcast", {"text": "hi"})
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"text": "hi"}
    assert isinstance(msg["timestamp"], str)


def test_build_message_rejects_unknown_type():
    with pytest.raises(InvalidMessage):
        build_message("shout", {})


def test_parse_message_round_trip():
    original = build_message("system", {"event": "ping"}, timestamp="2026-08-13T00:00:00+00:00")
    parsed = parse_message(encode(original))
    assert parsed == original


@pytest.mark.parametrize("raw", ["not json", "[]", "42", '"str"'])
def test_parse_message_rejects_non_object(raw):
    with pytest.raises(InvalidMessage):
        parse_message(raw)


@pytest.mark.parametrize(
    "data",
    [
        {"type": "unknown", "payload": {}, "timestamp": "t"},
        {"type": "broadcast", "payload": "not-a-dict", "timestamp": "t"},
        {"type": "broadcast", "payload": {}, "timestamp": 123},
        {"payload": {}, "timestamp": "t"},
        {"type": "broadcast", "timestamp": "t"},
    ],
)
def test_parse_message_rejects_bad_schema(data):
    with pytest.raises(InvalidMessage):
        parse_message(json.dumps(data))
