import json

import pytest

from notification_server.messages import (
    InvalidMessage,
    error_message,
    make_message,
    parse_message,
)


def test_parse_valid_broadcast_message():
    raw = json.dumps({"type": "broadcast", "payload": {"text": "hi"}, "timestamp": "2026-01-01T00:00:00Z"})
    msg = parse_message(raw)
    assert msg == {"type": "broadcast", "payload": {"text": "hi"}, "timestamp": "2026-01-01T00:00:00Z"}


def test_parse_fills_in_missing_timestamp():
    raw = json.dumps({"type": "system", "payload": {}})
    msg = parse_message(raw)
    assert msg["timestamp"]


def test_parse_rejects_invalid_json():
    with pytest.raises(InvalidMessage):
        parse_message("not json")


def test_parse_rejects_non_object_json():
    with pytest.raises(InvalidMessage):
        parse_message(json.dumps([1, 2, 3]))


def test_parse_rejects_unsupported_type():
    with pytest.raises(InvalidMessage):
        parse_message(json.dumps({"type": "bogus", "payload": {}}))


def test_parse_rejects_non_object_payload():
    with pytest.raises(InvalidMessage):
        parse_message(json.dumps({"type": "broadcast", "payload": "nope"}))


@pytest.mark.parametrize("msg_type", ["broadcast", "direct", "system"])
def test_parse_accepts_all_valid_types(msg_type):
    raw = json.dumps({"type": msg_type, "payload": {}})
    msg = parse_message(raw)
    assert msg["type"] == msg_type


def test_make_message_rejects_unsupported_type():
    with pytest.raises(InvalidMessage):
        make_message("bogus", {})


def test_error_message_shape():
    err = error_message("boom")
    assert err["type"] == "system"
    assert err["payload"]["event"] == "error"
    assert err["payload"]["message"] == "boom"
