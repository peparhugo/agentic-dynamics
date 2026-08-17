"""Execute an ``agent_task`` workflow — the ``execute`` phase of the spec/compiler DAG.

Drives an agent through a workflow's phases inside a git worktree, commits after each
phase, and records the ledger (tokens, cost, ``test_executed_success``) per phase. This
is the reusable-workflow engine: compile a spec, then run it against any goal / model /
worktree.

Phase kinds (from ``workflow.params.phases``):
  - ``agent`` (default) — invoke the LLM with the phase prompt. The prompt may use the
    ``{goal}`` and ``{prior_phases}`` placeholders.
  - ``test`` — run the language's suite independently (via ``test_runner.run_suite``)
    and record ``test_executed_success``. No LLM involved.

The agent works directly in ``workdir``; prior-phase artifacts are committed there, so
later phases read them from the repo. Fails fast by default (``stop_on_error``).

RAG scope isolation (the load-bearing invariant): by default the retrieval filter is
scoped per cell — :func:`cell_scope` yields ``self-<worktree basename>`` (the cell
identity), overridden by ``FINOPS_CELL_ID`` when set — so an augmented cell reads only
its own worktree's knowledge, never the global store. ``run_workflow`` defaults both
``repository_id`` and ``acl_scope`` to that cell scope *before* the retrieve fn is
built, whenever ``rag_augment`` is enabled and ``repository_id`` is empty. An
explicitly non-empty ``rag_params.repository_id`` is preserved unchanged — that is the
*shared-scope* override for coordinated parallel workstreams. The empty scope must
never again mean "global".
"""

from __future__ import annotations

import functools
import hashlib
import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends import run_agentic
from .experiment_spec import ExperimentSpec, validate_spec
from .language import detect_language
from .live import LivePublisher
from .step_routing import (
    ModelSignals,
    RouteState,
    RoutingPreferences,
    resolve_pool,
    route_step,
    validate_workflow_routing,
)
from .test_runner import run_suite, suite_succeeded


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@dataclass
class PhaseResult:
    """Ledger record for one phase of a workflow run."""

    phase: str
    kind: str  # agent | test
    status: str  # ok | failed
    model: str = ""
    duration_s: float = 0.0
    commit_hash: str = ""
    error: str = ""
    # agent phases
    tokens: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_hit_rate: float = 0.0
    session_id: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    final_response: str = ""
    confidence: float | None = None  # [H] execution-confidence signal (agent phases)
    # augmentation provenance (populated only when rag_augment is enabled)
    raw_prompt_hash: str = ""
    pre_phase_commit: str = ""
    retrieval_attempt_id: str = ""
    constructor_attempt_id: str = ""
    selected_evidence_ids: list[str] = field(default_factory=list)
    augmentation_versions: dict[str, str] = field(default_factory=dict)
    augmentation_tokens: dict[str, int] = field(default_factory=dict)
    augmentation_cost_usd: float = 0.0
    augmentation_latency_ms: float = 0.0
    fallback_mode: str = ""
    # test phases
    test_executed_success: bool | None = None
    tests_passed: int = 0
    tests_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "kind": self.kind,
            "status": self.status,
            "model": self.model,
            "duration_s": self.duration_s,
            "commit_hash": self.commit_hash,
            "error": self.error,
            "tokens": self.tokens,
            "cost_usd": self.cost_usd,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cache_hit_rate": self.cache_hit_rate,
            "session_id": self.session_id,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "confidence": self.confidence,
            # augmentation provenance — persisted structured, never in-memory-only
            "raw_prompt_hash": self.raw_prompt_hash,
            "pre_phase_commit": self.pre_phase_commit,
            "retrieval_attempt_id": self.retrieval_attempt_id,
            "constructor_attempt_id": self.constructor_attempt_id,
            "selected_evidence_ids": self.selected_evidence_ids,
            "augmentation_versions": self.augmentation_versions,
            "augmentation_tokens": self.augmentation_tokens,
            "augmentation_cost_usd": self.augmentation_cost_usd,
            "augmentation_latency_ms": self.augmentation_latency_ms,
            "fallback_mode": self.fallback_mode,
            "test_executed_success": self.test_executed_success,
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
        }


@dataclass
class WorkflowRunResult:
    """Ledger for a full workflow run."""

    spec_name: str
    model: str
    workdir: str
    goal: str
    phases: list[PhaseResult] = field(default_factory=list)
    git_sha: str = ""
    started_at: str = ""
    ended_at: str = ""

    @property
    def total_cost_usd(self) -> float:
        return round(sum(p.cost_usd for p in self.phases), 6)

    @property
    def ok(self) -> bool:
        return bool(self.phases) and all(p.status == "ok" for p in self.phases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_name": self.spec_name,
            "model": self.model,
            "workdir": self.workdir,
            "goal": self.goal,
            "git_sha": self.git_sha,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "total_cost_usd": self.total_cost_usd,
            "ok": self.ok,
            "phases": [p.to_dict() for p in self.phases],
        }


def _build_phase_prompt(phase: dict[str, Any], goal: str, prior: list[str]) -> str:
    prompt = str(phase.get("prompt", ""))
    prior_summary = "\n".join(f"- {p}" for p in prior) if prior else "(none)"
    return prompt.replace("{goal}", goal).replace("{prior_phases}", prior_summary)


def _evidence_from_attempt(attempt: Any) -> list[Any]:
    """Extract :class:`EvidenceUnit`-shaped items from a retrieval attempt.

    ``retrieve()`` returns a ``RetrievalAttempt`` whose ``selected_evidence`` is a
    list of candidates carrying ``id``/``text``/``authority``/``locator``; the
    constructor consumes the equivalent shape. This adapter keeps the seam tolerant
    of either (real candidates or test doubles).
    """
    selected = getattr(attempt, "selected_evidence", []) or []
    from .prompt_constructor import EvidenceUnit  # lazy — avoids import-time coupling

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
            )
        )
    return units


def _augment_prompt(
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
    from .prompt_constructor import (
        ConstructionRequest,
        DEFAULT_CONSTRUCTOR_MODEL,
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
        outcome.constructor_attempt_id = getattr(augmented, "constructor_attempt_id", "") or _attempt_id(
            "constructor", base_prompt, commit_sha, constructor_model
        )
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


def _default_retrieve_fn() -> Callable[..., Any]:
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
    from .embeddings import ChromaStore
    from .graph import Neo4jClient
    from .retrieval import retrieve as _retrieve

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
    # ``no_rag`` when both are down) rather than raising out of ``_augment_prompt``.
    return functools.partial(_retrieve, dense_store=dense_store, graph_client=graph_client)


def _default_construct_fn(rag_params: dict[str, Any], run_agent: Callable[..., Any]) -> Callable[..., Any]:
    """Build a default constructor whose model call reuses the injected executor ``run_agent``.

    The constructor runs on ``DEFAULT_CONSTRUCTOR_MODEL`` (cheapest), so the wiring has
    a real end-to-end path when ``rag_augment`` is enabled without explicit injection.
    """
    from .prompt_constructor import DEFAULT_CONSTRUCTOR_MODEL, ModelPromptConstructor

    constructor_model = str(rag_params.get("constructor_model", DEFAULT_CONSTRUCTOR_MODEL))

    def run_constructor(prompt: str) -> str:
        ar = run_agent(
            prompt,
            model=constructor_model,
            backend=None,
            workdir="",
            thinking_effort="low",
            thinking_budget_tokens=0,
            output_token_limit=int(rag_params.get("output_budget_tokens", 1500)),
            timeout=int(rag_params.get("constructor_timeout", 30)),
            silent_mode=True,
            enforce_pytest=False,
        )
        return str(getattr(ar, "final_response", "") or "")

    return ModelPromptConstructor(model=constructor_model, run_constructor=run_constructor).construct


def _git_commit(workdir: Path, phase: str, goal: str) -> str:
    """Stage and commit the worktree; return the short hash, or "" if nothing to commit.

    ``.instrument/`` (the runner's own session transcripts) is excluded from the snapshot
    via a pathspec so ephemeral transcripts stop entering history (docs/routing_next_steps.md
    item 5.1). The exclusion is explicit here rather than relying on ``.gitignore``, since a
    fresh worktree may not yet carry the repo's ignore rules.
    """
    try:
        subprocess.run(
            ["git", "add", "-A", "--", ":(exclude).instrument"],
            cwd=workdir, capture_output=True, timeout=60,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=workdir, capture_output=True
        )
        if staged.returncode == 0:
            return ""
        msg = f"[workflow] {phase} — {goal[:60]}"
        c = subprocess.run(["git", "commit", "-q", "-m", msg], cwd=workdir, capture_output=True, timeout=120)
        if c.returncode != 0:
            return ""
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=workdir, capture_output=True, text=True)
        return h.stdout.strip()
    except Exception:
        return ""


def _git_head(workdir: Path) -> str:
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=workdir, capture_output=True, text=True)
        return h.stdout.strip()
    except Exception:
        return ""


def _completed_phases(workdir: Path, phase_names: list[str], goal: str) -> set[str]:
    """Return phase names that already have a ``[workflow] <phase>`` commit *for this goal*.

    The worktree inherits ``[workflow] <phase>`` commits from every workflow merged into
    main, and phase names collide across workflows (scope/rewrite/verify). Match the goal
    prefix in the commit subject so resume only skips this run's own phases.
    """
    try:
        log = subprocess.run(
            ["git", "log", "--format=%s"], cwd=workdir, capture_output=True, text=True
        )
    except Exception:
        return set()
    goal_prefix = goal[:40]
    completed: set[str] = set()
    for line in log.stdout.splitlines():
        m = re.search(r"\[workflow\]\s+(\S+)\s+—\s+(.+)", line)
        if m and m.group(1) in phase_names and m.group(2).startswith(goal_prefix):
            completed.add(m.group(1))
    return completed


def _cell_id(spec_name: str, model: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in f"{spec_name}_{model}")
    return f"wf_{slug.lower().strip('_')}"


def cell_scope(workdir: str | Path) -> str:
    """Return the per-cell retrieval scope for a worktree.

    The cell identity is the worktree basename (``f"self-{workdir.name}"``) — each
    augmented cell reads only its own worktree's knowledge, never the global store.
    ``FINOPS_CELL_ID`` overrides the basename when set (a worker that already pinned a
    cell id keeps that identity), so the scope stays ``self-<identity>`` either way.
    """
    identity = os.environ.get("FINOPS_CELL_ID") or Path(workdir).name
    return f"self-{identity}"


def run_workflow(
    spec: ExperimentSpec,
    *,
    goal: str,
    model: str,
    workdir: str | Path,
    backend: str | None = None,
    thinking_effort: str = "high",
    thinking_budget_tokens: int = 0,
    output_token_limit: int = 0,
    timeout: int = 1800,
    silent_mode: bool = False,
    enforce_pytest: bool = False,
    commit: bool = True,
    stop_on_error: bool = True,
    resume: bool = False,
    publish: bool = True,
    fork: bool | None = None,
    preferences: RoutingPreferences | None = None,
    signals: dict[str, ModelSignals] | None = None,
    run_agentic_fn: Callable[..., Any] | None = None,
    rag_augment: bool | None = None,
    retrieve_fn: Callable[..., Any] | None = None,
    construct_fn: Callable[..., Any] | None = None,
    rag_params: dict[str, Any] | None = None,
) -> WorkflowRunResult:
    """Run a compiled ``agent_task`` spec against a goal in a git worktree.

    ``resume=True`` skips phases that already have a ``[workflow] <phase>`` commit and
    re-enters from the first incomplete phase (carrying prior-phase context).
    ``publish=True`` emits live telemetry to Redis so the Control Room shows the run as a
    cell (``story_status`` hash + ``status``/``events:<cell>`` channels). Each phase
    publishes a ``step_finish`` event carrying its tokens/cost, which feeds the ticker.
    ``fork=True`` chains each agent phase off the previous phase's session (opencode
    ``--session <id> --fork``; Claude CLI ``--resume <id> --fork-session``; same model
    only) so the shared context prefix is served as provider cache reads. ``fork=None``
    falls back to the spec's ``workflow.params.fork`` flag.
    ``enforce_pytest=False`` (default) stops the runner from injecting the blanket
    "Run pytest. Fix failures." standardized constraint into agent phases — each phase
    must specify its own tests, and a phase can opt in via ``enforce_pytest: true`` on
    the phase. ``run_agentic_fn`` is injectable so tests can substitute a fake agent.

    RAG augmentation (``retrieve -> construct -> render``) runs between ``route_step``
    and ``run_agent`` only when ``spec.workflow.params.rag_augment`` (or ``rag_augment=``)
    is true — default OFF, so the executor prompt stays byte-for-byte identical to
    ``_build_phase_prompt``. ``retrieve_fn`` / ``construct_fn`` are injectable; ``rag_params``
    carries budgets, ``constructor_model``, ``pinned_policy``, ``inherited_tools``, and
    ``user_constraints``. Test phases are never augmented; any retrieval/constructor
    failure falls back to the base prompt and records a named fallback mode.

    Per-step routing (``docs/routing_design.md``): when the spec declares
    ``workflow.params.model_pool``, each agent phase's model is chosen by
    :func:`instrument.step_routing.route_step` from the phase's selector (``model`` pin /
    ``allowed_models`` subset / full pool), scored by ``preferences`` over ``signals``.
    The router prices the cache-prefix loss of a model switch, so the existing fork chain
    (``fork: true``) keeps forking for free when it stays on the prior model. Without a
    ``model_pool`` the workflow is single-model (``model``) — backward compatible.
    """
    errors = validate_spec(spec)
    errors += validate_workflow_routing(spec, default_model=model)
    if errors:
        raise ValueError("invalid spec: " + "; ".join(errors))

    phases = spec.workflow.params.get("phases", [])
    if not phases:
        raise ValueError("workflow.params.phases is empty")

    wd = Path(workdir).resolve()
    if not wd.is_dir():
        raise ValueError(f"workdir not found: {wd}")

    language = str(spec.workflow.params.get("language") or "")
    if not language:
        profile = detect_language(wd)
        language = profile.name if profile else "python"

    run_agent = run_agentic_fn or run_agentic

    # RAG augmentation seam. Default OFF — the prompt passed to the executor is then
    # byte-for-byte identical to ``_build_phase_prompt``. ``retrieve_fn``/``construct_fn``
    # are injectable for tests; when unset, production resolves the real retrieve +
    # a constructor whose model call reuses ``run_agent`` (default flash model).
    rag_augment = rag_augment if rag_augment is not None else bool(
        spec.workflow.params.get("rag_augment", False)
    )
    rag_params = dict(rag_params or spec.workflow.params.get("rag", {}) or {})
    # Thread the per-cell scope through the retrieval filter: an augmented cell reads
    # only its own worktree's knowledge. Both repository_id and acl_scope default to
    # the cell scope BEFORE the retrieve fn is built; an explicitly non-empty
    # repository_id is the shared-scope override (coordinated parallel workstreams)
    # and is preserved unchanged — the empty scope never again means "global".
    if rag_augment and not str(rag_params.get("repository_id", "")).strip():
        scope = cell_scope(wd)
        rag_params["repository_id"] = scope
        rag_params["acl_scope"] = scope
    pinned_policy = str(rag_params.get("pinned_policy", ""))
    inherited_tools = list(rag_params.get("inherited_tools") or DEFAULT_INHERITED_TOOLS)

    result = WorkflowRunResult(
        spec_name=spec.name, model=model, workdir=str(wd), goal=goal, started_at=_now()
    )

    cell_id = _cell_id(spec.name, model)
    publisher = LivePublisher(cell_id) if publish else None
    if publisher is not None and publisher.enabled:
        publisher.set_status("running")
        publisher.publish_event({
            "type": "text", "sessionID": cell_id,
            "part": {"text": f"workflow {spec.name} — {goal[:120]}"},
        })

    prior: list[str] = []
    start_idx = 0
    if resume:
        phase_names = [str(p.get("name", "?")) for p in phases]
        completed = _completed_phases(wd, phase_names, goal)
        for i, phase_def in enumerate(phases):
            name = str(phase_def.get("name", "?"))
            if name in completed:
                prior.append(f"{name} (ok)")
                start_idx = i + 1
            else:
                break

    fork_enabled = fork if fork is not None else bool(spec.workflow.params.get("fork", False))

    # Per-step routing context. The pool is the spec's ``model_pool`` when declared, else the
    # single run model (backward compatible). Preferences and the signal store may be passed
    # explicitly (tests) or carried in ``workflow.params`` (spec-driven).
    model_pool = resolve_pool(spec, default_model=model)
    if preferences is None:
        preferences = RoutingPreferences.from_dict(spec.workflow.params.get("preferences"))
    if signals is None:
        raw_signals = spec.workflow.params.get("signals") or {}
        signals = {m: ModelSignals.from_dict(d) for m, d in raw_signals.items()} if isinstance(
            raw_signals, dict
        ) else {}

    prev_session_id = ""
    prev_model = ""
    prev_cache_read_tokens = 0

    for phase_def in phases[start_idx:]:
        name = str(phase_def.get("name", "?"))
        kind = str(phase_def.get("kind", "agent"))
        phase_timeout = int(phase_def.get("timeout", timeout))
        pr = PhaseResult(phase=name, kind=kind, status="ok")
        t0 = time.time()

        try:
            if kind == "test":
                suite = run_suite(wd, language, timeout=phase_timeout)
                pr.tests_passed = suite["passed"]
                pr.tests_total = suite["total"]
                pr.test_executed_success = suite_succeeded(suite)
                if suite.get("failed", 0) > 0 or suite.get("errors", 0) > 0:
                    pr.status = "failed"
                    pr.error = suite.get("tail", "")[-400:]
            else:
                prompt = _build_phase_prompt(phase_def, goal, prior)
                # Point the agent's built-in publisher at this workflow's cell so the
                # fine-grained session events stream into the Control Room.
                prev_cell = os.environ.get("FINOPS_CELL_ID")
                os.environ["FINOPS_CELL_ID"] = cell_id
                try:
                    # Select this step's model: pin wins, allowed_models restricts, else the
                    # full pool — scored over measured signals, pricing a model switch's cache
                    # loss (§2/§4 of docs/routing_design.md).
                    state = RouteState(
                        pool=model_pool,
                        prev_model=prev_model or None,
                        prev_session_id=prev_session_id,
                        prev_cache_read_tokens=prev_cache_read_tokens,
                    )
                    model_i = route_step(phase_def, state, preferences, signals=signals)

                    # RAG augmentation seam — retrieve -> construct -> render, placed
                    # between route_step and run_agent (never before routing, so the
                    # augmentation sees the selected executor model). Test phases bypass
                    # this entirely (they live in the ``kind == "test"`` branch).
                    if rag_augment:
                        pre_commit = _git_head(wd)
                        pr.pre_phase_commit = pre_commit
                        outcome = _augment_prompt(
                            base_prompt=prompt,
                            goal=goal,
                            phase_def=phase_def,
                            model=model_i,
                            commit_sha=pre_commit or result.git_sha,
                            inherited_tools=inherited_tools,
                            pinned_policy=pinned_policy,
                            rag_params=rag_params,
                            retrieve_fn=retrieve_fn or _default_retrieve_fn(),
                            construct_fn=construct_fn or _default_construct_fn(rag_params, run_agent),
                        )
                        prompt = outcome.prompt
                        pr.raw_prompt_hash = outcome.raw_prompt_hash
                        pr.retrieval_attempt_id = outcome.retrieval_attempt_id
                        pr.constructor_attempt_id = outcome.constructor_attempt_id
                        pr.selected_evidence_ids = outcome.selected_evidence_ids
                        pr.augmentation_versions = outcome.versions
                        pr.augmentation_tokens = outcome.token_counts
                        pr.augmentation_cost_usd = outcome.cost_usd
                        pr.augmentation_latency_ms = outcome.latency_ms
                        pr.fallback_mode = outcome.fallback_mode

                    agent_kwargs: dict[str, Any] = {
                        "model": model_i,
                        "backend": backend,
                        "workdir": str(wd),
                        "thinking_effort": thinking_effort,
                        "thinking_budget_tokens": thinking_budget_tokens,
                        "output_token_limit": output_token_limit,
                        "timeout": phase_timeout,
                        "silent_mode": silent_mode,
                        "enforce_pytest": bool(
                            phase_def.get("enforce_pytest", enforce_pytest)
                        ),
                    }
                    # Cache-aware forking: reuse the previous phase's session prefix so
                    # the shared context is served as provider cache reads (DeepSeek
                    # cache read ~120x cheaper than input). A model switch breaks the
                    # cache prefix, so only fork when the model is unchanged. Both
                    # backends support it (opencode --session/--fork; claude --resume/--fork-session).
                    if (
                        fork_enabled
                        and prev_session_id
                        and prev_model == model_i
                    ):
                        agent_kwargs["session_id"] = prev_session_id
                        agent_kwargs["fork"] = True
                    ar = run_agent(prompt, **agent_kwargs)
                finally:
                    if prev_cell is None:
                        os.environ.pop("FINOPS_CELL_ID", None)
                    else:
                        os.environ["FINOPS_CELL_ID"] = prev_cell
                pr.model = model_i
                pr.tokens = {
                    "in": getattr(ar, "prompt_tokens", 0),
                    "out": getattr(ar, "completion_tokens", 0),
                    "reasoning": getattr(ar, "reasoning_tokens", 0),
                    "answer": getattr(ar, "answer_tokens", 0),
                    "explanation": getattr(ar, "explanation_tokens", 0),
                    "total": getattr(ar, "total_tokens", 0),
                }
                pr.cost_usd = getattr(ar, "estimated_cost_usd", 0.0)
                pr.confidence = getattr(ar, "confidence", None)
                pr.cache_read_tokens = getattr(ar, "cache_read_tokens", 0)
                pr.cache_write_tokens = getattr(ar, "cache_write_tokens", 0)
                pr.cache_hit_rate = round(getattr(ar, "cache_hit_rate", 0.0), 4)
                sid = getattr(ar, "session_id", "")
                if sid:
                    pr.session_id = sid
                    prev_session_id = sid
                prev_model = model_i
                prev_cache_read_tokens = getattr(ar, "cache_read_tokens", 0)
                pr.files_created = list(getattr(ar, "files_created", []) or [])
                pr.files_modified = list(getattr(ar, "files_modified", []) or [])
                pr.final_response = getattr(ar, "final_response", "")
                if not getattr(ar, "ok", True):
                    pr.status = "failed"
                    pr.error = getattr(ar, "error", "") or f"exit_code={getattr(ar, 'exit_code', '?')}"
        except Exception as exc:  # one bad phase must not crash the runner
            pr.status = "failed"
            pr.error = repr(exc)

        pr.duration_s = round(time.time() - t0, 2)
        if commit and pr.status == "ok":
            pr.commit_hash = _git_commit(wd, name, goal)

        prior.append(f"{name} ({pr.status})")
        result.phases.append(pr)

        if publisher is not None and publisher.enabled:
            tokens = pr.tokens or {}
            publisher.publish_event({
                "type": "step_finish", "sessionID": cell_id,
                "part": {
                    "text": f"phase {name} {pr.status}",
                    "tokens": {
                        "input": tokens.get("in", 0),
                        "output": tokens.get("out", 0),
                        "reasoning": tokens.get("reasoning", 0),
                        "total": tokens.get("total", 0),
                    },
                    "cost": pr.cost_usd,
                },
            })

        if pr.status == "failed" and stop_on_error:
            break

    result.ended_at = _now()
    result.git_sha = _git_head(wd)
    if publisher is not None and publisher.enabled:
        publisher.set_status("done" if result.ok else "failed")
    return result
