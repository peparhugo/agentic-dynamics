"""Environment-driven configuration for the Redis backbone and SQLite store."""
from __future__ import annotations

import os

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_DATABASE_URL = "notifications.db"
DEFAULT_TRANSPORT = "websocket"


def redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def transport_name() -> str:
    """Which `BaseTransport` implementation to use, selected via the
    TRANSPORT env var (e.g. "websocket", "sse", "polling"). Defaults to
    "websocket"."""
    return os.environ.get("TRANSPORT", DEFAULT_TRANSPORT)


def database_path() -> str:
    """Resolve DATABASE_URL to a plain SQLite file path.

    Accepts either a bare path or a `sqlite:///...` URL so the same env var
    convention used by other SQLite-backed services works here too.
    """
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url
