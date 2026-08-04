"""Base62 short code generation and validation."""

from __future__ import annotations

import re
import secrets
import string

ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

# Custom codes: 4-32 chars, base62 plus hyphen/underscore.
CUSTOM_CODE_RE = re.compile(r"^[0-9a-zA-Z_-]{4,32}$")


def generate_code(length: int = 6) -> str:
    """Return a cryptographically random base62 code."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid_custom_code(code: str) -> bool:
    return bool(CUSTOM_CODE_RE.match(code))
