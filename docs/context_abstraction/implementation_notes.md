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
