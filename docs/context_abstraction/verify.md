# Context Abstraction Plane — Verification

**Spec:** `experiments/specs/context_abstraction_plane.yaml`
**Phase:** `verify` (phase 3 of 3 — `review` → `design` → **`verify`**)
**Verifies:** `docs/context_abstraction/review.md` (phase 1), `docs/context_abstraction/design.md` (phase 2)
**Date:** 2026-08-20 · **Model:** anthropic/claude-opus-5 · **Branch:** `feature/context-abstraction-plane`

---

## 0. Method

Every check below was **executed**, not asserted. Where a check is mechanical (git state,
citation accuracy, section coverage) the command and its output are summarised; where a check is
a judgment (does mechanism X actually satisfy claim Y) the reasoning is given and the specific
design section is named.

Three properties this report deliberately has:

1. **It reports what it ran.** A verification that only restates the design's own claims verifies
   nothing. The 34 citation spot-checks in §5 re-read the cited source ranges independently of
   the review and design phases.
2. **It found things.** Six findings are recorded in §9, one of them material (F1). A verify
   phase that finds nothing on a 1,453-line design is not a verify phase.
3. **A finding is not automatically a FAIL.** A required check FAILs when the requirement is
   unmet. A defect in something the design *did* deliver is recorded as a finding against that
   check with its severity, and the check's status states plainly whether the requirement is
   still met.

---

## 1. Summary — PASS/FAIL per required check

| # | Required check | Status | Evidence |
|---|---|---|---|
| **V1** | Design-only boundary: only `docs/context_abstraction/*` added/modified; no `src/`, `scripts/`, `tests/` changes | **PASS** | §2 — `git status --porcelain` empty; `git diff --name-only HEAD` empty; two workflow commits touch only `docs/context_abstraction/` |
| **V2** | Every `design_input` item traced to a concrete mechanism in `design.md` | **PASS** | §3 — all 9 items mapped to a named section + mechanism |
| **V3** | All seven `open_questions` answered with a schema/sketch, not prose | **PASS** (2 deviations noted) | §4 — 5 of 7 answered with fenced dataclass/YAML; OQ3 and OQ7 answered with structured tables (F5) |
| **V4** | The generalized load-bearing rule is enforceable: every consumed fact has a declared producing source or reducer, and all five refusal conditions are specified | **PASS** | §5 — `FACT_PREDICATES.produced_by` non-empty invariant + R1–R10 compile refusals + the five runtime conditions at `design.md:1065` |
| **V5** | The review's component-audit citations are preserved; no design claim contradicts the audited code state | **PASS** | §6 — 34/34 independent citation spot-checks PASS; 4 quantitative claims re-verified |
| **V6** | The observe-only supervisor boundary is preserved | **PASS** | §7 — design adds zero call sites to `supervise.py`/`supervisor.py`; actuation stays unarmed; `AUTOMATABLE_ACTIONS` is code, not config |
| **V7** | The existing authority hierarchy is preserved | **PASS** | §8 — no tier added, no reorder; `is_canonical` consumes the existing `IntEnum` ordering; `SOURCE_TYPES` gains one additive row |

**Overall: PASS with six findings** (one material, four minor, one confirmed non-issue). None
blocks the pull; F1 should be fixed before the design is implemented, and §9 says exactly how.

---

## 2. V1 — Design-only boundary · **PASS**

```
$ git status --porcelain
(empty)

$ git diff --name-only HEAD
(empty)

$ git rev-parse --abbrev-ref HEAD
feature/context-abstraction-plane

$ git log --oneline -3
69c33db1e [workflow] design  — Review the existing architecture against the Context Abstrac
a72c78a21 [workflow] review  — Review the existing architecture against the Context Abstrac
28bdb168e Add context_abstraction_plane spec: opus-5 review + design of the Canonical …
```

The working tree is clean and the two phase commits are the runner's own
`[workflow] <phase>` commits. Files added across the run:

| File | Phase | Lines |
|---|---|---|
| `docs/context_abstraction/review.md` | review | 529 |
| `docs/context_abstraction/design.md` | design | 1,453 |
| `docs/context_abstraction/verify.md` | verify (this file) | — |

**Nothing under `src/`, `scripts/`, `tests/`, `admin/`, `firebase/`, or `experiments/` was
created, modified, or deleted.** Hard rule 1 (DESIGN ONLY) is satisfied.

*Note on scope, for the implementer:* the design proposes future edits to `knowledge.py`
(one additive `SOURCE_TYPES` row) and `kb_worker.py` (consumer skip for `source_type="fact"`).
Neither is made here. `knowledge.py` is on hard rule 7's protected list, so §6.2 of this report
examines whether "one additive registration row" is genuinely registration rather than redesign.

---

## 3. V2 — `design_input` item tracing · **PASS**

Each of the proposal's nine numbered items, traced to the mechanism that implements it. "Mechanism"
means a named schema, function, or rule — not a paragraph agreeing with the item.

| `design_input` item | Design section | Concrete mechanism | Verified |
|---|---|---|---|
| **(1) Six levels L0–L5**, and "a decision receives a PROJECTION across layers, not one complete layer" | §5 (mapping), §6.3 (`ControlContext`) | The snapshot carries per-level tuples (`workload`/`workflow`/`job`/`resource`) populated **only** from the contract's `requires_facts`; §6.1's `excludes:` block names what is withheld | ✔ projection, not a layer dump |
| **(2) Evidence is not canonical state**; every value carries scope/source/validity/authority/level/derivation/evidence | §1 (thesis), §3.1 (`CanonicalFact`) | All seven properties are dataclass fields: `scope_path`, `reducer`+`evidence_ids`, `valid_from`/`valid_to`/`expires_at`, `authority`, `abstraction_level`, `inputs_digest`, `evidence_ids` | ✔ all seven present |
| **(2b) Relevance ranking is not truth resolution** | §2 (loop table), §3.3 | Facts are **excluded from the `kb-chroma-v1`/`kb-neo4j-v1` consumers**, so a fact is structurally unreachable from `retrieval.retrieve()`; retrieval is absent from loop stages 2–4 by design and the table says so | ✔ structural, not conventional |
| **(2c) Exactly one current representation, or explicitly unknown/conflicted** | §3.2, §4.5, §6.3 | Version-chain identity (one slot = `fact_entity_id`) + `fact_state()` precedence ladder adding `conflicted`; `Unknown` is a distinct snapshot collection with a `reason` | ✔ incl. the review's §4.3 correction that these are new states |
| **(3) `CanonicalFact`** with the proposal's field list | §3.1 | Full frozen dataclass; every proposed field present (`subject`/`predicate`/`value`, `scope_type`, `scope_id`, `abstraction_level`, `authority`, `epistemic_status`, `evidence_ids`, `source_revision`, `observed_at`, `valid_from`, `valid_to`, `expires_at`, `reducer_version`, `supersedes`) | ✔ complete |
| **(4) Deterministic versioned reducers**; LLM statements stay ADVISORY; authority ⊥ abstraction level | §4.1–§4.2, §3.4 | `ReducerSpec` + `Reducer` signature + `ReducerInput` (no I/O, injected clock); `EPISTEMIC_MAP` pins ADVISORY for judgments; `is_canonical()` + validator C5 exclude them; §3.1 documents the four level×authority combinations that force two axes | ✔ incl. the worked `workflow_health/v1` |
| **(5) Context Compiler** — input contract, `ControlContext` output, then decision→validator→executor→ledger→facts loop | §6.1–§6.4, §2 | `route_next_job.yaml` contract; `ControlContext` dataclass with every proposed field (`snapshot_id`, `decision_type`, `scope_path`, `invariants`, `objectives`, per-level tuples, `unknowns`, `conflicts`, `stale`, `evidence_ids`); `compile_context()` 9-step algorithm | ✔ complete |
| **(6) Generalized load-bearing rule** → fact contracts (fact + scope + `max_age_seconds` + `on_missing` + `on_conflict`) | §7.1–§7.3 | `FactRequirement` with exactly those fields (+ `min_authority`, `value_type`); refusals R1–R10; the five runtime conditions | ✔ — see V4 (§5) |
| **(7) Component placement** — KB/retrieval stay evidence; new compiler/agent/validator; `workflow_runner` executes; `step_routing` stays one policy; controller sits AROUND the runner | §2 (loop table), §8.4 | 20-row table placing every existing component; `step_routing.route_step` becomes the reference control rule and measurement baseline; the controller compiles a snapshot *around* `run_workflow`, never inside a phase prompt | ✔ |
| **(8) Hierarchy** org→…→attempt, downward policy / upward facts, controlled inheritance | §10.1–§10.3 | `scope_path` grammar; `scope_visible()` generalizing `scope_excluded` from equality to ancestor-prefix; downward = policy + `inheritable`, **monotone tightening only**; upward = declared reducers only; lateral forbidden | ✔ incl. `cell_scope` ≡ job scope |
| **(9) Agentic Dynamics loop** observe→canonicalize→abstract→decide→execute→measure→update | §2 | ASCII loop + the 20-row placement table + §8.5's hash-linked provenance chain end to end | ✔ |

**Result: 9/9 traced, plus the two sub-claims of item (2). PASS.**

---

## 4. V3 — All seven open questions answered with a schema · **PASS** (2 deviations)

Measured by counting fenced code/YAML blocks per section and inspecting their content.

| OQ | Section | Form of answer | Blocks | Verdict |
|---|---|---|---|---|
| **OQ1** CanonicalFact + identity + evidence resolution + epistemics | §3 | Frozen dataclass, identity formulas, `SourceTypeSpec` row, JSON payload example, `EPISTEMIC_MAP`, `is_canonical()`, `PredicateSpec` + registry table | **6** | **PASS** |
| **OQ2** Reducer model, chains, staleness cascade | §4 | Package layout, `ReducerSpec`, `Reducer`/`ReducerInput`, worked `workflow_health_v1`, persistence pipeline, `verify_chain()`, `fact_state()`, conflict ladder | **7** | **PASS** |
| **OQ3** L0–L5 mapping to existing components | §5 | Structured 6-row × 5-column table naming existing components, new reducers, and ship-time facts | 0 | **PASS**, deviation F5 |
| **OQ4** Context Compiler contracts + snapshot semantics + degradation | §6 | Full `route_next_job.yaml`, `compile_context()` algorithm, `ControlContext`/`FactRef`/`Unknown` dataclasses, halt-vs-degrade table, `snapshot_id` formula | **4** | **PASS** |
| **OQ5** RuleSpec fact-contract extension + what the compiler refuses | §7 | `FactRequirement` + amended `RuleSpec` + `normalize_requirement`, full spec YAML with a control rule, R1–R10 refusal table with error strings | **3** | **PASS** |
| **OQ6** ControlDecision + validator + supervisor boundary | §8 | Action table, `ControlDecision`/`Precondition`/`ExpectedEffect` dataclasses, C1–C10 check table, `AUTOMATABLE_ACTIONS`, provenance chain, actor×permission table | **4** | **PASS** |
| **OQ7** Implementation order (measure-before-policy) | §9 | Structured 9-row increment table (ships / consumed by / gate), the five-reason justification for `spec_status/v1` first, blocked-items table | 0 | **PASS**, deviation F5 |

The spec's wording was "concrete schemas (dataclass or YAML sketches, not prose)". OQ3 is a
**mapping** question and OQ7 an **ordering** question; a table is the precise form for both and is
emphatically not prose. Recorded as deviation **F5** rather than silently passed, because the
literal instruction said dataclass-or-YAML.

**Additionally verified** — the two questions with the highest chance of being answered
hand-wavily were checked in detail:

- **OQ5's "what the compiler refuses"** is answered with ten *named* refusals carrying draft
  error strings in the existing house style (`experiment_spec.py:405-408`, verified §6), not a
  general statement that invalid specs are refused.
- **OQ6's provenance chain** is answered as an eight-link hash chain (§8.5) with the specific
  mechanism that makes the single-valued `causes` field sufficient — registering the snapshot
  itself as an observation record. This is the design's answer to a real limitation the review
  raised (§4.1), not a restatement.

---

## 5. V4 — The generalized load-bearing rule is enforceable · **PASS**

The rule: *no control action may consume a value that is not canonical, current, scope-valid, and
produced by a declared source or reducer.* Enforceability requires three things; all three are
specified.

### 5.1 Every consumed fact has a declared producer — **verified**

`PredicateSpec.produced_by` (`design.md` §3.5) is a non-empty tuple of reducer versions, and
compile refusals **R1** (predicate not in the registry) and **R2** (declared but `produced_by`
empty) make a producerless requirement unspecifiable. **R3** extends this transitively: a
requirement is refused when the required predicate's reducer *consumes* something no reducer
produces — so the whole reduction ladder must exist, not just the top rung.

This is verifiably stronger than today's gate. The review established
(`review.md` §3d(ii), re-verified in §6 below) that 23 `LEDGER_FIELDS` names are declared with
zero writers, and that a rule requiring `deadline_slack` **passes today's `validate_rules`**.
Under R1/R2, `deadline_slack` cannot even be declared as a predicate until something produces it
— and §5/§9 of the design correctly leave it out of the registry and out of increment 1.

### 5.2 The five runtime refusal conditions are specified — **verified**

`design.md:1065`:

> "…the Context Compiler refuses (i.e. returns `admissible=False`) when a required fact is
> **absent**, **stale**, **conflicted**, **out of scope**, or **lacks a valid derivation chain**"

| Condition | Mechanism | Where |
|---|---|---|
| absent | `Unknown(reason="no_fact")` + the entry's `on_missing` | §6.3 |
| stale | `fact_state()` rung 4 (expiry, non-current input, newer reducer) + `max_age_seconds` | §4.5, §7.1 |
| conflicted | `fact_state()` rung 3 + the 4-rung resolution ladder + `on_conflict` | §4.5 |
| out of scope | `scope_visible()` prefix rule; surfaced as `Unknown(reason="out_of_scope")` | §10.2, `design.md:905` |
| no derivation chain | `verify_chain()` failure **demotes to `unknown`** rather than silently including | §4.4, §6.2 step 5 |

### 5.3 The compile-time / run-time split is correct — **verified**

The design states (§7.3): *compile time proves producibility; run time proves currency*, and
explains why either alone is insufficient. This is the direct, correct fix for the review's §4.4
finding. Independently checked: today's `validate_rules` (`experiment_spec.py:373-409`, verified
§6) computes `available = LEDGER_FIELDS ∪ produces`, which is a producibility check only — so the
design's characterisation of the existing gate is accurate, and its addition is exactly the
missing half.

**Additional strength worth recording:** `verify_chain()` is called **twice** — once by the
compiler (§6.2 step 5) and once by the validator (C6). The design justifies this by analogy to
`knowledge_stream.publish_event`'s lineage gate, which fires "even when actuation IS armed"
(verified at `knowledge_stream.py:178-192`). The precedent is real and the posture matches.

---

## 6. V5 — Review citations preserved; no claim contradicts the code · **PASS**

### 6.1 Citation spot-checks: 34/34 PASS

Each check re-read the cited source range and asserted the construct named by the design is
actually there. Executed independently of both prior phases.

| Cited by design as | Verified |
|---|---|
| `retrieval.py:392-406` `scope_excluded` | ✔ |
| `retrieval.py:396-405` empty-scope = unknown/legacy, never global | ✔ |
| `retrieval.py:973-981` hard scope pre-filter | ✔ |
| `retrieval.py:63-71` `AUTHORITY_MULTIPLIER` (POLICY absent) | ✔ |
| `record_factory.py:67-98` `record_to_artifact` | ✔ |
| `record_factory.py:101-195` `build_record` | ✔ |
| `record_factory.py:77-83` blanked volatile timestamps | ✔ |
| `record_factory.py:49-55` injected clock | ✔ |
| `knowledge.py:141` `actuation` `SOURCE_TYPES` row | ✔ |
| `knowledge.py:81-85` `Authority` IntEnum ordering | ✔ |
| `knowledge.py:343` `causes` field | ✔ |
| `knowledge.py:104-119` "documentation + a sanity anchor, not a validator" | ✔ |
| `generate_manifest.py:75-108` `_derive_lifecycle` | ✔ |
| `generate_manifest.py:111-221` `_compact_registry_index` | ✔ |
| `generate_manifest.py:85-94` supersede-by-pointer | ✔ |
| `generate_manifest.py:129-132` tombstone is terminal | ✔ |
| `knowledge_stream.py:178-192` write guard + armed + lineage gates | ✔ |
| `step_routing.py:424-469` `route_step` | ✔ |
| `step_routing.py:96-108` `RoutingPreferences` | ✔ |
| `step_routing.py:10-13` pure-function discipline | ✔ |
| `step_routing.py:184-186` both-declared refusal | ✔ |
| `workflow_runner.py:22-29` shared-scope override | ✔ |
| `experiment_spec.py:164` `RuleSpec.requires` | ✔ |
| `experiment_spec.py:405-408` gate error string style | ✔ |
| `experiment_spec.py:44-103` `LEDGER_FIELDS` | ✔ |
| `knowledge_ingestion.py:466-468` MEASURED-vs-ADVISORY on `test_executed_success` | ✔ |
| `observation_ingestion.py:62-70` timestamp folded into identity | ✔ |
| `actuation_ingestion.py:8-22` zero-call-sites doctrine | ✔ |
| `actuation_ingestion.py:76-88` one identity per candidate | ✔ |
| `compile_experiment.py:142-209` `compare_arms` | ✔ |
| `pipeline_status.py:30-63` `stage_summary` | ✔ |
| `supervise.py:56` "Never recommend steering or interrupting" | ✔ |
| `supervisor.py:1-6` observation metadata only, no OpenCode client | ✔ |
| `docs/supervisor_design.md:104-116` four-part authorization boundary | ✔ |

### 6.2 Quantitative claims re-verified

| Claim | Check | Result |
|---|---|---|
| "60+ spec YAMLs are committed" (design §7.1, motivating backward compatibility) | `ls experiments/specs/*.yaml \| wc -l` | **65** ✔ |
| "the compiler DAG is a fixed 7-node chain" (review §2 row 4; design §5) | `compile_experiment.py:34` — `("validate","cells","execute","measure","compare","writeup","adapt")` | **7** ✔ |
| "`workflow_runner._cell_id` → `wf_<spec>_<model>`" (design §10.1) | `workflow_runner.py:237-240` | ✔ exact |
| "a grep-for-zero-call-sites test, exactly as `actuation_ingestion.py:8-22` does" (design §9, I0 gate) | `tests/test_actuation_ingestion.py:121,140-156` — `test_no_call_sites_construct_actuation_records`, CI-enforced | ✔ **the precedent is a real, executable test**, not a convention |

That last row *strengthens* the design: I0's exit gate ("schema exercised, zero call sites,
enforced by a test") is a pattern the repository already enforces in CI, so the design's most
unusual proposal — ship a schema nothing calls — has a working precedent.

### 6.3 Contradiction sweep — one apparent conflict examined and cleared

**Apparent conflict:** `design.md:310` registers `"fact"` in `SOURCE_TYPES` with nominal
`Authority.DERIVED`, while `design.md:393` maps `epistemic_status="declared"` → `Authority.POLICY`.
A policy-level fact would therefore carry POLICY authority under a source type registered as
DERIVED.

**Cleared.** `knowledge.py:104-119` (verified above) states the `SOURCE_TYPES` authority/evidence
columns are "documentation + a sanity anchor, not a validator", that several types are
context-dependent, and that "each producer's own derivation decides at construction time" — and
`report` is precisely such a case (registered MEASURED, DERIVED from the entropy arm). The design's
arrangement is the existing contract used as intended. Recorded as **F6 (non-issue)** so a future
reader who spots the same thing does not re-open it.

No other design claim contradicts the audited code state.

---

## 7. V6 — Observe-only supervisor boundary preserved · **PASS**

| Requirement | Design's provision | Verified |
|---|---|---|
| The automated supervisor never actuates | §8.6 row 1 and §11 row 9: "This design adds **no call site** to it"; `supervise.py`/`supervisor.py` appear in the design only as *unchanged* | ✔ — three mentions, all "unchanged" (`design.md:133,1234,1415`) |
| Actuation is not armed | §8.6 commitment 1 and §11 row 8: `FINOPS_ACTUATION_ARMED` stays default-off; the design sets it nowhere | ✔ — three mentions, all "default-off" (`design.md:1235,1240,1414`) |
| No new actuation surface | `AUTOMATABLE_ACTIONS = {continue, route}` — both pre-execution, in-process, reversible choices `workflow_runner` already makes via `route_step` | ✔ |
| Irreversible actions stay human-gated | `stop`/`retry`/`escalate` are proposal-only (recorded, surfaced as flags, never applied); `steer`/`interrupt` remain behind the existing four-part boundary | ✔ |
| The boundary is about *who*, not *whether* | §8.6's four-row actor × permission table, which is the design's adoption of the review's §4.2 correction | ✔ |

**Strengthening detail worth recording:** `AUTOMATABLE_ACTIONS` is specified as a module constant
with the explicit rationale that widening it "should require a code review to change" — not an
env var, not a config key. That is a stricter posture than the existing `FINOPS_ACTUATION_ARMED`
env flag, and it is the correct direction.

---

## 8. V7 — Existing authority hierarchy preserved · **PASS**

| Requirement | Verified |
|---|---|
| No tier added or removed | Every `Authority.*` reference in the design is one of the existing five (`design.md:310,384,389,391,393,395,411`); no new member is proposed |
| No reordering | `is_canonical()` uses `fact.authority >= Authority.DERIVED`, consuming the existing `IntEnum` ordering (`knowledge.py:81-85`, verified) rather than redefining it |
| POLICY stays supreme and non-retrievable | Facts are excluded from the retrieval consumers entirely (§3.3), so the design cannot make policy probabilistically retrievable; §10.2's monotone-tightening rule makes "POLICY outranks any controller" operational (a descendant may narrow an inherited constraint, never widen it) |
| ADVISORY can never become canonical | Enforced at three independent points: `EPISTEMIC_MAP` pins the mapping, `is_canonical()` excludes it, validator C5 refuses any decision citing it. Hard rule 3 satisfied structurally |
| `knowledge.py` is not redesigned | The only proposed change is one additive `SOURCE_TYPES` row — the same registration pattern `spec_lifecycle` is applying for a `spec` type. Additive registration of a new `source_type` is explicitly anticipated by `message_family()`'s closed-by-default default (`knowledge.py:160-173`) |

---

## 9. Findings

Severity: **material** = fix before implementing · **minor** = fix during implementation ·
**non-issue** = examined and cleared, recorded so it is not re-opened.

### F1 — `on_missing: classify` on an *invariant* silently disables a safety constraint · **material**

**Where:** `design.md` §6.1, the `route_next_job.yaml` contract:

```yaml
invariants:
  - fact: max_spend_usd
    on_missing: classify     # absent ceiling => unconstrained; recorded as unknown, not invented
```

**Problem.** Invariants are the constraints validator check **C8** enforces. Under `classify`,
an absent `max_spend_usd` leaves `admissible = True` with the ceiling recorded in `unknowns` — so
C8 has nothing to check and the decision proceeds **unconstrained by spend**. For a *required
fact*, `classify` is the right handling (the design's own example — a first phase legitimately
has no accumulated cost — is correct). For an *invariant*, it converts a safety property into a
silent no-op, which is the opposite of the design's stated posture everywhere else
("closed by default", "fail closed").

**Recommendation.** Restrict invariant entries to `on_missing ∈ {halt, escalate}` and add a
compile-time refusal:

> **R11** — `rule "x": invariant 'max_spend_usd' declares on_missing 'classify'; an invariant may
> only halt or escalate. A constraint that degrades to unknown is not a constraint.`

`escalate` is the right default for increment 1: the decision is refused *and* a human is told,
rather than routing being blocked entirely before `policy_facts/v1` has run.

### F2 — C5 admits an empty `facts_used` · **minor**

**Where:** `design.md` §8.3, check C5 — "`facts_used ⊄ canonical facts of the snapshot`".

**Problem.** The empty set is a subset of every set, so a decision citing **no** facts passes C5.
For `continue` that is fine (the null action needs no basis). For `route` it means a controller
acted with no stated basis, which breaks the §8.5 provenance chain's usefulness and makes
`expected_effect` unscoreable — you cannot ask "which facts led to good outcomes" of a decision
that cites none.

**Recommendation.** C5 additionally requires `facts_used` non-empty for any action other than
`continue`.

### F3 — The `expected_effect` scoring loop has no declared destination · **minor**

**Where:** `design.md` §8.2 (the field), §9 I6 (the gate: "`expected_effect` scored").

**Problem.** The design motivates recording predictions well ("a controller that can never be
wrong cannot be improved") and says they are scored against measurement — but does not say
*where the score lands*. Without a destination it is an analysis someone remembers to run.

**Recommendation.** Name it as a measurement rule in the existing vocabulary — e.g.
`decision_calibration` (plane `measurement`, `[C]`) producing `decision_regret` — so it flows
through `evaluate_rules`/`compare_arms` (`compile_experiment.py:142-209,343-377`) rather than a
new path. This also makes the plane's own quality a spec-declared metric, consistent with the
repo's load-bearing rule applied reflexively.

### F4 — Where `conflicted` is computed is stated two ways · **minor**

**Where:** `design.md:121` (loop table) says `kb_worker`/`generate_manifest._derive_lifecycle`
get an "extended vocabulary"; §4.5 puts the `conflicted`/`stale` derivation in the plane's own
`fact_state()`.

**Problem.** These imply different blast radii. `_derive_lifecycle` is shared by **every**
`source_type`; extending it there would change lifecycle semantics for code, findings, reviews,
and ledger records — none of which asked for a `conflicted` state.

**Recommendation.** Keep `_derive_lifecycle` untouched and compute `conflicted`/`stale` only in
`fact_state()`. This is also what "the plane sits ABOVE" (hard rule 7's spirit) implies, and the
narrower change is strictly safer. Amend the loop-table cell to read "REUSE, unchanged; the plane
adds its own `fact_state()` on top".

### F5 — OQ3 and OQ7 are answered with tables rather than fenced schemas · **minor (deviation)**

The instruction said "concrete schemas (dataclass or YAML sketches, not prose)". OQ3 (a mapping)
and OQ7 (an ordering) are answered with structured tables. Tables are not prose and are arguably
the more precise form for both, so V3 passes — but the deviation is recorded rather than
silently absorbed. Optional remedy: express the increment order as a YAML `increments:` list so
the ordering is machine-checkable against `REDUCERS`/`FACT_PREDICATES` at implementation time.

### F6 — `source_type="fact"` nominal `DERIVED` vs `declared` facts carrying `POLICY` · **non-issue**

Examined in §6.3 and cleared: `knowledge.py:104-119` states the `SOURCE_TYPES` authority column
is documentation, not a validator, and that producers decide at construction time (`report` is an
existing precedent). Recorded so a future reader does not re-open it.

---

## 10. What this verification did **not** check

Stated so the boundary of the assurance is clear:

1. **Implementability.** No code was written, so no schema was compiled, no test run. The design's
   claim that the fact pipeline works end to end via `build_record → publish_event → kb-registry-v1
   → manifest` is verified as *architecturally consistent with the cited code*, not as *executed*.
2. **Performance.** The read-time staleness cascade's cost (design §13 risk 2) and registry
   compaction under fact volume (risk 4) are unmeasured. Both are named in the design's own
   residual risks.
3. **Completeness of `FACT_PREDICATES`.** The registry table is explicitly illustrative; whether
   the ~16 listed predicates suffice for `route_next_job` in practice is an I4 measurement, which
   is exactly where the design puts it.
4. **The `spec_lifecycle` merge dependency** (design §9, risk 5) — that arm is running now and its
   outcome is not knowable from this worktree.

---

## 11. Verdict

**PASS — all seven required checks met.** The design is internally consistent, its 34 spot-checked
citations are accurate against the code as it stands today, it preserves the observe-only
supervisor rail and the authority hierarchy without modification, and it makes the generalized
load-bearing rule enforceable through a producer-declaration invariant, ten compile-time
refusals, and five runtime refusal conditions.

Six findings are recorded. **F1 is material and should be fixed before implementation** — a
one-line contract change plus one additional compile refusal (R11). F2–F4 are minor and can be
handled during implementation; F5 is a noted deviation; F6 is cleared.

The design-only boundary is intact: the working tree is clean and this run touched nothing outside
`docs/context_abstraction/`.
