from webcrawler.scheduler import RecrawlScheduler


def _clock(start=0.0):
    state = {"t": start}
    return lambda: state["t"], state


def test_next_interval_growth_and_shrink():
    s = RecrawlScheduler(min_interval=10, max_interval=100, growth=2.0, shrink=0.5)
    assert s.next_interval(10, changed=False) == 20
    assert s.next_interval(20, changed=False) == 40
    assert s.next_interval(40, changed=True) == 20
    assert s.next_interval(100, changed=False) == 100  # capped
    assert s.next_interval(10, changed=True) == 10  # floored


def test_record_updates_state():
    clock, state = _clock()
    s = RecrawlScheduler(min_interval=10, max_interval=100, clock=clock)
    s.schedule("http://x.com/", initial_interval=10)
    assert s.record("http://x.com/", changed=False) == 20
    assert s.record("http://x.com/", changed=True) == 10


def test_due_uses_clock():
    clock, state = _clock()
    s = RecrawlScheduler(min_interval=10, clock=clock)
    s.schedule("http://x.com/", initial_interval=10)
    assert s.due(now=5) == []
    assert len(s.due(now=10)) == 1
    assert len(s.due(now=11)) == 1


def test_next_due_time():
    clock, state = _clock()
    s = RecrawlScheduler(min_interval=10, clock=clock)
    s.schedule("http://a.com/", initial_interval=10)
    s.schedule("http://b.com/", initial_interval=30)
    assert s.next_due_time(now=0) == 10
    assert s.next_due_time(now=20) == 30
