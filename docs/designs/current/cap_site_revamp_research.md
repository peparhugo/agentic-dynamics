---
status: accepted
---
# CAP Site Revamp: Research, Editorial, and Visual Specification

**Status:** accepted research gate for the public-site rebuild.
**Scope:** research and editorial audit only. No production implementation is authorized by this document.
**Evidence freeze:** `apps/website/data.js`, generated 2026-08-26 17:27 UTC; manifest commit `21b64112`.
**Policy:** [P] Every future site claim must have an evidence class, source field or artifact, corpus/scope, and date. A field that is null, absent, historical, or untagged is not silently turned into a number.

## 1. Decision Record

### 1.1 The site to build

The public site is a research publication for an emerging field, not a product funnel. Its job is to let a reader understand a named question, inspect the instrument, encounter bounded evidence, distinguish measured observations from computed results and models, and see the next open experiments. It must make the operator credible by making the evidence inspectable, not by asserting expertise.

**Positioning statement -- VERBATIM, binding for later phases**

> Agentic Dynamics is the empirical study of how agents behave as tasks, environments, workflows, and time change. It begins with a practical question: what does an agentic outcome cost once verification, recovery, inherited context, and downstream consequences are included? The field's method is to instrument real agent work, derive named information from the resulting record, test policy choices as controlled arms, and repeat only where uncertainty remains. This site publishes the instrument, the corpus boundary, the verdicts, the nulls, and the open problems. It does not sell certainty, a routing product, or a universal best practice.

This statement is a [P] editorial decision, learned from Santa Fe Institute's field-facing research IA and Distill's research-publication posture. Sources: `https://www.santafe.edu/research/overview`; `https://distill.pub/2020/communicating-with-interactive-articles/`.

### 1.2 What field establishment means here

| Required field signal | Site expression | Basis |
|---|---|---|
| Named question | The Question page asks how changing agent-environment conditions alter accepted outcomes, verification, recovery, cost, and downstream loss. | [P], learned from SFI's program-first research navigation and Distill's one-idea articles. |
| Method | The Instrument page exposes cells, factor assignments, ledger events, independent tests, measurement rules, and policy arms. | [M]/[C] platform architecture; `ARCHITECTURE.md`, `apps/website/methodology.html`. |
| Instrument | A hand-drawn cycle names the ordering: instrument -> derive -> write policy -> grid -> campaign. | [P], required by the repository's load-bearing measurement rule. |
| Evidence | The Evidence page leads with corpus receipt, metric definition, n/coverage, result, limitation, and artifact link. | [P], learned from arXiv's versioned artifacts and FT/NYT editorial charts. |
| Open problems | A dedicated final section enumerates untriggered escalation, missing typed checkpoints, unmeasured LSP, underpowered calibration, and model/domain limits. | [M]/[C] verdicts below; [P] placement. |
| Limits | Every chart and card shows provenance and scope in the first view; no important limitation is hidden in a tooltip. | [P], learned from Distill details-on-demand guidance and arXiv version/citation discipline. |
| Reproducibility | Each finding has stable artifact path, generation date, corpus identifier, and GitHub/source link. | [P], learned from Observable's inspect/fork posture and arXiv's versioned record. |

### 1.3 Credibility rules

1. [P] Render evidence classes as a compact, repeated key: `[M] measured`, `[C] computed`, `[H] heuristic`, `[X] external`, `[P] policy/proposal`. Use the existing taxonomy in `data.js:4-7`; add `[P]` for decisions and proposals rather than presenting them as observations.
2. [P] A measured value needs its denominator, scope, and capture basis at the point of interpretation. A computed value needs its formula/inputs. A modeled value needs assumptions and an explicit non-forecast label.
3. [P] The first visible unit on evidence pages is a finding with its receipt, not a dashboard KPI. This transfers Distill's answer-first plus details-on-demand pattern and FT/NYT chart restraint.
4. [P] Null is a result. Render `not measured`, `untriggered`, `no canonical lab output`, or `underpowered` as named states; never render `0`, `--` without explanation, or an old fallback.
5. [P] The site must never imply that an adaptive policy has been armed merely because `cap_2b` passed a non-inferiority decision. The verdict only authorizes design review.

### 1.4 Explicit anti-SaaS exclusions

The rebuilt public navigation and copy must not contain pricing, tiers, package comparisons, demo booking, "get started", conversion calculators, customer-logo walls, testimonial quotes, "why us" feature grids, implementation timelines sold as an offer, "accelerator" branding, or claims that the operator will tune an enterprise. These patterns make a research field read as a SaaS pitch. This is [P], learned negatively from the current `accelerator.html` and positively from SFI, arXiv, and academic-lab research structures.

Permitted calls to action are: read the evidence, inspect the method, open a source artifact, reproduce a run, read a verdict, and examine an open question.

## 2. Evidence and Editorial Ledger

### 2.1 Source hierarchy and publication rule

| Rank | Authority | Permitted use |
|---|---|---|
| 1 | Immutable campaign score/ledger artifact and independent test result | A specific campaign verdict or measured value. |
| 2 | Current `apps/website/data.js` and `experiments/data_manifest.json` | Current public corpus claims and data-bound charts. |
| 3 | Current accepted verdict/design document that points to rank 1 | Explanation, scope, authorization boundary. |
| 4 | Historical `_results_summary.json` and literal historical page prose | Historical context only, visibly dated and never merged into current corpus counts. |
| 5 | External publication/source | `[X]` contextual claim only, with direct link and date. |
| 6 | Editorial or operating decision | `[P]`, labeled proposal/decision rather than evidence. |

The current manifest explicitly marks `_results_summary.json` historical (`experiments/data_manifest.json:23-28`). It cannot source a current site claim. The build's known limitations are also binding: 116/227 historical sessions use heuristic correctness; 17 operator-model combinations have per-cell n below 5; Rules 6-9 are modeled; historical model counts are imbalanced (`experiments/data_manifest.json:36-40`).

### 2.2 `data.js` field and provenance audit

`data.js` is the sole generated website data file (`apps/website/CONTEXT.md:41-45`). The following inventory is complete at its top-level contract. Any later component must consume a listed field through a source adapter, not transcribe it into HTML.

| Object | Fields / role | Evidence class or audit finding | Rewrite treatment |
|---|---|---|---|
| `_meta` | `generated_at`, `provenance_note` | [P] metadata; classes are defined at `data.js:4-7` | Show generation date in a site-wide evidence drawer. |
| `summary` | worktrees, sessions, reports, cost, architectures, variants, story counts, configs, registry counts/tombstones | Per-field `_provenance` at `data.js:30-51`: M except story counts/cost fields and eligibility/used counts C | Approved current-corpus receipt only. |
| `resolution_report` | expected/resolved/missing/unreadable/ambiguous/duplicate/waivers | No provenance object | Do not display until generator adds field-level class; it is an integrity diagnostic, not a headline. |
| `publication_contract` | identities, policy and normalization versions, generator identity | No provenance object | Use as an artifact receipt, not narrative copy. |
| `public_statistics` | session/story/cost, providers, configs/specs, operators, labs | Per-field `_provenance` at `data.js:87-102` | Approved for a compact corpus/method receipt. |
| `models` | seven current story-model rows: cells, costs, cache, tests, tokens, test execution, energy, strategy counts | Raw rows do **not** carry per-field `_provenance`; generator must add it before a claim badge can be automatic | Use only through explicitly mapped evidence adapters that label observed values [M] and derived averages [C], or add generator tags first. |
| `perturbation_models` | historical single-session model rows | Individual `_provenance` objects at `data.js:514,676,838,997,1159,1321` | Historical precursor only, never combined with current story model data. |
| `charts` | chart-ready series | Derived display payload | Replace Chart.js with D3/SVG only when the source field/class is passed through. |
| `calculator` | model costs, assumptions, WOC ratio | Mixed operating/model inputs | Retire the sales-like calculator; preserve any transparent model as a labeled `[C]` explorable only. |
| `derived` | cost gap, total provider costs, pass rate, tests | `_provenance` at `data.js:1504-1515` | Approved only with formula and model set. Current cost gap is 22x [C]. |
| `operator_comparison`, `perturbation_class_breakdown`, `energy_ranking`, `strategy_distribution`, `routing` | historical analysis series and strategy/routing projections | Mixed historical, heuristic, and policy content | Do not headline. Publish only as archived evidence with original scope/class. |
| `correctness_escape_quadrants`, `sonar` | empty/diagnostic surfaces | Missing current lab data | Render as absent measurement, not zero. |
| `design_parameters` | thresholds and assumptions | `provenance: "design"` at `data.js:3687-3711` | Convert to `[P]` proposal/assumption cards. |
| `external_sources` | energy/literature inputs | [X] at `data.js:3717-3750` | Keep as clearly external context, never causal support for a corpus finding. |
| `stories`, `reviews`, `analysis`, `labs` | raw current records and analysis output | stories carry a measured-source note at `data.js:3755`; `labs` is `{}` at `4719` | Preserve data access; all missing lab panels must say "no canonical output". |

**Binding data defect:** current static page fallbacks and `app.js` can display a stale literal when an underlying value is null or an object is absent. `app.js:65-102` maps only named statistics; its `MODEL_RESOLUTION` is a presentation choice, not a measurement. Later implementation must remove competing static numeric fallbacks for live statistics and must not infer a tag from a model name.

### 2.3 Current corpus receipt -- approved numbers

| Claim/value | Class | Exact source field / artifact | Required wording |
|---|---|---|---|
| 1,067 story sessions | [M] | `data.js.summary.sessions_total`; `public_statistics.story_sessions` | "1,067 captured story sessions in the current build." |
| 215 stories; 150 unique cells + 65 reruns | [C] | `summary.stories_total`, `.stories_unique`, `.stories_re_runs` | State all three quantities together; do not call 215 "unique". |
| $309.1685 total / $309.17 displayed | [M] raw total; [C] story-total display aggregate | `summary.total_cost`, `.story_total_cost` | State exact basis: summed captured story costs; rounded display. |
| 7 variants, 3 providers, 35 configs | [M] | `summary.variants`, `.configs`; `public_statistics.providers` | Corpus/method receipt, not capability ranking. |
| Registry: 215 current story rows, 215 resolved payloads, 0 unresolved | [M] | `summary.registry_current_records`, `.resolved_measurement_payloads`, `.unresolved_waivered` | Preserve distinct registry/resolution fields. |
| 64 clean findings; 77 contaminated and 10 no-measurement tombstones; 87 total | [M] | `summary.canonical_findings`, tombstone fields | Explain that tombstones are exclusions/retractions, not missing successes. |
| Compact registry: 12,152 entities, 12,065 current, 87 tombstoned; 302 story, 64 finding | [M] | `experiments/data_manifest.json` registry compaction, audited 2026-08-26 | Use only in an artifact/registry page, never beside the 215 story-row receipt without label. |
| Append-only index: 33,771 physical rows | [M] | `experiments/results/registry_index.jsonl`, audited 2026-08-26 | Registry implementation detail; no home-page use. |
| Cost gap: 22x | [C] | `data.js.derived.cost_gap = 1.630840 / .074461 = 21.9x` | "22x observed average-cost spread in this current model set; not matched-task causal evidence." |

### 2.4 Verdict ledger -- decisions, calibration, and nulls

| Claim/value | Class | Source | Mandatory qualification |
|---|---|---|---|
| `cap_2b`: NON-INFERIOR | [C] decision rule over [M] outcomes | `docs/designs/current/cap_2b.md:29-85`; score JSON `cap_2b_score_20260826T160018Z.json` | Randomized pilot, DeepSeek v4 Pro; n=9 per arm, n=6 defect-bearing; descriptive decision rule only. |
| Static: $0.080062 total, CPVO $0.013344, 6/9 verified | [M] cost/outcome, [C] CPVO/rate/CI | `cap_2b.md:31-41` | Must show arm and n. |
| Adaptive: $0.094364 total, CPVO $0.010485, 9/9 verified | [M] cost/outcome, [C] CPVO/rate/CI | `cap_2b.md:31-41` | Must show arm and n. |
| CPVO ratio 0.7857, 95% CI [0.6842, 0.9105], margin <=1.10; success gap -0.3333, margin <=.05 | [C] | `cap_2b.md:58-85` | The result authorizes **design review only**, not control activation (`:89-96`). |
| Measured escalation E_x: 11.4671 Sol; 12.5134 Sonnet | [C] ratios of [M] costs | escalation score `:9-38` | n=1 per escalation model; descriptive, no CI. Include numerator and denominator. |
| Baseline $.008949; fixes $.102619 / $.111982; swings $.092218 / $.100632 | [M] cost inputs, [C] losses | escalation score `:44-70` | Measured values replace neither sourced 3.1 nor 28 globally; state scope. |
| Calibration: 0/3 -> 2/3 | [C] rate over [M] outcomes | `cap_2a_rerun2.md:37-44,61-67,69-81` | 2/3=.6667, Wilson [0.2077,.9385], n=3; descriptive, not statistical clearance. |
| Randomization after calibration | [P] preregistered procedure | `cap_2b_preregistration.md:149-166`; `cap_2b.md:4-12` | State 3 static + 3 adaptive in each clean/critical/style block, not a general claim of policy superiority. |
| Escalate arm untriggered | [M] outcome state | `cap_session_routing_prospective.md:92-108,128-139` | All six escalate cells passed first attempt; $0.005946 is no-escalation-needed, not a premium estimate. |
| EFFICIENT archetype empty | [H] threshold-specific historical display result | `evidence.html:199-219`; soundness audit `experiments/reviews/claude_soundness_audit.md:165-168` | Do not reuse as a current/universal null. Retired summary says 44 efficient; show the threshold dependency if archived. |
| No current LSP measurement | [M] absence/coverage | `data.js.analysis.*.lsp_*` as `{value:null,n_available:0,coverage:0}` | Publish as "not measured: LSP unavailable", never "0 errors". |

### 2.5 Historical and personal narrative ledger

| Claim/value | Class | Source | Rewrite disposition |
|---|---|---|---|
| $20 API key; Rome-Naples train; near-$700 monthly subscriptions | [H] first-person origin record | `apps/website/story.html:51-64`; workflow calls it relational spine | Keep as first-person attributed origin. Do not badge as telemetry or imply a receipt. |
| 347 instrumented/total sessions | [H] historical snapshot | `story.html:66-70,87-91`; rebrand plan `docs/agentic_dynamics_rebrand_plan.md:287-292` | Keep only with "historical snapshot" label or remove from stats. No data.js field was found. |
| 772 sessions / 156 stories / $219.51 | [M] prior live-story snapshot | `docs/archive/HANDOFF_2026-08-17.md:54-65` | Not rendered as current. Mention only in a data-version history. |
| 227 historical runs, 224 reports, 201 Grit denominator, 8 models, 10 operators | mixed [M]/[C]/[H] historical precursor | `evidence.html:464-499`; retired `_results_summary.json` | Archive as precursor with its own receipt; never add to 1,067 current sessions. |
| 249 historical sessions, 34 configs, 7 signals, 4 archetypes | historical literals, mixed provenance | `methodology.html:44-60` | Revalidate against a source artifact before publication; current page has inconsistent 227/249 references. |
| 69x historical cost gap | [C] over historical measured prices | soundness audit `experiments/reviews/claude_soundness_audit.md:39-44` | Archived only; no matched-task causal interpretation. |
| 3 models / 347 / $12.73 / 224 reports / 2,000+ / 911 reviews | untagged narrative/literal snapshots | `story.html:66-148` | Retire from global stats; keep only as dated origin-story context after source reconciliation. |

### 2.6 Every numeric claim currently visible -- page ledger

This is the editorial control list. Semicolon-separated values in one cell are a single contiguous page claim and must be treated together; no later phase may cherry-pick a number from an unapproved group.

| Page | Current numbers/number groups | Class/source status | Rewrite action |
|---|---|---|---|
| Home | 1,067; 7; 215; $309.17 | current receipt: M/M/C/C from `summary` | Keep with receipt. |
| Home | five sessions; 215 stories; 3 codebases; 2 tiers; 7 models | current design/corpus mix; 3/2 literal | Rebind all to generated data or simplify to method description. |
| Home | $.16 -> $.34; 18.7K -> 34.9K; ~2x; $0.07/$3.75; 47K; 98%; 6.3K; 86%/97%; 1.5%/2.5%; 7,9,13,34,34,117,122 tests | literal or absent current `labs`; some values drift from model rows | Remove until canonical labs emit. Do not leave chart-like prose with no current source. |
| Evidence | 215,150,65,7,1,067,$309.1685/$309.17; 215/215/0/64/77/10/87 | current receipt, source table 2.3 | Keep; make tag and date visible. |
| Evidence | model table $.07/33.5/.66/96.4/46.6K through $4.58/122.1/.65/73.1/14.3K; 41x,2.9x,10x,-.23,19/31,23/31 | model row fields lack individual tags; literals may disagree with data.js current averages | Regenerate from tagged model adapter or remove. Never hand-type. |
| Evidence | 349 commit reviews,72 story reviews,322 issues; review table 0.92/.86/.79/80/0 through 0.88/.74/.72/70/12 | historical/current review aggregate not attached to source tag in page | Rebind to `reviews` data with n and review-model disclosure. |
| Evidence | archetype counts and correctness/quality/escape values; EFFICIENT empty | heuristic/historical; LSP is null | Archive or qualify; replace LSP zero-like display with absent measurement. |
| Evidence | five-session $.16 -> $.34 and 2x; Grit figures/strength/classes | `labs:{}` makes current panels unavailable | Keep placeholders only as explicit no-output states; no stale prose. |
| Evidence archive | 227/224/201; 69x; per-model 119/44/18/9/7/7/7/6; 116; 8x10 | historical precursor, with published limitations | Move to a separately dated precursor appendix. |
| Methodology | 249;10;7;4;34;8;227; 18 markers;37 terms;2,215/222;0/.19/.25+;$15M/$1.10M;~11K;25+;112.6%;69x;6-50%;1.80x | historical/mixed and internally inconsistent | Audit each from a non-retired artifact; no current landing-page use. |
| Framework | 1/G cells; 227;$.005-$1.01;72%;8.4-50%;.3-30%; beta=.001; EPM 1.6/2.5;50%;11.5%;28.2x/68.7x; calculator assumptions 10,20,500,$20K,$10K,5K,70%,.015 | architecture plus [P]/[X] scenario inputs | Keep system diagram; delete calculator/enterprise scenario as SaaS/modeling pitch. Model formulas may return as `[C]` explorable with explicit inputs. |
| Framework | .16 -> .34;2.13x;2x/10x;50%/72h;<1%;$.09/$.16/$4.78;7 -> 122;6-50% | stale/historical/literal mix | Retire unless new artifact-backed adapters exist. |
| Accelerator | all numeric enterprise promises: 80%;$.015/$1.01;3-year/N2;20/80;78.6%;4-6 weeks;.90;25-75x;5,000;$1,688; thresholds; tiers; 1.0/8-12/28.2 | SaaS-style `[P]`/modelled or stale claims | Retire page; fold only open hypotheses into Framework/Open Questions. |
| Story | $20;$700;$2.04/$12.73/$4.64;3;347;17x;224;8; 11/8/14%;8.5%;$10/$1.98/$3.96;5.1x/2.5x;78%;35K;97-98%;6K;73/$2.32;7/$.09;2,000+;1,067;215;7;911;700W;220%;6.7-12%;1.8x;2% | origin [H], stale data fallbacks, and [X] context mixed | Preserve $20/Rome attributed story; remove/reconcile every other stat or label historical/external in prose. |
| Glossary | beta=.001;1.6/2.5%;r=.115/WOC=.90;.85/.70;2x/10x;$.14/$3.75;<50/>80%;100% failure; narration 11/8/8/0 | mixed design, external, historical, null runtime values | Rewrite glossary as definitions with source links, no untagged numeric prescriptions. |
| Related Work | July 2026;227;8;3;10;$.02/$1.08;69x;~11K;30%;95%/$.12;17/14/3;WOC .90;50%;11/8/0/8.5%;$.14/$3.75;26.8x;20K/223K;94%/.76;50%/72h;millions daily | external claims and stale historical literals | Merge into Evidence's Related Work note. Retain only direct quoted external claims [X] and clearly scoped instrument comparisons. |

## 3. Learned Visual and Editorial Patterns

### 3.1 Named exemplars studied

| Exemplar | What was studied | Transferable pattern | URL / rights boundary |
|---|---|---|---|
| Distill | Interactive-article theory, multiple representations, details-on-demand, limits of interaction | One idea per primary graphic; prose remains complete without interaction; interaction exposes assumptions or local detail. | `https://distill.pub/2020/communicating-with-interactive-articles/`; study/reference only unless an article repo license is verified. |
| Santa Fe Institute | Research themes/projects/people/results navigation and institutional tone | Present field, program, people, outputs, and research questions as durable objects rather than conversion steps. | `https://www.santafe.edu/research/overview`; all rights reserved, reference only. |
| The Pudding | Sticky scrollytelling process pattern | Use one bounded scroll sequence only where progression is the argument; static conclusion remains visible. | `https://pudding.cool/process/scrollytelling-sticky/`; style learned, not copied. |
| Financial Times Graphics | The Uber Game's system-facing simulation and restraint | If a reader changes an assumption, show state, trade-off, baseline, and caveat; never turn uncertainty into a game. | `https://ig.ft.com/uber-game/`; copyrighted reference only. |
| New York Times Interactive | "You Draw It" prediction/reveal pattern, documented by Distill; direct page access returned 403 | Optional prediction can create attention before reveal, but the actual result cannot be withheld. | `https://www.nytimes.com/interactive/2017/05/07/upshot/college-admissions.html`; reference only. |
| Observable HQ | Notebook/fork/data attachment exploration | Make data/artifacts inspectable and link out to exploration; keep publication surface stable and curated. | `https://observablehq.com/`; Observable Plot/Framework are ISC, but notebooks need their own rights check. |
| Bret Victor, Explorable Explanations | Editable assumptions embedded in an authored explanation | Interaction earns its place only when it builds intuition about a bounded model. | `https://worrydream.com/ExplorableExplanations/`; Tangle code had no verified reuse license, reference only. |
| arXiv | Versioned/citable records and artifact discipline | Every report/finding needs date, version, source artifact, and revision history. | `https://info.arxiv.org/help/license/index.html`; submission licenses vary; metadata CC0. |
| Academic lab sites: Stanford HAI, MIT Media Lab, EMBL-EBI | Research cards, group/project/publication organization, data governance | Type research outputs and show their metadata rather than marketing them. | `https://hai.stanford.edu/research`, `https://www.media.mit.edu/research/`, `https://www.ebi.ac.uk/about/terms-of-use`; reference only. |
| Operator Story page | First-person four-part origin, concrete $20/Rome incident, question broadening | Keep one personal anomaly as relational spine; let it resolve into a falsifiable research question rather than self-promotion. | `apps/website/story.html:51-210`; content rights belong to operator/repository. |

### 3.2 Local example library -- hard gate passed

The following working, standalone examples were fetched from their listed sources and adapted into `apps/website/references/`. Every file contains source URL, license/attribution note, demonstration, and transfer note in its first comment. These files are the implementation mental model; later component PRs must cite the file(s) they adapted in a source comment and in their design note.

| Craft | Local reference files | Source/license | Later use |
|---|---|---|---|
| SVG flow | `svg-marker-flow.html` | MDN marker, CC0 | cycle, escalation flow, plane dependencies |
| SVG evidence state | `svg-pattern-surface.html` | MDN pattern, CC0 | observed vs modeled/unknown surface |
| SVG focus | `svg-filter-focus.html` | MDN filter, CC0 | selected policy/plane without deleting context |
| SVG motion | `svg-animated-status.html` | MDN animate, CC0 | one subtle status trace with reduced-motion fallback |
| D3 scatter | `d3-labeled-scatter.html` | Observable D3 scatterplot, ISC | labeled cost-verification comparison |
| D3 bar | `d3-bar-axes.html` | Observable D3 bar chart, ISC | compact curated comparison |
| D3 line | `d3-line-arc.html` | Observable D3 line chart, ISC | five-session cost arc |
| D3 interactive curve | `d3-interactive-curve.html` | kbroman/d3examples LOD curve, MIT | N-squared assumption explorable |
| Narrative side | `scroll-sticky-side.html` | Scrollama sticky-side, MIT | Story causal sequence |
| Narrative overlay | `scroll-sticky-overlay.html` | Scrollama sticky-overlay, MIT | calibration arc only |
| Cards | `card-details.html` | MDN Card, CC0 | evidence-status 10-rule cards |
| Badge/tooltip | `card-tooltip-badge.html` | USWDS card, public-domain/CC0 terms | source/definition disclosure |
| Editorial type | `type-editorial-measure.html` | Bootstrap typography, MIT | prose measure, lead, pull quote, caption |
| Responsive layout | `type-responsive-grid.html` | MDN column layouts, CC0 | reading column plus evidence receipt |

No reference example is production code or a copy of a copyrighted editorial site. The only production dependencies recommended below are native browser APIs, inline SVG, and pinned D3 if a chart needs axes/scales/interaction.

### 3.3 Visualization architecture decision

| Need | Chosen primitive | Why | Trade-off and source |
|---|---|---|---|
| Conceptual diagrams: cycle, planes, modes, autonomy | Hand-rolled inline SVG | The corpus is small; layout, labels, arrows, accessible `<title>/<desc>`, and print output matter more than a chart API. | More authored coordinates; use `svg-marker-flow.html`, `svg-pattern-surface.html`, `svg-filter-focus.html`. Learned from Distill one-idea diagrams. |
| Static data with <=10 marks | Inline SVG, no library | Lower payload and visual control; direct labels remove legend hunting. | Manual scales; use only for stable, curated data. Learned from FT/NYT restraint. |
| Axes, scatterplot, line/bar series, direct hover detail | D3 v7, imported only on the page that needs it | D3 supplies correct scales/axes/selection updates without a chart framework or canvas opacity. | A dependency and code surface; cite the appropriate `d3-*.html` reference. Do not use Chart.js. |
| Formula/assumption explorable | D3 + native range input, one variable at a time | Reader can see the N-squared consequence while assumptions stay visible. | It is [C], not evidence; cite `d3-interactive-curve.html`, Bret Victor, and Distill. |
| Narrative progression | CSS `position: sticky` plus native `IntersectionObserver` | No scroll framework is necessary for two bounded sequences. | Must have a static/mobile linear reading path; cite both Scrollama-derived references and The Pudding. |
| Rules/cards/receipts | Semantic HTML, CSS Grid, `<details>` | First-view status and source cannot depend on JavaScript; details are optional. | Avoid flip cards, hover-only state, and concealed important text. Cite both card references and Distill. |

This is a [P] decision. It rejects heavy charting frameworks because their abstraction does not pay for a small, curated corpus and would fight the site-specific evidence and diagram language.

## 4. Visual Language and Diagram Inventory

### 4.1 Visual language

| Element | Binding specification | Learned basis |
|---|---|---|
| Typography | Serif body: Source Serif 4 (or a system serif fallback); sans display/UI: IBM Plex Sans (or system sans fallback); mono only for source fields, formulas, and receipt metadata. Body measure 42-46rem; display type is compact, not billboard-like. | `type-editorial-measure.html`, Bootstrap typography hierarchy; Distill's prose-first research voice. |
| Color | Warm paper `#f7f4ed`, ink `#17212b`, measured teal `#287271`, computed/model amber `#9b6a28`, low-contrast graphite for context. Color never denotes a model/provider. | [P] **NOVEL** palette, reason: it visibly removes the existing dark calculator/console aesthetic while reserving color for evidence class; execution pattern from `svg-pattern-surface.html` and FT restraint. |
| Evidence encoding | Badge plus text class; solid fill for measured observation, hatch for model/external scenario, outline/muted state for null/untriggered, never color alone. | `svg-pattern-surface.html`; Distill details-on-demand; arXiv provenance discipline. |
| Motion | Zero ambient decoration. One short path/dot trace may show a process state; all information remains in the static frame; obey `prefers-reduced-motion`. | `svg-animated-status.html`; MDN animate accessibility note; Distill: motion for state/causality, not novelty. |
| Illustration | No stock art, product mockups, gradient blobs, or generic AI imagery. Every hero visual teaches a claim or method. | Distill one-idea graphics; SFI research-facing posture. |
| Cards | Rectangular research slips, not glossy floating SaaS cards. Status/date/source appear above or beside title; expansion reveals method/limitations. | `card-details.html`, `card-tooltip-badge.html`, Stanford HAI research cards. |

### 4.2 Diagram inventory

Every diagram below must be original, adapted from the cited local mechanism rather than copied. Each receives a figure number, terse caption, alt text, evidence legend, source artifact links, and an adjacent prose equivalent.

| Diagram | Sketch-level specification | Evidence / labels | Exemplar and local reference |
|---|---|---|---|
| Instrument cycle | A five-node ring/returning path: Instrument -> Derive -> Write policy -> Grid -> Campaign -> Instrument. Derive is the only path into policy. | Structural [P] / platform method; label that unmeasured requirements block policy. | Distill one-idea diagrams; `svg-marker-flow.html`, `svg-animated-status.html`. |
| N x M problem | Two orthogonal rails: N linked sessions and M measurement angles; their intersection is an evidence surface, with a second analysis pass. | [P] explanatory map; cite current story workflow and no numerical surface claim. | Observable explanatory views; `svg-pattern-surface.html`, `type-responsive-grid.html`. |
| Eight planes | Layered/dependency map of core, experiment, measurement, runtime, adapters, knowledge, control, reporting. Direction arrows obey architecture tiers. | [P] architecture explanation, source `ARCHITECTURE.md`; no performance inference. | SFI program map; `svg-marker-flow.html`, `svg-filter-focus.html`. |
| One engine / two operating modes | Two inputs: fixed assignment -> one cell; factor cross-product -> G cells. They converge at cell -> compile -> jobs -> attempts -> ledger; only grid branches to compare/adapt. | [P] from written compiler/runtime. No business KPI. | Current framework's useful conceptual structure; Distill; `svg-marker-flow.html`. |
| Bounded-autonomy envelope | Human policy boundary outside; inside: declared constraints, execution, independent verification; exits are accept, reject/rework, halt/escalate. | [P] policy/architecture; visually distinguish proposed typed checkpoint capability from not-run state. | FT system simulation restraint; `svg-pattern-surface.html`, `svg-filter-focus.html`. |
| Cost curves | Two panels: immediate observed session arc, if canonical lab data exists; separate cumulative N-squared scenario curve with beta input. | First is [M]/[C] with corpus/n; second is [C] with formula and controls. Never merge lines or imply forecast. | FT/NYT chart restraint; Bret Victor; `d3-line-arc.html`, `d3-interactive-curve.html`. |
| Escalation chain | Cell baseline $.008949 -> rejected outcome / downstream defect -> Sol fix $.102619, E_x=11.4671; Sonnet fix $.111982, E_x=12.5134. Side note says n=1/model. | [M] costs, [C] ratio/loss. Include no causal generalization. | Distill causal graphic; `svg-marker-flow.html`, `svg-pattern-surface.html`. |
| Calibration arc | Three sequential panels: 0/3 initial; 2/3 rerun with [.2077,.9385] Wilson interval; randomized 2b NON-INFERIOR with CPVO ratio [.6842,.9105] and its authorization boundary. | [C] summaries over M outcomes; each has n. End label: design review only. | The Pudding bounded scroll; `scroll-sticky-overlay.html`, `d3-line-arc.html`. |
| Ten rules | Ten expandable cards grouped: instrumented, proposed, decided. Each has status, premise, inputs, evidence class, source/updated date, limitation, next test. | Never call a rule "measured" if only premise/input is measured. Statuses must be computed from verdicts. | Stanford HAI / arXiv cards; `card-details.html`, `card-tooltip-badge.html`. |

## 5. Information Architecture and Editorial Map

### 5.1 Narrative spine

The route is **Story -> Question -> Method -> Evidence -> Framework -> Open Questions**. Home is a concise field index that points to these chapters; it is not an executive dashboard.

| Future page | Purpose | Current material | Required editorial slot for new findings |
|---|---|---|---|
| Home / Field | Field definition, current corpus receipt, one cycle diagram, links to chapters | `index.html` | `home_current_receipt`: generated current corpus, date, manifest link. |
| Story | First-person $20/Rome anomaly -> measurement question -> field | `story.html` | `story_afterword`: dated operator note that links a new finding rather than rewriting origin. |
| Question | Name the problem: accepted outcome under changing conditions, not a price sheet | New extraction from home/story | `question_open_hypotheses`: one generated list of unanswered, testable questions. |
| Method / Instrument | Explain cells, ledger, independent evaluation, perturbation, compiler gate, reproducibility | `methodology.html`, useful framework architecture | `method_method_delta`: what was newly captured, changed, or unavailable. |
| Evidence | Current corpus receipt; 3-5 carefully scoped findings; verdicts; data/artifacts; historical precursor appendix | `evidence.html`, selected related work | `evidence_latest_finding`: one dated finding card wired from data.js/artifact adapter. |
| Framework | Describe how information becomes proposed/decided policy; display bounded-autonomy envelope and rule cards | `framework.html` minus calculator/sales content | `framework_decision_delta`: a status change for a policy/review decision, always linked to verdict. |
| Open Questions | Honest nulls, non-generalization boundary, missing instrumentation, next campaigns | scattered limitations and verdicts | `open_questions_registry`: generated issues with status, requested signal, and campaign link. |
| Glossary / Archive | Stable definitions, historical corpus/data version history, related work citations | `glossary.html`, precursor/evidence archive, `databricks.html` | `archive_release_note`: manifest/version change and retired claims. |

### 5.2 Merge, move, and retire decisions

| Current page | Decision | Reason |
|---|---|---|
| `index.html` | Keep, rebuild as Field index | Current name/field statement and cycle are strong; remove dashboard/card visual language and stale literal findings. |
| `story.html` | Keep, shorten and editorialize | The $20/Rome origin is the relational spine. Separate personal [H] narrative, current [M]/[C] corpus, historical [M] snapshot, and [X] context. |
| `methodology.html` | Keep as Method/Instrument | The core instrument is field-defining. Revalidate/retire historical literals and obsolete paths. |
| `evidence.html` | Keep as primary Evidence chapter | It owns current receipt and should absorb related-work comparison. Remove/archive unavailable lab claims. |
| `framework.html` | Keep as Framework chapter | The compiler/mode and autonomy diagrams are valuable. Remove business calculator, provider playbook, and unvalidated prescriptions. |
| `accelerator.html` | Retire | It is explicitly the SaaS/enterprise-acceleration surface prohibited by this positioning. Migrate only named open hypotheses. |
| `databricks.html` | Merge into Evidence as a small Related Work appendix | Related work is supporting context, not a top-level identity. Preserve external attribution and scope differences. |
| `glossary.html` | Keep, rebuild as definitions plus source anchors | Prevents coined terms from becoming claims by attaching each definition to its method/artifact/status. |

### 5.3 Update mechanism

1. `scripts/build_data.py` remains the only producer of `apps/website/data.js`; static page prose may not compete with its live numbers.
2. Add a small typed editorial adapter that accepts: value, evidence class, source field/artifact, corpus, denominator/coverage, updated date, limitation, and display formatter. This is [P], learned from arXiv citation records and the existing `data-stat` contract.
3. Every page consumes its named editorial slot in table 5.1. A new finding therefore lands in `data.js` plus one page-specific slot, not a scattered set of hand-edited numbers.
4. The archive release note records value/source changes. A changed corpus cannot silently rewrite a prior result; it becomes a new dated receipt.
5. Null/untriggered states are first-class values in the adapter. Rendering a missing current lab output must produce its named absence, not a historical fallback.

## 6. Implementation Gates for Later Phases

1. The 14-file local library in `apps/website/references/` must remain committed before visual implementation begins. This gate is now satisfied.
2. Before any chart or numeric prose is implemented, its ledger row must be marked Keep, Archive, or Revalidate. Revalidate means no visual until its source adapter and class are added.
3. Before an interaction is implemented, cite one local reference file and one named exemplar from sections 3-4 in a component comment/design note.
4. Before deploy, adversarial review must test: stale-fallback removal, provenance/denominator visibility, page-to-artifact links, mobile/static fallbacks, reduced motion, keyboard details, and the anti-SaaS exclusions.
5. Dual deployment happens only after the content/data audit passes: canonical `ai-finops-rulebook` and mirror `agentic-dynamics` from `apps/website/`.

## 7. Research Log

| Check | Result | Evidence |
|---|---|---|
| R1 read audit | PASS | Eight HTML pages, `data.js` top-level contract/provenance, runtime mapping, current manifest/registry, campaign verdicts, historical handoff and review audit were inspected. |
| R2 positioning | PASS | Binding anti-SaaS field statement and credibility rules are recorded in section 1. |
| R3 named-exemplar research | PASS | Distill, SFI, Pudding, FT, NYT, Observable, Bret Victor, arXiv, academic labs, and local Story were studied; URLs and transfer rules are in section 3. |
| R3c local code library | PASS | Four SVG, four D3, two scrollytelling, two card/UI, and two typography/layout working examples are in `apps/website/references/`. |
| R3d visual synthesis | PASS | Typography, palette, motion, primitives, and nine diagram specs are binding in section 4. |
| R4 IA/updatability | PASS | Narrative spine, page dispositions, named editorial slots, and source-adapter update rule are in section 5. |

**LOG: PASS.** This document and `apps/website/references/` are the editorial/visual gate for the later public-site rebuild.
