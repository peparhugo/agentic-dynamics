from webcrawler.robots import RobotsCache, RobotsTxt


def test_disallow_private():
    r = RobotsTxt("User-agent: *\nDisallow: /private/\n")
    assert not r.is_allowed("http://x.com/private/secret", "*")
    assert r.is_allowed("http://x.com/public/", "*")


def test_allow_overrides_disallow_longest_match():
    r = RobotsTxt(
        "User-agent: *\nDisallow: /private/\nAllow: /private/public/\n"
    )
    assert r.is_allowed("http://x.com/private/public/page", "*")
    assert not r.is_allowed("http://x.com/private/secret", "*")


def test_wildcard_and_anchor():
    r = RobotsTxt("User-agent: *\nDisallow: /download/*.pdf$\n")
    assert not r.is_allowed("http://x.com/download/file.pdf", "*")
    assert r.is_allowed("http://x.com/download/file.pdf.zip", "*")
    assert r.is_allowed("http://x.com/other/file.pdf", "*")


def test_user_agent_grouping():
    r = RobotsTxt(
        "User-agent: Googlebot\nDisallow: /nogoogle/\n"
        "User-agent: *\nDisallow: /private/\n"
    )
    assert not r.is_allowed("http://x.com/nogoogle/a", "Googlebot")
    assert r.is_allowed("http://x.com/nogoogle/a", "Bingbot")
    assert not r.is_allowed("http://x.com/private/a", "Bingbot")


def test_ua_substring_match():
    r = RobotsTxt("User-agent: Googlebot\nDisallow: /x/\n")
    ua = "Mozilla/5.0 (compatible; Googlebot/2.1)"
    assert not r.is_allowed("http://x.com/x/y", ua)


def test_crawl_delay():
    r = RobotsTxt("User-agent: *\nCrawl-delay: 2.5\n")
    assert r.crawl_delay("*") == 2.5


def test_sitemap_extraction():
    r = RobotsTxt("User-agent: *\nDisallow:\nSitemap: http://x.com/sitemap.xml\n")
    assert "http://x.com/sitemap.xml" in r.sitemaps


def test_comments_and_blank_lines_ignored():
    r = RobotsTxt("# comment\n\nUser-agent: *\nDisallow: /a\n")
    assert not r.is_allowed("http://x.com/a")


def _make_cache(text, status=200):
    def fetcher(url):
        return status, text

    return RobotsCache(fetcher, user_agent="*", ttl=3600)


def test_cache_allows_when_no_robots():
    cache = _make_cache(None, status=404)
    assert cache.is_allowed("http://x.com/anything")


def test_cache_disallow_on_server_error():
    cache = _make_cache(None, status=500)
    assert not cache.is_allowed("http://x.com/anything")


def test_cache_respects_robots():
    cache = _make_cache("User-agent: *\nDisallow: /private/\n")
    assert not cache.is_allowed("http://x.com/private/a")
    assert cache.is_allowed("http://x.com/public/a")


def test_cache_is_cached():
    calls = []

    def fetcher(url):
        calls.append(url)
        return 200, "User-agent: *\nDisallow: /\n"

    cache = RobotsCache(fetcher, user_agent="*", ttl=3600)
    cache.is_allowed("http://x.com/a")
    cache.is_allowed("http://x.com/b")
    assert len(calls) == 1
