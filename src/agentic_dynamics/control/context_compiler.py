"""CAP I4 — the Context Compiler (read-only): contract + scope → ``ControlContext`` snapshot.

This is the "abstract" rung of the design's loop (§2 stage 3): it turns a decision-type
*contract* (``experiments/contexts/<decision_type>.yaml``, §6.1) plus a scope address into a
frozen, content-addressed snapshot of exactly the facts that decision type is allowed to see —
never more (design's thesis, commitment 3: "a controller never queries the fact store"). Nothing
in the running system yet CONSUMES a compiled ``ControlContext`` (I6 does); this module ships so
the snapshot machinery is exercised — and, once wired at the composition root, measured over a
real campaign — before anything decides anything from it (design §9 I4 row).

Two things this module deliberately does NOT do, because the design places them elsewhere:

* It never queries ``knowledge.retrieval`` or ``knowledge.prompt_constructor`` — those serve the
  *executor* prompt (relevance ranking), not a controller (truth resolution). Importing either
  here would be exactly the leak §11.2 forbids, and ``tests/test_dependency_direction.py``
  (``test_control_does_not_import_retrieval_or_prompt_constructor``) enforces it structurally.
* It never modifies ``control.step_routing.route_step`` — the reference control rule stays the
  measurement baseline (design §8.4). The snapshot-recording seam (:func:`make_snapshotting_router`)
  *wraps* it; it is a drop-in :class:`~agentic_dynamics.runtime.routing.Router`, injected at the
  composition root (``scripts/run_workflow.py``) exactly where ``route_step`` is injected today —
  ``runtime.workflow_runner`` still never imports ``control`` (Debt-2 is preserved).

Read this alongside ``core.contracts`` (:class:`~agentic_dynamics.core.contracts.FactRequirement`,
introduced there because it is I5's reserved home and the shape is shared with the compile-time
gate) and ``control.facts`` (the schema this module resolves against: ``FACT_PREDICATES``,
``FactRef``/``Unknown``/``Conflict``/``StaleFact``, ``verify_chain``, ``fact_state``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import yaml

from agentic_dynamics.control.facts import (
    FACT_PREDICATES,
    CanonicalFact,
    Conflict,
    FactRef,
    PredicateSpec,
    StaleFact,
    Unknown,
    fact_state,
    verify_chain,
)
from agentic_dynamics.control.profiles import ChallengeProfile, DomainProfile, compose_requirements
from agentic_dynamics.control.reducers import REDUCERS
from agentic_dynamics.core.contracts import (
    FactRequirement,
    normalize_requirement,
)
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR, PROJECT_ROOT, REGISTRY_INDEX_PATH
from agentic_dynamics.knowledge.knowledge import (
    Authority,
    KnowledgeRecord,
)
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID, record_to_event
from agentic_dynamics.knowledge.record_factory import (
    build_record as build_record_from_parts,
)
from agentic_dynamics.knowledge.spec_ingestion import registry_head
from agentic_dynamics.runtime.routing import Objective

# ── The one additive SOURCE_TYPES row this increment registers ──
#
# Design §8.5: "every compiled ControlContext is persisted as an observation-family record so a
# ControlDecision's single-valued `causes` can point at it." Registration, not redesign — the
# exact same additive pattern I0 used for `source_type="fact"`. Kept here (not knowledge.py's
# own docstring block) because it is this module's only knowledge.py touch; see
# ``knowledge.SOURCE_TYPES`` for the actual registration.
SNAPSHOT_SOURCE_TYPE = "context_snapshot"

#: Where decision-type contracts live (design §6.1). A contract is reusable across specs; a
#: ``RuleSpec.requires_facts`` (I5, ``core.contracts``) is the per-spec binding to one.
CONTRACTS_DIR = PROJECT_ROOT / "experiments" / "contexts"

#: Fallback ``source_revision`` for a snapshot compiled outside a specific commit (mirrors
#: ``reducers._common.REVISION_FALLBACK``'s posture: pin to the artifact kind, never fabricate).
REVISION_FALLBACK = "context_snapshot/unrevisioned"

EXTRACTOR_VERSION = "context_snapshot/v1"


def _now_iso(now: datetime | None = None) -> str:
    """Injected-clock timestamp (mirrors ``record_factory._now_iso`` — tests pin it)."""
    return (now or datetime.now(timezone.utc)).isoformat()


# ── The decision-type contract (design §6.1) ─────────────────────


@dataclass(frozen=True)
class ContractSpec:
    """One decision type's declared needs — loaded from ``experiments/contexts/<name>.yaml``.

    Reusable across specs (many specs route steps); a spec's ``RuleSpec.requires_facts`` (I5) is
    the narrower per-spec binding *to* one of these, never a second copy of it.
    """

    decision_type: str
    contract_version: str
    decision_scope: str  # the scope_type this decision is made at
    allowed_actions: tuple[str, ...]
    max_snapshot_age_seconds: int | None
    invariants: tuple[FactRequirement, ...]
    objectives: tuple[Objective, ...]
    requires_facts: tuple[FactRequirement, ...]
    excludes: tuple[str, ...]

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ContractSpec:
        missing = [k for k in ("decision_type", "contract_version") if k not in d]
        if missing:
            raise ValueError(f"context contract missing required field(s): {missing}")
        return cls(
            decision_type=str(d["decision_type"]),
            contract_version=str(d["contract_version"]),
            decision_scope=str(d.get("decision_scope", "job")),
            allowed_actions=tuple(str(a) for a in d.get("allowed_actions", []) or []),
            max_snapshot_age_seconds=d.get("max_snapshot_age_seconds"),
            invariants=tuple(
                normalize_requirement(e) for e in d.get("invariants", []) or []
            ),
            objectives=tuple(Objective.from_dict(o) for o in d.get("objectives", []) or []),
            requires_facts=tuple(
                normalize_requirement(e) for e in d.get("requires_facts", []) or []
            ),
            excludes=tuple(str(e) for e in d.get("excludes", []) or []),
        )


def load_contract(decision_type: str, *, contracts_dir: Path = CONTRACTS_DIR) -> ContractSpec:
    """Load and parse the contract for ``decision_type``. Raises ``ValueError`` when absent or
    when its ``decision_type`` field disagrees with the requested one (a copy/rename mistake)."""
    path = contracts_dir / f"{decision_type}.yaml"
    if not path.is_file():
        raise ValueError(
            f"no context contract for decision_type {decision_type!r} at {path} "
            f"(design R9: a control rule's decision_type must name a committed contract)"
        )
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    contract = ContractSpec.from_dict(raw)
    if contract.decision_type != decision_type:
        raise ValueError(
            f"contract at {path} declares decision_type {contract.decision_type!r}, "
            f"expected {decision_type!r}"
        )
    return contract


# ── Scope addressing + visibility (design §10) ───────────────────

#: The ancestry spine, root to leaf. ``resource`` is orthogonal (§10.1) and never appears in a
#: scope_path segment order check, so it is deliberately excluded from this list.
SCOPE_ORDER: tuple[str, ...] = ("organization", "program", "workload", "workflow", "job", "attempt")


def parse_scope_path(scope_path: str) -> list[tuple[str, str]]:
    """Parse ``org:r/workload:s/job:c`` into ``[(scope_type, id), ...]``, root to leaf."""
    out: list[tuple[str, str]] = []
    for seg in scope_path.split("/"):
        if ":" in seg:
            k, _, v = seg.partition(":")
            out.append((k, v))
    return out


def _parent_scope_path(segments: list[tuple[str, str]]) -> str | None:
    """The scope one rung up the abstraction ladder from ``segments``' leaf (design §10.1) —
    NOT simply "drop the last path segment".

    Reconciliation with the ACTUAL reducer-produced scope_paths (``control/reducers/*.py``),
    documented here because it is a genuine deviation from §10.1's idealized single-chain
    grammar (``org/.../workload/.../workflow/.../job/.../attempt``): the reducers make
    ``job``/``workflow`` SIBLING labels over the SAME cell id directly under ``workload``, not a
    nested pair (``job_facts.py``: ``workload:<w>/job:<cell>``; ``workflow_facts.py``:
    ``workload:<w>/workflow:<cell>`` — same ``<cell>``, different label, same depth), and nest
    ``attempt`` TWO segments under ``job`` (``job:<cell>/attempt:<phase>/run:<run_id>``, not
    one). So: an attempt (or its ``run:`` sibling segment)'s parent is its owning JOB (same
    cell, dropping ``attempt``+``run``); a job's parent is the WORKFLOW view of the SAME cell
    (design §10.3: "job scope = the workflow-level view of the cell, one rung up the ladder" —
    same id, swapped label, not a dropped segment); a workflow's parent is its workload; a
    workload's parent is its organization (or ``None`` at the root).
    """
    if not segments:
        return None
    if segments[-1][0] == "run":
        segments = segments[:-1]  # the attempt_facts.py "attempt:<phase>/run:<id>" pair
    leaf_type, leaf_id = segments[-1]
    if leaf_type == "attempt":
        return "/".join(f"{k}:{v}" for k, v in segments[:-1])
    if leaf_type == "job":
        return "/".join(f"{k}:{v}" for k, v in segments[:-1]) + f"/workflow:{leaf_id}"
    if len(segments) <= 1:
        return None
    return "/".join(f"{k}:{v}" for k, v in segments[:-1])


def resolve_requirement_scope(requirement_scope: str, decision_scope_path: str) -> str | None:
    """Resolve a :class:`FactRequirement`'s ``scope`` keyword against the decision's own
    scope_path, into the scope_path a matching fact is expected to carry.

    ``self`` is the decision's own path verbatim. ``parent`` is :func:`_parent_scope_path`
    (one rung up the abstraction ladder — NOT a literal path-segment drop, see its docstring).
    An explicit scope_type keyword (``workload``, ``organization``, ...) truncates the path AT
    that segment — the ancestor address a policy/aggregate fact at that level is expected to
    carry. ``None`` when the decision's own path never reaches that scope_type (out of scope —
    design R4's runtime twin).
    """
    segments = parse_scope_path(decision_scope_path)
    if requirement_scope == "self":
        return decision_scope_path
    if requirement_scope == "parent":
        return _parent_scope_path(segments)
    for i, (k, _v) in enumerate(segments):
        if k == requirement_scope:
            return "/".join(f"{k2}:{v2}" for k2, v2 in segments[: i + 1])
    return None


def _is_ancestor(ancestor: str, path: str) -> bool:
    """True when ``ancestor`` is ``path`` itself or a proper scope-path prefix of it."""
    return path == ancestor or path.startswith(ancestor + "/")


def scope_visible(
    requested_scope_path: str,
    fact_scope_path: str,
    predicate: PredicateSpec | None = None,
) -> bool:
    """Can a decision at ``requested_scope_path`` see a fact declared at ``fact_scope_path``?

    THE HIERARCHICAL GENERALIZATION of ``retrieval.scope_excluded`` (design §10.2): equality
    becomes ancestor-prefix, and nothing else changes.

    * equal scope                       -> visible (own facts).
    * ``fact_scope_path`` is an ANCESTOR of the request -> visible IFF the predicate is
      ``inheritable`` or its ``abstraction_level`` is ``"policy"`` (downward flow only).
    * the request is an ancestor of ``fact_scope_path`` (a descendant peek) -> NOT visible —
      aggregates must come through a declared reducer, never an implicit rollup.
    * neither is a prefix of the other (lateral) -> NOT visible.

    The empty-scope semantics are preserved EXACTLY as ``retrieval.py`` defines them: an empty
    scope is never a wildcard, on either side.
    """
    if not requested_scope_path or not fact_scope_path:
        return False
    if requested_scope_path == fact_scope_path:
        return True
    if _is_ancestor(fact_scope_path, requested_scope_path):
        return predicate is not None and (
            predicate.inheritable or predicate.abstraction_level == "policy"
        )
    return False  # descendant peek or lateral — both forbidden


# ── The FactStore seam ───────────────────────────────────────────


class FactStore(Protocol):
    """Everything the compiler needs to resolve facts. Deliberately narrow (mirrors
    :class:`~agentic_dynamics.control.facts.ReducerInput`'s "no I/O inside the pure part"
    discipline, one layer up): the compiler itself does no I/O, so any store — in-memory
    fixtures for tests, or a real registry reader for production — can back it.
    """

    def current_facts(self, predicate: str) -> tuple[CanonicalFact, ...]:
        """Every fact for ``predicate`` whose OWN ``lifecycle_state`` is ``"current"``, across
        every scope (predicate cardinality is small; the compiler filters by scope itself)."""
        ...

    def resolve(self, fact_id: str) -> Mapping[str, Any] | None:
        """A minimal registry row for ``fact_id`` (at least ``lifecycle_state``), or ``None``
        when it does not resolve — the ``verify_chain``/``fact_state`` resolver contract."""
        ...

    def current_versions(self, fact_entity_id: str) -> tuple[Mapping[str, Any], ...] | None:
        """Every CURRENT registry row sharing ``fact_entity_id`` (the §4.5 conflict check), or
        ``None`` to skip the check (a store with no cross-entity index)."""
        ...


@dataclass
class InMemoryFactStore:
    """A :class:`FactStore` over an explicit fact list — the fixture every test uses, and a
    ready-made store for any in-process caller that already holds finalized facts (e.g. right
    after running a reducer batch in the same process, before anything hits the registry)."""

    facts: tuple[CanonicalFact, ...] = ()

    def current_facts(self, predicate: str) -> tuple[CanonicalFact, ...]:
        return tuple(
            f for f in self.facts if f.predicate == predicate and f.lifecycle_state == "current"
        )

    def resolve(self, fact_id: str) -> Mapping[str, Any] | None:
        for f in self.facts:
            if f.fact_id == fact_id:
                return {"knowledge_id": f.fact_id, "lifecycle_state": f.lifecycle_state}
        return None

    def current_versions(self, fact_entity_id: str) -> tuple[Mapping[str, Any], ...] | None:
        rows = [
            {"knowledge_id": f.fact_id, "lifecycle_state": f.lifecycle_state}
            for f in self.facts
            if f.fact_entity_id == fact_entity_id
        ]
        return tuple(rows) if rows else None


#: Reverse of ``facts.EPISTEMIC_MAP`` for the (authority, evidence_class) pairs that resolve to
#: exactly one ``epistemic_status`` (registry rows carry authority/evidence_class, not the
#: status itself). ``(MEASURED, "[M]")`` is genuinely ambiguous between "observed" and
#: "verified" — :class:`RegistryFactStore` documents the tie-break it takes (§ its own
#: docstring): a known, honest simplification of a read-only reconstruction path, not a
#: correctness requirement (nothing downstream branches on "observed" vs "verified").
_UNAMBIGUOUS_EPISTEMIC_REVERSE: dict[tuple[Authority, str], str] = {
    (Authority.DERIVED, "[C]"): "derived",
    (Authority.POLICY, "[P]"): "declared",
    (Authority.ADVISORY, "[H]"): "advisory",
}


@dataclass
class RegistryFactStore:
    """A :class:`FactStore` reading the REAL knowledge plane — DB 2's durable artifacts, never
    DB 1 telemetry (design §10.4's hard rule). No new transport: this is a read-only client of
    the exact pipe ``fact_ingestion``/``kb_produce_facts.py`` already write through —
    ``registry_index.jsonl`` (via the SAME ``spec_ingestion.registry_head`` head-resolution
    ``fact_ingestion.derive_fact_records`` uses to decide supersession) for identity/lifecycle,
    and ``KB_ARTIFACT_DIR/<knowledge_id>.json`` (the durable per-record artifact
    ``record_to_artifact`` produces) for the payload.

    Deliberately scoped to ``current_facts(predicate)`` returning at most a handful of rows: it
    resolves every ``FACT_PREDICATES`` entry whose ``subject_type``/``scope_type`` conventionally
    sets ``subject_id == scope_id`` (true of every I1–I3 reducer — see their module docstrings),
    by re-deriving each candidate scope's ``fact_entity_id`` from the registry's own indexed rows
    rather than scanning the whole file per query — see :meth:`_candidate_entity_ids`.
    """

    repository_id: str = REPOSITORY_ID
    registry_path: Path = REGISTRY_INDEX_PATH
    artifact_dir: Path = KB_ARTIFACT_DIR

    def _read_artifact(self, knowledge_id: str) -> dict[str, Any] | None:
        path = self.artifact_dir / f"{knowledge_id}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def _candidate_entity_ids(self, predicate: str) -> set[str]:
        """Every distinct ``entity_id`` on disk whose registered ``logical_locator`` ends in
        ``#<predicate>`` for a fact record — a single linear scan of the append-only index
        (mirrors ``_iter_registry_rows``' own graceful-skip-on-corruption posture)."""
        ids: set[str] = set()
        if not self.registry_path.exists():
            return ids
        suffix = f"#{predicate}"
        with open(self.registry_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("source_type") != "fact":
                    continue
                locator = str(row.get("logical_locator") or "")
                if locator.endswith(suffix) and row.get("entity_id"):
                    ids.add(row["entity_id"])
        return ids

    def _fact_from_head(self, entity_id: str) -> CanonicalFact | None:
        head = registry_head(
            entity_id, registry_path=self.registry_path, reason_prefix="fact-content="
        )
        if head is None:
            return None
        artifact = self._read_artifact(head.knowledge_id)
        if artifact is None:
            return None
        try:
            payload = json.loads(artifact.get("text") or "{}")
        except json.JSONDecodeError:
            return None
        authority_name = artifact.get("authority")
        try:
            authority = Authority[authority_name] if authority_name else Authority.DERIVED
        except KeyError:
            authority = Authority.DERIVED
        evidence_class = str(artifact.get("evidence_class") or "[C]")
        epistemic_status = _UNAMBIGUOUS_EPISTEMIC_REVERSE.get(
            (authority, evidence_class), "observed"
        )
        predicate = str(payload.get("predicate", ""))
        scope_path = str(payload.get("scope_path", ""))
        # The predicate's OWN declared scope_type (FACT_PREDICATES) is authoritative — never
        # "the last path segment", which would misread e.g. an attempt fact's trailing
        # `run:<id>` segment (attempt_facts.py's convention) as scope_type "run".
        predicate_spec = FACT_PREDICATES.get(predicate)
        scope_type = predicate_spec.scope_type if predicate_spec else ""
        scope_id = ""
        for seg_type, seg_id in parse_scope_path(scope_path):
            if seg_type == scope_type:
                scope_id = seg_id
        return CanonicalFact(
            fact_entity_id=entity_id,
            fact_id=head.knowledge_id,
            subject_type=str(payload.get("subject_type", "")),
            subject_id=str(payload.get("subject_id", "")),
            predicate=predicate,
            value=str(payload.get("value", "")),
            value_type=str(payload.get("value_type", "str")),
            unit=str(payload.get("unit", "")),
            scope_type=scope_type,
            scope_id=scope_id,
            scope_path=scope_path,
            abstraction_level=str(payload.get("abstraction_level", "fact")),
            epistemic_status=epistemic_status,
            authority=authority,
            evidence_class=evidence_class,
            observed_at=str(artifact.get("observed_at") or ""),
            valid_from=str(artifact.get("valid_from") or ""),
            valid_to=artifact.get("valid_to"),
            expires_at=payload.get("expires_at"),
            reducer=str(payload.get("reducer_version", "")).split("/")[0],
            reducer_version=str(payload.get("reducer_version", "")),
            evidence_ids=tuple(payload.get("evidence_ids") or ()),
            inputs_digest=str(payload.get("inputs_digest", "")),
            supersedes=artifact.get("supersedes"),
            source_revision=str(artifact.get("commit_sha") or ""),
            repository_id=str(artifact.get("repository_id") or self.repository_id),
            lifecycle_state="current",
        )

    def current_facts(self, predicate: str) -> tuple[CanonicalFact, ...]:
        out = []
        for entity_id in sorted(self._candidate_entity_ids(predicate)):
            fact = self._fact_from_head(entity_id)
            if fact is not None:
                out.append(fact)
        return tuple(out)

    def resolve(self, fact_id: str) -> Mapping[str, Any] | None:
        artifact = self._read_artifact(fact_id)
        if artifact is None:
            return None
        return {"knowledge_id": fact_id, "lifecycle_state": "current"}

    def current_versions(self, fact_entity_id: str) -> tuple[Mapping[str, Any], ...] | None:
        head = registry_head(fact_entity_id, registry_path=self.registry_path)
        if head is None:
            return None
        return ({"knowledge_id": head.knowledge_id, "lifecycle_state": "current"},)


# ── ContextRequest + ControlContext (design §6.2/§6.3) ────────────


@dataclass(frozen=True)
class ContextRequest:
    """One request to compile a snapshot: which contract, at which scope."""

    decision_type: str
    scope_type: str
    scope_id: str
    scope_path: str
    repository_id: str = REPOSITORY_ID


@dataclass(frozen=True)
class ControlContext:
    """What a controller is allowed to know for ONE decision. Frozen and content-addressed.

    The four "negative" collections (unknowns, conflicts, stale, advisory) answer WHY something
    is not here — a controller reading this snapshot can always tell "no evidence exists" from
    "scope-excluded" from "too old to trust" (design §6.3).
    """

    snapshot_id: str
    decision_type: str
    contract_version: str
    scope_path: str
    compiled_at: str  # NOT part of snapshot_id (§6.4) — content-addressed, not time-addressed

    invariants: tuple[FactRef, ...]
    objectives: tuple[Objective, ...]

    workload: tuple[FactRef, ...]
    workflow: tuple[FactRef, ...]
    job: tuple[FactRef, ...]
    resource: tuple[FactRef, ...]

    unknowns: tuple[Unknown, ...]
    conflicts: tuple[Conflict, ...]
    stale: tuple[StaleFact, ...]
    advisory: tuple[FactRef, ...]

    evidence_ids: tuple[str, ...]
    admissible: bool
    refusal: str


def compute_snapshot_id(
    *,
    contract_version: str,
    decision_type: str,
    scope_path: str,
    fact_ids: Iterable[str],
    unknowns: Iterable[Unknown],
    conflicts: Iterable[Conflict],
    stale: Iterable[StaleFact],
) -> str:
    """``sha256(contract_version | decision_type | scope_path | sorted fact_ids | digests)``
    (design §6.4) — ``compiled_at`` is excluded on purpose, so identical state yields an
    identical id (idempotent recompilation, provable-identical-inputs comparison across arms,
    and cacheability for free — the same reasoning ``record_to_artifact`` uses to blank its own
    volatile timestamps before hashing)."""
    parts = [
        contract_version,
        decision_type,
        scope_path,
        "|".join(sorted(fact_ids)),
        json.dumps([(u.predicate, u.scope, u.reason, u.handling) for u in unknowns], sort_keys=True),
        json.dumps(
            [(c.predicate, c.scope, sorted(f.fact_id for f in c.candidates)) for c in conflicts],
            sort_keys=True,
        ),
        json.dumps(
            [(s.fact.fact_id, s.scope, s.reason) for s in stale],
            sort_keys=True,
        ),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _age_seconds(observed_at: str, now: str) -> int:
    obs = _parse_iso(observed_at)
    cur = _parse_iso(now)
    if obs is None or cur is None:
        return 0
    return max(0, int((cur - obs).total_seconds()))


def _to_fact_ref(fact: CanonicalFact, *, now: str) -> FactRef:
    return FactRef(
        fact_id=fact.fact_id,
        predicate=fact.predicate,
        subject_id=fact.subject_id,
        scope_path=fact.scope_path,
        value=fact.value,
        value_type=fact.value_type,
        authority=fact.authority.name,
        epistemic_status=fact.epistemic_status,
        observed_at=fact.observed_at,
        age_seconds=_age_seconds(fact.observed_at, now),
        reducer_version=fact.reducer_version,
        evidence_ids=fact.evidence_ids,
    )


@dataclass
class _Resolution:
    """One requirement's outcome — exactly one of the four is populated."""

    fact_ref: FactRef | None = None
    unknown: Unknown | None = None
    conflict: Conflict | None = None
    stale: StaleFact | None = None


def _resolve_requirement(
    req: FactRequirement,
    *,
    decision_scope_path: str,
    store: FactStore,
    now: str,
) -> _Resolution:
    """Resolve one :class:`FactRequirement` against ``store`` (design §6.2 steps 3-5).

    Classification precedence: out-of-scope -> no candidate -> conflicted -> broken chain ->
    below min authority -> stale (predicate TTL cascade, or the requirement's own
    ``max_age_seconds`` tightening) -> satisfied. A chain failure DEMOTES a fact to unknown
    rather than silently admitting it (§6.2 step 5: "a fact whose provenance cannot be checked
    is not a fact").
    """
    target_scope_path = resolve_requirement_scope(req.scope, decision_scope_path)
    if target_scope_path is None:
        return _Resolution(
            unknown=Unknown(
                predicate=req.fact, scope=req.scope, reason="out_of_scope", handling=req.on_missing
            )
        )

    predicate_spec = FACT_PREDICATES.get(req.fact)
    candidates = [
        f
        for f in store.current_facts(req.fact)
        if scope_visible(target_scope_path, f.scope_path, predicate_spec)
    ]
    if not candidates and req.scope == "self":
        # Self-reflexive descendant allowance, documented deviation (implementation_notes.md):
        # a predicate whose OWN declared scope_type sits one rung BELOW the decision (design's
        # own §6.1 example: `phase_test_verified` is attempt-scoped, required at `scope: self`
        # by a JOB-scoped decision) still means "this job's own current state", not the general
        # "descendant peek" §10.2 forbids for AGGREGATION (unbounded reads across children with
        # no reducer). Only the single MOST RECENTLY OBSERVED fact strictly under the decision's
        # own scope_path is considered — never an unbounded scan, never a rollup — so this stays
        # one fact, not an aggregate, and requires no new reducer.
        descendants = [
            f
            for f in store.current_facts(req.fact)
            if f.scope_path.startswith(decision_scope_path + "/")
        ]
        if descendants:
            candidates = [max(descendants, key=lambda f: f.observed_at)]
    if not candidates:
        return _Resolution(
            unknown=Unknown(
                predicate=req.fact, scope=req.scope, reason="no_fact", handling=req.on_missing
            )
        )

    # More than one distinct entity_id visible at this scope is unexpected (§3.2: one slot per
    # scope+subject+predicate) but not impossible if subject_id ever diverges from scope_id;
    # deterministic tie-break (smallest fact_entity_id) rather than an arbitrary pick.
    by_entity: dict[str, list[CanonicalFact]] = {}
    for f in candidates:
        by_entity.setdefault(f.fact_entity_id, []).append(f)
    entity_id = sorted(by_entity)[0]
    group = sorted(by_entity[entity_id], key=lambda f: f.fact_id)
    fact = group[0]

    state = fact_state(
        fact, now=now, resolve=store.resolve, current_versions=store.current_versions
    )
    if state == "conflicted":
        return _Resolution(
            conflict=Conflict(
                predicate=req.fact,
                scope=req.scope,
                candidates=tuple(_to_fact_ref(f, now=now) for f in group),
                handling=req.on_conflict,
            )
        )
    if state in ("tombstoned", "superseded"):
        # Defensive: current_facts() already filters to lifecycle_state == "current", so this
        # is only reachable if the store's own bookkeeping disagrees with fact_state()'s
        # read-time derivation — treat as absent rather than trusting a stale local flag.
        return _Resolution(
            unknown=Unknown(
                predicate=req.fact, scope=req.scope, reason="no_fact", handling=req.on_missing
            )
        )
    if state == "stale":
        return _Resolution(
            stale=StaleFact(
                fact=_to_fact_ref(fact, now=now),
                scope=req.scope,
                reason="cascade",
                handling=req.on_missing,
            )
        )

    errors = verify_chain(fact, REDUCERS, resolve=store.resolve)
    if errors:
        return _Resolution(
            unknown=Unknown(
                predicate=req.fact, scope=req.scope, reason="broken_chain", handling=req.on_missing
            )
        )

    try:
        min_authority = Authority[req.min_authority]
    except KeyError:
        min_authority = Authority.DERIVED
    if fact.authority < min_authority:
        return _Resolution(
            unknown=Unknown(
                predicate=req.fact,
                scope=req.scope,
                reason="below_min_authority",
                handling=req.on_missing,
            )
        )

    ref = _to_fact_ref(fact, now=now)
    if req.max_age_seconds is not None and ref.age_seconds > req.max_age_seconds:
        return _Resolution(
            stale=StaleFact(
                fact=ref, scope=req.scope, reason="max_age_exceeded", handling=req.on_missing
            )
        )

    return _Resolution(fact_ref=ref)


def compile_context(
    request: ContextRequest,
    *,
    store: FactStore,
    now: str,
    contract: ContractSpec | None = None,
    contracts_dir: Path = CONTRACTS_DIR,
    domain: DomainProfile | None = None,
    challenge: ChallengeProfile | None = None,
) -> ControlContext:
    """Build the decision-specific snapshot (design §6.2). Deterministic; no LLM; no network
    beyond ``store``. ``contract`` may be pre-loaded (tests); production resolves it from
    ``contracts_dir`` by ``request.decision_type``.

    ``domain``/``challenge`` are the CAP addendum I8 profile inputs (design §2.3/§2.4). THE
    CONTRACT REMAINS THE SOLE GATE: step 0 (new, before resolution) composes ``challenge``'s
    ``context_requirements`` into ``contract.requires_facts`` via
    ``profiles.compose_requirements`` — contract-wins, never-widens (deviation D4) — and THAT
    composed tuple, not the raw contract field, is what steps 1-9 resolve against.
    ``contract.invariants`` is deliberately NEVER touched by composition: the safety gate stays
    exactly what the contract alone declares. ``domain`` is accepted here for symmetry and future
    declaration/audit use (a caller may want to record which domain governed a decision) but
    contributes NO ``FactRequirement`` entries in v1 — only a :class:`ChallengeProfile` carries
    ``context_requirements`` (§2.1); a :class:`DomainProfile` does not, so passing one changes
    nothing about what gets resolved (§2.1's honesty rule: no L4/undeclared claim is implied by
    accepting the parameter). An absent/unknown ``challenge`` (``None``, the default) is a
    no-op — the contract alone governs, unchanged from every pre-I8 caller.
    """
    contract = contract or load_contract(request.decision_type, contracts_dir=contracts_dir)
    if request.scope_type != contract.decision_scope:
        raise ValueError(
            f"contract {contract.decision_type!r} is scoped at {contract.decision_scope!r}; "
            f"request is scoped at {request.scope_type!r}"
        )
    effective_requires_facts = compose_requirements(contract, challenge)
    _ = domain  # accepted for future declaration/audit use only — see docstring above; not
    # consumed in v1 (only a ChallengeProfile carries context_requirements — §2.1's honesty rule)

    unknowns: list[Unknown] = []
    conflicts: list[Conflict] = []
    stale: list[StaleFact] = []
    buckets: dict[str, list[FactRef]] = {"workload": [], "workflow": [], "job": [], "resource": []}
    invariant_refs: list[FactRef] = []
    evidence: set[str] = set()
    admissible = True
    refusal_parts: list[str] = []

    def _apply(res: _Resolution, req: FactRequirement, *, is_invariant: bool) -> FactRef | None:
        nonlocal admissible
        if res.fact_ref is not None:
            evidence.add(res.fact_ref.fact_id)
            evidence.update(res.fact_ref.evidence_ids)
            return res.fact_ref
        handling = req.on_missing
        if res.unknown is not None:
            unknowns.append(res.unknown)
        elif res.stale is not None:
            stale.append(res.stale)
        elif res.conflict is not None:
            conflicts.append(res.conflict)
            handling = req.on_conflict
        if handling in ("halt", "escalate"):
            admissible = False
            refusal_parts.append(f"{req.fact} ({req.scope}): {handling}")
        return None

    for req in contract.invariants:
        res = _resolve_requirement(
            req, decision_scope_path=request.scope_path, store=store, now=now
        )
        ref = _apply(res, req, is_invariant=True)
        if ref is not None:
            invariant_refs.append(ref)

    for req in effective_requires_facts:
        res = _resolve_requirement(
            req, decision_scope_path=request.scope_path, store=store, now=now
        )
        ref = _apply(res, req, is_invariant=False)
        if ref is None:
            continue
        predicate_spec = FACT_PREDICATES.get(req.fact)
        scope_type = predicate_spec.scope_type if predicate_spec else "job"
        bucket = scope_type if scope_type in buckets else "job"
        buckets[bucket].append(ref)

    # Advisory context (§6.3): every ADVISORY-authority current fact for a required predicate,
    # visible in scope, surfaced for a human/researcher to read but never citable (C5, I6).
    advisory: list[FactRef] = []
    for req in effective_requires_facts:
        target_scope_path = resolve_requirement_scope(req.scope, request.scope_path)
        if target_scope_path is None:
            continue
        predicate_spec = FACT_PREDICATES.get(req.fact)
        for f in store.current_facts(req.fact):
            if f.epistemic_status != "advisory":
                continue
            if scope_visible(target_scope_path, f.scope_path, predicate_spec):
                advisory.append(_to_fact_ref(f, now=now))

    snapshot_id = compute_snapshot_id(
        contract_version=contract.contract_version,
        decision_type=contract.decision_type,
        scope_path=request.scope_path,
        fact_ids=evidence,
        unknowns=unknowns,
        conflicts=conflicts,
        stale=stale,
    )

    return ControlContext(
        snapshot_id=snapshot_id,
        decision_type=contract.decision_type,
        contract_version=contract.contract_version,
        scope_path=request.scope_path,
        compiled_at=now,
        invariants=tuple(invariant_refs),
        objectives=contract.objectives,
        workload=tuple(buckets["workload"]),
        workflow=tuple(buckets["workflow"]),
        job=tuple(buckets["job"]),
        resource=tuple(buckets["resource"]),
        unknowns=tuple(unknowns),
        conflicts=tuple(conflicts),
        stale=tuple(stale),
        advisory=tuple(advisory),
        evidence_ids=tuple(sorted(evidence)),
        admissible=admissible,
        refusal="; ".join(refusal_parts),
    )


# ── Snapshot persistence (design §8.5) ────────────────────────────


def snapshot_payload(ctx: ControlContext) -> dict[str, Any]:
    """The snapshot's canonical JSON payload — mirrors ``fact_ingestion.fact_payload``'s
    "the value lives inside the hashed text" decision (§3.3), applied to a snapshot instead of a
    fact: the recorded artifact is machine-readable, not a prose projection."""
    return {
        "snapshot_id": ctx.snapshot_id,
        "decision_type": ctx.decision_type,
        "contract_version": ctx.contract_version,
        "scope_path": ctx.scope_path,
        "admissible": ctx.admissible,
        "refusal": ctx.refusal,
        "evidence_ids": list(ctx.evidence_ids),
        "n_unknowns": len(ctx.unknowns),
        "n_conflicts": len(ctx.conflicts),
        "n_stale": len(ctx.stale),
        "unknown_predicates": sorted({u.predicate for u in ctx.unknowns}),
        "conflict_predicates": sorted({c.predicate for c in ctx.conflicts}),
        "stale_predicates": sorted({s.fact.predicate for s in ctx.stale}),
    }


def build_snapshot_record(
    ctx: ControlContext, *, repository_id: str, revision: str = REVISION_FALLBACK,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Map a :class:`ControlContext` onto a ``source_type="context_snapshot"``
    :class:`KnowledgeRecord` (design §8.5: registered as an observation-family record so a later
    ``ControlDecision``'s single-valued ``causes`` can point at it via ``knowledge_id``)."""
    return build_record_from_parts(
        source_type=SNAPSHOT_SOURCE_TYPE,
        source_uri=f"context_snapshot:{ctx.decision_type}:{ctx.scope_path}",
        logical_locator=ctx.snapshot_id,
        repository_id=repository_id,
        revision=revision,
        authority=Authority.DERIVED,
        evidence_class="[C]",
        text=json.dumps(snapshot_payload(ctx), sort_keys=True),
        extra_fields={"extractor_version": EXTRACTOR_VERSION},
        now=now,
    )


def record_snapshot(
    ctx: ControlContext,
    *,
    repository_id: str,
    revision: str = REVISION_FALLBACK,
    authorized: bool = True,
) -> KnowledgeRecord | None:
    """Best-effort durable persistence of one snapshot through the EXISTING knowledge pipe.

    Returns the record on success, ``None`` on ANY failure (no Redis, no write authorization,
    a malformed store) — a snapshot failure must never block the phase that triggered it, the
    same "never blocks the phase" posture ``augment.py`` already uses for retrieval/construction
    failures. This is I4's ONLY producer call site; nothing consumes what it writes yet.
    """
    try:
        from agentic_dynamics.knowledge import knowledge_stream as ks
        from agentic_dynamics.knowledge.record_factory import record_to_artifact

        record = build_snapshot_record(ctx, repository_id=repository_id, revision=revision)
        artifact = record_to_artifact(record)
        KB_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        (KB_ARTIFACT_DIR / f"{record.knowledge_id}.json").write_bytes(artifact)
        event = record_to_event(record, operation="upsert", reason="", now=None)
        client = ks.connect()
        ks.publish_event(
            client, event, authorized=authorized, source_type=SNAPSHOT_SOURCE_TYPE
        )
        return record
    except Exception:
        return None


# ── The snapshotting router (composition-root seam) ───────────────


def make_snapshotting_router(
    *,
    workload: str,
    cell_id: str,
    repository_id: str = REPOSITORY_ID,
    revision: str = REVISION_FALLBACK,
    store: FactStore | None = None,
    record: bool = True,
) -> Callable[..., str]:
    """Build a drop-in :class:`~agentic_dynamics.runtime.routing.Router` that ALSO compiles and
    (best-effort) records a ``route_next_job/v1`` snapshot beside every routing decision — the
    design's own phrasing (§9 I4: "snapshots recorded beside every route_step call").

    Never modifies ``route_step``'s decision: the returned model is always exactly what
    ``route_step`` chose. Injected at the composition root (``scripts/run_workflow.py``) in place
    of the bare ``route_step`` callable — ``runtime.workflow_runner`` never imports ``control``
    either way (Debt-2), since both are ``Router``-shaped closures supplied from outside it.
    Recording is opt-in at the call site (default True here, but the composition root gates it
    behind an explicit flag — see ``scripts/run_workflow.py``'s ``--cap-snapshot``) because it is
    the first CAP hook to touch a REAL production run path and a real Redis connection.
    """
    from agentic_dynamics.control.step_routing import route_step

    fact_store = store or RegistryFactStore(repository_id=repository_id)
    scope_path = f"org:{repository_id}/workload:{workload}/job:{cell_id}"

    def _router(job: dict, state, prefs, *, signals=None) -> str:
        model = route_step(job, state, prefs, signals=signals)
        if record:
            try:
                request = ContextRequest(
                    decision_type="route_next_job",
                    scope_type="job",
                    scope_id=cell_id,
                    scope_path=scope_path,
                    repository_id=repository_id,
                )
                ctx = compile_context(request, store=fact_store, now=_now_iso())
                record_snapshot(ctx, repository_id=repository_id, revision=revision)
            except Exception:
                pass  # snapshot recording is read-only measurement — never blocks routing
        return model

    return _router


# ── The REAL I5 compile-time gate (design §7.3) ───────────────────


def load_all_contracts(*, contracts_dir: Path = CONTRACTS_DIR) -> dict[str, ContractSpec]:
    """Load every ``experiments/contexts/*.yaml`` contract, keyed by ``decision_type``.

    The registry :func:`validate_spec_fact_contracts` (R9/R10/R11) needs — a compile-time gate
    must see every committed contract, not just the ones a given spec happens to reference,
    because R11 (an invariant's on_missing semantics) is a property OF the contract, checked
    independent of who references it.
    """
    contracts: dict[str, ContractSpec] = {}
    if not contracts_dir.is_dir():
        return contracts
    for path in sorted(contracts_dir.glob("*.yaml")):
        contract = load_contract(path.stem, contracts_dir=contracts_dir)
        contracts[contract.decision_type] = contract
    return contracts


def validate_spec_fact_contracts(
    spec: Any, *, contracts_dir: Path = CONTRACTS_DIR
) -> list[str]:
    """The ACTUAL CAP I5 compile-time gate — real ``FACT_PREDICATES``/``REDUCERS``/contracts.

    ``core.contracts.validate_fact_contracts`` is a pure function of whatever registries it is
    handed (tier 0 — it may not import ``control.facts``/``control.reducers``, design's
    docstring). THIS is the composition point: a caller in ``control`` (tier 2, which may see
    both ``core`` and ``experiment``) supplies the real registries. Callers: a spec-authoring
    test, ``scripts/validate_session.py``-style pre-flight checks, or any future producer that
    wants the I5 gate applied with real data — not ``compile_experiment.compile_spec`` itself,
    which stays tier 1 and therefore cannot call this (design's own §7.3 split: "compile time
    proves producibility" is ``experiment``'s job with an empty registry by default; a REAL
    registry is a ``control``-tier opt-in, exactly like the I4 snapshot hook is).
    """
    from agentic_dynamics.experiment.experiment_spec import validate_spec

    return validate_spec(
        spec,
        fact_predicates=FACT_PREDICATES,
        fact_reducers=REDUCERS,
        fact_contracts=load_all_contracts(contracts_dir=contracts_dir),
    )
