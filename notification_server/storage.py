"""Flat-file (JSON Lines) event storage. No databases — every event is appended
as one JSON object per line to a plain text file on disk."""

import json
import threading
from pathlib import Path


class FlatFileStorage:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append_event(self, event: dict) -> None:
        line = json.dumps(event)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def read_events(self) -> list:
        with self._lock:
            if not self.path.exists():
                return []
            with open(self.path, "r", encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
