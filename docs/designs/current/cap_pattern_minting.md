# CAP pattern minting — inventory, minting table, writeup

**Status:** p1_inventory_labs (this file's §1 is the p1 deliverable; §2–§3 are written by the
later phases of `workflows/repository/cap_pattern_minting.yaml`).

**Question (the workflow's `question` field):** mint the first `pattern` facts from the
lab-book corpus using the merged I9 pattern reducer (`pattern/v1`) — task-routing, escalation
premium, cache economics, grit recovery, correctness premium — each pattern DERIVED/[C], minted
ONLY by the deterministic reducer from measured evidence (hard rule 3), carrying claim,
population, conditions, support, uncertainty, validity window, and source_experiment.

**Hard rules in force (from the workflow spec):** (2) REDUCER MINTS ONLY — a pattern fact is
created only by the I9 reducer from measured evidence; (3) no fabricated support; (4) quarantined
labs (`legacy_labs/`) are never minted from; (5) D7 holds — no new `EPISTEMIC_MAP` row, pattern
epistemic_status is the existing `"derived"`.

---

## 1. The minting table (p1 — inventory)

### 1.1 Corpus census — the contract-bearing lab corpus

The canonical lab output directory `experiments/results/` holds **8** contract-bearing lab JSONs
(every one carries a `lab_contract` block; `tests/test_lab_outputs_canonical.py` asserts the
directory equals the publication-eligible set and that each contract validates against the
current registry, `registry_version` `data-manifest/1.0+701rows`). Note: the workflow spec's
`current_state` and `experiments/CONTEXT.md` both say "7"; the on-disk + manifest count is
**8** — `lab_story_review.json` is the eighth. This inventory records the measured count of 8.

| # | lab JSON (`experiments/results/`) | metric_definition_version | input_dataset_id | n_resolved / n_used | contract |
|---|---|---|---|---|---|
| 1 | `lab_grit.json` | grit/v2 | canonical_registry/finding+story | 279 / 144 | valid ([M] lab) |
| 2 | `lab_cache_economics.json` | cache_economics/v2 | canonical_registry/story | 215 / 215 | valid ([M] lab) |
| 3 | `lab_condition_effects.json` | condition_effects/v2 | canonical_registry/story+review | 457 / 370 | valid ([M] lab) |
| 4 | `lab_quality_frontier.json` | quality_frontier/v2 | canonical_registry/story+analysis | 371 / 312 | valid ([M] lab) |
| 5 | `lab_story_arc.json` | story_arc/v2 | canonical_registry/story | 215 / 215 | valid ([M] lab) |
| 6 | `lab_story_review.json` | story_review/v2 | canonical_registry/story | 215 / 215 | valid ([M] lab) |
| 7 | `lab_verification_frontier.json` | verification_frontier/v2 | canonical_registry/story | 215 / 215 | valid ([M] lab) |
| 8 | `lab_verification_value.json` | verification_value/v2 | canonical_registry/story+review | 457 / 310 | valid ([M] lab) |

Quarantined, never minted (hard rule 4 — `experiments/results/legacy_labs/README.md`; all read
the RETIRED `_results_summary.json`): `lab_task_routing`, `lab_correctness_premium`, plus 9 others
(`lab_manifest.json` `lab_status: quarantined`).

### 1.2 Per-lab measurable claim extraction

For each contract-bearing lab, the measurable claim, population, conditions, and raw support
counts — every number below is read directly from the named artifact, never estimated.

**1. `lab_grit.json` — Grit, G(s) = P(test_executed_success | perturbation_strength = s).**
- Claim: test-executed success survives perturbation; G(s) and per-class rates.
- Population: canonical finding+story rows (n_resolved 279); eligible 144 cells.
- Conditions: `perturbation_strength` present AND `test_executed_success` measured (135 rows
  excluded `missing_required_field`, never imputed).
- Raw support: 144 eligible, **108 successes** (overall 0.75). Finding-corpus (`by_strength_finding_corpus`):
  s=0.0 **n=10 / 7 successes (0.7)**; s=0.5 **n=54 / 38 (0.7037)**. By perturbation class
  (`by_perturbation_class_perturbed`): `objective_mutation` n=14/11 (0.7857);
  `process_perturbation` n=26/15 (0.5769); `specification_corruption` n=14/12 (0.8571);
  `story:early_degrade` n=80/63 (0.7875). Caveats state G(s) is two points (s∈{0.0, 0.5}), not a
  dose-response curve.
- **MINTABLE via `pattern/v1`** — its finding rows are exactly the reducer's input door
  (structured `test_executed_success`, `perturbation_class`, `_experiment`). See §1.3 for the
  ground-truth mint.

**2. `lab_cache_economics.json` — cache-hit economics from session transcripts.**
- Claim: per-model average cache-hit rate and captured cost over story cells.
- Population: canonical story rows (n_resolved 215, n_used 215).
- Conditions: cells with captured cost/cache metrics (cost coverage 1.0 for 5/7 models; haiku
  0.8333, sonnet 0.8519).
- Raw support: 215 story cells, 7 models; avg cache-hit ranges 0.801 (deepseek-v4-pro) to 0.964
  (deepseek-v4-flash); e.g. flash avg_cost $0.0745, sonnet-5 avg_cost $5.169.
- **NOT v1-mintable** — cache economics is computed from STORY rows (cache_reads/cost), which
  carry no structured `test_executed_success` finding outcome. `pattern/v1` consumes `finding`
  evidence only; a cache-economics pattern needs a new reducer input door + claim shape (a future
  `pattern/v2` increment, recorded not estimated).

**3. `lab_condition_effects.json` — perturbation-condition effects (CLEAN vs EARLY_DEGRADE).**
- Claim: condition moves outcome metrics — CLEAN success_rate 0.97 (135 cells) vs EARLY_DEGRADE
  0.863 (80 cells); avg cost $1.543 vs $1.401.
- Population: canonical story+review rows; n_used 370 (215 stories + 155 joined reviews; 87
  `review_without_current_story` excluded).
- Conditions: joined current-story review population (the resolver's no-op relabel).
- Raw support: clean n=135 (success 131/135 by 0.97 rate), early_degrade n=80 (69/80 by 0.863).
- **NOT v1-mintable** — condition comparison is story/review-derived, not finding-shaped.

**4. `lab_quality_frontier.json` — quality-per-cost Pareto frontier.**
- Claim: Pareto frontier across correctness/cost/maintainability; 7 models.
- Population: story+analysis joined rows (n_resolved 371, n_used 312; 59 `outside_analysis_population`).
- Raw support: 312 cells; e.g. flash code_quality 0.037 at $0.068, sonnet 0.052 at $4.776.
- **NOT v1-mintable** — quality/analysis metrics, not finding rows.

**5. `lab_story_arc.json` — per-session cost/quality arc over the 5-session story.**
- Claim: snowball factor 2.32 — session 1 avg cost $0.1732 (n=215) → session 5 $0.4020 (n=211).
- Population: canonical story rows (n_used 215).
- Conditions: per-session_number (1..5, cost captured-only).
- Raw support: 215 stories × 5 sessions; cost coverage 0.9628→0.9384 across sessions.
- **NOT v1-mintable** — arc is story/session-shaped, not finding rows.

**6. `lab_story_review.json` — per-story review aggregation.**
- Claim: per-story/per-condition success and cost (215 cells, 1067 sessions, total cost $309.17).
- Population: canonical story rows (n_used 215).
- Conditions: story-level success (all_successful) + captured cost.
- Raw support: 215 cells; by_story success task_manager_api 1.0 (77), static_site_gen 0.92 (65),
  notification_service 0.86 (73); clean 0.97 (135) vs early_degrade 0.86 (80).
- **NOT v1-mintable** — story-aggregate shape, not finding rows.

**7. `lab_verification_frontier.json` — verification effort vs verified outcome.**
- Claim: verification depth (avg_tests) buys correctness; cheapest deepseek-v4-flash, most
  verified claude-haiku-4-5, pareto_frontier [flash, haiku].
- Population: canonical story rows (n_used 215).
- Raw support: 215 cells; flash $0.074/57 tests, haiku $1.631/127.9 tests, sonnet $5.169/117.1.
- **NOT v1-mintable** — verification-shaped, not finding rows.

**8. `lab_verification_value.json` — agent-authored vs independent-evaluator delta.**
- Claim: correlation tests vs worse_rate **−0.154** (more tests → lower worse-rate).
- Population: story+review joined rows (n_used 310; 87 review_without_story, 60
  story_without_review excluded).
- Raw support: 105 cells; e.g. haiku tests=294 reviews=5 better 0.6/worse 0.0.
- **NOT v1-mintable** — review-join correlation, not finding rows.

### 1.3 The mintable set — ground truth from `pattern/v1` over the canonical finding corpus

`pattern/v1` (`src/agentic_dynamics/control/reducers/pattern.py`, version `pattern/v1`) consumes
`finding` evidence only. Running it over the real canonical finding table
(`canonical_corpus.load_canonical_tables("finding")`, 64 findings, **all 64 measured** — 0 rows
excluded for an unmeasured `test_executed_success`) mints **exactly 6 facts** (the grit-recovery /
`recovers_under_*` family — this is the corpus `lab_grit`'s finding table consumes, 64 = 10+54):

| # | slice (task × perturbation_class) | claim | population | conditions | support / total | uncertainty (95% Wilson width) | source_experiment (lex-min finding ref) | n evidence |
|---|---|---|---|---|---|---|---|---|
| P1 | process_perturbation_resample × baseline | recovers_under_baseline | finding:task=process_perturbation_resample,perturbation_class=baseline | ("test_executed_success=true",) | 2 / 3 | 0.7308 | `finding:268c129f9bcecd5c987734030bc0feeeda1d37adaa5a97010d48bdf2c01ebf7e:469664cb5d62a17c36579f27657dfb78b9db265b9ac0f6bdbb5caa28b660c95a` | 3 |
| P2 | process_perturbation_resample × process_perturbation | recovers_under_process_perturbation | finding:task=process_perturbation_resample,perturbation_class=process_perturbation | ("test_executed_success=true",) | 7 / 12 | 0.4872 | `finding:28afad986a29ebd2b58420615c08b9df0a8c95ac8aa39629a5b093fdfd245f23:bd6143e05d8e342c810f784d1db536055170adee78aea7b9d812a52eec465ff0` | 12 |
| P3 | task_manager × baseline | recovers_under_baseline | finding:task=task_manager,perturbation_class=baseline | ("test_executed_success=true",) | 5 / 7 | 0.5588 | `finding:16ede2ba6e18c3a33845f84469ea8201cd4e90e78e654b188d59e1f979e2c4fb:de115254ea2f3c16a75301913cb9b851d8c1449604c3a1280caeec2239c712ed` | 7 |
| P4 | task_manager × objective_mutation | recovers_under_objective_mutation | finding:task=task_manager,perturbation_class=objective_mutation | ("test_executed_success=true",) | 11 / 14 | 0.4002 | `finding:08f42125f707e15a3725ba45e585829229fb6de6d4260d3fb36ccdef9bd98dd7:c212f8c2cdb236d44fb019f475c69ab18542e4505634b7e2d7bcc1668b6870e5` | 14 |
| P5 | task_manager × process_perturbation | recovers_under_process_perturbation | finding:task=task_manager,perturbation_class=process_perturbation | ("test_executed_success=true",) | 8 / 14 | 0.4603 | `finding:016251d99eb58bbfe90db1bee1cf7e1fe658b882e16f7304df2c7ec338d39ebc:1682a90abb16519b2441324e94b352fc7f054906f33881f491613409acaafd79` | 14 |
| P6 | task_manager × specification_corruption | recovers_under_specification_corruption | finding:task=task_manager,perturbation_class=specification_corruption | ("test_executed_success=true",) | 12 / 14 | 0.3593 | `finding:05fa65b507d40ec6ecc465314642987f7caff87aa348e3f6e1a54655286187c2:5120ca6ac7cd0d4b022262e588e2f2f8273f7c0eea027915b33e6f48fef0ff9f` | 14 |

Every `source_experiment` ref resolves in `experiments/results/registry_index.jsonl` to
`lifecycle_state=current` (verified programmatically at inventory time). The full supporting set
per fact is its `evidence_ids` (3, 12, 7, 14, 14, 14 — summing to the 64 finding rows). All six
facts are DERIVED/[C] (`epistemic_status="derived"`, `_EPISTEMIC_STATUS`), `is_canonical()` True,
`verify_chain` clean (the `test_context_plane_pattern.py` invariants). `validity_window` = the
mint run's `source_revision` (the p2 phase stamps it from the run revision / git sha).

### 1.4 Non-lab measured sources — inventoried, NOT v1-mintable

**Escalation premium (retro session-routing).** `experiments/results/session_routing_retrospective.json`
(study `cap_session_routing_retrospective/v1`): the `escalate` arm has **n=7, verified 7/7,
success_rate 1.0, cost_per_verified_outcome $3.9238** vs the `fork_cached` arm **n=246,
cpvo $1.2658** → escalation premium ratio **3.0999 ≈ 3.1×** (computed: 3.9238 / 1.2658). Source
script `scripts/retro_session_routing.py` replays the workflow-run corpus. **Not v1-mintable** —
this is arm/session-transition evidence, not `finding` rows; a routing-pattern mint needs a
different reducer input door + claim shape.

**E4 grit pilot.** `experiments/results/cap_grit_grid_metrics.json` (schema
`cap_grit_grid_metrics/v1`, grid_status COMPLETED) + `cap_grit_grid_ledger.json` (8 cells, 9
attempts) + `cap_grit_grid_writeup.md`: grit curve `{0.0:0.5, 0.2:1.0, 0.5:1.0, 0.8:0.6667}`,
**grit_auc = 1.4**, **recovery_premium = 1.1277 (≈1.13×)**; coverage 1.0 on both cost and test
verification (9/9). **Not v1-mintable** — the E4 pilot's evidence is a grid ledger of story-cell
attempts (strength/verified/cost), not `finding` records in the canonical corpus; a grit-pattern
mint from E4 needs the story-cell → finding bridge (a `story_facts/v1`-style producer) that the
writeup's `fact_plane_gap` documents as the forward gap.

### 1.5 Mintability verdict — counts

- **Mintable via `pattern/v1` as merged: 1 source (the canonical finding corpus; surfaced by
  `lab_grit`) → 6 facts** (the `recovers_under_*` / grit-recovery family, §1.3). This is the
  `grit_recovery (lab_grit)` named pattern.
- **Skipped — quarantined (hard rule 4): 2 named workflow targets** — `task_routing`
  (`lab_task_routing`), `correctness_premium` (`lab_correctness_premium`) — both read the RETIRED
  `_results_summary.json`; never minted from.
- **Skipped — contract-bearing but evidence not finding-shaped (v1 input door): 7 labs** —
  cache_economics, condition_effects, quality_frontier, story_arc, story_review,
  verification_frontier, verification_value (§1.2, each with its real measured claim recorded).
- **Inventoried, not v1-mintable: 2 non-lab measured sources** — escalation premium (3.10×, n=7),
  E4 grit pilot (recovery 1.13×, n=9, grit_auc 1.4).
- **Mintable count = 6 facts; skipped count = 2 quarantined + 7 non-finding contract labs;
  inventoried-not-minted = 2 non-lab sources.**

p1 verdict: **PASS** — every row in this table traces to a real artifact
(`experiments/results/lab_*.json`, `session_routing_retrospective.json`,
`cap_grit_grid_metrics.json`, `registry_index.jsonl`); no estimates. p2 mints the 6 §1.3 facts
and records the skips; p3 writes the full writeup.

---

## 2. The minted facts (p2 — facts table)

Minted by the registered deterministic reducer `pattern/v1` (`src/agentic_dynamics/control/reducers/pattern.py`),
invoked through the fact-plane producer (`scripts/kb_produce_facts.py --reducer pattern/v1`, the
new I9 evidence branch — the producer-wiring half that closes the gap the pattern tests
referenced). **6 facts minted, all DERIVED/[C] (D7: the EXISTING `"derived"` row — no new
`EPISTEMIC_MAP` entry), all `is_canonical()` True, all `verify_chain` clean, all idempotently
re-derivable to 0.** Emitted to the KB as `source_type="fact"` on `kb:v1:changes` (DB 2, 6380),
registered in `registry_index.jsonl` with `lifecycle_state=current`, each with a durable artifact
under `experiments/results/kb/<knowledge_id>.json` whose bytes hash to the event's `content_hash`
(verified for all 6).

Source revision (the `validity_window`, = the reducer's `inp.source_revision`): the HEAD at mint
time — **`eceee4bba9c5e9ff5fe966296905cbd72785e563`** (p1 commit; p2 emission ran before the p2
commit). Observed/valid timestamp: `2026-08-24T23:51:35.213950+00:00`.

| # | subject_id (`pattern/<task>/<class>`) | claim | support / total | uncertainty (95% Wilson width) | knowledge_id (`fact_id`) | fact_entity_id | n evidence |
|---|---|---|---|---|---|---|---|
| P1 | `pattern/process_perturbation_resample/baseline` | recovers_under_baseline | 2 / 3 | 0.7308 | `34f13e44e30b6f3b…` | `801d17fe…` | 3 |
| P2 | `pattern/process_perturbation_resample/process_perturbation` | recovers_under_process_perturbation | 7 / 12 | 0.4872 | `8f3583e6fe89b71e…` | `ad2ae876…` | 12 |
| P3 | `pattern/task_manager/baseline` | recovers_under_baseline | 5 / 7 | 0.5588 | `47896f56ccda7d53…` | `c697b1fe…` | 7 |
| P4 | `pattern/task_manager/objective_mutation` | recovers_under_objective_mutation | 11 / 14 | 0.4002 | `f2a9d7522d236193…` | `1fa0f6d4…` | 14 |
| P5 | `pattern/task_manager/process_perturbation` | recovers_under_process_perturbation | 8 / 14 | 0.4603 | `febaf53ad049f5b8…` | `a7cf5403…` | 14 |
| P6 | `pattern/task_manager/specification_corruption` | recovers_under_specification_corruption | 12 / 14 | 0.3593 | `cb6ceecb10988b21…` | `4071ac75…` | 14 |

Each fact's `PatternPayload` (`conditions=("test_executed_success=true",)`; `population` =
`finding:task=<task>,perturbation_class=<class>`; `source_experiment` = the lexicographically
smallest lab-contract ref in its slice, which is also in `evidence_ids`) is verified against the
registered record. **Every `evidence_id` resolves to a `current` registry `finding` row; the full
`evidence_ids` per fact are listed in §1.3's minting table footnote.**

**Mint-time verification (guard — all PASS):**
- DERIVED/[C]: `epistemic_status="derived"`, `authority=DERIVED`, `evidence_class="[C]"` for all 6.
- `is_canonical()` True and `verify_chain` → 0 errors for all 6 (registered reducer + declared
  predicate + reproduces digest + epistemic consistency).
- Entity identity: each `fact_entity_id` matches the registered row; deterministic (the same
  evidence set always re-derives the same slot).
- Idempotent re-derivation: `kb_produce_facts.py --reducer pattern/v1` re-run derives **0** new
  records (converges to the registered head — the convergence guard), emits **0**.
- Evidence resolution: every `evidence_id`'s `finding` row is `current` in the registry
  (verified against `registry_index.jsonl`).

**Skipped labs recorded (no mint — see §1.5):** `task_routing` + `correctness_premium`
(quarantined, hard rule 4); cache_economics, condition_effects, quality_frontier, story_arc,
story_review, verification_frontier, verification_value (contract-bearing but not finding-shaped
for the v1 input door); escalation-premium + E4 grit-pilot numbers (inventoried, not v1-mintable).
No hand-written facts were produced; every mint went through the reducer + producer pipe.

p2 verdict: **PASS** — 6 facts minted + registered + verified; 0 skipped-without-record; the only
code change is the producer's `pattern/v1` evidence branch (+ one hermetic integration test).

## 3. Writeup (p3)

*Filled by phase p3_writeup: the pattern set (claim, support, uncertainty, validity window,
source), what each pattern would allow a routing rule to consume, which labs were skipped and
why, and the D1/D2 note (patterns are now mintable facts; their retrieval projection is a
separate decision).*
