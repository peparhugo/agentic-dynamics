---
status: accepted
---

# Control Room repair2 -- quoted-evidence entailment verdict

**Reviewer:** `openai/gpt-5.6-terra`
**Date:** 2026-09-11
**Scope:** `experiments/research/control_room/{taxonomy,catalogs,skills}.json`, their
stored `sources/<sha>.json` records, and the deterministic rebuilders
`build_taxonomy.py` and `reduce_knowledge.py`.

## Verdict: PASS

The three repair2 pass conditions are met.

| Pass condition | Result | Verification |
|---|---|---|
| Every positive support in taxonomy, catalogs, and skills has stored `evidence_quotes`. | PASS | Recursive audit: 44 taxonomy leaves, 89 catalog blocks, and 42 skill blocks have a quote array whose distinct SHA count equals their reported `support` or `support_max`. Structural taxonomy totals are now `record_count`, not source support. |
| Every stored quote is an exact stored-source sentence and states the declared technique. | PASS | Each active taxonomy quote is an exact substring of `sources/<sha>.json` and matches that leaf's sentence-level technique pattern. The generator rejects titles, excerpts, navigation labels, and whole-page-only matches. |
| No `PROMOTION` or `ABSENT` node survives. | PASS | All 44 current technique leaves have `semantic_verdict: "PASS"`. Below-bar but direct evidence is a thin PASS leaf. Unsupported candidates are excluded from `nodes` and downstream backing references. |

## Findings

| ID | Result | Finding | Disposition |
|---|---|---|---|
| Q1 | PASS | The prior source-wide pattern gate could select an unrelated sentence. | The count gate now calls the same sentence selector used to store the quote. |
| Q2 | PASS | Generic lexical matches admitted headings, navigation, and substring collisions. | Candidate quotes require sentence punctuation; patterns use bounded, technique-specific terms. |
| Q3 | PASS | Some structural annotation totals looked like evidence support without a source proof. | Structural nodes expose `record_count`; only technique leaves expose `support`. |
| Q4 | PASS | Catalogs and skills copied support numbers but did not carry their own quote proofs. | Each positive support block now embeds the full quote witness from its strongest backing leaf. |
| Q5 | PASS | Seven prior false positives, including `request logged`, `predictable`, navigation `Log`, and print-safe SVG, did not state their claimed techniques. | The affected leaves are excluded unless a direct, sentence-level proof survives. |
| Q6 | PASS | Re-running the reducer could compound local-policy prose or `[P]` labels. | Generated policy suffixes and markers are normalized before regeneration; repeated rebuilds are byte-stable. |

## Independent 15-node sample

The following nodes were independently checked by reading the cited stored source text.
Every quoted sentence below is verbatim from `sources/<sha>.json` and states the named technique.

| Node | SHA | Verified stored sentence |
|---|---|---|
| `tech-ia-widget-catalog` | `6039c7625aad32c5` | “Widget Examples - a collection of examples that demonstrate how to use the library.” |
| `tech-ia-command-palette` | `7417e982f156d980` | “Create a service by clicking the New button in the top right corner of your project canvas, or by typing new service from the command palette, accessible via CMD + K (Mac) or Ctrl + K (Windows).” |
| `tech-viz-chart-types` | `caa87df6c6cfc387` | “Apache ECharts provides more than 20 chart types available out of the box, along with a dozen components, and each of them can be arbitrarily combined to use.” |
| `tech-viz-chart-grammar` | `3c3c373dbb4ae6a0` | “It has a concise, memorable, yet expressive API, featuring scales and layered marks in the grammar of graphics style.” |
| `tech-viz-time-series-marks` | `c3a34c9200af26ab` | “uPlot is a fast, memory-efficient Canvas 2D-based chart for plotting time series, lines, areas, ohlc & bars.” |
| `tech-viz-data-table` | `7bb44646100f45ed` | “A nonmodal side panel allows for the full display (and editing) of a single record while still allowing the user to view the rest of the table’s data.” |
| `tech-viz-waterfall-timeline` | `f8ca1f22853b1f87` | “Most powerful of all is the Session Waterfall.” |
| `tech-int-aria-live` | `11655ccb46931ebe` | “aria-live: The aria-live=POLITENESS_SETTING is used to set the priority with which screen reader should treat updates to live regions - the possible settings are: off, polite or assertive.” |
| `tech-int-sort-filter` | `6c432f3f48666914` | “The folder filter is saved to the URL as a ?folder= query parameter, so filtered views persist across page reloads and can be shared with teammates.” |
| `tech-vis-design-tokens` | `17c5c86f3c683e8c` | “This allows you to share config and color tokens between charts.” |
| `tech-trust-alerting` | `d28ea3629b46d1b6` | “Grafana Alerting allows you to learn about problems in your systems moments after they occur.” |
| `tech-money-billing` | `11e34aac5147fea3` | “We announced AI-powered payments, our biggest-ever upgrades to Stripe Connect, new support for usage-based billing, increased interoperability, and a lot more.” |
| `tech-ops-eval-loop` | `8159075eb65dcf26` | “DeepEval is the eval harness for vibe coding agents -- closing the build -> eval -> patch loop your coding agent has been missing.” |
| `tech-ops-metrics` | `34d09509900f2a2b` | “See quality, cost, and latency metrics in the dashboard to monitor your LLM application.” |
| `thin-viz-gauge` | `b665ad15d558dbd6` | “This Klipfolio dashboard uses a radial gauge (1) to show the value of a particular metric within a range.” |

## Previously flagged checks

| Prior flag | Result |
|---|---|
| `tech-ia-board-per-domain` | Excluded; no active node or downstream evidence backing. The domain split remains local `[P]` policy. |
| `tech-money-budget-thresholds` | Excluded; no direct threshold sentence was found. |
| `tech-trust-uncertainty-encoding` | Excluded; no direct uncertainty/partiality sentence was found. |
| `tech-svg-print-safe-svg` | Excluded; the prior “Your blueprint for a better internet.” sentence no longer qualifies. |
| `tech-viz-log-stream` | Excluded; “request logged” does not establish a log-stream surface. |
| `tech-viz-heatmap` and `tech-ia-density-ladder` | Excluded; no sentence-level direct proof survived the tightened patterns. |

## Regression Gate

`tests/test_control_room_research_evidence.py` now enforces the evidence cardinality,
verbatim source text, technique-pattern, PASS-verdict, and excluded-node invariants. The
rebuilders were run repeatedly after this audit; `catalogs.json` and `skills.json` remained
byte-identical on the final repeat.
