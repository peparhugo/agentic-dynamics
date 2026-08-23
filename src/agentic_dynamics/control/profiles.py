"""CAP I8 — ``DomainProfile`` + ``ChallengeProfile`` (declared strategy, never a second gate).

Reserved home per the accepted addendum (``docs/designs/current/context_abstraction_addendum_
design.md``, §2, §6). A profile is the reusable, DECLARED representation of "what domain is this"
(:class:`DomainProfile`) and "what kind of problem is this" (:class:`ChallengeProfile`) — an
author's strategy input, not a measurement. Frozen dataclasses: a profile is immutable, and a new
version is a NEW record that supersedes the old one under a stable key, exactly as a modified
symbol is a new ``knowledge_id`` under a stable ``entity_id`` (``knowledge.py:13-18``) — see
:func:`declare_domain_profile` / :func:`declare_challenge_profile` for how that stability shows up
in a :class:`~agentic_dynamics.control.facts.CanonicalFact`'s ``fact_entity_id``.

THE COMPOSITION RULE THIS MODULE IMPLEMENTS AND NOTHING MORE (§2.3, deviation D4): a profile may
ADD context a decision may see; it may never RELAX what a contract requires or ADMIT what a
contract excludes. :func:`compose_requirements` composes ONLY a :class:`ChallengeProfile`'s
``context_requirements`` into a contract's ``requires_facts`` — the contract's ``invariants``
remain untouched and are the sole *safety* gate. The three other :class:`ChallengeProfile` fields
(``verification_policy``, ``deliberation``, ``session_policy``) are declared strategy inputs with
their OWN monotone-tightening obligations (verification may only add tools, deliberation may
reorder but never omit a contract-relied-on stage) — those obligations bind a FUTURE caller that
consumes this profile to drive an executor; nothing in this repository consumes them yet, so this
module does not fabricate enforcement code for a call site that does not exist (no half-finished
implementation; see the module's own honesty posture below).

THE HONESTY RULE THIS MODULE OBEYS (§2.1, deviation D6): v1 profiles declare L5 policy-adjacent
facts ONLY (``domain_profile_version`` / ``challenge_profile_version`` — both ``abstraction_level
="policy"``, workload-scoped, exactly like ``policy_facts.py``'s existing ``allowed_models`` /
``max_spend_usd`` / ``max_attempts`` rows). L4 workload-level predicates (a profile claiming to be
the PRODUCER of some workload-scoped measurement) are explicitly deferred — declaring one here
with no reducer behind it would repeat the exact ``LEDGER_FIELDS`` failure ``FACT_PREDICATES`` was
built to make structurally impossible (``control/facts.py``'s own docstring).

Deviation from the design doc's own framing: the addendum text (written before I0–I7 landed) marks
``compile_context``, ``FactRequirement``, and the contract machinery ``[design-only]``. They are
REAL as of this tree (``control/context_compiler.py``, ``core/contracts.py``) — this module is
written against the real signatures, not the design's placeholder sketch (see
``context_compiler.compile_context``'s docstring for the same note).

``challenge`` is a SEPARATE, compiler-owned enum declared here (:data:`DELIBERATION_STAGES`'s
keys), with a documented — not shared-constant — mapping to
``core.session_types.TASK_TYPES`` (the story-session phase vocabulary: ``greenfield``,
``feature_addition``, ``integration``, ``refactor``, ``cross_cutting``). The two vocabularies
overlap in spelling for ``greenfield``/``cross_cutting`` but answer different questions — a task
type says what KIND OF CHANGE a session made; a challenge archetype says what STRATEGY a decision
should follow — so they are declared independently here rather than imported, to avoid the exact
split-brain a shared constant would invite once one vocabulary needs a value the other doesn't
(``research``/``incident``/``migration`` have no ``TASK_TYPES`` analogue at all).

MIGRATION — swapping a workflow spec's static profile filing (the deliverable this increment
owes): ``workflows/repository/cap_addendum_implement.yaml`` (this very workflow) declares a
PROVISIONAL profile as free-text prose in ``workflow.params.context.domain_context`` /
``challenge_context`` (lines 24-36) — written before this module existed, because I8 had not
landed yet. :func:`migrate_static_filing` is the swap-in replacement: it resolves the SAME
declared content (domain ``software_delivery``, challenge archetype) against :data:`PROFILES`,
the structured registry this module now provides. The full swap procedure, for a future change
(deliberately NOT done here — it touches ``scripts/run_workflow.py``'s phase-prompt rendering,
outside this increment's reserved home and this increment's "no runner wiring changes" guard):

1. A workflow spec YAML gains two new optional ``workflow.params`` fields, e.g.
   ``domain_profile_id: software_delivery`` / ``challenge_profile_id: greenfield``, replacing the
   free-text ``context.domain_context`` / ``context.challenge_context`` strings.
2. ``scripts/run_workflow.py`` (or ``runtime.workflow_runner``, whichever renders the phase
   prompt) calls ``migrate_static_filing(domain=..., challenge=...)`` and, when both resolve,
   renders the profile's OWN fields (``canonical_sources``, ``policies``, ``deliberation``, ...)
   into the phase prompt instead of splicing the hand-written prose in.
3. Until step 2 ships, the free-text fields remain the interim filing for every spec authored
   before this module existed; NEW specs should prefer referencing a :data:`PROFILES` entry by id
   in their own documentation/commit message even before the runner wiring lands, so the swap in
   step 2 is a mechanical find-and-replace, not a rediscovery of what each spec meant.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    CanonicalFact,
    EvidenceItem,
    ReducerInput,
    ReducerSpec,
    compute_fact_entity_id,
    recompute_inputs_digest,
)
from agentic_dynamics.core.contracts import ContractLike, FactRequirement

# ── §2.1 — the two declared-profile dataclasses ──────────────────


@dataclass(frozen=True)
class SessionPolicy:
    """The declared session-continuation strategy for a challenge archetype (addendum A.4, §2.6).

    ``shadow_only`` defaults ``True`` and MUST stay ``True`` until the I10 evidence-seed
    experiment (design §4.4) actually lands measured data — this field is the single switch a
    future increment would flip, and flipping it is explicitly out of THIS increment's scope
    (I8 never arms actuation; see the workflow spec's own "apply stays OFF" hard rule).
    """

    policy: str  # continue_default | fork_always | compress_and_fork | escalate_on_failure
    fork_when: tuple[str, ...] = ()  # "goal_changed" | "model_changed" | "phase_gap"
    max_fork_depth: int = 1
    compress_threshold_tokens: int = 0  # 0 = never auto-compress
    shadow_only: bool = True


@dataclass(frozen=True)
class DomainProfile:
    """The reusable, declared representation of ONE domain. Declared, never measured (§2.1).

    ``predicates``/``policies``/``patterns`` are three DIFFERENT kinds of reference, on purpose
    (design's own rationale, quoted): a predicate is a *schema* name (a :class:`PredicateSpec`
    key — checked against :data:`FACT_PREDICATES` by :func:`domain_profile_predicates_known`,
    never silently assumed); a policy or pattern is an *instance* with a fact id — a profile
    naming one that does not resolve is merely ``unknown`` at read time, not a refusal, because
    the profile is declared before the policy/pattern fact necessarily exists.
    """

    domain: str  # e.g. "software_delivery" — the profile's key
    profile_version: str  # "software_delivery/v1" — the extractor version (§2.2), NOT derived
    canonical_sources: tuple[str, ...]  # ARCHITECTURE.md, pyproject.toml, ...
    predicates: tuple[str, ...]  # subset of FACT_PREDICATES this domain registers (NAMES)
    policies: tuple[str, ...]  # L5 policy fact ids this domain declares (tests_must_pass, ...)
    patterns: tuple[str, ...]  # I9 pattern fact ids considered in-domain
    verification: tuple[str, ...]  # deterministic tools: pytest, ruff, mypy, ...


@dataclass(frozen=True)
class ChallengeProfile:
    """The working strategy for a problem archetype. SELECTED, never hard-coded (addendum A.2).

    ``context_requirements`` is the ONLY field :func:`compose_requirements` reads (§2.3, deviation
    D4) — ``deliberation``/``verification_policy``/``session_policy`` are strategy inputs a future
    executor-facing caller would consume, not a second requirements gate.
    """

    challenge: str  # greenfield | cross_cutting | small_change | research | incident | migration
    profile_version: str  # "challenge/cross_cutting/v1"
    context_requirements: tuple[FactRequirement, ...]  # composed into a contract, never around it
    deliberation: tuple[str, ...]  # ordered stage names per archetype (§2.5)
    session_policy: SessionPolicy  # A.4 — session continuation/fork is a CAP decision (§4)
    verification_policy: tuple[str, ...]  # which of the domain's tools gate this challenge


# ── §2.5 — deliberation stages per archetype ─────────────────────

#: The design's own seed table (§2.5). Keys ARE the ``challenge`` vocabulary (:data:`CHALLENGES`).
DELIBERATION_STAGES: dict[str, tuple[str, ...]] = {
    "greenfield": ("survey", "scaffold", "implement_core", "wire_tests", "verify", "finish"),
    "cross_cutting": (
        "map_impact",
        "identify_invariants",
        "choose_sequence",
        "implement_in_slices",
        "regression_gates",
    ),
    "small_change": ("locate", "edit", "lint_test", "finish"),
    "research": (
        "state_hypotheses",
        "measurable_variables",
        "inspect_priors",
        "design_discriminating_test",
        "execute",
        "accept_reject",
    ),
    "incident": (
        "triage",
        "reproduce",
        "isolate_root_cause",
        "patch",
        "regression_gates",
        "postmortem",
    ),
    "migration": (
        "inventory",
        "map_parity",
        "migrate_in_slices",
        "verify_behavior",
        "regression_gates",
        "cutover",
    ),
}

#: The closed ``challenge`` vocabulary — the keys of :data:`DELIBERATION_STAGES`.
CHALLENGES: frozenset[str] = frozenset(DELIBERATION_STAGES)


def domain_profile_predicates_known(profile: DomainProfile) -> tuple[str, ...]:
    """Return the entries of ``profile.predicates`` that are NOT declared in
    :data:`~agentic_dynamics.control.facts.FACT_PREDICATES` — empty means every claimed predicate
    is real. A :class:`DomainProfile` naming an undeclared predicate would be exactly the
    ``LEDGER_FIELDS`` failure the fact schema exists to make impossible (facts.py's own
    docstring); this is the read-time check a caller runs before trusting a profile's claim
    (deliberately not a dataclass ``__post_init__`` — a frozen profile is pure data, and the
    schema it is checked against, :data:`FACT_PREDICATES`, can grow after the profile is authored)."""
    return tuple(p for p in profile.predicates if p not in FACT_PREDICATES)


# ── §2.3 — the composition rule (contract stays the SOLE gate) ───


class ProfileCompositionError(ValueError):
    """Raised when composing a :class:`ChallengeProfile` into a contract would relax what the
    contract requires, admit a fact the contract excludes, or otherwise change a requirement's
    scope/type in a way that is not a pure tightening (§2.3)."""


#: Rank for :attr:`core.contracts.FactRequirement.min_authority` — HIGHER rank is a STRICTER
#: floor (fewer facts qualify). Mirrors ``core.contracts.MIN_AUTHORITY_LEVELS`` (ADVISORY is
#: deliberately absent there too — R5 refuses a control rule that could consume it).
_MIN_AUTHORITY_RANK: dict[str, int] = {"DERIVED": 0, "SOURCE": 1, "MEASURED": 2, "POLICY": 3}

#: Rank for ``on_missing`` — HIGHER rank is STRICTER (fails closed rather than degrading).
#: ``classify``/``investigate`` both admit a decision in a degraded state and are ranked equal;
#: ``escalate`` blocks pending review; ``halt`` refuses outright (mirrors R11's own "an invariant
#: that classifies is not a constraint" ordering, generalized to the ``requires_facts`` axis).
_ON_MISSING_STRICTNESS: dict[str, int] = {"classify": 0, "investigate": 0, "escalate": 1, "halt": 2}

#: Rank for ``on_conflict`` — same STRICTER-is-higher convention. ``prefer_higher_authority``
#: resolves a conflict through a judgment call rather than either failing closed (``halt``) or
#: forwarding it (``escalate``), so it ranks between ``classify`` and the two failure modes.
_ON_CONFLICT_STRICTNESS: dict[str, int] = {
    "classify": 0,
    "prefer_higher_authority": 1,
    "escalate": 2,
    "halt": 2,
}


def tighten(existing: FactRequirement, addition: FactRequirement) -> FactRequirement:
    """Merge two :class:`FactRequirement` entries for the SAME fact into their strictest union.

    Pure; never widens. ``max_age_seconds``/``min_authority``/``on_missing``/``on_conflict`` each
    resolve to whichever side is STRICTER (never the profile's looser ask) — a contract's own
    requirement can only get tighter by a profile naming the same fact, never looser. ``scope``
    and ``value_type`` have no sensible "stricter" merge (they name WHERE/WHAT, not HOW STRICTLY)
    — a profile that disagrees with the contract on either is a structural conflict, not a
    tightening, and raises :class:`ProfileCompositionError` rather than silently picking one.
    """
    if existing.fact != addition.fact:
        raise ProfileCompositionError(
            f"tighten() called on two different facts: {existing.fact!r} vs {addition.fact!r}"
        )
    if existing.scope != addition.scope:
        raise ProfileCompositionError(
            f"profile requires {addition.fact!r} at scope {addition.scope!r}; the contract "
            f"already requires it at scope {existing.scope!r} — a profile may not change a "
            f"contract requirement's scope"
        )
    if (
        existing.value_type is not None
        and addition.value_type is not None
        and existing.value_type != addition.value_type
    ):
        raise ProfileCompositionError(
            f"profile requires {addition.fact!r} as {addition.value_type!r}; the contract "
            f"already requires it as {existing.value_type!r}"
        )

    max_age = existing.max_age_seconds
    if addition.max_age_seconds is not None:
        max_age = addition.max_age_seconds if max_age is None else min(max_age, addition.max_age_seconds)

    min_authority = existing.min_authority
    if _MIN_AUTHORITY_RANK.get(addition.min_authority, 0) > _MIN_AUTHORITY_RANK.get(min_authority, 0):
        min_authority = addition.min_authority

    on_missing = existing.on_missing
    if _ON_MISSING_STRICTNESS.get(addition.on_missing, 0) > _ON_MISSING_STRICTNESS.get(on_missing, 0):
        on_missing = addition.on_missing

    on_conflict = existing.on_conflict
    if _ON_CONFLICT_STRICTNESS.get(addition.on_conflict, 0) > _ON_CONFLICT_STRICTNESS.get(
        on_conflict, 0
    ):
        on_conflict = addition.on_conflict

    return replace(
        existing,
        max_age_seconds=max_age,
        min_authority=min_authority,
        on_missing=on_missing,
        on_conflict=on_conflict,
        value_type=existing.value_type or addition.value_type,
    )


def compose_requirements(
    contract: ContractLike,
    challenge: ChallengeProfile | None,
) -> tuple[FactRequirement, ...]:
    """Merge ``challenge``'s ``context_requirements`` into ``contract``'s ``requires_facts``,
    contract-wins (§2.3).

    The invariant this implements, in one sentence: a profile may ADD context a decision may see,
    but it may never RELAX what the contract requires and never ADMIT what the contract excludes.
    An absent/unknown profile (``challenge is None``) is a no-op — the contract alone governs
    (§2.4's own resolution step). Deliberately does NOT touch ``contract.invariants``: the
    contract's invariants remain the sole SAFETY gate (deviation D4) — this function only ever
    widens the "context a decision may see" set, and only within the bound :func:`tighten`
    enforces.
    """
    merged: dict[str, FactRequirement] = {r.fact: r for r in contract.requires_facts}
    if challenge is None:
        return tuple(merged.values())
    excluded = set(contract.excludes)
    for req in challenge.context_requirements:
        if req.fact in excluded:
            raise ProfileCompositionError(
                f"challenge profile {challenge.challenge!r} requires fact {req.fact!r}; "
                f"contract {contract.decision_type!r} excludes it"
            )
        if req.fact in merged:
            merged[req.fact] = tighten(merged[req.fact], req)
        else:
            merged[req.fact] = req
    return tuple(merged.values())


# ── §2.2 — persistence identity: profiles declared as POLICY facts ─
#
# The two predicates below (``domain_profile_version``/``challenge_profile_version``) are declared
# directly in ``control/facts.py``'s own ``FACT_PREDICATES`` literal (additive — the same "one new
# row" posture I9 uses for its own ``pattern`` predicate), NOT mutated into that dict from here:
# facts.py is I0's schema module and stays the single place a predicate is declared, so nothing
# else needs to import this module to discover what a fact predicate means.

# ── the ``profiles/v1`` reducer — the ONLY legitimate minter of the two predicates above ──

VERSION = "profiles/v1"

PROFILES_V1 = ReducerSpec(
    name="profiles",
    version=VERSION,
    level="policy",
    scope_type="workload",
    consumes=("profile",),  # the declared profile OBJECT itself — not a spec's L5 config
    produces=("domain_profile_version", "challenge_profile_version"),
    determinism="pure",
)

#: A profile declaration is a human/operator declaration — DECLARED (POLICY/[P]), exactly the
#: epistemic status ``policy_facts.py`` uses for the same reason.
_EPISTEMIC_STATUS = "declared"
_AUTHORITY, _EVIDENCE_CLASS = EPISTEMIC_MAP[_EPISTEMIC_STATUS]


def _profile_fact(inp: ReducerInput, *, subject_id: str, predicate: str, value: str) -> CanonicalFact:
    """Build one declared profile fact at workload scope ``subject_id`` (the domain/challenge
    name IS the scope: a profile is not bound to any one spec's workload, so it is its own)."""
    spec = FACT_PREDICATES[predicate]
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="workload",
            scope_id=subject_id,
            predicate=predicate,
            subject_type="policy",
            subject_id=subject_id,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="policy",
        subject_id=subject_id,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="workload",
        scope_id=subject_id,
        scope_path=f"org:{inp.repository_id}/workload:{subject_id}",
        abstraction_level=spec.abstraction_level,
        epistemic_status=_EPISTEMIC_STATUS,
        authority=_AUTHORITY,
        evidence_class=_EVIDENCE_CLASS,
        observed_at=inp.now,
        valid_from=inp.now,
        valid_to=None,
        expires_at=None,
        reducer="profiles",
        reducer_version=VERSION,
        evidence_ids=(),  # declared, not reduced from evidence
        inputs_digest="",  # back-filled below
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=inp.source_revision,
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def profiles_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit ``domain_profile_version``/``challenge_profile_version`` facts for every
    :class:`DomainProfile`/:class:`ChallengeProfile` in ``inp.evidence``.

    Pure and total, mirroring ``policy_facts_v1``: the same profile object always yields the
    byte-identical fact (same ``fact_entity_id``, same value), so re-declaring an unchanged
    profile is idempotent and re-declaring a bumped ``profile_version`` is a NEW value under the
    SAME ``fact_entity_id`` — a supersession, not a new slot (§2.2's "one record per (profile,
    version), not per (profile, predicate)" decision, expressed here as one SLOT per (kind, id)).
    """
    facts: list[CanonicalFact] = []
    for item in inp.evidence:
        if not isinstance(item, EvidenceItem):
            continue
        payload = item.payload
        if isinstance(payload, DomainProfile):
            facts.append(
                _profile_fact(
                    inp,
                    subject_id=payload.domain,
                    predicate="domain_profile_version",
                    value=payload.profile_version,
                )
            )
        elif isinstance(payload, ChallengeProfile):
            facts.append(
                _profile_fact(
                    inp,
                    subject_id=payload.challenge,
                    predicate="challenge_profile_version",
                    value=payload.profile_version,
                )
            )
    return facts


def declare_domain_profile(
    profile: DomainProfile, *, now: str, repository_id: str, source_revision: str = ""
) -> CanonicalFact:
    """Declare ``profile`` as a POLICY fact AT CONSTRUCTION — the ergonomic single-profile
    entrypoint over :func:`profiles_v1` (still going through the registered reducer; hard rule 3's
    "only a registered reducer mints a fact" discipline applies here exactly as it does to every
    other declared/derived fact in the plane)."""
    inp = ReducerInput(
        scope_path=f"org:{repository_id}/workload:{profile.domain}",
        scope_type="workload",
        scope_id=profile.domain,
        repository_id=repository_id,
        evidence=(
            EvidenceItem(
                source_type="profile",
                evidence_id=f"domain:{profile.domain}:{profile.profile_version}",
                payload=profile,
            ),
        ),
        facts=(),
        now=now,
        source_revision=source_revision,
    )
    return profiles_v1(inp)[0]


def declare_challenge_profile(
    profile: ChallengeProfile, *, now: str, repository_id: str, source_revision: str = ""
) -> CanonicalFact:
    """Declare ``profile`` as a POLICY fact AT CONSTRUCTION — see :func:`declare_domain_profile`."""
    inp = ReducerInput(
        scope_path=f"org:{repository_id}/workload:{profile.challenge}",
        scope_type="workload",
        scope_id=profile.challenge,
        repository_id=repository_id,
        evidence=(
            EvidenceItem(
                source_type="profile",
                evidence_id=f"challenge:{profile.challenge}:{profile.profile_version}",
                payload=profile,
            ),
        ),
        facts=(),
        now=now,
        source_revision=source_revision,
    )
    return profiles_v1(inp)[0]


# ── §6 — the PROFILES registry + the migration helper ────────────

DOMAIN_SOFTWARE_DELIVERY = DomainProfile(
    domain="software_delivery",
    profile_version="software_delivery/v1",
    canonical_sources=(
        "ARCHITECTURE.md",
        "agent_config/mental-model.md",
        "docs/designs/current/context_abstraction_design.md",
        "docs/designs/current/context_abstraction_addendum_design.md",
        "docs/context_abstraction/implementation_notes.md",
    ),
    predicates=(
        "spec_status",
        "workflow_health",
        "allowed_models",
        "max_spend_usd",
        "max_attempts",
        "domain_profile_version",
        "challenge_profile_version",
    ),
    policies=(
        "hard_rule_3_reducers_only",
        "contract_is_the_gate",
        "proposal_only_actuation",
        "apply_stays_off",
    ),
    patterns=(),  # I9 had not landed at I8 authorship time — no real pattern fact ids to cite yet
    verification=("pytest", "ruff", "mypy"),
)


def _seed_challenge_profile(challenge: str) -> ChallengeProfile:
    """Build the seed :class:`ChallengeProfile` for one archetype from :data:`DELIBERATION_STAGES`.

    ``context_requirements=()`` for every seeded archetype — an honest v1 baseline (§2.1's honesty
    rule): the composition MACHINERY (:func:`compose_requirements`) is fully implemented and
    tested, but no real decision-type contract yet names a fact this repository's challenge
    archetypes should add, so shipping a fabricated requirement here would be exactly the kind of
    claim this design forbids. A future profile author adds real entries as real contracts need
    them, superseding ``profile_version`` when they do (§2.2).
    """
    return ChallengeProfile(
        challenge=challenge,
        profile_version=f"challenge/{challenge}/v1",
        context_requirements=(),
        deliberation=DELIBERATION_STAGES[challenge],
        session_policy=SessionPolicy(policy="continue_default"),
        verification_policy=("pytest",),
    )


#: The profile registry (§6), keyed by ``(kind, id)`` — ``kind`` is ``"domain"`` or
#: ``"challenge"``. §2.4's compile-time resolution step ("resolve request.domain_id/challenge_id
#: against the profile registry by address") reads this dict; :func:`resolve_profile` is the typed
#: accessor.
PROFILES: dict[tuple[str, str], DomainProfile | ChallengeProfile] = {
    ("domain", DOMAIN_SOFTWARE_DELIVERY.domain): DOMAIN_SOFTWARE_DELIVERY,
    **{("challenge", c): _seed_challenge_profile(c) for c in DELIBERATION_STAGES},
}


def resolve_profile(kind: str, profile_id: str) -> DomainProfile | ChallengeProfile | None:
    """Look up :data:`PROFILES` by address. ``None`` (never a refusal) when unknown — §2.4's own
    resolution rule: "an absent/unknown profile is a no-op (the contract alone governs)"."""
    return PROFILES.get((kind, profile_id))


def migrate_static_filing(
    *, domain: str = "software_delivery", challenge: str
) -> tuple[DomainProfile | None, ChallengeProfile | None]:
    """Resolve the structured :data:`PROFILES` entries that supersede a workflow spec's free-text
    ``context.domain_context`` / ``context.challenge_context`` prose filing.

    See the module docstring's "MIGRATION" section for the full swap procedure and why the actual
    spec/runner rewiring is a deliberately separate, future change. This helper is the piece that
    change would call; it exists now so authoring it later is a wiring change, not a redesign.
    """
    return resolve_profile("domain", domain), resolve_profile("challenge", challenge)


__all__ = [
    "SessionPolicy",
    "DomainProfile",
    "ChallengeProfile",
    "DELIBERATION_STAGES",
    "CHALLENGES",
    "domain_profile_predicates_known",
    "ProfileCompositionError",
    "tighten",
    "compose_requirements",
    "PROFILES_V1",
    "profiles_v1",
    "declare_domain_profile",
    "declare_challenge_profile",
    "DOMAIN_SOFTWARE_DELIVERY",
    "PROFILES",
    "resolve_profile",
    "migrate_static_filing",
]
