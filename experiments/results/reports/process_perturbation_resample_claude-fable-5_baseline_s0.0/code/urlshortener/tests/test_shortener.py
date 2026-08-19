from unittest.mock import patch

from app.shortener import (
    ALPHABET,
    generate_unique_code,
    is_valid_code,
    is_valid_url,
)


def test_generate_unique_code_default_length(app):
    with app.app_context():
        code = generate_unique_code()
        assert len(code) == 6
        assert all(ch in ALPHABET for ch in code)


def test_generate_unique_code_is_random(app):
    with app.app_context():
        codes = {generate_unique_code() for _ in range(50)}
        # extremely unlikely to collide 50 times out of 62^6 possibilities
        assert len(codes) == 50


def test_generate_unique_code_retries_on_collision(app):
    """Simulate a collision on the first attempt(s) and confirm the
    generator retries instead of returning a duplicate code."""
    with app.app_context():
        from app.models import URL
        from app.extensions import db

        taken = "AAAAAA"
        db.session.add(URL(short_code=taken, long_url="https://example.com"))
        db.session.commit()

        real_choice = __import__("secrets").choice
        calls = {"n": 0}

        def rigged_choice(seq):
            # force the first 6 chars generated to reproduce "AAAAAA"
            if calls["n"] < 6:
                calls["n"] += 1
                return "A"
            return real_choice(seq)

        with patch("app.shortener.secrets.choice", side_effect=rigged_choice):
            code = generate_unique_code()

        assert code != taken


def test_generate_unique_code_grows_length_when_exhausted(app):
    with app.app_context():
        with patch("app.shortener.URL") as mock_url:
            # Pretend every lookup finds an existing collision so the
            # generator is forced to grow the code length.
            mock_url.query.filter_by.return_value.first.return_value = object()
            try:
                generate_unique_code(min_length=1, max_length=1)
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass


def test_is_valid_url():
    assert is_valid_url("https://example.com/path")
    assert is_valid_url("http://example.com")
    assert not is_valid_url("ftp://example.com")
    assert not is_valid_url("not-a-url")
    assert not is_valid_url("")
    assert not is_valid_url(None)
    assert not is_valid_url("javascript:alert(1)")


def test_is_valid_code():
    assert is_valid_code("abc123")
    assert not is_valid_code("")
    assert not is_valid_code(None)
    assert not is_valid_code("has space")
    assert not is_valid_code("bad/slash")
    assert not is_valid_code("x" * 17)
