"""Pytest configuration.

Point the notification server at a throwaway SQLite database and a default
Redis broker before the application module is imported so every test runs
against an isolated persistence layer.
"""

import os
import tempfile

_fd, _db_path = tempfile.mkstemp(prefix="test_messages_", suffix=".db")
os.close(_fd)
os.environ.setdefault("DATABASE_URL", _db_path)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
