import pytest

from webcrawler.url_utils import (
    canonicalize_url,
    domain_of,
    hostname_of,
    is_http_url,
    normalize_url,
    same_host,
)


def test_lowercases_scheme_and_host():
    assert normalize_url("HTTP://WWW.Example.COM/") == "http://www.example.com/"


def test_removes_default_port():
    assert normalize_url("http://example.com:80/path") == "http://example.com/path"
    assert normalize_url("https://example.com:443/path") == "https://example.com/path"


def test_keeps_non_default_port():
    assert normalize_url("http://example.com:8080/path") == "http://example.com:8080/path"


def test_removes_fragment():
    assert normalize_url("http://example.com/a#section") == "http://example.com/a"


def test_removes_trailing_slash():
    assert normalize_url("http://example.com/a/") == "http://example.com/a"
    assert normalize_url("http://example.com/") == "http://example.com/"


def test_strips_tracking_and_sorts_query():
    url = "http://example.com/search?q=x&utm_source=google&b=2"
    assert normalize_url(url) == "http://example.com/search?b=2&q=x"


def test_collapses_dot_segments():
    assert normalize_url("http://example.com/a/../b") == "http://example.com/b"
    assert normalize_url("http://example.com/a/./b") == "http://example.com/a/b"


def test_normalizes_percent_encoding():
    assert normalize_url("http://example.com/%7euser") == "http://example.com/~user"


def test_collapses_duplicate_slashes():
    assert normalize_url("http://example.com//a//b") == "http://example.com/a/b"


def test_non_http_scheme_untouched():
    assert normalize_url("mailto:user@example.com") == "mailto:user@example.com"


def test_canonicalize_resolves_relative():
    assert canonicalize_url("/about", "http://example.com/dir/") == "http://example.com/about"


def test_is_http_url():
    assert is_http_url("http://x.com")
    assert is_http_url("https://x.com")
    assert not is_http_url("ftp://x.com")
    assert not is_http_url("mailto:a@b.com")


def test_host_helpers():
    assert hostname_of("http://WWW.Example.COM/x") == "www.example.com"
    assert domain_of("http://example.com:8080/x") == "example.com:8080"
    assert same_host("http://example.com/a", "http://example.com:80/b")
    assert not same_host("http://example.com/a", "http://other.com/a")
