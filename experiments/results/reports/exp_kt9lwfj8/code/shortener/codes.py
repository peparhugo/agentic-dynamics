"""Short code generation and validation."""

from __future__ import annotations

import re
import secrets

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
CUSTOM_CODE_RE = re.compile(r"^[0-9A-Za-z_-]{3,32}$")
RESERVED = {"api", "health", "static"}


def generate_code(length: int = 7) -> str:
    """Cryptographically random base62 code."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid_custom_code(code: str) -> bool:
    return bool(CUSTOM_CODE_RE.match(code)) and code.lower() not in RESERVED
