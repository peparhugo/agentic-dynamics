"""Tests for short code generation."""

import pytest

from shortener.shortcodes import (
    ALPHABET,
    generate_short_code,
    generate_unique_short_code,
)


def test_default_length():
    assert len(generate_short_code()) == 6


def test_custom_length():
    assert len(generate_short_code(8)) == 8


def test_alphabet_only():
    for _ in range(100):
        code = generate_short_code()
        assert all(ch in ALPHABET for ch in code)


def test_codes_are_random_and_unique():
    codes = {generate_short_code() for _ in range(1000)}
    assert len(codes) == 1000


def test_invalid_length_raises():
    with pytest.raises(ValueError):
        generate_short_code(0)


def test_unique_code_skips_collisions():
    seen = set()
    result = generate_unique_short_code(
        lambda c: c in seen, max_attempts=100
    )
    assert result not in seen


def test_unique_code_uses_first_non_colliding(monkeypatch):
    # Force a deterministic candidate sequence.
    _candidates = iter(["abc", "def", "ghi"])
    monkeypatch.setattr(
        "shortener.shortcodes.generate_short_code",
        lambda length=6: next(_candidates),
    )

    calls = {"n": 0}

    def exists(code):
        calls["n"] += 1
        return code in ("abc", "def")

    result = generate_unique_short_code(exists, length=3, max_attempts=10)
    assert result == "ghi"
    assert calls["n"] == 3


def test_unique_code_gives_up_after_max_attempts():
    with pytest.raises(RuntimeError):
        generate_unique_short_code(lambda c: True, max_attempts=5)
