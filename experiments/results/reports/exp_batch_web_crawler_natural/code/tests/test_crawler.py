from webcrawler.crawler import Crawler
from webcrawler.fetcher import Fetcher, HttpResponse
from webcrawler.robots import RobotsCache


def _allow_all_cache():
    def fetcher(url):
        return 404, None

    return RobotsCache(fetcher, user_agent="testbot", ttl=3600)


def _make_crawler(pages, recrawl=False, **fetcher_kwargs):
    def http_get(url, headers, timeout):
        body = pages.get(url)
        if body is None:
            return HttpResponse(url=url, status=404, headers={}, body=b"")
        return HttpResponse(
            url=url, status=200, headers={"content-type": "text/html"}, body=body.encode()
        )

    fetcher = Fetcher(
        _allow_all_cache(), default_delay=0.0, http_get=http_get, **fetcher_kwargs
    )
    return Crawler(fetcher, recrawl=recrawl, sleep=lambda d: None)


def test_crawl_indexes_linked_pages():
    pages = {
        "http://site.com/": '<html><body><a href="/a">a</a><a href="/b">b</a></body></html>',
        "http://site.com/a": "<html><body>page a</body></html>",
        "http://site.com/b": "<html><body>page b</body></html>",
    }
    crawler = _make_crawler(pages)
    stats = crawler.crawl(["http://site.com/"], max_pages=3)
    assert stats.pages_crawled == 3
    assert stats.pages_indexed == 3
    assert len(crawler.documents) == 3
    assert "http://site.com/a" in crawler.documents


def test_crawl_dedup_identical_content():
    pages = {
        "http://site.com/": '<html><body><a href="/dup1">1</a><a href="/dup2">2</a></body></html>',
        "http://site.com/dup1": "<html><body>same content</body></html>",
        "http://site.com/dup2": "<html><body>same content</body></html>",
    }
    crawler = _make_crawler(pages)
    stats = crawler.crawl(["http://site.com/"], max_pages=3)
    assert stats.pages_crawled == 3
    assert stats.pages_indexed == 2  # one duplicate
    assert stats.duplicates == 1


def test_crawl_respects_robots_blocking():
    def http_get(url, headers, timeout):
        return HttpResponse(url=url, status=200, headers={"content-type": "text/html"}, body=b"<html>x</html>")

    def robots_fetcher(url):
        return 200, "User-agent: *\nDisallow: /blocked/\n"

    cache = RobotsCache(robots_fetcher, user_agent="testbot", ttl=3600)
    fetcher = Fetcher(cache, default_delay=0.0, http_get=http_get)
    crawler = Crawler(fetcher, recrawl=False, sleep=lambda d: None)
    stats = crawler.crawl(["http://site.com/blocked/page"], max_pages=1)
    assert stats.blocked_by_robots == 1
    assert stats.pages_crawled == 1
    assert stats.pages_indexed == 0


def test_crawl_handles_errors():
    def http_get(url, headers, timeout):
        raise RuntimeError("boom")

    fetcher = Fetcher(
        _allow_all_cache(),
        default_delay=0.0,
        http_get=http_get,
        max_retries=1,
        base_delay=0.0,
        sleep=lambda d: None,
    )
    crawler = Crawler(fetcher, recrawl=False, sleep=lambda d: None)
    stats = crawler.crawl(["http://site.com/"], max_pages=1)
    assert stats.errors == 1
    assert stats.pages_indexed == 0


class _FakeClock:
    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        return self.t


def test_crawl_recrawls_changed_pages():
    clock = _FakeClock()

    # Page "changes" from v1 to v2 after t >= 5.0.
    def http_get(url, headers, timeout):
        body = "v1-content" if clock.t < 5.0 else "v2-content"
        return HttpResponse(
            url=url, status=200, headers={"content-type": "text/html"}, body=body.encode()
        )

    fetcher = Fetcher(_allow_all_cache(), default_delay=0.0, http_get=http_get)
    crawler = Crawler(
        fetcher,
        recrawl=True,
        sleep=lambda d: clock.__setattr__("t", clock.t + d),
        clock=clock,
    )
    # scheduler defaults: min_interval=300s -> too slow for a test, so use
    # a short interval via a custom scheduler.
    from webcrawler.scheduler import RecrawlScheduler

    crawler.scheduler = RecrawlScheduler(min_interval=1.0, max_interval=10.0, clock=clock)

    stats = crawler.crawl(["http://site.com/"], max_pages=4)
    assert stats.pages_crawled == 4
    assert stats.recrawls == 3
    assert stats.duplicates == 2
    assert stats.pages_indexed == 2  # v1 once, v2 once
