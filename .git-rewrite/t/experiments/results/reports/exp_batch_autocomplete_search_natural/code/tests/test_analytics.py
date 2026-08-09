import pytest
from autocomplete.analytics import AnalyticsTracker


class TestAnalyticsTracker:
    def test_track_creates_event(self):
        tracker = AnalyticsTracker()
        event = tracker.track("search_start", {"query": "test"})
        assert event["type"] == "search_start"
        assert event["data"]["query"] == "test"
        assert "timestamp" in event

    def test_get_events_returns_all(self):
        tracker = AnalyticsTracker()
        tracker.track("a", {"n": 1})
        tracker.track("b", {"n": 2})
        events = tracker.get_events()
        assert len(events) == 2
        assert events[0]["type"] == "a"
        assert events[1]["type"] == "b"

    def test_get_events_with_type_filter(self):
        tracker = AnalyticsTracker()
        tracker.track("click", {"x": 1})
        tracker.track("impression", {"y": 2})
        tracker.track("click", {"z": 3})
        clicks = tracker.get_events(event_type="click")
        assert len(clicks) == 2
        assert all(e["type"] == "click" for e in clicks)

    def test_get_events_with_limit(self):
        tracker = AnalyticsTracker()
        for i in range(10):
            tracker.track("event", {"i": i})
        events = tracker.get_events(limit=3)
        assert len(events) == 3

    def test_clear_removes_all(self):
        tracker = AnalyticsTracker()
        tracker.track("a", {})
        tracker.track("b", {})
        tracker.clear()
        assert len(tracker.get_events()) == 0

    def test_count_all(self):
        tracker = AnalyticsTracker()
        tracker.track("a", {})
        tracker.track("b", {})
        assert tracker.count() == 2

    def test_count_by_type(self):
        tracker = AnalyticsTracker()
        tracker.track("click", {})
        tracker.track("click", {})
        tracker.track("impression", {})
        assert tracker.count("click") == 2
        assert tracker.count("impression") == 1

    def test_track_no_data(self):
        tracker = AnalyticsTracker()
        event = tracker.track("ping")
        assert event["data"] == {}
