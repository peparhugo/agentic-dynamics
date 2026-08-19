"""Collision-resistant short code generation."""

import secrets
import string

# URL-safe alphabet without ambiguous characters (0/O, 1/l/I removed).
ALPHABET = "23456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"

_DEFAULT_LENGTH = 6


def generate_short_code(length: int = _DEFAULT_LENGTH) -> str:
    """Generate a cryptographically random short code.

    Uses :func:`secrets.choice` (backed by the OS CSPRNG) so codes are
    unpredictable and collision-resistant. The alphabet is base-56, so a
    6-character code has 56**6 (~30 billion) combinations.
    """
    if length < 1:
        raise ValueError("length must be a positive integer")
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_unique_short_code(exists, length: int = _DEFAULT_LENGTH,
                               max_attempts: int = 10) -> str:
    """Generate a code that is unique according to ``exists``.

    ``exists`` is a callable that returns ``True`` when a candidate code is
    already taken. Retries on collision, raising :class:`RuntimeError` if the
    collision space cannot be satisfied within ``max_attempts``.
    """
    for _ in range(max_attempts):
        code = generate_short_code(length)
        if not exists(code):
            return code
    raise RuntimeError(
        f"could not generate a unique short code after {max_attempts} attempts"
    )
