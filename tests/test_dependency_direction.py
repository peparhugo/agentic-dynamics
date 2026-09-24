"""Dependency-direction lint (critique rec 8, verbatim; strengthened refactor-repair Debt-2).

Enforces the package-boundary rules of ``ARCHITECTURE.md`` §2 by walking the import graph of
every ``src/agentic_dynamics/**`` module (plus ``apps/**``) with ``ast`` — including *relative*
imports, which are resolved against the package layout so ``from ..control import X`` can no
longer bypass the cross-plane analysis. The tier map is *descriptive*; the forbidden edges are
the explicit rules — not a blanket tier DAG.

**Node identity is PATH-BASED.** Every graph node is the file's dotted module path
(``agentic_dynamics.runtime.workflow_runner``, ``apps.control_room.services.registry``), never
the bare filename stem. The pre-fix graph keyed on ``(plane, stem)``, so same-named files in one
plane — e.g. ``apps/control_room/services/registry.py`` and ``apps/control_room/routes/registry.py``
(both ``("apps", "registry")``) — silently merged into ONE node whose edge list was whichever file
the filesystem walk read last. The same class of collision hit ``telemetry``, ``design_sessions``,
``docs_health``, ``operations`` and every ``__init__`` under ``apps/``. Path-based keys make each
file its own node, and ``test_graph_nodes_are_path_based_and_collision_free`` pins that.

Tier map:

* tier 0 ``core`` — ``core``
* tier 1 ``planes`` — ``experiment``, ``measurement``, ``runtime``, ``adapters``,
  ``knowledge``, ``reporting``
* tier 2 ``control`` — ``control``
* tier 3 ``apps`` — ``apps/`` (outside ``src/agentic_dynamics/``, still linted)

The eight forbidden-edge assertions are rec-8-verbatim. The *only* tier-1→tier-2 edges allowed
are the two adapter telemetry edges (``opencode``/``claude_adapter`` → ``control.live``):
``runtime.workflow_runner`` no longer imports ``control`` at all — it consumes the runtime-owned
``Router``/``TelemetryPublisher`` protocols (``runtime/routing.py``, ``runtime/telemetry.py``)
with the control implementations injected at the composition root (``scripts/run_workflow.py``),
per the Debt-2 dependency inversion. The two data-flow guards (retrieval never supplies POLICY
facts / never writes the KB; knowledge never actuates) live in ``tests/test_data_flow.py``.

**Checkout-only surfaces (``scripts/``, ``workflows/``) — what IS and is NOT gated.** These
namespace packages (no ``__init__.py``; a wheel does not ship them) are walked as graph nodes so
that ONE real edge is enforced: the package planes must never import them
(``test_package_does_not_import_scripts_or_workflows``). That is the direction that protects the
library from re-acquiring checkout-only CLI logic. The rest of their import graph stays OUTSIDE
the ruleset, deliberately and precisely — not by omission:

* The tier map ends at ``apps``; there is no terminal tier for entry points, and BOTH cross-edges
  exist TODAY: ``apps/control_room/server.py``, ``services/docs_health.py``,
  ``services/registry.py``, ``services/subscription_usage.py`` and ``routes/registry.py`` import
  ``scripts.*`` (apps → scripts), and ``scripts/verify_control_room_rendering.py`` imports
  ``apps.control_room.server`` (scripts → apps). Gating those edges means either a sanctioned
  tier rule or migrating the CLI logic into the package — and the latter is explicitly deferred
  (``pyproject.toml``: the CLI is CHECKOUT-ONLY; script-logic migration is post-repair
  hardening). A rule that quietly allowed every scripts edge would fake coverage, so the edges
  are named here instead.
* ``tests/**`` stays out of scope by convention: tests import both surfaces on purpose and assert
  against them.

**Known limitation (unchanged by this hardening).** ``from pkg.mod import submod`` records the
target as ``pkg.mod``, not ``pkg.mod.submod`` — the alias name is not resolved to a submodule
node. The named forbidden-module check therefore matches direct module imports
(``from agentic_dynamics.knowledge.retrieval import …``) and that module's descendants, exactly
as the pre-fix check did; tightening it would change which imports count as edges and belongs to
a separate, deliberate widening of the gate.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
AD = ROOT / "src" / "agentic_dynamics"
APPS = ROOT / "apps"
SCRIPTS = ROOT / "scripts"
WORKFLOWS = ROOT / "workflows"

CORE = "core"
PLANES = {"experiment", "measurement", "runtime", "adapters", "knowledge", "reporting"}
CONTROL = "control"
LEGACY = "legacy"

#: Checkout-only surfaces walked for the package→scripts/workflows guard only. A wheel does not
#: ship them (they are namespace packages), and their own import graphs stay outside the ruleset
#: — the module docstring names the apps↔scripts edges that would fail if they were gated today.
CHECKOUT_ONLY = {"scripts", "workflows"}

# Hindsight is an inspiration-only reference for conservative data handling. Keeping this guard
# separate from the tier graph makes the architectural boundary executable without pretending that
# an external package belongs to any repository plane.
INSPIRATION_ONLY_IMPORT_PREFIX = "hindsight"

TIER1 = PLANES
TIER2 = {CONTROL}

#: The *complete* set of allowed tier-1 → tier-2 (plane → control) edges — the observe-only
#: telemetry seam ("telemetry up, decisions down"). After the Debt-2 inversion these are only
#: the two adapters publishing telemetry; ``runtime.workflow_runner`` uses the injected Router
#: + TelemetryPublisher protocols instead of importing ``control``. Any other plane module
#: importing ``control`` is a rec-8 violation.
PINNED_T1_TO_T2 = frozenset(
    {
        ("agentic_dynamics.adapters.opencode", "agentic_dynamics.control.live"),
        ("agentic_dynamics.adapters.claude_adapter", "agentic_dynamics.control.live"),
    }
)

#: The control-plane modules whose import from ``control`` is forbidden (rule 7): control
#: consumes facts, not arbitrary retrieved text.
RETRIEVAL_MODULES = frozenset(
    {
        "agentic_dynamics.knowledge.retrieval",
        "agentic_dynamics.knowledge.prompt_constructor",
    }
)


def _module_path(path: Path) -> str:
    """The dotted-path identity of a source file, e.g. ``agentic_dynamics.runtime.foo``.

    Path-based, never stem-based: ``src/agentic_dynamics/**`` drops the ``src`` container so the
    parts line up with the import vocabulary, while ``apps/**``/``scripts/**`` keep their prefix.
    """
    parts = list(path.relative_to(ROOT).parts)
    parts[-1] = Path(parts[-1]).stem
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def _plane_of_module(module: str) -> str | None:
    """The plane (or ``apps``/``scripts``/``workflows``) of a dotted module path, else ``None``.

    ``legacy`` and unknown roots return ``None`` — ``legacy/`` is quarantined dead code
    (retired in phase E) and deliberately excluded from the tier map.
    """
    parts = module.split(".")
    if parts[0] == "apps":
        return "apps"
    if parts[0] in CHECKOUT_ONLY:
        return parts[0]
    if len(parts) >= 2 and parts[0] == "agentic_dynamics" and parts[1] in (CORE, *PLANES, CONTROL):
        return parts[1]
    return None


def _module_files() -> list[Path]:
    """Every linted source file: ``src/agentic_dynamics/**`` (legacy excluded), ``apps/**``, and
    the checkout-only ``scripts/**`` (archive excluded) + ``workflows/**`` surfaces."""
    files = [p for p in AD.rglob("*.py") if _plane_of_module(_module_path(p)) is not None]
    if APPS.exists():
        files.extend(APPS.rglob("*.py"))
    for surface in (SCRIPTS, WORKFLOWS):
        if surface.exists():
            files.extend(
                p for p in surface.rglob("*.py") if "archive" not in p.relative_to(surface).parts
            )
    return files


def _resolve_target(import_name: str) -> str | None:
    """Resolve an absolute import target to its dotted repo module path, or ``None`` if external.

    Only the internal roots are mapped: ``agentic_dynamics.<known plane>…``, ``apps.*`` and the
    checkout-only ``scripts.*`` / ``workflows.*`` surfaces. Everything else (stdlib/third-party)
    is out of scope.
    """
    parts = import_name.split(".")
    if parts[0] == "agentic_dynamics":
        if len(parts) >= 2 and parts[1] in (CORE, *PLANES, CONTROL):
            return import_name
        return None
    if parts[0] in ("apps", *CHECKOUT_ONLY):
        return import_name
    return None


def _resolve_relative(module_parts: list[str], level: int, module: str | None) -> str | None:
    """Resolve a relative import to its dotted module path, or ``None`` if out of scope.

    ``level`` is the ``ast.ImportFrom.level`` (1 = current package, 2 = parent, …); ``module``
    is the relative target (``None`` for ``from . import …``). Walks ``level - 1`` package
    segments up from the current module, appends ``module``, then keeps the result only when it
    lands on an in-scope root.
    """
    package = module_parts[:-1]
    up = level - 1
    if up > len(package):
        return None  # escapes the package entirely — out of scope
    base = package[: len(package) - up]
    parts = base + (module.split(".") if module else [])
    joined = ".".join(parts)
    return joined if _plane_of_module(joined) is not None else None


def _imports_of(path: Path) -> list[str]:
    """The package-internal import targets (dotted module paths) of one source file.

    Both absolute and *relative* imports are resolved: a relative ``from ..control import X``
    is walked against the package layout (``_resolve_relative``) so it can no longer bypass the
    cross-plane analysis (refactor-repair Debt-2).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_parts = _module_path(path).split(".")
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve_target(alias.name)
                if target:
                    out.append(target)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                target = _resolve_target(node.module or "")
                if target:
                    out.append(target)
            else:
                target = _resolve_relative(module_parts, node.level, node.module)
                if target:
                    out.append(target)
    return out


def _graph() -> dict[str, list[str]]:
    """Source dotted module path → its internal import targets (dotted module paths)."""
    return {_module_path(path): _imports_of(path) for path in _module_files()}


GRAPH = _graph()


def _sources_in(planes: set[str]) -> list[str]:
    return sorted(node for node in GRAPH if _plane_of_module(node) in planes)


def _assert_no_edge(sources: set[str], forbidden: set[str], *, reason: str) -> None:
    """Assert no source in ``sources`` imports any target whose plane is in ``forbidden``."""
    violations = []
    for src in _sources_in(sources):
        for target in GRAPH[src]:
            if _plane_of_module(target) in forbidden:
                violations.append(f"{src} -> {target}")
    assert not violations, f"{reason}:\n" + "\n".join(sorted(violations))


def test_core_imports_nothing_from_higher_tiers():
    """Rule 1 — core is tier 0; it imports only stdlib/third-party + core siblings."""
    _assert_no_edge({CORE}, PLANES | TIER2 | {"apps"}, reason="core imports a higher tier")


def test_measurement_does_not_import_control():
    """Rule 2 (rec-8 verbatim)."""
    _assert_no_edge({"measurement"}, TIER2, reason="measurement imports control")


def test_knowledge_does_not_import_control():
    """Rule 3 (rec-8 verbatim) — knowledge does not actuate."""
    _assert_no_edge({"knowledge"}, TIER2, reason="knowledge imports control")


def test_experiment_does_not_import_control():
    """Rule 4 — the platform defines; control consumes."""
    _assert_no_edge({"experiment"}, TIER2, reason="experiment imports control")


def test_reporting_does_not_import_control():
    """Rule 5 — output does not steer."""
    _assert_no_edge({"reporting"}, TIER2, reason="reporting imports control")


def test_nothing_imports_apps():
    """Rule 6 — apps consume the system; nothing below tier 3 is consumed-by-apps."""
    _assert_no_edge({CORE} | PLANES | TIER2, {"apps"}, reason="below-tier-3 imports apps")


def test_control_does_not_import_retrieval_or_prompt_constructor():
    """Rule 7 (rec-8 verbatim) — control consumes facts, not arbitrary retrieved text."""
    violations = []
    for src in _sources_in(TIER2):
        for target in GRAPH[src]:
            if any(
                target == module or target.startswith(module + ".") for module in RETRIEVAL_MODULES
            ):
                violations.append(f"{src} -> {target}")
    assert not violations, "control imports retrieval/prompt_constructor:\n" + "\n".join(
        sorted(violations)
    )


def test_tier1_to_tier2_edges_are_exactly_pinned():
    """The two execution→control observation edges are the COMPLETE tier-1→tier-2 set."""
    edges: set[tuple[str, str]] = set()
    for src in _sources_in(PLANES):
        for target in GRAPH[src]:
            if _plane_of_module(target) in TIER2:
                edges.add((src, target))
    assert edges == PINNED_T1_TO_T2, (
        f"unexpected tier-1→tier-2 edges: {sorted(edges - PINNED_T1_TO_T2)}; "
        f"missing pinned edges: {sorted(PINNED_T1_TO_T2 - edges)}"
    )


def test_package_does_not_import_scripts_or_workflows():
    """The package planes never import the checkout-only CLI/workflow surfaces.

    Probe the graph is actually populated for both surfaces — the guard must not pass because
    the nodes were never walked.
    """
    assert any(node.startswith("scripts.") for node in GRAPH), "scripts nodes missing from graph"
    assert any(node.startswith("workflows.") for node in GRAPH), (
        "workflows nodes missing from graph"
    )
    _assert_no_edge(
        {CORE} | PLANES | TIER2,
        CHECKOUT_ONLY,
        reason="a package plane imports checkout-only scripts/workflows logic",
    )


def test_runtime_surfaces_do_not_import_hindsight():
    """The inspiration-only boundary excludes direct Hindsight runtime dependencies.

    The architecture records patterns learned from the committed dossier, but the repository must
    remain runnable with its own mechanisms. This AST check covers the linted Python runtime
    surfaces, including ``src/``, ``apps/``, ``scripts/``, and ``workflows/``; it intentionally
    checks imports only, so it does not widen the existing package tier rules or require an
    optional external dependency merely to run the guard.
    """
    violations: list[str] = []
    for path in _module_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported_roots: list[str] = []
            if isinstance(node, ast.Import):
                imported_roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_roots = [node.module.split(".", 1)[0]]
            if any(
                root.casefold().startswith(INSPIRATION_ONLY_IMPORT_PREFIX)
                for root in imported_roots
            ):
                violations.append(f"{path}: Hindsight runtime import")
    assert not violations, "inspiration-only Hindsight dependency detected:\n" + "\n".join(
        violations
    )


def test_apps_contain_no_domain_rules():
    """Rule 8 (rec-8 verbatim) — apps may compose layers but contain no domain rules.

    Enforced as an AST-marker scan: no ``ExperimentSpec(`` / ``RuleSpec(`` / ``Factor(``
    construction anywhere in ``apps/**``.
    """
    if not APPS.exists():
        return
    markers = {"ExperimentSpec", "RuleSpec", "Factor"}
    for path in APPS.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else None
                )
                assert name not in markers, (
                    f"{path}: apps contain domain-rule construction {name}(...)"
                )


def test_graph_nodes_are_path_based_and_collision_free():
    """Every source file is its own node, keyed by dotted path — same-stem files never merge.

    The pre-fix graph used ``(plane, stem)``: these two registry modules were one node under
    ``("apps", "registry")``, so the gate saw only whichever file's edges the walk read last. The
    same collision class covered ``telemetry``/``design_sessions``/``docs_health``/``operations``
    and every ``apps/**/__init__.py``.
    """
    nodes = list(GRAPH)
    assert len(nodes) == len(set(nodes)), "graph node identities are not unique"
    assert "apps.control_room.services.registry" in GRAPH
    assert "apps.control_room.routes.registry" in GRAPH
    # Distinct nodes with distinct edge sets (the service is a pure file reader; the route
    # composes the service + Flask — a merged node would have lost one of the two).
    assert (
        GRAPH["apps.control_room.services.registry"] != GRAPH["apps.control_room.routes.registry"]
    )
    # Both same-stem __init__ packages are distinct too.
    assert "apps.control_room.routes.__init__" in GRAPH
    assert "apps.control_room.services.__init__" in GRAPH


def test_relative_imports_resolve_across_planes():
    """``from ..control import X`` resolves to ``control`` — no longer ignored (Debt-2).

    The pre-Debt-2 lint skipped every ``level >= 1`` import, so a plane module could reach
    ``control`` via ``from ..control import X`` and dodge the cross-plane assertions. The
    resolver now walks the package layout, so that hole is closed.
    """
    parts = ["agentic_dynamics", "runtime", "foo"]  # src/agentic_dynamics/runtime/foo.py
    assert _resolve_relative(parts, 1, "bar") == "agentic_dynamics.runtime.bar"  # `from .bar …`
    assert _resolve_relative(parts, 1, None) == "agentic_dynamics.runtime"  # `from . import …`
    assert _resolve_relative(parts, 2, "control") == "agentic_dynamics.control"  # `from ..control`
    assert (
        _resolve_relative(parts, 2, "control.step_routing")
        == "agentic_dynamics.control.step_routing"
    )
    assert _resolve_relative(parts, 2, "measurement") == "agentic_dynamics.measurement"
    # A level that escapes the package entirely is out of scope, not a false edge.
    assert _resolve_relative(parts, 5, "x") is None
    # Apps files resolve relative to the apps package prefix the same way.
    app_parts = ["apps", "control_room", "routes", "flags"]
    assert _resolve_relative(app_parts, 1, "helpers") == "apps.control_room.routes.helpers"
    assert _resolve_relative(app_parts, 2, "services") == "apps.control_room.services"


def test_module_path_aligns_with_the_import_vocabulary():
    """``_module_path`` maps a source file to the dotted path the resolver uses."""
    assert _module_path(AD / "runtime" / "workflow_runner.py") == (
        "agentic_dynamics.runtime.workflow_runner"
    )
    assert _module_path(AD / "core" / "paths.py") == "agentic_dynamics.core.paths"
    assert _module_path(APPS / "control_room" / "services" / "context.py") == (
        "apps.control_room.services.context"
    )
    assert _module_path(SCRIPTS / "kb_worker.py") == "scripts.kb_worker"
    assert _module_path(WORKFLOWS / "compile_workflow.py") == "workflows.compile_workflow"
