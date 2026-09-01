"""The ``retrieve -> construct -> render`` augmentation seam for one agent phase.

Extracted from ``workflow_runner.py`` (R7 of ``docs/review/restructure.md``) so the
runtime-RAG knowledge base stays testable without a workflow run. :func:`augment_prompt`
is the entire augmentation; ``workflow_runner`` keeps only phase execution plus the
opt-in self-build emit.

The seam runs between ``route_step`` and ``run_agent`` (never before routing, so the
augmentation sees the selected executor model), gated by ``rag_augment`` (default OFF).
It is pure w.r.t. the worktree — no writes, no commits. Any retrieval or constructor
failure reverts to ``base_prompt`` and records a named fallback mode, so augmentation
never blocks a phase.

Read-only by construction: this module references ``publish_event`` zero times. The
sole KB writer is the opt-in ``emit_self`` path in ``workflow_runner``
(``knowledge_ingestion.emit_phase_finding``). The dense/lexical store wiring here is
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
    raw_prompt_hash: str = ""
    retrieval_attempt_id: str = ""
    constructor_attempt_id: str = ""
    selected_evidence_ids: list[str] = field(default_factory=list)
    versions: dict[str, str] = field(default_factory=dict)
    token_counts: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0


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
) -> AugmentationOutcome:
    """Run ``retrieve -> construct -> render`` between ``route_step`` and ``run_agent``.

    Pure w.r.t. the worktree (no writes). Any retrieval/constructor failure reverts to
    ``base_prompt`` and records a named fallback mode — augmentation never blocks the
    phase. ``retrieve_fn`` returns a ``RetrievalAttempt``-shaped object;
    ``construct_fn`` maps a ``ConstructionRequest`` to an ``AugmentedPrompt``.
    """
    from agentic_dynamics.knowledge.prompt_constructor import (
        DEFAULT_CONSTRUCTOR_MODEL,
        ConstructionRequest,
        hash_work_item,
    )

    outcome = AugmentationOutcome(
        prompt=base_prompt,
        fallback=True,
        fallback_mode="no_rag",
        raw_prompt_hash=hash_work_item(base_prompt),
    )
    t0 = time.time()
    try:
        # 1. retrieve (deterministic; may degrade but not raise on missing legs)
        attempt = retrieve_fn(
            raw_work_item=base_prompt,
            phase_objective=goal,
            commit_sha=commit_sha,
            repository_id=str(rag_params.get("repository_id", "")),
            acl_scope=str(rag_params.get("acl_scope", "")),
            executor_context_tokens=int(rag_params.get("executor_context_tokens", 200_000)),
            remaining_input_tokens=int(rag_params.get("remaining_input_tokens", 200_000)),
            rag_token_limit=int(rag_params.get("rag_token_limit", 8000)),
            pattern_projection=bool(rag_params.get("pattern_projection", False)),
        )
        if attempt is None:
            raise RuntimeError("retrieve returned no attempt")
        retrieval_mode = str(getattr(attempt, "fallback_mode", "") or "no_rag")
        outcome.retrieval_attempt_id = getattr(attempt, "retrieval_attempt_id", "") or _attempt_id(
            "retrieval", base_prompt, commit_sha
        )

        # 2. construct (one bounded model call + deterministic renderer)
        evidence = _evidence_from_attempt(attempt)
        constructor_model = str(rag_params.get("constructor_model", DEFAULT_CONSTRUCTOR_MODEL))
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
        outcome.versions = dict(getattr(augmented, "versions", {}) or {})
        outcome.token_counts = dict(getattr(augmented, "token_counts", {}) or {})
        outcome.cost_usd = float(getattr(augmented, "cost_usd", 0.0) or 0.0)
        if constructor_fell_back:
            outcome.versions = {**outcome.versions, "constructor": "deterministic-fallback"}
    except Exception:
        outcome.prompt = base_prompt
        outcome.fallback = True
        outcome.fallback_mode = "no_rag"
    finally:
        outcome.latency_ms = round((time.time() - t0) * 1000.0, 2)
    return outcome


def default_retrieve_fn() -> Callable[..., Any]:
    """Lazily construct the dense + graph stores and bind them to ``retrieve``.

    Called only on the ``rag_augment`` path (never at import time), so the optional
    deps (chromadb / neo4j) stay optional and core startup never constructs a store.
    Each store is built independently and bound via ``functools.partial``; a store
    that cannot be constructed (missing optional dep or unreachable client) is bound
    as ``None`` so :func:`retrieve` marks that leg down. A store that constructs but
    is unreachable at query time is handled by ``retrieve``'s existing per-leg
    try/except — augmentation never blocks the phase.

    Endpoint conventions: ``ChromaStore`` reads ``CHROMA_HOST``/``CHROMA_PORT``;
    ``Neo4jClient`` uses its own URI/auth constructor defaults (env-overridable per
    ``graph.py``).
    """
    from agentic_dynamics.knowledge.embeddings import ChromaStore
    from agentic_dynamics.knowledge.graph import Neo4jClient
    from agentic_dynamics.knowledge.retrieval import retrieve as _retrieve

    # Dense leg: runtime-RAG knowledge chunks live in their own collection, isolated
    # from the historical ``session_embeddings`` collection.
    dense_store = None
    try:
        dense_store = ChromaStore(collection_name="knowledge_chunks_v1")
    except Exception:
        dense_store = None

    # Graph leg: lexical (full-text) search + bounded expansion over the knowledge graph.
    graph_client = None
    try:
        graph_client = Neo4jClient()
    except Exception:
        graph_client = None

    # Bind whichever stores survived construction. ``retrieve`` already runs each leg
    # behind its own try/except, so a down store degrades to the surviving legs (and to
    # ``no_rag`` when both are down) rather than raising out of ``augment_prompt``.
    return functools.partial(_retrieve, dense_store=dense_store, graph_client=graph_client)


def default_construct_fn(
    rag_params: dict[str, Any], run_agent: Callable[..., Any]
) -> Callable[..., Any]:
    """Build a default constructor whose model call reuses the injected executor ``run_agent``.

    The constructor runs on ``DEFAULT_CONSTRUCTOR_MODEL`` (cheapest), so the wiring has
    a real end-to-end path when ``rag_augment`` is enabled without explicit injection.
    """
    from agentic_dynamics.knowledge.prompt_constructor import (
        DEFAULT_CONSTRUCTOR_MODEL,
        ModelPromptConstructor,
    )

    constructor_model = str(rag_params.get("constructor_model", DEFAULT_CONSTRUCTOR_MODEL))

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
