import time
import threading


class AnalyticsTracker:
    def __init__(self):
        self._events = []
        self._lock = threading.Lock()

    def track(self, event_type, data=None):
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "data": data or {},
        }
        with self._lock:
            self._events.append(event)
        return event

    def get_events(self, limit=None, event_type=None):
        with self._lock:
            events = list(self._events)
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        if limit and limit > 0:
            events = events[-limit:]
        return events

    def clear(self):
        with self._lock:
            self._events.clear()

    def count(self, event_type=None):
        if event_type:
            return len([e for e in self._events if e["type"] == event_type])
        return len(self._events)
