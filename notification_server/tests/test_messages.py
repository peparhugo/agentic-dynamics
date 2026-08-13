import pytest

from notification_server.messages import (
    MessageError,
    encode,
    make_message,
    parse_client_message,
)


def test_make_message_has_required_fields():
    message = make_message("broadcast", {"text": "hi"})
    assert message["type"] == "broadcast"
    assert message["payload"] == {"text": "hi"}
    assert "timestamp" in message and isinstance(message["timestamp"], str)


def test_make_message_rejects_unsupported_type():
    with pytest.raises(ValueError):
        make_message("not-a-type", {})


def test_encode_round_trips_through_json():
    import json

    message = make_message("system", {"event": "ack"})
    assert json.loads(encode(message)) == message


@pytest.mark.parametrize("msg_type", ["broadcast", "direct", "system", "subscribe", "unsubscribe"])
def test_parse_client_message_accepts_supported_types(msg_type):
    raw = '{"type": "%s", "payload": {"a": 1}}' % msg_type
    parsed = parse_client_message(raw)
    assert parsed == {"type": msg_type, "payload": {"a": 1}}


def test_parse_client_message_defaults_missing_payload_to_empty_dict():
    parsed = parse_client_message('{"type": "system"}')
    assert parsed["payload"] == {}


def test_parse_client_message_rejects_invalid_json():
    with pytest.raises(MessageError):
        parse_client_message("not json")


def test_parse_client_message_rejects_unsupported_type():
    with pytest.raises(MessageError):
        parse_client_message('{"type": "unknown", "payload": {}}')


def test_parse_client_message_rejects_non_object_payload():
    with pytest.raises(MessageError):
        parse_client_message('{"type": "broadcast", "payload": "oops"}')


def test_parse_client_message_rejects_non_object_message():
    with pytest.raises(MessageError):
        parse_client_message("[1, 2, 3]")
