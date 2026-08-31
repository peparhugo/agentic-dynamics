"""Subscription-usage cache service for the Control Room (politeness layer).

The provider usage endpoints (``api.anthropic.com/api/oauth/usage``,
``chatgpt.com/backend-api/wham/usage``) are read-only and free, but the dashboard
must not hammer them on a poll loop. This service enforces:

- a Redis TTL cache (``finops:subscription_usage``, 15 min) — dashboard polls hit
  Redis, never the providers;
- a 60 s minimum-refetch floor — even ``?refresh=1`` cannot force more than one
  provider fetch per minute;
- a stampede lock — concurrent misses fetch once, the rest wait;
- a disk fallback — ``experiments/results/usage/subscription_usage_latest.json``
  (written by ``scripts/subscription_usage.py`` and kept in sync on live fetches)
  serves a stale-but-recent snapshot when Redis is down and the fetch fails.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.subscription_usage import append_history, fetch_usage

CACHE_KEY = "finops:subscription_usage"
CACHE_TTL_SECONDS = 15 * 60
MIN_REFRESH_INTERVAL_SECONDS = 60
FILE_STALE_MAX_SECONDS = 24 * 60 * 60

_lock = threading.Lock()


class UsageUnavailableError(RuntimeError):
    """No fresh or recent usage snapshot exists anywhere (providers + caches)."""


def _usage_dir(root: Path) -> Path:
    return root / "experiments" / "results" / "usage"


def history_summary(root: Path) -> dict[str, object]:
    """Summarize the durable usage history ledger (count + time span)."""
    path = _usage_dir(root) / "subscription_usage_history.jsonl"
    count = 0
    first_at = None
    last_at = None
    try:
        with open(path) as fh:
            for line in fh:
                count += 1
                try:
                    fetched = json.loads(line).get("fetched_at")
                except json.JSONDecodeError:
                    continue
                if not fetched:
                    continue
                if first_at is None:
                    first_at = fetched
                last_at = fetched
    except OSError:
        pass
    return {
        "path": str(path),
        "count": count,
        "earliest_fetched_at": first_at,
        "latest_fetched_at": last_at,
    }


def _age_seconds(fetched_at: str | None) -> int | None:
    if not fetched_at:
        return None
    try:
        parsed = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - parsed).total_seconds())
    except ValueError:
        return None


def _disk_payload(root: Path) -> dict[str, Any] | None:
    path = root / "experiments" / "results" / "usage" / "subscription_usage_latest.json"
    try:
        payload = json.loads(path.read_text())
        age = _age_seconds(payload.get("fetched_at"))
        if age is None or age > FILE_STALE_MAX_SECONDS:
            return None
        return payload
    except (OSError, json.JSONDecodeError):
        return None


def _fetch_live(redis: Any, root: Path) -> dict[str, Any]:
    """Fetch from the providers and refresh every cache; raises on failure.

    Every live fetch is appended to the durable history ledger (shared with the
    CLI via ``append_history``) — cache hits never append.
    """
    payload = fetch_usage()
    with contextlib.suppress(Exception):
        redis.setex(CACHE_KEY, CACHE_TTL_SECONDS, json.dumps(payload))
    with contextlib.suppress(Exception):
        usage_dir = _usage_dir(root)
        usage_dir.mkdir(parents=True, exist_ok=True)
        (usage_dir / "subscription_usage_latest.json").write_text(json.dumps(payload, indent=2))
    append_history(payload, _usage_dir(root))
    return payload


def load_or_refresh(
    redis_factory: Callable[[], Any],
    root: Path,
    *,
    force: bool = False,
) -> tuple[dict[str, Any], str, int | None]:
    """Return ``(payload, served_from, age_seconds)`` with the politeness contract.

    ``served_from`` is ``"redis-cache"`` | ``"live"`` | ``"disk-cache"``. A forced
    refresh younger than ``MIN_REFRESH_INTERVAL_SECONDS`` is refused (rate-limited)
    and the cache is served instead.
    """
    redis = None
    try:
        redis = redis_factory()
    except Exception:
        redis = None

    if redis is not None:
        try:
            cached = redis.get(CACHE_KEY)
        except Exception:
            cached = None
        if cached:
            try:
                payload = json.loads(cached)
                age = _age_seconds(payload.get("fetched_at"))
            except (json.JSONDecodeError, AttributeError):
                payload, age = None, None
            if payload and age is not None:
                if age < CACHE_TTL_SECONDS:
                    return payload, "redis-cache", age
                if force and age < MIN_REFRESH_INTERVAL_SECONDS:
                    return payload, "redis-cache", age  # refused refetch — polite floor

    with _lock:
        if redis is not None:
            try:
                cached = redis.get(CACHE_KEY)
            except Exception:
                cached = None
            if cached:
                try:
                    payload = json.loads(cached)
                    age = _age_seconds(payload.get("fetched_at"))
                    if payload and age is not None and age < CACHE_TTL_SECONDS:
                        return payload, "redis-cache", age
                except (json.JSONDecodeError, AttributeError):
                    pass
        try:
            return _fetch_live(redis, root), "live", 0
        except Exception:
            pass

    disk = _disk_payload(root)
    if disk is not None:
        disk = dict(disk)
        disk.setdefault("stale", True)
        return disk, "disk-cache", _age_seconds(disk.get("fetched_at"))
    raise UsageUnavailableError("no subscription-usage snapshot available (providers + caches all down)")
