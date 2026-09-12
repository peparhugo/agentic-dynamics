---
status: accepted
---
# Control Room refresh feature parity — a1 audit

**Status:** audit complete; the parity test is RED by design (7 failed / 11 passed) — that
failure list *is* the gap this work order exists to close.
**Work order:** `workflows/repository/control_room_refresh_rework.yaml`, phase `a1_parity_audit`.
**Merge parents:** main side `1457b9299` (the merge's second parent) · refresh side `b16891b3a`
(the first parent) · merge `0244f3315` · current tree `c9a788cbd`.
**Pinned by:** `tests/test_control_room_feature_parity.py` (browser-free; reads the static
modules as text and asserts the anchors below).
**Rework target (a2):** port every "missing / degraded" row into the refreshed presentation —
`parity.js` is the natural host — **without weakening the test and without reverting the
refresh's design language.**

## 1. What the merge did (the gap's shape)

`0244f3315` resolved `apps/control_room/static/index.html` + `app.js` to the **refresh side
wholesale**: the refreshed shell loads only `app.js` (the one-resting-screen glance client),
`charts.js`, `visuals.js`, and `parity.js`. Main's monolithic `app.js` (4109 lines: Operations,
Surfaces, Routing, Registry, Subscription usage, the keyed-list consumer) is gone from the tree.

`server.py` + `routes/` kept main's **routes**, so every endpoint survives
(`/api/operations`, `/api/runs/<id>`, `/api/quality`, `/api/value`, `/api/arms/compare`,
`/api/queue/sla`, `/api/escalations`, `/api/batch`, `/api/energy`, `/api/stories/<name>/arc`,
`/api/routing`, `/api/registry`, `/api/registry/<entity_id>`, `/api/subscription-usage`).
`parity.js` re-houses **some** of main's read views as workbench lenses, but three renderers were
never ported (routing, registry filters/lineage, subscription usage — each now a generic
`renderKV`/`panel-table` dump) and two cross-cutting behaviours were dropped (A7 per-panel error
rendering, the shared keyed-list reconciler, per-board refresh wiring).

## 2. Method

```
git show 1457b9299:apps/control_room/static/app.js        # main read views (4109 lines)
git show b16891b3a:apps/control_room/static/parity.js     # refresh parity module (1313 lines)
git show HEAD:apps/control_room/static/parity.js          # merged/current parity.js (1836 lines)
git ls-tree -r --name-only <ref> -- apps/control_room/    # surface inventory per parent
grep -n "<anchor>" apps/control_room/static/*.js *.html   # presence check per anchor
python -m pytest tests/test_control_room_feature_parity.py -q
```

The test's helper set: `REFRESH_MODULES = (app.js, charts.js, visuals.js, parity.js)` (exactly
what the refreshed `index.html` loads); DOM/wiring anchors are read from `index.html` too.

## 3. Recorded failing list (the proof of the gap)

Captured from one run on the current tree:

```
7 failed, 11 passed in 0.12s
FAILED test_surface_failure_renders_the_named_reason_and_its_url
FAILED test_routing_board_renders_structured_recommendations
FAILED test_registry_board_keeps_its_filters_and_lineage_view
FAILED test_registry_table_pins_its_canonical_columns
FAILED test_subscription_usage_board_renders_providers_and_the_meter
FAILED test_polled_lists_use_the_shared_keyed_list_reconciler
FAILED test_read_boards_keep_their_refresh_affordances
```

| Failing test | Missing main anchors (verbatim from the assertion) |
|---|---|
| `test_surface_failure_renders_the_named_reason_and_its_url` | `function renderSurfaceError`, `renderSurfaceError(` |
| `test_routing_board_renders_structured_recommendations` | `function routingTable`, `Per-task routing`, `Per-task model routing recommendations`, `Best correctness`, `Best efficiency`, `best_correctness_model`, `best_efficiency_model`, `Strategy simulation`, `Routing strategy simulation`, `Avg correctness`, `No routing data yet` |
| `test_registry_board_keeps_its_filters_and_lineage_view` | `function renderRegistryTable`, `function loadRegistryLineage`, `record_type`, `registry-filter-type`, `registry-filter-lifecycle`, `registry-filter-since`, `registry-lineage` |
| `test_registry_table_pins_its_canonical_columns` | `knowledge_id`, `Canonical-state registry entries` |
| `test_subscription_usage_board_renders_providers_and_the_meter` | `function loadSubscriptionUsage`, `function usageUsd`, `function usageMetrics`, `function usageEmpty`, `function usageError`, `subscription-usage?refresh=1`, `served_from`, `refresh_error`, `showing the last snapshot`, `Window`, `Resets (UTC)`, `deepseek_platform` |
| `test_polled_lists_use_the_shared_keyed_list_reconciler` | no loaded script is `keyed-list.js` and no refreshed module references `ControlRoomKeyedList` |
| `test_read_boards_keep_their_refresh_affordances` | `operations-refresh`, `surfaces-refresh`, `routing-refresh`, `registry-refresh`, `usage-refresh` |

The 11 passing tests are the **controls** (the refresh itself and the features that did survive):
the workbench re-houses both read lenses; Operations helpers/sections/labels/click-through; the
A7 degraded-DB semantics; the run-detail named error; the degraded lists on quality/SLA/batch;
all Surfaces routes + panels; the step-12 batch lane; the run-detail drawer close control.

## 4. Feature checklist (feature → main anchor → where it must live post-rework)

Legend: **PRESENT** = anchor survives in the refreshed modules · **DEGRADED** = a weaker
substitute exists · **MISSING** = no home. "Home" = the refreshed static surface (markup or a
loaded module; `parity.js` where the workbench lens already lives).

### A. Operations board (main step-5/6/7) — `parity.js` workbench lens

| Feature | Main anchor (`1457b9299` `app.js`) | Current tree | Post-rework home |
|---|---|---|---|
| Lazy board loader + in-flight/loaded guards | `loadOperations(force)` (`:3033`), `state.operationsLoaded/operationsRequestInFlight` | PRESENT (simpler `loadOperations(host)`) | `parity.js` `loadOperations` |
| Packet renderer | `renderOperations(data)` (`:3057`) | PRESENT | `parity.js` `renderOperations` |
| Summary cards | `Control epoch`, `Repo head`, `Active runs`, `Decisions owed`, `Promotable runs`, `Unhealthy workers` (`:3072-3077`) | PRESENT (`kv-table`) | `parity.js` |
| Degraded / attention / safe-actions / lag blocks | `DEGRADED SURFACES`, `ATTENTION`, `SAFE ACTIONS`, `PROJECTION LAG` (`:3087-3178`) | PRESENT | `parity.js` |
| Active+promotable run table | `RUN_HEADERS` = `["Run","Spec","State","Phases","Model","Candidate","Started"]` (`:3030`), `runRow` (`:3014`) | PRESENT | `parity.js` |
| Generic record table | `objectTable` (`:3216`) | PRESENT | `parity.js` |
| Run detail | `openRunDetail` (`:3184`), `renderRunDetail` (`:3231`), sections `ATTEMPTS/GATES/APPROVALS/COMMAND JOURNAL` (`:3252-3278`) | PRESENT | `parity.js` |
| Click-through rows | `tr.dataset.runId` + `role="button"` + Enter/Space (`:2994-2999`, `:3610-3620`) | PRESENT (`data-run-id`) | `parity.js` |
| State-block renderer | `stateText(value)` → `"<state> — <reason>"` (`:2964-2974`) | PRESENT | `parity.js` |

### B. A7 — unavailability rendered, never blanked

| Feature | Main anchor | Current tree | Post-rework home |
|---|---|---|---|
| Degraded control DB ⇒ counts read `unavailable`, not `0` | `dbDegraded` (`:3068`), empty states `"…could not be read — …"` (`:3103-3160`) | PRESENT | `parity.js` |
| Run detail 200-with-error rendered by name | `"Run detail unavailable:"` (`:3200`) | PRESENT | `parity.js` |
| **Per-panel surface failure renders reason + URL** | **`renderSurfaceError(name, url, error)` (`:3333`) + `Promise.allSettled` (`:3300`)** | **MISSING** (inlines `"unavailable — HTTP <status>"`, reason dropped) | **`parity.js` surfaces lens** |
| Degraded lists on quality/SLA/batch | `data.degraded` renderers (`:3382,3436,3487`) | PRESENT | `parity.js` |
| Shell never queries an empty selector | `if (!selector) return` (`shell.js`) | PRESENT in `shell.js` (loaded only by main's index; see H) | refreshed loaded module |

### C. Surfaces board (main step-6/7) — read models

| Feature | Main anchor | Current tree | Post-rework home |
|---|---|---|---|
| Route table | `SURFACE_ROUTES` 7 routes (`:3284-3292`) | PRESENT | `parity.js` |
| Panel dispatch | `renderSurfacePanel(name,data)` (`:3338`) | PRESENT | `parity.js` |
| Quality / Value / Arms / SLA / Escalations / Energy panels | `renderQualityPanel` `:3352`, `renderValuePanel` `:3389`, `renderArmsPanel` `:3410`, `renderSlaPanel` `:3434`, `renderEscalationPanel` `:3468`, `renderEnergyPanel` `:3507` | PRESENT | `parity.js` |
| Story arc panel + fetch | `renderStoryArcPanel` `:3534`, `renderStoryArcBody` `:3560`, `loadStoryArc` `:3584`, `#story-arc-name`/`#story-arc-body` | PRESENT | `parity.js` |

### D. The step-12 batch lane — `renderBatchPanel`

| Feature | Main anchor | Current tree | Post-rework home |
|---|---|---|---|
| Not-measurable state + scanned count | `not measurable — … (scanned …)` (`:3493-3497`) | PRESENT | `parity.js` |
| Measurable fraction | `batch fraction … (batch_jobs/marked_jobs)` (`:3494`) | PRESENT | `parity.js` |
| Modeled scenario (discount/horizon/class) | `modeled scenario: …` (`:3499-3502`) | PRESENT | `parity.js` |
| Degraded list | `data.degraded` (`:3487`) | PRESENT | `parity.js` |

### E. Routing board — structured, not a KV dump

| Feature | Main anchor (`app.js`) | Current tree | Post-rework home |
|---|---|---|---|
| Semantic table builder | `routingTable(caption, headers, rows)` (`:2168`) | **MISSING** (uses `renderKV`) | `parity.js` routing lens |
| Per-task recommendations | `"Per-task routing"`, cols `["Task","Route","Target","Best correctness","Best efficiency"]`, `task.best_correctness_model`/`best_efficiency_model` (`:2234-2248`) | **MISSING** | `parity.js` |
| Strategy simulation | `"Strategy simulation"`, cols `["Strategy","N","Total cost","Avg correctness"]` (`:2249-2259`) | **MISSING** | `parity.js` |
| Empty state | `"No routing data yet. Run experiments across multiple models first."` (`:2232`) | **MISSING** | `parity.js` |
| Error state | `"Routing unavailable. Live workspace remains connected."` (`:2263`) | DEGRADED (HTTP-only) | `parity.js` |

### F. Registry board — filters + click-through lineage

| Feature | Main anchor | Current tree | Post-rework home |
|---|---|---|---|
| Filter controls | `#registry-filter-type`, `#registry-filter-lifecycle`, `#registry-filter-since` (`main_index.html:755/769/778`), submit wiring (`:3857`) | **MISSING** | `index.html` (in the workbench registry lens or a rebuilt drawer) |
| Filter params | `record_type` / `lifecycle` / `since` (`:2419-2424`) | **MISSING** | `parity.js` `loadRegistry` |
| Rendered table | `renderRegistryTable(rows)` (`:2436`), clickable `tr` w/ Enter/Space (`:2464-2470`) | **MISSING** | `parity.js` |
| Canonical columns/caption | `knowledge_id`, `"Canonical-state registry entries — activate a row for its lineage"` (`:2445-2448`) | **MISSING** | `parity.js` |
| One-hop lineage | `loadRegistryLineage(entityId)` (`:2485`), `#registry-lineage`/`#registry-lineage-content` (`main_index.html:785-787`), `Causes (justifying observation)` (`:2498`) | DEGRADED (`showLineage` generic KV) | `parity.js` + markup anchor |

### G. Subscription-usage (Money) board — providers + the authoritative meter

| Feature | Main anchor (`app.js`) | Current tree | Post-rework home |
|---|---|---|---|
| Loader + in-flight guard + refresh | `loadSubscriptionUsage(force)` (`:2271`), `#usage-refresh` (`main_index.html:826`) | **MISSING** (generic `renderKV`) | `parity.js` money lens |
| Honest money formatting | `usageUsd` (missing ⇒ `"Unavailable"`, never `$0.00`) (`:2193`) | **MISSING** | `parity.js` |
| Metric cards / empty / error states | `usageMetrics` `:2199`, `usageEmpty` `:2212`, `usageError` `:2217` | **MISSING** | `parity.js` |
| Cache provenance | `cacheState`/`data.stale`/`served_from`/`refresh_error` (`:2297-2306`) | **MISSING** | `parity.js` |
| Provider windows | cols `["Window","Used","Length","Resets (UTC)"]` (`:2315-2322`) | **MISSING** | `parity.js` |
| Local cash + platform meter | `"deepseek — per-token cash"`, `"deepseek platform — authoritative meter"`, `deepseek_platform`, `platform meter` (`:2325-2382`) | **MISSING** | `parity.js` |
| Refresh-failure keeps last snapshot | `"showing the last snapshot"`, `data-usage-refresh-error` (`:2305-2390`) | **MISSING** | `parity.js` |

### H. Keyed-list reconciliation (calm under poll)

| Feature | Main anchor | Current tree | Post-rework home |
|---|---|---|---|
| Shared reconciler loaded before the client | `keyed-list.js` (`main index.html:841`, `keyed-list.js` itself) | **MISSING from the refreshed `index.html`** (`shell.js`/`keyed-list.js`/`board-fleet.js`/`control-room-core.js`/`detail-sheet.js` are present but **not loaded**) | refreshed `index.html` loads `keyed-list.js` (or a loaded module references `ControlRoomKeyedList`) |
| Write-on-change helpers | `ControlRoomKeyedList.{reconcile,setText,setHidden,setAttribute,setClassName}` | **MISSING from the loaded set** | shared module consumed by `app.js`/`parity.js` polled lenses |
| app.js consumer | `const list = root.ControlRoomKeyedList` (`main app.js:35`) | replaced by a private `reconcileList` in `app.js` (run-list/attention only) | parity lenses reuse the shared module |

### I. Read-board refresh affordance (event wiring)

| Feature | Main anchor | Current tree | Post-rework home |
|---|---|---|---|
| Operations refresh | `#operations-refresh` + `bindSurfaceViews` (`:3609`) | **MISSING** (`shell.js` has it but is not loaded) | workbench lens action / `index.html` |
| Surfaces refresh | `#surfaces-refresh` (`:3627`) | **MISSING** | workbench lens action |
| Routing refresh | `#routing-refresh` (`:3835`) | **MISSING** | workbench lens action |
| Registry refresh | `#registry-refresh` (`:3856`) | **MISSING** | workbench lens action |
| Usage refresh | `#usage-refresh` (`:3836`) | DEGRADED (money lens has a `Refresh usage` action but no `usage-refresh` anchor) | workbench lens action |

### J. Run-detail drawer control (DOM anchor)

| Feature | Main anchor | Current tree | Post-rework home |
|---|---|---|---|
| Drawer container | `#run-detail-drawer` (`main_index.html:691`) | PRESENT (created in `parity.js`) | `parity.js` / markup |
| Drawer title / close | `#run-detail-title`, `#run-detail-close` / `aria-label="Close run detail"` (`:693-694`) | PRESENT by `aria-label` | `parity.js` |
| Escape closes, focus restored | `closeRunDetail` (`:3209`) | DEGRADED (no focus restore) | `parity.js` |

## 5. Acceptance for a2

1. `python -m pytest tests/test_control_room_feature_parity.py -q` → **0 failed**.
2. `python -m pytest tests/test_control_room_static_views.py tests/test_control_room_parity.py -q` stays green.
3. `python3 scripts/verify_control_room_rendering.py --check-fixtures` PASSES.
4. The refresh's design language is untouched — no revert of `index.html`/`app.js` to main's
   destination board; main's read views are integrated **into** the workbench lenses.
