---
status: accepted
---
# Context Abstraction Plane — Implementation Notes

**Append-only.** This file records the design deviations and verify-phase findings that the
implement spec (`workflows/repository/context_abstraction_implement.yaml`) must carry into
I0–I7. Never rewrite or delete an existing line — append new entries below the last one.

## 1. Addendum A reference (out of scope)

`docs/designs/current/context_abstraction_design.md` Addendum A (I8 profiles, I9 patterns,
I10 checkpoint) is OUT OF SCOPE for this spec; I8–I10 are implemented under a follow-up design
spec, not here.

## 2. F1 resolution (material)

An invariant with `on_missing: classify` silently disables a safety constraint — invariants
require halt semantics; the validator refuses a contract whose invariant lacks halt semantics
(new check documented under C8); the design's `max_spend_usd` example is amended: either
demote it from `invariants` to `requires_facts` or set `on_missing: halt`.

## 3. F2 resolution

Check C5 rejects an empty `facts_used`.

## 4. F3 resolution

`expected_effect` scores are recorded on the decision record, never applied.

## 5. F4 resolution

`conflicted` is computed in the reducer (`fact_state()`), read by the compiler.

## 6. F5 resolution

OQ3/OQ7 table-form answers accepted as-is.

## 7. F6 resolution

`source_type=fact` nominal authority column is documentation only — no change.

## 8. CAP I0-I3 repair (r1-r4, material — carried forward into I4)

Before I4 (`context_compiler.py`) could resume, an audit found the I0-I3 reducers/fact-ingestion
implementation had four load-bearing gaps against the design's own stated invariants. All four are
fixed (`src/agentic_dynamics/control/reducers/{attempt_facts,job_facts,workflow_facts,_common}.py`,
`src/agentic_dynamics/control/fact_ingestion.py`, `scripts/kb_produce_facts.py`); the decisions
below are genuine deviations from what the design text left implicit, and I4 (or any future reader
of the fact plane) must know them:

1. **Run identity is a new, explicit concept — content-addressed, not caller-supplied.**
   `_common.run_artifact_id(run)` = sha256 of a run's own canonical (sorted-key) JSON. Introduced
   because `EvidenceItem.evidence_id` for a workflow run used to be `f"workflow:{spec_name}"` —
   spec-name-only — so every run of the same spec collided on identity regardless of model, phase
   values, or when it ran (two distinct persisted run artifacts silently merged into one fact).
2. **Attempt facts (L1) are PER-RUN; job facts (L2) are CURRENT-PER-CELL.** This is an explicit,
   asymmetric identity choice the original design left unstated (§ its own open question 2: "does
   a fact supersede by entity_id, or accumulate like observations?"). Attempt facts fold
   `run_artifact_id` into `scope_id` (`<cell>:<phase>:<run_id>`) so they NEVER supersede across
   runs (an attempt is a historical execution record — "phase X of run Y cost $Z" — not a mutable
   summary); job facts keep the pre-existing cell-only scope so they DO supersede via the existing
   registry chain (a job fact answers "what is the current state of this cell, right now"). Two
   opposite identity strategies for two adjacent abstraction levels, by design, not oversight.
3. **Content identity is NOT run identity — `fact_fingerprint` must ignore provenance.**
   Once `evidence_ids` carried a real run-specific citation (deviation 1), two runs of the same
   job cell that happened to measure the SAME value got DIFFERENT `evidence_ids` (each cites its
   own run) and therefore, if the fingerprint hashed them, DIFFERENT fingerprints — every
   re-run, even a pure re-confirmation, would have spuriously superseded the previous value and
   defeated the "unchanged → no-op" convergence guard the design explicitly requires. Fixed:
   `fact_ingestion.fact_fingerprint` hashes the DECLARATIVE payload only (predicate/value/scope/
   subject/abstraction_level/expires_at/reducer_version), excluding `evidence_ids`/
   `inputs_digest`. The persisted artifact (`knowledge_id`/`content_hash`) is untouched and still
   differs per run — only the supersession-worthiness decision changed.
4. **`derive_fact_records` guarantees oldest-first chaining itself — it does not merely benefit
   from a well-behaved caller.** Originally the "which value ends up current" outcome depended on
   the ORDER facts were handed in (a caller-side contract: `kb_produce_facts.load_run_jsons`
   sorts oldest-first). An adversarial review (r4) found this meant out-of-order evidence (a
   caller — or a future producer bug — handing facts newest-first) would let an OLDER observation
   win the "current" slot. Fixed: `derive_fact_records` now stably sorts its input by
   `observed_at` internally, so the guarantee holds regardless of caller behavior.

Two further r4 defense-in-depth additions, not identity deviations but worth recording alongside:
duplicate evidence (two on-disk run artifacts with byte-identical content) is deduped at
`kb_produce_facts._run_evidence` by `run_artifact_id`, and `workflow_facts_v1` independently
dedupes its finalized input facts by `fact_id` before aggregating, so a duplicated artifact
upstream can never double-count a phase in `workflow_phases_completed`/`workflow_status`.

Also material: `workflow_status`/`workflow_health` now treat `job_status` (derived from
`WorkflowRunResult.ok`, which sees EVERY phase) as authoritative over a phase-only scan for the
literal string `"failed"` — a phase status of `"skipped"`/`"error"`/`"timeout"` would otherwise
read as "not failed". And `projected_budget_overrun` is emitted only when BOTH a budget ceiling
AND a measured cost are known — an unmeasured cost previously fabricated a `0.0` overrun.

## 9. I4 deviations (material — the Context Compiler against the REAL reducer scope_paths)

I4 (`src/agentic_dynamics/control/context_compiler.py`) resumed after the I0-I3 repair. Three
deviations from a literal reading of design §10.1's idealized single-chain scope grammar
(`org/.../workload/.../workflow/.../job/.../attempt`), all forced by the ACTUAL scope_paths the
I1-I3 reducers already emit (`control/reducers/{job_facts,workflow_facts,attempt_facts}.py`),
not by a re-reading of the design's intent:

1. **`job` and `workflow` are SIBLING labels over the SAME cell id, not a nested pair.**
   `job_facts.py` emits `workload:<w>/job:<cell>`; `workflow_facts.py` emits
   `workload:<w>/workflow:<cell>` — same `<cell>`, same depth, different label (design §10.3
   already says so in prose: "job scope = the workflow-level view of the cell, one rung up the
   ladder"). `resolve_requirement_scope`'s `"parent"` keyword therefore does NOT drop the last
   path segment generically — from a job-scoped decision it swaps the label to `workflow:<cell>`
   (`context_compiler._parent_scope_path`), not "org:.../workload:...".
2. **`attempt` nests TWO segments under `job`, not one.** `attempt_facts.py` emits
   `job:<cell>/attempt:<phase>/run:<run_id>` (the `run:` segment is the I0-I3 repair's
   content-addressed run identity, deviation 1 in §8 above). `_parent_scope_path` drops the
   trailing `run:` segment before checking the leaf type, so an attempt scope's parent correctly
   resolves to its owning `job:<cell>`, not `job:<cell>/attempt:<phase>`.
3. **`scope: self` for a predicate declared ONE RUNG below the decision's own scope resolves via
   a narrow "self-reflexive descendant" allowance, not a strict scope_path equality check.** The
   design's own §6.1 example requires `phase_test_verified` (attempt-scoped) at `scope: self`
   under a `job`-scoped decision — those two scope_paths are never equal by construction (per
   deviation 2). `_resolve_requirement` falls back, ONLY for `scope: self` and ONLY when strict
   `scope_visible()` finds nothing, to the single MOST RECENTLY OBSERVED current fact whose
   scope_path is strictly under the decision's own scope_path. This is deliberately narrower than
   the general "descendant peek" §10.2 forbids for aggregation (unbounded reads across children
   with no reducer): it never returns more than one fact, and it only fires for `self`, never for
   an ancestor/explicit scope keyword — so a sibling job's attempts, or a workflow's OTHER job's
   facts, are still structurally unreachable.

Also: the I4 hook (`context_compiler.make_snapshotting_router`, wired via `run_workflow.py
--cap-snapshot`) is the FIRST CAP call site to touch a real production run path and a real Redis
connection. It ships OFF by default (an explicit opt-in flag, not the default `router=`) — a
narrower posture than the design's own "snapshots recorded beside every route_step call" phrasing
implies literally, so the plane's first production write is a deliberate, reviewable operator
decision, consistent with I7's later apply seam being OFF by default for the same reason. Flip
procedure: pass `--cap-snapshot` to `scripts/run_workflow.py`; nothing else changes, and a
snapshot failure (no Redis, unauthorized write) never affects the run (`record_snapshot` swallows
every exception).

## 10. I5 — fact contracts in the spec gate (`FactRequirement` gains its refusal gate)

`core/contracts.py` gains `validate_fact_contracts` (refusals R1-R11) and `RuleSpec` gains
`requires_facts`/`decision_type` (`src/agentic_dynamics/experiment/experiment_spec.py`). Two
points worth recording, neither a deviation from the design's intent, both forced by
`tests/test_dependency_direction.py`'s tier rules (`experiment` may not import `control`; `core`
may not import either):

1. **The compile-time gate is genuinely two-layer, not one function.**
   `core.contracts.validate_fact_contracts` is pure and duck-typed — it takes
   `predicates`/`reducers`/`contracts` as plain `Mapping`s (structural `Protocol`s, never a
   concrete import of `control.facts.PredicateSpec`/`ReducerSpec` or
   `experiment.experiment_spec.RuleSpec`) so `core` (tier 0) never imports `experiment` (tier 1)
   or `control` (tier 2). `experiment_spec.validate_rules`/`validate_spec` gained THREE new
   keyword-only parameters (`fact_predicates`/`fact_reducers`/`fact_contracts`), all defaulting
   to `None` — `None` means "skip the I5 gate entirely", which is what keeps every
   `validate_spec(spec)` call site in the codebase (including `compile_experiment.compile_spec`,
   which stays tier 1 and therefore cannot supply the real registries) validating byte-for-byte
   unchanged. The REAL gate — real `FACT_PREDICATES`/`REDUCERS`/loaded contracts —  is
   `control.context_compiler.validate_spec_fact_contracts(spec)`, a `control`-tier (tier 2)
   function that CAN see both `core` and `experiment` and is the actual "a spec requiring an
   unproduced predicate is refused" call site the I5 gate (design §9) means.
2. **R11 is additive to the design's own R1-R10 table** (§7.3), carrying forward the F1
   resolution already recorded in §2 above: an invariant with `on_missing` outside
   `{halt, escalate}` is refused. Checked for every LOADED contract (not just ones a spec's
   rules reference), because the property is of the CONTRACT, independent of who cites it.

## 11. I6 — the shadow controller + validator (decisions recorded without touching the armed gate)

`control/decisions.py` (`ControlDecision`/`Precondition`/`ExpectedEffect`/`AUTOMATABLE_ACTIONS`),
`control/rules.py` (`route_next_job_v1`, `make_shadow_router`), and `control/validator.py`
(`validate_decision`, checks C1-C10) ship the shadow controller. One material deviation from a
literal reading of design §8.2 ("Persisted as `source_type="actuation"`... REUSE"):

**A shadow decision's durable artifact is written directly; `publish_event` is never called for
it.** `knowledge_stream.publish_event`'s actuation gate unconditionally requires
`FINOPS_ACTUATION_ARMED=1` (or `armed=True`) for ANY `source_type="actuation"` message — there is
no lower-privilege "record but don't arm" mode inside that function. But design §8.6's commitment
1 is unconditional the other way: "It does not arm actuation... this design adds nothing that
sets it." Calling `publish_event(..., armed=True)` from the shadow hook would satisfy "decisions
get recorded" while violating "never arms actuation"; calling it unarmed would raise on every
single shadow decision, defeating "recorded" entirely. `control.rules.record_shadow_decision`
resolves the conflict by stopping one step earlier in the SAME pipe design §4.3/§8.2 reuses:
`record_to_artifact` writes the durable, content-addressed, per-record JSON
(`KB_ARTIFACT_DIR/<knowledge_id>.json`) — so a decision is a real, auditable, inspectable
artifact — but the pointer event is never published to `kb:v1:changes`, so it never reaches the
live registry/stream a real actuation consumer would react to, and `publish_event`'s armed gate
is never even invoked. This is STRICTER than I4's snapshot recording (an OBSERVATION-family
record, which has no armed gate and DOES call `publish_event`) — a shadow decision is
discoverable only by scanning `KB_ARTIFACT_DIR` directly (`scripts/shadow_decision_report.py`
does exactly this, filtering on `extractor_version="actuation/v1"`), never via
`scripts/registry.py` or `experiments/data_manifest.json`. If a future increment (I7+) needs
shadow decisions in the live registry for a UI or a lineage walk, that is a deliberate, reviewable
widening of this file's own posture, not an oversight.

F2 (an action other than `continue` with empty `facts_used` is refused, check C5) and F3
(`decision_calibration` as a named measurement rule) are implemented verbatim per their
resolutions in the workflow spec's own phase prompt. `AUTOMATABLE_ACTIONS = frozenset({"continue",
"route"})` is CODE in `control/decisions.py`, imported (never re-declared) by both `rules.py` and
`validator.py`, so there is exactly one definition to audit.

## 12. I7 — the apply seam for `route` (kept OFF; the flip procedure)

`control.rules.make_applying_router` (a strict superset of I6's `make_shadow_router`) is the ONLY
function in the plane that can change what model actually executes a phase. It applies the
fact-based rule's `route` choice INSTEAD of `step_routing.route_step`'s ONLY when a freshly
re-compiled snapshot (the C7 TOCTOU re-check) still validates the decision through ALL of C1-C10
AND the action is `"route"` (`"continue"`, the other `AUTOMATABLE_ACTIONS` member, always means
"use `route_step`'s default" by construction). Any failure anywhere — an inadmissible snapshot, a
C1-C10 refusal, a missing contract, an exception — falls back to `route_step`'s deterministic
choice; that fallback is the SAFE path this seam is built around, not a degraded one.

**Wiring is a per-spec opt-in, never a default and never a CLI flag alone.**
`scripts/run_workflow.py` reads `spec.workflow.params.get("control_route", False)` — a field in
the SPEC YAML, not an invocation-time switch — and only then builds `make_applying_router(...)`
as the injected `Router`; every other spec keeps `route_step` unchanged regardless of how the
script is invoked. This is deliberately narrower than `--cap-shadow`/`--cap-snapshot` (I6/I4's
per-INVOCATION measurement opt-ins): applying a routing decision changes what actually executes,
so the decision to allow it belongs to the spec's own author, committed and reviewable, not to
whoever happens to run the script that day.

**The flip procedure — what an operator does to enable this for a real spec, and what must be
true first (design §9 I7's own gate):**

1. Run the spec for a meaningful number of cycles with `--cap-shadow` (implies `--cap-snapshot`)
   so `route_next_job_v1` proposes BESIDE `step_routing.route_step` without ever executing.
2. Read `python scripts/shadow_decision_report.py` — the agreement rate
   (`1 - decision_regret`) between the plane's proposals and what `step_routing` actually chose.
3. Read `python scripts/decision_arm_comparison.py` — the REAL measured cost/quality loss per
   model that actually ran (`compile_experiment.compare_arms`), so a divergent proposal can be
   checked against real precedent: does the plane's typical alternative model have a worse
   measured loss than the baseline?
4. Only once both reports support "the plane is at least non-inferior for this spec" does the
   operator add `workflow.params.control_route: true` to that ONE spec's YAML, in a normal,
   reviewable commit — never a global default, never an environment variable.
5. After flipping, keep watching `decision_arm_comparison.py` (now with `applied: true` rows
   mixed in) — an applied decision that regresses cost/quality is exactly what the campaign loop
   (`AdaptSpec`) exists to catch and revert.

**As of this increment, step 4 has not happened for any spec** — verified in
`tests/test_context_plane_seam.py::test_no_committed_spec_opts_into_control_route`, which checks
the REAL committed spec corpus, not just a fixture. No campaign data exists yet to justify a
flip; this increment ships the seam and the measurement harness that would produce that data,
per design §9 I7's own ordering.

## 13. I8 — `DomainProfile`/`ChallengeProfile` (`control/profiles.py`, new home)

Implements `docs/designs/current/context_abstraction_addendum_design.md` §2 against the REAL
I0–I7 code (the addendum text predates I0–I7 landing and marks `compile_context`/
`FactRequirement` `[design-only]`; both are real — `control/profiles.py`'s own docstring notes
this explicitly, same posture as `context_compiler.py`'s existing note about its own module).

**Schema** — `SessionPolicy`, `DomainProfile`, `ChallengeProfile` are frozen dataclasses exactly
per §2.1/§2.6 field lists. `DELIBERATION_STAGES` (§2.5's six-archetype table) and `CHALLENGES`
(its keys) are declared here as a compiler-owned enum, documented — never imported — against
`core.session_types.TASK_TYPES` (the two vocabularies answer different questions and only
partially overlap in spelling; see the module docstring for the full reasoning).

**Homes** — `control/profiles.py` (new, this increment's reserved home) carries everything:
the dataclasses, `compose_requirements`/`tighten`, the `PROFILES` registry, and — deviating
slightly from the reserved-homes table's silence on a reducer for I8 — the `profiles/v1`
`ReducerSpec` + `profiles_v1` pure reducer, registered into `control/reducers/__init__.py`'s
`REDUCERS`/`_IMPLS` dicts exactly like every other reducer (I1–I3's own precedent). This was a
deliberate choice, not an oversight: "profiles declared as POLICY facts at construction" needs
SOME registered minter for `verify_chain` to accept the fact it produces, and hard rule 3's
"only a registered reducer mints a fact" discipline is general, not I9-pattern-specific, so I8's
facts are held to it too. The two new predicates themselves (`domain_profile_version`,
`challenge_profile_version` — both `abstraction_level="policy"`, workload-scoped, `inheritable
=True`, mirroring the existing `allowed_models`/`max_spend_usd`/`max_attempts` L5 rows) are
declared directly in `control/facts.py`'s own `FACT_PREDICATES` literal (additive), not mutated
into that dict from `profiles.py` — facts.py stays the one place a predicate is declared. This
widens `tests/test_context_plane_facts.py`'s call-site allowlist (`control/profiles.py` added to
`LEGITIMATE_CALLERS`) and its two exact-set completeness assertions (`test_predicate_registry_
has_the_design_seed_rows`, `test_predicate_inheritance_flags_match_the_design_table`) — both
updated in place, per that file's own "each increment widens this allowlist explicitly, never
silently" rule.

**Deviation (minor) — profile fact scope_id.** The design does not specify what scope a profile
declaration binds to (profiles are cross-spec, unlike `policy_facts.py`'s per-spec-name scoping).
`_profile_fact` uses the domain/challenge id itself as `scope_id` (`workload:<domain>` /
`workload:<challenge>`) — a profile is its own workload-scope anchor, which also gives
`compute_fact_entity_id` a stable, collision-free slot per (kind, id) independent of which spec
happens to declare it first.

**Deviation (minor) — `tighten()`'s scope taken literally from the design pseudocode.** §2.3's
sketch types `merged` as `dict[tuple[str, str], FactRequirement]` but its own dict comprehension
keys by `r.fact` (a bare string) — an inconsistency in the design-only sketch. Implemented as
written (keyed by `fact` name alone, per the actual comprehension), documented here rather than
silently "fixed" to the annotated type, since the annotation and the code it sketches disagree
and the code is the more specific signal. `tighten()` itself additionally raises
`ProfileCompositionError` on a `scope` or `value_type` disagreement between the contract's and
the profile's requirement for the same fact (not specified by the design; there is no sensible
"stricter" merge for either axis — see the module docstring's `tighten()` rationale) — these are
new refusal cases, additive to the "raises on loosen" the design names.

**`compile_context` extension (§2.3/§2.4)** — gains `domain: DomainProfile | None = None` and
`challenge: ChallengeProfile | None = None` keyword parameters. Only `challenge.
context_requirements` is composed (via `profiles.compose_requirements`) into the effective
`requires_facts` BEFORE the existing 9-step resolution runs; `contract.invariants` is never
touched (deviation D4: the contract's invariants remain the sole SAFETY gate). `domain` is
accepted and threaded through for symmetry/future audit use but contributes no requirements in
v1 (verified by `test_compile_context_accepts_a_domain_profile_without_changing_resolution`) —
per D6, a `DomainProfile` declares L5-policy-adjacent facts only, and inventing an L4
domain-contributed requirement here with no real backing would be exactly the honesty-rule
violation §2.1 forbids. No contract YAML changed; no `ContractSpec`/`ControlContext` field added.

**Seeded `PROFILES` registry** — one `DomainProfile` (`software_delivery`, this repository's own
CAP control-plane domain) and six `ChallengeProfile`s (one per `DELIBERATION_STAGES` key), all
`context_requirements=()`. Deliberately empty: no real decision-type contract yet names a fact
these archetypes should add, and fabricating one to look more "complete" would violate the same
honesty rule. A future increment adds real entries as real contracts need them, superseding
`profile_version` when it does (§2.2's supersession model, exercised in
`test_bumping_profile_version_supersedes_under_the_same_entity_id`).

**Migration helper (the deliverable), not a rewiring** — `migrate_static_filing()` resolves
`PROFILES` entries that supersede a workflow spec's free-text `context.domain_context`/
`challenge_context` prose (`workflows/repository/cap_addendum_implement.yaml` lines 24-36 is
itself an example of the pattern being superseded — written before this module existed). The
actual spec-YAML/`run_workflow.py` rewiring that would CONSUME this helper is explicitly NOT
done here (this increment's guard: no runner wiring changes) — the module docstring's
"MIGRATION" section documents the three-step swap procedure for that future change. No existing
workflow spec YAML was edited by this increment.

**No L4 workload-fact claims, no contract changes** (this phase's GUARD) — verified structurally:
every `FACT_PREDICATES` row this increment adds has `abstraction_level="policy"`
(`test_profiles_v1_is_registered_and_declares_only_l4_never_l4_workload`), and no file under
`experiments/contexts/` was touched.

Tests: `tests/test_context_plane_profiles.py` (new, 28 cases — dataclass shape, the registry,
the reducer/fact-minting path, versioning/supersession, `compose_requirements`/`tighten`'s
never-widens property both as a pure function and through the real `compile_context`).
Full suite green: `pytest tests/ -k "context_plane or dependency_direction or cap_i0_i3"` — 252
passed. PASS.

## 14. I9 — the `pattern` fact kind (`control/reducers/pattern.py`, D7)

Implements `docs/designs/current/context_abstraction_addendum_design.md` §3 (answers OQ4/OQ5)
against the REAL I0–I8 code. Proposal-only actuation; `apply` stays OFF (unaffected — this
increment adds no controller, no routing, no new actuation call site).

**Schema (`control/facts.py`, additive, I0's own home).** `PatternPayload` (frozen dataclass:
`claim`/`population`/`conditions`/`support`/`uncertainty`/`validity_window`/
`source_experiment`) plus one additive `FACT_PREDICATES["pattern"]` row
(`abstraction_level="workload"`, `scope_type="workload"`, `value_type="str"` — the canonical
JSON of `PatternPayload`, payload-in-value, `inheritable=True`). Per D7, **no new
`EPISTEMIC_MAP` row was added** — every `pattern` fact's `epistemic_status` is the EXISTING
`"derived"` row (`Authority.DERIVED`, `"[C]"`); verified explicitly by
`test_no_new_epistemic_map_row_was_added` (asserts the map's key set is exactly the original
five). This widens `tests/test_context_plane_facts.py`'s two exact-set completeness assertions
(`test_predicate_registry_has_the_design_seed_rows`, `test_predicate_inheritance_flags_match_
the_design_table`) to include `"pattern"`, per that file's own "each increment widens this
allowlist explicitly, never silently" rule (the same rule I8 followed in §13). No new call-site
allowlist entry was needed: `control/reducers/pattern.py` falls under the reducers package's
existing wholesale directory allowlist (`LEGITIMATE_DIRS`).

**The reducer (`control/reducers/pattern.py`, new — the design's own reserved home, §6).**
`PATTERN_V1`/`pattern_v1` is the SOLE registered producer of the `pattern` predicate
(`FACT_PREDICATES["pattern"].produced_by == ("pattern/v1",)`) — hard rule 3 made concrete for
this class (D3). `consumes` names the canonical-corpus tables (`finding`, `review`, `analysis` —
review constraint 4; NOT the retired `_results_summary.json`); v1 mines only `finding` evidence,
since that is the table carrying the structured `test_executed_success` field a pattern's
`support`/`conditions` need — `review`/`analysis` items are accepted (never crash) but
contribute nothing, the same "nothing to compute over → skip, never fabricate" posture as an
empty slice.

**Population slicing and the no-phantom rule (§3.3, verified against real records).** Findings
are grouped by `(task, perturbation_class)` (`row["_experiment"]` / `row["perturbation_class"]`
— the axes an actual finding row carries; the design's own worked example used `task`+
`condition`, an axis story records carry that finding records do not, so this is an adaptation
to the real schema, not a deviation from the design's intent). The coverage invariant is applied
TWICE, both verified by dedicated tests: (a) an empty slice mints no fact
(`test_empty_population_mints_no_fact`); (b) a row whose `test_executed_success` is not a real
`bool` is excluded from the slice entirely — never coerced into a "non-match"
(`test_unmeasured_outcomes_alone_mint_no_fact`) — the same null-is-not-zero rule
`measurement_coverage.py` enforces for cost/quality averages, applied here to a proportion's
population. `support` is a plain COUNT over deduplicated real rows (never an estimate); a
duplicate input row (the same lab-contract ref handed in twice) is deduped before counting,
mirroring `workflow_facts_v1`'s own r4 precedent (`test_duplicate_finding_records_are_deduped_
not_double_counted`). `uncertainty` is a 95% Wilson interval width, computed only at
`total >= MIN_SUPPORT_FOR_UNCERTAINTY = 3` (the same repetition floor the design's own F5 fix
uses, §4.4: "3 attempts/cell → the uncertainty term is estimable") — `None` below it, never a
fabricated number.

**`source_experiment` via lab-contract refs (§3.5) — REUSE, not a new cite format.**
`reporting.lab_contract.record_id(row)` yields the `"finding:<entity_id>:<knowledge_id>"` ref
per the design's own example; the reducer cites the lexicographically smallest ref among the
slice's records as `source_experiment` (deterministic) while `evidence_ids` carries the full
supporting set. `inputs_digest` is NOT recomputed via a second hash primitive
(`lab_contract.refs_digest`) — it uses the EXISTING `facts.recompute_inputs_digest` every other
reducer's fact uses (sha256 over sorted `evidence_ids` + `reducer_version`), which is not
optional: `verify_chain`'s check 3 always recomputes a fact's digest with that ONE formula
regardless of which reducer produced it, so a second formula would simply fail verification.
This is the same "no new hash, no new format" reuse the design asks for, achieved through the
schema's own existing helper rather than importing `lab_contract.refs_digest` a second time.

**Minting rules — hard rule 3 made executable, exercised end to end.** An LLM-proposed pattern
(`epistemic_status="advisory"`, a `reducer_version` that is not `pattern/v1`) is (a) never
`is_canonical()` (`test_advisory_pattern_is_never_canonical`), (b) refused by `verify_chain`
as belt-and-braces (`test_advisory_pattern_fails_verify_chain_too`), and (c) refused by the
REAL validator check C5 when cited in a `ControlDecision.facts_used`
(`test_advisory_pattern_proposal_is_uncitable_by_validate_decision_c5` — builds a minimal
synthetic `ContractSpec`/`ControlContext` directly, since no committed contract requires the
`pattern` predicate yet; C1–C4 are satisfied so the assertion exercises C5 itself, not an
earlier short-circuit).

**Minor defensive addition (not a deviation, not requested by the design): identity
sanitization.** `_slug()` sanitizes `task`/`perturbation_class` (non-alnum → `_`) before joining
them into the fact's `subject_id`/`scope_id`, mirroring `_common.cell_id`'s existing
sanitization for spec name + model — closes a theoretical `fact_entity_id` collision if either
axis ever contained a `/` (real corpus values today are simple identifiers, so this is
defense-in-depth, not a fix for an observed bug).

**Deliberately NOT done — the producer wiring gap (mirrors I8's own deferral, §13).**
`scripts/kb_produce_facts.py`'s `derive_facts()` dispatcher has no branch for `pattern/v1` (the
same gap I8 already left for `profiles/v1` — the CLI's `choices=tuple(REDUCERS)` accepts it, but
the dispatcher would fall through to the `spec_status/v1` evidence-loading branch and hand
`pattern_v1` spec-index evidence it correctly ignores, `source_type != "finding"`, yielding zero
facts rather than crashing). Wiring a real `finding`-evidence loader into that script is
producer-wiring work, out of this increment's reserved home (§6 lists only
`control/reducers/pattern.py` and the additive `control/facts.py` rows) and out of the GUARD
("no new transport") — left for the same future increment that will wire I8's producer.

Tests: `tests/test_context_plane_pattern.py` (new, 18 cases) — the fact-kind/no-new-map-row
check, reducer registration, a pattern derived from real fixture records AND from the REAL
canonical corpus (`canonical_corpus.load_canonical_tables("finding")`, skips gracefully if
unresolved rather than fabricating), grouping independence, the uncertainty estimability floor,
the two coverage-invariant no-phantom cases, non-`finding` evidence being ignored, duplicate-row
dedup, re-derivation byte-stability (forward and reversed input order) and idempotence,
`verify_chain` refusing an unregistered reducer, and the three-layer ADVISORY-uncitability
proof. `tests/test_context_plane_facts.py` widened (2 exact-set assertions +1 row each).
Full suite green: `pytest tests/ -k "context_plane or dependency_direction"` — 257 passed
(239 pre-existing + 18 new). `ruff check` clean on every touched file. PASS.

## 15. I9 — adversarial release verdict (independent re-verification, this increment)

A second, independent pass over §14's implementation and its own self-report, re-checking every
claim against the tree rather than trusting the prior write-up. Scope: `control/facts.py`'s
`PatternPayload`/`FACT_PREDICATES["pattern"]`, `control/reducers/pattern.py`, and
`tests/test_context_plane_pattern.py`, plus a regression sweep of everything a concurrent,
unrelated I10 checkpoint WIP (`e7b5a8469`, "preserved for resume", touching the SAME
`control/facts.py` and `control/reducers/__init__.py`) could have disturbed.

**D7 (no new `EPISTEMIC_MAP` row) — verified in code, not just asserted by a test.**
`EPISTEMIC_MAP` (`control/facts.py:83-95`) still has exactly the five original keys
(`observed`/`verified`/`derived`/`declared`/`advisory`); `FACT_PREDICATES["pattern"]` carries no
sixth. `test_no_new_epistemic_map_row_was_added` checks the map's key set directly, not a proxy.

**D3 (`verify_chain` mandatory, `is_canonical()` insufficient) — traced through
`control/facts.py:945-1028` line by line.** `is_canonical()` (`:945-957`) indeed checks only
`epistemic_status`/`authority`/`lifecycle_state` — no reducer check, confirming the attack F1
names is real absent D3's fix. `verify_chain()` check 4 (`:1011-1016`) is what actually enforces
"minted by a reducer declared to produce this predicate": it rejects a fact whose
`reducer_version`'s registered `ReducerSpec.produces` does not include `fact.predicate`. One
architectural note, not a defect in this increment: `verify_chain` cross-checks against the fact's
OWN claimed reducer's `produces`, not against `FACT_PREDICATES["pattern"].produced_by` — so the
enforcement boundary is "only code present in the hand-authored `REDUCERS` registry
(`control/reducers/__init__.py`) can mint," not "only exactly one named reducer can." This is the
same trust boundary every other predicate in the plane already relies on (registration is a
source-code change, never a runtime-reachable action for an LLM or caller), so it is not specific
to `pattern` and not a regression this increment introduces — noted for a future increment that
might want `produced_by`-exact enforcement, not a blocker for this one.

**GUARD "no LLM in the minting path" — verified by import-graph inspection, not just absence of
a keyword.** `pattern.py`'s import list (stdlib `json`/`math`/`dataclasses`/`typing` plus
`control.facts`, `control.reducers._common`, `reporting.lab_contract.record_id`) contains no
model/adapter/backend import; `record_id()` (`lab_contract.py:365-384`) is a pure string/hash
function over an already-resolved payload's `_registry` fields — no network, no subprocess, no
LLM call anywhere in the reducer's transitive closure.

**GUARD "no new transport" — verified.** `pattern_v1` performs no Redis/knowledge-stream/file
I/O; it is registered into the SAME `REDUCERS`/`_IMPLS` dicts every existing reducer uses
(`control/reducers/__init__.py:44,56`), consumed by the SAME `scripts/kb_produce_facts.py`
pipe every other reducer already goes through. No new persistence path was added.

**The four required test scenarios, verified present and load-bearing (not just named):**
"a pattern derived from real campaign records" —
`test_pattern_derived_from_real_records` (synthetic-but-real-shaped rows) AND
`test_pattern_derived_from_the_real_canonical_corpus` (§1b, mines
`canonical_corpus.load_canonical_tables("finding")` for real, skips rather than fabricates when
unresolved — actually exercised in this environment, not skipped: the corpus resolved and the
test minted real facts). "An ADVISORY proposal is uncitable" —
`test_advisory_pattern_proposal_is_uncitable_by_validate_decision_c5` builds a REAL
`ContractSpec`/`ControlContext`/`ControlDecision` and calls the REAL `validate_decision`, and the
refusal is confirmed to land on check `C5` specifically (not an earlier short-circuit — C1-C4 are
satisfied first). "Re-derivation stability" —
`test_re_derivation_from_the_same_evidence_is_byte_stable_regardless_of_order` compares
`fact_entity_id`/`value`/`evidence_ids`/`inputs_digest` byte-for-byte between forward and
reversed input order. "A pattern with no real support cannot be minted" —
`test_empty_population_mints_no_fact` (zero rows) and
`test_unmeasured_outcomes_alone_mint_no_fact` (rows present, no real measured outcome) both
assert `== []`; verified this is distinct from the legitimate "real slice, zero successes" case
(`payload.support == 0` from real rows is a permitted, non-phantom fact under §3.3 — the reducer
does not conflate "no evidence" with "evidence of absence").

**Regression sweep against the concurrent I10 WIP.** `tests/test_context_plane_checkpoint.py`
(the I10 WIP's own test file) fails to collect (`ImportError: cannot import name
'FactRequirement' from control.facts`) — confirmed out of scope for I9 (I10 is explicitly
"preserved for resume", not part of this increment's DELIVER). Every other test touching the
files the WIP commit shares with I9 (`control/facts.py`, `control/reducers/__init__.py`,
`control/decisions.py`, `control/rules.py`) is green:
`pytest tests/ --ignore=tests/test_context_plane_checkpoint.py -k "control or context_plane or
dependency_direction or fact or decision or rule or validator or knowledge"` — 503 passed, 0
failed. `pytest tests/ -k "context_plane or dependency_direction"
--ignore=tests/test_context_plane_checkpoint.py` — 257 passed (matches §14's own count exactly,
confirming the WIP introduced no drift into I9's surface). `ruff check
src/agentic_dynamics/control/reducers/pattern.py src/agentic_dynamics/control/facts.py` — clean.

**Verdict: PASS.** No code change required by this pass — §14's implementation holds up under
independent adversarial re-verification. The one note above (registry-membership vs.
`produced_by`-exact enforcement) is recorded as an accepted, plane-wide architectural property,
not a finding against this increment.

## 16. I10 — `SessionCheckpoint` + the `session_routing` contract (`control/checkpoint.py`,
`control/reducers/checkpoint.py`, `experiments/contexts/session_routing.yaml`)

Implements `docs/designs/current/context_abstraction_addendum_design.md` §4 (answers OQ6/OQ7)
against the REAL I0–I9 code. Proposal-only actuation throughout; `apply` stays OFF — this
increment adds no `make_applying_router`-equivalent for `session_routing` (only
`record_shadow_decision`, reused verbatim), and no committed spec's `workflow.params.control_route`
is ever `true` (verified over the real corpus, `test_no_committed_spec_opts_a_control_route_into_
session_routing`). This section picks up a checkpoint of PARTIAL work an earlier session left
("wip: d3 checkpoint partial work (decisions/facts/reducers) preserved for resume") — most of the
schema/reducer/rule/contract already existed; this pass found and fixed one material defect in the
inherited work (below) before treating the increment as done.

**Schema (`control/checkpoint.py`, new reserved home per design §6).** `SessionCheckpoint` is a
frozen dataclass with the per-field epistemic grades design §4.1's own table specifies, INCLUDING
the two demotions the accepted design's own deviations D1/D2 require (not the addendum's literal
wording — see the note below): `goal`/`completed`/`current_revision`/`acceptance_state` are
DERIVED (design's grade, unchanged); `context_snapshot_id` is `str | None = None` plus a NEW
`snapshot_available: bool = False` marker (D2 — no snapshot producer exists until I4 gains a real
capture call site); `verified_facts` is ADVISORY, not DERIVED (D1 — no canonical `fact`
`source_type` exists to cite); `open_hypotheses`/`failed_approaches`/`next_action` are ADVISORY
(unchanged). `DERIVED_FIELDS`/`ADVISORY_FIELDS` are the machine-checkable form of the split, with
an import-time completeness assert (every field graded exactly once, disjoint, exhaustive) mirroring
`EPISTEMIC_MAP`'s own self-checking pattern. `derived_payload()`/`advisory_payload()` implement D5
(resolving addendum design's own adversarial finding F3): the two payloads share zero keys, so an
ADVISORY narrative edit can never re-key the canonical fact's identity, and a controller citing the
checkpoint fact can never receive un-citable content at fact granularity.

**A note on this task's own DELIVER text vs. the accepted design.** The prompt's shorthand groups
`verified_facts`/`context_snapshot_id` under "DERIVED" — this is the addendum's OWN pre-deviation
wording, not the design that was actually accepted after review. The accepted design's §4.1 table,
its D1/D2 deviation-table rows, and adversarial finding F3 (§9) are unambiguous about why a literal
DERIVED grade for these two fields is a hard-rule-4 violation (an un-produced field masquerading as
measured/derived). Per this task's own GOAL line ("per the accepted addendum design"), the shipped
code follows the ACCEPTED DESIGN, not the prompt's paraphrase — documented in `control/checkpoint.
py`'s own module docstring and here, exactly as every other genuine deviation in this plane is
recorded: explicitly, never silently.

**The reducer (`control/reducers/checkpoint.py`, new — the design's own reserved home).**
`CHECKPOINT_V1`/`checkpoint_v1` is the sole registered producer of `session_checkpoint` and five
POSITIVE-MARKER booleans (`checkpoint_present`, `checkpoint_goal_unchanged`,
`checkpoint_phase_unchanged`, `checkpoint_model_unchanged`, `model_change_required`) plus a sixth,
`checkpoint_snapshot_identity`, declared in `FACT_PREDICATES` but structurally NEVER emitted in v1
(D2 — same "declared producer, chooses not to fire" posture `context_snapshot_id` itself takes).
Each marker is emitted ONLY as `"true"`, and ONLY when real evidence supports it — a false/changed/
unmeasured condition is represented by the fact's ABSENCE, never a fabricated `"false"` (the same
no-phantom discipline `control/reducers/pattern.py`, I9, already established). `checkpoint_from_run`
derives the DERIVED fields purely from a typed `WorkflowRunResult` dict (`completed` via a
git-I/O-free proxy — phase names with `status == "ok"` — since a pure reducer may never touch a live
git repo; `acceptance_state` combines `ok` with any real `test_executed_success` into one of
`verified_pass`/`verified_fail`/`unverified_ok`/`unverified_fail`). The `session_current` evidence
tag is reducer-local (not a `knowledge.SOURCE_TYPES` row, no new transport) and is joined to its
`workflow_run` by `spec_name` alone, deliberately narrower than the checkpoint's own `cell_id`
(spec_name+model) join — the one join key permissive enough to let `model_change_required` detect
the exact case (a different model in the "current" state) that predicate exists to catch.

**Contract (`experiments/contexts/session_routing.yaml`, new — the design's own reserved home).**
`allowed_actions: [continue, fork, compress_and_fork, escalate]`, `max_snapshot_age_seconds: 300`
(REUSE the frozen design's own figure), `invariants: []`. All four actions are proposal-only:
`AUTOMATABLE_ACTIONS` (`control/decisions.py`) stays exactly `{continue, route}`, unwidened;
`PROPOSABLE_ACTIONS` gains `fork`/`compress_and_fork` (`escalate` already existed from I6, reused
by name — a real actuation, a model change, never applied by this increment either).

**MATERIAL FINDING, found and fixed in this pass — `on_missing: halt` under `requires_facts` is
NOT "soft".** The addendum's own §4.2 YAML sketch groups five action-specific facts
(`checkpoint_goal_unchanged`/`_phase_unchanged`/`_model_unchanged`/`checkpoint_present`/
`model_change_required`) under an UNCONDITIONAL `invariants:` list — logically unsatisfiable,
because `checkpoint_model_unchanged` and `model_change_required` are MUTUALLY EXCLUSIVE by the
reducer's own positive-marker convention (exactly one fires per session with a checkpoint), so two
`on_missing: halt` invariants that can never BOTH be satisfied make the contract permanently
inadmissible — and `checkpoint_present: on_missing: halt` would ALSO permanently block a legitimate
first phase (no checkpoint yet). The inherited WIP correctly identified this (documented in the
contract file's own header, and proven mechanically by
`test_the_addendums_own_literal_invariant_grouping_would_be_refused_by_r11`, which reproduces the
addendum's literal grouping and shows R11 refuses it) and moved all five facts to `requires_facts:`
— but LEFT `on_missing: halt` on all five. This does not fix anything: `control/context_compiler.py`'s
`compile_context`/`_apply` helper applies `on_missing in {halt, escalate} -> admissible = False`
IDENTICALLY for `contract.invariants` and `effective_requires_facts` (`context_compiler.py:764-801`)
— nothing about the `requires_facts:` heading is inherently softer; only `on_missing: classify`/
`investigate` degrade without blocking admissibility. Verified empirically before touching the YAML:
a bare first-phase `ContextRequest` (only `workflow_phases_remaining` supplied, zero checkpoint
facts) against the shipped contract came back `admissible=False` — the EXACT bug the file's own
header claims to have resolved, reintroduced under a different heading, and (worse) unconditional
for every session with a checkpoint too, since `checkpoint_model_unchanged`/`model_change_required`
can never both resolve. **Fix:** the five action-specific facts now use `on_missing: classify` — an
absence is recorded as an `Unknown` (visible on `ControlContext.unknowns`) but never blocks
admissibility; `control.rules.session_routing_v1` reads their presence/absence from `ctx.job` via
`_find()` and does the actual per-action refusal at the RULE level (continue only when all three
equality markers resolved; escalate only when `model_change_required` resolved; fork as the safe
default once continuation cannot be proven; continue with nothing to compare against, on a first
phase, when no checkpoint exists at all). `workflow_phases_remaining` keeps `on_missing: halt` — it
is the one entry that is NOT action-scoped (every action needs it), REUSE of `route_next_job.yaml`'s
own precedent. Re-verified empirically post-fix across five scenarios (first phase, unchanged
session, model-changed, goal-changed, and genuinely STALE equality markers past the 600s TTL): all
five now come back `admissible=True` with the mechanically correct action proposed, including the
stale case correctly falling through to `fork` rather than `continue`.

**Validator enforcement (R11, "invariant-halt semantics").** `invariants: []` trivially satisfies
R11 (an invariant whose `on_missing` is outside `{halt, escalate}` is refused — I5, `core/
contracts.py`, `implementation_notes.md` §10.2); `test_shipped_session_routing_contract_never_
fails_r11` / `test_all_committed_contracts_pass_r11_via_load_all_contracts` check this against the
real loader over the real committed corpus. `test_the_addendums_own_literal_invariant_grouping_
would_be_refused_by_r11` is the adversarial proof R11 would in fact catch the addendum's own
literal (pre-deviation) invariant grouping, which is WHY this contract's real shape moves those
facts to `requires_facts` instead.

**The shadow control rule (`control.rules.session_routing_v1`, design §4.2/§4.3).** Reads the
(possibly-absent) marker facts from a compiled `ControlContext.job` and proposes exactly one of
`{continue, fork, escalate}` (v1 never proposes `compress_and_fork` — its trigger, context-token
growth past a threshold, has no measured signal yet; declared in `allowed_actions` for a future,
evidenced rule, never fabricated by this one). The session-continuation `continue` this function
proposes is a DIFFERENT decision from `route_next_job_v1`'s routing null-action `continue` (design
F4) — same string, different meaning — which is why `AUTOMATABLE_ACTIONS` must NOT be widened to
admit it; `control/decisions.py`'s own comment on `AUTOMATABLE_ACTIONS` documents this explicitly.
Every proposal is only ever recorded (`record_shadow_decision`, reused verbatim — no new recording
path) and surfaced; an automated `policy_rule:session_routing`-sourced proposal for a
non-automatable action (`fork`/`compress_and_fork`/`escalate`) is correctly REFUSED by check C9 in
`validate_decision` (the same `is_human = proposed_by.startswith("operator:")` rule
`test_c9_non_automatable_action_from_an_automated_proposer` already establishes for
`route_next_job_v1`'s own `retry` proposals) — `result.admitted is False`, `check == "C9"`. This is
the GUARD made mechanical, not merely asserted: an automated `fork` proposal is structurally
ineligible to be treated as authorized, regardless of how well-evidenced its `facts_used` is.

**Tests found needing a fix, and why (all in the inherited `tests/test_context_plane_checkpoint.py`,
39 → 38 cases after consolidation).** (1) `FactRequirement` was imported from `control.facts`
(where it does not live) instead of `core.contracts` (I5's actual home, `core/contracts.py:50`) —
a plain `ImportError` blocking collection of the entire file; fixed by moving the import. (2) The
original `test_continue_with_a_stale_snapshot_is_refused_by_c5` conflated "absent" with "stale":
it built a snapshot with ZERO checkpoint facts and asserted `ctx.admissible is False` — true only
because of the `on_missing: halt` bug above, and testing the wrong thing (the DELIVER text asks for
STALE, not merely first-phase-absent, which is a legitimate non-refusal case covered by a separate
test). Rewritten as `test_continue_with_a_stale_snapshot_is_refused`: genuinely stale equality
markers (`observed_at` ~4 days before `now`, past the contract's `max_age_seconds: 600`), asserting
(a) the rule structurally never proposes `continue` once the markers are unresolvable — it falls
through to `fork` — and (b) a hand-crafted decision that wrongly claims to cite one of the
excluded-as-stale fact_ids still fails C5, belt and braces. (3)
`test_real_rule_never_proposes_fork_without_citing_checkpoint_present` asserted
`result.admitted is True` for an automated `fork` proposal — backwards: `fork` is proposal-only by
design, so C9 correctly refuses it, and asserting `admitted is True` would have been asserting the
GUARD's own violation had the code actually behaved that way. Rewritten to assert the decision's
`facts_used` genuinely cites `checkpoint_present` (the honesty property the test name promises) AND
that `validate_decision` refuses it via C9 specifically — turning a backwards assertion into a
positive proof of "apply stays OFF" for this action. (4)
`test_no_committed_spec_opts_a_control_route_into_session_routing` grepped the whole `experiments/`/
`workflows/` tree for the bare substring `"session_routing"` and asserted zero hits outside the
contract YAML — a false positive against legitimate, unrelated prior CAP work already committed to
this branch (an evidence-seed experiment definition, a retrospective analysis, spec-authoring
workflow prose) that references the topic name without doing any runner wiring. Rewritten to reuse
the EXACT check I7's own gate already established
(`test_context_plane_seam.py::test_no_committed_spec_opts_into_control_route`): load every committed
spec and assert `workflow.params.control_route` is never truthy — the actual wiring seam, checked
against the real corpus, not a name collision.

**Ruff.** `I001` (import ordering), five `SIM300` (Yoda-condition set-equality assertions), and one
`B017` (blind `pytest.raises(Exception)`, narrowed to `dataclasses.FrozenInstanceError`) — all
pre-existing style debt in the inherited test file, fixed (`ruff check --fix` plus one manual
narrowing); `ruff check` clean on every touched file after.

Tests: `tests/test_context_plane_checkpoint.py` (38 cases, 4 fixed per above) — the schema's
epistemic split and payload separation, the reducer's positive-marker/no-phantom/D2-never-emitted/
join-key/re-derivation-stability properties, the real contract's R11-cleanliness and the addendum's
own literal grouping failing R11 (proving why this shape differs), `session_routing_v1`'s four-way
branching including the stale-continue and checkpointless-fork refusals via the real validator,
shadow-only recording (`record_shadow_decision`, never `publish_event`), and
`AUTOMATABLE_ACTIONS`/`control_route` immutability over the real corpus.
`tests/test_context_plane_facts.py` widened by the inherited WIP (`test_predicate_registry_has_
the_design_seed_rows` +7 rows; `test_predicate_inheritance_flags_match_the_design_table` needed no
change — all six new predicates are job-scoped, non-inheritable, exactly as design).

Full suite green: `pytest tests/test_context_plane_checkpoint.py` — 38 passed.
`pytest tests/ -k "control or context_plane or dependency_direction or fact or decision or rule or
validator or knowledge or contract"` — 626 passed, 0 failed (up from I9's 503 baseline: +38
checkpoint + the rest already counted). `pytest tests/test_dependency_direction.py` — 11 passed
(no tier violation: `control/checkpoint.py` and `control/reducers/checkpoint.py` both stay tier-2
control code; `core/contracts.py`, I5's existing home, was not modified — only a test's import
path was corrected). `ruff check` clean on every touched file. A full untargeted `pytest tests/ -q`
run exceeds this environment's practical timeout (consistent with §15's own note) — the targeted
sweep above is the regression signal, covering every plane this increment (and the concurrent WIP
it resumed) touches. PASS.

## 17. I8-I10 — adversarial release verdict (six attack vectors, this pass)

**Role:** external adversarial reviewer, per the six vectors this pass's own prompt names. Each
vector was worked against the REAL tree (not the design doc's sketch), re-verified by running
the code, not just reading it. Two vectors produced MATERIAL findings; both are fixed, with
regression tests proving the fix and proving the exploit is closed. One vector produced a
material finding that is an ACCEPTED LIMITATION (inherited from I0, out of this addendum's
reserved-homes scope to redesign). Three vectors found nothing beyond what §13-§16 already
established, and are recorded here as independently RE-verified, not merely re-asserted.

### Finding table

| # | Vector | Finding | Severity | Resolution |
|---|---|---|---|---|
| G1 | I8 — can a profile widen a controller's view past its contract? | **Yes, found a concrete path.** `compose_requirements` validated NOTHING about a profile's OWN `context_requirements` entries when the fact was NOT already in the contract's `requires_facts` — `tighten()`'s rank-comparison defense (§13, D4) only activates when the SAME fact is already present; a BRAND-NEW fact skips it entirely (`merged[req.fact] = req`, used as-is). Concretely: a `ChallengeProfile.context_requirements` entry naming a real predicate (e.g. `checkpoint_present`) with `min_authority="ADVISORY"` composed cleanly, and — verified end to end through the REAL `compile_context` — let an ADVISORY-graded fact resolve into `ControlContext.job` (the bucket the compiler's own docstring documents as the decision's CITABLE context), duplicated into `ControlContext.advisory` too. A decision that then CITES the fact_id in `facts_used` is still refused by check C5 (which independently re-derives "is this fact advisory" from the fact's own `epistemic_status`, never from which bucket it landed in) — but nothing forces a control RULE to cite every fact_id it reads out of `ctx.job` via `_find()`; a rule that only used the (wrongly-admitted) VALUE to branch, without recording provenance, would be silently influenced by an unverified advisory judgment with zero trace and zero refusal downstream. | **Material** | **Fixed** — `_validate_context_requirement` (new, `control/profiles.py`) rejects a profile-supplied `FactRequirement` whose `min_authority`/`on_missing`/`on_conflict`/`scope` falls outside the SAME closed vocabularies `core.contracts` already enforces for spec-authored rules (mirrors R1/R2/R5/R7), and whose `fact` names an undeclared or unproduced predicate (mirrors R1/R2) — closing the gap `validate_fact_contracts` never covered in the first place (that function only iterates `spec.rules` and each loaded contract's `invariants`; a profile's `context_requirements` are composed at `compile_context` RUNTIME, a path R1-R8 was never wired to see). 4 new tests in `tests/test_context_plane_profiles.py`: the exploit reproduced end to end through the real `compile_context` and refused; the pure `compose_requirements` unit refusing bad `min_authority`/`on_missing`/an unknown predicate. 4 pre-existing tests whose fixtures used fictional fact names ("a"/"b") in a profile's OWN `context_requirements` were updated to real, registered predicates (`checkpoint_present`, `workflow_phases_remaining`) — the fictional names on the CONTRACT side (never validated by this new check) were left as-is. |
| G2 | I9 — can a pattern become canonical without a deterministic reducer, or with fabricated support? | **The "without a reducer" half: no** — §15 already re-verified D3's `verify_chain` enforcement holds (an unregistered/wrong reducer_version is refused). **The "with fabricated support" half: yes, found a concrete path `verify_chain` does not close.** `facts.recompute_inputs_digest`'s own docstring is explicit that it implements only PART of the design's formula: `sha256(evidence_ids | reducer_version | input VALUES)` — I0 hashes only the input IDENTITIES and `reducer_version`, "the portion recoverable from the fact alone"; the "input values" term is explicitly out of scope ("not part of this self-contained check"). Concretely: a `pattern` fact keeping a REAL fact's genuine `evidence_ids`/`reducer_version`/`epistemic_status`/`authority` verbatim, but with a hand-fabricated `value` (support/uncertainty inflated far past what those cited records actually show — verified with `support=4` substituted for a real count of `1`), reproduces its own `inputs_digest` (the digest never touched `value`), passes ALL FIVE `verify_chain` checks with zero errors, and `is_canonical()` returns `True`. | **Material, ACCEPTED LIMITATION** | **Not fixed — recorded, with a pinning test.** This is an INHERITED I0 architectural property (the digest formula's own scope, documented as deliberate by I0's own docstring), not something D3's "verify_chain is mandatory for pattern" rule was ever meant to close (D3 makes verify_chain MANDATORY for the class; it does not change what verify_chain itself checks) — and it is PLANE-WIDE (every reducer's fact, not `pattern`-specific). A proper fix needs a `resolve` callable that returns FULL evidence PAYLOADS (not just registry metadata, which is all `verify_chain`'s `resolve` parameter is contracted to return today) so a fact's claimed value could be re-derived and compared — that resolver does not exist anywhere in this plane yet (the same producer-wiring gap §14 already noted for `pattern_v1` itself), and building one touches shared I0 infrastructure (`facts.verify_chain`/`recompute_inputs_digest`) well beyond I9's reserved home. `test_known_limitation_verify_chain_does_not_catch_a_fabricated_value_on_real_evidence_ids` (new, `tests/test_context_plane_pattern.py`) pins the gap: if a future fix to `verify_chain`/`recompute_inputs_digest` closes it, THIS test starts failing and must be updated on purpose, never silently. |
| G3 | I10 — can an ADVISORY checkpoint field leak into a DERIVED claim, or a proposal leak into `AUTOMATABLE_ACTIONS`? | **No leak found, on either half — independently re-verified, not merely re-asserted.** `DERIVED_FIELDS`/`ADVISORY_FIELDS` share zero keys (import-time assert in `control/checkpoint.py`); `derived_payload()` is a POSITIVE allowlist keyed off `DERIVED_FIELDS`, so a future field added to `SessionCheckpoint` without classifying it crashes at import, never silently leaks. `AUTOMATABLE_ACTIONS` stays exactly `{continue, route}` (`control/decisions.py`, untouched); traced `make_applying_router` (I7) and confirmed it is hardcoded to `route_next_job` and only ever applies `action == "route"` — `session_routing_v1` never proposes `"route"`, so there is structurally no path for a session-routing proposal to reach the one function in the whole plane that can change what executes. One property worth making EXPLICIT rather than assumed: `record_shadow_decision` does **not** call `validate_decision` — it records EVERY proposal unconditionally (by design: "recorded" is meant to capture the plane's full decision history for later audit/comparison, independent of whether that decision would be ADMITTED). Verified directly: the SAME automated `fork` proposal C9 refuses to admit (`policy_rule:session_routing`, not `operator:`) is still successfully recorded. | — (confirmatory) | New test `test_recording_is_unconditional_even_for_a_decision_c9_would_refuse` (`tests/test_context_plane_checkpoint.py`) makes this property explicit and load-bearing in the suite, rather than leaving it as an implicit consequence other tests happen not to contradict. |
| G4 | I10 — does `session_routing`'s `continue` invariant hold under a re-derived snapshot (TOCTOU)? | **No, found a concrete gap.** `validate_decision`'s check C7 (`validator._c7_freshness_and_preconditions`) does two independent things: (a) a pure snapshot-AGE check against `now`, and (b) a per-`Precondition` re-check against a FRESHLY compiled snapshot — but (b) is a no-op when `decision.preconditions == ()` (the dataclass default). `session_routing_v1`'s `continue` branch (the one action whose entire safety claim IS "goal/phase/model are PROVABLY unchanged") never set `preconditions` at any of its 5 `ControlDecision(...)` construction sites — so C7 degraded to JUST the age check for `continue`, which catches "the snapshot is too OLD" but not "the world changed within the freshness window" (verified: a `continue` compiled while goal/phase/model all resolved `True`, re-checked against a fresh snapshot where the goal has since changed — still well inside `max_snapshot_age_seconds: 300` — was WRONGLY ADMITTED before the fix). `route_next_job_v1` (I6) already established the correct pattern for its own `route` proposal (`workflow_phases_remaining`, re-checked via a `Precondition`) — `session_routing_v1` had not followed it. | **Material** | **Fixed** — `continue`'s `ControlDecision` now carries a `Precondition(fact=<marker>, op="is_true", ...)` for each of the three equality markers (`checkpoint_goal_unchanged`/`_phase_unchanged`/`_model_unchanged`), mirroring `route_next_job_v1`'s own established pattern verbatim (`op="is_true"` matches the reducer's own positive-marker convention: a marker is present-and-`"true"`, or absent — there is no `"false"` value to compare against). Verified end to end (by hand, then pinned in tests) that a stale `continue` — admitted under the OLD code — is now REFUSED (`check="C7"`) against a fresh snapshot where a marker no longer resolves, while a `continue` re-checked against an UNCHANGED fresh snapshot is still correctly admitted (the non-regression half). 3 new tests in `tests/test_context_plane_checkpoint.py`. |
| G5 | Dependency direction / tier map for the new/modified modules | **No violation.** `control/profiles.py`'s new imports (`MIN_AUTHORITY_LEVELS`/`ON_CONFLICT`/`ON_MISSING`/`SCOPE_KEYWORDS` from `core.contracts`) are control (tier 2) importing core (tier 0) — the correct direction, already an established edge (`ContractLike`/`FactRequirement` were already imported from the same module). `control/reducers/pattern.py`'s `reporting.lab_contract` import is control (tier 2) importing reporting (tier 1) — downward, permitted (only the REVERSE, tier-1-importing-tier-2, is restricted to the one pinned adapter-telemetry seam `test_tier1_to_tier2_edges_are_exactly_pinned` checks). `core/contracts.py` itself was not modified and remains zero-import pure stdlib. | — (confirmatory) | `pytest tests/test_dependency_direction.py` — 11/11 passed. Direct import of every touched module (`profiles`, `checkpoint`, `reducers.checkpoint`, `reducers.pattern`, `rules`, `facts`, `core.contracts`) succeeds with no circular-import or tier error. |
| G6 | Regression to I0-I7 suites + the apply-stays-OFF guarantee | **No regression.** Both committed apply-seam guards were re-run directly and independently: `test_context_plane_seam.py::test_no_committed_spec_opts_into_control_route` (I7's own gate, `route_next_job`) and `test_context_plane_checkpoint.py::test_no_committed_spec_opts_a_control_route_into_session_routing` (I10's, rewritten in the prior pass to use the SAME `control_route`-based check) both pass — no committed spec anywhere sets `workflow.params.control_route: true` for EITHER decision type. | — (confirmatory) | The EXACT §16 filter (`pytest tests/ -k "control or context_plane or dependency_direction or fact or decision or rule or validator or knowledge or contract"`) — **635 passed, 0 failed** (up from §16's own 626 baseline by exactly +9, matching the 9 new test cases this pass added: 4 in G1, 1 in G2, 1 in G3, 3 in G4). A WIDER net adding `experiment_spec`/`compile_experiment`/`kb_produce`/`seam` (pulling in pre-existing tests §16's filter did not select, not just this pass's new ones) — **679 passed, 0 failed**. `ruff check` clean on every touched file (`control/profiles.py`, `control/rules.py`, `tests/test_context_plane_{profiles,pattern,checkpoint}.py`). A full untargeted `pytest tests/ -q` still exceeds this environment's practical timeout (§15/§16's own note, unrelated to this pass — likely slow/skip-gated integration tests elsewhere in the 1900+ test corpus); the targeted sweep is the regression signal. |

### Release verdict

**I8, I9, and I10 are MERGE-READY**, with the two material findings (G1, G4) fixed and
regression-tested in this same pass, and one material-but-accepted limitation (G2) explicitly
documented rather than silently present. `apply` stays OFF throughout — verified structurally
(G3, G5, G6), not merely asserted: `AUTOMATABLE_ACTIONS` is untouched, no apply seam exists for
`session_routing` at all, and no committed spec opts into `route_next_job`'s existing one either.
Proposal-only actuation holds for every I10 action (`continue`/`fork`/`compress_and_fork`/
`escalate`): all four are recorded (unconditionally, by design — G3) and none are ever applied.

**Follow-ups (not blockers for this merge):**

1. **The static-profile-filing migration** — `control/profiles.py`'s own `migrate_static_filing()`
   is the deliverable; the CONSUMER wiring (`scripts/run_workflow.py`'s phase-prompt rendering
   calling it, replacing `workflows/repository/cap_addendum_implement.yaml`'s free-text
   `context.domain_context`/`challenge_context` prose) is explicitly NOT done — documented as a
   3-step swap procedure in the module's own MIGRATION section (§13).
2. **The prospective session-routing evidence-seed experiment** (design §4.4) — gated on real
   checkpoint records existing at volume; also gated on instrumenting `cost_inference`/
   `cache_hit`/`service_time_ms`/`rework_cost`/`attempt_number` (currently declared-not-written,
   per F5's own resolution in the addendum design). Specified, not run.
3. **Producer wiring for `pattern/v1` and `profiles/v1`** — `scripts/kb_produce_facts.py`'s
   `derive_facts()` dispatcher has no branch for either (§13/§14's own "Deliberately NOT done"
   notes); until it does, neither reducer is reachable from a real production ingestion run.
4. **G2's value-fabrication gap** (this pass) — a longer-term, I0-scoped follow-up: extend
   `verify_chain`'s `resolve` contract (or add a parallel check) to compare a fact's claimed
   `value` against a fresh re-derivation from its cited evidence PAYLOADS, not just confirm the
   citations exist. Plane-wide, not `pattern`-specific — affects every DERIVED fact's `value`
   field, though `pattern` is the class most likely to have downstream policy weight riding on
   an unverified number.
5. **A pre-existing, plane-wide R1-R8 gap this pass's G1 fix does NOT extend to**: `core.contracts.
   validate_fact_contracts` validates a SPEC's own `rule.requires_facts` and every loaded
   contract's `invariants` (R11), but never a loaded CONTRACT's own `requires_facts` against
   R1-R8 (predicate exists, has a producer, legal `min_authority`, etc.) — only a REFERENCING
   rule's requirements get that scrutiny. Neither `route_next_job.yaml` nor `session_routing.yaml`
   currently exploits this (both use legal values throughout, re-checked while investigating G1),
   but nothing STRUCTURALLY prevents a future hand-authored contract from doing so. Worth closing
   for defense-in-depth in a future I5-scoped pass — out of this addendum's own reserved homes.

**PASS.**
