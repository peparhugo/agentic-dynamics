from webcrawler.legal import CrawlPolicy
from webcrawler.parser import parse_html
from webcrawler.robots import RobotsCache


def _robots_cache(text="User-agent: *\nDisallow: /private/\n"):
    def fetcher(url):
        return 200, text

    return RobotsCache(fetcher, user_agent="testbot", ttl=3600)


def test_can_crawl_robots():
    policy = CrawlPolicy(_robots_cache())
    assert policy.can_crawl("http://ok.com/public")
    assert not policy.can_crawl("http://ok.com/private/x")


def test_can_crawl_opt_out():
    policy = CrawlPolicy(_robots_cache(), opt_out_hosts=["badsite.com"])
    assert not policy.can_crawl("http://badsite.com/anything")
    assert policy.is_opted_out("badsite.com")


def test_opt_out_case_insensitive():
    policy = CrawlPolicy(_robots_cache(), opt_out_hosts=["BadSite.COM"])
    assert policy.is_opted_out("badsite.com")


def test_may_index_noindex():
    policy = CrawlPolicy(_robots_cache())
    page = parse_html('<html><head><meta name="robots" content="noindex"></head></html>')
    assert not policy.may_index(page)
    page2 = parse_html("<html><body>ok</body></html>")
    assert policy.may_index(page2)


def test_may_follow_nofollow():
    policy = CrawlPolicy(_robots_cache())
    page = parse_html('<html><head><meta name="robots" content="nofollow"></head></html>')
    assert not policy.may_follow(page)
