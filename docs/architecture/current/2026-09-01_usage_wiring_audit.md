---
status: accepted
---

# Control Room Usage Wiring Audit

**Date:** 2026-09-01
**Scope:** subscription-usage/v3 producer, polite cache, API route, Control Room
UI, live endpoint, and tests
**Change policy:** audit only. No implementation files were changed in this phase.

## Result

**LOG: PASS — audit completed; gap_count=10.**

The repository contains an end-to-end implementation path. The provider fetcher emits
the expected Anthropic, OpenAI, DeepSeek local, and DeepSeek platform blocks; the
service applies a Redis-backed cache and disk fallback; the route is registered; and
the portal has a usage panel with a refresh control. The audit found ten gaps or
hardening items before the completion phase.

**LIVE_CHECK: FAIL — the requested running portal payload could not be observed.**
The default `127.0.0.1:8000` listener is not the Control Room: it returned a 404 with
`chroma-trace-id`. Loopback port 8001 was closed. The running Flask Control Room was
reachable at `100.83.229.3:8001`, where `/` returned the portal shell but both
`/api/subscription-usage` and `/api/subscription-usage?refresh=1` returned Flask 404.
Its process is `/home/drseuss/ai-finops-framework/apps/control_room/server.py`, with
working directory `/home/drseuss/ai-finops-framework`, rather than this worktree.
Consequently, no live provider values, cache age, response headers, or live rendered
usage state can be claimed from this checkout.

## Chain Audit

| Stage | Evidence | Assessment |
|---|---|---|
| Provider producer | `scripts/subscription_usage.py:36`, `:100-155`, `:318-490`, `:493-523` | Emits `subscription-usage/v3`; normalizes Anthropic `five_hour`/`seven_day` windows and resets, OpenAI subscription windows, local DeepSeek cash, and DeepSeek platform wallet/meter data. Provider failures are represented as `ok: false` blocks. |
| Polite cache | `apps/control_room/services/subscription_usage.py:29-32`, `:96-172` | Redis TTL is 900 seconds, the intended refetch floor is 60 seconds, and disk fallback accepts snapshots up to 24 hours old. The implementation has a forced-refresh ordering defect and validation edge cases listed below. |
| API route | `apps/control_room/routes/telemetry.py:177-205`, `:266-276` | `GET /api/subscription-usage` is registered and returns provider blocks, DeepSeek blocks, fetched time, stale/source flags, history, and cache age/limits. It omits the producer `schema` field and does not set HTTP cache headers. |
| Portal panel | `apps/control_room/static/index.html:716-730`, `apps/control_room/static/app.js:1867-1957` | The shell exposes the panel and Refresh button. The client renders provider tables, local per-token cash, platform wallet/lifetime/14-day estimate, cache age, stale state, and source. It is source-verified, not live-browser-verified because the running server returned 404. |
| Refresh/polling | `apps/control_room/static/app.js:2699-2700`, `:2950-2967` | Manual refresh calls `?refresh=1`; startup loads usage and a 60-second poll calls the non-forced endpoint. There is no in-flight guard or disabled/loading state for overlapping calls. |
| Tests | `tests/test_subscription_usage.py`, `tests/test_subscription_usage_api.py`, `tests/test_admin_frontend.py` | Focused run passed 29 tests. Backend tests cover normalization, cache hit/miss, disk fallback, forced refresh, and 503; frontend tests do not exercise usage rendering or refresh behavior. |

## Gap Table

| Surface | Present | Gap |
|---|---|---|
| 1. Producer/schema contract | The producer constant is `subscription-usage/v3` and the latest persisted snapshot is v3 (`scripts/subscription_usage.py:36`, `:517-523`). | The module docstring still documents v1 (`:12-14`); dedicated fixtures still use v1/v2; and the API response drops `payload["schema"]` (`routes/telemetry.py:190-205`). This makes deployed/schema drift harder to detect. |
| 2. Anthropic 5h/7d windows | `normalize_anthropic()` emits both windows, utilization, reset time, and `locked_reason`; the UI renders utilization and reset time (`subscription_usage.py:100-116`, `app.js:1890-1906`). | `locked_reason` is not rendered. Empty windows produce a table with no explicit no-data state, and a locked/quota-blocked condition is not visually distinguished from an ordinary window. |
| 3. OpenAI Prolite windows | `normalize_openai()` preserves the plan, primary/secondary/additional windows, utilization, duration, reset time, and `allowed` (`subscription_usage.py:119-155`); the UI renders the windows and resets. | `allowed` is not rendered. An empty or disallowed window has no explicit state beyond a blank table or unavailable provider block. |
| 4. DeepSeek per-token cash | The local `deepseek` block has 14-day totals, daily cash, sessions, tokens, subagent split, and model totals; the UI labels it as local opencode.db cash (`subscription_usage.py:250-315`, `app.js:1908-1929`). | This is a local estimate and explicitly undercounts container-worker activity. If there are no rows, the UI shows an unavailable message, but if rows exist with an empty day list it renders an empty table without a no-data explanation. |
| 5. DeepSeek platform balance and spend | `deepseek_platform` has wallet balance, lifetime cost, daily meter totals, and 14-day estimated cost (`subscription_usage.py:441-490`); the UI displays Wallet, lifetime, 14d estimate, and an authoritative meter table (`app.js:1931-1953`). | The values are distinct in text but not prominent at a glance: wallet balance, lifetime spend, and 14-day estimate are one inline sentence rather than separately labeled metrics. The UI does not expose a separate explicit platform-spend card or reconcile local cash against platform spend. |
| 6. Cache TTL, floor, fallback | The service declares a 15-minute Redis TTL, 60-second floor, process lock, and recent disk fallback (`services/subscription_usage.py:7-14`, `:29-32`, `:148-172`). | The fresh-cache return at `:143-144` occurs before the forced-refresh floor branch at `:145-146`, so `refresh=1` cannot refetch an otherwise fresh snapshot even when it is older than 60 seconds. Cached payloads are not schema-validated; future timestamps can appear fresh; and Redis outages can cause repeated provider attempts before disk fallback. |
| 7. Cache age and HTTP cache semantics | The API returns `cache.age_seconds`, TTL, and minimum refresh interval (`routes/telemetry.py:199-204`); the UI visibly renders age, source, stale/fresh, fetched time, and TTL (`app.js:1884-1889`). | No usage-specific `Cache-Control`, `Age`, `ETag`, or equivalent response headers are set. The requested cache-age visibility exists in JSON/UI but is not independently represented in HTTP metadata. |
| 8. Error, empty, and expired states | Provider errors and total service failure are not silent: the client renders an unavailable message, and the route returns 503 when no snapshot exists (`app.js:1892-1894`, `:1910-1911`, `:1933-1934`, `:1955-1957`; route `:185-188`). | Provider errors use generic `.empty-state` rather than `.error-state`; empty arrays render blank tables; expired disk data has no distinct expired state; and a refresh failure replaces previously good content instead of retaining it with an error notice. |
| 9. Refresh interaction and concurrency | The button is wired to `loadSubscriptionUsage(true)`, which calls `/api/subscription-usage?refresh=1`; polling is scheduled every 60 seconds (`app.js:2699-2700`, `:2960-2967`). | The Refresh button is not disabled and no request-in-flight guard exists. Startup, polling, and manual refresh can overlap and render responses out of order. There is also no success/failure announcement through the existing live-region helpers. |
| 10. Verification and deployment parity | The repository tests pass and the served static shell contains the usage panel and usage client code. | There are no frontend behavioral tests for usage rendering, refresh, stale/expired/error states, or empty windows. The running Control Room is from another checkout and returns 404 for the route, so the live API and UI end-to-end contract is not currently verified from this worktree. |

## Live Verification Record

The following read-only requests were made without starting or restarting a service:

| Request | Observed result |
|---|---|
| `GET http://127.0.0.1:8000/api/subscription-usage` | 404; response carried `chroma-trace-id`, indicating this was not the Flask Control Room route. |
| `GET http://127.0.0.1:8001/api/subscription-usage` | Connection refused on loopback. |
| `GET http://100.83.229.3:8001/` | 200 Flask portal shell. |
| `GET http://100.83.229.3:8001/api/subscription-usage` | 404 Flask response. |
| `GET http://100.83.229.3:8001/api/subscription-usage?refresh=1` | 404 Flask response. |
| `GET http://100.83.229.3:8001/static/app.js` | 200; served client contains `loadSubscriptionUsage`, the cache-age line, platform wallet/estimate labels, and the refresh URL. |

Because the API returned 404, the live check could not inspect Anthropic reset
timestamps, OpenAI windows, DeepSeek wallet/meter/spend values, cache age, or actual
browser rendering. The implementation evidence above is therefore explicitly
repository/static evidence, not a substitute for a successful live check.

## Test Record

Command:

```text
python3 -m pytest -q tests/test_subscription_usage.py tests/test_subscription_usage_api.py tests/test_admin_frontend.py
```

Result: **29 passed** in 0.60 seconds. The environment emitted a warning that the
`timeout` pytest configuration option was unknown, indicating the timeout plugin is
not installed in that interpreter; this did not affect the focused test result.

## Completion Handoff

The implementation phase should address only the ten gap rows above, preserve the
existing read-only provider query and cache boundary, and add tests for the behavior
that cannot currently be proven by the test suite. After implementation, restart or
point the portal at this worktree and repeat both normal and `refresh=1` live requests
on the configured `FINOPS_PORT`, then verify the rendered panel in a browser.
