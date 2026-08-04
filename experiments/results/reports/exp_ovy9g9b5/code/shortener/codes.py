"""Collision-resistant short code generation.

Codes are random base62 strings drawn from a CSPRNG. Collision resistance
comes from two layers:

1. A large keyspace (62^7 ~ 3.5 trillion for the default length), making
   random collisions vanishingly rare.
2. An explicit check-and-retry loop against the database unique constraint;
   if a collision does occur we retry, growing the code length after
   repeated failures so generation always terminates quickly.
"""

from __future__ import annotations

import secrets
import string
from typing import Callable

ALPHABET = string.ascii_letters + string.digits  # base62
DEFAULT_LENGTH = 7
MAX_ATTEMPTS_PER_LENGTH = 5
MAX_LENGTH = 16


def random_code(length: int = DEFAULT_LENGTH) -> str:
    """Return a random base62 code of the given length."""
    if length < 1:
        raise ValueError("length must be >= 1")
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_unique_code(
    exists: Callable[[str], bool],
    length: int = DEFAULT_LENGTH,
) -> str:
    """Generate a code for which ``exists(code)`` is False.

    Retries on collision; escalates length if a given length keeps
    colliding, so the function terminates even in a pathological store.
    """
    current = length
    while current <= MAX_LENGTH:
        for _ in range(MAX_ATTEMPTS_PER_LENGTH):
            code = random_code(current)
            if not exists(code):
                return code
        current += 1
    raise RuntimeError("could not generate a unique short code")


def is_valid_code(code: str) -> bool:
    """True if the code looks like one of ours (base62, sane length)."""
    return (
        1 <= len(code) <= MAX_LENGTH
        and all(c in ALPHABET for c in code)
    )
