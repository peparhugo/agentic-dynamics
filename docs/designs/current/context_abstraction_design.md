---
status: accepted
---
# The Context Abstraction Plane — Design

**Spec:** `experiments/specs/context_abstraction_plane.yaml`
**Phase:** `design` (phase 2 of 3 — `review` → **`design`** → `verify`)
**Prior phase:** `docs/context_abstraction/review.md` (component audit; every "what exists"
claim below is that document's, and inherits its citations)
**Date:** 2026-08-20 · **Model:** anthropic/claude-opus-5 · **Branch:** `feature/context-abstraction-plane`
**Deliverable rule:** design-only. This phase adds exactly one file
(`docs/context_abstraction/design.md`) and modifies nothing under `src/`, `scripts/`,
`tests/`, or `admin/`. Nothing here is implemented.

---

## 0. How to read this document

The review established that the repository has a near-complete **evidence plane** and a
near-complete **execution plane**, and nothing in between. This document designs the layer in
between and nothing else.

It is organised as: the thesis (§1), the full loop with every existing component placed in it
(§2), then the seven open questions answered in order with concrete schemas (§3–§9), then the
scope hierarchy in full (§10), the explicit scope boundary (§11), and traceability back to the
review's corrections (§12).

Conventions:

- **Every schema is a sketch, not code.** Dataclasses are written in Python syntax with
  docstrings and inline comments because that is the repo's convention
  (`AGENTS.md`: "Dataclasses over dicts", type hints on public signatures) and because a typed
  sketch cannot hide an ambiguity that prose can. They are illustrative; no file is created.
- **Citations** are `file:line` from the review. Where this document proposes something new it
  says **NEW**; where it reuses an existing mechanism it says **REUSE** and names it.
- **Design decisions carry their reasoning inline**, marked *Why:*. A decision without a
  stated reason is a decision nobody can revisit safely.

### The six hard rules this design is bound by (from the spec's `hard_rules`)

| # | Rule | Where honoured |
|---|---|---|
| 1 | Design only — documents, no code changes | This document; §11 |
| 2 | No new transport — reuse ledger, knowledge stream, registry/manifest supersede machinery, the Redis plane split | §3.3, §4.3, §10.4 |
| 3 | Deterministic reducers only for canonical derived facts; LLM judgment is ADVISORY always | §3.4, §4, §8.5 |
| 4 | Exactly one canonical representation per fact, or explicitly unknown/conflicted | §3.2, §4.5 |
| 5 | Preserve the observe-only supervisor rail and the existing authority hierarchy | §3.4, §8.6 |
| 6 | The generalized load-bearing rule is the gate | §7 |
| 7 | Do not redesign `knowledge.py` / `retrieval.py` / `prompt_constructor.py` — the plane sits ABOVE them | §3.3, §11 |

---

## 1. Thesis

> **Evidence is what happened. A fact is what is true, now, in a scope. A snapshot is what a
> particular decision is allowed to know. A decision is a typed, validated, provenance-carrying
> proposal to change the future.**

The system today can answer "what happened" extremely well and "what is true now" only by
re-deriving it, ad hoc, inside whichever function needs it. The plane's whole job is to make
"what is true now" a **first-class, typed, scoped, versioned, auditable artifact** — and then
to make it the *only* thing a controller may read.

Four structural commitments follow, and everything else in this document is a consequence of
one of them:

1. **A fact is a statement, not a document.** `subject · predicate · value`, with scope,
   validity, authority, and a derivation chain. (§3)
2. **Only a deterministic, versioned reducer may mint a canonical fact.** An LLM may only ever
   produce an ADVISORY fact, and ADVISORY facts are structurally excluded from every control
   path — not by convention, by a validator check. (§4)
3. **A controller never queries the fact store.** It receives a compiled, contract-bounded
   `ControlContext` snapshot; anything the contract did not ask for is not in the snapshot, and
   anything the contract asked for and could not be satisfied appears as an explicit
   `unknown` / `conflict` / `stale` entry — never as silence. (§6)
4. **The gate generalizes, it does not fork.** `RuleSpec.requires` becomes a fact contract, the
   existing compiler refusal becomes a producibility check, and a *new* runtime refusal covers
   currency. The review found the current gate proves schema availability but not fact currency
   (review §4.4); this is the fix. (§7)

---

## 2. The loop the design completes

The spec names the loop: **observe → canonicalize → abstract → decide → execute → measure →
update**. The system today implements `execute → measure → information`. The plane supplies
`canonicalize → abstract → decide` and closes the ring.

```
                          ┌──────────────────── THE AGENTIC DYNAMICS LOOP ────────────────────┐
                          │                                                                     │
   (1) OBSERVE            │  (2) CANONICALIZE        (3) ABSTRACT           (4) DECIDE          │
   run artifacts,   ──────┼──▶ reducers ──▶ facts ──▶ Context Compiler ──▶ ControlContext ──▶  │
   commits, test          │    (deterministic,        (contract-bounded,      snapshot           │
   results, KB            │     versioned)             scope-resolved)            │              │
   records                │         │                                             ▼              │
        ▲                 │         │                                     control rule proposes  │
        │                 │         │                                       ControlDecision      │
        │                 │         │                                             │              │
        │                 │         │                                             ▼              │
   (6) MEASURE            │         │                                     ControlValidator       │
   test_runner,           │         │                                     (10 ordered checks)    │
   evaluate_rules,   ◀────┼─────────┴───────────── (7) UPDATE ◀──────────────────┤              │
   compare_arms           │                     facts re-derive at read time      │ admitted     │
        ▲                 │                                                        ▼              │
        │                 │                                              (5) EXECUTE             │
        └─────────────────┼──────────────────────────────── workflow_runner / worker ────────────┘
                          └─────────────────────────────────────────────────────────────────────┘
```

### Where every existing component sits

| Loop stage | Component | Role | Status |
|---|---|---|---|
| **1. Observe** | `workflow_runner.PhaseResult` → `scripts/run_workflow.py:108` JSON | typed per-phase run artifact — the richest L0 the system has | EXISTS, unchanged |
| | `story.py` `StoryResult` / `SessionResult` | per-cell / per-session artifacts | EXISTS, unchanged |
| | `test_runner.run_suite` | the sole independent source of `test_executed_success` | EXISTS, unchanged |
| | `knowledge.py` / `knowledge_stream.py` producers (9 families) | durable evidence records + pointer events on DB 2 | EXISTS, unchanged |
| | git commits (`[workflow] <phase>`) | immutable phase-completion evidence | EXISTS, unchanged |
| | `live.py` telemetry (DB 1) | operator display only — **explicitly not evidence** | EXISTS, excluded by rule |
| **2. Canonicalize** | **`reducers/` package** | deterministic versioned reducers evidence → `CanonicalFact` | **NEW** (§4) |
| | `record_factory.build_record` | identity + content-hash ordering for the fact's record form | REUSE, unchanged |
| | `knowledge_stream.publish_event` | the one durable write path for the fact's pointer event | REUSE, unchanged |
| | `kb_worker.py` `kb-registry-v1` + `generate_manifest._derive_lifecycle` | supersession → `current \| superseded \| tombstoned` | REUSE, extended vocabulary (§4.5) |
| **3. Abstract** | **`context_compiler.py`** | contract + scope → `ControlContext` snapshot | **NEW** (§6) |
| | **`fact_contracts` in `RuleSpec`** | what a decision is allowed and required to know | **NEW** (§7) |
| | `retrieval.py` | **not in this loop** — relevance ranking for *executor* prompts | EXISTS, untouched |
| | `prompt_constructor.py` | **not in this loop** — executor prompt construction | EXISTS, untouched |
| **4. Decide** | **`control_rules/` (policy functions)** | `decide(ControlContext) -> ControlDecision` | **NEW** (§8) |
| | `step_routing.route_step` | the *reference* deterministic control rule, kept as-is | EXISTS, re-placed (§8.4) |
| | **`control_validator.py`** | 10 ordered admission checks | **NEW** (§8.3) |
| | `actuation_ingestion.derive_actuation_record` + `publish_event` gates | the decision's durable, armed, lineage-checked record form | REUSE, payload extended (§8.2) |
| **5. Execute** | `workflow_runner.run_workflow` | executes phases; consumes an admitted `route` decision as its model choice | EXISTS, one seam (§9, I7) |
| | `worker.py` / `enqueue.py` | job transport | EXISTS, unchanged |
| **6. Measure** | `compile_experiment.evaluate_rules`, `compare_arms` | measurement rules + arm comparison — now also measures the *plane* | EXISTS, unchanged |
| | `supervise.py` | observes and flags; **never** actuates | EXISTS, unchanged (§8.6) |
| **7. Update** | `fact_state()` read-time derivation | staleness cascade without a scheduler | **NEW** (§4.5) |

*Why place retrieval and prompt_constructor explicitly outside the loop:* the review's first
critical distinction (§3a) is that retrieval is relevance ranking, not truth resolution. If
retrieval appeared anywhere in stages 2–4, a ranked document could become a controller input,
and the "relevance is never truth" rule would be a convention rather than a structure. Their
absence from this table is load-bearing.

---

## 3. OQ1 — `CanonicalFact`: schema, identity, evidence resolution, epistemics

### 3.1 The dataclass

```python
@dataclass(frozen=True)
class CanonicalFact:
    """One typed, scope-bound, current statement about the system.

    A fact is deliberately NOT a document. `knowledge.KnowledgeRecord` answers "what did this
    artifact say at this revision"; a CanonicalFact answers "what is true about this subject,
    in this scope, right now". The two are related by construction (§3.3: every fact is
    persisted AS a KnowledgeRecord with source_type="fact"), but the semantics are different
    and the plane must never conflate them — that conflation is exactly the gap the review
    found at rows 2 and 7 of the component audit.

    Frozen because a fact is immutable: a new value is a NEW fact that supersedes the old one,
    exactly as a modified symbol is a new `knowledge_id` under a stable `entity_id`
    (knowledge.py:13-18). Nothing ever mutates a fact in place; that is what makes the
    derivation chain auditable and the supersession spine reusable.
    """

    # ── Identity (two ids, mirroring knowledge.py's entity_id / knowledge_id pair) ──
    fact_entity_id: str
    """The stable LOGICAL SLOT: 'the value of <predicate> for <subject> in <scope>'.

    Computed with the EXISTING helper (knowledge.compute_entity_id:184-191) so the plane adds
    no second identity algorithm:

        fact_entity_id = compute_entity_id(
            repository_id = <scope's repository_id>,
            source_uri    = f"fact://{scope_type}/{scope_id}/{predicate}",
            logical_locator = f"{subject_type}:{subject_id}#{predicate}",
        )

    Why the slot is keyed by (scope, subject, predicate) and NOT by time: this is what makes
    "exactly one canonical representation per fact" (hard rule 4) mechanically true — one slot,
    one current version, resolved by the registry compaction that already exists
    (generate_manifest.py:111-221). Contrast observation_ingestion.py:62-70, which deliberately
    folds the timestamp INTO identity because every supervisor verdict is an independent fact.
    Facts take the opposite choice, and §3.2 explains why that is the right one here.
    """

    fact_id: str
    """The immutable VERSION of the slot — one particular value, derived at one moment by one
    reducer version. Computed with the existing helper (knowledge.compute_knowledge_id:194-203):

        fact_id = compute_knowledge_id(
            entity_id       = fact_entity_id,
            source_revision = source_revision,
            content_hash    = sha256(canonical payload bytes),
            extractor_version = reducer_version,     # the reducer IS the extractor
        )

    Consequence, and the reason this reuse is worth more than it looks: because
    `reducer_version` is folded into the id, bumping a reducer version RE-KEYS every fact it
    produces. The new facts then supersede the old ones through the machinery that already
    exists, with no new versioning concept. Reducer versioning is free.
    """

    # ── The statement itself ──
    subject_type: str    # job | attempt | workflow | workload | spec | model | resource | policy
    subject_id: str      # e.g. "wf_context_abstraction_plane_anthropic_claude_opus_5"
    predicate: str       # MUST be a key of FACT_PREDICATES (§3.5) — a closed vocabulary
    value: str           # canonical STRING encoding; typed by `value_type` below
    value_type: str      # bool | int | float | usd | seconds | tokens | timestamp | enum | str
    unit: str = ""       # "" | "usd" | "s" | "tokens" — redundant with value_type, kept for display

    # ── Placement in the hierarchy ──
    scope_type: str      # organization | program | workload | workflow | job | attempt | resource
    scope_id: str
    scope_path: str      # "org:agentic-dynamics/workload:rag_bare_vs_augmented/job:self-wt_03"
    abstraction_level: str
    """L1..L5 as a NAME, not a number: fact | job | workflow | workload | policy.

    Kept as a SEPARATE axis from `authority`, per the proposal's insistence (design_input 4).
    The four combinations that motivate the separation, all of which occur in practice:
      - low level  + MEASURED : attempt token count            (fact  / MEASURED)
      - high level + DERIVED  : workflow_health                (workflow / DERIVED)
      - high level + POLICY   : workload budget ceiling        (policy / POLICY)
      - high level + ADVISORY : supervisor "seems off track"   (workflow / ADVISORY)
    A single blended axis cannot express those four, which is why the proposal is right here.
    """

    # ── Epistemics (§3.4 — a SINGLE discriminator, from which the two existing axes derive) ──
    epistemic_status: str   # observed | verified | derived | declared | advisory
    authority: Authority    # DERIVED from epistemic_status — never chosen freely
    evidence_class: str     # DERIVED from epistemic_status — [M] [C] [H] [P] [X]

    # ── Validity window ──
    observed_at: str        # when the underlying evidence was observed (NOT when reduced)
    valid_from: str         # when this value became true (usually == observed_at)
    valid_to: str | None    # None = open; set by the registry view when superseded
    expires_at: str | None
    """Explicit obsolescence horizon, from FACT_PREDICATES[predicate].default_ttl_seconds.

    Why a fact carries its own expiry rather than letting each consumer decide: the volatility
    of a predicate is a property OF THE PREDICATE, not of the reader. `current_commit` for a
    finished job never expires; `queue_depth` is meaningless after 60 seconds. Putting the TTL
    on the fact makes staleness computable without knowing who is asking, and makes a contract's
    `max_age_seconds` an additional TIGHTENING, never the only defence.
    """

    # ── Derivation chain (what makes a derived fact auditable) ──
    reducer: str            # "workflow_health"
    reducer_version: str    # "workflow_health/v1" — folded into fact_id (see above)
    evidence_ids: tuple[str, ...]
    """The FULL input set: `knowledge_id`s of evidence records AND/OR `fact_id`s of
    lower-level facts. Ordered, deduplicated, and hashed into the payload.

    Why fact_ids are allowed here: this is precisely what makes the staleness cascade
    transitive by construction (§4.5). An L3 fact cites the L2 fact_ids it consumed, so if an
    L1 input is superseded, the L3 fact resolves as stale on the next read with no write and no
    scheduler.
    """
    inputs_digest: str      # sha256 over (sorted evidence_ids | reducer_version | input values)
    supersedes: str | None  # predecessor fact_id for the SAME fact_entity_id (REUSE of knowledge.py:348)
    source_revision: str    # commit sha when the fact is repository-bound, else a producer marker
    repository_id: str      # REUSE — the existing scope string (§10.3)

    # ── Derived, index-only (never stored in the artifact; recomputed on read) ──
    lifecycle_state: str = "current"
    """current | superseded | tombstoned | conflicted | unknown.

    Marked index-only for exactly the reason generate_manifest.py:75-108 gives for its own
    lifecycle derivation ("index-only, computed, never stored"): a stored lifecycle is a lie the
    moment a successor appears. `conflicted` and `unknown` are NEW states (review §4.3 found the
    registry has only three) and are specified in §4.5.
    """
```

### 3.2 Identity: why the slot is time-invariant

The repository already contains both possible identity strategies, and the choice between them
determines whether "the current value" is a **lookup** or a **scan**:

| Strategy | Example in repo | Identity includes time? | "Current value" costs |
|---|---|---|---|
| Version chain | `code`/`finding`/`ledger_*` records | No — `entity_id` is stable | O(1) registry lookup |
| Independent events | `observation` (`observation_ingestion.py:62-70`), `actuation` (`actuation_ingestion.py:76-88`) | Yes — timestamp folded in | O(n) max-by-time scan |

**Decision: facts use the version-chain strategy.**
*Why:* (a) the whole point of a fact is "the one current value", and a lookup is the only
implementation of that which cannot silently return two answers; (b) the registry compaction
that resolves "one current row per `entity_id`" already exists and is tested
(`generate_manifest.py:111-221`); (c) the alternative — scanning by time — reintroduces exactly
the ambiguity the plane exists to remove, because two producers can write the same timestamp.

*Consequence, stated honestly:* the history of a fact is the supersession chain, which the
compacted manifest keeps only as a `versions` list and which needs `registry.py lineage --live`
(Neo4j) for the full walk. Facts therefore get **cheap current-value reads and expensive
history reads**. That is the correct trade for a control plane; an analysis workload that wants
fact history should read the underlying evidence, which is immutable and complete.

### 3.3 Persistence: a fact IS a `KnowledgeRecord` with `source_type="fact"`

*Why not a new store:* hard rule 2 (no new transport). Everything the fact plane needs —
identity, content hashing, durable artifacts, a stream with retries and dead-lettering,
idempotent consumers, a registry index, lifecycle derivation, a CLI — exists and is exercised.
Building a parallel store would duplicate all of it and immediately drift.

The mapping, using only *additive registration* (which `spec_lifecycle` is already doing for a
`spec` type, so this is a known-good pattern and not a redesign of `knowledge.py`):

```python
# knowledge.SOURCE_TYPES — ONE additive row (registration, not redesign; cf. hard rule 7)
"fact": SourceTypeSpec("observation", Authority.DERIVED, "[C]"),
#        ^ observation family: a fact states what IS, never an instruction to act.
#          The nominal authority/evidence_class columns are documentation
#          (knowledge.py:104-119 says so explicitly); each fact's real values come from
#          §3.4's mapping at construction time.
```

| `KnowledgeRecord` field | Carries |
|---|---|
| `source_uri` | `fact://{scope_type}/{scope_id}/{predicate}` |
| `logical_locator` | `{subject_type}:{subject_id}#{predicate}` — human-legible in `registry.py show` |
| `repository_id` | the scope's repository id (§10.3) |
| `commit_sha` / `source_revision` | `source_revision` |
| `extractor_version` | **`reducer_version`** — the reducer is the extractor |
| `authority`, `evidence_class` | derived from `epistemic_status` (§3.4) |
| `valid_from`, `valid_to`, `observed_at` | the validity window |
| `supersedes` | predecessor `fact_id` |
| `text` | **the canonical JSON payload** — see the decision below |
| `content_hash`, `knowledge_id` | computed by `record_factory.build_record` unchanged |

**Decision: the fact's typed payload is the canonical JSON encoding placed in `text`.**

```python
# The payload — deterministic, sorted keys, no whitespace variance. This is what `text` holds.
{
  "abstraction_level": "workflow",
  "evidence_ids": ["<fact_id>", "<fact_id>", "<knowledge_id>"],
  "expires_at": null,
  "inputs_digest": "9f2c…",
  "predicate": "workflow_phases_completed",
  "reducer_version": "workflow_facts/v1",
  "scope_path": "org:agentic-dynamics/workload:context_abstraction_plane/job:self-wt_03",
  "subject_id": "wf_context_abstraction_plane_anthropic_claude_opus_5",
  "subject_type": "workflow",
  "unit": "",
  "value": "2",
  "value_type": "int"
}
```

*Why the payload goes in `text` rather than a side artifact:* `content_hash` is
`sha256(record_to_artifact(record))` (`record_factory.py:191`), and `record_to_artifact`
serialises `record.to_dict()` with the derived ids and volatile timestamps blanked
(`record_factory.py:67-98`). Putting the payload in `text` therefore means **the value is
inside the hash**: change a fact's value and you get a new `content_hash`, hence a new
`fact_id`, hence a supersession — automatically, with no new invariant to maintain. A side
artifact would need its own hash threaded into the record, i.e. a new mechanism, i.e. hard
rule 2 violated. It also directly fixes the review's prose-projection defect (§3d(iv)): unlike
`ledger_ingestion.py:173`, a fact's numbers are machine-readable without parsing prose.

*The cost, and its mitigation:* a JSON blob is poor lexical/dense search material.
**Facts are therefore not retrieval candidates at all** — the `kb-chroma-v1` and `kb-neo4j-v1`
consumers skip `source_type == "fact"`; only `kb-registry-v1` (and the ledger consumer)
process them. *Why this is a feature, not a compromise:* the plane resolves facts by **address**
(`fact_entity_id`), never by relevance. Making facts structurally unreachable from
`retrieval.retrieve()` is the strongest possible enforcement of "relevance ranking is not truth
resolution" (review §3a) — a future contributor cannot accidentally rank their way to a
controller input.

### 3.4 `epistemic_status` composed with the existing `Authority`

The review's §4.5 flagged that a free-standing `epistemic_status` would be a **third**
overlapping provenance axis next to `authority` and `evidence_class`, inviting exactly the
"which field is authoritative" drift the ordering was built to prevent.

**Decision: `epistemic_status` is the single discriminator; `authority` and `evidence_class`
are pure functions of it.** Not a convention — a construction-time computation, so the three can
never disagree.

```python
#: The ONE mapping. A fact constructor takes epistemic_status and derives the other two;
#: passing authority explicitly is not part of the API. Rationale per row below.
EPISTEMIC_MAP: dict[str, tuple[Authority, str]] = {
    # An event was recorded by the system itself (a commit exists, a token count was emitted).
    "observed":  (Authority.MEASURED, "[M]"),
    # An INDEPENDENT verifier confirmed it — today that means test_runner.run_suite, the sole
    # source of test_executed_success. Same authority as `observed`, different meaning, and the
    # distinction is already made in code at knowledge_ingestion.py:466-468 (MEASURED when
    # test_executed_success is a real bool, ADVISORY when None).
    "verified":  (Authority.MEASURED, "[M]"),
    # Computed by a deterministic versioned reducer from other facts/evidence.
    "derived":   (Authority.DERIVED,  "[C]"),
    # Asserted by policy or configuration — a human/operator declaration, not a measurement.
    "declared":  (Authority.POLICY,   "[P]"),
    # A judgment (LLM, heuristic, supervisor verdict). NEVER canonical. See is_canonical().
    "advisory":  (Authority.ADVISORY, "[H]"),
}
```

```python
def is_canonical(fact: CanonicalFact) -> bool:
    """True when a fact may be consumed by a control path.

    This single predicate is the executable form of hard rule 3 ("LLM judgment is ADVISORY,
    always"). ADVISORY facts are still STORED — suppressing them would lose information and
    make supervisor verdicts unauditable — but they are placed in ControlContext.advisory
    (§6.3), and ControlValidator check C5 (§8.3) refuses any decision whose `facts_used` cites
    one. So an LLM statement can be recorded, displayed, and studied; it can never be a reason.
    """
    return (
        fact.epistemic_status != "advisory"
        and fact.authority >= Authority.DERIVED     # IntEnum ordering, knowledge.py:81-85
        and fact.lifecycle_state == "current"
    )
```

*Why keep ADVISORY facts in the same store at all:* because the interesting research question —
"how often is the supervisor's heuristic verdict right, measured against the canonical facts?" —
requires both in one comparable form. Excluding them would protect the control path and destroy
the measurement. Placing them in the store but outside `is_canonical` protects both.

### 3.5 The predicate registry — the "declared source" half of the load-bearing rule

```python
@dataclass(frozen=True)
class PredicateSpec:
    """The declaration of ONE fact predicate. This table is the plane's schema of the world.

    It exists so the generalized load-bearing rule has something to check against: "no control
    action may consume a value that is not produced by a declared source or reducer" is only
    enforceable if there is a registry of declarations. FACT_PREDICATES is that registry, and it
    plays the same role for facts that LEDGER_FIELDS (experiment_spec.py:44-103) plays for
    ledger information today — with the crucial difference that a predicate names its PRODUCER,
    so the review's "declared but written by nothing" failure (§3d(ii)) cannot recur.
    """
    name: str
    value_type: str
    unit: str
    subject_type: str
    scope_type: str
    abstraction_level: str
    produced_by: tuple[str, ...]
    """Reducer version(s) that may emit this predicate. NON-EMPTY IS THE INVARIANT: a predicate
    with no producer is unwritable AND unrequirable, which is what makes `budget` and
    `deadline_slack` (declared in LEDGER_FIELDS with zero writers) impossible to declare here
    until something actually produces them."""
    default_ttl_seconds: int | None
    volatile: bool
    """True when the value changes on the timescale of a decision (queue depth, running status).
    A control rule requiring a volatile predicate MUST set max_age_seconds (§7.3 refusal R6)."""
    inheritable: bool = False
    """True when descendants of the declaring scope may read it (downward flow, §10.2)."""
    aggregates_from: str = ""
    """When set, the child predicate this one rolls up from — the only legal upward path."""
```

Illustrative first rows (the full table is an implementation artifact; these are the ones
increments I1–I3 in §9 would populate):

| predicate | value_type | subject | scope | level | produced_by | ttl | volatile | inheritable |
|---|---|---|---|---|---|---|---|---|
| `spec_status` | enum | spec | workload | fact | `spec_status/v1` | none | no | yes |
| `spec_superseded_by` | str | spec | workload | fact | `spec_status/v1` | none | no | yes |
| `current_commit` | str | job | job | fact | `job_facts/v1` | none | no | no |
| `phase_status` | enum | attempt | attempt | fact | `attempt_facts/v1` | none | no | no |
| `phase_test_verified` | bool | attempt | attempt | fact | `attempt_facts/v1` | none | no | no |
| `attempt_cost_usd` | usd | attempt | attempt | fact | `attempt_facts/v1` | none | no | no |
| `attempt_tokens_out` | tokens | attempt | attempt | fact | `attempt_facts/v1` | none | no | no |
| `attempt_cache_hit_rate` | float | attempt | attempt | fact | `attempt_facts/v1` | none | no | no |
| `attempt_confidence` | float | attempt | attempt | fact | `attempt_facts/v1` | none | no | no |
| `job_accumulated_cost_usd` | usd | job | job | job | `job_facts/v1` | none | no | no |
| `workflow_phases_completed` | int | workflow | workflow | workflow | `workflow_facts/v1` | none | no | no |
| `workflow_phases_remaining` | int | workflow | workflow | workflow | `workflow_facts/v1` | none | no | no |
| `workflow_status` | enum | workflow | workflow | workflow | `workflow_facts/v1` | none | no | no |
| `allowed_models` | enum-list | policy | workload | policy | `policy_facts/v1` | none | no | **yes** |
| `max_spend_usd` | usd | policy | workload | policy | `policy_facts/v1` | none | no | **yes** |
| `max_attempts` | int | policy | workload | policy | `policy_facts/v1` | none | no | **yes** |

Note what is **absent** and why: `budget_remaining`, `deadline_slack`, `dependency_failed`,
`critical_path`, `queue_depth`, `worker_capacity`, `job_priority`, `business_value`. Every one
is either a modelling gap or telemetry-only (review §3d(iii)); none has a producer today, so
none may be declared. §9 states what would have to happen first.

---

## 4. OQ2 — The reducer model, derivation chains, and the staleness cascade

### 4.1 Where reducers live and what they are

```
src/instrument/reducers/
    __init__.py         # REDUCERS registry; the only public surface
    spec_status.py      # spec_status/v1        (L1, workload scope)   ← ships first (§9, I1)
    attempt_facts.py    # attempt_facts/v1      (L1, attempt scope)
    job_facts.py        # job_facts/v1          (L2, job scope)
    workflow_facts.py   # workflow_facts/v1     (L3, workflow scope)
    policy_facts.py     # policy_facts/v1       (L5, declared — parses spec/policy config)
```

```python
@dataclass(frozen=True)
class ReducerSpec:
    """The declaration of one deterministic, versioned reducer.

    Discipline copied verbatim from two places that already work:
      * step_routing.py:10-13 — "a pure function — no I/O, no RNG — so it is trivially
        unit-testable and reusable"; the same argument applies with more force here, because a
        reducer's output is persisted and cited by decisions.
      * record_factory._now_iso:49-55 — an INJECTED clock, so tests pin timestamps and
        production uses the real one. A reducer that reads the wall clock directly is not
        reproducible and cannot be replayed against historical evidence.
    """
    name: str
    version: str            # "workflow_facts/v1" — the string folded into every fact_id
    level: str              # fact | job | workflow | workload | policy
    scope_type: str         # the scope of the facts it emits
    consumes: tuple[str, ...]
    """Input contract: evidence source_types (e.g. "ledger_attempt") and/or predicate names of
    lower-level facts. Declared so the compiler can verify a reduction LADDER exists before any
    rule requires the top of it — the load-bearing rule applied to reducers themselves."""
    produces: tuple[str, ...]   # predicate names; must all exist in FACT_PREDICATES
    determinism: str = "pure"   # "pure" | "pure_with_injected_clock"

# The signature every reducer implements. No I/O: the caller resolves inputs and persists
# outputs, so the reducer itself is a pure function that a test can call with fixtures.
Reducer = Callable[[ReducerInput], list[CanonicalFact]]

@dataclass(frozen=True)
class ReducerInput:
    """Everything a reducer may see. Deliberately narrow: no Redis handle, no filesystem,
    no network. If a reducer needs more inputs, that is a `consumes` change and therefore a
    VERSION change — which is the point."""
    scope_path: str
    scope_type: str
    scope_id: str
    repository_id: str
    evidence: tuple[EvidenceItem, ...]   # resolved L0 records/artifacts, ordered deterministically
    facts: tuple[CanonicalFact, ...]     # resolved lower-level facts (already filtered to current)
    now: str                             # injected clock
    source_revision: str
```

### 4.2 A worked reducer (the shape all of them take)

```python
WORKFLOW_HEALTH_V1 = ReducerSpec(
    name="workflow_health",
    version="workflow_health/v1",
    level="workflow",
    scope_type="workflow",
    consumes=("workflow_phases_remaining", "workflow_failed_phases", "job_accumulated_cost_usd",
              "max_spend_usd"),
    produces=("workflow_health",),
)

def workflow_health_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit `workflow_health ∈ {healthy, degraded, at_risk}` for one workflow scope.

    This is the design_input's own example ("workflow_health/v1(failed_critical_jobs,
    deadline_slack, budget_remaining) -> 'at_risk'") adjusted to the facts that ACTUALLY exist
    (review §3d): deadline_slack and budget_remaining have no producer, so this v1 uses failed
    phases and spend-against-declared-ceiling instead. That substitution is the design honouring
    measure-before-policy rather than the proposal's illustrative field list.

    Determinism requirements this satisfies, and why each matters:
      * total order over inputs (sorted by fact_entity_id) — two runs over the same evidence
        must produce byte-identical payloads, or the content hash (and thus fact_id) differs
        and a spurious supersession is recorded;
      * no wall-clock read — `inp.now` only, so a replay against historical evidence reproduces
        the historical fact exactly;
      * total function — every branch returns a value or an explicit `unknown` fact; a reducer
        that returns nothing is indistinguishable from a reducer that was never run, and the
        Context Compiler must be able to tell those apart.
    """
    ...
```

### 4.3 How a fact is persisted (the pipeline, entirely reused)

```
reducer(ReducerInput) -> [CanonicalFact]
   │
   ├─▶ record_factory.build_record(source_type="fact", ..., extractor_version=reducer_version,
   │        text=canonical_payload_json)                        # REUSE record_factory.py:101-195
   ├─▶ record_to_artifact(record) -> bytes                      # REUSE record_factory.py:67-98
   │        └─ written to experiments/results/facts/<fact_id>.json
   ├─▶ record_to_event(record)                                  # REUSE knowledge_ingestion
   └─▶ knowledge_stream.publish_event(r, event, authorized=True, source_type="fact")
            │                                                    # REUSE knowledge_stream.py:129-194
            ▼
        kb:v1:changes  (DB 2)
            ├─ kb-registry-v1  → registry_index.jsonl → generate_manifest compaction → lifecycle
            ├─ kb-ledger-v1    → checkpoint
            ├─ kb-chroma-v1    → SKIPPED for source_type="fact"   (§3.3: facts are not searchable)
            └─ kb-neo4j-v1     → SKIPPED for source_type="fact"
```

Two properties come free and are worth naming because they were expensive to build:
**idempotence** (re-running a reducer over unchanged evidence derives the same `fact_id`, so the
keyed upsert is a no-op — `record_factory.py:74-83`) and **the write guard** (a read-only
process cannot emit facts — `knowledge_stream.py:178-181`).

### 4.4 Derivation-chain validation

```python
def verify_chain(fact: CanonicalFact, resolve: Callable[[str], RegistryRow | None]) -> list[str]:
    """Return refusal reasons for `fact`'s derivation chain; empty list = valid.

    Called by (a) the Context Compiler before a fact may enter a snapshot, and (b) the
    ControlValidator (check C6) before a decision may cite it. Checked TWICE on purpose — the
    same "closed by default, checked in more than one place" posture the actuation gates already
    use (knowledge_stream.py:182-192 checks lineage even when actuation IS armed).
    """
    errors = []
    # 1. The reducer must be registered. An unregistered reducer_version means the fact was
    #    produced by code that no longer exists — its semantics are unknowable.
    if fact.reducer_version not in REDUCERS:
        errors.append(f"fact {fact.fact_id}: reducer {fact.reducer_version!r} is not registered")
    # 2. Every input must resolve. A dangling evidence_id means the chain is broken, not weak.
    for eid in fact.evidence_ids:
        if resolve(eid) is None:
            errors.append(f"fact {fact.fact_id}: evidence {eid} does not resolve in the registry")
    # 3. The digest must reproduce — catches a hand-edited artifact or a partial write.
    if recompute_inputs_digest(fact) != fact.inputs_digest:
        errors.append(f"fact {fact.fact_id}: inputs_digest mismatch (artifact altered?)")
    # 4. The reducer must be declared to produce this predicate, at this level and scope.
    spec = REDUCERS.get(fact.reducer_version)
    if spec and fact.predicate not in spec.produces:
        errors.append(f"fact {fact.fact_id}: {fact.reducer_version} does not declare {fact.predicate!r}")
    if spec and fact.abstraction_level != spec.level:
        errors.append(f"fact {fact.fact_id}: level {fact.abstraction_level!r} != reducer level {spec.level!r}")
    # 5. Epistemic consistency — authority/evidence_class must equal the §3.4 mapping.
    if EPISTEMIC_MAP.get(fact.epistemic_status) != (fact.authority, fact.evidence_class):
        errors.append(f"fact {fact.fact_id}: authority/evidence_class contradict epistemic_status")
    return errors
```

### 4.5 The staleness cascade — read-time derivation, no scheduler

**Decision: staleness is DERIVED AT READ TIME, exactly as `lifecycle_state` already is.**

```python
def fact_state(fact: CanonicalFact, *, now: str, resolve) -> str:
    """Return current | stale | superseded | tombstoned | conflicted | unknown.

    Precedence is fixed and total (first match wins), because an ambiguous state is worse than
    a wrong one — a controller can handle "stale", it cannot handle "maybe".

      1. tombstoned  — this fact's slot was explicitly retracted (terminal, per
                       generate_manifest.py:129-132's tombstone-is-terminal rule).
      2. superseded  — some other fact's `supersedes` names this fact_id (REUSE of
                       generate_manifest.py:85-94, which resolves supersession by POINTER, not
                       by trusting a stored state — correct even for rows written by older code).
      3. conflicted  — two or more CURRENT facts share this fact_entity_id with different
                       values and neither supersedes the other (see the resolution ladder below).
      4. stale       — expires_at < now, OR any evidence_id resolves to a row that is not
                       current, OR a NEWER registered reducer version produces this predicate.
      5. current     — otherwise.
      (unknown is not a state OF a fact; it is the compiler's answer when NO fact fills a
       required slot — see §6.3. Keeping the two separate matters: "we have a stale value" and
       "we never had a value" call for different `on_missing` handling.)
    """
```

*Why read-time and not eager re-derivation:* three reasons, in order of weight.
(1) **Correctness under partial failure.** An eager cascade must re-derive every downstream fact
when an upstream one changes; if it crashes halfway, the store holds a mix of re-derived and
stale facts with no marker distinguishing them. Read-time derivation is always correct against
whatever the registry currently says.
(2) **Precedent.** `generate_manifest._derive_lifecycle` (`:75-108`) already made this exact
choice for the exact same reason, and its docstring explains that deriving from the successor
pointer is correct *even for rows written before the deriving code existed*. Facts inherit that
robustness for free.
(3) **Cost.** The cascade is O(depth of the derivation chain) per fact read, and the design caps
depth at 4 (evidence → L1 → L2/L3 → L4). A scheduler would be new transport (hard rule 2) and a
new failure mode, to save a bounded, small cost.

*The transitive property, stated precisely:* because `evidence_ids` may contain `fact_id`s
(§3.1), and rule 4 marks a fact stale when **any** input is not current, staleness propagates
upward automatically with no write. A superseded L1 attempt fact makes its L2 job fact stale on
the next read, which makes the L3 workflow fact stale in turn.

*Optional optimisation, explicitly out of increment 1:* a batch `refresh_facts(scope_path)`
that re-runs reducers over the current evidence and emits fresh versions. It is a **performance**
tool, never a correctness requirement — the system must be correct with it switched off.

**The conflict resolution ladder** (deterministic, no LLM, first match wins):

```
1. Higher `authority` wins.                      (POLICY > SOURCE > MEASURED > DERIVED > ADVISORY)
2. Same authority, same reducer_version:         newer `observed_at` wins.
3. Same authority, DIFFERENT reducer versions:   the newer registered version wins IFF the older
                                                 version is deprecated in REDUCERS; else CONFLICTED.
4. Otherwise:                                    CONFLICTED — both facts stay, neither is current,
                                                 and every contract requiring this predicate gets
                                                 its `on_conflict` handling (§7.2).
```

*Why rule 3 refuses to auto-resolve two live reducer versions:* two undeprecated reducers
disagreeing about the same predicate is a **design error**, not a data condition. Silently
preferring one hides the error; surfacing `conflicted` forces someone to deprecate one. This is
the same instinct as `validate_step_selector` refusing a phase that declares both `model` and
`allowed_models` (`step_routing.py:184-186`).

---

## 5. OQ3 — The L0–L5 mapping to existing components

Condensed from the review's audit table, now stated as the target architecture. **Bold** = new.

| Level | Definition | Exists today | The plane adds | Facts available at ship time |
|---|---|---|---|---|
| **L0 Evidence** | Immutable observations and artifacts | `PhaseResult`/`WorkflowRunResult` JSON, `StoryResult`, git commits, `test_runner` output, 9 KB producer families, `KnowledgeEvent`/`KnowledgeRecord` | *nothing* — L0 is complete | n/a |
| **L1 Canonical facts** | Typed, current, scope-bound statements | validity spine only (registry lifecycle) | **`CanonicalFact` + `attempt_facts/v1`, `job_facts/v1`, `spec_status/v1`** | `current_commit`, `phase_status`, `phase_test_verified`, `attempt_cost_usd`, `attempt_tokens_*`, `attempt_cache_hit_rate`, `attempt_confidence` (ADVISORY), `spec_status` |
| **L2 Job/phase state** | Goal, acceptance, attempts, blockers, risk | `PhaseResult` (typed but per-run, in-memory) | **`job_facts/v1`** | `job_accumulated_cost_usd`, `job_status`, `job_model_used`, `job_current_commit` |
| **L3 Workflow state** | Completed phases, deps, accumulated cost, slack | `_completed_phases` (git-derived, in-function) | **`workflow_facts/v1`, `workflow_health/v1`** | `workflow_phases_completed/remaining`, `workflow_status`, `workflow_cost_usd`, `workflow_health` |
| **L4 Workload/program** | Priorities, capacity, portfolio budget, value | *nothing durable* (queue telemetry is DB 1) | **nothing in increment 1** — see §9/§11 | *none* |
| **L5 Intent and policy** | Allowed models, max spend, permissions, priorities | prose policy records + per-spec config (`StopSpec`, `model_pool`) | **`policy_facts/v1`** (parses declared config into `declared` facts) | `allowed_models`, `max_spend_usd`, `max_attempts` |

**Where job / workflow / workload state lives:** in the *same* fact store, distinguished only by
`scope_type` + `abstraction_level` + the reducer that produced it. There is no separate "job
state table". *Why:* a second store would need its own identity, validity, and conflict rules —
three chances to disagree with the first store. One store, many scopes, is the only arrangement
where "exactly one canonical representation per fact" is checkable by a single mechanism.

**L4's honest status:** absent by necessity, not by oversight. Priorities, capacity, portfolio
budget, and business value have **no producer and no model** in this system (review §3d(iii)).
Declaring L4 predicates now would reproduce the exact failure the review documented — 23
`LEDGER_FIELDS` declared with zero writers, one of which (`deadline_slack`) would pass today's
gate and hand a controller a value that has never existed. §9 states what must happen first.

---

## 6. OQ4 — The Context Compiler: contracts, snapshots, and degradation

### 6.1 The decision-type contract (YAML, versioned, committed)

Contracts live in `experiments/contexts/<decision_type>.yaml`. *Why a separate directory
rather than inside the spec:* a contract is reusable across specs (many specs route steps),
while `RuleSpec` fact contracts (§7) are per-spec bindings. The contract declares the
**decision type's** needs; the spec declares **this experiment's** policy over it.

```yaml
# experiments/contexts/route_next_job.yaml
# The decision-type contract for "which model should execute the next workflow phase".
# Chosen as the FIRST contract because the decision already exists and is already made
# deterministically by step_routing.route_step (step_routing.py:424-469) — so the plane can be
# measured against a working baseline instead of being trusted on faith.
decision_type: route_next_job
contract_version: "route_next_job/v1"

# The scope at which this decision is made. The compiler resolves the scope_path from the
# caller's (scope_type, scope_id) and refuses a request whose scope_type differs.
decision_scope: job

# The action vocabulary this decision type may emit. The validator refuses anything else
# (check C3). Deliberately tiny: `route` chooses the next phase's model, `continue` accepts
# the default. Nothing here can stop, retry, or steer anything.
allowed_actions: [route, continue]

# Maximum age of the snapshot at APPLY time. Prevents a decision computed from state that has
# since moved from being applied — the TOCTOU guard. 300s is [H], chosen as ~2x a typical phase
# gap; it is a parameter, not a discovery.
max_snapshot_age_seconds: 300

# ── Invariants: L5 policy facts that CONSTRAIN the decision. A decision violating one is
#    refused by the validator (check C8), regardless of what the controller proposed.
invariants:
  - fact: allowed_models
    scope: workload          # inherited downward to this job (§10.2)
    on_missing: halt         # without knowing the allowed set, no routing decision is safe
    on_conflict: halt
  - fact: max_spend_usd
    scope: workload
    on_missing: classify     # absent ceiling => unconstrained; recorded as unknown, not invented
    on_conflict: prefer_higher_authority

# ── Objectives: what the decision optimizes. Mirrors the EXISTING preferences block
#    (step_routing.RoutingPreferences, step_routing.py:96-108) so the plane does not invent a
#    second objective language.
objectives:
  - signal: correctness
    direction: maximize
    weight: 2.0
  - signal: cost
    direction: minimize
    weight: 1.0

# ── Required facts: the state this decision is ALLOWED and REQUIRED to see. Anything not
#    listed here is NOT in the snapshot — that is the "a control agent must not receive all
#    available context" directive, made mechanical.
requires_facts:
  - fact: job_accumulated_cost_usd
    scope: self
    max_age_seconds: 600
    min_authority: MEASURED
    on_missing: classify        # a first phase has no accumulated cost yet — legitimately unknown
    on_conflict: halt

  - fact: workflow_phases_remaining
    scope: parent
    max_age_seconds: 600
    min_authority: DERIVED
    on_missing: halt            # routing without knowing how much work remains is guesswork
    on_conflict: halt

  - fact: phase_test_verified
    scope: self
    max_age_seconds: 3600
    min_authority: MEASURED
    on_missing: classify
    on_conflict: halt

# ── Explicitly excluded: named so a reader can see the exclusion is deliberate, and so a
#    future contributor must edit the contract (a reviewable act) to widen the controller's view.
excludes:
  - sibling_job_facts        # lateral reads are forbidden by the hierarchy (§10.2)
  - live_telemetry           # DB 1 is never a fact source (§10.4)
  - advisory_facts           # available in ControlContext.advisory, never citable (C5)
```

### 6.2 The compiler

```python
def compile_context(request: ContextRequest, *, store: FactStore, now: str) -> ControlContext:
    """Build the decision-specific snapshot. Deterministic; no LLM; no network beyond the store.

    Algorithm (each step exists for a reason stated after it):

      1. Load the contract for request.decision_type; refuse an unknown or version-mismatched
         contract.                       — an unversioned contract cannot be audited later.
      2. Resolve request.(scope_type, scope_id) to a full scope_path.
                                          — every downstream visibility check is a path check.
      3. For each requires_facts entry, resolve the slot at the requested scope using the
         visibility rules of §10.2 (self / parent / named ancestor).
                                          — resolution is by ADDRESS, never by search.
      4. Classify each resolution: satisfied | unknown | stale | conflicted, using fact_state()
         (§4.5) and the entry's max_age_seconds / min_authority.
                                          — the four outcomes map 1:1 onto the four handlings.
      5. verify_chain() every satisfied fact; a chain failure DEMOTES it to `unknown`
         (with reason "broken derivation chain") rather than silently including it.
                                          — a fact whose provenance cannot be checked is not a fact.
      6. Resolve invariants the same way, into ControlContext.invariants.
      7. Apply on_missing / on_conflict handling to compute `admissible` (§6.3).
      8. Collect every advisory fact in scope into .advisory (visible, never citable).
      9. Compute snapshot_id (§6.4) and freeze.
    """
```

### 6.3 The snapshot, and how degradation is surfaced

```python
@dataclass(frozen=True)
class ControlContext:
    """What a controller is allowed to know for ONE decision. Frozen and content-addressed.

    The four "negative" collections (unknowns, conflicts, stale, advisory) are the design's most
    important feature and the direct answer to the review's finding that retrieval cannot
    distinguish "no evidence exists" from "all evidence was scope-excluded" (review §3a.5). A
    controller reading this snapshot can always tell WHY something is not here.
    """
    snapshot_id: str
    decision_type: str
    contract_version: str
    scope_path: str
    compiled_at: str            # NOT part of snapshot_id — see §6.4

    invariants: tuple[FactRef, ...]     # L5 constraints that bound any decision
    objectives: tuple[Objective, ...]   # what to optimize (from the contract)

    workload: tuple[FactRef, ...]       # L4 — empty in increment 1, and honestly so
    workflow: tuple[FactRef, ...]       # L3
    job: tuple[FactRef, ...]            # L2
    resource: tuple[FactRef, ...]       # model/pool facts (measured signals)

    unknowns: tuple[Unknown, ...]       # required, absent — with the reason
    conflicts: tuple[Conflict, ...]     # required, multiple current values — with all candidates
    stale: tuple[StaleFact, ...]        # required, present, past its age bound — with the age
    advisory: tuple[FactRef, ...]       # visible context; NEVER citable in facts_used

    evidence_ids: tuple[str, ...]       # transitive closure — the audit trail for the decision
    admissible: bool
    refusal: str                        # non-empty iff admissible is False

@dataclass(frozen=True)
class FactRef:
    """A fact as the controller sees it: the value plus everything needed to judge and cite it."""
    fact_id: str
    predicate: str
    subject_id: str
    scope_path: str
    value: str
    value_type: str
    authority: str
    epistemic_status: str
    observed_at: str
    age_seconds: int          # computed at compile time against `now` — the controller never
                              # computes ages itself, so freshness policy lives in ONE place
    reducer_version: str
    evidence_ids: tuple[str, ...]

@dataclass(frozen=True)
class Unknown:
    predicate: str
    scope: str
    reason: str               # "no_fact" | "broken_chain" | "below_min_authority" | "out_of_scope"
    handling: str             # the contract's on_missing for this entry
```

**Halt vs degrade** is decided per requirement by `on_missing` / `on_conflict`, never globally:

| Handling | Effect on the snapshot | When to use it |
|---|---|---|
| `halt` | `admissible = False`, `refusal` names the predicate; **the controller is never invoked** | The decision is unsafe without it (e.g. `allowed_models`) |
| `escalate` | `admissible = False` **and** an advisory flag record is emitted onto the human rail | A human should know a decision could not be made |
| `classify` | Materialised in `unknowns`; `admissible` stays True; the controller may act but **may not cite it** (C5) | Legitimately-absent values (a first phase has no accumulated cost) |
| `investigate` | `admissible = False` **and** a `measurement_gap` advisory record naming the predicate is emitted | The absence is itself the finding — this is the plane feeding measure-before-policy |

*Why per-requirement rather than a global policy:* the same missing fact is fatal for one
decision and irrelevant for another. A global "fail closed" would make the plane unusable; a
global "degrade" would make it unsafe. The contract is the only place that knows.

### 6.4 `snapshot_id` semantics

```
snapshot_id = sha256(
    contract_version | decision_type | scope_path
    | join(sorted(fact_id for every fact in the snapshot))
    | digest(unknowns) | digest(conflicts) | digest(stale)
)
```

`compiled_at` is **excluded** from the hash.

*Why exclude the timestamp:* it makes the snapshot **content-addressed** — identical state
yields an identical `snapshot_id`. Three things follow. (a) *Idempotence*: recompiling for a
retry produces the same id, so a decision can be matched to state without a lookup table.
(b) *Provable identity of inputs*: two decisions carrying the same `snapshot_id` were provably
made from identical state — invaluable when comparing control arms. (c) *Cacheability* for free.

This is the same reasoning `record_to_artifact` uses when it blanks `valid_from`/`observed_at`/
`indexed_at` from the hash input (`record_factory.py:77-83`) — "stable across re-derivations,
which is exactly what makes the producer idempotent". Freshness is carried by
`FactRef.age_seconds` and enforced by `max_snapshot_age_seconds` at apply time, so excluding the
timestamp from the identity costs no safety.

---

## 7. OQ5 — Fact contracts in `RuleSpec`: the generalized load-bearing rule

> **From:** "to make policies, we need information."
> **To:** *no control action may consume a value that is not canonical, current, scope-valid, and
> produced by a declared source or reducer.*

### 7.1 The extension (backward compatible by construction)

```python
@dataclass
class FactRequirement:
    """One fact a rule consumes, with its currency and failure semantics.

    This generalizes today's bare-string `requires` entry (experiment_spec.py:164). The review
    found that the current gate proves SCHEMA AVAILABILITY but not FACT CURRENCY (§4.4): a rule
    requiring `deadline_slack` passes today because the NAME is in LEDGER_FIELDS, even though
    nothing has ever written a value. Every field below exists to close one part of that gap.
    """
    fact: str                       # predicate name; must exist in FACT_PREDICATES
    scope: str = "self"             # self | parent | workload | organization | <scope_type>
    max_age_seconds: int | None = None
    min_authority: str = "DERIVED"  # never "ADVISORY" — refused (R5)
    on_missing: str = "halt"        # halt | escalate | classify | investigate
    on_conflict: str = "halt"       # halt | escalate | prefer_higher_authority | classify
    value_type: str | None = None   # optional assertion against the registry (catches drift)

@dataclass
class RuleSpec:
    """UNCHANGED fields, ONE addition. The old shape keeps working."""
    name: str
    plane: str
    evidence_class: str
    requires: list[str] = field(default_factory=list)          # legacy: ledger field names
    produces: list[str] = field(default_factory=list)
    requires_facts: list[FactRequirement] = field(default_factory=list)   # NEW

    @staticmethod
    def normalize_requirement(entry: str | dict) -> FactRequirement:
        """A bare string means the legacy contract, made explicit.

        `"confidence"` == FactRequirement(fact="confidence", scope="self",
                                          max_age_seconds=None, on_missing="halt").
        Why normalize rather than fork the code paths: one validator, one set of error messages,
        and every existing spec keeps validating unchanged — which matters because 60+ spec YAMLs
        are committed and none of them should need editing for this design to land.
        """
```

### 7.2 A complete contract in a spec

```yaml
rules:
  # A MEASUREMENT rule: produces facts, consumes only evidence. Unchanged shape.
  - name: workflow_progress
    plane: measurement
    evidence_class: "[C]"
    requires: []
    produces: [workflow_phases_completed, workflow_phases_remaining, workflow_status]

  # A CONTROL rule: consumes facts under a full contract. This is the new shape.
  - name: route_next_job
    plane: control
    evidence_class: "[H]"
    decision_type: route_next_job          # binds to experiments/contexts/route_next_job.yaml
    requires_facts:
      - fact: workflow_phases_remaining
        scope: parent
        max_age_seconds: 600
        min_authority: DERIVED
        on_missing: halt
        on_conflict: halt
      - fact: job_accumulated_cost_usd
        scope: self
        max_age_seconds: 600
        min_authority: MEASURED
        on_missing: classify
        on_conflict: halt
      - fact: allowed_models
        scope: workload
        max_age_seconds: null              # policy facts are not volatile
        min_authority: POLICY
        on_missing: halt
        on_conflict: halt
    produces: [route_decision]
```

### 7.3 What the compiler refuses, and when

The critical split, and the design's direct answer to review §4.4:

> **Compile time proves PRODUCIBILITY. Run time proves CURRENCY.**
> The compiler can know whether anything *could ever* produce a fact. It cannot know whether a
> value *exists right now* — that is the Context Compiler's job, every time, per decision.

```python
def validate_fact_contracts(spec: ExperimentSpec) -> list[str]:
    """Compile-time refusals. Composed into validate_spec() alongside validate_rules().

    Returns error strings in the existing house style (experiment_spec.py:405-408) so a failing
    spec reads the same whichever gate rejected it.
    """
```

| # | Compile-time refusal | Error message (sketch) |
|---|---|---|
| R1 | Predicate not in `FACT_PREDICATES` | `rule "route_next_job" requires fact 'deadline_slack' — no such predicate is declared. Declare it with a producing reducer first.` |
| R2 | Predicate declared but `produced_by` is empty | `rule "x" requires 'budget_remaining' — declared but produced by no reducer. Instrument it first.` |
| R3 | No reduction ladder: a required predicate's reducer `consumes` something nothing produces | `rule "x" requires 'workflow_health' — its reducer workflow_health/v1 consumes 'deadline_slack', which no reducer produces. The ladder is incomplete.` |
| R4 | Scope unreachable from the rule's decision scope | `rule "x" requires 'attempt_cost_usd' at scope 'attempt' from a workload-scoped decision — no aggregation reducer exists. Declare one or raise the requirement's scope.` |
| R5 | `min_authority: ADVISORY` | `rule "x" requires 'supervisor_verdict' at min_authority ADVISORY — a control rule may never consume an advisory value.` |
| R6 | Volatile predicate with `max_age_seconds: null` | `rule "x" requires volatile fact 'workflow_status' with no max_age_seconds — a control rule may not consume a volatile fact with unbounded age.` |
| R7 | `on_missing`/`on_conflict` outside the vocabulary | `rule "x": on_missing 'retry' is not one of ['classify','escalate','halt','investigate']` |
| R8 | `value_type` disagrees with the registry | `rule "x" requires 'job_accumulated_cost_usd' as 'int'; the registry declares 'usd'.` |
| R9 | Control rule with a `decision_type` that has no contract file | `rule "x": decision_type 'rebalance_fleet' has no contract in experiments/contexts/` |
| R10 | Contract/rule disagreement — the rule requires a fact the contract excludes | `rule "x" requires 'sibling_job_cost'; contract route_next_job/v1 excludes sibling_job_facts.` |

And at **run time**, the Context Compiler refuses (i.e. returns `admissible=False`) when a
required fact is **absent**, **stale**, **conflicted**, **out of scope**, or **lacks a valid
derivation chain** — each subject to that requirement's `on_missing`/`on_conflict` handling
(§6.3). These five are precisely the conditions the spec's `hard_rules` (6) names, and they are
runtime conditions by nature: no static analysis can know them.

*Why the two gates must both exist:* compile-time alone permits the `deadline_slack` failure
(name declared, never written). Runtime alone permits a spec to ship naming a predicate nothing
can ever produce, failing only in production, per decision, forever. Together they are the
generalized load-bearing rule.

---

## 8. OQ6 — `ControlDecision`, `ControlValidator`, and the actuation boundary

### 8.1 The minimal first action set

| Action | In increment 1? | Rationale |
|---|---|---|
| `continue` | **Yes — applied** | The null action. Must exist so "the controller ran and chose nothing" is distinguishable from "the controller did not run". |
| `route` | **Yes — applied** | Chooses the next phase's model. `step_routing.route_step` already makes exactly this choice deterministically, in-process, before execution; it is reversible, adds no new actuation surface, and gives a measurable baseline. |
| `retry` | Proposal only | No attempt lineage is measured (review §3d(ii)); a retry whose outcome cannot be attributed is unmeasurable. |
| `escalate` | Proposal only | Escalation targets a human; it belongs on the flag rail until measured. |
| `stop` | Proposal only | Irreversible. Requires `max_spend_usd`/deadline facts that do not exist. |
| `split`, `parallelize`, `pause`, `rollback` | **No** | Each requires a dependency model the system does not have (review §2 row 4). |

*"Proposal only" means:* the decision is constructed, validated, and durably recorded, and then
surfaced as a flag for a human — never applied by an automated path. This is how a control rule
earns the right to act: by being measured while inert.

### 8.2 `ControlDecision`

```python
@dataclass(frozen=True)
class ControlDecision:
    """A typed, validated, provenance-carrying proposal to change the future.

    Persisted as source_type="actuation" (REUSE — knowledge.py:141, actuation_ingestion.py),
    NOT as a new record family. The review found (§4.1) that the envelope, identity, POLICY
    authority, action vocabulary, `causes` lineage requirement, and the armed gate already
    exist with zero call sites, and that inventing a parallel decision type would give the
    system two decision families with two lineage gates. This dataclass is therefore the TYPED
    PAYLOAD that travels in that record's body, plus four fields the existing payload lacks.
    """
    decision_id: str
    snapshot_id: str
    """The snapshot this decision was made from. Also the resolution of `causes`: the snapshot
    is itself registered as an observation-family record, so the actuation record's single-valued
    `causes` (knowledge.py:343) points at the snapshot, and the snapshot carries the full
    evidence set. This is what makes one `causes` pointer SUFFICIENT — the review flagged
    (§4.1) that `causes` alone cannot express "this decision used seven facts"; via the snapshot
    it can, without touching knowledge.py."""
    decision_type: str
    contract_version: str

    action: str                     # continue | route | retry | escalate | stop
    target_type: str                # job | workflow | attempt
    target_id: str
    parameters: dict[str, Any]      # e.g. {"model": "anthropic/claude-haiku-4-5"}

    facts_used: tuple[str, ...]
    """fact_ids actually consumed. MUST be a subset of the snapshot's canonical facts (C5).
    Not decorative: this is what lets a later analysis ask "which facts, at which values, led to
    decisions that produced good outcomes" — the plane's own measurement."""

    expected_effect: tuple[ExpectedEffect, ...]
    """The falsifiable prediction. Recording it BEFORE execution is what turns control into an
    experiment: the same `compare_arms` machinery (compile_experiment.py:142-209) can then score
    predicted against measured. A controller that never predicts can never be wrong, and a
    controller that can never be wrong cannot be improved."""

    preconditions: tuple[Precondition, ...]
    proposed_by: str                # "policy_rule:route_next_job" | "operator:<id>" | "advisor:<model>"
    proposed_at: str
    rationale: str                  # free text; NEVER load-bearing — validators ignore it

@dataclass(frozen=True)
class Precondition:
    """A condition re-checked against a FRESH snapshot at apply time (C7) — the TOCTOU guard.

    Why re-check rather than trust the snapshot: between compile and apply, a phase may finish,
    a cost may cross a ceiling, a policy may change. Without re-checking, the plane would apply
    decisions derived from a world that no longer exists — which is precisely the failure mode
    the whole design exists to prevent.
    """
    fact: str
    scope: str
    op: str                 # eq | ne | lt | lte | gt | gte | in | is_true | is_false
    value: Any
    max_age_seconds: int

@dataclass(frozen=True)
class ExpectedEffect:
    predicate: str          # the fact expected to move
    direction: str          # increase | decrease | unchanged
    magnitude: float | None
    horizon: str            # "next_phase" | "end_of_workflow"
```

### 8.3 `ControlValidator` — ten ordered checks

```python
def validate_decision(decision, *, snapshot, fresh_snapshot, contract, now) -> ValidationResult:
    """Admit or refuse. Deterministic, total, and ordered — first failure short-circuits.

    Ordered cheapest-and-most-fundamental first, so a refusal names the most basic thing that
    was wrong rather than an incidental downstream symptom.
    """
```

| # | Check | Refuses when | Why it exists |
|---|---|---|---|
| C1 | Snapshot binding | `decision.snapshot_id` unknown, or its `decision_type`/`scope_path` differ | A decision with no verifiable state origin is unauditable |
| C2 | Snapshot admissibility | `snapshot.admissible` is False | The compiler already refused; the controller should never have run |
| C3 | Action vocabulary | `action ∉ contract.allowed_actions` | The contract, not the controller, bounds what can be done |
| C4 | Target scope | `target_id` is not within `snapshot.scope_path` | Prevents a job controller acting on another job |
| C5 | Facts citation | `facts_used ⊄ canonical facts of the snapshot`; or cites an advisory / unknown / stale / conflicted entry | **The hard-rule-3 enforcement point**: LLM judgment can never become a reason |
| C6 | Derivation chains | `verify_chain()` fails for any cited fact | Second, independent check (mirrors `publish_event`'s belt-and-braces lineage gate) |
| C7 | Freshness + preconditions | `now - snapshot.compiled_at > contract.max_snapshot_age_seconds`, or any precondition is false on `fresh_snapshot` | The TOCTOU guard |
| C8 | Policy invariants | The action would violate an invariant (model ∉ `allowed_models`; projected spend > `max_spend_usd`) | Policy outranks any controller — the `Authority` ordering made executable |
| C9 | Actuation authorization | `action ∉ AUTOMATABLE_ACTIONS` for an automated proposer; or the spec's control rule did not pass the compile gate; or the target is a live session and the proposer is not human | **The supervisor-boundary enforcement point** (§8.6) |
| C10 | Recordability | The decision cannot be rendered as a valid actuation record (missing `causes`, unresolvable snapshot record) | A decision that cannot be recorded must not be applied — no unlogged actions |

```python
#: The ONLY actions an automated proposer may have APPLIED in increment 1.
#: Both are pre-execution, in-process, reversible choices that the system already makes
#: deterministically today. Widening this set is a deliberate, reviewable edit — never a config
#: value, never an env var, because "what may a machine do without a human" should require a
#: code review to change.
AUTOMATABLE_ACTIONS: frozenset[str] = frozenset({"continue", "route"})
```

### 8.4 Where `step_routing` sits now

`step_routing.route_step` becomes **the reference implementation of the `route_next_job` control
rule** and is not modified. In increment I4 the plane runs *beside* it: for every routing call,
compile a `ControlContext`, run the fact-based rule, record both choices, and compare. In I7 —
and only after that comparison shows the fact-based rule is at least as good — a spec may opt
into applying the plane's choice.

*Why keep the old router:* it is pure, deterministic, tested, and correct for what it knows. The
plane's claim is that a router which also sees workflow state does better; that claim must be
**measured against the incumbent**, using `compare_arms`, not asserted.

### 8.5 The provenance chain, end to end

```
L0 evidence record (knowledge_id)
  └─▶ reducer (reducer_version, inputs_digest)
        └─▶ CanonicalFact (fact_id, evidence_ids)
              └─▶ ControlContext (snapshot_id = f(sorted fact_ids), registered as an observation record)
                    └─▶ ControlDecision (facts_used ⊆ snapshot; causes = snapshot's knowledge_id)
                          └─▶ actuation record (armed + lineage gates, knowledge_stream.py:182-192)
                                └─▶ execution (workflow_runner phase; PhaseResult)
                                      └─▶ measured outcome (L0 again → new facts)
                                            └─▶ expected_effect scored against measurement
```

Every arrow is a hash-linked, immutable step. Given any decision, one can recover the exact
facts, the exact reducer versions, and the exact evidence that produced it — and then ask
whether it was right.

### 8.6 The supervisor boundary — who may actuate what

The review corrected the proposal's framing here (§4.2): the supervisor never actuates, but the
*system* does — through a human-gated door (`docs/supervisor_design.md:100-151`). The invariant
is about **who**, not **whether**.

| Actor | May propose | May have applied | Gate |
|---|---|---|---|
| `supervise.py` (automated assessor) | observation + flag records only | **nothing** | Unchanged. `supervisor.py:1-6` keeps no OpenCode client; `supervise.py:56` still forbids recommending steering. **This design adds no call site to it.** |
| A control rule in a compiled spec | any action in the contract | only `AUTOMATABLE_ACTIONS`, and only after the spec passed both gates | C9 + the compile gate + `FINOPS_ACTUATION_ARMED` (unchanged, still default-off) |
| An LLM ("advisor") | nothing canonical — its output is an ADVISORY fact | **nothing** | C5. Structurally excluded, not merely discouraged |
| A human operator via the Control Room | steer / interrupt | steer / interrupt | The existing four-part authorization boundary (`docs/supervisor_design.md:104-116`) plus the actuation gates |

**Three commitments this design makes about actuation:**
1. It does **not** arm actuation. `FINOPS_ACTUATION_ARMED` stays default-off and this design
   adds nothing that sets it.
2. It adds **no** new actuation surface: `route`/`continue` are pre-execution in-process choices
   `workflow_runner` already makes.
3. It preserves the one-way property: everything the plane may apply automatically is
   reversible; everything irreversible (`stop`, `interrupt`, `rollback`) requires a human.

---

## 9. OQ7 — Implementation order (measure-before-policy)

The ordering rule, applied to itself: **a fact must be produced and observed before any contract
may require it; a contract must be compiled and logged before any rule may consume it; a rule
must be measured inert before it may be applied.**

| # | Increment | Ships | Consumed by | Gate before the next increment |
|---|---|---|---|---|
| **I0** | Fact schema + predicate registry | `CanonicalFact`, `FACT_PREDICATES`, `EPISTEMIC_MAP`, `"fact"` in `SOURCE_TYPES`, `verify_chain` | **nothing** — zero call sites, unit-tested only | Schema exercised in tests; a grep-for-zero-call-sites test, exactly as `actuation_ingestion.py:8-22` does |
| **I1** | **First reducer: `spec_status/v1`** | Spec-status facts from `spec_lifecycle`'s run-derived status | Nothing; visible via `registry.py query --record-type fact` | Facts appear in the registry with correct lifecycle across a supersede |
| **I2** | Ledger reducers | `attempt_facts/v1`, `job_facts/v1` over the typed run artifacts | Nothing | Facts reproduce the values already in the run JSONs, byte-for-byte on re-derivation |
| **I3** | Workflow reducer | `workflow_facts/v1` (+ `policy_facts/v1` for declared L5) | Nothing | Staleness cascade demonstrated: superseding an L1 fact makes the L3 fact resolve stale |
| **I4** | Context Compiler (read-only) | `context_compiler.py`, `route_next_job/v1` contract, snapshots recorded beside every `route_step` call | Logged, compared — **not consumed** | Snapshot admissibility rate and unknown/stale/conflict rates measured over a real campaign |
| **I5** | Fact contracts in the spec gate | `FactRequirement`, `validate_fact_contracts`, refusals R1–R10 | Compiler refuses bad specs | A spec requiring an unproduced predicate is refused with the right message |
| **I6** | Controller + validator, **shadow mode** | `control_rules/route_next_job`, `control_validator.py`, decisions recorded and validated but never applied | Recorded | Agreement/divergence vs `step_routing` measured; `expected_effect` scored |
| **I7** | Apply `route` for one opted-in spec | The seam in `run_workflow` | Applied | `compare_arms` shows non-inferior loss vs the deterministic router |
| **I8+** | Everything requiring new modelling | budget ownership, deadlines, dependencies, L4 | — | Blocked until the operator declares owners (see below) |

### Why `spec_lifecycle`'s spec-status facts go first

1. **Its inputs already exist.** `spec_lifecycle` derives status from run events and the existing
   ledger; the reducer consumes what that arm already produces. No new instrumentation.
2. **Zero volatility.** A spec's status changes on the timescale of days, so `max_age_seconds`
   pressure and the staleness cascade are exercised gently, not under load.
3. **Zero blast radius.** No control rule consumes spec status, so a wrong fact is inert.
4. **It exercises the entire pipe end to end** — reducer → payload → `build_record` → artifact →
   event → stream → `kb-registry-v1` → registry index → manifest compaction → lifecycle →
   `registry.py query` — on a case where a mistake is cheap.
5. **It has a natural supersede.** A spec superseded by another is exactly the case
   `generate_manifest`'s chain logic handles, so the reuse claim gets tested immediately.

*Dependency note (honest):* `spec_lifecycle` is running now and its `spec` `source_type` is not
yet committed (review §4.7). I1 must therefore either land after it merges or derive spec status
directly from the run JSONs. The design does not assume its output exists.

### The blocked items, and what would unblock them

| Blocked | Why | Unblocked by |
|---|---|---|
| `budget_remaining` | No budget *owner* is modelled. `StopSpec.budget_usd` is per-spec config nothing enforces | An operator decision: which scope owns a budget. Then `max_spend_usd` becomes a **declared** L5 fact and `budget_remaining` a derived L3/L4 fact |
| `deadline_slack` | No deadline is ever recorded | Same shape: declare `due_at` at a scope, then derive slack |
| `dependency_failed`, `critical_path` | No dependency edges exist between phases or jobs | Declaring dependencies in `workflow.params.phases` — a spec-schema change out of this design's scope |
| L4 workload facts | No capacity/priority/value is measured | Durable job-status artifacts (today only DB 1 telemetry) plus a priority model |
| `retry`/`stop` as applied actions | No attempt lineage is measured | Instrumenting `attempt_number`, `parent_attempt_id`, `retry_reason` — declared in `LEDGER_FIELDS`, written by nothing |

---

## 10. The scope hierarchy

### 10.1 Levels and addressing

```
organization  →  program  →  workload  →  workflow  →  job  →  attempt
                                                    ↘  resource (orthogonal: model, pool, queue)

scope_path := "org:<id>[/program:<id>][/workload:<id>][/workflow:<id>][/job:<id>][/attempt:<id>]"
```

Binding to identifiers that already exist — *why:* a hierarchy that invents new ids for things
the system already names guarantees two id systems and a mapping table to keep in sync.

| Scope | Bound to | Source |
|---|---|---|
| `organization` | `"agentic-dynamics"` | `knowledge_ingestion.REPOSITORY_ID` |
| `program` | *unused in increment 1* | — |
| `workload` | the spec name | `ExperimentSpec.name` |
| `workflow` | the workflow cell id | `workflow_runner._cell_id` (`wf_<spec>_<model>`) |
| `job` | the cell / story id | `cell_scope(workdir)` → `self-<worktree>`; `StoryResult.story_id` |
| `attempt` | phase name / session id | `PhaseResult.phase`, `PhaseResult.session_id` |
| `resource` | model id | `PROVIDER_PRICING` keys / `model_pool` entries |

### 10.2 Inheritance rules

```python
def scope_visible(requested: str, fact_scope: str, predicate: PredicateSpec) -> bool:
    """Can a decision at `requested` see a fact at `fact_scope`?

    THE HIERARCHICAL GENERALIZATION of retrieval.scope_excluded (retrieval.py:392-406), which
    today is an EQUALITY test. Equality becomes ancestor-prefix, and nothing else changes:

      * equal scope                          → visible (own facts)
      * fact_scope is a PREFIX of requested  → visible IFF the predicate is `inheritable` or
                                               abstraction_level == "policy"     (DOWNWARD flow)
      * requested is a prefix of fact_scope  → NOT visible (no peeking into descendants;
                                               aggregates must be produced by a declared reducer)
      * neither is a prefix of the other     → NOT visible (LATERAL reads are forbidden — this is
                                               the "a job controller sees no sibling-job details"
                                               rule, made mechanical)

    The empty-scope semantics are preserved EXACTLY as retrieval.py:396-405 defines them: an
    empty scope means unknown/legacy and is never a wildcard. A fact with no scope_path is not
    global; it is unusable by the plane. Restating this is not pedantry — silently treating
    empty as "global" is the single most likely way to leak another cell's state.
    """
```

**Downward flow — policy, objectives, constraints:**
1. A `policy`-level fact declared at scope S is visible at every descendant of S.
2. `Inheritable` non-policy facts follow the same rule (declared per predicate, default False).
3. **Nearest ancestor wins** on conflict — the most specific declaration overrides.
4. **Monotone tightening only.** A descendant may narrow an inherited constraint, never widen
   it: `max_spend_usd` resolves to the `min` over the ancestor chain; `allowed_models` resolves
   to the `intersection`. *Why:* if a descendant could widen, any job could grant itself
   unlimited budget, and L5 would be advisory in practice. Tightening-only makes the ordering
   `POLICY > everything` operational rather than decorative.

**Upward flow — facts:**
1. Aggregation happens **only** through a reducer whose `scope_type` is the parent and whose
   `consumes` names the child predicates. No implicit rollup, ever.
2. An aggregate fact exposes the **value, the count, and the `evidence_ids`** — never child
   identities in its payload. A sibling cannot read the `evidence_ids` anyway (they resolve to
   facts outside its visibility), so aggregation does not become a lateral-read side channel.
3. Aggregation is declared in the registry via `aggregates_from`, so the compiler can verify a
   ladder exists (refusal R4) before a rule requires the top of it.

### 10.3 Composition with the existing per-cell `repository_id`

The existing per-cell scope is **not replaced and not wrapped** — it is *identified* with one
level of the hierarchy:

> `cell_scope(workdir)` → `self-<worktree>` **is the `job` scope id.**

Consequences, all of them free:
- A job-scope fact carries `repository_id = "self-<worktree>"`, so the existing HARD retrieval
  pre-filter (`retrieval.py:973-981`) already isolates it from other cells even though facts are
  not retrieval candidates. Defence in depth at no cost.
- An explicitly non-empty `rag_params.repository_id` (the *shared-scope override* for coordinated
  parallel workstreams, `workflow_runner.py:22-29`) maps to a **workload**-scope id. The existing
  override semantics are preserved exactly: it is a deliberate widening, never a default.
- Facts above the job level carry the workload/organization id (`REPOSITORY_ID`), which is
  already the KB's default shared scope.

### 10.4 The two Redis planes

| Plane | Where | Contents | The plane's relationship to it |
|---|---|---|---|
| **Knowledge** | 6380 **DB 2**, `kb:v1:changes` | evidence records, fact records, registry index | **The only source of canonical facts.** Reducers write here; the compiler reads here |
| **Control / telemetry** | 6380 **DB 1** | `live.LivePublisher` pub/sub, `story_jobs`/`story_status`, supervisor flags | **Never read by the compiler.** Display, queueing, and human triage only |

**The rule, stated so it can be checked:** *if a value exists only on DB 1, it is not a fact.*
To become one it must be reduced from a durable artifact on the knowledge plane.

*Why so strict:* DB 1 values are ephemeral, unscoped, unauthenticated, and carry no validity
window — every property the fact plane exists to provide. A single "just read the status hash,
it's right there" shortcut would silently reintroduce all four.

*The concrete cost, stated plainly:* `cell_run_status` (queued/running/done/failed) is
**telemetry only** today (`pipeline_status.py:30-63`) and therefore cannot be an L1 fact. Any
contract needing live run status is blocked until a durable job-status artifact exists. The
design accepts that constraint rather than weakening the rule — this is the same call the
review made at audit row 5.

---

## 11. Scope boundary — what this design would NOT build, and why

| # | Not built | Why not |
|---|---|---|
| 1 | **A new fact database** | Hard rule 2. The registry + artifacts + stream already provide identity, hashing, durability, retries, dead-lettering, idempotence, lifecycle, and a CLI. A second store would duplicate all of it and drift. |
| 2 | **Any change to `retrieval.py`, `prompt_constructor.py`, or `knowledge.py` internals** | Hard rule 7. The only knowledge.py touch is one additive `SOURCE_TYPES` row — registration, the same pattern `spec_lifecycle` uses. |
| 3 | **An eager re-derivation scheduler** | §4.5. New transport, new failure mode, and read-time derivation is *more* correct under partial failure. Revisit only if profiling shows read cost matters. |
| 4 | **Any LLM in a reducer, the compiler, or the validator** | Hard rule 3. An LLM may only produce an ADVISORY fact, structurally excluded by `is_canonical` and check C5. |
| 5 | **L4 workload/portfolio facts** | Nothing measures capacity, priority, or business value. Declaring them would repeat the exact `LEDGER_FIELDS` failure the review documented — a name that passes the gate with no value behind it. |
| 6 | **`budget_remaining` / `deadline_slack`** | These are **modelling** gaps, not measurement gaps: no one has decided which scope owns a budget or a deadline. That is an operator decision, and it must precede instrumentation. |
| 7 | **A job dependency graph / critical path** | No dependency edges exist anywhere; the compiler DAG is a fixed 7-node chain. Inventing dependencies to satisfy a design would be fiction. |
| 8 | **Arming actuation, or any automated `steer`/`interrupt`/`stop`** | §8.6. `FINOPS_ACTUATION_ARMED` stays default-off; irreversible actions stay human-gated. |
| 9 | **Any change to `supervise.py` / `supervisor.py`** | The observe-only rail is preserved by adding nothing to it. |
| 10 | **Replacing `step_routing`** | It is pure, tested, and correct for what it knows. It becomes the reference control rule and the measurement baseline. |
| 11 | **A control-plane UI** | The Control Room already renders flags and telemetry; facts are queryable through `registry.py`. A UI before the facts are trusted would encourage acting on them before they are measured. |
| 12 | **Migrating existing records into facts** | Facts are derived forward from evidence, which is immutable and complete. A backfill is a reducer run over historical artifacts — available any time, not a prerequisite. |
| 13 | **A general rules/expression language for contracts** | The contract YAML is deliberately declarative and closed (fixed vocabularies for `on_missing`, `on_conflict`, `op`). An expression language would make refusals unpredictable, which defeats the gate. |

---

## 12. Traceability — how this design answers the review's corrections

| Review finding | Where answered |
|---|---|
| §4.1 ControlDecision is not greenfield; the actuation family already exists | §8.2 — `ControlDecision` is the typed payload of the existing `actuation` record; the snapshot resolves the single-valued `causes` limitation |
| §4.2 "Never steers" is about *who*, not *whether* | §8.6 — an explicit actor × permission table; `AUTOMATABLE_ACTIONS` is code, not config |
| §4.3 `conflicted`/`unknown` are new states, not reuse | §4.5 — added to the lifecycle vocabulary with a deterministic resolution ladder; §6.3 keeps `unknown` (no fact) distinct from `stale` (old fact) |
| §4.4 The gate proves schema availability, not fact currency | §7.3 — the compile-time/run-time split, refusals R1–R10, and the five runtime refusal conditions |
| §4.4 The gate is already duplicated in `validate_preferences` | §6.1 — the contract reuses `RoutingPreferences`' objective language rather than inventing a third |
| §4.5 `epistemic_status` would be a third overlapping axis | §3.4 — it is the *single* discriminator; `authority` and `evidence_class` are computed from it |
| §4.6 Token events are telemetry, not evidence | §10.4 — "if it exists only on DB 1, it is not a fact", with the cost accepted |
| §4.7 `JobRecord`/`AttemptRecord` are docs, not code | §5 — reducers consume the real types (`PhaseResult`, `StoryResult`) |
| §4.7 `spec_lifecycle` is a forward reference | §9 — I1 does not assume its `spec` source_type has landed |
| §3d(iv) The prose-projection defect | §3.3 — a fact's payload is canonical JSON inside `text`, hashed into its identity |
| §3a Relevance is not truth | §3.3 — facts are excluded from the search consumers entirely, so relevance cannot reach a controller |

---

## 13. Residual risks (handed to the verify phase)

1. **Payload-in-`text` is a deliberate overload.** It buys hashing, supersession, and idempotence
   for free, at the cost of making `text` non-prose for one `source_type`. Mitigated by excluding
   facts from the search consumers; the verify phase should confirm no consumer assumes `text`
   is prose.
2. **Read-time cascade depth.** Bounded at 4 today. If a future reducer ladder deepens, read cost
   grows linearly; the `refresh_facts` optimisation exists as the escape hatch.
3. **Contract proliferation.** One contract per decision type is right at 1–5 types and awkward at
   50. Not a problem in increment 1; worth revisiting before the third contract.
4. **The registry is append-only JSONL plus a compaction pass.** Fact volume is higher than
   document volume. If compaction becomes slow, the fix is a compaction cadence, not a new store.
5. **`spec_lifecycle` merge order** (§9) is a real sequencing dependency on work running now.
