import pytest

from webcrawler.fetcher import Fetcher, FetchedPage, FetchError, HttpResponse
from webcrawler.robots import RobotsCache


def _allow_all_cache():
    def fetcher(url):
        return 404, None

    return RobotsCache(fetcher, user_agent="testbot", ttl=3600)


def _blocked_cache():
    def fetcher(url):
        return 200, "User-agent: *\nDisallow: /\n"

    return RobotsCache(fetcher, user_agent="testbot", ttl=3600)


def test_fetch_returns_page():
    def http_get(url, headers, timeout):
        return HttpResponse(
            url=url,
            status=200,
            headers={"content-type": "text/html", "etag": '"abc"', "last-modified": "Wed, 01 Jan 2020 00:00:00 GMT"},
            body=b"<html>hi</html>",
        )

    f = Fetcher(_allow_all_cache(), default_delay=0.0, http_get=http_get)
    page = f.fetch("http://x.com/")
    assert page.status == 200
    assert page.content == "<html>hi</html>"
    assert page.etag == '"abc"'
    assert page.last_modified == "Wed, 01 Jan 2020 00:00:00 GMT"
    assert page.is_html


def test_fetch_respects_robots():
    f = Fetcher(_blocked_cache(), default_delay=0.0, http_get=lambda u, h, t: None)
    with pytest.raises(FetchError) as exc:
        f.fetch("http://x.com/private")
    assert exc.value.code == "robots"


def test_fetch_conditional_headers():
    captured = {}

    def http_get(url, headers, timeout):
        captured.update(headers)
        return HttpResponse(url=url, status=200, headers={}, body=b"x")

    f = Fetcher(_allow_all_cache(), default_delay=0.0, http_get=http_get)
    f.fetch("http://x.com/", etag='"abc"', last_modified="Wed, 01 Jan 2020")
    assert captured["If-None-Match"] == '"abc"'
    assert captured["If-Modified-Since"] == "Wed, 01 Jan 2020"
    assert captured["User-Agent"] == "WebCrawler/1.0 (respects robots.txt)"


def test_fetch_304_not_modified():
    def http_get(url, headers, timeout):
        return HttpResponse(url=url, status=304, headers={}, body=b"")

    f = Fetcher(_allow_all_cache(), default_delay=0.0, http_get=http_get)
    page = f.fetch("http://x.com/", etag='"abc"')
    assert page.status == 304
    assert page.from_cache is True
    assert page.content == ""


def test_fetch_retries_server_error():
    attempts = {"n": 0}
    sleeps = []

    def http_get(url, headers, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return HttpResponse(url=url, status=500, headers={}, body=b"")
        return HttpResponse(url=url, status=200, headers={}, body=b"ok")

    f = Fetcher(
        _allow_all_cache(),
        default_delay=0.0,
        http_get=http_get,
        max_retries=3,
        backoff=2.0,
        base_delay=0.1,
        sleep=lambda d: sleeps.append(d),
    )
    page = f.fetch("http://x.com/")
    assert page.status == 200
    assert attempts["n"] == 3
    assert len(sleeps) == 2


def test_fetch_retry_after_on_429():
    attempts = {"n": 0}
    sleeps = []

    def http_get(url, headers, timeout):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return HttpResponse(url=url, status=429, headers={"retry-after": "5"}, body=b"")
        return HttpResponse(url=url, status=200, headers={}, body=b"ok")

    f = Fetcher(
        _allow_all_cache(),
        default_delay=0.0,
        http_get=http_get,
        sleep=lambda d: sleeps.append(d),
    )
    page = f.fetch("http://x.com/")
    assert page.status == 200
    assert 5 in sleeps


def test_fetch_network_error_raises():
    def http_get(url, headers, timeout):
        raise RuntimeError("connection refused")

    f = Fetcher(
        _allow_all_cache(),
        default_delay=0.0,
        http_get=http_get,
        max_retries=2,
        base_delay=0.0,
        sleep=lambda d: None,
    )
    with pytest.raises(FetchError) as exc:
        f.fetch("http://x.com/")
    assert exc.value.code == "network"
