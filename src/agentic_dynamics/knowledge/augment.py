"""The ``retrieve -> construct -> render`` augmentation seam for one agent phase.

Extracted from ``workflow_runner.py`` (R7 of ``docs/review/restructure.md``) so the
runtime-RAG knowledge base stays testable without a workflow run. :func:`augment_prompt`
is the entire augmentation; ``workflow_runner`` keeps only phase execution plus the
self-build finding emit (default ON since kb_finding_layer k1).

The seam runs between ``route_step`` and ``run_agent`` (never before routing, so the
augmentation sees the selected executor model), gated by ``rag_augment`` (default OFF).
It is pure w.r.t. the worktree — no writes, no commits. Any retrieval or constructor
failure reverts to ``base_prompt`` and records a named fallback mode, so augmentation
never blocks a phase.

Read-only by construction: this module references ``publish_event`` zero times. The
sole KB writer is the self-build ``emit_self`` path in ``workflow_runner``
(``knowledge_ingestion.emit_phase_finding`` — default ON for workflow runs since
kb_finding_layer k1). The dense/lexical store wiring here is
lazy (imports inside the default-wiring functions, never at import time) so the
optional deps (chromadb / neo4j) stay optional and core startup never constructs a
store.
"""

from __future__ import annotations

import functools
import hashlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

#: Default executor tool surface offered to the prompt constructor's ``allowed_tools``
#: subset check. Overridable via ``rag_params.inherited_tools``; the constructor may only
#: *reduce* this set, never add to it.
DEFAULT_INHERITED_TOOLS = ("read", "write", "edit", "bash", "grep", "glob", "list")

#: The RETIRED constructor model FAMILY (register L39): a fresh provider process refuses the
#: retired id, so an explicit ``constructor_model`` override naming this family is refused by
#: :func:`resolve_constructor_model` — LOUDLY, at WIRING time, instead of silently degrading to
#: a generic ``constructor_call_failed`` at call time (the exact defect this guard closes).
#:
#: The family token is deliberately held WITHOUT the ``provider/`` prefix (never the full
#: ``provider/id`` selection literal), so the bounded AST sweep in
#: ``tests/test_prompt_constructor.py`` still finds the retired id only as prose in the touched
#: modules — while the guard below still refuses the retired family for ANY provider namespace.
RETIRED_CONSTRUCTOR_MODEL_FAMILY = "deepseek-v4-flash"


class RetiredConstructorModelError(ValueError):
    """An explicit ``constructor_model`` named a RETIRED id (register L39); refuse loudly."""


def resolve_constructor_model(model: str | None = None) -> str:
    """Resolve a constructor model id, refusing the retired family with a NAMED cause.

    ``None``/empty resolves to the pinned live volume id (``DEFAULT_CONSTRUCTOR_MODEL``). Any
    explicit id whose routing family is :data:`RETIRED_CONSTRUCTOR_MODEL_FAMILY` raises
    :class:`RetiredConstructorModelError` at WIRING time, so the caller sees the retired id and
    its live replacement instead of a silent generic constructor fallback. The guard is
    family-keyed (not one literal), so a re-providered retired id cannot slip through.
    """
    from agentic_dynamics.knowledge.prompt_constructor import DEFAULT_CONSTRUCTOR_MODEL

    resolved = str(model) if model else DEFAULT_CONSTRUCTOR_MODEL
    if resolved.rsplit("/", 1)[-1] == RETIRED_CONSTRUCTOR_MODEL_FAMILY:
        raise RetiredConstructorModelError(
            f"constructor_model {resolved!r} is RETIRED (family "
            f"{RETIRED_CONSTRUCTOR_MODEL_FAMILY!r}, register L39): a fresh provider process "
            f"refuses it. Use the live volume model {DEFAULT_CONSTRUCTOR_MODEL!r}."
        )
    return resolved


def _attempt_id(kind: str, *parts: str) -> str:
    """Deterministic attempt id for retrieval/construction tracing.

    Keyed on the semantic inputs (never a session/fork id) so an attempt can be
    replayed and attributed without depending on a per-process random id.
    """
    digest = hashlib.sha256("|".join((kind, *parts)).encode("utf-8")).hexdigest()
    return f"{kind}:{digest[:16]}"


@dataclass
class AugmentationOutcome:
    """Result of ``retrieve -> construct -> render`` for one agent phase.

    ``fallback`` is True only when the phase reverted to the base prompt; otherwise
    the augmented (or degraded) prompt was produced and ``fallback_mode`` names the
    degradation level (``full`` / ``lexical_graph_only`` / ``dense_local_exact`` /
    ``no_rag``).
    """

    prompt: str
    fallback: bool = True
    fallback_mode: str = "no_rag"
    #: Named cause for a seam failure or constructor degradation. An empty value
    #: means the augmentation completed without a failure outcome.
    fallback_reason: str = ""
    raw_prompt_hash: str = ""
    retrieval_attempt_id: str = ""
    constructor_attempt_id: str = ""
    selected_evidence_ids: list[str] = field(default_factory=list)
    #: Per-evidence provenance for the selected set — [{"id","revision","source_type",
    #: "locator"}]. Follows the FINAL emitted set (the constructor may trim evidence), so
    #: it never claims a source the worker did not receive; rides the existing run result.
    selected_evidence: list[dict[str, str]] = field(default_factory=list)
    #: Named causes for retrieval legs that failed or exceeded the budget
    #: ({"dense"|"lexical"|"embedding"|"expansion": reason}) — carried through the
    #: augmentation outcome into the run result so a degraded pass stays diagnosable.
    retrieval_leg_errors: dict[str, str] = field(default_factory=dict)
    versions: dict[str, str] = field(default_factory=dict)
    token_counts: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    #: The swallowed exception on the no_rag fallback (retrieve/construct failure), so a
    #: degraded phase is distinguishable from a seam that never ran — the ledger records
    #: the error instead of erasing it. Empty when the augmentation completed.
    error: str = ""
    #: The per-phase context-route record (``context-route/v1``) built by the SINGLE builder
    #: in ``knowledge/context_layers`` — one honest disposition per resolved layer, plus the
    #: unroutable/unclassified items. ALWAYS populated by the seam (an unresolved route is an
    #: explicit ``route_status == "unknown"`` record, never a missing key), so the runner can
    #: copy it into the ledger verbatim. ``None`` only when a caller constructs the outcome
    #: directly without running the seam.
    context_route: dict[str, Any] | None = None


def _evidence_from_attempt(attempt: Any) -> list[Any]:
    """Extract :class:`EvidenceUnit`-shaped items from a retrieval attempt.

    ``retrieve()`` returns a ``RetrievalAttempt`` whose ``selected_evidence`` is a
    list of candidates carrying ``id``/``text``/``authority``/``locator``; the
    constructor consumes the equivalent shape. This adapter keeps the seam tolerant
    of either (real candidates or test doubles).
    """
    selected = getattr(attempt, "selected_evidence", []) or []
    from agentic_dynamics.knowledge.prompt_constructor import (
        EvidenceUnit,  # lazy — avoids import-time coupling
    )

    units: list[Any] = []
    for c in selected:
        cid = getattr(c, "id", "") or ""
        text = getattr(c, "text", "") or ""
        authority = getattr(c, "authority", "") or ""
        if hasattr(authority, "name"):
            authority = authority.name.lower()
        citation = ""
        if hasattr(c, "citation"):
            citation = c.citation()
        units.append(
            EvidenceUnit(
                knowledge_id=cid,
                text=text,
                authority=str(authority),
                citation=citation,
                content_hash=getattr(c, "content_hash", "") or "",
                token_count=int(getattr(c, "token_count", 0) or len(text.split())),
                source_type=str(getattr(c, "source_type", "") or ""),
                pattern_payload=getattr(c, "pattern_payload", None),
            )
        )
    return units


def augment_prompt(
    *,
    base_prompt: str,
    goal: str,
    phase_def: dict[str, Any],
    model: str,
    commit_sha: str,
    inherited_tools: list[str],
    pinned_policy: str,
    rag_params: dict[str, Any],
    retrieve_fn: Callable[..., Any],
    construct_fn: Callable[..., Any],
    route: Any = None,
    shared_scopes: Any = None,
) -> AugmentationOutcome:
    """Run ``retrieve -> construct -> render`` between ``route_step`` and ``run_agent``.

    Pure w.r.t. the worktree (no writes). Any retrieval/constructor failure reverts to
    ``base_prompt`` and records a named fallback reason — augmentation never blocks the
    phase. The injected callbacks are the only execution seam: this function does not
    publish knowledge, create an admission, or retry a failed paid call. ``retrieve_fn``
    returns a ``RetrievalAttempt``-shaped object; ``construct_fn`` maps a
    ``ConstructionRequest`` to an ``AugmentedPrompt``.

    ``route`` is the optional resolved :class:`~agentic_dynamics.knowledge.context_layers.LayerRoute`
    for this phase (the design §6 layer routing). When present it is mapped by
    :func:`~agentic_dynamics.knowledge.context_layers.resolve_layer_route` to the source-type
    prefilter, explicit shared repository ids, and pattern projection that shape the ONE
    existing ``retrieve`` path — no parallel retrieval and no new store. ``shared_scopes`` is
    the explicit shared-scope list (empty never means global); it is unioned with the route's
    own scopes for both retrieval and the record. Every pass (success OR fallback) populates
    ``outcome.context_route`` from the single ``build_context_route_record`` builder, so the
    ledger always carries one honest disposition per resolved layer (F4). Prohibited L4
    self-layer evidence is filtered OUT before ``construct_fn`` (R1), and the refused ids ride
    the record's L4 ``excluded`` disposition — so a belief id or its text can never reach the
    constructor input or the final prompt. On a route that resolved NO layers (A8-R1), evidence
    that maps to no layer is withheld from construction too: untyped content can never reach
    the constructor input or the final prompt, and its id is recorded with an honest
    ``unknown``/withheld disposition. The base prompt is preserved in every case.
    """
    from agentic_dynamics.knowledge.context_layers import (
        LAYER_SELF,
        build_context_route_record,
        layer_for_source_type,
        normalize_shared_scopes,
        resolve_layer_route,
        route_resolved,
        self_layer_prohibited,
    )
    from agentic_dynamics.knowledge.prompt_constructor import (
        ConstructionRequest,
        hash_work_item,
    )

    outcome = AugmentationOutcome(
        prompt=base_prompt,
        fallback=True,
        fallback_mode="no_rag",
        raw_prompt_hash=hash_work_item(base_prompt),
    )
    # The layer shaping is computed ONCE and threaded into retrieval; an absent route is the
    # identity shape, so a caller that does not route changes nothing about retrieval. The
    # shared ids are the union of the explicit keyword scopes and the route's own scopes, so
    # retrieval and the record agree (empty never means global).
    shape = resolve_layer_route(route, goal=goal, base_prompt=base_prompt)
    shared_ids = normalize_shared_scopes(shared_scopes, route)
    # R1: L4 self content is refused BEFORE construction, not labelled after it. The same
    # shared rule owns the decision here and in the record builder, so the two can never
    # disagree. ``excluded_evidence`` is initialised here so the ``finally`` record always
    # has it, even when retrieval raises before any evidence is seen.
    l4_prohibited = self_layer_prohibited(route)
    excluded_evidence: list[dict[str, str]] = []
    # A8-R1: evidence withheld BEFORE construction on an unresolved route. Initialised here
    # (not inside the try) so the ``finally`` record builder always receives it, even when
    # retrieval raises before any evidence is seen.
    withheld_evidence: list[dict[str, str]] = []
    t0 = time.time()
    stage = "retrieve"
    attempt: Any = None
    try:
        # 1. retrieve (deterministic; may degrade but not raise on missing legs)
        attempt = retrieve_fn(
            raw_work_item=base_prompt,
            phase_objective=goal,
            commit_sha=commit_sha,
            repository_id=str(rag_params.get("repository_id", "")),
            acl_scope=str(rag_params.get("acl_scope", "")),
            source_types=shape.source_types,
            shared_repository_ids=tuple(shared_ids),
            executor_context_tokens=int(rag_params.get("executor_context_tokens", 200_000)),
            remaining_input_tokens=int(rag_params.get("remaining_input_tokens", 200_000)),
            rag_token_limit=int(rag_params.get("rag_token_limit", 8000)),
            pattern_projection=(
                bool(rag_params.get("pattern_projection", False)) or shape.pattern_projection
            ),
        )
        if attempt is None:
            raise RuntimeError("retrieve returned no attempt")
        retrieval_mode = str(getattr(attempt, "fallback_mode", "") or "no_rag")
        outcome.retrieval_leg_errors = dict(getattr(attempt, "leg_errors", {}) or {})
        outcome.retrieval_attempt_id = getattr(attempt, "retrieval_attempt_id", "") or _attempt_id(
            "retrieval", base_prompt, commit_sha
        )

        # 2. construct (one bounded model call + deterministic renderer)
        stage = "construct"
        evidence = _evidence_from_attempt(attempt)
        # R1 pre-construction filter: when L4 is prohibited (absent route, the explicit
        # unknown sentinel, or any ordinary cell route), drop every self-layer item from
        # the constructor input. A refused item must never influence the final prompt; its
        # id is recorded on the L4 ``excluded`` disposition via ``excluded_evidence``.
        if l4_prohibited:
            kept: list[Any] = []
            for unit in evidence:
                if layer_for_source_type(getattr(unit, "source_type", "")) == LAYER_SELF:
                    excluded_evidence.append(
                        {
                            "id": str(getattr(unit, "knowledge_id", "") or ""),
                            "source_type": str(getattr(unit, "source_type", "") or ""),
                        }
                    )
                    continue
                kept.append(unit)
            evidence = kept
        # A8-R1 pre-construction withhold: on a route that resolved NO layers, an item with
        # no resolvable layer (``layer_for_source_type`` returns "") cannot be attributed to
        # any layer. Leave it OUT of constructor input — and therefore out of the final
        # prompt — and hand its {id, source_type} to the record builder as an honest
        # withheld/unknown disposition. Typed non-L4 items keep their existing
        # unclassified-but-served behavior; the base prompt is always preserved.
        if not route_resolved(route):
            kept_typed: list[Any] = []
            for unit in evidence:
                source_type = str(getattr(unit, "source_type", "") or "")
                if not layer_for_source_type(source_type):
                    withheld_evidence.append(
                        {
                            "id": str(getattr(unit, "knowledge_id", "") or ""),
                            "source_type": source_type,
                        }
                    )
                    continue
                kept_typed.append(unit)
            evidence = kept_typed
        # u5: a retired ``constructor_model`` override is REFUSED by name here (inside the seam's
        # guarded step, so the phase still records a NAMED cause and preserves the base prompt
        # rather than proceeding on a model a fresh process refuses). Non-retired overrides —
        # including no override — resolve unchanged to the live volume id.
        constructor_model = resolve_constructor_model(rag_params.get("constructor_model"))
        request = ConstructionRequest(
            raw_work_item=base_prompt,
            phase_objective=goal,
            pinned_policy=pinned_policy,
            evidence=evidence,
            inherited_tools=list(inherited_tools),
            user_constraints=list(rag_params.get("user_constraints", []) or []),
            executor_model=model,
            commit_sha=commit_sha,
            constructor_model=constructor_model,
        )
        augmented = construct_fn(request)
        if augmented is None or not getattr(augmented, "prompt", ""):
            raise RuntimeError("constructor produced no prompt")

        outcome.prompt = str(augmented.prompt)
        # A constructor that internally fell back to its deterministic renderer still
        # produced a valid prompt; record whether it did, but only mark the *phase*
        # as reverted when retrieval degraded.
        constructor_fell_back = bool(getattr(augmented, "fallback", False))
        outcome.fallback = False
        outcome.fallback_mode = "full" if retrieval_mode == "full" else retrieval_mode
        outcome.constructor_attempt_id = getattr(
            augmented, "constructor_attempt_id", ""
        ) or _attempt_id("constructor", base_prompt, commit_sha, constructor_model)
        outcome.selected_evidence_ids = list(getattr(augmented, "evidence_ids", []) or [])
        # Provenance follows the FINAL emitted set (review finding P2): the constructor may
        # trim evidence to fit its token budget, so copying the retrieval-level selection
        # would claim sources the worker never received. Map the final ids back to the
        # attempt's candidates for revision/source-type/locator.
        by_id = {
            str(getattr(c, "id", "") or ""): c
            for c in (getattr(attempt, "selected_evidence", []) or [])
        }
        outcome.selected_evidence = []
        for evidence_id in outcome.selected_evidence_ids:
            candidate = by_id.get(str(evidence_id))
            outcome.selected_evidence.append(
                {
                    "id": str(evidence_id),
                    "revision": (
                        str(getattr(candidate, "commit_sha", "") or "") if candidate else ""
                    ),
                    "source_type": (
                        str(getattr(candidate, "source_type", "") or "") if candidate else ""
                    ),
                    "locator": (str(getattr(candidate, "locator", "") or "") if candidate else ""),
                }
            )
        outcome.versions = dict(getattr(augmented, "versions", {}) or {})
        outcome.token_counts = dict(getattr(augmented, "token_counts", {}) or {})
        outcome.cost_usd = float(getattr(augmented, "cost_usd", 0.0) or 0.0)
        if constructor_fell_back:
            outcome.fallback_reason = str(
                getattr(augmented, "fallback_reason", "") or "constructor_fallback"
            )
            outcome.versions = {**outcome.versions, "constructor": "deterministic-fallback"}
    except Exception as exc:  # noqa: BLE001 — the fallback must never block the phase
        outcome.prompt = base_prompt
        outcome.fallback = True
        outcome.fallback_mode = "no_rag"
        outcome.fallback_reason = f"{stage}_failed"
        outcome.error = f"{type(exc).__name__}: {exc}"
    finally:
        outcome.latency_ms = round((time.time() - t0) * 1000.0, 2)
        # The record is built over the FINAL outcome state (success or fallback) so the
        # ledger always carries a per-layer disposition. The builder is the single owner of
        # the schema; if it ever raises, fall back to an explicit named-absence record
        # rather than dropping the key — the seam must never block the phase (F4/F5).
        try:
            outcome.context_route = build_context_route_record(
                phase_def,
                route,
                attempt,
                outcome,
                shared_scopes=shared_scopes,
                excluded_evidence=excluded_evidence,
                withheld_evidence=withheld_evidence,
            )
        except Exception as exc:  # noqa: BLE001 — recording must never block the phase
            outcome.context_route = {
                "schema": "context-route/v1",
                "phase": str((phase_def or {}).get("name", "") or ""),
                "phase_kind": str((phase_def or {}).get("kind", "") or ""),
                "role": "unknown",
                "route_status": "unknown",
                "shared_scopes": [],
                "layers": [],
                "unclassified": [],
                "served_count": 0,
                "fallback_mode": outcome.fallback_mode,
                "fallback_reason": f"context_route_record_failed: {type(exc).__name__}: {exc}",
                "routing_reason": "",
                "leg_errors": {},
            }
    return outcome


class SourceTypeResolutionError(RuntimeError):
    """Raised when a durable source-type artifact EXISTS but cannot be read or parsed.

    R2 distinction (the astra repair): a genuinely ABSENT artifact is clean, authoritative
    absence and is memoised as ``None``; an unreadable or malformed artifact is an
    OPERATIONAL FAILURE that must surface through retrieval's ``source_type_resolver``
    diagnostic, never be cached as clean absence. The retrieval caller
    (``retrieval._resolve_source_type``) catches this typed error, records the named
    diagnostic on the attempt's ``leg_errors``, and lets the pass continue safely.
    """


def _durable_source_type_resolver() -> Callable[[str], str | None]:
    """Build the k4 source-typing resolver: ``knowledge_id -> source_type`` from the durable
    artifact layer.

    The retrieval legs hand the resolver ONLY candidates whose store metadata carries no
    ``source_type`` (an older projection — e.g. the pre-canonical-state Chroma population,
    whose durable ``kb/<knowledge_id>.json`` artifact still carries the record's real type).
    The resolver reads that authoritative artifact deterministically (never an LLM) so the
    store-metadata gap is closed at query time instead of minting an untyped candidate.

    R2 (the production defect the prior F3 injected-throw tests bypassed): the two failure
    modes are now separated instead of both collapsing to a cached ``None``.
    * a genuinely ABSENT artifact in a valid store directory is clean absence — ``None``,
      memoised, because there is no durable record to type from;
    * a readable artifact with no ``source_type`` is also clean absence — ``None``, memoised;
    * an UNREADABLE or MALFORMED artifact raises :class:`SourceTypeResolutionError` and is
      NEVER memoised, so a store outage can never masquerade as an authoritative empty.

    R2b (the astra repair): the ``source_type`` FIELD is type-validated, not coerced. The
    former ``str(rec.get("source_type") or "")`` treated any falsy JSON value as clean
    absence and stringified any truthy one, so ``[]``/``false`` silently became absent and
    ``{"bad": 1}`` fabricated the type string ``"{'bad': 1}"``. A missing field and an
    explicit ``null`` remain clean absence; a string is stripped/lower-cased (an empty
    string is clean absence); any OTHER JSON type (list, bool, dict, number) raises the
    typed failure and is never cached, so a malformed field is a named diagnostic with safe
    continuation instead of a fake type or a fake absence.

    R2a (the astra repair): ``Path.exists()`` is NOT an authoritative absence test. When a
    parent path component of ``<store>/<knowledge_id>.json`` is a regular file (ENOTDIR) —
    e.g. ``KB_ARTIFACT_DIR`` itself points at a file — ``Path.exists()`` swallows the
    ``OSError`` and returns ``False``, so an OBSTRUCTED store read exactly like a clean
    absence. The resolver stats the store directory EXPLICITLY instead: a MISSING store
    directory is clean absence, but a store path that exists and is not a directory (or
    whose parent is a regular file) raises the typed failure, which retrieval records as a
    named ``source_type_resolver`` diagnostic while the pass continues. The store directory
    is read at CALL time (not captured at construction), so a repaired store is visible to
    the same resolver instance and an obstruction is never memoised.

    R2a residual (the att10 repair): the SAME ``Path.exists()`` defect hid on the individual
    artifact. A valid store directory can hold a flat ``<64-hex>.json`` symlink whose TARGET
    is a child of a regular file (ENOTDIR, errno 20); ``Path.exists()`` follows the link,
    swallows the ``OSError``, and returns ``False``, so an obstructed artifact read exactly
    like an authoritative absence and was CACHED as one. The lookup now stats the individual
    artifact and CLASSIFIES the result: ``FileNotFoundError`` (ENOENT — a genuinely missing
    artifact or a dangling symlink) is clean, memoised absence; any other ``OSError``
    (ENOTDIR, ``PermissionError``, …) raises the typed failure and never touches the cache;
    a path that stats successfully falls through to ``open()``. So a repaired store is
    visible to the SAME resolver instance, and an obstructed artifact is a named diagnostic,
    never a cached empty.
    """
    import json as _json
    import stat as _stat

    from agentic_dynamics.core import paths as _paths

    cache: dict[str, str | None] = {}

    def _resolve(knowledge_id: str) -> str | None:
        if knowledge_id in cache:
            return cache[knowledge_id]
        # R2a: read the store directory at CALL time so a config/store repair is visible to
        # the same resolver instance; the path is never captured at construction.
        store_dir = _paths.KB_ARTIFACT_DIR
        path = store_dir / f"{knowledge_id}.json"
        # ``exists()`` cannot distinguish a genuinely absent record from an obstructed store
        # (a non-directory parent makes every child stat raise ENOTDIR, which ``exists()``
        # reports as ``False``). Stat the directory explicitly and classify by mode.
        try:
            store_stat = os.stat(store_dir)
        except FileNotFoundError:
            # No artifact store created/configured: there is no durable record to type from.
            # This is clean, authoritative absence and the one path memoised as ``None``.
            cache[knowledge_id] = None
            return None
        except OSError as exc:
            # ENOTDIR (a parent component is a regular file) or any other stat failure is an
            # OPERATIONAL failure, not absence. Raise typed and never touch the cache.
            raise SourceTypeResolutionError(
                f"source_type resolver could not stat artifact store {store_dir!r} for "
                f"{knowledge_id!r}: {type(exc).__name__}: {exc}"
            ) from exc
        if not _stat.S_ISDIR(store_stat.st_mode):
            # The store path exists but is not a directory (e.g. a regular file occupying
            # the store path): an OBSTRUCTED store, never clean absence.
            raise SourceTypeResolutionError(
                f"source_type resolver artifact store {store_dir!r} is not a directory "
                f"(mode {_stat.S_IFMT(store_stat.st_mode):#o}) for {knowledge_id!r}"
            )
        # R2a residual: ``Path.exists()`` is not an authoritative absence test EITHER. It
        # follows the artifact symlink and swallows the ``OSError`` when the TARGET is
        # obstructed — a target whose parent component is a regular file is ENOTDIR (errno
        # 20) — returning ``False`` exactly as it does for a genuinely missing record.
        # ``os.stat(path)`` lets us CLASSIFY the lookup instead: only ``FileNotFoundError``
        # (ENOENT, a missing artifact or a dangling symlink) is clean, memoised absence; any
        # OTHER ``OSError`` is an operational failure that raises typed and never touches the
        # cache, so a repaired store is visible to this same resolver instance. A path that
        # stats successfully (including a directory occupying the artifact path) falls
        # through to ``open()``, whose failure the existing handler already classes as typed.
        try:
            os.stat(path)
        except FileNotFoundError:
            # The store directory is valid and the artifact is genuinely absent: clean,
            # authoritative absence, memoised as ``None``.
            cache[knowledge_id] = None
            return None
        except OSError as exc:
            # ENOTDIR (an obstructed symlink target), PermissionError, or any other non-ENOENT
            # stat failure is an OPERATIONAL failure, not absence. Raise typed and never touch
            # the cache, so the failure is never memoised and a repaired artifact is visible.
            raise SourceTypeResolutionError(
                f"source_type resolver could not stat artifact {path!r} for "
                f"{knowledge_id!r}: {type(exc).__name__}: {exc}"
            ) from exc
        try:
            with path.open(encoding="utf-8") as fh:
                rec = _json.load(fh)
            if not isinstance(rec, dict):
                raise ValueError(f"artifact root is {type(rec).__name__}, not a JSON object")
        except Exception as exc:  # noqa: BLE001 — operational failure is NOT absence
            # R2: an unreadable/malformed artifact is an operational failure, not a clean
            # empty. Raise a typed error so retrieval's diagnostic records it under
            # ``source_type_resolver`` while the pass continues — and crucially do NOT
            # touch ``cache``, so the failure is never memoised as authoritative absence.
            raise SourceTypeResolutionError(
                f"source_type resolver could not read artifact for {knowledge_id!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        # R2b: validate the ``source_type`` field TYPE instead of coercing it. JSON can hold a
        # list/bool/dict/number here; ``str(rec.get("source_type") or "")`` silently turned
        # ``[]`` and ``false`` into clean absence (via their falsiness) and FABRICATED the
        # string ``"{'bad': 1}"`` from a dict — a type the artifact never declared. A missing
        # field or an explicit ``null`` is clean absence; a string is stripped/lower-cased and
        # an empty string is clean absence; any other JSON type raises the typed failure, which
        # is NEVER cached, so the malformation surfaces as a named ``source_type_resolver``
        # diagnostic while the pass continues.
        field = rec.get("source_type")
        if field is None:
            resolved: str | None = None
        elif isinstance(field, str):
            resolved = field.strip().lower() or None
        else:
            raise SourceTypeResolutionError(
                f"source_type resolver artifact for {knowledge_id!r} has a non-string "
                f"source_type of type {type(field).__name__} ({field!r}); refusing to "
                "fabricate a type"
            )
        # A readable artifact with no source_type is clean absence and IS memoised (only
        # the operational-failure paths above skip the cache).
        cache[knowledge_id] = resolved
        return resolved

    return _resolve


class _UnavailableDenseStore:
    """Leg stand-in that RAISES the recorded construction cause.

    A construction failure must surface in ``leg_errors`` with its cause, not vanish into a
    silent ``None`` — which reads identically to "no store configured" (diagnostic acceptance
    gap). ``retrieve`` catches the raise per leg and names it, so the pass still degrades.
    When the cause is a TYPED embedder failure the original exception is CHAINED onto the
    raised ``RuntimeError`` (``raise ... from cause``), so the retrieval seam's one-level
    ``__cause__`` token lookup still names ``embedder-unreachable`` / ``embedder-module-absent``
    distinctly instead of collapsing to a module-missing traceback.
    """

    def __init__(self, cause: str, *, cause_exc: BaseException | None = None) -> None:
        self._cause = cause
        self._cause_exc = cause_exc

    def search(self, *args: Any, **kwargs: Any) -> list[Any]:
        error = RuntimeError(f"dense store construction failed: {self._cause}")
        if self._cause_exc is not None:
            raise error from self._cause_exc
        raise error


class _UnavailableGraphClient:
    """Leg stand-in that RAISES the recorded construction cause (lexical leg + expansion)."""

    def __init__(self, cause: str) -> None:
        self._cause = cause

    def search_knowledge_fulltext(self, *args: Any, **kwargs: Any) -> list[Any]:
        raise RuntimeError(f"graph client construction failed: {self._cause}")

    def expand_candidates(self, *args: Any, **kwargs: Any) -> list[Any]:
        raise RuntimeError(f"graph client construction failed: {self._cause}")


def default_retrieve_fn() -> Callable[..., Any]:
    """Lazily construct the dense + graph stores and bind them to ``retrieve``.

    Called only on the ``rag_augment`` path (never at import time), so the optional
    deps (chromadb / neo4j) stay optional and core startup never constructs a store.
    Each store is built independently and bound via ``functools.partial``; a store
    that cannot be constructed (missing optional dep or unreachable client) is bound
    as a FAILING STAND-IN carrying its construction cause, so the cause reaches
    ``attempt.leg_errors`` through the ordinary reporting path (review diagnostic gap) —
    never as a silent ``None``. A store that constructs but is unreachable at query time
    is handled by ``retrieve``'s existing per-leg try/except — augmentation never blocks
    the phase.

    Both legs share ONE ``Neo4jClient`` (review: perf — no two clients per factory call, one
    connection pool); ``Neo4jClient`` uses its own URI/auth constructor defaults
    (env-overridable per ``graph.py``).
    """
    from agentic_dynamics.knowledge.graph import Neo4jClient
    from agentic_dynamics.knowledge.neo4j_vectors import Neo4jVectorStore
    from agentic_dynamics.knowledge.retrieval import retrieve as _retrieve

    # Graph leg: lexical (full-text) search + bounded expansion over the knowledge graph.
    graph_client: Any = None
    graph_cause = ""
    graph_exc: BaseException | None = None
    try:
        graph_client = Neo4jClient()
    except Exception as exc:  # noqa: BLE001 — the cause is REPORTED through the leg
        graph_client = None
        graph_cause = f"{type(exc).__name__}: {exc}"
        graph_exc = exc

    # Dense leg: embeddings ride the SAME Knowledge nodes the lexical leg reads (operator
    # decision 2026-09-19 — the Chroma service is retired; one store, one client lifecycle).
    dense_store: Any = None
    dense_cause = ""
    dense_cause_exc: BaseException | None = None
    if graph_client is None:
        # One client serves both legs; its failure IS the dense leg's cause too.
        dense_cause = graph_cause or "the Neo4j client is unavailable"
        dense_cause_exc = graph_exc
    else:
        try:
            dense_store = Neo4jVectorStore(client=graph_client)
        except Exception as exc:  # noqa: BLE001 — the cause is REPORTED through the leg
            dense_store = None
            dense_cause = f"{type(exc).__name__}: {exc}"
            # Chain the typed cause so a construction-time embedder failure keeps its stable
            # token (retrieval reads ``__cause__``); the embedded default transport means this
            # path no longer imports the optional ``ollama`` package at all.
            dense_cause_exc = exc

    dense_leg = (
        dense_store
        if dense_store is not None
        else (
            _UnavailableDenseStore(dense_cause, cause_exc=dense_cause_exc) if dense_cause else None
        )
    )
    lexical_leg = (
        graph_client
        if graph_client is not None
        else (_UnavailableGraphClient(graph_cause) if graph_cause else None)
    )

    # k4 no-silent-empties: bind the durable-artifact source-type resolver so a candidate
    # whose store metadata carries no source_type is typed from the authoritative kb/ layer
    # (never an untyped participant in selection). The resolver is only consulted for
    # silent-metadata candidates and memoises per knowledge_id.
    source_type_resolver = _durable_source_type_resolver()

    # Bind whichever stores survived construction. ``retrieve`` already runs each leg
    # behind its own try/except, so a down store degrades to the surviving legs (and to
    # ``no_rag`` when both are down) rather than raising out of ``augment_prompt``.
    return functools.partial(
        _retrieve,
        dense_store=dense_leg,
        graph_client=lexical_leg,
        source_type_resolver=source_type_resolver,
    )


def default_construct_fn(
    rag_params: dict[str, Any], run_agent: Callable[..., Any]
) -> Callable[..., Any]:
    """Build a default constructor whose model call reuses the injected executor ``run_agent``.

    The constructor runs on ``DEFAULT_CONSTRUCTOR_MODEL`` (cheapest), so the wiring has
    a real end-to-end path when ``rag_augment`` is enabled without explicit injection.
    The id is resolved from that pinned live constant — never a module-literal id — so the
    retired ``deepseek/deepseek-v4-flash`` can never be selected here. An explicit override
    pointing at the retired family is REFUSED by :func:`resolve_constructor_model` BEFORE any
    executor call (a typed, named refusal — never a silent generic constructor fallback). The
    consumer path is guarded by
    ``tests/test_prompt_constructor.py::test_default_construct_fn_resolves_live_model_id`` and
    the retired-override refusal test.
    """
    from agentic_dynamics.knowledge.prompt_constructor import ModelPromptConstructor

    constructor_model = resolve_constructor_model(rag_params.get("constructor_model"))

    def run_constructor(prompt: str) -> str:
        ar = run_agent(
            prompt,
            model=constructor_model,
            backend=None,
            workdir=str(rag_params.get("workdir") or os.getcwd()),
            thinking_effort="low",
            thinking_budget_tokens=0,
            output_token_limit=int(rag_params.get("output_budget_tokens", 1500)),
            timeout=int(rag_params.get("constructor_timeout", 30)),
            silent_mode=True,
            enforce_pytest=False,
        )
        return str(getattr(ar, "final_response", "") or "")

    return ModelPromptConstructor(
        model=constructor_model, run_constructor=run_constructor
    ).construct
