"""CAP I0 — the CanonicalFact schema + predicate registry (zero call sites by design).

This module is the *schema* half of the Context Abstraction Plane
(``docs/designs/current/context_abstraction_design.md``). It declares what a **fact** is — a
typed, scoped, current statement about the system (``subject · predicate · value``) — and the
predicate vocabulary every reducer must emit into. It is deliberately **not** the machinery that
*produces* facts: that is the reducers package (I1–I3), which feeds ``build_record`` and the
durable stream (design §4.3). I0 ships only the schema so it is exercised in tests before
anything in the running system depends on it.

READ THIS BEFORE ADDING A CALL SITE — THAT IS THE WHOLE POINT OF THIS MODULE EXISTING:
``CanonicalFact`` / ``FACT_PREDICATES`` / ``verify_chain`` are built and unit-tested so their
schema is exercised *before* anything produces a fact. The **one legitimate first call site** is
the reducers package (``control/reducers/``, I1–I3), which instantiates facts and registers their
``ReducerSpec`` in the ``REDUCERS`` registry. Nothing else may import this module until a reducer
exists whose output a rule may consume — the same "declared source before consumer" ordering the
``requires``/``produces`` gate enforces everywhere else (``AGENTS.md``'s load-bearing rule).

Schema is per design §3 (identity + epistemics), §3.5 (predicate registry), §4 (ReducerSpec —
the schema ``verify_chain`` consumes), and §6.3 (``FactRef`` / ``Unknown``, consumed by the I4
Context Compiler). The epistemic mapping (§3.4) is the single discriminator from which
``authority`` and ``evidence_class`` derive, so the three can never disagree.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from agentic_dynamics.knowledge.knowledge import Authority, compute_entity_id

# ── Closed vocabularies (the schema's fixed axes) ───────────────


#: The ``value_type`` vocabulary (§3.1): how to interpret a fact's canonical STRING ``value``.
#: ``enum-list`` is the composite type the §3.5 table uses for ``allowed_models`` (a list of
#: model ids rendered as a comma-joined string), which §3.1's scalar list does not spell out
#: but the table requires.
VALUE_TYPES = frozenset(
    {
        "bool",
        "int",
        "float",
        "usd",
        "seconds",
        "tokens",
        "timestamp",
        "enum",
        "enum-list",
        "str",
    }
)

#: The ``abstraction_level`` vocabulary (§3.1): L1..L5 as a NAME, not a number. Kept as a
#: separate axis from ``authority`` so the four practice cases (low/MEASURED, high/DERIVED,
#: high/POLICY, high/ADVISORY) stay expressible.
ABSTRACTION_LEVELS = frozenset({"fact", "job", "workflow", "workload", "policy"})

#: The ``subject_type`` vocabulary (§3.1) — what a fact is *about*.
SUBJECT_TYPES = frozenset(
    {"job", "attempt", "workflow", "workload", "spec", "model", "resource", "policy"}
)

#: The ``scope_type`` vocabulary (§3.1, §10.1) — where a fact is true. ``resource`` is the
#: orthogonal scope (model, pool, queue); the rest are the ancestry spine.
SCOPE_TYPES = frozenset(
    {"organization", "program", "workload", "workflow", "job", "attempt", "resource"}
)


# ── Epistemics (§3.4) — the single discriminator ────────────────


#: Type alias for the epistemic mapping: ``epistemic_status -> (authority, evidence_class)``.
EpistemicMap = dict[str, tuple[Authority, str]]


#: The ONE mapping (§3.4). A fact constructor takes ``epistemic_status`` and *derives* the other
#: two axes; passing ``authority`` explicitly is not part of the API, so the three can never
#: disagree (review §4.5 flagged a free-standing third axis as drift-inviting).
EPISTEMIC_MAP: EpistemicMap = {
    # An event was recorded by the system itself (a commit exists, a token count was emitted).
    "observed": (Authority.MEASURED, "[M]"),
    # An INDEPENDENT verifier confirmed it — today that means test_runner.run_suite, the sole
    # source of test_executed_success. Same authority as `observed`, different meaning.
    "verified": (Authority.MEASURED, "[M]"),
    # Computed by a deterministic versioned reducer from other facts/evidence.
    "derived": (Authority.DERIVED, "[C]"),
    # Asserted by policy or configuration — a human/operator declaration, not a measurement.
    "declared": (Authority.POLICY, "[P]"),
    # A judgment (LLM, heuristic, supervisor verdict). NEVER canonical — see is_canonical().
    "advisory": (Authority.ADVISORY, "[H]"),
}

#: The epistemic-status vocabulary — the keys of :data:`EPISTEMIC_MAP`.
EPISTEMIC_STATUSES = frozenset(EPISTEMIC_MAP)


# ── CanonicalFact (§3.1) ────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class CanonicalFact:
    """One typed, scope-bound, current statement about the system.

    A fact is deliberately NOT a document. ``knowledge.KnowledgeRecord`` answers "what did this
    artifact say at this revision"; a CanonicalFact answers "what is true about this subject,
    in this scope, right now". The two are related by construction (every fact is persisted AS
    a ``KnowledgeRecord`` with ``source_type="fact"`` — design §3.3) but the semantics differ
    and the plane must never conflate them.

    Frozen because a fact is immutable: a new value is a NEW fact that supersedes the old one,
    exactly as a modified symbol is a new ``knowledge_id`` under a stable ``entity_id``.
    ``kw_only=True`` keeps the §3.1 field order (``unit`` carries a default mid-list) without a
    positional-construction foot-gun on a 27-field schema.
    """

    # ── Identity (two ids, mirroring knowledge.py's entity_id / knowledge_id pair) ──
    fact_entity_id: str
    """The stable LOGICAL SLOT: 'the value of <predicate> for <subject> in <scope>'.

    Computed with the EXISTING helper (knowledge.compute_entity_id) — see
    :func:`compute_fact_entity_id` — so the plane adds no second identity algorithm. Keyed by
    (scope, subject, predicate) and NOT by time, so "exactly one canonical representation per
    fact" is a lookup, resolved by the registry compaction that already exists.
    """

    fact_id: str
    """The immutable VERSION of the slot — one value, derived at one moment by one reducer
    version. Computed with the existing helper (knowledge.compute_knowledge_id) folding
    ``reducer_version`` in as the extractor version, so bumping a reducer RE-KEYS every fact it
    produces and supersession is free (design §3.1).
    """

    # ── The statement itself ──
    subject_type: str  # job | attempt | workflow | workload | spec | model | resource | policy
    subject_id: str  # e.g. "wf_context_abstraction_plane_anthropic_claude_opus_5"
    predicate: str  # MUST be a key of FACT_PREDICATES (§3.5) — a closed vocabulary
    value: str  # canonical STRING encoding; typed by `value_type` below
    value_type: str  # bool | int | float | usd | seconds | tokens | timestamp | enum | str
    unit: str = ""  # "" | "usd" | "s" | "tokens" — redundant with value_type, kept for display

    # ── Placement in the hierarchy ──
    scope_type: str  # organization | program | workload | workflow | job | attempt | resource
    scope_id: str
    scope_path: str  # "org:agentic-dynamics/workload:rag_bare_vs_augmented/job:self-wt_03"
    abstraction_level: str  # fact | job | workflow | workload | policy

    # ── Epistemics (§3.4 — a SINGLE discriminator, from which the two axes derive) ──
    epistemic_status: str  # observed | verified | derived | declared | advisory
    authority: Authority  # DERIVED from epistemic_status — never chosen freely
    evidence_class: str  # DERIVED from epistemic_status — [M] [C] [H] [P] [X]

    # ── Validity window ──
    observed_at: str  # when the underlying evidence was observed (NOT when reduced)
    valid_from: str  # when this value became true (usually == observed_at)
    valid_to: str | None  # None = open; set by the registry view when superseded
    expires_at: str | None
    """Explicit obsolescence horizon, from FACT_PREDICATES[predicate].default_ttl_seconds.

    Volatility is a property OF THE PREDICATE, not of the reader, so staleness is computable
    without knowing who is asking (design §3.1).
    """

    # ── Derivation chain (what makes a derived fact auditable) ──
    reducer: str  # "workflow_health"
    reducer_version: str  # "workflow_health/v1" — folded into fact_id (see above)
    evidence_ids: tuple[str, ...]
    """The FULL input set: ``knowledge_id``s of evidence records AND/OR ``fact_id``s of
    lower-level facts. Ordered, deduplicated, and hashed into the payload (design §3.1)."""
    inputs_digest: str  # sha256 over (sorted evidence_ids | reducer_version)
    supersedes: str | None  # predecessor fact_id for the SAME fact_entity_id
    source_revision: str  # commit sha when repository-bound, else a producer marker
    repository_id: str  # the existing scope string (§10.3)

    # ── Derived, index-only (never stored in the artifact; recomputed on read) ──
    lifecycle_state: str = "current"
    """current | superseded | tombstoned | conflicted | unknown (design §4.5).

    Index-only for the same reason generate_manifest.py derives its own lifecycle: a stored
    lifecycle is a lie the moment a successor appears.
    """


# ── PredicateSpec + the FACT_PREDICATES registry (§3.5) ─────────


@dataclass(frozen=True)
class PredicateSpec:
    """The declaration of ONE fact predicate. This table is the plane's schema of the world.

    It exists so the generalized load-bearing rule has something to check against: "no control
    action may consume a value that is not produced by a declared source or reducer" is only
    enforceable if there is a registry of declarations. ``FACT_PREDICATES`` is that registry —
    with the crucial difference from ``LEDGER_FIELDS`` that a predicate names its PRODUCER, so
    the review's "declared but written by nothing" failure (§3d(ii)) cannot recur.
    """

    name: str
    value_type: str
    unit: str
    subject_type: str
    scope_type: str
    abstraction_level: str
    produced_by: tuple[str, ...]
    """Reducer version(s) that may emit this predicate. NON-EMPTY IS THE INVARIANT: a predicate
    with no producer is unwritable AND unrequirable, which is what makes ``budget`` and
    ``deadline_slack`` (declared in LEDGER_FIELDS with zero writers) impossible to declare here
    until something actually produces them."""
    default_ttl_seconds: int | None
    volatile: bool
    """True when the value changes on the timescale of a decision (queue depth, running status).
    A control rule requiring a volatile predicate MUST set max_age_seconds (refusal R6)."""
    inheritable: bool = False
    """True when descendants of the declaring scope may read it (downward flow, §10.2)."""
    aggregates_from: str = ""
    """When set, the child predicate this one rolls up from — the only legal upward path."""


#: The predicate registry — the design's §3.5 seed table (16 rows). Every row names its
#: ``produced_by`` reducer; a predicate with no producer is unrepresentable here by construction.
FACT_PREDICATES: dict[str, PredicateSpec] = {
    # spec-status facts (I1, workload scope, inheritable downward).
    "spec_status": PredicateSpec(
        name="spec_status",
        value_type="enum",
        unit="",
        subject_type="spec",
        scope_type="workload",
        abstraction_level="fact",
        produced_by=("spec_status/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "spec_superseded_by": PredicateSpec(
        name="spec_superseded_by",
        value_type="str",
        unit="",
        subject_type="spec",
        scope_type="workload",
        abstraction_level="fact",
        produced_by=("spec_status/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "spec_supersedes": PredicateSpec(
        name="spec_supersedes",
        value_type="enum-list",
        unit="",
        subject_type="spec",
        scope_type="workload",
        abstraction_level="fact",
        produced_by=("spec_status/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "spec_last_run_at": PredicateSpec(
        name="spec_last_run_at",
        value_type="timestamp",
        unit="",
        subject_type="spec",
        scope_type="workload",
        abstraction_level="fact",
        produced_by=("spec_status/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "spec_latest_ok": PredicateSpec(
        name="spec_latest_ok",
        value_type="bool",
        unit="",
        subject_type="spec",
        scope_type="workload",
        abstraction_level="fact",
        produced_by=("spec_status/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "spec_latest_model": PredicateSpec(
        name="spec_latest_model",
        value_type="str",
        unit="",
        subject_type="spec",
        scope_type="workload",
        abstraction_level="fact",
        produced_by=("spec_status/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "spec_latest_cost_usd": PredicateSpec(
        name="spec_latest_cost_usd",
        value_type="usd",
        unit="usd",
        subject_type="spec",
        scope_type="workload",
        abstraction_level="fact",
        produced_by=("spec_status/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "spec_n_runs": PredicateSpec(
        name="spec_n_runs",
        value_type="int",
        unit="",
        subject_type="spec",
        scope_type="workload",
        abstraction_level="fact",
        produced_by=("spec_status/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    # job facts (I2).
    "current_commit": PredicateSpec(
        name="current_commit",
        value_type="str",
        unit="",
        subject_type="job",
        scope_type="job",
        abstraction_level="job",
        produced_by=("job_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    # attempt facts (I2).
    "phase_status": PredicateSpec(
        name="phase_status",
        value_type="enum",
        unit="",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "phase_test_verified": PredicateSpec(
        name="phase_test_verified",
        value_type="bool",
        unit="",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "attempt_cost_usd": PredicateSpec(
        name="attempt_cost_usd",
        value_type="usd",
        unit="usd",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "attempt_tokens_out": PredicateSpec(
        name="attempt_tokens_out",
        value_type="tokens",
        unit="tokens",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "attempt_tokens_in": PredicateSpec(
        name="attempt_tokens_in",
        value_type="tokens",
        unit="tokens",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "attempt_model": PredicateSpec(
        name="attempt_model",
        value_type="str",
        unit="",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "phase_commit": PredicateSpec(
        name="phase_commit",
        value_type="str",
        unit="",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "attempt_cache_hit_rate": PredicateSpec(
        name="attempt_cache_hit_rate",
        value_type="float",
        unit="",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "attempt_confidence": PredicateSpec(
        name="attempt_confidence",
        value_type="float",
        unit="",
        subject_type="attempt",
        scope_type="attempt",
        abstraction_level="fact",
        produced_by=("attempt_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    # job-level aggregate (I2).
    "job_accumulated_cost_usd": PredicateSpec(
        name="job_accumulated_cost_usd",
        value_type="usd",
        unit="usd",
        subject_type="job",
        scope_type="job",
        abstraction_level="job",
        produced_by=("job_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "job_status": PredicateSpec(
        name="job_status",
        value_type="enum",
        unit="",
        subject_type="job",
        scope_type="job",
        abstraction_level="job",
        produced_by=("job_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    "job_n_phases": PredicateSpec(
        name="job_n_phases",
        value_type="int",
        unit="",
        subject_type="job",
        scope_type="job",
        abstraction_level="job",
        produced_by=("job_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
    ),
    # workflow facts (I3).
    "workflow_phases_completed": PredicateSpec(
        name="workflow_phases_completed",
        value_type="int",
        unit="",
        subject_type="workflow",
        scope_type="workflow",
        abstraction_level="workflow",
        produced_by=("workflow_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
        # Rolls up from the per-phase status facts (aggregation through a declared parent-scope
        # reducer only — §10.2.3).
        aggregates_from="phase_status",
    ),
    "workflow_phases_remaining": PredicateSpec(
        name="workflow_phases_remaining",
        value_type="int",
        unit="",
        subject_type="workflow",
        scope_type="workflow",
        abstraction_level="workflow",
        produced_by=("workflow_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
        aggregates_from="phase_status",
    ),
    "workflow_status": PredicateSpec(
        name="workflow_status",
        value_type="enum",
        unit="",
        subject_type="workflow",
        scope_type="workflow",
        abstraction_level="workflow",
        produced_by=("workflow_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
        aggregates_from="job_status",
    ),
    "workflow_health": PredicateSpec(
        name="workflow_health",
        value_type="enum",
        unit="",
        subject_type="workflow",
        scope_type="workflow",
        abstraction_level="workflow",
        produced_by=("workflow_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
        # healthy | degraded | at_risk — derived from the job's status + spend-against-ceiling.
        aggregates_from="job_status",
    ),
    "projected_budget_overrun": PredicateSpec(
        name="projected_budget_overrun",
        value_type="usd",
        unit="usd",
        subject_type="workflow",
        scope_type="workflow",
        abstraction_level="workflow",
        produced_by=("workflow_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
        # max(0, accumulated spend − max_spend_usd) — emitted only when a ceiling exists (§4.2's
        # "spend-against-declared-ceiling" substitution for the unproducible deadline_slack).
        aggregates_from="job_accumulated_cost_usd",
    ),
    # policy facts (I3, L5 — declared, inheritable downward).
    "allowed_models": PredicateSpec(
        name="allowed_models",
        value_type="enum-list",
        unit="",
        subject_type="policy",
        scope_type="workload",
        abstraction_level="policy",
        produced_by=("policy_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "max_spend_usd": PredicateSpec(
        name="max_spend_usd",
        value_type="usd",
        unit="usd",
        subject_type="policy",
        scope_type="workload",
        abstraction_level="policy",
        produced_by=("policy_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
    "max_attempts": PredicateSpec(
        name="max_attempts",
        value_type="int",
        unit="",
        subject_type="policy",
        scope_type="workload",
        abstraction_level="policy",
        produced_by=("policy_facts/v1",),
        default_ttl_seconds=None,
        volatile=False,
        inheritable=True,
    ),
}


# ── ReducerSpec (§4.1) — the schema verify_chain() consumes ─────


@dataclass(frozen=True)
class ReducerSpec:
    """The declaration of one deterministic, versioned reducer.

    Discipline copied verbatim from two places that already work: ``step_routing``'s pure-function
    contract (no I/O, no RNG) and ``record_factory._now_iso``'s injected clock. A reducer's output
    is persisted and cited by decisions, so a reducer that reads the wall clock directly is not
    reproducible and cannot be replayed against historical evidence.
    """

    name: str
    version: str  # "workflow_facts/v1" — the string folded into every fact_id
    level: str  # fact | job | workflow | workload | policy
    scope_type: str  # the scope of the facts it emits
    consumes: tuple[str, ...]
    """Input contract: evidence source_types (e.g. "ledger_attempt") and/or predicate names of
    lower-level facts. Declared so the compiler can verify a reduction LADDER exists before any
    rule requires the top of it."""
    produces: tuple[str, ...]  # predicate names; must all exist in FACT_PREDICATES
    determinism: str = "pure"  # "pure" | "pure_with_injected_clock"


# ── Reducer input (the §4.1 "everything a reducer may see" shape) ─


@dataclass(frozen=True)
class EvidenceItem:
    """One resolved L0 evidence input a reducer may consume (design §4.1).

    A reducer never does I/O — the CALLER resolves inputs (reads the index, loads the records)
    and hands them over. ``source_type`` names the evidence family; ``evidence_id`` is a stable
    locator (a ``knowledge_id`` when the evidence IS a knowledge record, else a deterministic
    key); ``payload`` is the resolved object the reducer reads (e.g. a ``SpecStatusEntry``).
    """

    source_type: str
    evidence_id: str
    payload: Any = None


@dataclass(frozen=True)
class ReducerInput:
    """Everything a reducer may see. Deliberately narrow: no Redis handle, no filesystem, no
    network. If a reducer needs more inputs, that is a ``consumes`` change and therefore a
    VERSION change — which is the point (design §4.1)."""

    scope_path: str
    scope_type: str
    scope_id: str
    repository_id: str
    evidence: tuple[EvidenceItem, ...]  # resolved L0 records/artifacts, ordered deterministically
    facts: tuple[CanonicalFact, ...]  # resolved lower-level facts (already filtered to current)
    now: str  # injected clock — a reducer that reads the wall clock is not reproducible
    source_revision: str


#: The signature every reducer implements (design §4.1). No I/O: the caller resolves inputs and
#: persists outputs, so the reducer itself is a pure function a test can call with fixtures.
Reducer = Callable[[ReducerInput], list[CanonicalFact]]


# ── Snapshot-facing value types (§6.3) ──────────────────────────


@dataclass(frozen=True)
class FactRef:
    """A fact as a controller sees it: the value plus everything needed to judge and cite it.

    Consumed by the I4 Context Compiler's ``ControlContext``; declared here (not in
    ``context_compiler.py``) because it is part of the fact schema's public surface.
    """

    fact_id: str
    predicate: str
    subject_id: str
    scope_path: str
    value: str
    value_type: str
    authority: str  # enum NAME, not the enum — the snapshot is a serialized boundary
    epistemic_status: str
    observed_at: str
    age_seconds: int  # computed at compile time against `now`; freshness policy lives in ONE place
    reducer_version: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class Unknown:
    """A required fact that could not be satisfied, with the reason and the contract's handling.

    ``unknown`` is NOT a state OF a fact (that would be §4.5's ``fact_state``); it is the
    compiler's answer when NO fact fills a required slot — "we never had a value" vs "we have a
    stale value" call for different ``on_missing`` handling (design §6.3).
    """

    predicate: str
    scope: str
    reason: str  # "no_fact" | "broken_chain" | "below_min_authority" | "out_of_scope"
    handling: str  # the contract's on_missing for this entry


@dataclass(frozen=True)
class Conflict:
    """A required fact resolved to TWO OR MORE current, disagreeing values (§4.5's conflict
    resolution ladder exhausted with neither side winning) — every candidate is kept so a reader
    can see exactly what disagreed, never just the winner's silence about the loser."""

    predicate: str
    scope: str
    candidates: tuple[FactRef, ...]
    handling: str  # the contract's on_conflict for this entry


@dataclass(frozen=True)
class StaleFact:
    """A required fact that resolved, but past its currency bound (§4.5's ``stale`` state, or a
    requirement's own ``max_age_seconds`` tightening) — the value plus its age, so the compiler
    never silently drops a value the contract nonetheless refuses to trust as-is."""

    fact: FactRef
    scope: str
    reason: str  # "expired" | "cascade" | "max_age_exceeded"
    handling: str  # the contract's on_missing for this entry (stale is treated as unsatisfied)


# ── Identity helpers (§3.1, §3.3) — reuse, never re-derive ──────


def fact_source_uri(scope_type: str, scope_id: str, predicate: str) -> str:
    """The fact's ``source_uri`` (§3.3): ``fact://<scope_type>/<scope_id>/<predicate>``."""
    return f"fact://{scope_type}/{scope_id}/{predicate}"


def fact_logical_locator(subject_type: str, subject_id: str, predicate: str) -> str:
    """The fact's ``logical_locator`` (§3.3): ``<subject_type>:<subject_id>#<predicate>``."""
    return f"{subject_type}:{subject_id}#{predicate}"


def compute_fact_entity_id(
    *,
    repository_id: str,
    scope_type: str,
    scope_id: str,
    predicate: str,
    subject_type: str,
    subject_id: str,
) -> str:
    """The fact's stable LOGICAL SLOT (§3.1) — reuse of ``knowledge.compute_entity_id``.

    Keyed by (scope, subject, predicate) and NOT by time, so "exactly one canonical
    representation per fact" is mechanically a lookup, resolved by the existing registry
    compaction. This is the opposite identity strategy from ``observation`` records, which
    deliberately fold the timestamp into identity (every verdict is an independent fact).
    """
    return compute_entity_id(
        repository_id,
        fact_source_uri(scope_type, scope_id, predicate),
        fact_logical_locator(subject_type, subject_id, predicate),
    )


# ── Epistemic gate (§3.4) ───────────────────────────────────────


def is_canonical(fact: CanonicalFact) -> bool:
    """True when a fact may be consumed by a control path.

    The executable form of hard rule 3 ("LLM judgment is ADVISORY, always"). ADVISORY facts are
    still STORED (so supervisor verdicts stay auditable) but are structurally excluded from
    control: they land in ``ControlContext.advisory`` and check C5 refuses any decision whose
    ``facts_used`` cites one.
    """
    return (
        fact.epistemic_status != "advisory"
        and fact.authority >= Authority.DERIVED  # IntEnum ordering, knowledge.py:81-85
        and fact.lifecycle_state == "current"
    )


# ── Derivation-chain validation (§4.4) ──────────────────────────


def recompute_inputs_digest(fact: CanonicalFact) -> str:
    """Reproduce a fact's ``inputs_digest`` from the derivation inputs it carries (§3.1).

    The design's formula is ``sha256(sorted evidence_ids | reducer_version | input values)``.
    I0 hashes the input *identities* and the reducer version — the portion recoverable from the
    fact alone — which is exactly what makes the digest a tamper-evident checksum over the
    derivation chain: a hand-edited ``evidence_ids`` or ``reducer_version`` breaks it. The
    "input values" term requires resolving each input, which the Context Compiler supplies via
    ``verify_chain``'s ``resolve`` callable in I4; it is not part of this self-contained check.
    """
    parts = sorted(fact.evidence_ids)
    parts.append(fact.reducer_version)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def verify_chain(
    fact: CanonicalFact,
    registry: Mapping[str, ReducerSpec],
    resolve: Callable[[str], object | None] | None = None,
) -> list[str]:
    """Return refusal reasons for ``fact``'s derivation chain; empty list = valid (§4.4).

    ``registry`` maps ``reducer_version`` -> ``ReducerSpec`` (the ``REDUCERS`` registry the
    reducers package exposes, I1–I3). ``resolve`` maps an ``evidence_id`` to its registry row
    (or ``None`` when it does not resolve); when omitted the evidence-resolution check is
    skipped — I0 has no store to resolve against, so it exercises the remaining checks.

    Called by (a) the Context Compiler before a fact may enter a snapshot, and (b) the
    ControlValidator (check C6) before a decision may cite it — checked twice on purpose, the
    same "closed by default, checked in more than one place" posture as the actuation lineage
    gate. Returns ALL reasons (not the first), so a broken fact names everything wrong with it.
    """
    errors: list[str] = []
    spec = registry.get(fact.reducer_version)
    # 1. The reducer must be registered. An unregistered reducer_version means the fact was
    #    produced by code that no longer exists — its semantics are unknowable.
    if spec is None:
        errors.append(f"fact {fact.fact_id}: reducer {fact.reducer_version!r} is not registered")
    # 2. Every input must resolve. A dangling evidence_id means the chain is broken, not weak.
    if resolve is not None:
        for eid in fact.evidence_ids:
            if resolve(eid) is None:
                errors.append(
                    f"fact {fact.fact_id}: evidence {eid} does not resolve in the registry"
                )
    # 3. The digest must reproduce — catches a hand-edited artifact or a partial write.
    if recompute_inputs_digest(fact) != fact.inputs_digest:
        errors.append(f"fact {fact.fact_id}: inputs_digest mismatch (artifact altered?)")
    # 4. The reducer must be declared to produce this predicate, at this level.
    if spec is not None:
        if fact.predicate not in spec.produces:
            errors.append(
                f"fact {fact.fact_id}: {fact.reducer_version} does not declare {fact.predicate!r}"
            )
        if fact.abstraction_level != spec.level:
            errors.append(
                f"fact {fact.fact_id}: level {fact.abstraction_level!r} "
                f"!= reducer level {spec.level!r}"
            )
    # 5. Epistemic consistency — authority/evidence_class must equal the §3.4 mapping.
    if EPISTEMIC_MAP.get(fact.epistemic_status) != (fact.authority, fact.evidence_class):
        errors.append(
            f"fact {fact.fact_id}: authority/evidence_class contradict epistemic_status "
            f"{fact.epistemic_status!r}"
        )
    return errors


# ── Staleness cascade (§4.5) — read-time derivation, no scheduler ─


def fact_state(
    fact: CanonicalFact,
    *,
    now: str,
    resolve: Callable[[str], Mapping[str, Any] | None],
    current_versions: Callable[[str], tuple[Mapping[str, Any], ...] | None] | None = None,
) -> str:
    """Return ``current | stale | superseded | tombstoned | conflicted`` for one fact (§4.5).

    Read-time derivation, exactly as ``generate_manifest._derive_lifecycle`` derives
    ``current | superseded | tombstoned`` from the successor pointer — and DELIBERATELY kept
    separate from it (F4): that function's vocabulary stays untouched, and the two NEW states
    (``conflicted``, and the cascade's ``stale``) are computed here, in the plane, not pushed
    into the shared lifecycle vocabulary.

    ``resolve(id)`` maps a ``fact_id`` (or ``evidence_id``) to its registry row — a Mapping with
    at least a ``lifecycle_state`` key (``current | superseded | tombstoned``) — or ``None`` when
    unresolvable. ``current_versions(entity_id)`` returns ALL current rows for a slot (for the
    ``conflicted`` check); ``None`` skips that check.

    Precedence is fixed and total — first match wins (§4.5's "an ambiguous state is worse than a
    wrong one"):

    1. ``tombstoned`` — this fact's own row was explicitly retracted.
    2. ``superseded`` — this fact's own row was replaced (successor pointer).
    3. ``conflicted`` — two or more CURRENT rows share ``fact_entity_id`` with different ids.
    4. ``stale`` — ``expires_at < now``, OR any ``evidence_id`` resolves to a non-current row
       (the staleness cascade: superseding an L1 fact makes the L3 fact that cites it stale on
       the next read, transitively by construction — §4.5). The third stale condition — "a NEWER
       registered reducer version produces this predicate" — is deferred: reducer deprecation has
       no registry representation yet.
    5. ``current`` — otherwise.
    """
    row = resolve(fact.fact_id) if fact.fact_id else None
    if row is not None and row.get("lifecycle_state") == "tombstoned":
        return "tombstoned"
    if fact.lifecycle_state == "tombstoned":
        return "tombstoned"
    if row is not None and row.get("lifecycle_state") == "superseded":
        return "superseded"
    if fact.lifecycle_state == "superseded":
        return "superseded"

    if current_versions is not None:
        rows = current_versions(fact.fact_entity_id) or ()
        current = [r for r in rows if r.get("lifecycle_state") in (None, "current")]
        ids = {r.get("knowledge_id") or r.get("fact_id") for r in current}
        if len(ids) > 1:
            return "conflicted"

    if fact.expires_at and fact.expires_at < now:
        return "stale"
    for eid in fact.evidence_ids:
        erow = resolve(eid)
        if erow is not None and erow.get("lifecycle_state") in ("superseded", "tombstoned"):
            return "stale"

    return "current"
