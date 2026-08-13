"""Message validation and handling for the notification server."""

import json
from datetime import datetime
from typing import Dict, Any, Optional


class Message:
    """Represents a notification message."""

    SUPPORTED_TYPES = {'broadcast', 'direct', 'system'}

    def __init__(self, message_type: str, payload: Dict[str, Any], timestamp: Optional[str] = None):
        self.type = message_type
        self.payload = payload
        self.timestamp = timestamp or datetime.utcnow().isoformat()

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps({
            'type': self.type,
            'payload': self.payload,
            'timestamp': self.timestamp
        })

    @staticmethod
    def from_json(data: str) -> 'Message':
        """Deserialize message from JSON string."""
        obj = json.loads(data)
        return Message(
            message_type=obj.get('type'),
            payload=obj.get('payload', {}),
            timestamp=obj.get('timestamp')
        )


class MessageHandler:
    """Validates and handles notification messages."""

    SUPPORTED_TYPES = {'broadcast', 'direct', 'system'}

    @staticmethod
    def validate_message(data: str) -> bool:
        """Validate message format and structure."""
        try:
            obj = json.loads(data)
            return (
                'type' in obj
                and obj['type'] in MessageHandler.SUPPORTED_TYPES
                and 'payload' in obj
                and isinstance(obj['payload'], dict)
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return False
