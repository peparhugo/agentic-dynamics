"""Subscription usage check — hit the providers' OAuth usage endpoints directly.

Two read-only, quota-free endpoints (no model calls, no spend):

- Anthropic (Claude Code plan): ``https://api.anthropic.com/api/oauth/usage``
  with the OAuth token from ``~/.claude/.credentials.json`` (the same token
  Claude Code's ``/usage`` uses; refreshed in-memory if expired).
- OpenAI (ChatGPT/Codex plan): ``https://chatgpt.com/backend-api/wham/usage``
  with the ChatGPT OAuth token from ``~/.local/share/opencode/auth.json``
  (type=oauth; refreshed in-memory if expired).

Output: ``experiments/results/usage/subscription_usage_latest.json`` (schema
``subscription-usage/v1``) + an append-only history line in
``experiments/results/usage/subscription_usage_history.jsonl``.

Secrets never leave this process: tokens are read from disk or minted via the
refresh flow in memory and are never written to the output files.

Usage:
    python scripts/subscription_usage.py            # fetch + persist + pretty print
    python scripts/subscription_usage.py --json     # compact machine output
    python scripts/subscription_usage.py --no-write # check only, persist nothing
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = "subscription-usage/v3"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "usage"
DEEPSEEK_LOOKBACK_DAYS = 14

CLAUDE_CREDS_PATH = Path(os.environ.get("FINOPS_CLAUDE_CREDS_PATH", "~/.claude/.credentials.json")).expanduser()
OPENCODE_AUTH_PATH = Path(os.environ.get("FINOPS_OPENCODE_AUTH_PATH", "~/.local/share/opencode/auth.json")).expanduser()
OPENCODE_DB_PATH = Path(os.environ.get("FINOPS_OPENCODE_DB", "~/.local/share/opencode/opencode.db")).expanduser()
DEEPSEEK_PLATFORM_TOKEN_PATH = Path(
    os.environ.get("FINOPS_DEEPSEEK_PLATFORM_TOKEN_PATH", "~/.config/opencode/deepseek_platform.token")
).expanduser()

ANTHROPIC_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
ANTHROPIC_TOKEN_URL = "https://api.anthropic.com/api/oauth/token"
OPENAI_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
DEEPSEEK_SUMMARY_URL = "https://platform.deepseek.com/api/v0/users/get_user_summary"
DEEPSEEK_USAGE_URL = "https://platform.deepseek.com/api/v0/usage/by_api_key/amount"
DEEPSEEK_TZ_OFFSET_SECONDS = -21600

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


def _get_json(url: str, token: str, headers: dict | None = None) -> tuple[int | None, object]:
    h = {
        "Authorization": f"Bearer {token}",
        "User-Agent": _UA,
        "Accept": "*/*",
        "Content-Type": "application/json",
    }
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:  # network/timeout/parse
        return None, str(e)


def _post_form(url: str, data: dict[str, str]) -> str | None:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "opencode/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()).get("access_token")
    except Exception:
        return None


def _iso(epoch_s: object) -> str | None:
    if isinstance(epoch_s, (int, float)) and epoch_s:
        return datetime.fromtimestamp(float(epoch_s), tz=timezone.utc).isoformat()
    if isinstance(epoch_s, str) and epoch_s:
        return epoch_s
    return None


def normalize_anthropic(raw: dict) -> dict:
    """Map the Anthropic oauth/usage response to the canonical window shape."""
    windows = []
    for name in ("five_hour", "seven_day"):
        w = raw.get(name)
        if isinstance(w, dict):
            windows.append({
                "name": name,
                "used_percent": w.get("utilization"),
                "resets_at": _iso(w.get("resets_at")),
                "locked_reason": w.get("locked_reason"),
            })
    return {
        "plan": (raw.get("plan") or {}).get("name") if isinstance(raw.get("plan"), dict) else None,
        "windows": windows,
        "metered_spend_usd": None,
    }


def normalize_openai(raw: dict) -> dict:
    """Map the chatgpt /backend-api/wham/usage response to the canonical shape."""
    windows = []
    rl = raw.get("rate_limit") or {}
    if isinstance(rl.get("primary_window"), dict):
        windows.append({
            "name": "primary",
            "used_percent": rl["primary_window"].get("used_percent"),
            "limit_seconds": rl["primary_window"].get("limit_window_seconds"),
            "resets_at": _iso(rl["primary_window"].get("reset_at")),
            "allowed": rl.get("allowed"),
        })
    if isinstance(rl.get("secondary_window"), dict):
        windows.append({
            "name": "secondary",
            "used_percent": rl["secondary_window"].get("used_percent"),
            "limit_seconds": rl["secondary_window"].get("limit_window_seconds"),
            "resets_at": _iso(rl["secondary_window"].get("reset_at")),
            "allowed": rl.get("allowed"),
        })
    for arl in raw.get("additional_rate_limits") or []:
        name = arl.get("limit_name") or arl.get("metered_feature")
        inner = (arl.get("rate_limit") or {})
        for slot in ("primary_window", "secondary_window"):
            if isinstance(inner.get(slot), dict):
                windows.append({
                    "name": f"{name}/{slot.removesuffix('_window')}",
                    "used_percent": inner[slot].get("used_percent"),
                    "limit_seconds": inner[slot].get("limit_window_seconds"),
                    "resets_at": _iso(inner[slot].get("reset_at")),
                    "allowed": inner.get("allowed"),
                })
    return {
        "plan": raw.get("plan_type"),
        "windows": windows,
        "metered_spend_usd": None,
    }


def _anthropic_token() -> str | None:
    try:
        creds = json.loads(CLAUDE_CREDS_PATH.read_text())["claudeAiOauth"]
    except Exception:
        return None
    token = creds.get("accessToken")
    exp = creds.get("expiresAt") or 0
    if isinstance(exp, (int, float)) and exp and datetime.now(timezone.utc).timestamp() > exp - 60:
        token = _post_form(ANTHROPIC_TOKEN_URL, {
            "grant_type": "refresh_token",
            "refresh_token": creds.get("refreshToken", ""),
            "client_id": "claude.ai",
        }) or token
    return token


def _openai_token() -> str | None:
    try:
        auth = json.loads(OPENCODE_AUTH_PATH.read_text()).get("openai") or {}
    except Exception:
        return None
    token = auth.get("access")
    exp = auth.get("expires") or 0
    if isinstance(exp, (int, float)) and exp and datetime.now(timezone.utc).timestamp() > exp - 60:
        token = _post_form(OPENAI_TOKEN_URL, {
            "grant_type": "refresh_token",
            "refresh_token": auth.get("refresh", ""),
            "client_id": "pdlLIX2Y72MIl2rhLhTE9VV9bN2kBsTe",
        }) or token
    return token


# ── DeepSeek (per-token cash) side of the ledger ────────────────────────────

#: Row tuple from the opencode DB: (model_id, is_subagent, cost, tokens,
#: cache_read, time_created_ms). Parsed out of the session table so the
#: aggregation stays pure (testable without a live DB).
DeepseekRow = tuple[str, bool, float, int, int, int]


def _read_deepseek_rows(days: int = DEEPSEEK_LOOKBACK_DAYS) -> list[DeepseekRow]:
    """Read DeepSeek session rows from the local opencode DB (incl. subagents).

    Cost here is opencode's own estimate from its pricing table — a local
    reconciliation surface, NOT the platform meter. Container-run cells (fleet
    story workers) live in the container's own opencode DB and are invisible to
    this store: the totals undercount real spend by exactly that gap.
    """
    import sqlite3

    if not OPENCODE_DB_PATH.exists():
        return []
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    rows = []
    try:
        conn = sqlite3.connect(str(OPENCODE_DB_PATH))
        cur = conn.execute(
            """
            SELECT model, parent_id, cost,
                   tokens_input, tokens_output, tokens_reasoning, tokens_cache_read,
                   time_created
            FROM session
            WHERE model LIKE '%"providerID":"deepseek"%' AND time_created >= ?
            """,
            (cutoff,),
        )
        for model, parent_id, cost, tin, tout, treason, tcache, created in cur.fetchall():
            model_id = model or "deepseek/unknown"
            try:
                parsed = json.loads(model)
                model_id = f"deepseek/{parsed.get('id', 'unknown')}"
            except (ValueError, TypeError):
                pass
            tokens = int(tin or 0) + int(tout or 0) + int(treason or 0)
            rows.append((
                model_id,
                parent_id is not None,
                float(cost or 0.0),
                tokens,
                int(tcache or 0),
                int(created or 0),
            ))
        conn.close()
    except Exception:
        return []
    return rows


def _utc_date(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def aggregate_deepseek(rows: list[DeepseekRow], days: int = DEEPSEEK_LOOKBACK_DAYS) -> dict:
    """Aggregate opencode DeepSeek rows into day buckets + totals (pure).

    Buckets are calendar-day UTC, oldest first, within the lookback window;
    subagent sessions (``parent_id`` set) are split out per bucket and in the
    totals so the cash attribution is auditable.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    by_day: dict[str, dict] = {}
    model_totals: dict[str, dict] = {}
    totals = {
        "cost_usd": 0.0, "sessions": 0, "subagent_cost_usd": 0.0,
        "subagent_sessions": 0, "tokens": 0, "cache_read": 0,
    }
    for model_id, is_subagent, cost, tokens, cache_read, created in rows:
        date = _utc_date(created)
        if date < cutoff:
            continue
        day = by_day.setdefault(date, {
            "date": date, "cost_usd": 0.0, "sessions": 0,
            "subagent_cost_usd": 0.0, "subagent_sessions": 0, "tokens": 0,
        })
        mtot = model_totals.setdefault(model_id, {"cost_usd": 0.0, "sessions": 0})
        day["cost_usd"] += cost
        day["sessions"] += 1
        day["tokens"] += tokens
        mtot["cost_usd"] += cost
        mtot["sessions"] += 1
        totals["cost_usd"] += cost
        totals["sessions"] += 1
        totals["tokens"] += tokens
        totals["cache_read"] += cache_read
        if is_subagent:
            day["subagent_cost_usd"] += cost
            day["subagent_sessions"] += 1
            totals["subagent_cost_usd"] += cost
            totals["subagent_sessions"] += 1

    totals["models"] = {m: round(v["cost_usd"], 6) for m, v in sorted(model_totals.items())}
    totals["cost_usd"] = round(totals["cost_usd"], 6)
    totals["subagent_cost_usd"] = round(totals["subagent_cost_usd"], 6)
    return {
        "days": [by_day[d] for d in sorted(by_day)],
        "totals": totals,
    }


def deepseek_usage() -> dict:
    """The per-token cash block for the ledger (never fatal — DB may be absent)."""
    rows = _read_deepseek_rows()
    if not rows:
        return {
            "ok": False,
            "source": "opencode_db",
            "path": str(OPENCODE_DB_PATH),
            "error": "no deepseek sessions in the local opencode DB (or DB absent)",
        }
    result = aggregate_deepseek(rows)
    result.update({
        "ok": True,
        "source": "opencode_db",
        "path": str(OPENCODE_DB_PATH),
        "note": "local opencode.db estimates — container-run cells (fleet story workers) "
                "are invisible to this DB and undercount the platform meter",
    })
    return result


# ── DeepSeek platform meter (the authoritative token/cost record) ───────────

_METER_RATE_ALIASES = {
    "deepseek-v4-flash-vision-exp": "deepseek-v4-flash",
    "deepseek-chat & deepseek-reasoner": "deepseek-v4-pro",
}


def _meter_rates(model: str) -> dict | None:
    """Repo pricing rates (per 1M tokens, off-peak) for a meter model name.

    Whitelist-only: an unknown meter model gets NO rate, so its dollar estimate
    stays absent (``0.0`` is never fabricated for an unpriceable model).
    """
    try:
        from agentic_dynamics.measurement.efficiency import get_pricing
    except Exception:
        return None
    name = _METER_RATE_ALIASES.get(model, model)
    if name not in ("deepseek-v4-pro", "deepseek-v4-flash"):
        return None
    try:
        return get_pricing("deepseek", name)
    except ValueError:
        return None


def _deepseek_platform_token() -> str | None:
    token = os.environ.get("FINOPS_DEEPSEEK_PLATFORM_TOKEN")
    if token:
        return token
    try:
        return DEEPSEEK_PLATFORM_TOKEN_PATH.read_text().strip() or None
    except OSError:
        return None


def _platform_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": _UA,
        "Accept": "*/*",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-platform": "web",
        "x-client-version": "1.0.0",
        "Referer": "https://platform.deepseek.com/usage",
    }


def _platform_biz(body: object) -> dict | None:
    """Unwrap the platform envelope (``code``/``data.biz_data``)."""
    if not isinstance(body, dict) or body.get("code") != 0:
        return None
    data = body.get("data")
    if not isinstance(data, dict) or data.get("biz_code") != 0:
        return None
    biz = data.get("biz_data")
    return biz if isinstance(biz, dict) else None


def normalize_platform_amount(raw: dict) -> dict:
    """Aggregate the meter's per-(key, model) daily token buckets into days.

    Pure: ``raw`` is the parsed ``biz_data`` from the platform's
    ``/usage/by_api_key/amount`` response. Dollars are ESTIMATED from the
    repo's DeepSeek pricing table (off-peak) applied to the meter's own token
    counts — cache reads dominate and are priced at the cache rate.
    """
    by_day: dict[str, dict] = {}
    model_totals: dict[str, dict] = {}
    totals = {
        "requests": 0, "response_tokens": 0,
        "cache_hit_tokens": 0, "cache_miss_tokens": 0, "estimated_cost_usd": 0.0,
    }
    for series in raw.get("series") or []:
        model = series.get("model") or "?"
        rates = _meter_rates(model)
        model_total = {
            "requests": 0, "response_tokens": 0,
            "cache_hit_tokens": 0, "cache_miss_tokens": 0, "estimated_cost_usd": 0.0,
        }
        for bucket in series.get("buckets") or []:
            usage = bucket.get("usage") or {}
            miss = int(usage.get("PROMPT_CACHE_MISS_TOKEN") or 0)
            hit = int(usage.get("PROMPT_CACHE_HIT_TOKEN") or 0)
            resp = int(usage.get("RESPONSE_TOKEN") or 0)
            req = int(usage.get("REQUEST") or 0)
            day = by_day.setdefault(bucket.get("time"), {
                "date": _utc_date(int(bucket.get("time") or 0) * 1000),  # meter: epoch seconds
                "requests": 0, "response_tokens": 0,
                "cache_hit_tokens": 0, "cache_miss_tokens": 0, "estimated_cost_usd": 0.0,
            })
            cost = 0.0
            if rates:
                cost = (miss * rates["input"] + resp * rates["output"] + hit * rates["cache_read"]) / 1_000_000
            day["requests"] += req
            day["response_tokens"] += resp
            day["cache_hit_tokens"] += hit
            day["cache_miss_tokens"] += miss
            day["estimated_cost_usd"] += cost
            model_total["requests"] += req
            model_total["response_tokens"] += resp
            model_total["cache_hit_tokens"] += hit
            model_total["cache_miss_tokens"] += miss
            model_total["estimated_cost_usd"] += cost
        for key in ("requests", "response_tokens", "cache_hit_tokens", "cache_miss_tokens"):
            totals[key] += model_total[key]
        totals["estimated_cost_usd"] += model_total["estimated_cost_usd"]
        acc = model_totals.setdefault(model, {k: 0 for k in model_total})
        for key, value in model_total.items():
            acc[key] += value

    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"], 6)
    model_totals = {
        m: {k: (round(v, 4) if k.endswith("_usd") else v) for k, v in acc.items()}
        for m, acc in model_totals.items()
    }
    return {
        "days": [by_day[t] for t in sorted(by_day)],
        "totals": {"estimated_cost_usd": totals["estimated_cost_usd"], **model_totals},
    }


def deepseek_platform_usage() -> dict:
    """The authoritative platform-meter block (tokens per day + estimated $).

    Token counts are the meter's own (ground truth for reconciliation against
    the local opencode.db block); dollar estimates apply the repo's off-peak
    pricing, and the wallet line carries the platform's REAL dollar balances.
    """
    token = _deepseek_platform_token()
    if not token:
        return {
            "ok": False,
            "source": "platform_meter",
            "error": "no platform token (set FINOPS_DEEPSEEK_PLATFORM_TOKEN or write "
                     f"{DEEPSEEK_PLATFORM_TOKEN_PATH})",
        }
    headers = _platform_headers(token)

    status, body = _get_json(DEEPSEEK_SUMMARY_URL, token, headers)
    wallet = {}
    if status == 200 and isinstance(body, dict):
        biz = _platform_biz(body)
        if biz:
            wallets = biz.get("normal_wallets") or []
            costs = biz.get("total_costs") or []
            if wallets:
                wallet["balance_usd"] = float(wallets[0].get("balance") or 0.0)
            if costs:
                wallet["lifetime_cost_usd"] = float(costs[0].get("amount") or 0.0)

    now = int(datetime.now(timezone.utc).timestamp())
    start = (now // 86400 - DEEPSEEK_LOOKBACK_DAYS) * 86400
    end = (now // 86400 + 1) * 86400
    url = f"{DEEPSEEK_USAGE_URL}?start={start}&end={end}&tz={DEEPSEEK_TZ_OFFSET_SECONDS}"
    status, body = _get_json(url, token, headers)
    biz = _platform_biz(body) if status == 200 and isinstance(body, dict) else None
    if biz is None:
        return {
            "ok": False,
            "source": "platform_meter",
            "error": f"usage endpoint failed: http {status}: {str(body)[:200]}",
            "wallet": wallet,
        }
    result = normalize_platform_amount(biz)
    result.update({
        "ok": True,
        "source": "platform_meter",
        "wallet": wallet,
        "note": "authoritative meter token counts; dollars estimated at repo off-peak rates",
    })
    return result


def fetch_usage() -> dict:
    """Fetch both providers; a provider that fails is reported, never fatal."""
    providers: dict[str, object] = {}

    tok = _anthropic_token()
    if tok:
        status, body = _get_json(ANTHROPIC_USAGE_URL, tok)
        if status == 200 and isinstance(body, dict):
            providers["anthropic"] = {"ok": True, **normalize_anthropic(body)}
        else:
            providers["anthropic"] = {"ok": False, "error": f"http {status}: {str(body)[:200]}"}
    else:
        providers["anthropic"] = {"ok": False, "error": "no claude credentials found"}

    tok = _openai_token()
    if tok:
        status, body = _get_json(OPENAI_USAGE_URL, tok)
        if status == 200 and isinstance(body, dict):
            providers["openai"] = {"ok": True, **normalize_openai(body)}
        else:
            providers["openai"] = {"ok": False, "error": f"http {status}: {str(body)[:200]}"}
    else:
        providers["openai"] = {"ok": False, "error": "no openai oauth credentials found"}

    return {
        "schema": SCHEMA,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "providers": providers,
        "deepseek": deepseek_usage(),
        "deepseek_platform": deepseek_platform_usage(),
    }


def append_history(payload: dict, root: Path | None = None) -> None:
    """Append one snapshot line to the durable usage history ledger (JSONL).

    One line per live provider fetch — cache hits never append. Both the CLI and
    the Control Room service call this, so the history is one canonical stream
    under ``experiments/results/usage/subscription_usage_history.jsonl``.
    """
    results_dir = root if root is not None else RESULTS_DIR
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        with open(results_dir / "subscription_usage_history.jsonl", "a") as fh:
            fh.write(json.dumps(payload) + "\n")
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Query subscription usage endpoints (read-only, free).")
    parser.add_argument("--json", action="store_true", help="compact machine output")
    parser.add_argument("--no-write", action="store_true", help="check only, persist nothing")
    args = parser.parse_args()

    result = fetch_usage()
    if not args.no_write:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "subscription_usage_latest.json").write_text(json.dumps(result, indent=2))
        append_history(result)

    ok = all(p.get("ok") for p in result["providers"].values())
    print(json.dumps(result) if args.json else json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
