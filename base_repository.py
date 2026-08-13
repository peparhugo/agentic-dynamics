"""
Abstract base repository for the flat-file (JSON) data access layer.

Concrete repositories (TaskRepository, UserRepository) extend this class to
get shared read/write/locking machinery, and implement the domain-specific
CRUD methods (create, get, ...) required by the abstract interface. Route
handlers depend only on repository methods, never on file I/O directly.
"""

import json
import os
import threading
from abc import ABC, abstractmethod


class BaseRepository(ABC):
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict:
        with open(self.path, "r") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)

    def _ensure_initialized(self, default_data: dict) -> None:
        if not os.path.exists(self.path):
            self._write(default_data)

    @abstractmethod
    def create(self, *args, **kwargs) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get(self, *args, **kwargs):
        raise NotImplementedError
