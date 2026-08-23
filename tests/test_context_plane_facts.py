"""Tests for CAP I0 — the fact schema + predicate registry (``control/facts.py``).

Covers the frozen ``CanonicalFact`` schema, the closed predicate vocabulary
(``FACT_PREDICATES``, 16 seed rows from design §3.5), the single-discriminator epistemic
mapping (§3.4) and its ``is_canonical`` gate, the identity helpers (§3.1), the
derivation-chain validator ``verify_chain`` (§4.4), and — the plan's own CI-enforced
invariant (design §9 I0) — that the module has **zero call sites**: nothing imports
``control.facts`` except this test and the module itself, exactly as
``actuation_ingestion`` ships call-site-free (``actuation_ingestion.py:8-22``).
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from agentic_dynamics.control.facts import (
    ABSTRACTION_LEVELS,
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    SCOPE_TYPES,
    SUBJECT_TYPES,
    VALUE_TYPES,
    CanonicalFact,
    FactRef,
    ReducerSpec,
    Unknown,
    compute_fact_entity_id,
    fact_logical_locator,
    fact_source_uri,
    is_canonical,
    recompute_inputs_digest,
    verify_chain,
)
from agentic_dynamics.knowledge.knowledge import (
    ACTUATION_TYPES,
    OBSERVATION_TYPES,
    SOURCE_TYPES,
    Authority,
    compute_entity_id,
    message_family,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FACTS_MODULE = REPO_ROOT / "src" / "agentic_dynamics" / "control" / "facts.py"

#: The reducer a well-formed fixture fact is produced by. Mirrors the design's §3.5 rows
#: (``workflow_facts/v1`` emits the three ``workflow_*`` predicates at ``workflow`` level).
WORKFLOW_FACTS_V1 = ReducerSpec(
    name="workflow_facts",
    version="workflow_facts/v1",
    level="workflow",
    scope_type="workflow",
    consumes=("ledger_attempt", "phase_status"),
    produces=(
        "workflow_phases_completed",
        "workflow_phases_remaining",
        "workflow_status",
    ),
)


def _registry() -> dict[str, ReducerSpec]:
    """A minimal reducers registry keyed by ``reducer_version`` (the ``REDUCERS`` shape, I1–I3)."""
    return {"workflow_facts/v1": WORKFLOW_FACTS_V1}


def _fact(**overrides) -> CanonicalFact:
    """Build a valid, self-consistent derived ``workflow_phases_completed`` fact.

    ``inputs_digest`` is recomputed from the fact's own derivation inputs unless the caller
    supplies one explicitly, so ``verify_chain``'s digest check passes by default and a test
    that wants a *tampered* digest passes ``inputs_digest="wrong"``.
    """
    base = {
        "fact_entity_id": "entity_wf_phases_completed",
        "fact_id": "fact_0001",
        "subject_type": "workflow",
        "subject_id": "wf_demo",
        "predicate": "workflow_phases_completed",
        "value": "2",
        "value_type": "int",
        "unit": "",
        "scope_type": "workflow",
        "scope_id": "wf_demo",
        "scope_path": "org:agentic-dynamics/workload:demo/workflow:wf_demo",
        "abstraction_level": "workflow",
        "epistemic_status": "derived",
        "authority": Authority.DERIVED,
        "evidence_class": "[C]",
        "observed_at": "2026-08-22T00:00:00+00:00",
        "valid_from": "2026-08-22T00:00:00+00:00",
        "valid_to": None,
        "expires_at": None,
        "reducer": "workflow_facts",
        "reducer_version": "workflow_facts/v1",
        "evidence_ids": ("ledger_attempt_0001",),
        "inputs_digest": "",
        "supersedes": None,
        "source_revision": "abc123",
        "repository_id": "agentic-dynamics",
        "lifecycle_state": "current",
    }
    base.update(overrides)
    fact = CanonicalFact(**base)
    if "inputs_digest" not in overrides:
        fact = replace(fact, inputs_digest=recompute_inputs_digest(fact))
    return fact


# ── CanonicalFact schema (§3.1) ─────────────────────────────────


def test_canonical_fact_is_frozen():
    fact = _fact()
    with pytest.raises(FrozenInstanceError):
        fact.value = "3"  # type: ignore[misc]


def test_canonical_fact_defaults_unit_and_lifecycle_state():
    fact = _fact()
    assert fact.unit == ""
    assert fact.lifecycle_state == "current"


def test_canonical_fact_evidence_ids_are_a_tuple():
    # The derivation chain must be an ordered, immutable sequence, never a mutable list.
    assert isinstance(_fact().evidence_ids, tuple)


def test_canonical_fact_requires_the_identity_and_statement_fields():
    # kw_only construction: omitting any required field is a loud TypeError, not a silent
    # default. A fact with no value, no scope, or no reducer is unrepresentable.
    with pytest.raises(TypeError):
        CanonicalFact(fact_id="x")  # type: ignore[call-arg]


# ── Closed vocabularies ─────────────────────────────────────────


def test_closed_vocabularies_cover_the_design_axes():
    assert {"observed", "verified", "derived", "declared", "advisory"} <= set(EPISTEMIC_MAP)
    assert {"fact", "job", "workflow", "workload", "policy"} <= ABSTRACTION_LEVELS
    assert {"spec", "job", "attempt", "workflow", "policy"} <= SUBJECT_TYPES
    assert {"workload", "workflow", "job", "attempt", "resource"} <= SCOPE_TYPES


def test_value_types_cover_every_seed_predicate():
    for spec in FACT_PREDICATES.values():
        assert spec.value_type in VALUE_TYPES, (
            f"{spec.name} has unknown value_type {spec.value_type!r}"
        )


# ── Epistemics (§3.4) ───────────────────────────────────────────


def test_epistemic_map_derives_authority_and_evidence_class():
    assert EPISTEMIC_MAP == {
        "observed": (Authority.MEASURED, "[M]"),
        "verified": (Authority.MEASURED, "[M]"),
        "derived": (Authority.DERIVED, "[C]"),
        "declared": (Authority.POLICY, "[P]"),
        "advisory": (Authority.ADVISORY, "[H]"),
    }


def test_is_canonical_admits_non_advisory_current_facts():
    assert is_canonical(_fact())  # derived / DERIVED / current
    assert is_canonical(
        _fact(epistemic_status="declared", authority=Authority.POLICY, evidence_class="[P]")
    )
    assert is_canonical(
        _fact(epistemic_status="observed", authority=Authority.MEASURED, evidence_class="[M]")
    )


def test_is_canonical_excludes_advisory():
    assert not is_canonical(
        _fact(epistemic_status="advisory", authority=Authority.ADVISORY, evidence_class="[H]")
    )


def test_is_canonical_excludes_non_current_lifecycle():
    assert not is_canonical(_fact(lifecycle_state="superseded"))
    assert not is_canonical(_fact(lifecycle_state="tombstoned"))


# ── Identity helpers (§3.1, §3.3) ───────────────────────────────


def test_fact_locators_follow_the_design_forms():
    assert fact_source_uri("workflow", "wf_demo", "workflow_status") == (
        "fact://workflow/wf_demo/workflow_status"
    )
    assert fact_logical_locator("workflow", "wf_demo", "workflow_status") == (
        "workflow:wf_demo#workflow_status"
    )


def test_compute_fact_entity_id_reuses_the_existing_identity_algorithm():
    # The plane adds no second identity algorithm: it is the EXISTING compute_entity_id over
    # the fact's source_uri + logical_locator (design §3.1).
    expected = compute_entity_id(
        "agentic-dynamics",
        fact_source_uri("workflow", "wf_demo", "workflow_status"),
        fact_logical_locator("workflow", "wf_demo", "workflow_status"),
    )
    assert (
        compute_fact_entity_id(
            repository_id="agentic-dynamics",
            scope_type="workflow",
            scope_id="wf_demo",
            predicate="workflow_status",
            subject_type="workflow",
            subject_id="wf_demo",
        )
        == expected
    )


def test_compute_fact_entity_id_is_time_invariant():
    # Keyed by (scope, subject, predicate) — never by time — so re-deriving the same slot at a
    # different moment yields the SAME entity_id (the version chain, not an event stream).
    a = compute_fact_entity_id(
        repository_id="agentic-dynamics",
        scope_type="job",
        scope_id="self-wt_03",
        predicate="current_commit",
        subject_type="job",
        subject_id="self-wt_03",
    )
    b = compute_fact_entity_id(
        repository_id="agentic-dynamics",
        scope_type="job",
        scope_id="self-wt_03",
        predicate="current_commit",
        subject_type="job",
        subject_id="self-wt_03",
    )
    assert a == b


# ── FACT_PREDICATES registry (§3.5) ─────────────────────────────


def test_predicate_registry_has_the_design_seed_rows():
    assert set(FACT_PREDICATES) == {
        "spec_status",
        "spec_superseded_by",
        "spec_supersedes",
        "spec_last_run_at",
        "spec_latest_ok",
        "spec_latest_model",
        "spec_latest_cost_usd",
        "spec_n_runs",
        "current_commit",
        "phase_status",
        "phase_test_verified",
        "attempt_cost_usd",
        "attempt_tokens_out",
        "attempt_tokens_in",
        "attempt_model",
        "phase_commit",
        "attempt_cache_hit_rate",
        "attempt_confidence",
        "job_accumulated_cost_usd",
        "job_status",
        "job_n_phases",
        "workflow_phases_completed",
        "workflow_phases_remaining",
        "workflow_status",
        "workflow_health",
        "projected_budget_overrun",
        "allowed_models",
        "max_spend_usd",
        "max_attempts",
    }


def test_every_predicate_names_a_producer():
    # NON-EMPTY produced_by is the invariant that makes "declared but written by nothing"
    # impossible to represent here (design §3.5) — the review's LEDGER_FIELDS failure (§3d(ii)).
    for name, spec in FACT_PREDICATES.items():
        assert spec.produced_by, f"predicate {name!r} has no producing reducer"
        assert isinstance(spec.produced_by, tuple)


def test_predicate_axes_stay_within_the_closed_vocabularies():
    for name, spec in FACT_PREDICATES.items():
        assert spec.value_type in VALUE_TYPES, name
        assert spec.abstraction_level in ABSTRACTION_LEVELS, name
        assert spec.subject_type in SUBJECT_TYPES, name
        assert spec.scope_type in SCOPE_TYPES, name


def test_predicate_inheritance_flags_match_the_design_table():
    inheritable = {name for name, spec in FACT_PREDICATES.items() if spec.inheritable}
    assert inheritable == {
        "spec_status",
        "spec_superseded_by",
        "spec_supersedes",
        "spec_last_run_at",
        "spec_latest_ok",
        "spec_latest_model",
        "spec_latest_cost_usd",
        "spec_n_runs",
        "allowed_models",
        "max_spend_usd",
        "max_attempts",
    }
    # Only the workflow aggregates declare ``aggregates_from`` (the legal upward roll-up path,
    # §10.2.3); every other predicate defaults it to "" (no implicit upward rollup).
    aggregated = {
        name: spec.aggregates_from for name, spec in FACT_PREDICATES.items() if spec.aggregates_from
    }
    assert aggregated == {
        "workflow_phases_completed": "phase_status",
        "workflow_phases_remaining": "phase_status",
        "workflow_status": "job_status",
        "workflow_health": "job_status",
        "projected_budget_overrun": "job_accumulated_cost_usd",
    }
    for spec in FACT_PREDICATES.values():
        assert spec.default_ttl_seconds is None
        assert spec.volatile is False


def test_predicate_spec_is_frozen():
    spec = FACT_PREDICATES["allowed_models"]
    with pytest.raises(FrozenInstanceError):
        spec.inheritable = False  # type: ignore[misc]


# ── verify_chain (§4.4) ─────────────────────────────────────────


def test_verify_chain_accepts_a_valid_fact():
    assert verify_chain(_fact(), _registry()) == []


def test_verify_chain_refuses_an_unregistered_reducer():
    fact = _fact(reducer_version="ghost/v1")
    errors = verify_chain(fact, _registry())
    assert any("not registered" in e for e in errors)


def test_verify_chain_refuses_a_tampered_digest():
    fact = _fact(inputs_digest="deadbeef")
    errors = verify_chain(fact, _registry())
    assert any("inputs_digest mismatch" in e for e in errors)


def test_verify_chain_refuses_a_predicate_the_reducer_does_not_produce():
    fact = _fact(predicate="allowed_models", subject_type="policy", value_type="enum-list")
    errors = verify_chain(fact, _registry())
    assert any("does not declare" in e for e in errors)


def test_verify_chain_refuses_a_level_mismatch():
    fact = _fact(abstraction_level="job")
    errors = verify_chain(fact, _registry())
    assert any("level" in e and "!=" in e for e in errors)


def test_verify_chain_refuses_an_epistemic_mismatch():
    # authority/evidence_class must be a pure function of epistemic_status (§3.4); a fact that
    # carries a MEASURED authority under a `derived` status is internally inconsistent.
    fact = _fact(epistemic_status="derived", authority=Authority.MEASURED, evidence_class="[M]")
    errors = verify_chain(fact, _registry())
    assert any("contradict epistemic_status" in e for e in errors)


def test_verify_chain_resolves_evidence_ids_when_given_a_resolver():
    def resolve(eid: str) -> object | None:
        return None if eid == "dangling_0001" else eid

    assert verify_chain(_fact(), _registry(), resolve=resolve) == []
    fact = _fact(evidence_ids=("dangling_0001",))
    errors = verify_chain(fact, _registry(), resolve=resolve)
    assert any("does not resolve" in e for e in errors)


def test_verify_chain_reports_every_problem_not_just_the_first():
    fact = _fact(
        reducer_version="ghost/v1",
        predicate="allowed_models",
        inputs_digest="tampered",
        epistemic_status="derived",
        authority=Authority.MEASURED,
        evidence_class="[M]",
    )
    errors = verify_chain(fact, _registry())
    assert len(errors) >= 3


# ── FactRef / Unknown (§6.3) ────────────────────────────────────


def test_fact_ref_and_unknown_are_frozen_value_objects():
    ref = FactRef(
        fact_id="fact_0001",
        predicate="workflow_status",
        subject_id="wf_demo",
        scope_path="org:agentic-dynamics/workload:demo/workflow:wf_demo",
        value="ok",
        value_type="enum",
        authority="DERIVED",
        epistemic_status="derived",
        observed_at="2026-08-22T00:00:00+00:00",
        age_seconds=0,
        reducer_version="workflow_facts/v1",
        evidence_ids=("ledger_attempt_0001",),
    )
    unknown = Unknown(
        predicate="workflow_status", scope="workflow", reason="no_fact", handling="halt"
    )
    with pytest.raises(FrozenInstanceError):
        ref.value = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        unknown.reason = "broken_chain"  # type: ignore[misc]


# ── source_type="fact" registration (design §3.3) ───────────────


def test_fact_is_registered_as_an_observation_source_type():
    assert "fact" in SOURCE_TYPES
    assert message_family("fact") == "observation"
    assert "fact" in OBSERVATION_TYPES
    assert "fact" not in ACTUATION_TYPES


# ── CI-enforced invariant: only authorized callers import the schema ──

#: The unambiguous public names this module exports. A bare reference to any of these outside
#: ``facts.py`` (and its test) is a call site the gate below must account for.
PUBLIC_NAMES = frozenset({"CanonicalFact", "FACT_PREDICATES", "EPISTEMIC_MAP", "verify_chain"})

#: The exact call sites CAP I1/I4/I6 authorize — the fact-ingestion mapping, the batch
#: producer, (I4) the read-only Context Compiler, which resolves ``FACT_PREDICATES``/
#: ``FactRef``/``Unknown``/``Conflict``/``StaleFact`` into a ``ControlContext`` snapshot, and
#: (I6) the shadow controller rule + validator, which cite ``FactRef``/``verify_chain`` while
#: proposing and admitting decisions. I0 had none (the zero-call-sites gate); each increment
#: widens this allowlist explicitly, never silently.
LEGITIMATE_CALLERS = frozenset(
    {
        "src/agentic_dynamics/control/fact_ingestion.py",
        "scripts/kb_produce_facts.py",
        "src/agentic_dynamics/control/context_compiler.py",
        "src/agentic_dynamics/control/rules.py",
        "src/agentic_dynamics/control/validator.py",
    }
)

#: The reducer package (I1–I3) is the schema's first producer and is authorized wholesale; it
#: will grow with I2/I3, so it is a directory prefix rather than a per-file allowlist.
LEGITIMATE_DIRS = ("src/agentic_dynamics/control/reducers/",)


def _references_facts_module(path: Path) -> bool:
    """Return True if ``path`` imports the ``facts`` module or references a core public name."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "facts" or alias.name.endswith(".facts"):
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "facts" or mod.endswith(".facts"):
                return True
            for alias in node.names:
                if alias.name == "facts":
                    return True
        elif (
            isinstance(node, ast.Name)
            and node.id in PUBLIC_NAMES
            or isinstance(node, ast.Attribute)
            and node.attr in PUBLIC_NAMES
        ):
            return True
    return False


def _legitimate(rel: str) -> bool:
    """True when ``rel`` is one of the call sites the current increment authorizes."""
    return rel in LEGITIMATE_CALLERS or any(rel.startswith(prefix) for prefix in LEGITIMATE_DIRS)


def test_only_authorized_callers_import_the_facts_module():
    # design §9: the fact schema gains call sites one increment at a time. I0 shipped with ZERO
    # (the schema exercised in tests only, exactly as actuation_ingestion ships call-site-free);
    # I1 authorizes the reducer package (the first producer), the fact-ingestion mapping, and the
    # batch producer. Anything else — especially a ``knowledge`` module or a controller — that
    # imports the schema is a design violation: facts must not reach retrieval or a control rule
    # before a declared producer exists.
    scan_roots = [REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "apps"]
    offenders = []
    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path.resolve() == FACTS_MODULE.resolve():
                continue
            if _references_facts_module(path):
                rel = str(path.relative_to(REPO_ROOT))
                if not _legitimate(rel):
                    offenders.append(rel)
    assert offenders == [], f"unauthorized facts module call site(s): {offenders}"
