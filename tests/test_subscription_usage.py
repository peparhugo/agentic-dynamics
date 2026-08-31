"""Subscription usage normalizer tests — pure functions, no network."""

import json
from datetime import datetime, timezone

from scripts.subscription_usage import (
    _iso,
    aggregate_deepseek,
    append_history,
    fetch_usage,
    normalize_anthropic,
    normalize_openai,
    normalize_platform_amount,
)

RAW_ANTHROPIC = {
    "five_hour": {
        "utilization": 1.0,
        "resets_at": "2026-08-31T18:19:59.898685+00:00",
        "limit_dollars": None,
        "used_dollars": None,
        "locked_reason": None,
    },
    "seven_day": {
        "utilization": 16.0,
        "resets_at": "2026-09-02T13:59:59.898709+00:00",
        "locked_reason": None,
    },
}

RAW_OPENAI = {
    "user_id": "user-7GfVnbUa7tZYUsShgARyCmRc",
    "plan_type": "prolite",
    "rate_limit": {
        "allowed": True,
        "limit_reached": False,
        "primary_window": {
            "used_percent": 0,
            "limit_window_seconds": 604800,
            "reset_after_seconds": 568822,
            "reset_at": 1788751815,
        },
        "secondary_window": None,
    },
    "additional_rate_limits": [
        {
            "limit_name": "GPT-5.3-Codex-Spark",
            "metered_feature": "codex_bengalfox",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 0,
                    "limit_window_seconds": 18000,
                    "reset_after_seconds": 18000,
                    "reset_at": 1788200993,
                },
                "secondary_window": {
                    "used_percent": 0,
                    "limit_window_seconds": 604800,
                    "reset_after_seconds": 604800,
                    "reset_at": 1788787793,
                },
            },
        }
    ],
}


def test_anthropic_normalizer():
    out = normalize_anthropic(RAW_ANTHROPIC)
    names = [w["name"] for w in out["windows"]]
    assert names == ["five_hour", "seven_day"]
    five = out["windows"][0]
    assert five["used_percent"] == 1.0
    assert five["resets_at"] == "2026-08-31T18:19:59.898685+00:00"
    assert out["windows"][1]["used_percent"] == 16.0


def test_anthropic_normalizer_tolerates_missing_plan():
    out = normalize_anthropic(RAW_ANTHROPIC)
    assert out["plan"] is None
    assert out["metered_spend_usd"] is None


def test_openai_normalizer():
    out = normalize_openai(RAW_OPENAI)
    assert out["plan"] == "prolite"
    names = [w["name"] for w in out["windows"]]
    assert names == ["primary", "GPT-5.3-Codex-Spark/primary", "GPT-5.3-Codex-Spark/secondary"]
    assert out["windows"][0]["used_percent"] == 0
    assert out["windows"][0]["limit_seconds"] == 604800
    spark = out["windows"][1]
    assert spark["limit_seconds"] == 18000
    assert spark["resets_at"] == "2026-08-31T18:29:53+00:00"


def test_openai_normalizer_empty_rate_limit():
    out = normalize_openai({"plan_type": "prolite"})
    assert out["windows"] == []


def test_iso():
    assert _iso(1788751815) == "2026-09-07T03:30:15+00:00"
    assert _iso("2026-08-31T18:19:59Z") == "2026-08-31T18:19:59Z"
    assert _iso(None) is None
    assert _iso(0) is None


def test_append_history_appends_jsonl_lines(tmp_path):
    payload = {"schema": "subscription-usage/v1", "fetched_at": _iso(1788751815), "providers": {}}
    append_history(payload, tmp_path)
    append_history(payload, tmp_path)
    path = tmp_path / "subscription_usage_history.jsonl"
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[0]["fetched_at"] == "2026-09-07T03:30:15+00:00"


def test_fetch_usage_shape(monkeypatch, tmp_path):
    import scripts.subscription_usage as su

    monkeypatch.setattr(su, "_anthropic_token", lambda: "tok")
    monkeypatch.setattr(su, "_openai_token", lambda: "tok")
    monkeypatch.setattr(su, "_get_json", lambda url, token: (200, RAW_ANTHROPIC if "anthropic" in url else RAW_OPENAI))
    monkeypatch.setattr(su, "_read_deepseek_rows", lambda: [])
    monkeypatch.setattr(su, "_deepseek_platform_token", lambda: None)
    payload = fetch_usage()
    assert payload["schema"] == "subscription-usage/v3"
    assert payload["providers"]["anthropic"]["ok"] is True
    assert payload["providers"]["openai"]["plan"] == "prolite"
    assert payload["deepseek"]["ok"] is False  # no DB rows in the test
    assert payload["deepseek_platform"]["ok"] is False  # no platform token in the test


RAW_PLATFORM = {
    "start": 1786924800,
    "end": 1788220800,
    "bucket": 86400,
    "models": ["deepseek-v4-pro", "deepseek-v4-flash"],
    "series": [
        {
            "api_key": {"name": "vds", "sensitive_id": "sk-7e3cc****59e0", "valid": True},
            "model": "deepseek-v4-pro",
            "buckets": [
                {"time": 1787011200, "usage": {
                    "RESPONSE_TOKEN": 1_000_000, "REQUEST": 100,
                    "PROMPT_CACHE_HIT_TOKEN": 10_000_000, "PROMPT_CACHE_MISS_TOKEN": 1_000_000}},
            ],
        },
        {
            "api_key": {"name": "vds", "sensitive_id": "sk-7e3cc****59e0", "valid": True},
            "model": "deepseek-v4-flash",
            "buckets": [
                {"time": 1787011200, "usage": {
                    "RESPONSE_TOKEN": 500_000, "REQUEST": 50,
                    "PROMPT_CACHE_HIT_TOKEN": 1_000_000, "PROMPT_CACHE_MISS_TOKEN": 200_000}},
            ],
        },
    ],
}


def test_normalize_platform_amount_day_buckets_and_cost_estimate():
    out = normalize_platform_amount(RAW_PLATFORM)
    assert len(out["days"]) == 1
    day = out["days"][0]
    assert day["date"] == "2026-08-18"
    assert day["requests"] == 150
    assert day["response_tokens"] == 1_500_000
    assert day["cache_hit_tokens"] == 11_000_000
    assert day["cache_miss_tokens"] == 1_200_000
    # pro: 1M miss*0.66 + 1M resp*1.98 + 10M hit*0.022 = 0.66+1.98+0.22 = 2.86
    # flash: 200k miss*0.22 + 500k resp*0.66 + 1M hit*0.007 = 0.044+0.33+0.007 = 0.381
    assert abs(day["estimated_cost_usd"] - (2.86 + 0.381)) < 1e-6
    totals = out["totals"]
    assert abs(totals["estimated_cost_usd"] - (2.86 + 0.381)) < 1e-6
    assert totals["deepseek-v4-pro"]["estimated_cost_usd"] == 2.86


def test_normalize_platform_amount_unknown_model_gets_no_cost():
    raw = {
        "series": [{
            "api_key": {"name": "x", "valid": True},
            "model": "deepseek-unknown-model",
            "buckets": [{"time": 1787011200, "usage": {
                "RESPONSE_TOKEN": 1000, "REQUEST": 1,
                "PROMPT_CACHE_HIT_TOKEN": 0, "PROMPT_CACHE_MISS_TOKEN": 1000}}],
        }],
    }
    out = normalize_platform_amount(raw)
    assert out["days"][0]["estimated_cost_usd"] == 0.0  # no rate -> unknown, never fabricated


def _ms(year, month, day, hour=12):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() * 1000)


def test_aggregate_deepseek_day_buckets_and_subagent_split():
    rows = [
        ("deepseek/deepseek-v4-pro", False, 5.0, 1_000_000, 100_000, _ms(2026, 8, 30)),
        ("deepseek/deepseek-v4-pro", True, 0.5, 100_000, 0, _ms(2026, 8, 30)),
        ("deepseek/deepseek-v4-flash", False, 0.05, 10_000, 5_000, _ms(2026, 8, 31)),
        ("deepseek/deepseek-v4-pro", False, 2.0, 500_000, 0, _ms(2026, 8, 28)),
    ]
    out = aggregate_deepseek(rows)
    assert [d["date"] for d in out["days"]] == ["2026-08-28", "2026-08-30", "2026-08-31"]
    aug30 = out["days"][1]
    assert aug30["cost_usd"] == 5.5
    assert aug30["sessions"] == 2
    assert aug30["subagent_cost_usd"] == 0.5
    assert aug30["subagent_sessions"] == 1
    assert aug30["tokens"] == 1_100_000

    totals = out["totals"]
    assert totals["cost_usd"] == 7.55
    assert totals["sessions"] == 4
    assert totals["subagent_cost_usd"] == 0.5
    assert totals["subagent_sessions"] == 1
    assert totals["cache_read"] == 105_000
    assert totals["models"] == {
        "deepseek/deepseek-v4-flash": 0.05,
        "deepseek/deepseek-v4-pro": 7.5,
    }


def test_aggregate_deepseek_drops_rows_outside_lookback_window():
    old = [("deepseek/deepseek-v4-pro", False, 99.0, 1, 0, _ms(2026, 7, 1))]
    out = aggregate_deepseek(old, days=14)
    assert out["days"] == []
    assert out["totals"]["sessions"] == 0
