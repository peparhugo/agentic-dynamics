---
status: accepted
---

# Control Room repair — entailment / support re-check (campaign `control_room_research_repair`, p3)

**Reviewer:** `openai/gpt-5.6-terra`  
**Date:** 2026-09-11  
**Scope:** the p0 repaired taxonomy, catalogs, and skills; the p1 run-object direction; and the p2
one-resting-screen IA. This is an adversarial read-only review: it records defects and required
dispositions; it does not repair reviewed artifacts.

## Verdict

**NOT CLEAN — remediation required before the repaired artifacts can be called zero-promotion.**

The repair fixed the original, high-profile promotions (`board-per-domain`, `quota-wallet`,
`budget-thresholds`, `degraded-banner`, etc.), and the artifact transport is strong: all stored
references resolve and every persisted support value equals the current crosswalk's record union.
That is an **arithmetic pass**, not the promised semantic pass.

The repaired crosswalk still assigns adjacent but non-equivalent labels to narrow nodes: for example,
`fuzzy-find`/`fuzzy-filter`/`aliases` increase `tech-ia-command-palette`; process/resource monitors
and terminal recordings increase `tech-viz-log-stream`; spinner/progress increase
`tech-int-skeleton-loading`; generic color-scale labels increase
`tech-vis-colorblind-safe-status`. Those source records do not state the promoted technique under
the repair's own rule. The direction then presents several of those supports as `[X]` grounding.

Two non-taxonomy correctness defects also need disposition: p1 calls an invented lifecycle state
machine `[M]` and aligned to the control-db graph when its state names do not exist; p2 promises all
seven desktop glance answers in the default viewport but permits a narrow-desktop fallback that puts
the required rail below the fold. Both are contract problems, not styling disagreements.

## 1. Method

1. Parsed all **229** corpus records: agentops 48, dashboards 58, dataviz 41, cli 34, craft 48.
2. Recomputed each non-group crosswalk leaf's `support` as the cardinality of the distinct corpus
   records whose `techniques` set intersects that leaf's persisted `taxonomy.crosswalk` labels, and
   recomputed `support_by_family` from the same records.
3. Rebuilt the taxonomy in memory using `build_taxonomy.py` and compared `corpus_totals`,
   `crosswalk`, `repair`, `split_merge`, and all nodes byte-for-structure with the committed JSON.
4. Read the counterexample records' facet labels, titles, notes, and stored source text where needed;
   the review treats the corpus record's own `techniques` field as the p0 method says it does.
5. Resolved every taxonomy example, catalog/skill source reference, direction appendix source, and
   direction catalog/taxonomy reference against the corpus/taxonomy.
6. Checked the structured `[P]` records for a reason, then read p1/p2's prose classifications against
   the actual control-db vocabulary and the stated no-interaction contract.

## 2. Findings

| ID | Severity | Artifact / claim | Evidence | Required disposition |
|---|---|---|---|---|
| E1 | **BLOCKER** | `taxonomy.json` calls itself direct raw-label support with zero label promotion; p1 §4 uses the resulting node supports as `[X]` grounding. | The support arithmetic is correct **for its crosswalk**, but the crosswalk still promotes labels into techniques those records do not state. Table §3 gives direct counterexamples and lower bounds: command palette 11→8 literal-label records; tab bar 8→5; density ladder 8→3; log stream 32→25; skeleton loading 5→2; colorblind-safe status 12→7; prompt registry 3→0 literal labels; release feed 26→17. | Rebuild the crosswalk from record-level direct evidence/quoted spans. Rename the node to an honest umbrella where the broader pattern is retained, or keep the narrow node at only its literal/direct support. Regenerate catalogs, skills, p1 and p2; every move losing backing becomes `[P]` with a reason. |
| E2 | **HIGH** | `docs/research/control_room_direction.md:94-110` says its lifecycle is aligned to the enforced control-db transition graph and labels it `[M]`. | The diagram names `proposed`, `leased`, `awaiting-evidence`, `verified`, `flagged`, `awaiting-decision`, `settled`, `archived`, `superseded`, and `dead-letter`. `RunState` actually defines `queued`, `running`, `awaiting_approval`, `verifying`, `promotable`, `promoting`, `merged`, `projecting`, `published`, `failed`, `cancelled`, `quarantined` (`control_db.py:171-188`); the enforced forward graph is at `:193-208`. The two are not aligned. | Replace the diagram with the actual `RunState` graph, or label the proposed UX abstraction `[P]` and show a total mapping to actual states. Do not call the abstraction measured or use it to imply `safe_actions` exist for invented states. |
| E3 | **MEDIUM** | `docs/research/control_room_ia.md:141-152` promises every `ON-G1..G7` answer is in the default viewport. T1 (`:170-174`) allows R3 to collapse to a ticker and move its full rail beneath the roster. | ON-G4 needs five labelled money numbers; ON-G1 needs worker/projection health; ON-G7 needs grouped composition. §4 assigns all three to R3, but the narrow fallback no longer says the ticker contains all of them. The document's own definition calls below-fold placement a glance failure. AC-12 permits the fallback without checking those answers. | Specify a minimum ticker schema that still answers ON-G1/G4/G7 in the viewport, or explicitly narrow the desktop contract at that breakpoint as p2 already does for mobile. Update AC-12 to check the chosen outcome, not merely that the route did not change. |
| E4 | **MEDIUM** | The p0 repair review promises each raw label crosses to "at most one canonical technique leaf" (`docs/reviews/control_room_taxonomy_repair.md:33`), but `taxonomy.crosswalk` overlaps eight labels. | `fuzzy-filter` belongs to both command-palette and sort-filter; `real-time-metrics` to live-follow and metrics; `span-tree`, `traces-spans`, and `tracing` to both causal-lineage and trace-tree; `trace-waterfall`/`waterfall-timeline` to both timeline and trace-tree; `sparkline` to time-series and micro-visual. Some overlap may be defensible, but the documented method is false and the relationship is unqualified double support. | Choose and document one rule: (a) one direct leaf per label, or (b) explicit many-to-many evidence roles with a per-node quotation demonstrating each role. Do not claim a partition while emitting overlaps. E1's re-audit must test this rule. |
| E5 | **MEDIUM** | p1/p2 claim discipline calls internal artifacts `[X]` in several places, and calls prospective UI placement `[M]`. | `[X]` is defined as external observation, but p2 calls r6c IA1/IA9 `[X]` (`control_room_ia.md:147,150`) and the local r1 need `[X]` (`:152`). p1 calls proposed roster fields "shown per roster row" `[M]` while citing an adversary requirement (`control_room_direction.md:108-110`). The underlying packet fields/r0 facts are measured; showing them in a new region is policy. | Make the source class local: r0/runtime facts `[M]`; external exemplars `[X]`; adversary requirements/design placement `[P]` (or the repo's review class where applicable). Split each sentence so measured field availability is not used to label a proposed UI placement `[M]`. |

## 3. The remaining label-promotion counterexamples (E1)

The table uses a **literal-label lower bound**, not a proposed final taxonomy. It counts only the raw
labels that name the node itself or an uncontroversial literal synonym. The reported support can be
retained only after a record-level quotation proves a broader label actually states the node's
technique. It cannot be retained merely because the pattern is adjacent or useful.

| Repaired node | Reported support | Literal/direct lower bound | Non-literal contributors currently counted | Records read / why it fails the rule |
|---|---:|---:|---|---|
| `tech-ia-command-palette` | 11 | 8 (`command-palette`) | `fuzzy-find`, `fuzzy-filter`, `aliases` | fzf `69fcc77a700dd447` is a "command-line fuzzy finder"; Gum `0a4ed3be7e9c30d9` is shell-script UI with a fuzzy filter; k9s `1a478e7877c824fe` supplies aliases. None is a command palette. Rename to command/find or remove the three contributions. |
| `tech-ia-tab-bar` | 8 | 5 (`tabs`, `native-tabs`, `tab-bar`) | `split-panes`, `panes`, `splits`, `multiplexing` | Warp panes, Ghostty split panes, kitty splits, and WezTerm multiplexing are valid terminal navigation evidence, but do not state a tab bar. Rename the node to tab/pane navigation or count only the tab labels. |
| `tech-ia-density-ladder` | 8 | 3 (`density-ladder`) | `density`, `responsive-layout`, `responsive-sizing` | Responsive layout/sizing states adaptation, not a persisted density ladder. The direct density-ladder sources may stay; the node needs a quote/rule for any additional record. |
| `tech-viz-log-stream` | 32 | 25 (`logs`, `streaming`, `real-time-streaming`, `request-log`) | `process-monitor`, `resource-monitor`, `session-recording` | nvitop `f0d68d37b1d8bc32` is a GPU process viewer; btop/bottom are resource monitors; asciinema `98f6c32519cf6e4c` records terminal sessions. Those are not log streams. Rename the umbrella or stop counting them for a log-stream claim. |
| `tech-int-skeleton-loading` | 5 | 2 (`skeleton-loading`) | `spinner`, `progress` | Bubble Tea Bubbles `50530f8a2dd9dc7a` supplies a spinner; Rich/gdu supply progress. NN/g explicitly distinguishes skeletons from progress indicators. They cannot raise skeleton-loading support. |
| `tech-vis-colorblind-safe-status` | 12 | 7 (`colorblind-safe-status`, `colorblind-safe`) | sequential/diverging/categorical colors, color perception/scales | D3 scale chromatic and ColorBrewer state palette/scale techniques, not that a status encoding is colorblind safe. Retain a broader color-encoding node or require explicit accessibility evidence. |
| `tech-ops-prompt-registry` | 3 | 0 exact `prompt-registry` labels | `prompt-versioning`, `prompt-deployment`, `prompt-hub` | LangSmith's `195faedbb34b0887` text supports a Prompt & Context Hub that stores/versions prompts; Langfuse supports prompt management. Those may justify a **prompt-management/hub** node, but do not satisfy the taxonomy's own raw-label rule for a node named `prompt-registry`. Rename with quotes or downgrade. |
| `tech-ops-release-feed` | 26 | 17 (`changelog`, `deployments`) | `provisioning`, `serverless-containers`, `webhooks` | Grafana provisioning, Modal containers, and Stripe webhooks are not release-feed records. They may support deployment infrastructure, not a feed. |

Other nodes need the same record-level review before a clean verdict: `tech-vis-design-tokens`
counts themes/palettes as tokens; `tech-vis-type-scale` counts ligatures as a scale;
`tech-trust-alerting` counts monitors; `tech-ops-observability` counts gateway proxy/MCP; and
`tech-ops-issue-tracking` counts error-code reference. This review did not certify them by
association.

## 4. Clean checks

These checks are real strengths, but do not cure E1–E5.

| Check | Result |
|---|---|
| Corpus integrity | PASS — all 229 records and all five input SHA256s match `taxonomy.json.inputs`. |
| Persisted support arithmetic | PASS — all 57 non-group crosswalk leaves reproduce exact `support` and `support_by_family`; the in-memory builder's `corpus_totals`, `crosswalk`, `repair`, `split_merge`, and nodes equal the committed artifact. |
| Prior inflated nodes | PASS — the seven p0-deleted nodes are absent from `nodes` and recorded in `taxonomy.repair.deleted_nodes`. |
| Taxonomy example references | PASS — 922 emitted example references resolve exactly by SHA, family, URI, and title. |
| Catalog references | PASS — 276 references resolve exactly; all 70 cited taxonomy-node ids exist. |
| Skill references | PASS — 72 references resolve exactly; all 62 cited taxonomy-node ids exist. |
| Direction citations | PASS — 76 appendix corpus rows and 25 `[cat:catalog/item]` references resolve. |
| Structured `[P]` catalog records | PASS — 10/10 have `evidence_class: "[P]"` and a non-empty one-line `policy_reason`. |
| Structured skill policies | PASS — 7 skills carry policies; every policy entry has a reason. |
| No source-link breakage in p2 | PASS — p2 contains no corpus/catalog citation token that fails resolution; its local r0/r1/r6c paths exist. |

## 5. Required disposition order

1. **Blocker: repair E1 semantically, not only arithmetically.** Persist per-node supporting record
   ids plus the exact source span or an explicit raw-label equivalence rationale. The builder must
   reject a label-to-node mapping when the record does not state that node's technique. Recompute
   supports, family counts, thinness, catalogs, skills, p1, and p2.
2. **Repair E4 in the same change.** Either enforce the documented one-leaf rule or document/test
   explicit many-to-many roles. The current method cannot claim both a partition and overlap.
3. **Repair p1 lifecycle vocabulary (E2).** Use the actual `RunState` graph or label the desired UX
   lifecycle `[P]` with a mapping. Only the database graph may underwrite `safe_actions`.
4. **Repair p2 breakpoint behavior (E3).** The default-viewport promise needs a complete minimum
   rail schema, not an unspecified ticker. Make the desktop and mobile scope explicit in AC-1/2/12.
5. **Normalize claim classes (E5).** The reworked prose must distinguish facts measured in the
   repository from external observations and future UI policy. Do not use `[X]` for r1/r6c or `[M]`
   for a new placement.
6. **Then rerun this adversary.** A clean pass requires a source-by-source support table that covers
   every surviving leaf, not only the original eight disputed r3 nodes.

## 6. Residual risk

The live-run direction is stronger than r5's board grammar and the IA has a clear desktop mapping,
but those design gains should not be published as corpus-backed evidence until E1 is fixed. The
correct immediate status is: **reference integrity clean; support entailment not yet clean; p1/p2
design policy useful but needs the stated claim-class and contract repairs.**
