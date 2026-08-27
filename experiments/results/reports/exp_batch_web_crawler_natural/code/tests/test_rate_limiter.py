from webcrawler.rate_limiter import HostPoliteness, TokenBucket


def test_token_bucket_immediate_when_full():
    tb = TokenBucket(rate=1.0, capacity=3.0)
    assert tb.acquire() == 0.0
    assert tb.acquire() == 0.0
    assert tb.acquire() == 0.0
    # exhausted -> must wait roughly 1/rate seconds
    wait = tb.acquire()
    assert wait > 0.5


def test_token_bucket_try_acquire():
    tb = TokenBucket(rate=1.0, capacity=1.0)
    assert tb.try_acquire() is True
    assert tb.try_acquire() is False


def test_token_bucket_requires_positive_rate():
    import pytest

    with pytest.raises(ValueError):
        TokenBucket(rate=0)


def test_host_politeness_default_delay():
    t = [0.0]
    p = HostPoliteness(default_delay=2.0, clock=lambda: t[0])
    assert p.acquire("a.com") == 0.0
    t[0] = 1.0
    assert p.acquire("a.com") == 1.0  # must wait until t=2.0


def test_host_politeness_independent_hosts():
    t = [0.0]
    p = HostPoliteness(default_delay=5.0, clock=lambda: t[0])
    p.acquire("a.com")
    assert p.acquire("b.com") == 0.0  # different host, no delay


def test_host_politeness_delay_provider():
    t = [0.0]
    p = HostPoliteness(
        default_delay=1.0, delay_provider=lambda h: 4.0, clock=lambda: t[0]
    )
    assert p.delay_for("anything") == 4.0
    assert p.acquire("a.com") == 0.0
    t[0] = 2.0
    assert p.acquire("a.com") == 2.0
