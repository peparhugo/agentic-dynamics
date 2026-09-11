---
status: accepted
---

# Control Room research — entailment / quality review (campaign r6a)

**Reviewer:** `openai/gpt-5.6-terra`  
**Date:** 2026-09-11  
**Scope:** `docs/research/control_room_direction.md` (r5),
`experiments/research/control_room/{skills,catalogs}.json` (r4), and their claimed support in
`taxonomy.json` (r3) plus the five `corpus/*.jsonl` files.  
**Out of scope:** redesigning the direction, acquiring new sources, editing the corpus/taxonomy, or
changing portal code. This pass writes this review only.

`[src:*]` tags below use r5's appendix table; this pass independently checked the tag, URI, family,
and SHA prefix against the corpus.

## Verdict

**NOT CLEAN — remediation required before r7.**

The provenance graph is unusually strong: actual source references resolve to stored corpus records,
and r4 copied the support fields it was given by r3 faithfully. The failure is semantic, not a broken
link: r3's crosswalk promotes generic labels (`chart-types`, `dashboards`, `status`, `alerting`,
`payments`) into narrow techniques (`gauge`, `heatmap-status-grid`, `board-per-domain`,
`budget-thresholds`, `quota-wallet`, `degraded-banner`) without source records stating those narrow
claims. r4/r5 then present the resulting supports as direct evidence.

That is incompatible with the campaign rule that later artifacts make no claims beyond the records.
The direction can retain many of the proposed moves as **policy/design choices**, but it cannot present
them as high-support external findings until the crosswalk and descendants are repaired.

## 1. Coverage and method

1. Parsed all **229** corpus records: agentops 48, dashboards 58, dataviz 41, cli 34, craft 48.
2. Checked all r5 source citations: the 54 real `[src:*]` tags used before the appendix resolve to an
   appendix row whose 16-character SHA prefix exists in a corpus record. All r5 `skill`, `catalog`,
   and `taxonomy` references resolve too. The only non-resolving syntax was the documentation legend
   placeholder, not a claim citation.
3. Checked all **49 catalog items** and **9 skill records**. Every emitted SHA/family/URI triple
   resolves to the corpus. Every copied taxonomy-node support/family value matches `taxonomy.json`.
   Thus the support-copy transport is clean; the source of the defect is the taxonomy's interpretation.
4. Recomputed direct raw-label coverage for disputed nodes, read the stored source text for NN/g
   dashboards, ECharts renderer/ARIA guidance, uPlot, Braintrust evaluation, and Langfuse
   observability/analytics, and compared that text with the downstream claim.
5. Audited r5's r0 disposition tables for coverage. M1–M14 and A1–A12 are all addressed. This pass
   does not re-audit r0's code measurements; it treats r0 as the campaign's accepted measured input.

## 2. Findings

| ID | Severity | Artifact / claim | Evidence | Required disposition |
|---|---|---|---|---|
| E1 | HIGH | Mark-specific supports are inflated: `tech-viz-gauge=25`, `tech-viz-heatmap-status-grid=30`, `tech-viz-virtualized-table=32`; r4 exposes them as `ch-gauge`, `ch-status-grid`, `ch-table`; r5 makes them defaults in §7. | Direct raw labels in all corpus files: `gauge=1` (craft), `heatmap-status-grid=1` (craft), `virtualized-table=3` (craft). r3 obtains the larger values by allocating generic `chart-types`, `status`, `table-view`, `tables`, and unrelated monitor labels to those narrow leaves. `table-view` is not evidence of virtualization. | Recompute direct support per specific mark. Retain generic dashboard/chart evidence at an umbrella node; do not use it as a mark-specific count. Re-evaluate every dependent catalog/skill/r5 default against the repaired threshold. |
| E2 | HIGH | `tech-ia-board-per-domain=55` underwrites r4's claim that it is the “dominant ops IA” and r5's work/money/health/decisions board split. | No corpus record carries raw `board-per-domain`. The support is allocated from generic `dashboards`, `dashboard`, and `dashboard-grid`, which establish dashboard existence, not separation into these operator domains. | Recast the four-board layout as a local **[P] direction** driven by r0 M1–M5 and operator needs, not a dominant external pattern. Remove/recompute the 55 support claim unless direct domain-separation sources are acquired. |
| E3 | HIGH | The money node claims are unsupported: `money-budget-thresholds=19`, `money-quota-wallet=7`; r4 says Stripe + agent-ops sources “treat money as its own domain”; r5 puts provider windows, wallet, leases and budget thresholds on one cited board. | Raw corpus technique labels contain `budget=0`, `quota=0`, `wallet=0`. `money-budget-thresholds` is generic `alerting`/`alerting-rules`; `money-quota-wallet` is mostly generic Stripe `payments` plus one pricing record. Langfuse analytics documents dashboards, metrics and alerts `[src:langfuse-cost]`; it does not establish this room's quota/wallet/lease composition. r0 M1 directly establishes the **local** need. | Retain the money-board move as `[P]` backed by local r0 M1, but remove the external-support count and “sources treat money as its own domain” claim. Do not claim quota/wallet/budget evidence until directly sourced. |
| E4 | HIGH | `tech-trust-degraded-banner=11` and `tech-trust-uncertainty-encoding=3` support r4/r5 requirements to name failing dependencies and display `metered/estimated/unknown`, partiality, confidence, and “unmeasured.” | Raw corpus labels contain `degraded=0`, `uncertainty=0`, `confidence=0`, `partiality=0`, `unmeasured=0`. The degraded node is generic `status`; the uncertainty node is generic eval/chart labels. Langfuse observability supports trace fields (prompt/model/token/latency) `[src:langfuse-obs]`; it does not entail the room's cost-provenance classes or a dependency-naming banner. | Narrow citations to what sources state (trace/provenance and score vocabulary). Mark named dependency banners, M/E/U cost class, and unmeasured/partial encoding as `[P]` local design policies, or cite the repository's own cost/projection contracts explicitly. |
| E5 | MEDIUM | Universal/superlative claims overreach: “every major agent-ops source ships a trace waterfall,” “F1 is unanimous on the eval loop,” “the corpus converges on” OTel, and “ECharts [has] the strongest single-library a11y evidence.” | Direct labels: `trace-waterfall=13/48` F1 records; evaluation raw labels are a subset of F1, not unanimous; `otel-instrumentation=3`, `vendor-agnostic-tracing=1`, `sdk-instrumentation=1`. ECharts has an ARIA guide `[src:echarts-aria]`, but no defined comparative test makes it “strongest.” Braintrust does support datasets/evals/online scoring `[src:braintrust]`; Langfuse supports trace observability `[src:langfuse-obs]`. | Replace `every`, `unanimous`, `converges`, and `strongest` with narrow, cited statements: “these cited sources document…” Define a comparison method before making a superlative. |
| E6 | MEDIUM | r4 skills fail to carry several r4 item caveats; `skill-svg` says the flow-diagram cluster has “2 sources” while its cited taxonomy node reports 4. | Low/single-family catalog items include D3 5 (dataviz only), React kits 10 (dataviz only), progressive disclosure 4 (craft only), timeline 14 (agentops only), icon 4/elevation 3/print-safe SVG 3 (craft only), degraded banner 11 (dashboards only), eval 24 (agentops only). `tech-svg-flow-diagram` reports 4 after crosswalk allocation, while raw `flow-diagram` is 2 and the skill says 2. | Give every synthesized claim the relevant thin/single-family caveat, or remove it from the synthesis. Repair the crosswalk first, then make source-count language use one documented definition (raw-label support vs canonical-cluster support). Define `support_max` in `skills.json`; it is otherwise easy to misread. |
| E7 | MEDIUM | The r5 claim that the source corpus proves a no-build default and rules out React is an absence-to-necessity inference. | r0 §9.8 is the actual no-build **local guardrail**. F2 product stacks are explicitly mostly `unknown`; dataviz/craft show viable vanilla/SVG options (`uPlot`, D3, CSS/SVG) but do not prove React is unnecessary. | Keep “no build” as `[P]` constrained by r0 §9.8. Phrase corpus evidence as viable alternatives, not proof that React is unnecessary. Revisit only via a controlled framework comparison. |
| E8 | LOW | Seven unique catalog citation titles drift from exact corpus titles (10 emitted ref instances), although their SHA/family/URI keys are valid. | Affected SHAs include `c3a34c9200af26ab` (uPlot), `6039c7625aad32c5` (Ratatui), `45d0b1b722e4bd6d` (Rich), `88846b6feced9773` (Smashing type), `b8bc0e988e39ee25` (Smashing SVG), `f0d68d37b1d8bc32` and `1062824463740c2a` (nvitop). | Copy exact corpus titles (or omit titles) when regenerating catalogs. Provenance is still resolvable; this is metadata drift, not a broken citation. |

## 3. Direct-support check behind E1–E4

| Taxonomy node | Reported support | Direct raw label support | Why the reported count is not entailed |
|---|---:|---:|---|
| `tech-viz-gauge` | 25 | `gauge=1` | Process monitors, progress, graphs and generic chart types were allocated to gauges. |
| `tech-viz-heatmap-status-grid` | 30 | `heatmap-status-grid=1` | Generic status and chart-types labels were allocated to a heatmap/status-grid mark. |
| `tech-viz-virtualized-table` | 32 | `virtualized-table=3` | Table/view/table labels were treated as evidence of virtualized implementation. |
| `tech-ia-board-per-domain` | 55 | `board-per-domain=0` | Generic dashboards do not state domain partitioning. |
| `tech-money-budget-thresholds` | 19 | `budget=0` | Generic alerting labels were treated as budget thresholds. |
| `tech-money-quota-wallet` | 7 | `quota=0`, `wallet=0` | Payments/pricing was treated as quota/wallet support. |
| `tech-trust-degraded-banner` | 11 | `degraded=0` | Generic status was treated as a named-dependency degraded banner. |
| `tech-trust-uncertainty-encoding` | 3 | `uncertainty=0`, `unmeasured=0` | Eval/chart labels were treated as explicit uncertainty language. |

This table does **not** say the design moves are wrong. It says the reported empirical support is not
what the source records say. r0 can independently motivate many moves (notably money, projections,
than claimed external convergence.

## 4. Direction claim coverage

| Surface | Entailment result | Notes |
|---|---|---|
| r5 §1 sleek criteria | PARTIAL | The six criteria are valid r1 acceptance/policy criteria. The cited product-hierarchy language (“rank state before chrome”) is more specific than text extraction demonstrates; keep it as direction, not visual measurement. |
| r5 §3 glance/drill-down/alert | PARTIAL | The ON mapping and r0 premises are covered. Claims relying on money, degraded, uncertainty, status-grid, virtualized-table, and timeline support inherit E1–E6. |
| r5 §4 M1–M14 / A1–A12 dispositions | COVERED AS POLICY | All 26 audit findings are explicitly dispositioned. The r0 measurements support the problem statements; proposed moves are policy and must not be labeled as corpus consensus where E1–E4 apply. |
| r5 §5 rejected alternatives | PARTIAL | No-build derives from r0; canvas/SVG tradeoff is directly supported by ECharts `[src:echarts-canvas]`; palette alongside visual navigation is supported by the cited examples. “React unnecessary” and “D3 for every chart” need the E5/E7 narrowing. |
| r5 §6 layout proposition | POLICY, NOT MEASURED | A concrete proposal is permitted in r5. Retain it, but do not treat four domain boards or the attention-strip hierarchy as externally measured prevalence. |
| r5 §7 chart proposition | NOT CLEAN | Gauge, status grid, virtualized table, small-multiple and timeline defaults depend on the inflated/one-family nodes in E1/E5/E6. Direct uPlot support is strong for time-series/data-point performance; it does not prove “hundreds of concurrent live series.” |
| r5 §8 SVG proposition | MOSTLY CLEAN | `viewBox`, `<use>`, SVG text, title/desc, CSS styling, path animation, forced-colors and reduced-motion claims are directly covered by MDN/CSS-Tricks/Smashing/W3C records. Flow-layout support needs the E6 count correction. |
| r5 §9 visual system | PARTIAL | CSS custom properties, `color-mix`, contrast, forced-colors, typography, icon labeling, and reduced motion are directly supported. “Dark-first” and the particular token/elevation composition are design policy; the named Material/Apple density gap remains. |
| r5 §10 no-regression/drift | CLEAN AS R0 DERIVATION | These are r0 measured-code requirements, not web-corpus claims. |

## 5. Clean checks

- `taxonomy.json` input hashes and its five family counts match the corpus.
- Actual r5 source citations, and all r5 catalog/skill/taxonomy ids, resolve. This is a real strength:
  the direction can be repaired without reacquiring its provenance.
- All 49 r4 catalog items and 9 skill records cite resolvable SHA/family/URI triples.
- r4's copied support values match r3. The issue is interpretation in r3, not r4's copying layer.
- Directly read source records do support their narrow statements:
  - ECharts documents a renderer tradeoff: canvas for many elements, SVG for lower memory/zoom
    properties `[src:echarts-canvas]`.
  - uPlot documents Canvas 2D, live streaming, and an explicit 166,650-point benchmark
    `[src:uplot]`.
  - Braintrust documents offline/online evaluation, datasets, scorers and comparison
    `[src:braintrust]`.
  - Langfuse documents structured traces with prompt/model/token/latency/tool fields
    `[src:langfuse-obs]`.
  - WCAG/MDN/W3C directly support contrast, forced-colors, live regions and table/APG semantics
    `[src:wcag-contrast]` `[src:mdn-forced-colors]` `[src:mdn-live-regions]` `[src:w3c-tables]`
    `[src:w3c-apg]`.

## 6. Required disposition order

1. **Blocker:** repair r3's raw-label-to-canonical crosswalk for E1–E4. A broad label can support an
   umbrella catalog but cannot manufacture a specific leaf. Recompute `support`, family counts and
   the thin-leaf threshold from the repaired membership.
2. **Blocker:** regenerate r4 catalogs/skills and r5 direction from the repaired taxonomy. Drop leaves
   below the bar; carry source-family caveats into every synthesized skill that retains a thin or
   one-family claim.
3. **Required:** distinguish external observation `[X]`, measured local r0 fact `[M]`, and direction
   policy `[P]` in r5. This is especially necessary for money grouping, thresholding, M/E/U
   provenance classes, named degraded banners, board composition, and external-alert rejection.
4. **Required:** replace universal/superlative wording with source-bounded wording and define any
   reported support metric (`support_max`, direct/raw support, canonical/cluster support).
5. **Hygiene:** repair the seven exact-title drifts in `catalogs.json` during regeneration.

No new source acquisition or portal implementation is required to close these findings; this is a
derivation/citation repair inside the existing r3→r5 artifact chain.
