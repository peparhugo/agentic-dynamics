"""The context-layer vocabulary and the deterministic phase -> layer routing rule.

Design: ``docs/designs/proposed/agent_world_models.md`` §6 (the context layers) and §9
(first steps). Register **L60**, first bounded unit. This module is the single owner of
three contracts, so the routing rule, the source-type material, and the per-phase record
can never drift apart:

1. **The vocabulary** — the five layers ``L0`` (task) .. ``L4`` (self), an ordered tuple
   and the closed *layer-status* set (:data:`LAYER_STATUSES`). A status outside the set
   is a bug, not a new state. [P]
2. **The routing rule** — :func:`resolve_phase_layers` maps a phase's name/kind (plus
   explicit spec hints) to a :class:`LayerRoute`, and :func:`resolve_layer_route` turns that
   route into the ``retrieve()``-facing :class:`LayerRetrievalShape` (source-type prefilter,
   explicit shared scopes, pattern projection). Both are *deterministic*: identical inputs
   produce an equal result, because they consult no clock, no random source, and no store.
   The layers map onto the EXISTING one knowledge plane as source-type shaping of
   ``retrieve()`` — this module builds no parallel retrieval path and no new store. [C]
3. **The record** — :func:`build_context_route_record` is the SINGLE builder of the
   per-phase record schema (``context-route/v1``). Every served item gets an honest
   disposition; a layer that could not retrieve is a NAMED absence, never an empty
   success and never a fabricated zero (measured-or-absent). The augment seam and the
   runner both call this builder, so the ledger can never disagree with the route. [C]

**Honesty frame.** The mapping below is a heuristic ([H]) grounded in the design doc's
§6 table; the *prohibition* of L4 for cell phases is policy ([P]) — the AIO's private
self-knowledge records (beliefs, reflections, wave verdicts, org-root decisions) are
never resolved by a cell agent, even if a caller asks for them. The record keeps every
served item attributable to a layer and names every failure.

Non-goals (inherited from the world-models doc): no external memory service, no new
retrieval store, no LLM in the resolver. This module is pure vocabulary + arithmetic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentic_dynamics.knowledge.knowledge import SOURCE_TYPES

#: The versioned per-phase record schema. A consumer that does not recognise this string
#: must treat the record as opaque rather than guess at its shape.
CONTEXT_ROUTE_SCHEMA = "context-route/v1"

# ── Layer vocabulary ────────────────────────────────────────────

LAYER_TASK = "L0"  # goal + brief + phase — the base prompt, always present
LAYER_STRUCTURE = "L1"  # code graph, module map, mental-model surfaces ("what is this system")
LAYER_HISTORY = "L2"  # register rows, close/decision records, prior attempts ("what happened here")
LAYER_OUTCOMES = "L3"  # measured distributions: failure classes, routing, cost/latency
LAYER_SELF = "L4"  # the AIO self-knowledge layer (private; never resolved by a cell agent)

#: The closed layer vocabulary in presentation order. The order is load-bearing: it is the
#: deterministic sort key for resolved layers and the order the record emits them.
LAYERS: tuple[str, ...] = (
    LAYER_TASK,
    LAYER_STRUCTURE,
    LAYER_HISTORY,
    LAYER_OUTCOMES,
    LAYER_SELF,
)

#: layer id -> position, so any layer collection sorts deterministically (unknown ids last).
_LAYER_ORDER: dict[str, int] = {name: index for index, name in enumerate(LAYERS)}

# ── The closed layer-status set ─────────────────────────────────

LAYER_STATUS_SERVED = "served"  # evidence for this layer reached the phase
LAYER_STATUS_EMPTY = "empty"  # retrieval completed, no error, and no evidence matched
LAYER_STATUS_NAMED_ABSENT = "named_absent"  # a leg failed / no attempt: named, never a zero
LAYER_STATUS_UNKNOWN = "unknown"  # served item could not be attributed to a resolved layer
LAYER_STATUS_EXCLUDED = "excluded"  # prohibited content (L4) refused, or explicitly dropped

#: The closed status set. A record status that is not a member is a contract violation.
LAYER_STATUSES: tuple[str, ...] = (
    LAYER_STATUS_SERVED,
    LAYER_STATUS_EMPTY,
    LAYER_STATUS_NAMED_ABSENT,
    LAYER_STATUS_UNKNOWN,
    LAYER_STATUS_EXCLUDED,
)
LAYER_STATUS_SET = frozenset(LAYER_STATUSES)

# ── Phase roles (the input to the routing rule) ─────────────────

ROLE_PLANNING = "planning"
ROLE_IMPLEMENTATION = "implementation"
ROLE_VERIFICATION = "verification"
ROLE_REVIEW = "review"
ROLE_UNKNOWN = "unknown"

ROLE_VALUES: tuple[str, ...] = (
    ROLE_PLANNING,
    ROLE_IMPLEMENTATION,
    ROLE_VERIFICATION,
    ROLE_REVIEW,
    ROLE_UNKNOWN,
)

# ── Execution-scope -> routing-role translation (A11-R1) ────────

#: The declared execution scopes (``experiment_spec.SCOPE_VOCABULARY``) that carry a routing
#: role in this module's context-layer vocabulary. The two vocabularies are DIFFERENT closed
#: sets: ``implementation`` coincides, but the read-only scopes do not name a routing role.
#: This table is the ONE translation, owned here so the runner never has to know it and the two
#: vocabularies cannot drift silently. Every key is a member of ``SCOPE_VOCABULARY``; the one
#: scope deliberately absent is ``proposal_write`` — writing a proposal is an execution
#: envelope, not an evidence-routing role (it neither needs L1 structure nor implies a review),
#: so an unmapped scope leaves any explicit ``role``/``phase_role`` hint intact and falls
#: through to the name classifier exactly as before. [H]
EXECUTION_SCOPE_ROLES: dict[str, str] = {
    "implementation": ROLE_IMPLEMENTATION,
    "review_readonly": ROLE_REVIEW,
    "adversarial_readonly": ROLE_REVIEW,
    "research_readonly": ROLE_PLANNING,
}


def execution_scope_role(scope: str) -> str:
    """Translate a declared execution scope to a routing role (``""`` when unmapped).

    A phase's declared ``scope`` is a MEMBER of ``experiment_spec.SCOPE_VOCABULARY`` (an
    execution envelope: what the phase may mount, read, and write), while routing roles are
    this module's layer-selection vocabulary. The two are not interchangeable, so the scope
    string must be TRANSLATED rather than passed through: only a scope listed in
    :data:`EXECUTION_SCOPE_ROLES` carries routing semantics. An unknown, empty, or
    deliberately-unmapped scope (``proposal_write``) returns ``""`` so the caller RETAINS the
    phase's explicit ``role``/``phase_role`` hint instead of discarding it and silently
    name-classifying. Pure and deterministic (no clock, no store, no model).
    """
    needle = str(scope or "").strip().lower()
    return EXECUTION_SCOPE_ROLES.get(needle, "")


#: Substring markers (lower-cased) that classify a phase by its name/kind. Order of the
#: checks in :func:`classify_phase_role` — review, then verification, then planning, then
#: implementation — is the specificity order: a phase named ``g_adversarial_review`` is a
#: review even though "review" and "adversarial" both appear. [H]
_REVIEW_MARKERS: tuple[str, ...] = (
    "review",
    "adversarial",
    "posterior",
    "postmortem",
    "audit",
    "critique",
    "retro",
)
_VERIFICATION_MARKERS: tuple[str, ...] = (
    "test",
    "verif",
    "gate",
    "validat",
    "check",
    "assert",
    "accept",
)
_PLANNING_MARKERS: tuple[str, ...] = (
    "plan",
    "prior",
    "recon",
    "design",
    "proposal",
    "explore",
    "research",
    "spec",
    "author",
)
_IMPLEMENTATION_MARKERS: tuple[str, ...] = (
    "implement",
    "execute",
    "build",
    "fix",
    "repair",
    "refactor",
    "wire",
    "migrat",
    "code",
)

# ── Layer -> source_type material (the existing nine-producer vocabulary) ───────

#: The single layer -> source_type map. Each ``source_type`` is a member of
#: :data:`agentic_dynamics.knowledge.knowledge.SOURCE_TYPES` (the one KB vocabulary);
#: a test asserts every mapped string is registered, so a rename cannot silently orphan
#: a layer. The sets are DISJOINT and deterministic — an evidence item maps to at most
#: one layer, so the record never double-counts a source. [H]
#:
#: Deliberately unassigned: ``policy`` (pinned repository policy — read from the
#: checkout, never probabilistically retrieved), ``actuation`` (an instruction to act,
#: never evidence), and ``context_snapshot`` (address-only, a decision's frozen view).
LAYER_SOURCE_TYPES: dict[str, tuple[str, ...]] = {
    LAYER_TASK: (),  # L0 is the base prompt — no store lookup
    LAYER_STRUCTURE: ("code",),
    LAYER_HISTORY: (
        "story",
        "review",
        "ledger_job",
        "ledger_attempt",
        "meta_session",
        "decision",
        "observation",
        "flag",
        "finding",
        "spec",
    ),
    LAYER_OUTCOMES: ("report", "pattern", "fact", "orphan"),
    LAYER_SELF: ("belief", "reflection", "wave_verdict"),
}

#: Sanity anchor: mapped source types that are NOT registered in the one KB vocabulary.
#: Kept empty by construction and asserted in the tests — a rename in ``SOURCE_TYPES``
#: surfaces here instead of silently orphaning a layer. [C]
_UNREGISTERED_LAYER_SOURCE_TYPES: tuple[str, ...] = tuple(
    source_type
    for layer_types in LAYER_SOURCE_TYPES.values()
    for source_type in layer_types
    if source_type not in SOURCE_TYPES
)

#: The stable top-level keys every context-route record carries. A consumer may rely on
#: their presence; a missing key is a contract violation, not an optional field.
CONTEXT_ROUTE_RECORD_KEYS: tuple[str, ...] = (
    "schema",
    "phase",
    "phase_kind",
    "role",
    "route_status",
    "shared_scopes",
    "layers",
    "unclassified",
    "served_count",
    "fallback_mode",
    "fallback_reason",
    "routing_reason",
    "leg_errors",
)

#: The stable keys of every per-layer disposition entry.
CONTEXT_ROUTE_LAYER_KEYS: tuple[str, ...] = (
    "layer",
    "status",
    "source_types",
    "evidence_ids",
    "reason",
)

#: The stable keys of every unclassified (unattributable) evidence entry.
CONTEXT_ROUTE_UNCLASSIFIED_KEYS: tuple[str, ...] = (
    "id",
    "source_type",
    "status",
    "reason",
)

#: The NAMED reason recorded for evidence the seam withheld BEFORE construction because it
#: carried no resolvable layer on an UNRESOLVED route (A8-R1). A named constant, not an
#: inline literal, so the seam and its gate cannot drift on the wording.
UNRESOLVED_WITHHELD_REASON = "withheld before construction: untyped evidence on an unresolved route"

#: The NAMED reason on the synthetic ``unclassified`` LAYER entry when ONLY
#: served-but-unattributable evidence is present on an unresolved route: real served
#: material that maps to no layer. Named (not inline) so the layer summary and its gate
#: cannot drift; the wording must stay true of what was actually served.
UNRESOLVED_UNCLASSIFIED_SERVED_REASON = (
    "unroutable request: served evidence carries no layer disposition"
)

#: The NAMED reason on the synthetic ``unclassified`` LAYER entry when ONLY evidence
#: withheld BEFORE construction is present (A9-R1-note). Nothing was served, so the
#: summary must never claim served evidence; it names the withhold instead. The phrase
#: intentionally avoids ``served evidence carries no layer disposition`` for a record
#: whose ``served_count`` is zero.
UNRESOLVED_UNCLASSIFIED_WITHHELD_ONLY_REASON = (
    "unroutable request: no evidence was served; the evidence was withheld before construction"
)

#: The NAMED reason on the synthetic ``unclassified`` LAYER entry when BOTH
#: served-but-unattributable evidence AND withheld evidence are present (A9-R1-note): the
#: summary names BOTH dispositions, so an auditor can see why each id is unclassified.
UNRESOLVED_UNCLASSIFIED_MIXED_REASON = (
    "unroutable request: served evidence carries no layer disposition and "
    "evidence was withheld before construction"
)


# ── The routing rule's output ───────────────────────────────────


@dataclass(frozen=True)
class LayerRoute:
    """The resolved context-layer route for one phase.

    Frozen so a route is hashable and comparable: :func:`resolve_phase_layers` is
    deterministic, and two identical inputs must produce equal routes (the determinism
    gate). ``layers`` is the ordered tuple of *retrieval* layers resolved for the phase
    (``L0`` is the base prompt and is recorded by the builder, not resolved here);
    ``prohibited`` names layers refused by policy (always ``L4`` for a cell phase);
    ``source_types`` is the union of the resolved layers' source types, the exact shaping
    the retrieval prefilter consumes; ``shared_scopes`` are the EXPLICIT shared repository
    ids (empty means the cell's own scope only — empty never means global).
    """

    phase_name: str
    phase_kind: str = ""
    role: str = ROLE_UNKNOWN
    layers: tuple[str, ...] = ()
    prohibited: tuple[str, ...] = ()
    shared_scopes: tuple[str, ...] = ()
    source_types: tuple[str, ...] = ()
    reason: str = ""

    @classmethod
    def unknown(cls, phase_name: str = "", phase_kind: str = "") -> LayerRoute:
        """The honest fallback when no rule fires: no layer resolved, L4 still prohibited."""
        return cls(
            phase_name=str(phase_name or ""),
            phase_kind=str(phase_kind or ""),
            role=ROLE_UNKNOWN,
            layers=(),
            prohibited=(LAYER_SELF,),
            reason="routing unresolved",
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialise the route (the pre-augmentation half of the ledger record)."""
        return {
            "phase_name": self.phase_name,
            "phase_kind": self.phase_kind,
            "role": self.role,
            "layers": list(self.layers),
            "prohibited": list(self.prohibited),
            "shared_scopes": list(self.shared_scopes),
            "source_types": list(self.source_types),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class LayerRetrievalShape:
    """The ``retrieve()``-facing shaping derived from a resolved :class:`LayerRoute`.

    This is the *only* bridge between the layer vocabulary and the one existing retrieval
    path: it carries the source-type prefilter (the resolved layers' positive material), the
    explicit shared repository ids (the F2 union arm), and two advisory bits — the query
    *intent* label and whether pattern projection is needed so L3 outcome/pattern records are
    not filtered out by the candidate gate. It wires no store and starts no parallel search;
    an unrouted/unknown route yields the identity shape (no prefilter, no shared scopes), so
    the pre-existing retrieval path is preserved exactly. [C]
    """

    source_types: tuple[str, ...] = ()
    shared_repository_ids: tuple[str, ...] = ()
    pattern_projection: bool = False
    intent: str = ""

    def to_retrieve_kwargs(self) -> dict[str, Any]:
        """The ``retrieve()`` keyword shaping this route contributes (never a new path)."""
        return {
            "source_types": self.source_types,
            "shared_repository_ids": self.shared_repository_ids,
            "pattern_projection": self.pattern_projection,
        }


# ── Helpers ─────────────────────────────────────────────────────


def _as_layers(layers: Any) -> tuple[str, ...]:
    """Normalise a layer argument to an ordered tuple of layer ids (a bare str is one id)."""
    if layers is None:
        return ()
    if isinstance(layers, str):
        raw: tuple[Any, ...] = (layers,)
    else:
        raw = tuple(layers)
    return tuple(str(item).strip() for item in raw if str(item).strip())


def _sorted_layers(layer_ids: Any) -> tuple[str, ...]:
    """Deterministically order layer ids by the vocabulary (unknown ids last, stable)."""
    unique = {layer for layer in _as_layers(layer_ids)}
    return tuple(sorted(unique, key=lambda layer: _LAYER_ORDER.get(layer, len(LAYERS))))


def layer_source_types(layers: Any) -> tuple[str, ...]:
    """Union the source types of ``layers``, in deterministic layer/source order.

    This is the exact positive material a ``source_types`` retrieval prefilter consumes:
    a layer is served by retrieving records whose ``source_type`` is in its set. An
    unknown layer contributes nothing (it is dropped, not guessed at); ``L0`` is the base
    prompt and therefore contributes nothing. Duplicates collapse in first-seen order so
    the result is stable across callers.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for layer in _sorted_layers(layers):
        for source_type in LAYER_SOURCE_TYPES.get(layer, ()):
            if source_type not in seen:
                seen.add(source_type)
                ordered.append(source_type)
    return tuple(ordered)


def layer_for_source_type(source_type: str) -> str:
    """Map one ``source_type`` to its layer id, or ``""`` when it maps to no layer.

    The layer sets are disjoint, so the mapping is a pure function with no ambiguity. An
    unregistered/empty type returns ``""`` — the caller records it as *unclassified*
    rather than forcing it into a layer (measured-or-absent).
    """
    needle = str(source_type or "").strip().lower()
    if not needle:
        return ""
    for layer in LAYERS:
        if needle in LAYER_SOURCE_TYPES.get(layer, ()):
            return layer
    return ""


def route_resolved(route: Any) -> bool:
    """Whether ``route`` is a :class:`LayerRoute` that resolved at least ONE layer.

    This is the ONE shared predicate behind "did routing resolve real material?", used by
    both the augment seam's pre-construction withholding (A8-R1) and
    :func:`build_context_route_record`, so the seam and the record can never diverge about
    whether a route is resolved. ``True`` iff ``route`` is a :class:`LayerRoute` with a
    non-empty ``layers`` tuple:

    * ``None`` — no route was resolved → ``False`` (the honest unknown);
    * the explicit :meth:`LayerRoute.unknown` sentinel (``layers == ()``, reason
      ``"routing unresolved"``) → ``False`` — the SAME honest failure as ``None``;
    * a route that resolved the L2 floor → ``True``, even when its *role* is ``unknown``:
      the floor is real material, so the two cases must not conflate.

    Pure and deterministic (no clock, no store, no model).
    """
    return isinstance(route, LayerRoute) and bool(route.layers)


def shared_history_scopes(rag_params: Any) -> list[str]:
    """Parse the EXPLICIT shared history scopes from ``rag_params``.

    Default is ``[]`` — a cell retrieves only its own scope, and an empty list never means
    "global". Accepts ``shared_history_scopes`` (canonical), ``shared_scopes`` or
    ``shared_repository_ids``; a bare string is treated as a one-element list. Every entry
    is stripped, de-duplicated (first-seen order), and empty entries are dropped. The
    explicit global wildcards ``*`` / ``global`` / ``all`` are refused so a caller cannot
    widen a cell into the whole KB by accident ([P] — never global). [C]
    """
    if not isinstance(rag_params, Mapping):
        return []
    raw: Any = None
    for key in ("shared_history_scopes", "shared_scopes", "shared_repository_ids"):
        if rag_params.get(key) is not None:
            raw = rag_params.get(key)
            break
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        scope = str(item or "").strip()
        if not scope or scope.lower() in {"*", "global", "all"} or scope in seen:
            continue
        seen.add(scope)
        out.append(scope)
    return out


def classify_phase_role(phase_name: str, phase_kind: str = "") -> str:
    """Classify a phase into one of the routing roles by name/kind (deterministic).

    Specificity order: review, verification, planning, implementation, else unknown. A
    ``kind == "test"`` phase is verification regardless of its name. No clock, no model,
    no store — the same inputs always yield the same role. [H]
    """
    haystack = f"{phase_name or ''} {phase_kind or ''}".lower()
    kind = str(phase_kind or "").strip().lower()
    if any(marker in haystack for marker in _REVIEW_MARKERS):
        return ROLE_REVIEW
    if kind == "test" or any(marker in haystack for marker in _VERIFICATION_MARKERS):
        return ROLE_VERIFICATION
    if any(marker in haystack for marker in _PLANNING_MARKERS):
        return ROLE_PLANNING
    if any(marker in haystack for marker in _IMPLEMENTATION_MARKERS):
        return ROLE_IMPLEMENTATION
    return ROLE_UNKNOWN


def resolve_phase_layers(
    phase_name: str,
    phase_kind: str = "",
    hints: Mapping[str, Any] | None = None,
) -> LayerRoute:
    """Resolve the ordered retrieval layers for one phase (deterministic).

    Rule (design §6; [H] for the role mapping, [P] for the L4 prohibition):

    ============================  ======  ======  ======
    role                          L1      L2      L3
    ============================  ======  ======  ======
    planning                      yes     yes     yes
    implementation                yes     yes     only if ``risk``
    verification                  no      yes     only if ``risk``
    review                        no      yes     only if ``risk``
    unknown                       no      yes     only if ``risk``
    ============================  ======  ======  ======

    Every phase resolves **L2 history at open** (the floor): even an unrecognised phase
    opens with what happened here before. ``L1`` structure is the planning/implementation
    need. ``L3`` outcomes land at planning moments, or wherever a caller names a risk hint
    (``risk`` / ``risk_moment``). ``L4`` self is **never** resolved for a cell phase: if
    requested it is moved to ``prohibited`` and remains out of ``layers``. Only an
    explicit ``cell_phase=False`` hint (a controller-owned phase) may resolve L4.

    Hints (all optional): ``role``/``phase_role``/``scope`` — explicit role override;
    ``layers``/``context_layers`` — additional explicit layer ids (unknown ids dropped);
    ``risk``/``risk_moment`` — force L3; ``cell_phase`` — default ``True`` (a cell phase);
    ``shared_history_scopes`` (and aliases) — parsed by :func:`shared_history_scopes`.
    """
    hint_map: Mapping[str, Any] = hints if isinstance(hints, Mapping) else {}

    explicit_role = (
        str(hint_map.get("role") or hint_map.get("phase_role") or hint_map.get("scope") or "")
        .strip()
        .lower()
    )
    role = (
        explicit_role
        if explicit_role in ROLE_VALUES
        else classify_phase_role(phase_name, phase_kind)
    )

    # The floor: every phase opens with history. Then add role-specific layers.
    resolved: set[str] = {LAYER_HISTORY}
    if role in (ROLE_PLANNING, ROLE_IMPLEMENTATION):
        resolved.add(LAYER_STRUCTURE)
    if role == ROLE_PLANNING or bool(hint_map.get("risk") or hint_map.get("risk_moment")):
        resolved.add(LAYER_OUTCOMES)

    # Explicit layer requests may add L1/L2/L3; L4 is policy-gated below.
    cell_phase = bool(hint_map.get("cell_phase", True))
    prohibited: list[str] = []
    for layer in _as_layers(hint_map.get("layers") or hint_map.get("context_layers")):
        if layer == LAYER_SELF and cell_phase:
            if LAYER_SELF not in prohibited:
                prohibited.append(LAYER_SELF)
            continue
        if layer in (LAYER_STRUCTURE, LAYER_HISTORY, LAYER_OUTCOMES, LAYER_SELF):
            resolved.add(layer)

    # L4 is never resolved for a cell phase, even when not explicitly requested.
    if cell_phase and LAYER_SELF not in prohibited:
        prohibited.append(LAYER_SELF)
    if cell_phase:
        resolved.discard(LAYER_SELF)

    ordered = _sorted_layers(resolved)
    return LayerRoute(
        phase_name=str(phase_name or ""),
        phase_kind=str(phase_kind or ""),
        role=role,
        layers=ordered,
        prohibited=tuple(prohibited),
        shared_scopes=tuple(shared_history_scopes(hint_map)),
        source_types=layer_source_types(ordered),
        reason=f"role={role}",
    )


#: Coarse [H] markers that a phase is asking what happened/what is likely (an L2/L3 question)
#: rather than how the system is built (an L1 question). Only used to *label* the intent.
_OUTCOME_INTENT_MARKERS: tuple[str, ...] = (
    "what happened",
    "previous",
    "prior attempt",
    "failure",
    "risk",
    "outcome",
    "likely",
    "cost",
    "latency",
)


def _query_intent(route: LayerRoute, goal: str, base_prompt: str) -> str:
    """Deterministically name what the phase is asking for ([H], no LLM).

    The intent is the *label* of the shaping, not a query rewriter: it reports which layer
    the phase's question is anchored on so the record and the ledger show why a route was
    shaped the way it was. The resolved layers are authoritative; the goal/base-prompt text
    only breaks ties between an outcomes-seeking and a structure-seeking question.
    """
    if LAYER_OUTCOMES in route.layers:
        return "outcomes"
    text = f"{goal}\n{base_prompt}".lower()
    if any(marker in text for marker in _OUTCOME_INTENT_MARKERS):
        return "history"
    if LAYER_STRUCTURE in route.layers:
        return "structure"
    return "task"


def resolve_layer_route(
    route: LayerRoute | None,
    *,
    goal: str = "",
    base_prompt: str = "",
) -> LayerRetrievalShape:
    """Map a resolved :class:`LayerRoute` to the ``retrieve()`` shaping (the ONE path).

    The design's routing rule (§6) selects *which* layers a phase needs; this function is
    the arithmetic that turns that selection into the existing retrieval engine's inputs:

    * ``source_types`` — the resolved layers' source-type union, threaded as ``retrieve``'s
      prefilter so only a layer's material can enter fusion. ``L0`` (the base prompt)
      contributes nothing; an unknown/unresolved route yields ``()`` — the identity, never
      "match nothing".
    * ``shared_repository_ids`` — the route's EXPLICIT shared scopes (empty never means
      global), threaded as the requested ∪ shared union arm (F2).
    * ``pattern_projection`` — enabled exactly when L3 outcomes are resolved, because the
      candidate gate otherwise drops ``pattern`` records before fusion, which would make the
      "serve L3" route silently empty. [C]
    * ``intent`` — a deterministic label of the phase's question (``structure`` / ``history``
      / ``outcomes`` / ``task``) recorded for audit; it never rewrites the query. [H]

    A ``None``/non-:class:`LayerRoute` route is the honest unknown: the identity shape, so a
    caller that could not resolve a route changes nothing about retrieval. The function is
    pure (no clock, no store, no model) and is the sole owner of this mapping.
    """
    if not isinstance(route, LayerRoute):
        return LayerRetrievalShape(intent=ROLE_UNKNOWN)
    return LayerRetrievalShape(
        source_types=route.source_types,
        shared_repository_ids=route.shared_scopes,
        pattern_projection=LAYER_OUTCOMES in route.layers,
        intent=_query_intent(route, str(goal or ""), str(base_prompt or "")),
    )


# ── The single record builder ───────────────────────────────────


def _get(holder: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` from a mapping, an object attribute, or ``default`` (test-double safe)."""
    if holder is None:
        return default
    if isinstance(holder, Mapping):
        return holder.get(key, default)
    return getattr(holder, key, default)


def _phase_identity(phase: Any) -> tuple[str, str]:
    """Extract ``(name, kind)`` from a phase string, mapping, or phase-like object."""
    if isinstance(phase, str):
        return phase, ""
    if isinstance(phase, Mapping):
        name = phase.get("name") or phase.get("phase_name") or phase.get("id") or ""
        kind = phase.get("kind") or phase.get("phase_kind") or ""
        return str(name), str(kind)
    name = getattr(phase, "name", "") or getattr(phase, "phase_name", "")
    kind = getattr(phase, "kind", "") or getattr(phase, "phase_kind", "")
    return str(name or ""), str(kind or "")


def _normalize_evidence(item: Any) -> dict[str, str]:
    """Normalise a served item (Candidate or provenance dict) to ``{id, source_type}``."""
    if isinstance(item, Mapping):
        evidence_id = item.get("id", "")
        source_type = item.get("source_type", "")
    else:
        evidence_id = getattr(item, "id", "")
        source_type = getattr(item, "source_type", "")
    return {
        "id": str(evidence_id or ""),
        "source_type": str(source_type or "").strip().lower(),
    }


#: Sentinel distinguishing "the holder has no served-evidence field at all" from "the holder
#: provided an EMPTY served list". The distinction is load-bearing for F4: an outcome whose
#: constructor trimmed every candidate to zero served NOTHING, and must not resurrect the
#: attempt's unserved candidates as if they had been handed to the worker.
_MISSING = object()


def _served_evidence(outcome: Any, attempt: Any) -> list[dict[str, str]]:
    """The FINAL served evidence set: the outcome's own list, else the attempt's.

    The constructor may trim the retrieved set, so the outcome's ``selected_evidence`` is
    the honest "served" list; the attempt's candidates are used ONLY when the outcome has no
    served-evidence field at all (a test double). An outcome that explicitly provides an
    EMPTY list served nothing and is respected as empty (never back-filled from the attempt).
    """
    for holder in (outcome, attempt):
        if holder is None:
            continue
        selected = _get(holder, "selected_evidence", _MISSING)
        if selected is _MISSING or selected is None:
            continue
        return [_normalize_evidence(item) for item in selected]
    return []


def normalize_shared_scopes(shared_scopes: Any, route: LayerRoute | None = None) -> list[str]:
    """Union the explicit keyword scopes with the route's scopes, canonical parsing applied.

    This is the single place the two shared-scope sources are merged, so retrieval and the
    record can never disagree about which scopes were honoured. Explicit global wildcards
    are still refused by :func:`shared_history_scopes` (empty never means global).
    """
    scopes = shared_history_scopes({"shared_history_scopes": shared_scopes})
    if isinstance(route, LayerRoute):
        for scope in route.shared_scopes:
            if scope not in scopes:
                scopes.append(scope)
    return scopes


def self_layer_prohibited(route: LayerRoute | None) -> bool:
    """Whether L4 self-layer content must be REFUSED for ``route`` (policy, [P]).

    This is the ONE shared rule (R1) used by both the seam's pre-construction evidence
    filter (``augment.augment_prompt``) and :func:`build_context_route_record`, so the
    seam and the record can never disagree about whether self content was allowed.

    L4 is prohibited unless the route EXPLICITLY resolved ``L4`` and did not mark it
    prohibited: an absent/``None`` route, the explicit :meth:`LayerRoute.unknown` sentinel,
    and every ordinary cell route all prohibit it. Only a controller-owned phase (a route
    with ``L4`` in ``layers``) may serve self content.
    """
    if not isinstance(route, LayerRoute):
        return True
    return (LAYER_SELF in route.prohibited) or (LAYER_SELF not in route.layers)


def build_context_route_record(
    phase: Any,
    route: LayerRoute | None,
    attempt: Any,
    outcome: Any,
    *,
    shared_scopes: Any,
    excluded_evidence: Any = None,
    withheld_evidence: Any = None,
) -> dict[str, Any]:
    """Build the SINGLE per-phase ``context-route/v1`` record.

    ``phase`` is a phase name/mapping/object; ``route`` the resolved :class:`LayerRoute`
    (or ``None``, or the explicit :meth:`LayerRoute.unknown` sentinel, when routing failed)
    — an unresolved route is recorded as ``route_status == "unknown"`` WITH its named
    reason in ``routing_reason``. ``routing_reason`` is a STABLE TOP-LEVEL KEY computed
    ALWAYS: it names why routing failed (the sentinel's ``route.reason`` when present,
    else ``"routing unresolved"``) for an unresolved route, and is ``""`` for a route
    that resolved at least one layer. It is deliberately SEPARATE from
    ``fallback_reason`` (the outcome's retrieval/construction failure), so a competing
    retrieval fallback can never erase the routing diagnosis (A8-R4). A route that
    resolved at least one layer (the L2 floor) stays
    ``resolved`` even when its *role* is ``unknown``; only a route that resolved NO layers
    is the sentinel. ``attempt`` a ``RetrievalAttempt``-shaped object; ``outcome`` an
    ``AugmentationOutcome`` (or ``None``). ``shared_scopes`` is REQUIRED: the explicit
    shared repository ids the caller threaded into retrieval (empty means the cell scope
    only, never global). ``excluded_evidence`` is the OPTIONAL list of ``{id, source_type}``
    items that a caller refused BEFORE construction (the seam's R1 pre-filter): their ids
    are carried on the L4 ``excluded`` disposition, so the refusal is honest per item
    rather than inferred after the fact. ``withheld_evidence`` is the OPTIONAL list of
    ``{id, source_type}`` items the seam withheld BEFORE construction because they carried
    no resolvable layer on an UNRESOLVED route (A8-R1): each is appended to the record's
    ``unclassified`` list with ``status == "unknown"`` and a named withhold reason, and its
    id rides the synthetic ``unclassified`` layer entry, so a withheld item is never
    silently dropped nor ever counted as served. The synthetic layer's ``reason`` is
    TRUTHFUL about the kinds it lists (A9-R1-note): served-but-unattributable evidence, a
    withheld-before-construction record (nothing served), or both — a withheld-only record
    never claims served evidence.

    Every resolved layer gets exactly one disposition drawn from the closed set:

    * ``served`` — at least one served item maps to the layer (ids recorded);
    * ``named_absent`` — no attempt, an augmentation fallback, or a failed leg: the reason
      is named, never an empty success;
    * ``empty`` — retrieval completed cleanly and matched nothing for the layer;
    * ``excluded`` — prohibited L4 content was refused (its ids are still recorded);
    * ``unknown`` — a served item could not be attributed to a resolved layer (also the
      disposition of every item under an unresolved route), so no item is ever served
      without a record.

    ``L0`` is always recorded ``served`` (the base prompt is preserved by the seam, even
    on fallback), so a reader can see the task layer was not silently dropped.
    """
    phase_name, phase_kind = _phase_identity(phase)
    is_route = isinstance(route, LayerRoute)
    if is_route:
        if not phase_name:
            phase_name = route.phase_name
        if not phase_kind:
            phase_kind = route.phase_kind
        role = route.role
        resolved = tuple(route.layers)
    else:
        role = ROLE_UNKNOWN
        resolved = ()

    # A route is only "resolved" when it resolved at least ONE layer. The explicit
    # ``LayerRoute.unknown()`` sentinel (role unknown, layers == ()) and ``None`` both
    # resolve NO layers and must record ``unknown`` — they are the same honest failure. A
    # route that resolved the L2 floor (layers non-empty) stays ``resolved`` even when its
    # role is ``unknown``: the floor is real material, so the two cases must not conflate.
    # The predicate is the SHARED ``route_resolved`` helper (A8-R1), so the seam's
    # pre-construction withholding and this builder can never disagree about resolution.
    route_is_resolved = route_resolved(route)
    route_unresolved = not route_is_resolved

    # L4 must be EXPLICITLY resolved to be servable; otherwise any self-layer evidence is
    # refused. This keeps the prohibition even for a manually built route that omitted
    # ``prohibited`` — not requested means not served. The shared helper is the SAME rule
    # the seam uses, so the filter and the record cannot diverge (R1).
    l4_prohibited = self_layer_prohibited(route)

    served_items = _served_evidence(outcome, attempt)
    # Items a caller already refused BEFORE construction (the seam's pre-filter). They are
    # not attributed to a layer; their ids feed the L4 excluded disposition below, so the
    # record names exactly what was withheld instead of re-deriving it from a prompt that
    # never should have contained it (R1 honesty).
    refused_items = [_normalize_evidence(item) for item in (excluded_evidence or [])]
    excluded_ids: list[str] = []
    excluded_seen: set[str] = set()
    for item in refused_items:
        if item["id"] and item["id"] not in excluded_seen:
            excluded_seen.add(item["id"])
            excluded_ids.append(item["id"])

    # Items the seam WITHHELD before construction because they were untyped on an unresolved
    # route (A8-R1). They never reached the constructor, so they cannot be served; each gets
    # an honest ``unknown`` disposition with the named withhold reason and joins the same
    # ``unclassified`` list as served-but-unattributable items, so nothing is silently
    # dropped and the synthetic ``unclassified`` layer entry below still lists every one.
    withheld_items = [_normalize_evidence(item) for item in (withheld_evidence or [])]

    # Attribute each served item to a layer. L4 content is refused by policy; anything
    # else that maps nowhere is unclassified (recorded, never silently served). The two
    # unclassified KINDS are counted separately (A9-R1-note): a served-but-unattributable
    # item and an item withheld BEFORE construction carry different truths, and the
    # synthetic layer summary below must not claim one when only the other occurred.
    served_by_layer: dict[str, list[str]] = {layer: [] for layer in resolved}
    unclassified: list[dict[str, str]] = []
    served_unclassified_count = 0
    withheld_unclassified_count = 0
    for item in served_items:
        layer_id = layer_for_source_type(item["source_type"])
        if layer_id == LAYER_SELF and l4_prohibited:
            if item["id"] and item["id"] not in excluded_seen:
                excluded_seen.add(item["id"])
                excluded_ids.append(item["id"])
            continue
        if layer_id and layer_id in served_by_layer:
            served_by_layer[layer_id].append(item["id"])
            continue
        unclassified.append(
            {
                "id": item["id"],
                "source_type": item["source_type"] or "untyped",
                "status": LAYER_STATUS_UNKNOWN,
                "reason": (
                    "unroutable request: no layer resolved"
                    if route_unresolved
                    else "source_type maps to no resolved layer"
                ),
            }
        )
        served_unclassified_count += 1
    for item in withheld_items:
        if item["id"] and any(existing["id"] == item["id"] for existing in unclassified):
            # Never double-record the same evidence (an item is either served or withheld).
            continue
        unclassified.append(
            {
                "id": item["id"],
                "source_type": item["source_type"] or "untyped",
                "status": LAYER_STATUS_UNKNOWN,
                "reason": UNRESOLVED_WITHHELD_REASON,
            }
        )
        withheld_unclassified_count += 1

    # The outcome's fallback + leg errors are the named-absence inputs.
    fallback = bool(_get(outcome, "fallback", False))
    fallback_mode = str(_get(outcome, "fallback_mode", "") or "no_rag")
    fallback_reason = str(_get(outcome, "fallback_reason", "") or "")
    # A8-R4: the routing diagnosis is its OWN stable top-level key, computed ALWAYS so a
    # competing retrieval/constructor fallback can never erase it. An unresolved route
    # names why routing failed (the sentinel carries it on ``route.reason``; ``None`` gets
    # the same explicit default); a route that resolved at least one layer has no routing
    # reason at all (``""``). This is a SEPARATE field from ``fallback_reason``, which stays
    # the outcome's retrieval/construction failure — the two failures coexist in the record.
    routing_reason = (
        (str(getattr(route, "reason", "") or "").strip() or "routing unresolved")
        if route_unresolved
        else ""
    )
    raw_leg_errors = _get(outcome, "retrieval_leg_errors", None)
    if raw_leg_errors is None:
        raw_leg_errors = _get(attempt, "leg_errors", {}) or {}
    leg_errors = {str(key): str(value) for key, value in dict(raw_leg_errors).items()}
    leg_reason = "; ".join(f"{key}: {leg_errors[key]}" for key in sorted(leg_errors))

    def _disposition(layer_id: str, evidence_ids: list[str]) -> tuple[str, str]:
        """The one honest status for a layer given its served ids and the pass outcome."""
        if evidence_ids:
            return LAYER_STATUS_SERVED, ""
        if attempt is None:
            return LAYER_STATUS_NAMED_ABSENT, "no retrieval attempt recorded"
        if fallback:
            return LAYER_STATUS_NAMED_ABSENT, fallback_reason or "augmentation_fallback"
        if leg_errors:
            return LAYER_STATUS_NAMED_ABSENT, leg_reason or "retrieval_leg_failed"
        if route_unresolved:
            return LAYER_STATUS_UNKNOWN, "routing unresolved"
        return LAYER_STATUS_EMPTY, "retrieval completed with no evidence for this layer"

    # L0 (task) is always present as a served disposition: the base prompt is preserved.
    l0_status, l0_reason = (
        (LAYER_STATUS_SERVED, "base prompt preserved")
        if outcome is not None
        else (LAYER_STATUS_NAMED_ABSENT, "no base prompt recorded")
    )
    layers: list[dict[str, Any]] = [
        {
            "layer": LAYER_TASK,
            "status": l0_status,
            "source_types": list(LAYER_SOURCE_TYPES[LAYER_TASK]),
            "evidence_ids": [],
            "reason": l0_reason,
        }
    ]
    for layer_id in resolved:
        status, reason = _disposition(layer_id, served_by_layer.get(layer_id, []))
        layers.append(
            {
                "layer": layer_id,
                "status": status,
                "source_types": list(LAYER_SOURCE_TYPES.get(layer_id, ())),
                "evidence_ids": list(served_by_layer.get(layer_id, [])),
                "reason": reason,
            }
        )

    # The prohibited L4 layer always gets an explicit excluded disposition (never silent).
    if l4_prohibited and LAYER_SELF not in resolved:
        layers.append(
            {
                "layer": LAYER_SELF,
                "status": LAYER_STATUS_EXCLUDED,
                "source_types": list(LAYER_SOURCE_TYPES[LAYER_SELF]),
                "evidence_ids": excluded_ids,
                "reason": "prohibited self-layer content: never served to a cell phase",
            }
        )

    # An unresolved route — the explicit unknown sentinel OR ``None`` — with served items
    # still gets a layer-level unknown disposition, so a served non-self item is recorded
    # ``unclassified``/``unknown`` and is never counted as served. The layer-level reason
    # names the ACTUAL kinds present (A9-R1-note): served-but-unattributable evidence, or
    # evidence withheld BEFORE construction (nothing served), or both — a withheld-only
    # record must never claim served evidence when ``served_count`` is zero.
    if route_unresolved and unclassified:
        if served_unclassified_count and withheld_unclassified_count:
            unclassified_reason = UNRESOLVED_UNCLASSIFIED_MIXED_REASON
        elif withheld_unclassified_count:
            unclassified_reason = UNRESOLVED_UNCLASSIFIED_WITHHELD_ONLY_REASON
        else:
            unclassified_reason = UNRESOLVED_UNCLASSIFIED_SERVED_REASON
        layers.append(
            {
                "layer": "unclassified",
                "status": LAYER_STATUS_UNKNOWN,
                "source_types": [],
                "evidence_ids": [item["id"] for item in unclassified],
                "reason": unclassified_reason,
            }
        )

    served_count = sum(len(ids) for ids in served_by_layer.values())
    return {
        "schema": CONTEXT_ROUTE_SCHEMA,
        "phase": phase_name,
        "phase_kind": phase_kind,
        "role": role,
        "route_status": "resolved" if route_is_resolved else "unknown",
        "shared_scopes": normalize_shared_scopes(shared_scopes, route if is_route else None),
        "layers": layers,
        "unclassified": unclassified,
        "served_count": served_count,
        "fallback_mode": fallback_mode,
        "fallback_reason": fallback_reason,
        "routing_reason": routing_reason,
        "leg_errors": leg_errors,
    }


__all__ = [
    "CONTEXT_ROUTE_LAYER_KEYS",
    "CONTEXT_ROUTE_RECORD_KEYS",
    "CONTEXT_ROUTE_SCHEMA",
    "CONTEXT_ROUTE_UNCLASSIFIED_KEYS",
    "EXECUTION_SCOPE_ROLES",
    "LAYERS",
    "LAYER_HISTORY",
    "LAYER_OUTCOMES",
    "LAYER_SELF",
    "LAYER_SOURCE_TYPES",
    "LAYER_STATUSES",
    "LAYER_STATUS_EMPTY",
    "LAYER_STATUS_EXCLUDED",
    "LAYER_STATUS_NAMED_ABSENT",
    "LAYER_STATUS_SERVED",
    "LAYER_STATUS_SET",
    "LAYER_STATUS_UNKNOWN",
    "LAYER_STRUCTURE",
    "LAYER_TASK",
    "ROLE_IMPLEMENTATION",
    "ROLE_PLANNING",
    "ROLE_REVIEW",
    "ROLE_UNKNOWN",
    "ROLE_VALUES",
    "ROLE_VERIFICATION",
    "UNRESOLVED_UNCLASSIFIED_MIXED_REASON",
    "UNRESOLVED_UNCLASSIFIED_SERVED_REASON",
    "UNRESOLVED_UNCLASSIFIED_WITHHELD_ONLY_REASON",
    "UNRESOLVED_WITHHELD_REASON",
    "LayerRetrievalShape",
    "LayerRoute",
    "build_context_route_record",
    "classify_phase_role",
    "execution_scope_role",
    "layer_for_source_type",
    "layer_source_types",
    "normalize_shared_scopes",
    "resolve_layer_route",
    "resolve_phase_layers",
    "route_resolved",
    "self_layer_prohibited",
    "shared_history_scopes",
]
