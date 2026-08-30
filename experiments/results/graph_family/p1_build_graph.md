# persistent_code_graph — p1 build record (the persistent code graph loaded into the live neo4j)

**Phase:** `p1_build_graph` (spec `persistent_code_graph@0.1`).
**Role:** build the persistent code graph — BOUNDED to the build. Uses the existing wiring
(`code_ingestion.ingest_codebase_graph` → `graph.load_codebase_graph` for the module-level
`:CodeModule` graph; `graph.populate_versioned_graph` for the symbol-level
`:SymbolVersion`/`:ModuleVersion` graph with `CALLS` edges) to load the framework's own `src/`,
the 2d/2e fixture cells' codebases, and one story's 5-session arc — then records the node/edge
counts, the sample structural edges (INCLUDING the widgets→add dependants — the wall's edges),
and the snapshot deltas.
**Date:** 2026-08-31.
**Source revision (branch HEAD at phase start):** `e5ab0127e` (feature/persistent-code-graph).
**Graph service:** `bolt://localhost:7687` (FINOPS_NEO4J_URI). Machine-readable twin:
`experiments/results/graph_family/p1_build_graph.json`. Builder: `scripts/graph_family_build.py`.

## What was loaded (the corpus → the persistent graph)

| source | wiring | loaded as |
|---|---|---|
| the framework's own `src/agentic_dynamics` | `ingest_codebase_graph` → `load_codebase_graph` | `:CodeModule` 108 modules + `IMPORTS`/`IMPORTED_BY` edges under the `framework-src` run |
| the 2d/2e fixture cells (12 codebases — the `incorrect_rebuilt` cells, the probe, the 2e cells) | `ingest_codebase_graph` + `populate_versioned_graph` | `:CodeModule` (3/2 modules each) + `:ModuleVersion`/`:SymbolVersion`/`:Revision` with `CALLS`/`SUPERSEDES` — the widgets→add edges |
| one story's 5-session arc (`/tmp/story_c55b0cf5d2e9`, notification_service clean) | per-commit `CodeSnapshot` → `populate_versioned_graph` | 6 `:Revision` snapshots (seed + 5 sessions) with `SUPERSEDES` chains + per-commit deltas |

All loads are additive (`MERGE` + the two-ID contract): nothing was deleted.

## Node/edge counts (post-build, live graph)

| node/edge | count |
|---|---|
| `:CodeModule` nodes | 244 (108 framework + the fixture cells + the earlier corpus) |
| `:ModuleVersion` nodes | 4,098 |
| `:SymbolVersion` nodes | 32,001 |
| `:Revision` nodes | 281 |
| `:Knowledge` nodes | 33,961 |
| `IMPORTS` / `IMPORTED_BY` edges | 565 / 214 |
| `CALLS` edges | 5,394 |
| `CONTAINS` / `DEFINES` edges | 36,099 / 32,001 |
| `SUPERSEDES` edges | 3,499 |
| `TESTED_BY` edges | 9,685 |
| `TOUCHED` edges (`:ExperimentRun`→`:CodeModule`) | 272 |

## The wall's edges — the widgets→add dependants (THE fixture)

The persistent graph holds the `widgets→add` structural dependant edges for EVERY
`incorrect_rebuilt` cell (the 2e wall's cells). For
`self-cap2d_incorrect_rebuilt_status_quo_r1` the `CALLS` query against the live graph returns
**20 structural dependants of `add`**:

```
test_add, widget_1, widget_10, widget_11, widget_12, widget_13, widget_14, widget_15,
widget_16, widget_17, widget_18, widget_19, widget_2, widget_3, widget_4, widget_5,
widget_6, widget_7, widget_8, widget_9
```

The same 20 dependants exist for all four `incorrect_rebuilt` cells + the probe (and the
widgets are themselves changed symbols — the probe's seeds). This is the wall, made
inspectable: **the structural edges EXIST in the persistent graph** — the p2 phase will show
them side-by-side with the impacted counter's recorded 0.

Sample module-level structural edges (the same codebases at the module layer):

```
widgets.py -> calc.py     (IMPORTS — widgets.py imports calc)
test_calc.py -> calc.py   (IMPORTS)
```

## The cross-commit evolution shape (the story's 5-session arc)

`notification_service` (deepseek-v4-pro, clean), 6 commits: seed → Session 1 greenfield →
Session 2 feature_addition → Session 3 integration → Session 4 refactor → Session 5
cross_cutting. Per-commit structural shape (loaded into the graph under
`self-story_c55b0cf5d2e9`):

| commit | modules | symbols | CALLS edges | hub nodes (top in-degree) |
|---|---|---|---|---|
| seed `51ff538` | 1 | 17 | 16 | `get_db`(10), `get_user_from_token`(3), `hash_password`(2) |
| S1 greenfield `7aa30d8` | 2 | 32 | 20 | `_recv_json`(16) — the first hub appears |
| S2 feature_addition `3facd92` | 2 | 60 | 42 | `_recv_json`(37) — hub grows 2.3× |
| S3 integration `4e0171f` | 2 | 81 | 79 | `_recv_json`(48), `_start_background`/`_stop_background`(4) |
| S4 refactor `d5c1fe7` | 2 | 97 | 94 | `_recv_json`(48), `_get_transport`(5) — abstraction lands |
| S5 cross_cutting `eb4ec68` | 2 | 115 | 117 | `_recv_json`(59), `_make_timestamp`(10) |

The coupling drift is monotone: 16 → 117 CALLS edges as the sessions add features; the hub
`_recv_json` (the shared JSON-framing primitive) grows to 59 in-degree — a textbook new-hub
trajectory. Structural deltas per commit (typed `CodeDelta`): S1 is a rewrite (+33/−17
symbols); S2–S5 are additive (+28/+21/+16/+18 symbols) with the changes concentrated on the
message-route + transport symbols. The arc's graph footprint: 402 `:SymbolVersion` +
413 `SUPERSEDES` + 368 `CALLS` across the 6 `:Revision` nodes — the persistent, queryable
snapshot chain the design §2's cross-commit evolution calls for.

## Findings

1. **The persistent code graph is built.** The framework's own src (108 modules) + the 2d/2e
   fixture cells' codebases (12) + one story's 5-session arc are all live in the neo4j, via the
   existing wiring — the module layer (`CodeModule`/`IMPORTS`) and the symbol layer
   (`SymbolVersion`/`CALLS`/`SUPERSEDES`).
2. **The wall's edges are present and queryable.** The 20 `widgets→add` dependant edges exist
   for every `incorrect_rebuilt` cell. The impacted counter's 0 (recorded in
   `cap_adaptive_2d/p1_incorrect_rebuilt_probe.json`) is now checkable side-by-side against
   these edges — the semantic divergence (behavioral counter vs structural edges) is
   inspectable, which is exactly what p2's wall reproduction will show.
3. **The cross-commit evolution shape is captured.** The story's 5-session arc is loaded as a
   `:Revision`/`SUPERSEDES` chain with the per-commit structural deltas recorded — the added
   symbols, the coupling drift (16→117 call edges), the new hub nodes (`_recv_json` 16→59).

## Honest limits

- The framework src is loaded at the module layer only (the symbol layer for a ~4k-symbol
  framework was out of scope for this bounded build; the corpus already carried the framework's
  versioned symbols from the earlier ingestion).
- The story arc's `added_call_edges` include name-resolved builtin calls (the typed delta's
  raw view); the resolved call-edge counts in `snapshot_shapes` filter to in-snapshot symbols.
- The story arc is one clean `notification_service` run (the seed codebase is a full rewrite at
  S1); the perturbation-condition arcs are left to later phases.

**LOG:** framework src 108 modules / 125 imports loaded; 12 fixture cells loaded (module +
symbol layer); the wall's edges confirmed live (20 widgets→add dependants per `incorrect_rebuilt`
cell); story arc loaded as 6 revisions (402 symbol versions / 413 supersedes / 368 calls) with
the per-commit deltas recorded; record written to `experiments/results/graph_family/`. **PASS.**
