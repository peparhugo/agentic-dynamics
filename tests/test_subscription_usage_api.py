"""Control Room subscription-usage route tests — cache politeness, no network.

The provider endpoints must never be hammered by dashboard polls: a 15-minute
Redis TTL serves cached data, and even ``?refresh=1`` is refused within the
60-second min-refetch floor.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from apps.control_room import server  # noqa: F401  # side effect: sys.path setup
from apps.control_room.routes import telemetry as telemetry_routes
from apps.control_room.services import subscription_usage as usage_service


class FakeRedisUsage:
    """Minimal get/setex dict store — enough for the politeness contract."""

    def __init__(self, seed=None):
        self.values = dict(seed or {})

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, _ttl, value):
        self.values[key] = value


class StubServices:
    def __init__(self, redis, root):
        self._redis = redis
        self.root = root

    def redis(self):
        return self._redis


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _payload(fetched_at=None):
    return {
        "schema": "subscription-usage/v2",
        "fetched_at": fetched_at or _now_iso(),
        "providers": {
            "anthropic": {
                "ok": True,
                "plan": None,
                "windows": [{"name": "five_hour", "used_percent": 1.0,
                             "resets_at": "2026-08-31T18:20:00+00:00", "locked_reason": None}],
                "metered_spend_usd": None,
            },
            "openai": {
                "ok": True,
                "plan": "prolite",
                "windows": [{"name": "primary", "used_percent": 0, "limit_seconds": 604800,
                             "resets_at": "2026-09-07T03:30:15+00:00", "allowed": True}],
                "metered_spend_usd": None,
            },
        },
        "deepseek": {
            "ok": True,
            "source": "opencode_db",
            "path": "/home/drseuss/.local/share/opencode/opencode.db",
            "note": "local estimates",
            "days": [{"date": "2026-08-30", "cost_usd": 11.76, "sessions": 37,
                      "subagent_cost_usd": 0.0, "subagent_sessions": 0, "tokens": 17_040_579}],
            "totals": {"cost_usd": 14.32, "sessions": 50, "subagent_cost_usd": 0.0,
                       "subagent_sessions": 0, "tokens": 21_348_846, "cache_read": 0,
                       "models": {"deepseek/deepseek-v4-flash": 2.78,
                                  "deepseek/deepseek-v4-pro": 14.32}},
        },
        "deepseek_platform": {
            "ok": True,
            "source": "platform_meter",
            "wallet": {"balance_usd": 98.94, "lifetime_cost_usd": 321.06},
            "note": "authoritative meter token counts",
            "days": [{"date": "2026-08-30", "requests": 19545, "response_tokens": 16_474_401,
                      "cache_hit_tokens": 3_434_211_712, "cache_miss_tokens": 83_145_093,
                      "estimated_cost_usd": 21.66}],
            "totals": {"estimated_cost_usd": 207.0,
                       "deepseek-v4-pro": {"estimated_cost_usd": 163.0}},
        },
    }


def _client(monkeypatch, redis, root, fetch=None):
    monkeypatch.setattr(telemetry_routes, "_services", StubServices(redis, root))
    monkeypatch.setattr(usage_service, "fetch_usage", fetch if fetch is not None else lambda: _payload())
    return server.app.test_client()


def test_cache_hit_serves_without_fetching(monkeypatch, tmp_path):
    redis = FakeRedisUsage({usage_service.CACHE_KEY: json.dumps(_payload())})
    calls = []

    def boom():
        calls.append("fetch")
        raise AssertionError("cache hit must not fetch")

    client = _client(monkeypatch, redis, tmp_path, fetch=boom)
    response = client.get("/api/subscription-usage")

    assert response.status_code == 200
    body = response.get_json()
    assert body["served_from"] == "redis-cache"
    assert body["refetched_now"] is False
    assert body["stale"] is False
    assert body["providers"]["openai"]["plan"] == "prolite"
    assert body["deepseek"]["totals"]["cost_usd"] == 14.32
    assert body["deepseek_platform"]["wallet"]["balance_usd"] == 98.94
    assert calls == []
    # cache hits never append to the durable history
    assert body["history"]["count"] == 0


def test_miss_fetches_once_and_caches(monkeypatch, tmp_path):
    redis = FakeRedisUsage()
    calls = []

    def fetch():
        calls.append("fetch")
        return _payload()

    client = _client(monkeypatch, redis, tmp_path, fetch=fetch)
    first = client.get("/api/subscription-usage")
    second = client.get("/api/subscription-usage")

    assert first.get_json()["served_from"] == "live"
    assert second.get_json()["served_from"] == "redis-cache"
    assert calls == ["fetch"]
    assert usage_service.CACHE_KEY in redis.values
    # the live fetch is durable: exactly one history line, surfaced via the route
    history = first.get_json()["history"]
    assert history["count"] == 1
    assert history["earliest_fetched_at"] == history["latest_fetched_at"]
    assert (tmp_path / "experiments/results/usage/subscription_usage_history.jsonl").exists()


def test_forced_refresh_refused_within_minute_floor(monkeypatch, tmp_path):
    redis = FakeRedisUsage({usage_service.CACHE_KEY: json.dumps(_payload())})
    calls = []

    def boom():
        calls.append("fetch")
        raise AssertionError("fresh cache must refuse a forced refetch")

    client = _client(monkeypatch, redis, tmp_path, fetch=boom)
    response = client.get("/api/subscription-usage?refresh=1")

    assert response.status_code == 200
    body = response.get_json()
    assert body["served_from"] == "redis-cache"
    assert body["refetched_now"] is False
    assert calls == []


def test_forced_refresh_fetches_when_stale(monkeypatch, tmp_path):
    stale_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    redis = FakeRedisUsage({usage_service.CACHE_KEY: json.dumps(_payload(stale_at))})
    calls = []

    def fetch():
        calls.append("fetch")
        return _payload()

    client = _client(monkeypatch, redis, tmp_path, fetch=fetch)
    response = client.get("/api/subscription-usage?refresh=1")

    assert response.status_code == 200
    assert response.get_json()["served_from"] == "live"
    assert calls == ["fetch"]


def test_fetch_failure_serves_recent_disk_cache(monkeypatch, tmp_path):
    disk = tmp_path / "experiments" / "results" / "usage"
    disk.mkdir(parents=True)
    (disk / "subscription_usage_latest.json").write_text(json.dumps(_payload()))

    def boom():
        raise RuntimeError("providers down")

    client = _client(monkeypatch, FakeRedisUsage(), tmp_path, fetch=boom)
    response = client.get("/api/subscription-usage")

    assert response.status_code == 200
    body = response.get_json()
    assert body["served_from"] == "disk-cache"
    assert body["stale"] is True


def test_total_failure_returns_503(monkeypatch, tmp_path):
    def boom():
        raise RuntimeError("providers down")

    client = _client(monkeypatch, FakeRedisUsage(), tmp_path, fetch=boom)
    response = client.get("/api/subscription-usage")

    assert response.status_code == 503
    assert response.get_json()["error"] == "subscription_usage_unavailable"
