import string

import pytest

from shortener import codes


class TestRandomCode:
    def test_default_length(self):
        assert len(codes.random_code()) == codes.DEFAULT_LENGTH

    def test_custom_length(self):
        assert len(codes.random_code(12)) == 12

    def test_alphabet_is_base62(self):
        allowed = set(string.ascii_letters + string.digits)
        for _ in range(50):
            assert set(codes.random_code()) <= allowed

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError):
            codes.random_code(0)

    def test_codes_are_random(self):
        generated = {codes.random_code() for _ in range(200)}
        # With a 62^7 keyspace, 200 draws should essentially never collide.
        assert len(generated) == 200


class TestGenerateUniqueCode:
    def test_returns_code_not_in_store(self):
        store = {"aaaaaaa", "bbbbbbb"}
        code = codes.generate_unique_code(lambda c: c in store)
        assert code not in store

    def test_retries_on_collision(self):
        calls = []

        def exists(code):
            calls.append(code)
            return len(calls) < 3  # first two candidates "exist"

        code = codes.generate_unique_code(exists)
        assert len(calls) == 3
        assert code == calls[-1]

    def test_escalates_length_when_saturated(self):
        # A store that rejects every 7-char code forces length growth.
        code = codes.generate_unique_code(lambda c: len(c) == 7)
        assert len(code) > 7

    def test_gives_up_eventually(self):
        with pytest.raises(RuntimeError):
            codes.generate_unique_code(lambda c: True)


class TestIsValidCode:
    def test_accepts_base62(self):
        assert codes.is_valid_code("Abc123z")

    def test_rejects_empty(self):
        assert not codes.is_valid_code("")

    def test_rejects_symbols(self):
        assert not codes.is_valid_code("abc/123")
        assert not codes.is_valid_code("abc 123")

    def test_rejects_too_long(self):
        assert not codes.is_valid_code("a" * (codes.MAX_LENGTH + 1))
