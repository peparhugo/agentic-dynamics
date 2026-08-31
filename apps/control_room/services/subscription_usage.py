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

    def __init__(self, message: str, *, state: str = "unavailable", age_seconds: int | None = None):
        super().__init__(message)
        self.state = state
        self.age_seconds = age_seconds


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
        # Clock skew must not make a future snapshot appear younger than zero.
        return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))
    except (TypeError, ValueError):
        return None


def _decode_payload(raw: Any) -> tuple[dict[str, Any] | None, int | None]:
    """Decode the v3 cache contract and return its bounded age.

    Cache contents are an external boundary: a malformed or older snapshot must
    be treated as a miss rather than being allowed to fail the API route later.
    """
    try:
        if isinstance(raw, bytes):
            raw = raw.decode()
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except (AttributeError, TypeError, json.JSONDecodeError):
        return None, None
    if not isinstance(payload, dict) or payload.get("schema") != "subscription-usage/v3":
        return None, None
    if not isinstance(payload.get("providers"), dict):
        return None, None
    age = _age_seconds(payload.get("fetched_at"))
    return (payload, age) if age is not None else (None, None)


def _disk_snapshot(root: Path) -> tuple[dict[str, Any], int] | None:
    """Read a structurally valid disk snapshot, including expired snapshots."""
    path = root / "experiments" / "results" / "usage" / "subscription_usage_latest.json"
    try:
        payload, age = _decode_payload(path.read_text())
    except OSError:
        return None
    if payload is None or age is None:
        return None
    return payload, age


def _disk_payload(root: Path) -> dict[str, Any] | None:
    snapshot = _disk_snapshot(root)
    if snapshot is None:
        return None
    payload, age = snapshot
    return payload if age <= FILE_STALE_MAX_SECONDS else None


def _redis_snapshot(redis: Any) -> tuple[bool, tuple[dict[str, Any], int] | None]:
    """Read Redis and report both availability and an optional valid snapshot."""
    try:
        raw = redis.get(CACHE_KEY)
    except Exception:
        return False, None
    if not raw:
        return True, None
    payload, age = _decode_payload(raw)
    snapshot = (payload, age) if payload is not None and age is not None else None
    return True, snapshot


def _cache_can_serve(age: int, *, force: bool) -> bool:
    """Apply the explicit refresh floor before the ordinary cache TTL."""
    if force:
        return age < MIN_REFRESH_INTERVAL_SECONDS
    return age < CACHE_TTL_SECONDS


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

    redis_available, cached_snapshot = (
        _redis_snapshot(redis) if redis is not None else (False, None)
    )
    if cached_snapshot is not None:
        cached_payload, cached_age = cached_snapshot
        if _cache_can_serve(cached_age, force=force):
            return cached_payload, "redis-cache", cached_age

    # When Redis is unavailable, the durable snapshot is itself the cache. This
    # prevents a 60-second dashboard poll from repeatedly calling providers.
    disk_snapshot = _disk_snapshot(root) if not redis_available else None
    if disk_snapshot is not None:
        disk_payload, disk_age = disk_snapshot
        if _cache_can_serve(disk_age, force=force) or (
            not force and disk_age <= FILE_STALE_MAX_SECONDS
        ):
            disk_payload = dict(disk_payload)
            disk_payload["stale"] = True
            return disk_payload, "disk-cache", disk_age

    with _lock:
        redis_available, cached_snapshot = (
            _redis_snapshot(redis) if redis is not None else (False, None)
        )
        if cached_snapshot is not None:
            cached_payload, cached_age = cached_snapshot
            if _cache_can_serve(cached_age, force=force):
                return cached_payload, "redis-cache", cached_age
        try:
            return _fetch_live(redis, root), "live", 0
        except Exception as error:
            # A failed manual refresh must not erase the last usable snapshot.
            if cached_snapshot is not None:
                cached_payload, cached_age = cached_snapshot
                fallback = dict(cached_payload)
                fallback["stale"] = True
                fallback["refresh_error"] = str(error)
                return fallback, "redis-cache", cached_age

    disk = _disk_payload(root)
    if disk is not None:
        disk = dict(disk)
        disk.setdefault("stale", True)
        return disk, "disk-cache", _age_seconds(disk.get("fetched_at"))
    expired = _disk_snapshot(root)
    if expired is not None:
        _, age = expired
        raise UsageUnavailableError(
            "subscription-usage snapshot expired (older than 24 hours)",
            state="expired",
            age_seconds=age,
        )
    raise UsageUnavailableError(
        "no subscription-usage snapshot available (providers + caches all down)"
    )
