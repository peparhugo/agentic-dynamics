import json

import pytest

from notification_server.messages import Message, MessageValidationError


def test_valid_broadcast_message_from_json():
    raw = json.dumps({"type": "broadcast", "payload": {"text": "hi"}, "timestamp": "2026-01-01T00:00:00+00:00"})
    message = Message.from_json(raw)
    assert message.type == "broadcast"
    assert message.payload == {"text": "hi"}
    assert message.timestamp == "2026-01-01T00:00:00+00:00"


def test_valid_direct_message_from_dict():
    message = Message.from_dict({"type": "direct", "payload": {"target": "abc", "text": "hi"}})
    assert message.type == "direct"
    assert message.payload["target"] == "abc"


def test_valid_system_message():
    message = Message.from_dict({"type": "system", "payload": {}})
    assert message.type == "system"


@pytest.mark.parametrize("bad_type", [None, "", "unknown", "BROADCAST", 123])
def test_invalid_type_raises(bad_type):
    with pytest.raises(MessageValidationError):
        Message.from_dict({"type": bad_type, "payload": {}})


def test_missing_type_raises():
    with pytest.raises(MessageValidationError):
        Message.from_dict({"payload": {}})


def test_invalid_json_raises():
    with pytest.raises(MessageValidationError):
        Message.from_json("{not valid json")


def test_non_object_json_raises():
    with pytest.raises(MessageValidationError):
        Message.from_json("[1, 2, 3]")


def test_payload_must_be_object():
    with pytest.raises(MessageValidationError):
        Message.from_dict({"type": "broadcast", "payload": "not a dict"})


def test_default_payload_and_timestamp_are_populated():
    message = Message.from_dict({"type": "system"})
    assert message.payload == {}
    assert isinstance(message.timestamp, str) and message.timestamp


def test_to_dict_and_to_json_round_trip():
    message = Message(type="broadcast", payload={"a": 1}, timestamp="2026-01-01T00:00:00+00:00")
    as_dict = message.to_dict()
    assert as_dict == {"type": "broadcast", "payload": {"a": 1}, "timestamp": "2026-01-01T00:00:00+00:00"}
    round_tripped = Message.from_json(message.to_json())
    assert round_tripped == message
