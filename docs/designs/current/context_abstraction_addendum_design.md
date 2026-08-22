---
status: accepted
---
# Context Abstraction Plane — Addendum A (I8–I10) Design

**Spec:** Addendum A of `docs/designs/current/context_abstraction_design.md` (§A, lines 1460–1604) —
the three post-closure refinements I8 (`DomainProfile`/`ChallengeProfile`), I9 (`pattern`
epistemic class), I10 (typed session checkpoint).
**Phase:** `design` (phase 2 of 3 — `review` → **`design`** → `verify`).
**Prior phase:** `docs/designs/current/context_abstraction_addendum_review.md` (component audit;
every "what exists" claim below is that document's, and inherits its citations).
**Date:** 2026-08-22 · **Model:** deepseek/deepseek-v4-pro · **Branch:** `feature/cap-addendum-design`
**Deliverable rule:** design-only. This phase adds exactly one file
(`docs/designs/current/context_abstraction_addendum_design.md`) and modifies nothing under
`src/`, `scripts/`, `tests/`, or `admin/`. Every schema is a sketch, no file is created.

---

## 0. How to read this document

The addendum's own discipline governs: *"schemas are sketches, no file is created by this
addendum. I8–I10 are not part of `context_abstraction_implement`; they are implemented under a
follow-up design-only spec in the review → design → verify shape"*
(`context_abstraction_design.md:1468-1472`). This document is the **design** leg of that spec.

Three conventions, plus one structural fact that governs everything below:

- **NEW** marks a mechanism this design invents. **REUSE** marks a mechanism that already exists
  and names it with `file:line`. Where an addendum claim builds on something the frozen design
  only *sketches* (not code), it is marked **[design-only]** and the reserved home is cited.
- **Schemas are typed sketches** (dataclasses/YAML with docstrings + inline comments), the repo's
  convention (`AGENTS.md`: "Dataclasses over dicts", type hints on public signatures).
- **Citations are `file:line`**; the review's are inherited as-is, and every claim re-checked
  against the branch head.

> **The plane these increments refine does not exist in code yet** (review §0, §1). `EPISTEMIC_MAP`,
> `is_canonical()`, `FactRequirement`, `snapshot_id` are all **[design-only]**, holding empty
> reserved homes: `control/facts.py:1-8` (I0), `control/context_compiler.py:1-8` (I4),
> `core/contracts.py:1-8` (I5). This design therefore specifies I8/I9/I10 **against** those homes,
> and states per field whether it is *new-in-this-addendum*, *waits-on-I0/I4/I5*, or *exists*.

### The six hard rules (inherited verbatim from the frozen design, `context_abstraction_design.md:39-50`)

| # | Rule | How this design honours it |
|---|---|---|
| 1 | Design only — documents, no code changes | §7 |
| 2 | No new transport — reuse ledger, knowledge stream, registry/manifest, the Redis plane split | I8 persistence (§2.2), I9 reducer (§3.3), I10 (§4.2) |
| 3 | Deterministic reducers only; LLM judgment is ADVISORY always | I9 minting rules (§3.4), I10 DERIVED/ADVISORY split (§4.1) |
| 4 | Exactly one canonical representation, or explicitly unknown/conflicted | I8 profile versioning (§2.2), I10 demotion rule (§4.1) |
| 5 | Preserve the observe-only supervisor rail and the authority hierarchy | I10 §4.3 (`AUTOMATABLE_ACTIONS`), §7 |
| 6 | The generalized load-bearing rule is the gate | I8 composition rule (§2.3), I10 experiment (§4.4) |
| 7 | Do not redesign `knowledge.py` / `retrieval.py` / `prompt_constructor.py` | §7 |

---

## 1. Thesis

> **A profile declares *which* context and *what* strategy a domain and a challenge archetype
> bring to the same compiled snapshot. A pattern compresses measured campaign experience into one
> citable, validity-carrying fact. A checkpoint is the typed residue a session leaves for its
> successor. All three enter through the existing gate, none widens it.**

The frozen design left three gaps (`context_abstraction_design.md:1476-1479`): who selects the
contract and the deliberation stages, how validated experience becomes citable, and what durable
residue a session leaves when forked. The addendum names the three increments that close them.
This design gives each a **schema and a composition rule**, and — because the review established
the plane is design-only — it states plainly which of the four load-bearing primitives each
increment may assume (none of `EPISTEMIC_MAP`/`is_canonical`/`FactRequirement`/`snapshot_id` is
assumed to exist; each is either declared here or deferred to its owning increment).

One principle is used three times, and it is the load-bearing rule in its most direct form:
**a field that names a producer that does not exist is demoted or deferred, never silently
empty.** I8's profile `predicates`/`policies`/`patterns` must each resolve to a producing fact; I9's
`support`/`uncertainty` must come from real records; I10's `verified_facts`/`context_snapshot_id`
have no producer in v1 and are therefore demoted (§4.1). This is the review's constraint 6 made
into a rule (`context_abstraction_addendum_review.md` §5.6).

---

## 2. I8 — `DomainProfile` + `ChallengeProfile` (answers OQ1, OQ2, OQ3)

### 2.1 The dataclasses (NEW)

```python
# control/profiles.py  —  NEW reserved home (see §6). Frozen dataclasses: a profile is
# immutable, and a new version is a NEW record that supersedes the old one, exactly as a
# modified symbol is a new knowledge_id under a stable entity_id (knowledge.py:13-18).

@dataclass(frozen=True)
class DomainProfile:
    """The reusable, declared representation of ONE domain. Declared, never measured.

    A domain is *static configuration* about a whole class of work: which canonical sources are
    authoritative, which predicates this domain registers, which policy facts gate it, which
    pattern facts are in-domain, and which deterministic verification tools it trusts. None of
    these is measured by the plane — they are asserted by an operator (epistemic_status
    "declared", Authority.POLICY, evidence_class "[P]" — REUSE of the frozen EPISTEMIC_MAP row,
    context_abstraction_design.md:396). What *is* measured is the profile's *performance*,
    by campaign, before any profile is promoted (addendum A.2, context_abstraction_design.md:1530-1532).
    """
    domain: str                        # e.g. "software_delivery", "investing" — the profile's key
    profile_version: str               # "software_delivery/v1" — folded into knowledge_id (§2.2)
    canonical_sources: tuple[str, ...] # ARCHITECTURE.md, pyproject.toml, account_rules.md, ...
    predicates: tuple[str, ...]        # subset of FACT_PREDICATES this domain registers (NAMES, not ids)
    policies: tuple[str, ...]          # L5 policy fact ids (tests_must_pass, calls_only, ...)
    patterns: tuple[str, ...]          # I9 pattern fact ids considered in-domain
    verification: tuple[str, ...]      # deterministic tools: pytest, ruff, mypy, dependency guards

@dataclass(frozen=True)
class ChallengeProfile:
    """The working strategy for a problem archetype. SELECTED, never hard-coded (addendum A.2).

    The compiler loads a ChallengeProfile *by archetype name* at compile time; it does not bake
    stages in. Deliberation stages are per-archetype (§2.5); session handling is a declared
    policy that I10 turns into a measured decision (§4).
    """
    challenge: str                     # greenfield | cross_cutting | small_change | research
                                       # | incident | migration   (see §2.5 + the TASK_TYPES note)
    profile_version: str               # "challenge/cross_cutting/v1"
    context_requirements: tuple[FactRequirement, ...]   # [design-only] — §7.1 of the frozen
                                       # design (context_abstraction_design.md:959-975); resolved
                                       # by the compiler through the SAME requires_facts mechanism
    deliberation: tuple[str, ...]      # ordered stage names per archetype (§2.5)
    session_policy: SessionPolicy      # A.4 — session continuation/fork is a CAP decision (§4)
    verification_policy: tuple[str, ...]  # which of the domain's tools gate this challenge
```

**Why `profile_version` is a first-class field rather than derived:** the frozen design makes
reducer versioning free by folding `extractor_version` into `knowledge_id`
(`context_abstraction_design.md:201-204`). A profile is not reduced, it is authored; its "reducer
version" is the profile version, and it must be explicit so a supersession is a visible, auditable
act, not an accidental re-key.

**Why `predicates` are names while `policies`/`patterns` are ids:** the addendum writes
"`predicates: tuple[str, ...]` — the subset of FACT_PREDICATES this domain registers" and
"`policies: tuple[str, ...]` — L5 policy fact ids" (`context_abstraction_design.md:1504-1506`).
A predicate is a *schema* name (there is one `FACT_PREDICATES` table, [design-only]); a policy or
pattern is an *instance* with an id. The design keeps that distinction rather than flattening both
to ids, because a profile that claims a predicate with **no producer** must be refused at the
predicate level (see §2.3), while a profile that names a policy/pattern *fact id* that does not
resolve is an `unknown`, not a refusal.

### 2.2 Persistence and versioning — a `profile` is a `source_type` row, not a new store (answers OQ1)

**REUSE, not new transport (hard rule 2):** a profile persists exactly as `spec`/`policy` do —
an additive `SOURCE_TYPES` row, a producer following `spec_ingestion.py`'s shape, supersession
lineage through the existing registry.

```python
# knowledge.SOURCE_TYPES — ONE additive row (registration, not redesign; cf. hard rule 7).
# REUSE of the closed-by-default posture: an unregistered type defaults to "observation"
# (knowledge.py:168-181), so adding "profile" here is the same act spec_lifecycle performed
# for "spec" (knowledge.py:147).
"profile": SourceTypeSpec("observation", Authority.POLICY, "[P]"),   # NEW row
#            ^ observation family — a profile states what a domain/challenge DECLARES, never
#              an instruction to act. Mirrors the `spec` row's POLICY/[P] (knowledge.py:147).
```

| `KnowledgeRecord` field | Carries for a profile |
|---|---|
| `source_uri` | `profile://domain/{domain}` or `profile://challenge/{challenge}` |
| `logical_locator` | `domain_profile:{domain}` or `challenge_profile:{challenge}` |
| `repository_id` | the declaring scope (default `REPOSITORY_ID`, `knowledge_ingestion.py:93`) |
| `extractor_version` | `"profile/{profile_version}"` — the profile version is the extractor |
| `authority`, `evidence_class` | `POLICY`, `[P]` — **declared**, per §2.3 |
| `supersedes` | predecessor profile `knowledge_id` (REUSE `spec_ingestion.py:229,291`) |
| `text` | the canonical JSON payload (REUSE the frozen §3.3 payload-in-`text` decision) |

**Identity and version-chain (answers OQ1's "one record per what?"):**

```python
# REUSE knowledge.compute_entity_id (knowledge.py:192-199) and compute_knowledge_id
# (knowledge.py:202-211). The slot is keyed by (repository_id, profile name) — NOT version —
# so a version bump yields a NEW knowledge_id that supersedes the old one under a STABLE
# entity_id. This is the version-chain strategy (like code/finding/spec), which makes
# "the current profile" a single registry lookup, not a scan (frozen §3.2).
entity_id = compute_entity_id(
    repository_id  = repository_id,                 # the declaring scope
    source_uri     = f"profile://domain/{domain}",  # or profile://challenge/{challenge}
    logical_locator = f"domain_profile:{domain}",    # or challenge_profile:{challenge}
)
knowledge_id = compute_knowledge_id(
    entity_id       = entity_id,
    source_revision = source_revision,               # the commit that authored this version
    content_hash    = sha256(canonical payload),      # REUSE record_factory.build_record
    extractor_version = f"profile/{profile_version}", # the version IS the extractor
)
```

**Decision (OQ1): one record per (profile, version), not per (profile, predicate).**
*Why:* a profile is a *document-fact* — the reusable bundle. Splitting it into one fact per
predicate would multiply the supersession surface (N chains to keep consistent) and re-introduce
the scan the frozen design explicitly rejected (§3.2). A single record keeps "the current profile"
a lookup, and the `predicates`/`policies`/`patterns` fields are **references resolved at compile
time by address**, never embedded values. This is the same choice `spec_ingestion` makes (one
record per spec, lifecycle in the payload — `spec_ingestion.py:145-166`).

### 2.3 The composition rule — the contract stays the sole gate (answers OQ2)

The addendum's binding claim: *"the contract remains the sole gate — a profile cannot widen a
controller's view, because its `context_requirements` resolve through the same `requires_facts`
mechanism as §6.1"* (`context_abstraction_design.md:1494-1496`). This design makes that mechanical:

```python
def compose_requirements(
    contract: Contract,              # [design-only] the decision-type contract (frozen §6.1)
    challenge: ChallengeProfile | None,
) -> tuple[FactRequirement, ...]:    # [design-only] FactRequirement (frozen §7.1)
    """Merge a challenge profile's requirements into the contract's, contract-wins.

    The invariant this implements, in one sentence: a profile may ADD context a decision may
    see, but it may never RELAX what the contract requires and never ADMIT what the contract
    excludes. It is a source of FactRequirement entries, not a second gate and not a second
    authority — which is what "the contract remains the sole gate" means operationally.
    """
    merged: dict[tuple[str, str], FactRequirement] = {r.fact: r for r in contract.requires_facts}
    if challenge is None:
        return tuple(merged.values())
    for req in challenge.context_requirements:
        # (1) R10, extended to profiles: a profile may not require what the contract excludes.
        #     REUSE the refusal vocabulary (context_abstraction_design.md:1065); this is the
        #     "cannot widen the view" enforcement — the contract's `excludes` block is the ceiling.
        if contract.excludes(req.fact):
            raise ProfileCompositionError(f"profile requires {req.fact!r}; contract excludes it")
        if req.fact in merged:
            # (2) contract wins on every shared (fact, scope): the profile may only TIGHTEN
            #     (lower max_age_seconds, raise min_authority, stricter on_missing/on_conflict),
            #     never loosen — the same monotone-tightening rule as §10.2
            #     (context_abstraction_design.md:1352-1356). Loosening is refused.
            merged[req.fact] = tighten(merged[req.fact], req)   # NEW — pure, raises on loosen
        else:
            merged[req.fact] = req
    return tuple(merged.values())
```

**Why contract-wins with tighten-only:** a profile that could *relax* a contract requirement
(`on_missing: halt → classify`, or `min_authority: POLICY → DERIVED`) would let one archetype
silently widen what the decision is allowed to do — the exact "gate already duplicated" defect
the review flagged (`review.md` §4.4). Contract-wins plus tighten-only makes the composition
*monotone*, so the profile can never make the gate more permissive. The `excludes` refusal
(rule 1) is the profile-specific extension of the frozen R10 (`context_abstraction_design.md:1065`).

**Every profile requirement flows through the SAME compile gate (R1–R10) and the SAME runtime
resolution (compile_context steps 3–7, `context_abstraction_design.md:836-847`).** A profile
requirement naming an unproduced predicate is refused by R1/R2 exactly as a contract requirement
would be — so a profile cannot smuggle a dangling name (review §4.2, the `LEDGER_FIELDS` trap).

**Profile facts are `declared` (POLICY):** a profile fact carries `epistemic_status="declared"` →
`(Authority.POLICY, "[P]")` (REUSE `context_abstraction_design.md:396`). It **is** canonical
(`is_canonical()`: `authority >= DERIVED` and `lifecycle == "current"`, `context_abstraction_design.md:412-416`),
but it is *declared, not measured* — its performance is what campaigns measure, and nothing is
promoted before that (`context_abstraction_design.md:1530-1532`). A profile can therefore be read
by a controller, but a *policy derived from a profile's performance* must still climb the
measure-before-policy ladder.

**The three non-`context_requirements` profile fields are strategy inputs, not a second gate
(adversarial F2).** `compose_requirements` composes *only* `context_requirements`. The three
remaining profile fields — `verification_policy`, `deliberation`, `session_policy` — are selected
by the profile and must be bound by the same monotone rule or they become a concrete
widening path: `verification_policy` may only **add** tools to the contract's required
verification, never **drop** one a contract invariant depends on (monotone tightening,
`context_abstraction_design.md:1352-1356`); `deliberation` stages may reorder but never omit a
stage the contract's invariants rely on; `session_policy` is governed by §4.3 (fully shadow in
v1). The contract's `invariants` — not the profile — remain the sole *safety* gate; the profile is
a source of *strategy*, never of *constraints*. This is the precise sense in which "the contract
remains the sole gate": sole gate for safety; the profile contributes context and strategy through
the same resolution, never a parallel authority.

### 2.4 The `compile_context` signature change (answers OQ3's "what does it read")

The frozen signature (`context_abstraction_design.md:827`) gains two profile inputs; the request
gains two *selectors* so the compiler resolves by address, never search:

```python
def compile_context(
    request: ContextRequest,                       # [design-only] frozen §6.2 (decision_type,
                                                   #   scope_type, scope_id) — NEW: domain_id,
                                                   #   challenge_id selectors (default "")
    *,
    store: FactStore,                              # [design-only] frozen §6.2
    now: str,
    domain: DomainProfile | None = None,           # NEW — resolved profile inputs
    challenge: ChallengeProfile | None = None,     # NEW
) -> ControlContext:                               # [design-only] frozen §6.3
    """The §6 algorithm with two profile inputs (addendum A.2, context_abstraction_design.md:1519-1521).

    Resolution (NEW, added as step 0 — before the contract is loaded):
      0. resolve request.domain_id / request.challenge_id against the profile registry
         (PROFILES, §6) by address. An absent/unknown profile is a no-op (the contract alone
         governs); a present profile contributes requirements via compose_requirements (§2.3).
    Then steps 1–9 run unchanged (context_abstraction_design.md:830-848): the effective
    requires_facts are composed first, so the profile adds context through the SAME resolution,
    snapshot, and degradation machinery — never around it.
    """
```

**Why selectors + resolved inputs, not just passing the dataclasses:** the addendum says the
profile is *selected* (`context_abstraction_design.md:1510`). If the caller passed the dataclass,
selection would live in every caller. Selectors on the request keep selection at the composition
root and let the compiler resolve against the registry — the same "by address, never search"
discipline the frozen §6.2 step 1 uses for the contract.

**What execution-strategy routing selects (OQ3):** `route_step` selects a *model*
(`step_routing.py:188-233`) from `RouteState` (`runtime/routing.py:284-292`). I8 does **not**
extend `route_step`. It adds a *new* decision type — `select_execution_strategy` — whose contract
ships (in the implementation) at `experiments/contexts/select_execution_strategy.yaml` and whose
`allowed_actions` are the stage sequences of §2.5 plus the verification-tool subset. Its inputs
are exactly the profile + the facts the composed `requires_facts` resolves — i.e. the
`ChallengeProfile.deliberation` (stages), `verification_policy` (tools), and `session_policy`
(§4), none of which `RouteState` carries. The reference baseline it is measured against is
`route_step`'s fixed-model behavior, scored with the same `compare_arms` loss
(`compile_experiment.py:142-209`, REUSE) — because the claim "strategy-aware routing beats
model-only routing" must be measured against the incumbent, not asserted (frozen §8.4).

### 2.5 Deliberation stages per archetype (NEW table)

Each stage is a workflow phase name; the sequence is what `ChallengeProfile.deliberation` carries.
*Why a table and not code:* the stages are the *declared* default per archetype, selected (never
imposed) at compile time — the addendum's own framing (`context_abstraction_design.md:1526-1530`).

| `challenge` | `deliberation` stages |
|---|---|
| `greenfield` | `survey → scaffold → implement_core → wire_tests → verify → finish` |
| `cross_cutting` | `map_impact → identify_invariants → choose_sequence → implement_in_slices → regression_gates` |
| `small_change` | `locate → edit → lint_test → finish` |
| `research` | `state_hypotheses → measurable_variables → inspect_priors → design_discriminating_test → execute → accept_reject` |
| `incident` | `triage → reproduce → isolate_root_cause → patch → regression_gates → postmortem` |
| `migration` | `inventory → map_parity → migrate_in_slices → verify_behavior → regression_gates → cutover` |

**Reconciliation with `TASK_TYPES` (review §4.5):** the challenge axis is a *problem archetype*,
not a *task type*. `TASK_TYPES = {greenfield, feature_addition, integration, refactor, cross_cutting}`
(`core/session_types.py:40-42`) is the story-session phase vocabulary; `challenge` is the compiler's
strategy selector. They overlap on `greenfield`/`cross_cutting` and diverge elsewhere by design —
`small_change` ≈ `refactor`'s shallow case, `research`/`incident`/`migration` have no task-type
counterpart. The design **does not** re-fork `session_types.py` (review §4.5's warning): `challenge`
is a separate, compiler-owned enum declared here in `profiles.py`, with a *documented* mapping (not
a shared constant) to avoid the split-brain the review documented.

### 2.6 `SessionPolicy` (NEW — referenced by the addendum, never defined)

`ChallengeProfile.session_policy: SessionPolicy` (`context_abstraction_design.md:1516`) names a
type the addendum leaves undefined. This design defines it, and I10 (§4) makes it a decision:

```python
@dataclass(frozen=True)
class SessionPolicy:
    """The declared session-continuation strategy for a challenge archetype (A.4).

    Declared (POLICY) at profile construction; its *performance* is the I10 evidence-seed
    experiment's object (§4.4). Until that experiment lands, every non-null policy runs in
    SHADOW mode (recorded, surfaced, never applied) — the §8.6 boundary, addendum A.4.
    """
    policy: str                          # continue_default | fork_always | compress_and_fork
                                         # | escalate_on_failure  — the 4 arms of §4.4
    fork_when: tuple[str, ...] = ()      # conditions: "goal_changed", "model_changed", "phase_gap"
    max_fork_depth: int = 1              # bound on the fork chain
    compress_threshold_tokens: int = 0   # 0 = never auto-compress
    shadow_only: bool = True             # True until the evidence-seed experiment (§4.4) lands
```

---

## 3. I9 — the `pattern` fact kind (answers OQ4, OQ5)

### 3.1 The category axis — answered explicitly (adversarial vector 7, added post-review)

**Question:** does `pattern` belong in `EPISTEMIC_MAP` (a new way of knowing) or in the predicate
registry (a new *type of statement*)?

**Decision: `pattern` is a FACT KIND, not an epistemic status.** `EPISTEMIC_MAP` answers "how do
we know this?" — observed, verified, derived, declared, advisory. A pattern's epistemology is
always the same as any derived fact: a deterministic reducer computed it from measured evidence.
Adding `EPISTEMIC_MAP["pattern"]` would put a statement type on an axis that measures ways of
knowing, collapsing the two questions the frozen design deliberately keeps separate (review
§4.5: `epistemic_status` is the single discriminator; kind lives in the predicate). Concretely:

```python
# control/facts.py — NO new EPISTEMIC_MAP row. The kind is carried by the predicate:
#   FACT_PREDICATES["pattern"] = PatternPayload          # the fact-kind declaration
#   epistemic_status for every pattern fact is "derived"  # existing EPISTEMIC_MAP row:
#     EPISTEMIC_MAP["derived"] = (Authority.DERIVED, "[C]")   (context_abstraction_design.md:385-399)
```

This **deviates from Addendum A.3**, which proposed the additive row — deviation **D7** (design
§5, noted in the deviation table below): the payload is kept exactly as Addendum A specified; only
the categorical placement moves. *Why this deviation:* the frozen design's own discipline — the
three provenance axes (`epistemic_status` / `authority` / `evidence_class`) are computed from one
mapping so they can never disagree (§3.4). A `pattern` row would make `EPISTEMIC_MAP` a mixed
dictionary of "ways of knowing" and "statement types", inviting exactly the drift that mapping
was built to prevent.

**Why `DERIVED`/`[C]` and not `MEASURED` or `POLICY`:** a pattern is a *compressed abstraction over
measured evidence*, produced by a deterministic reducer — it is derived, not raw-measured, and it is
not operator-declared policy. The `DERIVED`/`[C]` pairing is already the repo's convention for
"analysis generated from measurements" (`Authority.DERIVED` docstring, `knowledge.py:75-76`), so the
existing `derived` row extends its meaning rather than inventing one (review §3b.1). The nominal
`SOURCE_TYPES` authority column remains documentation-only (`knowledge.py:110-113`); the real values
come from this map at construction time (the same arrangement the frozen verify cleared for `fact`,
`verify.md:258-262`).

### 3.2 `PatternPayload` (NEW — the typed body of every `pattern` fact)

```python
# control/facts.py — the payload type; persisted as the canonical JSON in `text` (REUSE frozen
# §3.3: payload-in-text so the value is inside the content hash).
@dataclass(frozen=True)
class PatternPayload:
    """The typed body of a `pattern` fact (addendum A.3, context_abstraction_design.md:1542-1551).

    Every field exists so a consumer can judge TRANSFERABILITY instead of blindly trusting the
    claim: what the abstraction says, over what population, under what conditions, with how much
    support, with what residual uncertainty, over what validity window, and from which experiment.
    """
    claim: str                      # the compressed abstraction: "incremental_refactor", ...
    population: str                 # what this pattern was learned over (the corpus slice, §3.3)
    conditions: tuple[str, ...]     # when it applied
    support: int                    # n of observations behind it — from real records (§3.3)
    uncertainty: float | None       # residual risk / interval width; None = not estimable
    validity_window: str            # the version/date range it claims to hold
    source_experiment: str          # lab-contract ref: "finding:<entity_id>:<knowledge_id>" (§3.5)
```

**`PatternPayload` → `CanonicalFact` field mapping (OQ5):** the payload is the `CanonicalFact`
value; the fact's own fields carry the epistemic grade.

| `CanonicalFact` field | Carries for a pattern |
|---|---|
| `predicate` | `"pattern"` — a new FACT_PREDICATES entry (produced by `pattern/v1`, §3.3) |
| `value` | the canonical JSON of `PatternPayload` (REUSE §3.3 payload-in-`text`) |
| `epistemic_status` / `authority` / `evidence_class` | `derived` / `DERIVED` / `[C]` (§3.1) |
| `abstraction_level` | `workload` (patterns are corpus-wide abstractions) |
| `scope_type` / `scope_id` | `workload` / the declaring scope (REUSE §10.1) |
| `evidence_ids` | the table-qualified refs of the records reduced (§3.5) |
| `reducer` / `reducer_version` | `pattern` / `pattern/v1` (§3.3) |

### 3.3 The pattern reducer (NEW — answers OQ4)

```python
# control/reducers/pattern.py — NEW reducer (in the reserved reducers/ package,
# control/reducers/__init__.py:1-9). Signature is the frozen Reducer/ReducerInput shape
# (context_abstraction_design.md:503-543), reused verbatim.

PATTERN_V1 = ReducerSpec(
    name="pattern",
    version="pattern/v1",
    level="workload",
    scope_type="workload",
    consumes=("finding", "review", "analysis"),   # the CANONICAL CORPUS tables — NOT the
        # retired _results_summary.json. REUSE canonical_corpus.TABLES =
        # ("story","review","analysis","finding") (canonical_corpus.py:81); the review's
        # constraint 4 (context_abstraction_addendum_review.md §5.4) is the binding rule here.
    produces=("pattern",),
    determinism="pure_with_injected_clock",        # REUSE the frozen §4.1 discipline
)

def pattern_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit `pattern` facts from measured finding/review/analysis records.

    Determinism requirements (the frozen §4.2 ones, restated because they are load-bearing for a
    citable fact): total order over inputs (sorted by record ref, §3.5), no wall-clock read
    (inp.now only), and a total function — a population slice with zero observations emits NO
    fact, never a support=0 fact.

    support  = the number of finding records in the population whose measured outcome matches
               the claim's conditions (a COUNT over real rows, never an estimate).
    uncertainty = a deterministic statistic over the same rows (e.g. the Wilson lower bound of
               the observed success rate, or the interval width); None when the slice is too
               small to estimate — the coverage invariant: an unavailable measurement is null,
               never zero (REUSE measurement_coverage.py:20-21,55-83).
    """
    ...
```

**Where `support` comes from (OQ4):** `support` is a *count over the canonical corpus's finding
rows* (`canonical_corpus.TABLES`, `canonical_corpus.py:81`), each row carrying structured
`test_executed_success`/`confidence`/`perturbation_strength` (`knowledge.py:342-345`). The
`population` string names the exact slice (e.g. `"finding:task=task_manager_api,condition=clean"`),
and `support` is the number of records in that slice satisfying `conditions`. **The coverage
invariant is the fabrication boundary**: an empty slice yields **no fact** (the reducer returns
`[]`), never a `support=0` fact — because "zero observations" and "zero successes" are different
claims, and conflating them is the exact "missing as zero" defect `measurement_coverage.py:20-21`
exists to prevent.

### 3.4 Minting rules — hard rule 3 made executable (answers OQ5's `is_canonical` interaction)

1. **Only a registered deterministic reducer mints a canonical pattern.** `pattern/v1` is the sole
   registered producer of the `pattern` predicate; `verify_chain` (frozen §4.4) refuses any pattern
   whose `reducer_version` is not in `REDUCERS`.
2. **An LLM may propose a pattern only as ADVISORY.** Its output is `epistemic_status="advisory"`
   → `(Authority.ADVISORY, "[H]")` (REUSE `context_abstraction_design.md:398`). Such a pattern is
   *stored* (recorded, displayed, studied) but is **structurally uncitable**: `is_canonical()`
   returns False (`authority < DERIVED`, `context_abstraction_design.md:412-416`), and validator C5
   refuses any decision whose `facts_used` cites it (`context_abstraction_design.md:1183`).
   [design-only both — the interaction is specified here, the code lands with I0/I6.]
3. **The reducer is pure** (injected clock, total order, no I/O) — so its output is reproducible
   and its `content_hash` (hence `fact_id`) is stable (REUSE the frozen §4.1 discipline).
4. **`support`/`uncertainty` come from real records, never fabricated** (§3.3).
5. **`is_canonical()` alone is NOT sufficient for the `pattern` class — `verify_chain()` is
   mandatory (adversarial F1).** `is_canonical()` (`context_abstraction_design.md:403-417`) checks
   only `epistemic_status`/`authority`/`lifecycle_state` — it does **not** check that a fact was
   minted by a registered deterministic reducer. A `pattern` fact carrying
   `epistemic_status="derived"` from any producer would therefore pass `is_canonical()` and enter
   a snapshot as canonical. The structural defence is `verify_chain()` (`context_abstraction_design.md:607-637`,
   checks 1–2: reducer registered, evidence resolves), which the compiler (step 5) and validator
   (C6) both run. This rule makes it a hard invariant for the pattern class: the `pattern`
   predicate's `produced_by` is exactly `("pattern/v1",)` — no other reducer, and no non-reducer
   producer, may mint a canonical `pattern` — and any `pattern` fact entering a snapshot must pass
   `verify_chain()`. Hard rule 3 is enforced by `verify_chain`, not by `is_canonical()` alone.

### 3.5 `source_experiment` via lab-contract refs (answers OQ5's cite-format half)

```python
source_experiment: str = record_id(payload)      # REUSE lab_contract.record_id →
        # "finding:<entity_id>:<knowledge_id>" (lab_contract.py:365-384) — byte-compatible with
        # the addendum's "finding:<entity_id>:<knowledge_id>" (context_abstraction_design.md:1550).
```

**REUSE, not a new cite format (review constraint 4):** the addendum says `source_experiment`
"reuses the contribution-lineage primitive merged in the closure (§A.5) rather than inventing a
second one" (`context_abstraction_design.md:1558`). That primitive is the v6 contract: the
table-qualified ref `record_id()` (`lab_contract.py:365-384`) for the single source experiment, and
the *set* of supporting records hashed with `refs_digest()` (`lab_contract.py:352-362`) into the
pattern fact's `inputs_digest`/`evidence_ids`. A consumer can therefore verify a pattern's evidence
exactly as `validate_contract` verifies a lab's (`lab_contract.py:620-793`): recompute the digest
from the resolver and compare. No new hash, no new format, no new transport.

---

## 4. I10 — the typed session checkpoint (answers OQ6, OQ7)

### 4.1 `SessionCheckpoint` with per-field epistemic markers (answers OQ6)

The addendum's schema (`context_abstraction_design.md:1567-1578`) is re-specified with a **final
grade per field**, applying the review's demotion rule (constraint 6): a field whose producer does
not exist is demoted, never silently empty.

```python
# control/checkpoint.py — NEW reserved home (§6). Persisted as a fact of predicate
# session_checkpoint/v1 through the existing pipe (frozen §3.3/§4.3): the deterministic
# components canonical, the session's narrative ADVISORY (addendum A.4).

@dataclass(frozen=True)
class SessionCheckpoint:
    goal: str                                  # [M] — WorkflowRunResult.goal (workflow_runner.py:160)
    completed: tuple[str, ...]                 # DERIVED [M] — _completed_phases git markers
                                               #   (workflow_runner.py:235-254) + index fallback (:290-328)
    current_revision: str                      # DERIVED [M] — _git_head (workflow_runner.py:227-232)
    verified_facts: tuple[str, ...] = ()       # v1 ADVISORY [H] — see DEMOTION below (was DERIVED)
    open_hypotheses: tuple[str, ...] = ()      # ADVISORY [H] — the session's own account
    failed_approaches: tuple[str, ...] = ()    # ADVISORY [H] — session's account (half-captured:
                                               #   PhaseResult.error/status, workflow_runner.py:89,81)
    next_action: str = ""                      # ADVISORY [H] — proposal, NEVER applied (§8.6,
                                               #   AUTOMATABLE_ACTIONS, context_abstraction_design.md:1196)
    acceptance_state: str = ""                 # DERIVED [C] — test_executed_success + status
                                               #   (workflow_runner.py:113,81); first_pass/accepted
                                               #   declared-not-written (experiment_spec.py:175-176)
    context_snapshot_id: str | None = None     # v1 None — see DEMOTION below (was required str)
    snapshot_available: bool = False           # NEW — explicit marker that no snapshot exists in v1
```

**Demotion rule (OQ6), stated once:**

| Field | Addendum's grade | v1 grade | Why |
|---|---|---|---|
| `verified_facts` | DERIVED ("canonical fact ids by reference") | **ADVISORY `[H]`** | There are no canonical facts (`control/facts.py:1-8` is a stub; no `source_type="fact"` in `SOURCE_TYPES`, `knowledge.py:125-150`). v1 populates it from `PhaseResult.selected_evidence_ids` (RAG evidence, `workflow_runner.py:106`) — *retrieval evidence, not canonical facts* — and marks it ADVISORY so nothing may cite it (C5). |
| `context_snapshot_id` | required `str` (§6.4) | **`str | None = None` + `snapshot_available=False`** | `snapshot_id` has no producer (`control/context_compiler.py:1-8`; formula at `context_abstraction_design.md:925-947` is [design-only]). A v1 checkpoint cannot carry it; the explicit `snapshot_available` flag keeps "no snapshot" distinguishable from "snapshot missing by accident". |
| `open_hypotheses` / `next_action` / `failed_approaches` | ADVISORY | ADVISORY (unchanged) | No capture surface today; populated by an ADVISORY producer (a best-effort `[H]` session-summary extractor over `PhaseResult.final_response`, `workflow_runner.py:99`), and structurally uncitable via C5. |
| `completed` / `current_revision` / `acceptance_state` | DERIVED | DERIVED (unchanged) | Derivability verified in the review §3c. |

**Are the three narrative fields ADVISORY annotations on the checkpoint record, or separate
`source_type` rows (OQ6's second half)?** **Separate ADVISORY records — NOT the canonical
checkpoint fact (adversarial F3).** `CanonicalFact` carries a SINGLE `epistemic_status`
(`context_abstraction_design.md:232`), and the fact's canonical JSON payload is exactly what
`content_hash` (hence `fact_id`) covers (`context_abstraction_design.md:333-361`). If the ADVISORY
narrative rode in the same payload, two defects follow: (a) an LLM-produced `next_action` would
re-key the CANONICAL fact's identity on every narrative edit — supersession noise driven by
non-canonical content; and (b) `is_canonical()`/C5 operate at **fact** granularity, so a controller
citing the checkpoint fact would receive the ADVISORY narrative as citable canonical content —
hard rule 3 violated at field granularity. The resolution: the `session_checkpoint` fact carries
ONLY the DERIVED fields; `open_hypotheses`/`failed_approaches`/`next_action` are emitted as
separate ADVISORY `source_type="checkpoint_narrative"` records that `is_canonical()` excludes and
C5 refuses. The addendum's "ride along as ADVISORY annotations" (`context_abstraction_design.md:1563-1564`)
is honoured at the *handoff* level — the checkpoint handoff bundles the canonical fact **plus** its
narrative records — not at the *fact* level.

### 4.2 The `session_routing` contract (answers OQ7)

```yaml
# experiments/contexts/session_routing.yaml   — NEW (in the contract directory I4 reserves;
# [design-only]: the directory does not exist today, review §I8.3).
decision_type: session_routing
contract_version: "session_routing/v1"
decision_scope: job                              # REUSE §6.1 decision_scope semantics
allowed_actions: [continue, fork, compress_and_fork, escalate]
max_snapshot_age_seconds: 300                    # [H] — ~2x a typical phase gap (REUSE the
                                                 #   frozen §6.1 value, context_abstraction_design.md:766)

# Invariants (the addendum's three, made mechanical; each is a validator C8-style check):
invariants:
  # (1) continue — the null action. Requires the checkpoint's context_snapshot_id to equal the
  #     freshly compiled snapshot's id AND unchanged goal/phase/model. In v1, snapshot equality
  #     degrades to goal+phase+model equality (see the v1 note below).
  - fact: checkpoint_goal_unchanged
    on_missing: halt
  - fact: checkpoint_phase_unchanged
    on_missing: halt
  - fact: checkpoint_model_unchanged
    on_missing: halt
  - fact: checkpoint_snapshot_identity      # snapshot_id == fresh snapshot id (v1: unenforceable)
    on_missing: classify                    # v1: no snapshot exists -> degrade, do not halt

  # (2) fork / compress_and_fork — never fork blind: a checkpoint must exist.
  - fact: checkpoint_present
    on_missing: halt                        # fork without a checkpoint is refused

  # (3) escalate — requires a checkpoint plus a model change.
  - fact: checkpoint_present
    on_missing: halt
  - fact: model_change_required             # escalate only when the model actually changes
    on_missing: halt

requires_facts:                              # what the decision is allowed to see (REUSE §6.1)
  - fact: session_checkpoint
    scope: self
    max_age_seconds: 600
    min_authority: DERIVED
    on_missing: classify                    # a first phase has no checkpoint yet — legitimately unknown
    on_conflict: halt
  - fact: workflow_phases_remaining          # REUSE the frozen §6.1 example
    scope: parent
    max_age_seconds: 600
    min_authority: DERIVED
    on_missing: halt
    on_conflict: halt

excludes:
  - sibling_job_facts                        # REUSE §6.1 — lateral reads forbidden (§10.2)
  - live_telemetry                           # DB 1 is never a fact source (§10.4)
  - advisory_facts                           # never citable (C5)
```

**`snapshot_id` semantics for a *session* (OQ7):** a session is not a single `decision_type` — it
spans many phases and many decisions. So the checkpoint's `context_snapshot_id` is **not** the id
of one decision snapshot; it is the id of the *session-context snapshot* — the snapshot the session
reasoned from at its last checkpoint. In the full design (once I4 lands) that is
`compile_context`'s output for the session's *current* phase, content-addressed (§6.4, so two
sessions with identical state produce the same id). **In v1 there is no snapshot producer, so the
`continue` invariant degrades:** `checkpoint_snapshot_identity` is `on_missing: classify`, and the
three equality invariants (`goal`/`phase`/`model`) — all checkable against existing fields
(`WorkflowRunResult.goal` `workflow_runner.py:160`; `PhaseResult.model` `workflow_runner.py:86`;
the fork chain's `prev_model` `workflow_runner.py:622`) — are what actually gate `continue` today.
This is the review's own prescription (demote, don't invent; `context_abstraction_addendum_review.md` §3c).

### 4.3 `AUTOMATABLE_ACTIONS` — what is code, what is a proposal

The existing set is `AUTOMATABLE_ACTIONS = {"continue", "route"}` (`context_abstraction_design.md:1196`),
where `continue` is the null action ("the controller ran and chose nothing",
`context_abstraction_design.md:1086`). This design's answer:

| Action | Automatable (code-applied) or proposal? | Reasoning |
|---|---|---|
| `continue` | **Proposal (shadow) in v1** — NOT the routing null-action `continue`. | The session-continuation `continue` is a *positive* decision (resume a session, carrying the stale-context risk the addendum prices at `context_abstraction_design.md:1587`), not the null "chose nothing" action that `AUTOMATABLE_ACTIONS`'s `continue` was designed for (`context_abstraction_design.md:1086`). Applying it would apply an unmeasured `[H]` trade. |
| `fork` | **Proposal** (recorded, validated, surfaced as a flag — never applied by an automated path). | Reversible but its value is an *unmeasured hypothesis* `[H]` (the continue-vs-fork trade, `context_abstraction_design.md:1587`). It earns the right to act by being measured inert — the frozen §8.1 "proposal only" doctrine (`context_abstraction_design.md:1093`). |
| `compress_and_fork` | **Proposal** | Same as `fork`, plus compression is destructive to context — strictly more consequential, so it stays inert until measured. |
| `escalate` | **Proposal** | Changes the model — a real actuation, and model-change requires a measured `escalation` result. In `ACTUATION_KINDS` (`actuation_ingestion.py:70`) but not in `AUTOMATABLE_ACTIONS`, and it stays out. |

**So `AUTOMATABLE_ACTIONS` is unchanged, and NO session action is applied in v1.** The routing
null-action `continue` in `{continue, route}` (`context_abstraction_design.md:1196`) is a *different*
action from the session-continuation `continue`; conflating them would admit an unmeasured `[H]`
session policy under C9. The `session_routing` controller therefore runs **fully shadow in v1** —
all four actions recorded and surfaced, none applied (the addendum's own "never applied",
`context_abstraction_design.md:1594-1595`) — and the runner's existing fork-chain
(`workflow_runner.py:591-597`, keyed on `prev_model == model_i`) remains the applied incumbent. A
session action graduates to `AUTOMATABLE_ACTIONS` only after the evidence-seed experiment (§4.4)
shows a non-inferior arm.

### 4.4 The 4-arm evidence-seed experiment (answers OQ7's "which signals")

```yaml
# The spec the implementation will compile — the measure-before-policy gate for promoting any
# session policy. NOT run by this design; specified here (§7).
name: session_policy_evidence_seed
question: >-
  Does continuing vs forking (with or without a checkpoint) vs escalating change verified success
  per dollar, net of cache and context-pressure effects?
workflow: {kind: agent_task, params: {phases: [...], fork: false}}   # arms control forking, not the runner
factors:
  - {name: model,       levels: [deepseek/deepseek-v4-pro, deepseek/deepseek-v4-flash]}   # 2 levels:
      # the escalate arm needs a target, and the model×policy interaction must be estimable (F5)
  - {name: session_policy, levels: [continue, fork_with_checkpoint, fork_blind, escalate_with_checkpoint]}
  - {name: repetition,  levels: [r1, r2, r3]}      # within-cell variance for the uncertainty term (F5)
design: factorial
rules:
  # The outcome measurement — requires are EXISTING ledger fields ONLY. No `snapshot_id`, no
  # `context_snapshot_id` (neither exists until I4). The four formerly-missing measured signals
  # are the backbone (experiment_spec.py:190-193).
  - name: session_policy_outcome
    plane: measurement
    evidence_class: "[C]"
    requires: [test_executed_success, confidence, tokens_in, tokens_out,
               tokens_answer, tokens_explanation, perturbation_strength]
    produces: [session_verified_success, session_context_growth]   # v1: only the WRITTEN-signal
        # derivable outcomes. session_cost_usd / session_cache_reuse / session_latency /
        # session_rework are PHASE 2, gated on instrumenting cost_inference / cache_hit /
        # service_time_ms / rework_cost (F5) — a produce may not depend on an unrequired input.
  # The shadow control arm — recorded, never applied (AUTOMATABLE_ACTIONS unchanged, §4.3).
  - name: session_policy_arm
    plane: control
    evidence_class: "[H]"
    requires: [test_executed_success, confidence, tokens_in, tokens_out]
    produces: [session_policy_decision]
comparison: {kind: effect_size, arm_factor: session_policy, loss: {cost: 1.0, quality: -5.0}}
stop: {budget_usd: 40.0, max_attempts: 3}     # 3 attempts/cell → the uncertainty term is estimable (F5)
adapt: {strategy: coordinate_descent, selection: highest_regret}
```

**The seven measured signals, mapped to existing ledger fields (with honest written-status):**

| Addendum signal (`context_abstraction_design.md:1592-1593`) | Existing ledger field | Written today? |
|---|---|---|
| verified success | `test_executed_success` (`experiment_spec.py:192`) | **Yes** — `workflow_runner.py:113` |
| total cost | `cost_inference` (`experiment_spec.py:184`) | **Declared-only** — writer is `PhaseResult.cost_usd` (`workflow_runner.py:92`); the I2 ledger reducers close this under the `attempt_cost_usd` predicate |
| cache utilization | `cache_hit` (`experiment_spec.py:172`) | **Declared-only** — written as `cache_read_tokens`/`cache_write_tokens`/`cache_hit_rate` (`workflow_runner.py:93-95`); a naming mismatch, not a measurement gap |
| latency | `service_time_ms` (`experiment_spec.py:171`) | **Declared-only** — raw writer is `PhaseResult.duration_s` (`workflow_runner.py:87`) |
| rework | `rework_cost` (`experiment_spec.py:187`) | **Declared-only** |
| repeated failures | `attempt_number` (`experiment_spec.py:159`) | **Declared-only** — raw writer is `PhaseResult.status`/`error` (`workflow_runner.py:81,89`) |
| context-token growth | `tokens_in` + `tokens_out` (`experiment_spec.py:179-180`) | **Yes** — `workflow_runner.py:605-612` |

**The load-bearing rule, applied to the experiment itself:** the *arms* (the four `session_policy`
levels) run in shadow mode, so they may be recorded before the declared-only signals are written;
but **no session policy is promoted** until the outcome signals are actually measured. The three
`requires` that are written today (`test_executed_success`, `confidence`, `tokens_*`) are what make
the shadow arm *writable* now; `cost_inference`/`cache_hit`/`service_time_ms`/`rework_cost`/
`attempt_number` must be instrumented (or read from the typed run artifacts, the review's
prescription) before the `session_policy_outcome` measurement rule can emit its `produces`. This is
the review's hard-rule risk for I10 (`context_abstraction_addendum_review.md` §6) made into the
experiment's own gate.

**Shadow-mode recording (OQ7's last question):** the `session_policy` decision is recorded through
the **existing `actuation` envelope** (`actuation_ingestion.py`, `source_type="actuation"`,
`knowledge.py:149`), *as a proposal* — the envelope already exists with zero call sites and its
`armed` gate default-off (`knowledge_stream.py:178-192`). Recording a proposal (not applying it)
does not arm anything: the record carries the decision, the snapshot it was made from (once I4
lands), and its `expected_effect`, and it is surfaced as a flag on the human rail. No new
observation type is needed — the review's §4.1 correction ("extend the actuation record, do not
add a second decision type") applies to session decisions exactly as it did to the controller's.

---

## 5. Deviation table

| # | Where | What this design changes vs Addendum A | Justification |
|---|---|---|---|
| D1 | I10 `SessionCheckpoint.verified_facts` | Addendum marks it `DERIVED` ("canonical fact ids by reference", `context_abstraction_design.md:1572`); this design **demotes it to ADVISORY `[H]` in v1**, populated from `PhaseResult.selected_evidence_ids` (`workflow_runner.py:106`). | No canonical facts exist (`control/facts.py:1-8`; no `source_type="fact"`, `knowledge.py:125-150`). Marking it DERIVED would ship a field that is empty forever — the `deadline_slack` failure (review §4.4). Demotion is the review's constraint 6. |
| D2 | I10 `SessionCheckpoint.context_snapshot_id` | Addendum has it as a required `str` (§6.4); this design makes it **`str | None = None`** with a NEW `snapshot_available: bool = False` flag, and the `continue` invariant degrades to `goal`+`phase`+`model` equality in v1. | `snapshot_id` has no producer until I4 (`control/context_compiler.py:1-8`; [design-only] formula `context_abstraction_design.md:925-947`). An explicit absent-flag keeps "no snapshot" distinguishable from "snapshot lost" (hard rule 4). |
| D3 | I9 minting, `is_canonical()` "unchanged" (`context_abstraction_design.md:1555`) | The design **adds** a mandatory `verify_chain()` for the `pattern` class: `is_canonical()` alone is insufficient, and `pattern.produced_by` is exactly `("pattern/v1",)`. | `is_canonical()` checks epistemic/authority/lifecycle only (`context_abstraction_design.md:403-417`); a non-reducer `derived` pattern would pass it. Deterministic-reducer enforcement lives in `verify_chain()`, which must be mandatory for a NEW DERIVED class (adversarial F1). |
| D4 | I8 "the contract remains the sole gate" (`context_abstraction_design.md:1494-1496`) | Narrowed to "sole **safety** gate": `verification_policy`/`deliberation`/`session_policy` are strategy inputs bound by monotone tightening, never a second authority. | The profile's three non-`context_requirements` fields are not composed by `compose_requirements`; without this narrowing they are a concrete widening path past the contract (adversarial F2). |
| D5 | I10 "narrative components ride along as ADVISORY annotations" (`context_abstraction_design.md:1563-1564`) | Implemented as **separate `checkpoint_narrative` ADVISORY records**, not same-fact annotations. | `CanonicalFact` has one `epistemic_status` and the payload is hashed into `fact_id`; a same-fact ADVISORY narrative would re-key the canonical fact and leak through C5 at fact granularity (adversarial F3). |
| D6 | I8 "profiles are L4's producer" (`context_abstraction_design.md:1488-1490`) | v1 profiles declare L5-policy-adjacent facts + their own predicates; they do **not** declare L4 workload facts (capacity/priority/value), which stay deferred per frozen §11.5. | Declaring L4 predicates now would reproduce the `LEDGER_FIELDS` failure the frozen design explicitly refuses (`context_abstraction_design.md:1415`); "L4 producer" is deferred until budget/deadline ownership is declared (adversarial F6). |
| D7 | A.3's additive `EPISTEMIC_MAP["pattern"]` row (`context_abstraction_design.md:1561`) | `pattern` is a **fact kind** carried by `FACT_PREDICATES`; its `epistemic_status` is the existing `derived` row. No new map row. | Epistemic status answers "how we know", the predicate answers "what type of statement"; a `pattern` map row would make `EPISTEMIC_MAP` a mixed dictionary of ways-of-knowing and statement types, inviting the drift §3.4 was built to prevent (adversarial vector 7, post-review). |

F4 (session `continue` conflation) and F5 (experiment sufficiency) are resolved by design edits that
**align with / specify within** Addendum A (A.4's "never applied" and "4 arms") rather than change
it, so they carry no deviation-table row; see §9. The `challenge`-vs-`TASK_TYPES` reconciliation
(§2.5) is a **clarification within** the addendum's own six values, not a change to them, so it is
not listed here.

---

## 6. Reserved-homes declaration (per increment)

Design-only: these are the homes the implementation will add files to; **no file is created now**.
Each new home is declared in the same zero-call-sites style the CAP homes already use
(`control/__init__.py:7-9`); the implementation extends that comment.

| Increment | New home | Contents | Extends |
|---|---|---|---|
| **I8** | `control/profiles.py` (NEW) | `DomainProfile`, `ChallengeProfile`, `SessionPolicy` (§2.6), the `PROFILES` lookup registry, the deliberation table (§2.5), `compose_requirements` (§2.3) | `control/__init__.py:7-9` reserved-homes comment (adds `profiles.py`) |
| **I9** | `control/reducers/pattern.py` (NEW) | `PATTERN_V1` + `pattern_v1` (§3.3) | the reserved `control/reducers/` package (`__init__.py:1-9`) |
| | `control/facts.py` (additive, I0 home) | `PatternPayload` (§3.2) + the `pattern` `FACT_PREDICATES` entry (kind-only; no `EPISTEMIC_MAP` row, §3.1) | the existing I0 home (`control/facts.py:1-8`) |
| **I10** | `control/checkpoint.py` (NEW) | `SessionCheckpoint` (§4.1) | `control/__init__.py:7-9` reserved-homes comment |
| | `control/reducers/checkpoint.py` (NEW) | `checkpoint/v1` — the deterministic reducer deriving the DERIVED fields (§4.1) | the reserved `control/reducers/` package |
| | `experiments/contexts/session_routing.yaml` (NEW) | the contract (§4.2) | the contract directory I4 reserves (review §I8.3) |
| | `control/rules.py` (I6 home, already reserved) | the `session_routing` shadow control rule (§4.3) | the existing I6 home |

No home is reserved for a profile *persistence producer* in this design — that is a
knowledge-plane producer (`knowledge/profiles_ingestion.py`, following `spec_ingestion.py`), and it
belongs to the implementation spec, not this addendum's design-only scope (§7).

---

## 7. Scope boundary — what I8–I10 do NOT build

| # | Not built | Why |
|---|---|---|
| 1 | **The fact layer itself** (`CanonicalFact`, `FACT_PREDICATES`, `EPISTEMIC_MAP`, `is_canonical`, `verify_chain`) | I0 owns these; this addendum only *references* them and declares the `pattern` row/`pattern` predicate (I9) against the reserved home `control/facts.py:1-8`. |
| 2 | **`snapshot_id` / the Context Compiler / `ControlContext`** | I4 owns them (`control/context_compiler.py:1-8`). I10 demotes `context_snapshot_id` rather than building a snapshot producer (§4.1, D2). |
| 3 | **`FactRequirement` / `validate_fact_contracts` (R1–R10)** | I5 owns them (`core/contracts.py:1-8`). I8's `compose_requirements` *calls* them; it does not reimplement them (§2.3). |
| 4 | **A profile persistence producer or a `profile` `SOURCE_TYPES` row** | Design-only: the row and the producer are *proposed* (§2.2), not registered. No `knowledge.py` change is made (hard rule 7). |
| 5 | **Any change to `retrieval.py` / `prompt_constructor.py` / `knowledge.py` internals** | Hard rule 7. The only `knowledge.py` touch in the whole design is one *proposed* additive `SOURCE_TYPES` row. |
| 6 | **Arming actuation, or any automated `fork`/`compress_and_fork`/`escalate`** | §4.3: `AUTOMATABLE_ACTIONS` is unchanged (`{continue, route}`); the three session actions stay proposal-only. `FINOPS_ACTUATION_ARMED` stays default-off. |
| 7 | **L4 workload/portfolio facts** | Profiles are "L4's producer" only in the sense that they are declared, measured-later facts; this design does not declare workload predicates (the review's `LEDGER_FIELDS` warning, §4.2). |
| 8 | **The LLM session-narrative extractor** for `open_hypotheses`/`failed_approaches`/`next_action` | Named (§4.1) as an ADVISORY `[H]` producer, but not designed or built — it is best-effort and structurally uncitable (C5). |
| 9 | **Running the evidence-seed experiment** | §4.4 *specifies* it; it is not run here. |
| 10 | **A general expression language, a new fact store, a re-derivation scheduler** | Inherited verbatim from the frozen §11 (`context_abstraction_design.md:1408-1422`). |

---

## 8. Traceability — how this design answers the review

| Review item | Where answered |
|---|---|
| §4.1 "the contract remains the sole gate" assumes a gate/contract that do not exist | §2.3 — `compose_requirements` is specified *against* the [design-only] `FactRequirement`/R1–R10, and states plainly it waits on I5 |
| §4.2 profiles re-enter the `LEDGER_FIELDS` trap | §2.1/§2.3 — `predicates`/`policies`/`patterns` are references resolved by address; a producerless name is refused by R1/R2, not silently empty |
| §4.3 "`is_canonical()` unchanged" presumes a predicate that does not exist | §3.1/§3.4 — the `pattern` kind is declared via `FACT_PREDICATES` with `epistemic_status="derived"` (no map row, D7); the LLM→ADVISORY interaction is specified (C5), not assumed |
| §4.4 `verified_facts` DERIVED is an over-claim | §4.1 D1 — demoted to ADVISORY in v1 |
| §4.5 `challenge` collides with `TASK_TYPES` | §2.5 — a documented mapping, no re-fork of `core/session_types.py` |
| §5 constraint 1 (treat the four primitives as planned) | §0 + every `[design-only]` marker; no primitive is assumed to exist |
| §5 constraint 2 (profile is a `source_type` row) | §2.2 |
| §5 constraint 3 (reuse the objective/contract vocabulary) | §2.3 (`requires_facts`), §4.4 (ledger fields) |
| §5 constraint 4 (pattern reducer consumes canonical corpus) | §3.3 (`consumes` = the corpus tables; no `_results_summary.json`) |
| §5 constraint 5 (reserve a profiles home) | §6 (I8 → `control/profiles.py`) |
| §5 constraint 6 (demote producerless DERIVED fields) | §4.1 D1/D2 |
| OQ1 (profile storage/identity/versioning) | §2.2 |
| OQ2 (context_requirements through the gate) | §2.3 |
| OQ3 (execution-strategy routing + baseline) | §2.4 |
| OQ4 (reducer input + `support`) | §3.3 |
| OQ5 (pattern authority + cite format) | §3.1, §3.2, §3.5 |
| OQ6 (v1 checkpoint grades + demotion) | §4.1 |
| OQ7 (session_routing identity/snapshot/shadow recording) | §4.2, §4.3, §4.4 |

---

## 9. Adversarial findings

**Role:** external critic, in the shape of `docs/review/finding_economics_review.md`. Six attack
vectors were worked; each produced at least one finding, and every finding was re-verified against
the tree (frozen design + code) before being written. Each finding is **resolved** — by a design
edit (with a one-line deviation note in §5) or by an accepted-risk entry with reasoning. Severity:
**material** = fixed in this edit; **minor** = noted, safe to defer.

### F1 — a `pattern` fact can be canonical without a deterministic reducer · **material** (vector 1)

**Attack:** does the pattern class violate hard rule 3 anywhere? **Yes, at the `is_canonical()`
boundary.** `is_canonical()` (`context_abstraction_design.md:403-417`) returns True for
`epistemic_status != "advisory" AND authority >= DERIVED AND lifecycle == "current"` — it does **not**
check that the fact was minted by a registered deterministic reducer. `verify_chain()`
(`context_abstraction_design.md:607-637`, checks 1–2: reducer registered, evidence resolves) is the
only place "minted by a deterministic reducer" is enforced, and it is a *separate* check. A `pattern`
fact carrying `epistemic_status="derived"` minted by any producer (an LLM asked to "derive a
pattern", a hand-written record) would pass `is_canonical()` and enter a snapshot as canonical. The
addendum's `"pattern": (DERIVED, "[C]")` sits at the exact authority band where this is most
tempting: it is *canonical by construction* while being *the compression of a judgment*.

**Resolution — design edit §3.4 rule 5 + deviation D3:** the `pattern` predicate's `produced_by` is
exactly `("pattern/v1",)`, and `verify_chain()` is mandatory for any `pattern` fact entering a
snapshot. Hard rule 3 is enforced by `verify_chain`, not `is_canonical()` alone. (This *deviates*
from A.3's "`is_canonical()` unchanged" — it is unchanged, but declared insufficient for this new
class.)

### F2 — a profile *can* widen a controller's view past its contract · **material** (vector 2)

**Attack:** find a concrete path. `compose_requirements` (§2.3) composes **only**
`context_requirements`. The other three `ChallengeProfile` fields — `verification_policy`,
`deliberation`, `session_policy` — are selected by the profile and **not** routed through the
contract's `requires_facts`/`excludes` at all. Concrete path: a challenge profile declaring
`verification_policy=("ruff",)` where the contract's verification invariant depends on `pytest`
would select a weaker verification regime than the contract, because nothing composes
`verification_policy` against the contract's verification facts. The addendum's central claim
"a profile cannot widen a controller's view" (`context_abstraction_design.md:1494-1496`) is
therefore **false for three of the profile's four inputs** as originally specified.

**Resolution — design edit §2.3 + deviation D4:** `verification_policy` may only *add* tools to the
contract's required verification, never drop one (monotone tightening, `context_abstraction_design.md:1352-1356`);
`deliberation` may reorder but never omit a contract-relied-on stage; `session_policy` is fully
shadow in v1. The contract is the sole **safety** gate; the profile contributes *strategy* only.

### F3 — ADVISORY narrative leaks into the canonical checkpoint payload · **material** (vector 3)

**Attack:** do ADVISORY narrative fields leak into canonical payload? **Yes.** The design (pre-edit)
placed `open_hypotheses`/`failed_approaches`/`next_action` "on the checkpoint record". `CanonicalFact`
has a SINGLE `epistemic_status` (`context_abstraction_design.md:232`), and the payload-in-`text`
decision makes `content_hash` (hence `fact_id`) a function of the whole payload
(`context_abstraction_design.md:333-361`). Two defects: (a) an LLM-produced `next_action` re-keys the
CANONICAL fact's identity on every narrative edit (supersession noise driven by non-canonical
content); (b) `is_canonical()`/C5 operate at **fact** granularity, so a controller citing the
checkpoint fact receives the ADVISORY narrative as citable canonical content — hard rule 3 violated
at field granularity.

*(Sub-note, vector 3's other half — PhaseResult duplication: the checkpoint's DERIVED fields
(`completed`/`current_revision`/`acceptance_state`) re-derive values already on the execution plane
(`_completed_phases` `workflow_runner.py:235-254`, `_git_head` `:227-232`, `test_executed_success`
`:113`). This is **not** a hard-rule-4 violation — the checkpoint is a *different* predicate at a
different subject/scope — but it is a redundancy the reducer must make auditable: `checkpoint/v1`'s
`consumes` must name these artifacts so the checkpoint is a *projection*, never a competing source.)*

**Resolution — design edit §4.1 + deviation D5:** the `session_checkpoint` fact carries **only** the
DERIVED fields; the three narrative fields become separate ADVISORY `source_type="checkpoint_narrative"`
records that `is_canonical()` excludes and C5 refuses. "Ride along as annotations" is honoured at the
*handoff* level (fact + narrative bundle), not the *fact* level.

### F4 — `continue` (session) is conflated with the routing null-action `continue` · **material** (vector 4)

**Attack:** are fork/compress/escalate applied or proposed? They are proposals — but the design's
pre-edit §4.3 labelled `continue` **Automatable** "because it is the null action". It is not: the
session-continuation `continue` (resume a session, carrying the stale-context risk priced at
`context_abstraction_design.md:1587`) is a *positive* `[H]` decision, whereas the `continue` in
`AUTOMATABLE_ACTIONS = {continue, route}` was designed as the routing null action ("the controller
ran and chose nothing", `context_abstraction_design.md:1086`). Admitting the session `continue` under
that name would let an automated `session_routing` controller **apply** an unmeasured `[H]` policy via
C9 — a measure-before-policy violation.

**Resolution — design edit §4.3 (no deviation; aligns with A.4's "never applied"):** `session_routing`
runs **fully shadow in v1** — all four actions recorded, none applied — and the runner's existing
fork-chain (`workflow_runner.py:591-597`) is the applied incumbent. `AUTOMATABLE_ACTIONS` is
unchanged; the two `continue`s are declared distinct.

### F5 — the 4-arm experiment cannot do its job as specified · **material** (vector 5)

**Attack:** is the evidence sufficient? Three defects, each re-verified against the spec in §4.4:
(a) **n=1 per arm** — `max_attempts: 1` with a single `model` level and no repetition factor gives one
observation per `session_policy` level, so the `uncertainty` term the promotion gate needs is
un-estimable; (b) **`escalate_with_checkpoint` is undefined** — escalate requires a model change, but
the only `model` level is `deepseek/deepseek-v4-pro`, so there is nothing to escalate *to*, and the
model×session_policy interaction is unmeasured; (c) **`session_policy_outcome.produces` depends on
unrequired inputs** — `session_cost_usd`/`session_cache_reuse` need `cost_inference`/`cache_hit`,
which are neither in the rule's `requires` nor written today (`experiment_spec.py:184,172` —
declared, zero writers), so the reducer could not compute them.

**Resolution — design edit §4.4 (no deviation; specification within A.4's "4 arms"):** add a second
`model` level (escalate target + interaction term), add a `repetition` factor (`r1,r2,r3`), set
`max_attempts: 3`, and restrict v1 `produces` to the WRITTEN-signal-derivable outcomes
(`session_verified_success`, `session_context_growth`); cost/cache/latency/rework outcomes are
deferred to a phase gated on instrumentation.

### F6 — "profiles are L4's producer" is reinterpreted away without a deviation note · **minor** (vector 6)

**Attack:** conflict with frozen §11 scope boundary? Addendum A.1 claims "profiles are L4's producer
— declared facts" (`context_abstraction_design.md:1488-1490`), but frozen §11.5 refuses to declare L4
workload facts (`context_abstraction_design.md:1415`), and this design's §7.7 states v1 profiles "do
not declare workload predicates". The tension was real but **undocumented** — a reader cannot tell
whether the addendum's "L4 producer" claim was dropped, deferred, or redefined. (No §8.6 observe-only
conflict: §4.3 leaves `AUTOMATABLE_ACTIONS` untouched and adds no call site to `supervise.py`/
`supervisor.py`; shadow-mode recording through the un-armed actuation envelope is within §8.6's
"a control rule may propose any action in the contract".)

**Resolution — deviation D6 (accepted-risk):** v1 profiles declare L5-policy-adjacent facts + their
own predicates; the L4-producer role is **deferred** until budget/deadline ownership is declared —
exactly the frozen §11.5 posture. Documented as D6 rather than silently redefined.

---

### Log — one line per attack vector

| Vector | Finding | Evidence (file:line) | Status |
|---|---|---|---|
| 1. pattern canonicity / hard rule 3 | F1 material | `is_canonical` lacks a reducer check: `context_abstraction_design.md:403-417` vs `verify_chain` `:607-637` | **resolved** — §3.4 r.5 + D3 |
| 2. profile widens past contract | F2 material | `verification_policy`/`deliberation`/`session_policy` not in `compose_requirements` (design §2.3, pre-edit) | **resolved** — §2.3 + D4 |
| 3. checkpoint dups PhaseResult + ADVISORY leak | F3 material | single `epistemic_status` `:232`; payload-in-`text` `:333-361`; C5 fact-granularity `:1183` | **resolved** — §4.1 + D5 |
| 4. session_routing vs `AUTOMATABLE_ACTIONS` | F4 material | routing null-action `continue` `:1086` vs session trade `:1587` | **resolved** — §4.3 (aligns with A.4) |
| 5. 4-arm evidence sufficiency | F5 material | `max_attempts: 1`, single model (design §4.4 pre-edit); `cost_inference`/`cache_hit` declared-not-written `experiment_spec.py:184,172` | **resolved** — §4.4 |
| 6. frozen §11 / §8.6 conflict | F6 minor | A.1 "L4 producer" `:1488-1490` vs §11.5 `:1415` | **resolved** — D6 (accepted-risk) |

**PASS** — six attack vectors worked, six findings (five material, one minor), all re-verified
against the tree, all resolved.

---

## Appendix — citation index

| Concern | Primary citations |
|---|---|
| Addendum A (field lists, invariants, arms) | `context_abstraction_design.md:1482-1604` |
| Frozen anchors (EPISTEMIC_MAP, is_canonical, FactRequirement, snapshot_id, AUTOMATABLE_ACTIONS, §3.3 payload-in-text, §10.2 tightening) | `context_abstraction_design.md:385-417,925-947,959-985,1065,1183,1196,1352-1356` |
| Reserved CAP homes | `control/__init__.py:7-9`; `control/facts.py:1-8`; `control/context_compiler.py:1-8`; `core/contracts.py:1-8`; `control/reducers/__init__.py:1-9`; `control/decisions.py:1-8` |
| Authority + identity + `SOURCE_TYPES` | `knowledge.py:61-85,100-119,125-150,192-211`; `knowledge_ingestion.py:93` |
| Spec producer (profile persistence template) | `spec_ingestion.py:76,80,229,235-303` |
| Routing contract + `route_step` + `RouteState` | `runtime/routing.py:284-292`; `step_routing.py:188-233` |
| Lab contract v6 + corpus | `lab_contract.py:114,352-362,365-384,620-793`; `canonical_corpus.py:81` |
| Coverage invariant | `measurement_coverage.py:20-21,55-83` |
| Phase/run ledger + fork + git completion | `workflow_runner.py:81-113,160,227-254,290-328,591-597,605-612,622` |
| Ledger fields (declared vs written) | `experiment_spec.py:135-194` (esp. `:159-193`) |
| Actuation envelope + gates | `actuation_ingestion.py:70`; `knowledge.py:149`; `knowledge_stream.py:178-192` |
| Session/task vocabulary | `core/session_types.py:40-42` |

---

## Log

| Check | Result |
|---|---|
| Design-only boundary: only the new doc; no `src/`/`scripts/`/`tests/`/`admin/` modified | **PASS** — `git status --porcelain` shows only this file |
| Every NEW mechanism marked NEW; every REUSE names `file:line` | **PASS** — §2–§4 |
| Every OQ from the review answered with a schema | **PASS** — §8 traceability maps OQ1–OQ7 |
| Deviation table present and honest | **PASS** — §5 (D1, D2) |
| Reserved-homes declared per increment | **PASS** — §6 |
| Scope boundary explicit | **PASS** — §7 |
