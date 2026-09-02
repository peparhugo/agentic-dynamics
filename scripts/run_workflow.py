"""Run an agent_task workflow (the execute phase) against a goal in a git worktree.

Usage:
    python scripts/run_workflow.py --spec workflows/repository/control_room_portal.yaml \
        --goal "Enhance the admin portal into a Control Room..." \
        --model openai/gpt-5.6-sol --workdir /tmp/pipeline/feature_admin-portal-control-plane

Writes the run ledger to ``experiments/results/workflows/<spec>/<timestamp>.json``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

# kb_produce_facts.py is a SIBLING script, not a package export — same dual-path dance as
# `_bootstrap` above: a direct `python scripts/run_workflow.py` run has `scripts/` itself on
# `sys.path[0]` (the bare `import` resolves); a test or caller that imports this file as
# `scripts.run_workflow` has the repo ROOT on `sys.path` instead (the `scripts.`-qualified
# fallback resolves). Imported here, not lazily inside `_fact_payloads`, because the hook
# is default-ON (§4 of the design doc) — it is the common path, not a conditional CAP opt-in like
# `control.rules`/`control.context_compiler` below.
try:
    import kb_produce_facts  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.run_workflow — repo root is on sys.path
    from scripts import kb_produce_facts  # noqa: E402

from agentic_dynamics.control import fact_ingestion as fi  # noqa: E402
from agentic_dynamics.control import outbox as ob  # noqa: E402
from agentic_dynamics.control.control_db import (  # noqa: E402
    ControlDB,
    ControlDBError,
    RunState,
    run_state_from_ledger_state,
)
from agentic_dynamics.control.live import LivePublisher  # noqa: E402
from agentic_dynamics.control.phase_evidence import make_phase_evidence_recorder  # noqa: E402
from agentic_dynamics.control.reducers._common import REVISION_FALLBACK  # noqa: E402
from agentic_dynamics.control.reducers._common import cell_id as _reducer_cell_id  # noqa: E402
from agentic_dynamics.control.run_lifecycle import RunHeartbeatThread  # noqa: E402
from agentic_dynamics.control.signal_store import build_signal_store, load_results  # noqa: E402
from agentic_dynamics.control.step_routing import ModelSignals, route_step  # noqa: E402
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, load_spec  # noqa: E402
from agentic_dynamics.experiment.spec_status import refresh_spec_status  # noqa: E402
from agentic_dynamics.knowledge import spec_ingestion as si  # noqa: E402
from agentic_dynamics.knowledge.knowledge_ingestion import _authorized_kb_write  # noqa: E402
from agentic_dynamics.knowledge.record_factory import _now_iso  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import cell_scope, run_workflow  # noqa: E402

#: CAP fact auto-emit (docs/architecture/current/cap_fact_auto_emit_design.md §4): the disable-flag
#: env var. Deliberately the ONE default-ON flag in the FINOPS_* family (every other gate —
#: FINOPS_KB_WRITE, FINOPS_ACTUATION_ARMED — is opt-in, "1"-truthy, default OFF): the fact store
#: must stay current WITHOUT an operator remembering to run kb_produce_facts.py by hand after
#: every run. Set to the literal string "0" to disable; any other value (including unset) is ON.
FACT_AUTO_EMIT_ENV = "FINOPS_FACT_AUTO_EMIT"

# P0-1 exit-code contract (control-plane stabilization): one process, one final machine
# envelope + one explicit exit code, so a parent (the orchestrator, a shell, CI) can tell
# succeeded / awaiting / failed apart WITHOUT parsing the child's stdout. The child prints
# the envelope (``WorkflowRunResult.to_dict()``) as its last JSON document; the exit code
# is the secondary signal a parent uses before (or instead of) parsing it.
EXIT_OK = 0
EXIT_AWAITING_APPROVAL = 10
EXIT_FAILED = 20
EXIT_INVALID_REQUEST = 30
EXIT_CANCELLED = 40


def exit_code_for_result(result: Any) -> int:
    """Map a run result to the P0-1 exit-code contract.

    Precedence: ``awaiting`` (a designed stop, never a failure) maps to 10 BEFORE the
    ``ok`` check — ``awaiting`` carries ``ok: False`` by construction, and collapsing it
    to 20 would misreport a checkpoint pause as a definitive failure.
    """
    if getattr(result, "awaiting", False):
        return EXIT_AWAITING_APPROVAL
    if not getattr(result, "ok", False):
        return EXIT_FAILED
    return EXIT_OK


def parse_child_envelope(stdout: str) -> dict[str, Any] | None:
    """Parse the child's final result envelope from its stdout (best effort).

    The child prints ``json.dumps(result.to_dict(), indent=2)`` as its last JSON
    document. Robust to preceding output AND to nested ``{`` lines inside the envelope:
    scan candidate opening braces from the END, trying each as the envelope's first line
    until one parses. Returns ``None`` when no envelope is found (an old child, a crash
    before the print) — the caller must then fall back to the exit code.
    """
    if not stdout:
        return None
    lines = stdout.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() != "{":
            continue
        try:
            obj = json.loads("\n".join(lines[i:]))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "ok" in obj:
            return obj
    return None


def classify_child_outcome(
    returncode: int | None, stdout: str
) -> dict[str, Any]:
    """Classify a spawned sibling's outcome: the P0-1 fail-closed decision.

    Precedence, fail-closed on conflict:
    1. the contract exit code is AUTHORITATIVE for a contract child — 10 means awaiting
       (a designed stop), anything other than 0/10 means failed. A child that wrote an
       ``awaiting`` envelope but exited 20 broke AFTER writing it: failed.
    2. the envelope is the fallback for a PRE-CONTRACT child (exit 0 with ``ok: false``
       or ``awaiting: true``) — the exact false-success shape P0-1 removes.
    Never trust ``returncode == 0`` alone: a pre-contract child exits 0 with a failed or
    awaiting result, and the envelope is the only thing that says so.
    """
    envelope = parse_child_envelope(stdout)
    if returncode == EXIT_AWAITING_APPROVAL:
        return {"state": "awaiting", "envelope": envelope}
    if returncode not in (None, EXIT_OK):
        return {"state": "failed", "envelope": envelope}
    if envelope is not None:
        if envelope.get("awaiting") is True:
            return {"state": "awaiting", "envelope": envelope}
        if envelope.get("ok") is False:
            return {"state": "failed", "envelope": envelope}
    return {"state": "ok", "envelope": envelope}



def _spec_declares_routing(spec: ExperimentSpec) -> bool:
    """True when the spec activates per-step routing (mirrors ``validate_workflow_routing``).

    Routing is active when the workflow declares a ``model_pool``, any per-phase
    ``model``/``allowed_models`` selector, or a ``preferences`` block. Only then do we bother
    building the signal store; single-model specs run unchanged (cold router).
    """
    params = spec.workflow.params
    if params.get("model_pool"):
        return True
    if params.get("preferences"):
        return True
    return any(
        "model" in p or "allowed_models" in p for p in (params.get("phases") or [])
    )


def _load_signals(path: str) -> dict[str, ModelSignals]:
    """Load an explicit signals override from a JSON file: ``{model: {field: value, …}}``."""
    with open(path) as fh:
        raw = json.load(fh)
    return {m: ModelSignals.from_dict(d) for m, d in raw.items()}


#: The versioned-graph env-var family (Neo4jClient at
#: ``agentic_dynamics/knowledge/graph.py:156`` — "local dev only — override via ENV for prod").
#: URI resolution precedence: ``--change-analysis-graph`` (CLI) > ``FINOPS_NEO4J_URI`` >
#: ``FINOPS_NEO4J_URL``. Credentials come ONLY from ``FINOPS_NEO4J_USER`` /
#: ``FINOPS_NEO4J_PASSWORD`` when set — nothing secret is hard-coded here; without them the
#: client's own constructor defaults apply.
NEO4J_URI_ENV = ("FINOPS_NEO4J_URI", "FINOPS_NEO4J_URL")
NEO4J_USER_ENV = "FINOPS_NEO4J_USER"
NEO4J_PASSWORD_ENV = "FINOPS_NEO4J_PASSWORD"


def resolve_graph_uri(cli_value: str | None) -> str | None:
    """Resolve the versioned-graph URI: CLI > ``FINOPS_NEO4J_URI`` > ``FINOPS_NEO4J_URL`` > None.

    ``None`` means no graph analysis was explicitly requested anywhere — the caller then
    leaves the graph client unconstructed (delta-only facts, exactly the pre-graph behavior).
    """
    if cli_value:
        return cli_value
    for env in NEO4J_URI_ENV:
        value = os.environ.get(env)
        if value:
            return value
    return None


def _build_graph_client(uri: str) -> Any | None:
    """Construct the ``Neo4jClient`` for a resolved URI, or None when the graph is unavailable.

    A missing optional ``neo4j`` dependency, an unparseable URI, or a server unreachable at
    construction all degrade to ``None`` — the analyzer then emits delta-only facts and the
    run carries an explicit ``graph_status``, never a CLI crash. Credentials are threaded ONLY
    from ``FINOPS_NEO4J_USER`` / ``FINOPS_NEO4J_PASSWORD`` when set; otherwise the client's own
    constructor defaults apply.
    """
    try:
        from agentic_dynamics.knowledge.graph import Neo4jClient
    except Exception:  # noqa: BLE001 — optional dependency; graph-unavailable is a state
        return None
    kwargs: dict[str, str] = {"uri": uri}
    user = os.environ.get(NEO4J_USER_ENV)
    password = os.environ.get(NEO4J_PASSWORD_ENV)
    if user:
        kwargs["user"] = user
    if password:
        kwargs["password"] = password
    try:
        return Neo4jClient(**kwargs)
    except Exception:  # noqa: BLE001 — unreachable graph degrades, never crashes the CLI
        return None


def _build_change_analyzer(args: argparse.Namespace) -> tuple[Any | None, Any | None]:
    """Composition-root wiring for the phase-boundary evidence seam (design §5.7, cap_2a p1).

    Returns ``(analyzer, graph_client)``. The analyzer is built ONLY when ``--change-analysis``
    is passed (the seam opt-in); the graph client is built ONLY when the analyzer is enabled
    AND a graph URI is explicitly requested (``--change-analysis-graph`` or the
    ``FINOPS_NEO4J_URI``/``FINOPS_NEO4J_URL`` env vars). Any graph-construction failure
    degrades to ``graph_client=None`` — delta-only facts, the pre-existing fallback. Without
    ``--change-analysis`` BOTH are None and the run is byte-identical to the pre-seam behavior
    (the no-op default is preserved even when the graph env vars are set).
    """
    if not args.change_analysis:
        return None, None
    from agentic_dynamics.control.evidence_analyzer import EvidenceChangeAnalyzer

    graph_client = None
    uri = resolve_graph_uri(args.change_analysis_graph)
    if uri:
        graph_client = _build_graph_client(uri)
    return EvidenceChangeAnalyzer(
        graph_client=graph_client,
        graph_requested=bool(uri),
    ), graph_client


def _build_phase_admission(spec: ExperimentSpec, args: argparse.Namespace):
    """Composition-root wiring for the per-phase spend gate (admission_leases p2).

    Returns the ``runtime.admission.PhaseAdmission`` callable the runner wraps each agent phase
    in, or ``None`` when no gate should be injected. ``None`` in two cases, both of which leave
    the run byte-identical to the pre-admission behaviour:

    * ``--no-admission`` — the explicit per-invocation escape (a repair run, a replay).
    * the gate is disarmed (``FINOPS_ADMISSION_REQUIRED`` unset/falsey) — the default posture
      while the freeze holds. Checked HERE as well as inside the gate so a disarmed run never
      even opens a Redis connection: the composition root should not require infrastructure for
      a feature the operator has not turned on.

    When the gate IS armed this function is deliberately **not** best-effort. Unlike the graph
    client (which degrades to delta-only facts) or the fact emitter (which degrades to a printed
    warning), an unreachable lease registry means the spend gate cannot be consulted — and the
    whole point of a fail-closed gate is that "cannot ask" is refused, not waved through. So
    ``LeaseRegistry.from_env``'s ``LeaseUnavailableError`` propagates and the run does not start.

    ``--campaign-budget-usd`` / ``--campaign-concurrency`` install the campaign scope's caps
    before the first phase. Without them the scope's already-installed caps apply, and an
    uncapped scope admits nothing — the registry has no default cap on purpose ("an admission
    layer whose unconfigured state is unlimited is not an admission layer").
    """
    if args.no_admission:
        print("admission: gate NOT injected (--no-admission)", file=sys.stderr)
        return None

    from agentic_dynamics.core.admission_context import admission_required

    if not admission_required():
        # The default while the freeze holds. Stated, not silent — an operator reading the run
        # log can see that no lease accounted for this run's spend.
        print(
            "admission: gate disarmed (FINOPS_ADMISSION_REQUIRED unset) — phases run unleased",
            file=sys.stderr,
        )
        return None

    from agentic_dynamics.control.admission import AdmissionController, make_phase_admission
    from agentic_dynamics.control.lease_registry import (
        LeaseKind,
        LeaseRegistry,
        LeaseScope,
        ScopeKind,
    )

    registry = LeaseRegistry.from_env()
    scope = LeaseScope(ScopeKind.CAMPAIGN, spec.name)
    if args.campaign_budget_usd is not None:
        registry.set_cap(LeaseKind.BUDGET, scope, float(args.campaign_budget_usd))
    if args.campaign_concurrency is not None:
        registry.set_cap(LeaseKind.CONCURRENCY, scope, float(args.campaign_concurrency))

    print(
        f"admission: ARMED — campaign scope {scope} "
        f"(budget cap {registry.get_cap(LeaseKind.BUDGET, scope)}, "
        f"concurrency cap {registry.get_cap(LeaseKind.CONCURRENCY, scope)})",
        file=sys.stderr,
    )
    return make_phase_admission(
        spec_name=spec.name,
        worktree_identity=Path(args.workdir).name,
        result_namespace=cell_scope(args.workdir),
        controller=AdmissionController(registry),
        campaign_scope=scope,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Run an agent_task workflow spec against a goal.")
    ap.add_argument("--spec", required=True, help="path to an ExperimentSpec YAML")
    ap.add_argument("--goal", required=True, help="feature/task prompt (substituted for {goal})")
    ap.add_argument("--model", required=True, help="provider/model id")
    ap.add_argument("--workdir", required=True, help="git worktree to run in")
    ap.add_argument("--backend", default=None, help="opencode | claude_cli (default: auto)")
    ap.add_argument("--thinking-effort", default="high")
    ap.add_argument("--thinking-budget-tokens", type=int, default=0)
    ap.add_argument("--output-token-limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=1800, help="per-phase timeout (s)")
    ap.add_argument("--phase-watchdog-min", type=float, default=None, metavar="MIN",
                    help="phase watchdog threshold in minutes (cap_runner_hardening p1): an "
                         "agent phase whose session transcript shows no new step for this long "
                         "is SIGTERM'd and fails with STALLED + evidence. Default "
                         "FINOPS_PHASE_WATCHDOG_MIN env, else 20; 0 disables the watchdog.")
    ap.add_argument("--no-commit", action="store_true", help="do not commit after phases")
    ap.add_argument("--resume", action="store_true",
                    help="skip phases that already have a [workflow] <phase> commit; when the "
                         "worktree has no such commits, fall back to the phases the derived "
                         "spec index (experiments/specs/index.json) shows as ok for this goal")
    ap.add_argument("--signals", default=None,
                    help="path to a JSON file mapping model id -> measured signals "
                         "(overrides the auto-built signal store)")
    ap.add_argument("--cap-snapshot", action="store_true",
                    help="CAP I4 (design §9): compile + best-effort record a route_next_job/v1 "
                         "ControlContext snapshot beside every routing decision. Read-only "
                         "measurement — nothing consumes the snapshot yet, and a snapshot "
                         "failure never affects the run. OFF by default: this is the first CAP "
                         "hook to touch a real production run + a real Redis connection.")
    ap.add_argument("--cap-shadow", action="store_true",
                    help="CAP I6 (design §9): everything --cap-snapshot does, PLUS runs the "
                         "fact-based route_next_job_v1 rule beside route_step, validates its "
                         "proposal (C1-C10), and records it as a shadow decision artifact — "
                         "never applied, never arms actuation. The actual route is always "
                         "route_step's, unchanged. Implies --cap-snapshot. OFF by default.")
    ap.add_argument("--no-fact-emit", action="store_true",
                    help="disable the CAP fact auto-emit hook (docs/architecture/current/"
                         "cap_fact_auto_emit_design.md) for THIS invocation only. The hook is "
                         "default-ON — every completed run derives its own attempt/job/policy/"
                         "workflow facts and emits them, best-effort, scoped to this run's own "
                         "repository_id (cell_scope). Also controlled by the "
                         f"{FACT_AUTO_EMIT_ENV}=0 environment variable (a per-process override, "
                         "e.g. for a worker that must never write to the KB); this CLI flag "
                         "always wins when both are set.")
    ap.add_argument("--change-analysis", action="store_true",
                    help="evidence-integrity e6 seam (design §5.7, review F3): inject the "
                         "concrete EvidenceChangeAnalyzer at the composition root so every "
                         "committed phase ALSO hands its typed delta to the phase-boundary "
                         "evidence loop — code_change_facts/v2 facts + ACL-scoped executor "
                         "neighborhood recorded on the phase result. Best-effort — a failed "
                         "analysis never affects the phase. OFF by default (opt-in). Without "
                         "this flag the seam is byte-identical inert, even when "
                         "--change-analysis-graph or the FINOPS_NEO4J_* env vars are set.")
    ap.add_argument("--change-analysis-graph", default=None, metavar="URI",
                    help="cap_2a p1 (design §5.7): versioned-graph client URI for the "
                         "phase-boundary evidence loop (bolt://host:port). Resolved CLI > "
                         "FINOPS_NEO4J_URI > FINOPS_NEO4J_URL; credentials (when set) from "
                         "FINOPS_NEO4J_USER / FINOPS_NEO4J_PASSWORD, otherwise the client's "
                         "own constructor defaults. Only consulted when --change-analysis is "
                         "also passed; a missing optional dep / unparseable URI / unreachable "
                         "graph degrades to delta-only facts with an explicit graph_status "
                         "(unavailable) — never a CLI crash.")
    ap.add_argument("--no-admission", action="store_true",
                    help="admission_leases p2: do NOT inject the per-phase spend gate for THIS "
                         "invocation. The gate itself is armed by the operator's "
                         "FINOPS_ADMISSION_REQUIRED=1 environment (default: disarmed, and then "
                         "this flag changes nothing) — this flag is the per-invocation escape "
                         "for a run that must execute outside the campaign's lease accounting "
                         "(a repair run, a replay). It is deliberately a CLI flag and not an "
                         "env var: skipping the gate should appear in the shell history of "
                         "whoever skipped it.")
    ap.add_argument("--campaign-budget-usd", type=float, default=None, metavar="USD",
                    help="admission_leases p2: the dollar ceiling installed on this workflow's "
                         "campaign budget scope before the run (per-token models only; "
                         "subscription models have no dollar cap by construction). Without it "
                         "the scope's already-installed cap applies, and an uncapped scope "
                         "admits nothing — unconfigured never means unlimited.")
    ap.add_argument("--campaign-concurrency", type=int, default=None, metavar="N",
                    help="admission_leases p2: the slot ceiling installed on this workflow's "
                         "campaign concurrency scope before the run. Size it with "
                         "control.lease_registry.recommended_concurrency() (the measured "
                         "beta_tokens=0.80 puts the knee at 6): the coordination tax is paid "
                         "in throughput, not dollars.")
    ap.add_argument("--orchestrator", action="store_true",
                    help="slice 2 (D-3/D-14/D-16): run each agent phase as a SIBLING cell "
                         "container with its scope config (via scripts/fleet/spawn_wrapper.py) "
                         "instead of in-process. OPT-IN — the default path is unchanged. The "
                         "orchestrator container mounts the docker socket (ro); a phase whose "
                         "scope fails validation refuses BEFORE the socket call.")
    ap.add_argument("--only-phase", default=None, metavar="NAME",
                    help="run a SINGLE phase (name) only — the sibling-cell entrypoint the "
                         "--orchestrator mode spawns for each phase. When set, the spec's phase "
                         "list is filtered to this name before the run.")
    ap.add_argument("--cell-image", default=None, metavar="IMAGE",
                    help="p3_base_image_caching: the image each PHASE cell runs under "
                         "--orchestrator mode (default: scripts/fleet/spawn_wrapper.CELL_IMAGE, "
                         "fleet/base). A per-job image built FROM fleet/base — see "
                         "scripts/fleet/build.sh job <name> — is named fleet/job-<name> and is "
                         "the only namespace the submit contract's `image` field accepts "
                         "(scripts/fleet/spawn_wrapper.py:JOB_IMAGE_PATTERN). Never changes the "
                         "orchestrator/workflow-runner container's OWN image (fleet/orchestrator "
                         "— the one socket-holder, unaffected by this flag).")
    args = ap.parse_args()

    spec = load_spec(Path(args.spec))

    # --orchestrator: the sibling-container execution path (slice 2). P0-2 (control-plane
    # stabilization): this is NO LONGER a second phase loop. It injects a DockerAgentExecutor
    # into the SAME engine below — the engine owns the loop, stop-on-failure, checkpoints,
    # gates, and the aggregate ledger; the executor only answers "run this one step in this
    # isolation envelope". The gate is threaded the same way as the in-process path: the
    # executor reads the phase's admission (bound to the ContextVar by the engine's
    # ``phase_admission_scope``) and stamps it onto the SPAWN REQUEST — a container inherits
    # an environment, not a call stack.
    if args.orchestrator:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "fleet"))
        from fleet.docker_executor import DockerAgentExecutor  # noqa: E402

        spec_path = f"/repo/{args.spec}"  # the sibling's view (the orchestrator mounts /repo)
        return _run_workflow_cli(
            spec, args,
            step_executor=DockerAgentExecutor(
                spec_path=spec_path,
                spec_name=spec.name,
                goal=args.goal,
                model=args.model,
                workdir=args.workdir,
                backend=args.backend,
                timeout=args.timeout,
                cell_image=args.cell_image,
            ),
        )

    return _run_workflow_cli(spec, args)


def _run_workflow_cli(
    spec: ExperimentSpec, args: argparse.Namespace, *, step_executor=None
) -> None:
    """The ONE engine's CLI wrapper (P0-2): build the composition root and run the engine.

    Shared by the in-process path (``step_executor=None`` → the engine's default
    LocalAgentExecutor) and the ``--orchestrator`` path (the DockerAgentExecutor injected
    above).     This is the single phase loop, ledger writer, and exit-code contract — the
    second phase loop is gone.
    """
    # --only-phase: filter the spec's phases to the named phase (the sibling-cell path). The
    # rest of the composition root (routing/signals/etc.) is unchanged — a single-phase run is
    # a normal run whose phase list happens to have one member. The FULL list's count and the
    # phase's true position are carried through so the Control Room publishes "i of N".
    only_phase_total: int | None = None
    only_phase_index: int | None = None
    if args.only_phase:
        phases = spec.workflow.params.get("phases") or []
        names = [str(p.get("name", "")) for p in phases]
        if args.only_phase not in names:
            raise SystemExit(
                f"--only-phase {args.only_phase!r}: no such phase (have {names})"
            )
        only_phase_index = names.index(args.only_phase)
        only_phase_total = len(phases)
        spec.workflow.params["phases"] = [phases[only_phase_index]]

    # Signal-store wiring (docs/routing_next_steps.md item 1): when the spec declares routing
    # and no explicit --signals override was supplied, build the store from the measured
    # corpus so the router consumes real data instead of cold-starting. The explicit
    # signals/preferences kwargs on run_workflow remain the override hook.
    signals: dict[str, ModelSignals] | None = None
    if args.signals:
        signals = _load_signals(args.signals)
    elif _spec_declares_routing(spec):
        try:
            signals = build_signal_store(load_results())
        except (FileNotFoundError, json.JSONDecodeError):
            # No measured corpus available — let the router cold-start deterministically.
            signals = None

    router = route_step
    if bool(spec.workflow.params.get("control_route", False)):
        # CAP I7 seam (design §9 I7): a PER-SPEC opt-in — only a spec that explicitly sets
        # `workflow.params.control_route: true` ever has the plane's route choice applied, and
        # only when a fresh validate_decision() admits it. OFF by default; no committed spec
        # sets this field (docs/designs/implemented/implementation_notes.md's flip procedure).
        # Takes priority over --cap-shadow/--cap-snapshot: those are per-INVOCATION measurement
        # opt-ins, this is the per-SPEC apply opt-in.
        from agentic_dynamics.control.rules import make_applying_router

        router = make_applying_router(
            workload=spec.name,
            cell_id=_reducer_cell_id(spec.name, args.model),
            repository_id=cell_scope(args.workdir),
        )
    elif args.cap_shadow:
        # CAP I6 seam: a drop-in Router that ALSO runs + validates + records the fact-based
        # shadow decision (design §9 I6 row) — a superset of --cap-snapshot. Built here, at the
        # composition root, exactly where `route_step` is injected — `runtime.workflow_runner`
        # never imports `control` either way (Debt-2).
        from agentic_dynamics.control.rules import make_shadow_router

        router = make_shadow_router(
            workload=spec.name,
            cell_id=_reducer_cell_id(spec.name, args.model),
            repository_id=cell_scope(args.workdir),
        )
    elif args.cap_snapshot:
        # CAP I4 seam: a drop-in Router that also compiles + records a snapshot (design §9 I4
        # row). Built here, at the composition root, exactly where `route_step` is injected —
        # `runtime.workflow_runner` never imports `control` either way (Debt-2).
        from agentic_dynamics.control.context_compiler import make_snapshotting_router

        router = make_snapshotting_router(
            workload=spec.name,
            cell_id=_reducer_cell_id(spec.name, args.model),
            repository_id=cell_scope(args.workdir),
        )

    # Phase-boundary evidence (design §5.7 — e6 of cap_evidence_integrity, review F3): the
    # concrete ChangeAnalyzer is injected HERE, at the composition root, exactly where
    # `route_step`/`publisher_factory` are — `runtime.workflow_runner` consumes only the
    # runtime-owned protocol. Opt-in via --change-analysis (default: the seam is inert).
    # --change-analysis-graph (or FINOPS_NEO4J_URI/FINOPS_NEO4J_URL) additionally wires the
    # versioned-graph client (cap_2a p1). The returned graph_client is a live driver handle
    # and is ALWAYS closed after the run, even when run_workflow raises; a run that never
    # requested graph analysis has graph_client=None and the finally is a no-op.
    change_analyzer, graph_client = _build_change_analyzer(args)

    # The per-phase spend gate (admission_leases p2) — injected at the composition root exactly
    # like ``router``/``publisher_factory``/``change_analyzer`` above, so ``runtime`` consumes
    # only the runtime-owned ``PhaseAdmission`` protocol and never imports ``control`` (Debt-2).
    # Returns None when the gate is disarmed or --no-admission was passed, in which case the
    # runner's seam is inert and the run is byte-identical to the pre-admission behaviour.
    phase_admission = _build_phase_admission(spec, args)

    # The control database's record of THIS run (control_db_publication p2). Opened BEFORE the
    # engine starts, not after it finishes, and that ordering is the point: a run whose row is
    # only written at the end leaves *nothing at all* behind when the runner is killed — the
    # exact hole `control_db` exists to close. A killed run now leaves a `running` row that the
    # control packet and the lease watchdog can see. Returns (None, None) in child mode or when
    # the database is unavailable, in which case every control-plane step below is a no-op.
    #
    # e1 (control_db_evidence): the writer handle stays OPEN across the engine run and becomes
    # the per-phase evidence recorder — every executed phase records its step_attempts +
    # gate_results rows LIVE (the write side that makes the packet's per-phase derivations
    # real), instead of nothing-at-all-until-the-terminal-write. The recorder is None in child
    # mode (no run row to bind to), so a `--only-phase` sibling records nothing — the parent
    # aggregates. Closed in the finally below, before the terminal write opens its own handle.
    control_run_id, control_db = _control_open_run(spec, args)
    phase_evidence_recorder = make_phase_evidence_recorder(control_db, control_run_id)

    # e2 (control_db_evidence): while this process runs the engine, a daemon heartbeat thread
    # proves to the zombie-run sweep that the run is ALIVE. A killed orchestrator stops beating
    # (the thread dies with the process), so the sweep can later cancel the dangling 'running'
    # row via the legitimate transition API instead of leaving it to manual cancellation. The
    # thread is started only when there is a run row to beat for (never in child mode) and is
    # stopped in the finally below BEFORE the writer handle closes — best-effort by contract: a
    # failed beat is logged and swallowed, never a reason a run fails. One beat is also recorded
    # SYNCHRONOUSLY here, before the thread starts, so a run that dies in the subsecond between
    # its row's creation and the thread's first beat still leaves a heartbeat row behind — the
    # sweep's 'unknown' bucket (no heartbeat row) then means "pre-e2 legacy run", not "died in
    # the creation window".
    run_heartbeat: RunHeartbeatThread | None = None
    if control_run_id is not None and control_db is not None:
        try:
            control_db.record_run_heartbeat(control_run_id)
        except (ControlDBError, OSError) as exc:
            print(
                f"warning: run heartbeat seed failed ({exc}) — thread will retry",
                file=sys.stderr,
            )
        run_heartbeat = RunHeartbeatThread(control_db.path, control_run_id)
        run_heartbeat.start()

    try:
        result = run_workflow(
            spec,
            goal=args.goal,
            model=args.model,
            workdir=args.workdir,
            backend=args.backend,
            thinking_effort=args.thinking_effort,
            thinking_budget_tokens=args.thinking_budget_tokens,
            output_token_limit=args.output_token_limit,
            timeout=args.timeout,
            commit=not args.no_commit,
            resume=args.resume,
            phase_watchdog_min=args.phase_watchdog_min,
            signals=signals,
            router=router,
            publisher_factory=LivePublisher,
            change_analyzer=change_analyzer,
            phase_total=only_phase_total,
            phase_index=only_phase_index,
            phase_admission=phase_admission,
            step_executor=step_executor,
            phase_evidence_recorder=phase_evidence_recorder,
        )
    finally:
        if run_heartbeat is not None:
            run_heartbeat.stop()
        if graph_client is not None:
            with contextlib.suppress(Exception):
                graph_client.close()
        if control_db is not None:
            with contextlib.suppress(Exception):
                control_db.close()

    print(json.dumps(result.to_dict(), indent=2))

    # P0-2 child contract (control_db_publication p2, held to the letter): in CHILD mode the
    # ledger write and the spec-index refresh are the PARENT's job. A `--only-phase` sibling
    # is one phase of the parent's run, not a run of its own — writing a partial ledger (which
    # `spec_status` would then read as run evidence) and refreshing the derived index would be
    # exactly the "children write ledgers / refresh indexes independently" the contract forbids.
    # The parent aggregates: it reads the child's result envelope from stdout and writes the ONE
    # aggregate ledger + the ONE index refresh. `_control_terminal_write` below is already
    # child-mode-inert (returns before doing anything) for the same reason, so ``out_path``
    # stays the default below in child mode (never written, never referenced).
    out_path: str = ""
    if not args.only_phase:
        out_dir = ROOT / "experiments" / "results" / "workflows" / spec.name
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = out_dir / f"{ts}.json"
        out_path.write_text(json.dumps(result.to_dict(), indent=2))
        print(f"\nledger: {out_path}", file=sys.stderr)
    # ``getattr`` so the composition-root tests that substitute a minimal result namespace
    # (no ``awaiting`` field) keep working unchanged.
    if getattr(result, "awaiting", False):
        # cap_runner_hardening2 §Gap 3 — a designed stop, not a failure: the operator's tools
        # read "awaiting operator approval", never a bare ok/failed. Exits 10 under the
        # P0-1 contract (a designed stop has its OWN exit code — 0 would make a parent
        # classify it as success, which is exactly the false-success path P0-1 removes).
        print(
            f"awaiting_operator_approval: phase '{getattr(result, 'awaiting_phase', '?')}' "
            f"(reason: {getattr(result, 'awaiting_reason', '?')})  cost: ${result.total_cost_usd:.4f}",
            file=sys.stderr,
        )
    else:
        print(f"cost: ${result.total_cost_usd:.4f}  ok: {result.ok}", file=sys.stderr)

    if not args.only_phase:
        _refresh_index(spec.name)
    # THE emission path (control_db_publication p2). One transaction records the run's terminal
    # transition, its result envelope, and every knowledge event it owes; a publisher then
    # drains the outbox with at-least-once delivery. The two former fire-and-forget calls
    # (`_emit_spec_record` / `_emit_workflow_facts`) are gone — their DERIVATION survives as
    # `_spec_payload` / `_fact_payloads` below, but nothing publishes directly any more.
    _control_terminal_write(spec, args, result, run_id=control_run_id, ledger_path=out_path)

    # P0-1 exit-code contract (control-plane stabilization): in CHILD mode (--only-phase —
    # the sibling the orchestrator spawns) the process exit code maps the run outcome so
    # the parent can classify the child WITHOUT parsing the envelope — 0 succeeded /
    # 10 awaiting_approval / 20 failed. This is the parent-child boundary where a false
    # success previously lived: a child that wrote ok:false still exited 0, and the
    # orchestrator's `returncode == 0` check mistook it for success.
    #
    # Deliberately scoped to child mode: the full in-process path's consumers (the
    # cap_2c/2d/2e grids, run_cap_grit_grid) read the ledger JSON and treat a recorded
    # ok:false as a designed outcome, not an abort — changing THEIR exit codes would
    # turn recorded failures into grid aborts. The exit code is the parent-child
    # handshake, not a universal success signal.
    if args.only_phase:
        raise SystemExit(exit_code_for_result(result))




def _fact_auto_emit_enabled(args: argparse.Namespace) -> bool:
    """Resolve the fact auto-emit flag: CLI > env > default-ON (design §4's precedence table).

    ``--no-fact-emit`` always wins when passed — an explicit per-invocation CLI flag outranks the
    ambient environment, matching this file's existing ``--signals``-overrides-auto-built-store
    and ``--no-commit``-overrides-``commit=True`` precedence (``run_workflow.py``'s own argparse
    block). Absent the CLI flag, only the literal string ``"0"`` on ``FINOPS_FACT_AUTO_EMIT``
    disables — every other value, including unset, is ON (the deliberate default-ON posture break
    from the rest of the opt-in ``FINOPS_*`` family; see the module-level docstring above the
    ``FACT_AUTO_EMIT_ENV`` constant).
    """
    if args.no_fact_emit:
        return False
    return os.environ.get(FACT_AUTO_EMIT_ENV) != "0"


def _fact_payloads(spec: ExperimentSpec, args: argparse.Namespace, result) -> list[dict]:
    """Derive this run's own fact records and render them as OUTBOX payloads. No I/O, no emit.

    The derivation half of the former ``_emit_workflow_facts`` (the CAP fact-auto-emit hook,
    design: ``docs/architecture/current/cap_fact_auto_emit_design.md``), unchanged: the same
    ``derive_run_facts`` call over the same evidence, with the same ``repository_id`` — which
    must stay ``cell_scope(args.workdir)`` so the facts this run emits share their
    ``scope_path``'s ``org:`` root with whatever THIS run's routing calls query, or
    ``context_compiler.scope_visible``'s ancestor-prefix match silently excludes them.

    What changed is only what happens NEXT. This function no longer opens Redis and publishes;
    it returns payloads for the outbox, and delivery becomes the publisher's at-least-once job.
    The pointer events are built by the producer's OWN builder (``kb_produce_facts.build_event``,
    which dispatches pattern projections to ``fi.pattern_projection_event`` and everything else
    to ``fi.fact_event``) and stored verbatim, so the envelope that reaches the stream is
    byte-identical to the one the direct path produced — only the route differs.

    ``checkpoint=True`` and the registry lines mirror ``kb_produce_facts.emit_records`` exactly,
    including the F2 emit-time registry materialization: the fact producer has always
    checkpointed each ``knowledge_id`` and appended its registry row, and routing the emission
    through the outbox must not quietly drop either.

    Derivation is deliberately NOT wrapped in a try/except here — the caller
    (:func:`_control_terminal_write`) owns the "never fail a finished run" guarantee for the
    whole control-plane step, and burying a second swallow here would hide which half failed.
    """
    records = kb_produce_facts.derive_run_facts(
        result,
        spec,
        repository_id=cell_scope(args.workdir),
        revision=result.git_sha or REVISION_FALLBACK,
        now=_now_iso(),
    )
    payloads = []
    for record in records:
        # Producer-specific operation/reason: a pattern projection is not a raw fact, and the
        # registry line's `reason` fingerprint is what the NEXT producer run reads back to
        # decide whether the fact actually changed.
        if record.source_type == fi.PATTERN_SOURCE_TYPE:
            operation = "supersede" if record.supersedes else "upsert"
            reason = fi.pattern_projection_reason(record)
        else:
            operation = fi.fact_operation(record)
            reason = fi.fact_reason(record)
        payloads.append(
            ob.knowledge_payload(
                record,
                kb_produce_facts.build_event(record),
                checkpoint=True,
                registry_lines=ob.registry_lines_for(record, operation=operation, reason=reason),
            )
        )
    return payloads


def _spec_payload(spec_name: str, *, revision: str) -> dict | None:
    """Derive this spec's lifecycle record as an OUTBOX payload, or ``None`` if unchanged.

    The derivation half of the former ``_emit_spec_record``. It must run AFTER
    :func:`_refresh_index`, because the record is derived from ``experiments/specs/index.json``
    and that index has to already reflect the run that just finished.

    ``None`` is the ordinary, non-exceptional answer in two cases: the spec is not in the index,
    or ``derive_spec_records`` found its lifecycle unchanged since the last registered version.
    Neither is a failure — there is genuinely nothing to say.

    ``checkpoint=False`` and no registry lines, because that is what ``emit_spec_record`` did:
    the spec producer decides "unchanged?" from the registry HEAD (``registry_head`` +
    ``lifecycle_fingerprint``), not from the consumer checkpoint hash, and it has never
    materialized its own registry row. Routing the emission through the outbox changes the
    delivery path only — it is not the place to widen a producer's behaviour.
    """
    entries = [e for e in si.load_index_entries(root=ROOT) if e.name == spec_name]
    if not entries:
        return None
    records = si.derive_spec_records(entries, revision=revision or "workflow-run")
    if not records:
        return None
    record = records[0]
    return ob.knowledge_payload(record, si.spec_event(record), checkpoint=False)


def _control_db() -> ControlDB | None:
    """Open the orchestrator's control database, or ``None`` when it cannot be opened.

    Returns ``None`` rather than raising for the same reason every other post-run step here is
    best-effort: a completed run's outcome may not change because a bookkeeping store was
    unavailable. The difference from the pre-outbox world is what a failure now costs — the
    events stay underived rather than being derived, published into the void, and forgotten.
    """
    try:
        return ControlDB.open()
    except (ControlDBError, OSError) as exc:
        print(f"warning: control db unavailable ({exc}) — control-plane record skipped",
              file=sys.stderr)
        return None


def _control_open_run(spec: ExperimentSpec, args: argparse.Namespace) -> tuple[str | None, ControlDB | None]:
    """Record this run in the control database as ``running``; return ``(run_id, db)``.

    Returns ``(None, None)`` — and records nothing — in CHILD mode. That is the P0-2 contract held
    exactly where it belongs: **children never emit; the parent aggregates.** A ``--only-phase``
    sibling is one phase of the parent's run, not a run of its own, so minting a second run row
    (and a second set of outbox events) for it would double-count the work and emit each phase's
    facts twice. The parent's terminal write covers every phase the children executed.

    The writer handle is returned OPEN: e1 (control_db_evidence) keeps it alive for the whole
    engine run so every executed phase's step_attempts/gate_results rows are written LIVE, not
    back-filled at the end (a killed run leaves per-phase rows behind, not just a dangling
    ``running`` row). The caller closes it in a ``finally`` immediately after ``run_workflow``
    returns, before the terminal write opens its own handle. Returns ``(None, None)`` when the
    database is unavailable (the run itself is unaffected — every control-plane step degrades to
    a no-op, exactly the pre-e1 posture).
    """
    if args.only_phase:
        return None, None
    db = _control_db()
    if db is None:
        return None, None
    try:
        run = db.create_run(
            spec_name=spec.name,
            model=args.model,
            state=RunState.RUNNING,
            reason="workflow run started",
        )
        print(f"control: run {run.run_id} ({run.state.value})", file=sys.stderr)
        return run.run_id, db
    except (ControlDBError, OSError) as exc:
        print(f"warning: control db run creation failed ({exc}) — run itself unaffected",
              file=sys.stderr)
        db.close()
        return None, None


def _derived(label: str, derive) -> list[dict]:
    """Run one producer's derivation, returning its payloads — or none, loudly, on failure.

    The per-producer fence. ``derive`` may return a single payload, a list, or ``None`` (the
    ordinary "nothing changed, nothing to say" answer, which is reported as a no-op rather than
    a warning because it is not one).
    """
    try:
        produced = derive()
    except Exception as exc:  # noqa: BLE001 — one producer's failure, not the run's
        print(f"warning: {label} derivation failed ({exc}) — run itself unaffected",
              file=sys.stderr)
        return []
    if produced is None:
        print(f"{label}: nothing to emit (unchanged or not indexed)", file=sys.stderr)
        return []
    payloads = produced if isinstance(produced, list) else [produced]
    print(f"{label}: {len(payloads)} event(s) queued", file=sys.stderr)
    return payloads


def _control_terminal_write(
    spec: ExperimentSpec,
    args: argparse.Namespace,
    result,
    *,
    run_id: str | None,
    ledger_path: Path,
) -> None:
    """The parent's ATOMIC terminal write, then a drain of the outbox. Never fails the run.

    One transaction (:func:`agentic_dynamics.control.outbox.record_terminal_run`) records all
    three facts that used to be scattered across a ledger file, a Redis publish, and nothing at
    all:

    1. **the run state transition** — ``running`` → the control state this run's ledger outcome
       maps to (``run_state_from_ledger_state``: succeeded → ``promotable``, because phases that
       passed authorise a promotion, they do not *are* one);
    2. **the run result envelope** — the ledger path (the pointer to the envelope JSON just
       written), the total cost, and the candidate SHA, all stamped onto the run row. They are
       passed to the terminal transition rather than written after it because a terminal state
       is immutable: that transition is the last moment they can be recorded at all;
    3. **the knowledge events this run owes** — the spec-lifecycle record and (unless
       ``--no-fact-emit`` / ``FINOPS_FACT_AUTO_EMIT=0``) the run's own facts, queued as
       ``pending`` outbox rows.

    Then :class:`~agentic_dynamics.control.outbox.OutboxPublisher` drains what it can. A drain
    that reaches nothing leaves the rows ``pending`` — which is the entire improvement: the
    obligation survives a downed stream instead of evaporating into a printed warning.

    The whole step is wrapped: derivation, transaction, and drain alike. A finished run's exit
    status may not depend on the control plane's health. What it no longer does is *forget*.
    """
    if run_id is None:
        # Child mode, or the database was unavailable at run start. Either way there is no run
        # row to transition and no aggregation to do here — see _control_open_run.
        if args.only_phase:
            print("control: child mode — parent aggregates, child emits nothing", file=sys.stderr)
        return

    db = _control_db()
    if db is None:
        return
    try:
        # Derivation is fenced OFF from the state record, one producer at a time. A corrupt
        # registry row or a reducer bug costs THAT producer's events and nothing else: the run
        # still terminates in the control database with an honest state. The opposite coupling —
        # a derivation failure leaving the run stuck in `running` forever — would turn a
        # knowledge-plane bug into a phantom in-flight run that the packet and the watchdog
        # would both have to reason about.
        payloads = []
        payloads.extend(
            _derived("spec record", lambda: _spec_payload(spec.name, revision=result.git_sha))
        )
        if _fact_auto_emit_enabled(args):
            payloads.extend(
                _derived("workflow facts", lambda: _fact_payloads(spec, args, result))
            )

        write = ob.record_terminal_run(
            db,
            run_id,
            state=run_state_from_ledger_state(result.state),
            payloads=payloads,
            reason=f"workflow run ended ({result.state})",
            cost_usd=result.total_cost_usd,
            ledger_path=str(ledger_path),
            candidate_sha=result.git_sha,
            ended_at=result.ended_at or None,
        )
        print(
            f"control: run {run_id} -> {write.run.state.value}  "
            f"outbox queued {len(write.events)}",
            file=sys.stderr,
        )

        # Delivery. `_authorized_kb_write()` is the SAME authorization the two direct-publish
        # call sites used, applied for the duration of the drain and no longer: the write guard
        # is unchanged, it has simply moved behind the one emission path.
        with _authorized_kb_write():
            report = ob.OutboxPublisher(db, authorized=True).drain()
        if report.stream_error:
            print(
                f"outbox: stream unreachable ({report.stream_error}) — "
                f"{len(write.events)} event(s) stay pending for the next drain",
                file=sys.stderr,
            )
        else:
            print(f"outbox: {json.dumps(report.to_dict())}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — a finished run's outcome never depends on this
        print(f"warning: control-plane terminal write failed ({exc}) — run itself unaffected",
              file=sys.stderr)
    finally:
        db.close()


def _refresh_index(spec_name: str) -> None:
    """Refresh the derived spec index now that this run's ledger is on disk.

    Best-effort by construction (the ``emit_self`` pattern of
    ``workflow_runner.py:254-267``): the run has already completed and its ledger is
    already written, so an index problem — an unreadable spec YAML, a read-only
    ``experiments/specs/``, anything — must degrade to a printed warning. It may never
    fail the run or change its exit status.

    The literal env ``FINOPS_SKIP_SPEC_INDEX=1`` skips the refresh entirely — the
    cap_adaptive_2d 4-wide grid sets it on the cell subprocesses so 4 concurrent
    ``refresh_spec_status`` writers never race ``experiments/specs/index.json``; the
    campaign's post-grid phase regenerates the index once (``spec_status.py``).
    """
    if os.environ.get("FINOPS_SKIP_SPEC_INDEX") == "1":
        return
    try:
        report = refresh_spec_status(spec_name, root=ROOT)
        print(f"spec index: {report.index_path} ({report.n_specs} specs)", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — a post-run bookkeeping step, never a gate
        print(
            f"warning: spec index refresh failed ({exc}) — run itself unaffected",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
