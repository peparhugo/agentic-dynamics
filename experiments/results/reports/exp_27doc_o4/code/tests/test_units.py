"""Unit tests for shortcode, storage, and rate limiter."""

import pytest

from shortener.ratelimit import RateLimiter
from shortener.shortcode import ALPHABET, generate_code, is_valid_custom_code
from shortener.storage import CodeCollisionError, SQLiteStorage


class TestShortcode:
    def test_length_and_alphabet(self):
        code = generate_code(8)
        assert len(code) == 8
        assert all(c in ALPHABET for c in code)

    def test_randomness(self):
        codes = {generate_code(6) for _ in range(200)}
        assert len(codes) == 200  # collision here is astronomically unlikely

    @pytest.mark.parametrize("code,ok", [
        ("abcd", True),
        ("my-link_1", True),
        ("abc", False),
        ("a" * 33, False),
        ("bad code", False),
        ("", False),
    ])
    def test_custom_validation(self, code, ok):
        assert is_valid_custom_code(code) is ok


class TestStorage:
    @pytest.fixture()
    def store(self, tmp_path):
        return SQLiteStorage(str(tmp_path / "u.db"))

    def test_save_and_get(self, store):
        store.save("abc123", "https://example.com")
        entry = store.get("abc123")
        assert entry.long_url == "https://example.com"
        assert entry.clicks == 0

    def test_collision_raises(self, store):
        store.save("dup111", "https://a.example")
        with pytest.raises(CodeCollisionError):
            store.save("dup111", "https://b.example")

    def test_click_increment_and_delete(self, store):
        store.save("c1c1c1", "https://example.com")
        store.increment_clicks("c1c1c1")
        store.increment_clicks("c1c1c1")
        assert store.get("c1c1c1").clicks == 2
        assert store.delete("c1c1c1") is True
        assert store.get("c1c1c1") is None
        assert store.delete("c1c1c1") is False

    def test_find_by_url(self, store):
        store.save("first1", "https://example.com/x")
        assert store.find_by_url("https://example.com/x").code == "first1"
        assert store.find_by_url("https://nope.example") is None


class TestRateLimiter:
    def test_sliding_window(self):
        rl = RateLimiter(max_requests=2, window_seconds=10)
        assert rl.allow("k", now=0.0) == (True, 0.0)
        assert rl.allow("k", now=1.0) == (True, 0.0)
        allowed, retry = rl.allow("k", now=2.0)
        assert not allowed
        assert retry == pytest.approx(8.0)
        # Oldest hit (t=0) falls out of the window at t=10.
        assert rl.allow("k", now=10.01)[0] is True

    def test_keys_are_independent(self):
        rl = RateLimiter(max_requests=1, window_seconds=10)
        assert rl.allow("a", now=0.0)[0] is True
        assert rl.allow("a", now=0.1)[0] is False
        assert rl.allow("b", now=0.1)[0] is True

    def test_reset(self):
        rl = RateLimiter(max_requests=1, window_seconds=10)
        rl.allow("a", now=0.0)
        rl.reset("a")
        assert rl.allow("a", now=0.1)[0] is True
