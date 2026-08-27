from webcrawler.frontier import Frontier


def _clock_factory(start=0.0):
    state = {"t": start}

    def clock():
        return state["t"]

    clock.state = state
    return clock


def test_frontier_basic_dequeue():
    f = Frontier(default_delay=0.0)
    assert f.add("http://a.com/1")
    assert f.add("http://a.com/2")
    assert f.next() == "http://a.com/1"
    f.complete("a.com")
    assert f.next() == "http://a.com/2"


def test_frontier_rejects_duplicate_url():
    f = Frontier()
    assert f.add("http://a.com/1")
    assert not f.add("http://a.com/1")
    assert not f.add("http://a.com:80/1")  # same canonical URL


def test_frontier_priority_within_host():
    f = Frontier(default_delay=0.0)
    f.add("http://a.com/low", priority=0.0)
    f.add("http://a.com/high", priority=10.0)
    assert f.next() == "http://a.com/high"
    f.complete("a.com")
    assert f.next() == "http://a.com/low"


def test_frontier_politeness_one_in_flight_per_host():
    clock = _clock_factory()
    f = Frontier(default_delay=2.0, clock=clock)
    f.add("http://a.com/1")
    f.add("http://a.com/2")
    f.add("http://b.com/1")

    assert f.next() == "http://a.com/1"
    assert f.next() == "http://b.com/1"  # different host proceeds
    assert f.next() is None  # both hosts in flight

    clock.state["t"] = 2.0
    f.complete("a.com")  # ready again at t=4.0
    f.complete("b.com")  # b has no more urls
    assert f.next() is None

    clock.state["t"] = 4.0
    assert f.next() == "http://a.com/2"


def test_frontier_complete_release():
    clock = _clock_factory()
    f = Frontier(default_delay=1.0, clock=clock)
    f.add("http://a.com/1")
    f.add("http://a.com/2")
    assert f.next() == "http://a.com/1"
    assert f.next() is None  # a.com in flight
    f.complete("a.com")  # ready at t=1.0
    assert f.next() is None  # not yet (t=0)
    clock.state["t"] = 1.0
    assert f.next() == "http://a.com/2"


def test_frontier_requeue_bypasses_seen():
    f = Frontier(default_delay=0.0)
    f.add("http://a.com/1")
    assert f.next() == "http://a.com/1"
    f.complete("a.com")
    # normal add would reject it as a duplicate
    assert not f.add("http://a.com/1")
    # requeue bypasses the seen filter (used for recrawls)
    assert f.requeue("http://a.com/1")
    assert f.next() == "http://a.com/1"


def test_frontier_pending_and_empty():
    f = Frontier(default_delay=0.0)
    assert not f
    f.add("http://a.com/1")
    assert f
    assert f.pending() == 1
    f.next()
    assert f.pending() == 0
