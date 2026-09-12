---
status: accepted
---

# Control Room research — taxonomy support repair (campaign `control_room_research_repair`, phase `p0_repair_taxonomy`)

**Date:** 2026-09-11
**Scope:** `experiments/research/control_room/taxonomy.json` (rebuilt),
`experiments/research/control_room/{catalogs,skills}.json` (regenerated from it),
and the two builders `build_taxonomy.py` / `reduce_knowledge.py`.
**Inputs:** the five family corpora `agentops.jsonl` (48), `dashboards.jsonl` (58),
`dataviz.jsonl` (41), `cli.jsonl` (34), `craft.jsonl` (48) — 229 records, 270 raw
technique labels.
**Trigger:** adversary pass r6a (`docs/reviews/control_room_research_entailment.md`)
found that r3 promoted broad labels into narrow techniques no source states, and
that r4/r5 then cited the inflated supports as measured evidence.

## 1. Verdict

**REPAIRED.** Every support count in the rebuilt taxonomy is now the number of
distinct corpus records whose **own technique labels directly name the node's
technique**. A broad label backs its umbrella node and nothing narrower. Seven
inflated nodes were deleted, four were recast/renamed to the technique the labels
actually state, and eight honest-but-thin leaves were left below the bar. The
regenerated catalogs carry 10 explicit `[P]` local-policy items and the regenerated
skills carry 7 `[P]` policy blocks; no item presents an unsupported move as a
finding. Every emitted source reference and taxonomy id resolves.

## 2. Method (zero label promotion)

1. Load the five corpora; take each record's `techniques` labels as the record's own
   statement of technique.
2. Crosswalk each raw label to at most one canonical technique leaf **only when the
   label literally names it**. If no direct home exists, the label stays unmapped
   (198/270 labels map; 156 mention-instances are intentionally outside technique
   clusters).
3. `support` = count of distinct records whose direct labels name the node; family
   counts come from those records. Group/dimension support is an exact union of child
   records, never a sum.
4. A leaf with `support < 3` is **thin**: kept for transparency, never promoted.
5. A node whose support existed only by promotion is **deleted** and recorded in
   `taxonomy.repair.deleted_nodes` with the broad labels that manufactured it.
6. Catalogs/skills are re-pointed at the repaired nodes; any recommendation whose
   backing node was deleted or fell below the bar becomes an explicit `[P]` local
   design policy with a one-line reason.

Reproduce:

```bash
python3 experiments/research/control_room/build_taxonomy.py    # taxonomy.json + repair ledger
python3 experiments/research/control_room/reduce_knowledge.py  # catalogs.json + skills.json + ref check
```

## 3. What was inflated

The r3 crosswalk allocated **generic umbrella labels** to **specific marks**:

| Node | Broad labels it was promoted from | r3 inflated it to |
|---|---|---:|
| `tech-ia-board-per-domain` | `dashboards`, `dashboard`, `dashboard-grid` | 55 |
| `tech-trust-source-provenance` | `logs`, `metrics`, `cost-tracking`, `data-join` | 40 |
| `tech-viz-heatmap-status-grid` | `status`, `chart-types` | 30 |
| `tech-viz-gauge` | `process-monitor`, `progress`, `chart-types` | 25 |
| `tech-money-budget-thresholds` | `alerting`, `alerting-rules` | 19 |
| `tech-trust-audit-trail` | `changelog`, `deployments`, `provisioning`, `webhooks` | 14 |
| `tech-trust-degraded-banner` | `status` | 11 |
| `tech-money-quota-wallet` | `payments`, `pricing` | 7 |
| `tech-trust-uncertainty-encoding` | `online-evaluation`, `eval`, `chart-types` | 3 |

Common failure shapes: *a status label is not a status grid*; *a metric is not a
provenance fact*; *a table label is not a virtualized table*; *a payment surface is
not an agent quota/wallet*; *a changelog is not an actor audit trail*.

## 4. Before/after support — affected nodes

"Before" = committed r3 `taxonomy.json`; "after" = rebuilt `taxonomy.json`.
`(deleted)` = no source record states the technique; `(thin)` = direct but `< 3`.

| Affected node | Before | After | Disposition |
|---|---:|---:|---|
| `tech-ia-board-per-domain` | 55 | — | deleted; recast as `tech-ia-dashboard-layout` (43) |
| `tech-trust-source-provenance` | 40 | — | deleted; `metrics`→`tech-ops-metrics`, `logs`→`tech-viz-log-stream`, `cost-tracking`→`tech-money-cost-attribution` |
| `tech-viz-heatmap-status-grid` | 30 | 4 | recast `tech-viz-heatmap` (direct `heatmap`/`heatmap-status-grid`) |
| `tech-viz-gauge` | 25 | 1 | `thin-viz-gauge` (thin, not promoted) |
| `tech-money-budget-thresholds` | 19 | — | deleted; generic `alerting` is `tech-trust-alerting` (23) |
| `tech-trust-audit-trail` | 14 | — | deleted; `changelog`/`deployments` are `tech-ops-release-feed` (26) |
| `tech-trust-degraded-banner` | 11 | — | deleted; `status` is `tech-trust-status-indicator` (9) |
| `tech-money-quota-wallet` | 7 | — | deleted; `payments` is `tech-money-billing` (7) |
| `tech-trust-uncertainty-encoding` | 3 | — | deleted |
| `tech-trust-freshness-indicator` | 4 | — | deleted (direct support 1) |
| `tech-viz-chart-grammar` | 52 | 15 | direct grammar labels only |
| `tech-viz-time-series-marks` | 39 | 12 | direct marks only |
| `tech-ia-widget-catalog` | 63 | 41 | direct widget/panel labels |
| `tech-viz-virtualized-table` | 32 | 32 | recast `tech-viz-data-table`; **virtualization** is 3 (`[P]`) |
| `tech-viz-log-stream` | 36 | 32 | direct log/stream labels |
| `tech-int-keyboard-first` | 30 | 22 | direct keyboard labels |
| `tech-svg-theme-aware-svg` | 29 | 11 | direct `theme-aware-svg` |
| `tech-vis-design-tokens` | 28 | 29 | direct token/theme labels |
| `tech-trust-alerting` | 28 | 23 | dropped generic `monitoring` |
| `tech-viz-sampling-decimation` | 15 | 17 | recast `tech-viz-rendering-performance`; decimation is 2 |
| `tech-int-empty-error-states` | 22 | 8 | split issue tracking out (`tech-ops-issue-tracking`, 15) |
| `tech-int-focus-management` | 12 | 6 | ARIA/live/semantics split to `tech-int-aria-live` (4) |
| `tech-int-reduced-motion` | 14 | 6 | direct `reduced-motion` |
| `tech-svg-micro-visual` | 22 | 17 | direct micro-mark labels |
| `tech-trust-causal-lineage` | 23 | 18 | session grouping split to `tech-ops-session-grouping` (14) |
| `tech-ia-master-detail` | 15 | 4 | direct `master-detail`/`docked-detail` |
| `tech-ia-tab-bar` | 15 | 8 | direct tab/pane labels |
| `tech-ia-command-palette` | 14 | 11 | direct palette/find labels |
| `tech-ia-density-ladder` | 14 | 8 | direct density/responsive labels |
| `tech-viz-timeline-gantt` | 14 | 14 | recast `tech-viz-waterfall-timeline` (trace waterfall) |
| `tech-vis-motion-easing` | 11 | 7 | direct `motion-easing` |
| `tech-vis-colorblind-safe-status` | 16 | 12 | direct color labels |
| `tech-svg-accessible-svg` | 10 | 5 | direct `accessible-svg` (ARIA split off) |
| `tech-vis-accent-economy` | 10 | 5 | direct `accent-economy` |
| `tech-vis-forced-colors` | 8 | 4 | direct `forced-colors` |
| `tech-money-cost-attribution` | 17 | 13 | direct `cost-tracking` |
| `tech-ops-observability` | 22 | 18 | dropped generic `monitoring` |
| `tech-ops-prompt-registry` | 4 | 3 | direct prompt-version/deploy labels |
| `tech-viz-small-multiples` | 4 | 2 | `thin-viz-small-multiples` (thin) |
| `tech-svg-flow-diagram` | 4 | 2 | `thin-svg-flow-diagram` (thin) |
| `tech-int-confirmation-door` | 3 | 1 | `thin-int-confirmation-door` (thin) |
| `thin-viz-threshold-bands` | 1 | 2 | direct `threshold-bands` + `staleness-threshold` |

Unchanged or effectively unchanged: `tech-int-live-follow` (22), `tech-int-sort-filter`
(11), `tech-int-skeleton-loading` (5), `tech-vis-type-scale` (9→10), `tech-vis-icon-family`
(4), `tech-vis-elevation-model` (3), `tech-svg-print-safe-svg` (3), `tech-ops-eval-loop`
(24), `tech-ops-trace-tree` (22→20), `thin-ops-self-host` (2), `thin-ia-modal-sheet` (1),
`thin-ia-overflow-drawer` (1).

Corpus totals (unchanged): 229 records, agentops 48 / dashboards 58 / dataviz 41 /
cli 34 / craft 48. Taxonomy nodes 105 → 109; promoted technique leaves 52 → 49;
thin leaves 4 → 8.

## 5. Nodes deleted (support only from a broader label)

| Deleted node | Was | Promoted from | Why it cannot stand |
|---|---:|---|---|
| `tech-ia-board-per-domain` | 55 | `dashboards`, `dashboard`, `dashboard-grid` | Generic boards do not state a work/money/health/decisions split. |
| `tech-trust-source-provenance` | 40 | `logs`, `metrics`, `cost-tracking`, `data-join` | Logs/metrics/cost state their own surfaces, not provenance. |
| `tech-money-budget-thresholds` | 19 | `alerting`, `alerting-rules` | Alerting is not a budget threshold. |
| `tech-trust-audit-trail` | 14 | `changelog`, `deployments`, `provisioning`, `webhooks` | Those are a release/deploy feed, not actor history. |
| `tech-trust-degraded-banner` | 11 | `status` | Generic status is not a named-dependency banner. |
| `tech-money-quota-wallet` | 7 | `payments`, `pricing` | Billing is not an agent quota/wallet/lease. |
| `tech-trust-uncertainty-encoding` | 3 | `online-evaluation`, `eval`, `chart-types` | Eval/chart labels do not state uncertainty encoding. |

Also: `tech-trust-freshness-indicator` deleted (direct support 1); `viz-gauge`,
`viz-small-multiples`, `svg-flow-diagram`, `int-confirmation-door` moved to explicit
`thin-*` nodes rather than promoted.

## 6. Recast / new nodes (direct labels with a real home)

| New node | Support | Families | Replaces / origin |
|---|---:|---|---|
| `tech-ia-dashboard-layout` | 43 | dashboards | `tech-ia-board-per-domain` (generic board only) |
| `tech-ops-metrics` | 34 | dashboards, agentops, cli | `metrics` labels ex-provenance |
| `tech-ops-release-feed` | 26 | dashboards | `changelog`/`deployments` ex-audit-trail |
| `tech-viz-data-table` | 32 | 4 | `tech-viz-virtualized-table` (tables ≠ virtualization) |
| `tech-ops-issue-tracking` | 15 | dashboards | `error-tracking`/`issues-list` ex-empty-states |
| `tech-ops-session-grouping` | 14 | agentops | `session-grouping` ex-causal-lineage |
| `tech-viz-waterfall-timeline` | 14 | agentops | `tech-viz-timeline-gantt` (trace waterfall) |
| `tech-trust-status-indicator` | 9 | dashboards | `status` ex-degraded-banner |
| `tech-money-billing` | 7 | dashboards, agentops | `payments` ex-quota-wallet |
| `tech-int-aria-live` | 4 | craft, dataviz | ARIA/live-region labels ex-focus-management |
| `tech-viz-chart-types` | 23 | dataviz, dashboards | the broad `chart-types` umbrella kept whole |
| `tech-viz-heatmap` | 4 | dataviz, craft | `heatmap` + `heatmap-status-grid` |
| `tech-viz-rendering-performance` | 17 | dataviz, cli, craft | renderer/performance labels ex-decimation |

## 7. Downgraded to [P] local design policy

Catalog items (`catalogs.json`, `evidence_class: "[P]"`, each with `policy_reason`):

| Item | Move demoted | Reason (one line) |
|---|---|---|
| `ia-board-per-domain` | Domain-split boards | No source states domain partitioning; inflated from generic dashboards. |
| `ia-money-grouping` | Money board (quota/wallet/leases) | No source states quota/wallet; promoted from payments/alerting. |
| `ch-gauge` | Gauge mark for a bounded quantity | Direct support is 1 record. |
| `ch-small-multiples` | Small multiples | Direct support is 2 records. |
| `ia-audit-trail` | Actor audit trail | No source states it; promoted from a release feed. |
| `tr-provenance` | Provenance badge | No source states it; grounded in the repo cost-provenance contract. |
| `tr-freshness` | Freshness / retained-window marker | Direct support is 1 record. |
| `tr-degraded` | Degraded banner naming the dependency | No source states it. |
| `tr-uncertainty` | Explicit uncertainty / unmeasured encoding | No source states it. |
| `svg-flow` | Flow-diagram topology | Direct support is 2 records. |

`ch-table` stays `[X]` for the table surface but carries a `policy_notes` entry that
row virtualization is `[P]` (3 direct records). `fw-no-build` stays `[X]` for the corpus
alternatives but carries a `policy_notes` entry that the no-build choice is a `[P]`
guardrail (r0 §9.8, r6a E7).

Skills (`skills.json`, `policy` array with per-move reason; recommendation prose now
ends with "Local [P] policy (not corpus findings): …"):

| Skill | [P] moves |
|---|---|
| `skill-delivery` | Stay build-less / rule out React. |
| `skill-shell-ia` | Domain-split boards; money board grouping; dedicated attention board. |
| `skill-glance` | Status grid as the glance default; money above the fold; named degraded/staleness summary. |
| `skill-charts` | Gauge; small multiples; virtualized-table implementation. |
| `skill-svg` | Specific flow-diagram topology. |
| `skill-trust` | Provenance badge; named degraded banner; uncertainty/unmeasured encoding; freshness marker. |
| `skill-synthesis` | All of the above, consolidated. |

`skill-visual-system` and `skill-agent-ops` keep no `[P]` moves: their backing nodes
survived the repair.

While regenerating, r6a E5's universal/superlative wording was also replaced with
source-bounded wording (fw-echarts "strongest" → its own ARIA guide; ch-timeline and
tr-lineage "every major agent-ops source" → the cited sources; ao-eval "F1 is
unanimous" → "the agent-ops sources document"; ia-attention-surface "all" → the cited
Grafana/Datadog/Sentry records).

## 8. Citation verification

- Every `sha256`/`uri` triple in `catalogs.json` and `skills.json` resolves to a
  corpus record; titles are re-copied exactly, closing the seven title drifts of r6a E8.
- Every `taxonomy_nodes` id in the catalogs and every `backing_nodes` id in the skills
  resolves to a node in the rebuilt `taxonomy.json`.
- `reduce_knowledge.py` fails the run (`SystemExit(1)`) if any reference does not
  resolve; the committed run reports **0 unresolved refs**.

## 9. Residual caveats (recorded, not resolved)

- The rebuilt supports are conservative: `support` comes from the record's encoded
  `techniques` labels, which are r2's extraction of the source text. A technique that a
  source states but r2 did not label stays unmapped (156 mention-instances). This can
  understate, never overstate, external support.
- Several surviving nodes are single-family (e.g. `tech-ops-eval-loop` agentops 24,
  `tech-viz-waterfall-timeline` agentops 14, `tech-trust-alerting` dashboards 23,
  `tech-ops-release-feed` dashboards 26). Catalogs/skills must carry the single-family
  caveat; the reduction copies it into `caveats`.
- The money, provenance, degraded-banner, uncertainty and domain-split moves are not
  wrong designs — they are now correctly labeled `[P]` local policy instead of
  high-support external findings, per the campaign's hard rule.
