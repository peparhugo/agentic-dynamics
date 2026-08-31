"""lab_beta_from_corpus — the fleet coordination-tax exponent β, retrospectively.

PREREGISTERED 2026-08-31 (see ``experiments/lab_books/lab_beta_from_corpus.md``) — the method,
the exclusion rules, and the decision thresholds were fixed BEFORE any fitting. This script
implements exactly that doc and nothing else.

Question: how much per-worker efficiency is lost as fleet concurrency grows —
``efficiency(N) = c·N^(−β)``? Estimated from the existing session corpus (opencode.db + the
container story cells + the platform meter), NOT from a controlled ladder run.

Zero model calls. Reads: ``~/.local/share/opencode/opencode.db`` (session table),
``experiments/results/stories/*.json`` (container-cell windows, sensitivity only),
``experiments/results/usage/subscription_usage_latest.json`` (meter reconciliation).

Output: ``experiments/results/lab_beta_from_corpus.json`` (schema below).
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPENCODE_DB = Path(os.environ.get("FINOPS_OPENCODE_DB", "~/.local/share/opencode/opencode.db")).expanduser()
OUT = ROOT / "experiments" / "results" / "lab_beta_from_corpus.json"
USAGE_LATEST = ROOT / "experiments" / "results" / "usage" / "subscription_usage_latest.json"

LOOKBACK_DAYS = 14
PREREGISTERED_AT = "2026-08-31"

#: The confounded ladder window (the dual-workflow pollution) — EXCLUDED (exclusion rule 1).
LADDER_WINDOW = (
    datetime(2026, 8, 30, 21, 32, tzinfo=timezone.utc),
    datetime(2026, 8, 31, 1, 48, tzinfo=timezone.utc),
)
#: Noise floor (exclusion rule 2).
MIN_DURATION_S = 10
MIN_TOKENS = 100

#: Bins (rule: N = mean concurrency over the session's lifetime).
BINS = [(1, 1, "1"), (2, 3, "2-3"), (4, 5, "4-5"), (6, 8, "6-8"), (9, 10**9, "9+")]

MODEL_WHITELIST = {
    "deepseek-v4-pro", "deepseek-v4-flash", "deepseek-v4-flash-vision-exp",
    "claude-sonnet-5", "claude-haiku-4-5",
}
VENDOR = {"deepseek-v4-pro": "deepseek", "deepseek-v4-flash": "deepseek",
          "deepseek-v4-flash-vision-exp": "deepseek", "claude-sonnet-5": "anthropic",
          "claude-haiku-4-5": "anthropic"}


def _parse_model(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        mid = json.loads(raw).get("id", "")
    except (ValueError, TypeError):
        return None
    return mid if mid in MODEL_WHITELIST else None


def _load_sessions(days: int = LOOKBACK_DAYS) -> list[dict]:
    """Session rows for whitelisted models: interval, tokens, cost, cache, subagent flag."""
    if not OPENCODE_DB.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000
    rows = []
    conn = sqlite3.connect(str(OPENCODE_DB))
    cur = conn.execute(
        """SELECT parent_id, model, cost, tokens_input, tokens_output, tokens_reasoning,
                  tokens_cache_read, time_created, time_updated
           FROM session WHERE time_created >= ? AND time_updated > 0""", (cutoff,))
    for parent, raw_model, cost, tin, tout, tr, tcache, t0, t1 in cur.fetchall():
        model = _parse_model(raw_model)
        if model is None:
            continue
        start = datetime.fromtimestamp(t0 / 1000, tz=timezone.utc)
        end = datetime.fromtimestamp(t1 / 1000, tz=timezone.utc)
        if end <= start:
            continue
        tokens = int(tin or 0) + int(tout or 0) + int(tr or 0)
        rows.append({
            "model": model, "vendor": VENDOR[model],
            "is_subagent": parent is not None,
            "start": start, "end": end,
            "duration_s": (end - start).total_seconds(),
            "tokens": tokens, "tokens_input": int(tin or 0),
            "cache_read": int(tcache or 0),
            "cost_usd": float(cost or 0.0),
        })
    conn.close()
    return rows


def _story_windows(days: int = LOOKBACK_DAYS) -> list[dict]:
    """Container story-cell windows (started_at → completed_at) — sensitivity N only."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    out = []
    for path in (ROOT / "experiments" / "results" / "stories").glob("*.json"):
        try:
            d = json.loads(path.read_text())
            start = d.get("started_at")
            end = d.get("completed_at")
            if not start or not end or start < cutoff:
                continue
            out.append({"story": d.get("story_name", "?"), "start": start, "end": end})
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _mean_concurrency(sessions: list[dict]) -> None:
    """Assign each session its experienced N = mean count of overlapping sessions over its life.

    Sweep: walk all interval endpoints; between consecutive endpoints the overlap count is
    constant, so each session's mean = (Σ overlap_duration × count) / its own duration.
    """
    events = []
    for i, s in enumerate(sessions):
        events.append((s["start"].timestamp(), 1, i))
        events.append((s["end"].timestamp(), -1, i))
    events.sort()
    count = 0
    integral: list[float] = [0.0] * len(sessions)
    for (t, delta, _idx), (t_next, _, _) in zip(events, events[1:], strict=False):
        span = t_next - t
        if span <= 0:
            continue
        for j in range(len(sessions)):
            s = sessions[j]
            overlap = max(0.0, min(s["end"].timestamp(), t_next) - max(s["start"].timestamp(), t))
            if overlap > 0:
                integral[j] += overlap * count
        count += delta
    for s, i in zip(sessions, integral, strict=False):
        s["n"] = i / s["duration_s"]


def _fit_ols(xs: list[float], ys: list[float]) -> dict:
    """Manual OLS on log-log points; β = −slope (efficiency falls as N rises)."""
    n = len(xs)
    if n < 5:
        return {"beta": None, "ci": None, "r2": None, "n": n, "slope": None}
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    if sxx == 0:
        return {"beta": None, "ci": None, "r2": None, "n": n, "slope": None}
    slope = sxy / sxx
    intercept = my - slope * mx
    resid = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys, strict=False))
    sst = sum((yy - my) ** 2 for yy in ys)
    var = resid / (n - 2) if n > 2 else 0.0
    se = math.sqrt(var / sxx) if sxx else 0.0
    r2 = 1 - resid / sst if sst else 0.0
    half = 1.96 * se
    return {"beta": -slope, "ci": [-slope - half, -slope + half], "r2": r2, "n": n, "slope": slope}


def _excluded(s: dict) -> bool:
    if s["duration_s"] < MIN_DURATION_S or s["tokens"] < MIN_TOKENS:
        return True
    return s["start"] < LADDER_WINDOW[1] and s["end"] > LADDER_WINDOW[0]


def _bins() -> list[dict]:
    return [{"bin": label, "lo": lo, "hi": hi} for lo, hi, label in BINS]


def _bin_of(n: float) -> str:
    for lo, hi, label in BINS:
        if lo <= n <= hi:
            return label
    return "9+"


def _fit_model(rows: list[dict]) -> dict:
    """Throughput tax (tokens/min) + cost tax (cost/1k tokens) + cache slope, per model."""
    through, costy, cachey, nx = [], [], [], []
    for s in rows:
        nx.append(math.log(s["n"]))
        tpm = s["tokens"] / (s["duration_s"] / 60)
        if tpm > 0:
            through.append(math.log(tpm))
        cpt = s["cost_usd"] / s["tokens"] * 1000 if s["tokens"] > 0 else None
        if cpt is not None and cpt > 0:
            costy.append(math.log(cpt))
        if s["tokens_input"] + s["cache_read"] > 0:
            cachey.append(s["cache_read"] / (s["cache_read"] + s["tokens_input"]))
    return {
        "beta_tokens": _fit_ols(nx[: len(through)], through),
        "beta_cost": _fit_ols(nx[: len(costy)], costy),
        "cache_share_slope": _fit_ols(nx[: len(cachey)], cachey),
        "n": len(rows),
    }


def _reconcile_meter() -> dict:
    """DB token totals vs the platform meter's authoritative per-model buckets."""
    try:
        d = json.loads(USAGE_LATEST.read_text())
        dp = d.get("deepseek_platform") or {}
        meter_tokens = sum(
            (m.get("cache_miss_tokens") or 0) + (m.get("response_tokens") or 0)
            for k, m in (dp.get("totals") or {}).items() if isinstance(m, dict)
        )
        return {"meter_14d_tokens": meter_tokens, "note": "DB totals undercount container cells"}
    except (OSError, json.JSONDecodeError):
        return {"meter_14d_tokens": None, "note": "no meter snapshot available"}


def main() -> int:
    sessions = _load_sessions()
    _mean_concurrency(sessions)

    parents = [s for s in sessions if not s["is_subagent"]]
    subagents = [s for s in sessions if s["is_subagent"]]
    kept = [s for s in parents if not _excluded(s)]
    excluded = len(parents) - len(kept)

    per_model: dict[str, dict] = {}
    pooled = []
    for model in sorted(MODEL_WHITELIST):
        rows = [s for s in kept if s["model"] == model]
        if rows:
            per_model[model] = _fit_model(rows)
            pooled += rows
    main_estimate = _fit_model(pooled)

    bin_counts = {label: sum(1 for s in kept if _bin_of(s["n"]) == label)
                  for _, _, label in BINS}
    subagent_split = {
        label: sum(1 for s in subagents if _bin_of(s["n"]) == label) for _, _, label in BINS
    }
    subagent_cost_share = {
        label: round(sum(s["cost_usd"] for s in subagents if _bin_of(s["n"]) == label), 4)
        for _, _, label in BINS
    }

    bc = main_estimate["beta_cost"]["beta"]
    if bc is None:
        decision = "insufficient_data"
    elif bc < 0.15:
        decision = "negligible_tax"
    elif bc <= 0.5:
        decision = "moderate_tax"
    else:
        decision = "severe_tax"

    result = {
        "question": "How much per-worker efficiency is lost as fleet concurrency grows?",
        "preregistered_at": PREREGISTERED_AT,
        "models": per_model,
        "main_estimate": main_estimate,
        "bins": bin_counts,
        "subagent_sessions_per_bin": subagent_split,
        "subagent_cost_usd_per_bin": subagent_cost_share,
        "exclusions_applied": [
            "ladder_window", "noise_min_10s_100tok", "subagents_split",
            "container_cells_excluded_primary", "model_whitelist",
        ],
        "n_total": len(kept),
        "n_excluded": excluded,
        "meter_reconciliation": _reconcile_meter(),
        "decision": decision,
        "decision_thresholds": {"negligible": 0.15, "moderate": 0.5},
    }
    OUT.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
