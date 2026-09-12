---
status: accepted
---

# Control Room research — taxonomy (campaign phase r3)

**Date:** 2026-09-11  
**Campaign:** `workflows/repository/control_room_research.yaml`, phase `r3_taxonomy`.  
**Inputs:** the five family corpora `agentops.jsonl` (48), `dashboards.jsonl` (58), `dataviz.jsonl` (41), `cli.jsonl` (34), `craft.jsonl` (48).  
**Outputs:** `experiments/research/control_room/taxonomy.json` (machine) and this document.

Every number below is a count of corpus records; every cluster cites its example refs in
`taxonomy.json`. No claim in this document goes beyond the records. Clusters **overlap**: a
record can appear in several clusters, so supports do not sum to the corpus total.

## 1. Method

1. Load all five corpora (agentops, dashboards, dataviz, cli, craft).
2. Crosswalk each of the 270 raw technique labels to a
   canonical leaf in the r1 facet vocabulary (56 leaves defined).
3. **SPLIT** umbrella labels that mix distinct techniques, and **MERGE** thin/synonymous
   labels. Promote a leaf to its own node only when it reaches the r1 §3.3 bar of
   **≥3 independent sources**; otherwise merge it into its group (`thin-*` nodes).
4. Add the category / aesthetic / stack / quality-signal dimension branches (synonyms merged).

## 2. Corpus totals

| Family | Records |
|---|---|
| agentops | 48 |
| dashboards | 58 |
| dataviz | 41 |
| cli | 34 |
| craft | 48 |
| **total** | **229** |

- Canonical technique leaves defined: **56**.
- Promoted (≥3 sources): **52**.
- Thin, merged below the bar: **4**.
- Raw labels not clustered (stack-like or source-specific, 12 mentions): 
  `recharts`, `react`, `tailwind`, `terminal-craft`, `ssh-apps`.

## 3. Split decisions (heterogeneous clusters)

| Umbrella label | Split into | Reason |
|---|---|---|
| `dashboards/dashboard` | `ia-board-per-domain`, `ia-widget-catalog` | The generic dashboard label mixes the board-per-domain IA with the widget catalog that fills it. |
| `chart-types/charts` | `viz-chart-grammar`, `viz-time-series-marks`, `viz-heatmap-status-grid`, `viz-gauge` | A chart-types umbrella spans grammar/library choice and several concrete mark families. |
| `widget-catalog/panel-library` | `ia-widget-catalog`, `viz-chart-grammar` | Widget catalogs include chart widgets and non-chart panels; split by whether the widget is a mark. |
| `status` | `viz-heatmap-status-grid`, `trust-degraded-banner` | status is both a per-node status grid encoding and a top-level degraded/health banner. |
| `metrics` | `trust-source-provenance`, `viz-time-series-marks` | metrics is the provenance/attribution fact and the time-series mark that draws it. |
| `monitoring` | `ops-observability`, `trust-alerting` | monitoring covers agent instrumentation and the alerting surface built on it. |
| `logs` | `viz-log-stream`, `trust-source-provenance` | logs are the live stream surface and a provenance-bearing record. |
| `cost-tracking` | `money-cost-attribution`, `trust-source-provenance` | cost tracking is a money surface and a provenance/attribution fact. |
| `alerting/alerting-rules` | `trust-alerting`, `money-budget-thresholds` | alerting covers the attention surface and spend/budget thresholds. |
| `accessibility` | `svg-accessible-svg`, `int-focus-management`, `vis-colorblind-safe-status`, `int-reduced-motion` | The accessibility label spans SVG alternatives, focus/ARIA, color safety and motion. |
| `motion` | `int-reduced-motion`, `vis-motion-easing` | motion is both the easing system and its reduced-motion escape hatch. |
| `opaque umbrella labels` | `(see unmapped)` | Labels naming an implementation stack or a single source's marketing copy (react, tailwind, terminal-craft, ...) are counted but not clustered as techniques. |

## 4. Merge decisions (thin / synonymous clusters)

| Merged labels | Into | Reason |
|---|---|---|
| `logs`, `log-stream`, `streaming`, `real-time-streaming`, `request-log`, `process-monitor`, `resource-monitor`, `session-recording` | `viz-log-stream` | Every live-stream label denotes one log/event surface; merged so support reflects the surface. |
| `table-view`, `virtualized-table`, `tables`, `table`, `reference-tables`, `list` | `viz-virtualized-table` | All large-tabular labels merged into the virtualized-table cluster. |
| `dashboards`, `dashboard`, `dashboard-grid` | `ia-board-per-domain` | Board labels merged; the widget catalog they contain is the separate ia-widget-catalog node. |
| `widget-catalog`, `widgets`, `panel-library`, `tui-components`, `blocks`, `dashboard-blocks`, `dashboard-components` | `ia-widget-catalog` | Thin synonymous widget/panel catalogs across F2/F3/F4 merged. |
| `design-tokens`, `color-tokens`, `color-palette`, `themes`, `theme-config`, `dark-theme`, `light-theme`, `light-mode`, `dark-first-theming`, `theming` | `vis-design-tokens` | Token/theming synonyms merged; dark-first is a value of the token system, not a separate cluster. |
| `span-tree`, `session-grouping`, `traces-spans`, `waterfall-timeline` | `trust-causal-lineage` | Trace-tree labels merged into the causal-lineage cluster (the waterfall mark stays in viz-timeline-gantt). |
| `tabs`, `native-tabs`, `split-panes`, `panes`, `splits`, `multiplexing` | `ia-tab-bar` | Terminal pane/tab labels merged into one navigation cluster. |
| `online-evaluation`, `eval`, `llm-evaluation`, `eval-narratives`, `scorer-config`, `pytest-style-scorers`, `experiment-comparison`, `regression-suite`, `prompt-comparison`, `dataset-management`, `datasets`, `rl-environments`, `playground-iteration`, `benchmarking`, `eval-monitoring`, `eval-metrics` | `ops-eval-loop` | Every eval/dataset/experiment label merged into one eval-loop cluster. |
| `micro-visual`, `sparkline`, `color-bars`, `braille-graphs` | `svg-micro-visual` | Thin micro-mark labels merged; they share the no-JS-runtime SVG/CSS craft. |
| `contrast`, `colorblind-safe`, `colorblind-safe-status`, `sequential-color`, `diverging-color`, `categorical-color`, `color-perception`, `color` | `vis-colorblind-safe-status` | Color labels merged into the colorblind-safe-status cluster. |

## 5. IA / layout clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `tech-ia-widget-catalog` | 63 | dashboards:41, cli:15, dataviz:7 | yes | promoted: >=3 sources |
| `tech-ia-board-per-domain` | 55 | dashboards:53, agentops:1, cli:1 | yes | promoted: >=3 sources |
| `tech-ia-tab-bar` | 15 | cli:14, craft:1 | yes | promoted: >=3 sources |
| `tech-ia-master-detail` | 15 | cli:11, craft:4 | yes | promoted: >=3 sources |
| `tech-ia-command-palette` | 14 | dashboards:11, cli:3 | yes | promoted: >=3 sources |
| `tech-ia-density-ladder` | 14 | dashboards:7, dataviz:3, craft:3, cli:1 | yes | promoted: >=3 sources |
| `tech-ia-progressive-disclosure` | 4 | craft:4 | yes | promoted: >=3 sources |
| `thin-ia-modal-sheet` | 1 | craft:1 | no | merged: below the >=3-source rule |
| `thin-ia-overflow-drawer` | 1 | craft:1 | no | merged: below the >=3-source rule |

## 6. Data / viz clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `tech-viz-chart-grammar` | 52 | dataviz:32, dashboards:19, cli:1 | yes | promoted: >=3 sources |
| `tech-viz-time-series-marks` | 39 | dashboards:20, dataviz:17, cli:2 | yes | promoted: >=3 sources |
| `tech-viz-log-stream` | 36 | dashboards:25, cli:7, agentops:2, dataviz:2 | yes | promoted: >=3 sources |
| `tech-viz-virtualized-table` | 32 | dashboards:25, cli:3, craft:3, dataviz:1 | yes | promoted: >=3 sources |
| `tech-viz-heatmap-status-grid` | 30 | dashboards:17, dataviz:10, cli:2, craft:1 | yes | promoted: >=3 sources |
| `tech-viz-gauge` | 25 | dataviz:10, dashboards:8, cli:6, craft:1 | yes | promoted: >=3 sources |
| `tech-viz-sampling-decimation` | 15 | cli:8, dataviz:5, craft:2 | yes | promoted: >=3 sources |
| `tech-viz-timeline-gantt` | 14 | agentops:14 | yes | promoted: >=3 sources |
| `tech-viz-small-multiples` | 4 | dataviz:3, craft:1 | yes | promoted: >=3 sources |
| `thin-viz-threshold-bands` | 1 | craft:1 | no | merged: below the >=3-source rule |

## 7. Interaction clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `tech-int-keyboard-first` | 30 | cli:15, dashboards:11, craft:4 | yes | promoted: >=3 sources |
| `tech-int-live-follow` | 22 | dashboards:13, cli:7, craft:2 | yes | promoted: >=3 sources |
| `tech-int-empty-error-states` | 22 | dashboards:17, agentops:2, craft:2, dataviz:1 | yes | promoted: >=3 sources |
| `tech-int-reduced-motion` | 14 | dashboards:7, craft:6, dataviz:1 | yes | promoted: >=3 sources |
| `tech-int-focus-management` | 12 | craft:7, dashboards:3, dataviz:2 | yes | promoted: >=3 sources |
| `tech-int-sort-filter` | 11 | dashboards:8, cli:2, craft:1 | yes | promoted: >=3 sources |
| `tech-int-skeleton-loading` | 5 | cli:3, craft:2 | yes | promoted: >=3 sources |
| `tech-int-confirmation-door` | 3 | cli:2, craft:1 | yes | promoted: >=3 sources |

## 8. Visual-system clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `tech-vis-design-tokens` | 28 | craft:10, dashboards:8, dataviz:8, cli:2 | yes | promoted: >=3 sources |
| `tech-vis-colorblind-safe-status` | 16 | craft:6, dashboards:5, dataviz:4, cli:1 | yes | promoted: >=3 sources |
| `tech-vis-motion-easing` | 11 | craft:7, dashboards:4 | yes | promoted: >=3 sources |
| `tech-vis-accent-economy` | 10 | craft:5, dashboards:4, cli:1 | yes | promoted: >=3 sources |
| `tech-vis-type-scale` | 9 | craft:5, dashboards:3, cli:1 | yes | promoted: >=3 sources |
| `tech-vis-forced-colors` | 8 | cli:4, craft:4 | yes | promoted: >=3 sources |
| `tech-vis-icon-family` | 4 | craft:4 | yes | promoted: >=3 sources |
| `tech-vis-elevation-model` | 3 | craft:3 | yes | promoted: >=3 sources |

## 9. Trust / ops clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `tech-trust-source-provenance` | 40 | dashboards:26, agentops:13, dataviz:1 | yes | promoted: >=3 sources |
| `tech-trust-alerting` | 28 | dashboards:23, agentops:5 | yes | promoted: >=3 sources |
| `tech-trust-causal-lineage` | 23 | agentops:16, dashboards:5, cli:2 | yes | promoted: >=3 sources |
| `tech-trust-audit-trail` | 14 | dashboards:7, cli:6, agentops:1 | yes | promoted: >=3 sources |
| `tech-trust-degraded-banner` | 11 | dashboards:11 | yes | promoted: >=3 sources |
| `tech-trust-freshness-indicator` | 4 | cli:3, craft:1 | yes | promoted: >=3 sources |
| `tech-trust-uncertainty-encoding` | 3 | agentops:2, dataviz:1 | yes | promoted: >=3 sources |

## 10. SVG / diagram clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `tech-svg-theme-aware-svg` | 29 | craft:12, cli:9, dataviz:8 | yes | promoted: >=3 sources |
| `tech-svg-micro-visual` | 22 | craft:12, dataviz:7, cli:3 | yes | promoted: >=3 sources |
| `tech-svg-accessible-svg` | 10 | craft:5, dashboards:3, dataviz:2 | yes | promoted: >=3 sources |
| `tech-svg-path-tracer` | 7 | craft:5, dataviz:2 | yes | promoted: >=3 sources |
| `tech-svg-flow-diagram` | 4 | cli:2, craft:2 | yes | promoted: >=3 sources |
| `tech-svg-print-safe-svg` | 3 | craft:3 | yes | promoted: >=3 sources |

## 11. Money clusters (emergent)

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `tech-money-budget-thresholds` | 19 | dashboards:19 | yes | promoted: >=3 sources |
| `tech-money-cost-attribution` | 17 | agentops:13, dashboards:4 | yes | promoted: >=3 sources |
| `tech-money-quota-wallet` | 7 | dashboards:6, agentops:1 | yes | promoted: >=3 sources |

## 12. Agent-ops clusters (emergent)

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `tech-ops-eval-loop` | 24 | agentops:24 | yes | promoted: >=3 sources |
| `tech-ops-trace-tree` | 22 | agentops:17, dashboards:5 | yes | promoted: >=3 sources |
| `tech-ops-observability` | 22 | agentops:19, dashboards:3 | yes | promoted: >=3 sources |
| `tech-ops-prompt-registry` | 4 | agentops:3, cli:1 | yes | promoted: >=3 sources |
| `thin-ops-self-host` | 2 | agentops:2 | no | merged: below the >=3-source rule |

### Thin (merged) technique nodes

| Node | Support | Families | Note |
|---|---|---|---|
| `thin-ia-modal-sheet` | 1 | craft | merged: below the >=3-source rule |
| `thin-ia-overflow-drawer` | 1 | craft | merged: below the >=3-source rule |
| `thin-viz-threshold-bands` | 1 | craft | merged: below the >=3-source rule |
| `thin-ops-self-host` | 2 | agentops | merged: below the >=3-source rule |

## 13. Category clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `cat-ops-dashboard` | 55 | dashboards:55 | yes | merged family-specific category values |
| `cat-agent-ops-room` | 42 | agentops:42 | yes | merged family-specific category values |
| `cat-design-craft` | 35 | craft:28, dataviz:6, cli:1 | yes | merged family-specific category values |
| `cat-terminal-app` | 33 | cli:33 | yes | merged family-specific category values |
| `cat-chart-library` | 28 | dataviz:28 | yes | merged family-specific category values |
| `cat-reference-standard` | 20 | craft:20 | yes |  |
| `cat-component-kit` | 7 | dataviz:7 | yes |  |
| `cat-case-study` | 6 | agentops:6 | yes |  |
| `cat-design-system` | 3 | dashboards:3 | yes |  |

## 14. Aesthetic clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `aes-unspecified` | 105 | agentops:48, dataviz:29, craft:27, cli:1 | yes |  |
| `aes-dark-dense` | 38 | dashboards:35, craft:3 | yes |  |
| `aes-light-minimal` | 32 | dashboards:17, craft:11, dataviz:4 | yes |  |
| `aes-terminal-native` | 23 | cli:23 | yes |  |
| `aes-high-contrast-mono` | 16 | cli:10, dashboards:6 | yes |  |
| `aes-hybrid-theme` | 13 | dataviz:8, craft:5 | yes |  |
| `aes-precision-instrument` | 1 | craft:1 | no |  |
| `aes-editorial` | 1 | craft:1 | no |  |

## 15. Stack clusters

| Node | Support | Families | ≥3 sources | Note |
|---|---|---|---|---|
| `stk-none` | 82 | agentops:48, craft:33, cli:1 | yes |  |
| `stk-unknown` | 64 | dashboards:58, dataviz:6 | yes |  |
| `stk-chart-lib` | 22 | dataviz:22 | yes |  |
| `stk-svg-css-only` | 15 | craft:15 | yes |  |
| `stk-vanilla-js` | 14 | dataviz:11, cli:3 | yes |  |
| `stk-tui-go` | 11 | cli:11 | yes |  |
| `stk-react` | 10 | dataviz:10 | yes |  |
| `stk-tui-rust` | 10 | cli:10 | yes |  |
| `stk-tui-python` | 8 | cli:8 | yes |  |
| `stk-d3` | 5 | dataviz:5 | yes |  |
| `stk-tui-native` | 5 | cli:5 | yes |  |
| `stk-canvas-webgl` | 2 | dataviz:2 | no |  |

## 16. Quality signals

| Signal | Distribution |
|---|---|
| `authority` | vendor-primary=175; practitioner=18; independent-analysis=15; standards-body=14; vendor-blog=7 |
| `recency` | current=212; recent=10; dated=7 |
| `accessibility_evidence` | none=196; claimed=20; audited=12; documented=1 |
| `performance_evidence` | none=227; measured=1; claimed=1 |
| `demonstrates` | true for 190/229 records |
| `open_implementation` | true for 156/229 records |

## 17. Coverage caveats (recorded, not resolved)

- `aesthetic=unspecified` dominates (105/229) because text extraction cannot see pixels;
  the visual-system claims rest on the sources that state their system (F2/F5).
- Material/Apple HIG density pages are client-rendered (0 chars) and absent from the craft
  corpus, so `ia-density-ladder` is evidenced indirectly (Every Layout, web.dev, Refactoring UI).
- `performance_evidence=measured` appears once (web.dev content-visibility); the rest is `none`.
- Some clusters rest on one family (e.g. agent-ops surfaces are F1-only); r4 must apply the
  single-source caveat there rather than treat the count as independent corroboration.

## 18. Reproduce

```bash
python3 scripts/research_fetch.py --from-file experiments/research/control_room/seeds/*.txt \
  --out-dir experiments/research/control_room   # r2a-r2e (already committed)
# taxonomy is derived by the r3 builder over corpus/*.jsonl; see taxonomy.json inputs[] for hashes
```

