"""Dependency-direction lint (critique rec 8, verbatim; strengthened refactor-repair Debt-2).

Enforces the package-boundary rules of ``ARCHITECTURE.md`` §2 by walking the import graph of
every ``src/agentic_dynamics/**`` module (plus ``apps/**``) with ``ast`` — including *relative*
imports, which are resolved against the package layout so ``from ..control import X`` can no
longer bypass the cross-plane analysis. The tier map is *descriptive*; the forbidden edges are
the explicit rules — not a blanket tier DAG.

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
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
AD = ROOT / "src" / "agentic_dynamics"
APPS = ROOT / "apps"

CORE = "core"
PLANES = {"experiment", "measurement", "runtime", "adapters", "knowledge", "reporting"}
CONTROL = "control"
LEGACY = "legacy"

TIER1 = PLANES
TIER2 = {CONTROL}

#: The *complete* set of allowed tier-1 → tier-2 (plane → control) edges — the observe-only
#: telemetry seam ("telemetry up, decisions down"). After the Debt-2 inversion these are only
#: the two adapters publishing telemetry; ``runtime.workflow_runner`` uses the injected Router
#: + TelemetryPublisher protocols instead of importing ``control``. Any other plane module
#: importing ``control`` is a rec-8 violation.
PINNED_T1_TO_T2 = frozenset({
    ("adapters.opencode", "control.live"),
    ("adapters.claude_adapter", "control.live"),
})


def _plane_of(rel: Path) -> str | None:
    """The plane (or ``apps``) a source file belongs to, or ``None`` if out of scope.

    Paths are repo-relative: ``src/agentic_dynamics/<plane>/<file>.py`` for the package and
    ``apps/...`` for the (Stage 5) application tier.
    """
    parts = rel.parts
    if not parts:
        return None
    if parts[0] == "apps":
        return "apps"
    if len(parts) >= 3 and parts[0] == "src" and parts[1] == "agentic_dynamics":
        return parts[2]
    return None


def _module_files() -> list[tuple[str, str, Path]]:
    """Every linted source file as ``(plane, stem, path)``.

    ``legacy/`` is quarantined dead code (retired in phase E) and deliberately excluded from
    the tier map; ``apps/`` is included when it exists (Stage 5).
    """
    files: list[tuple[str, str, Path]] = []
    for p in AD.rglob("*.py"):
        rel = p.relative_to(ROOT)
        plane = _plane_of(rel)
        if plane is None or plane == LEGACY:
            continue
        files.append((plane, p.stem, p))
    if APPS.exists():
        for p in APPS.rglob("*.py"):
            files.append(("apps", p.stem, p))
    return files


def _resolve_target(import_name: str) -> tuple[str, str | None] | None:
    """Resolve an absolute import target to ``(plane, module)`` or ``None`` if not internal."""
    parts = import_name.split(".")
    if parts[0] == "agentic_dynamics":
        if len(parts) == 1:
            return None  # `import agentic_dynamics` — no plane
        plane = parts[1]
        if plane in (CORE, *PLANES, CONTROL):
            module = parts[2] if len(parts) >= 3 else None
            return (plane, module)
        return None  # legacy / unknown — out of scope
    if parts[0] == "apps":
        return ("apps", parts[1] if len(parts) >= 2 else None)
    return None  # stdlib / third-party


def _module_parts(path: Path) -> list[str]:
    """The dotted module path of a source file, e.g. ``agentic_dynamics.runtime.foo``.

    ``apps/**`` files keep the ``apps`` prefix; ``src/agentic_dynamics/**`` files drop the
    ``src`` container so the parts line up with the import vocabulary.
    """
    parts = list(path.relative_to(ROOT).parts)
    parts[-1] = Path(parts[-1]).stem
    if parts and parts[0] == "src":
        parts = parts[1:]
    return parts


def _resolve_relative(
    module_parts: list[str], level: int, module: str | None
) -> tuple[str, str | None] | None:
    """Resolve a relative import to ``(plane, module)``, or ``None`` if out of scope.

    ``level`` is the ``ast.ImportFrom.level`` (1 = current package, 2 = parent, …); ``module``
    is the relative target (``None`` for ``from . import …``). Walks ``level - 1`` package
    segments up from the current module, appends ``module``, then reuses the same
    ``agentic_dynamics``/``apps`` mapping as ``_resolve_target``.
    """
    package = module_parts[:-1]
    up = level - 1
    if up > len(package):
        return None  # escapes the package entirely — out of scope
    base = package[: len(package) - up]
    parts = base + (module.split(".") if module else [])
    if parts and parts[0] == "agentic_dynamics" and len(parts) >= 2:
        plane = parts[1]
        if plane in (CORE, *PLANES, CONTROL):
            return (plane, parts[2] if len(parts) >= 3 else None)
        return None
    if parts and parts[0] == "apps":
        return ("apps", parts[1] if len(parts) >= 2 else None)
    return None


def _imports_of(path: Path) -> list[tuple[str, str | None]]:
    """The package-internal import targets ``(plane, module)`` of one source file.

    Both absolute and *relative* imports are resolved: a relative ``from ..control import X``
    is walked against the package layout (``_resolve_relative``) so it can no longer bypass the
    cross-plane analysis (refactor-repair Debt-2).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_parts = _module_parts(path)
    out: list[tuple[str, str | None]] = []
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


def _graph() -> dict[tuple[str, str], list[tuple[str, str | None]]]:
    """Source ``(plane, module)`` → its internal import targets ``(plane, module)``."""
    return {
        (plane, stem): _imports_of(path)
        for plane, stem, path in _module_files()
    }


GRAPH = _graph()


def _sources_in(planes: set[str]) -> list[tuple[str, str]]:
    return sorted(k for k in GRAPH if k[0] in planes)


def _assert_no_edge(sources: set[str], forbidden: set[str], *, reason: str) -> None:
    """Assert no source in ``sources`` imports any target in ``forbidden``."""
    violations = []
    for src in _sources_in(sources):
        for target_plane, target_module in GRAPH[src]:
            if target_plane in forbidden:
                violations.append(f"{src[0]}.{src[1]} -> {target_plane}.{target_module}")
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
        for target_plane, target_module in GRAPH[src]:
            if target_plane == "knowledge" and target_module in {"retrieval", "prompt_constructor"}:
                violations.append(f"{src[0]}.{src[1]} -> {target_plane}.{target_module}")
    assert not violations, "control imports retrieval/prompt_constructor:\n" + "\n".join(sorted(violations))


def test_tier1_to_tier2_edges_are_exactly_pinned():
    """The two execution→control observation edges are the COMPLETE tier-1→tier-2 set."""
    edges: set[tuple[str, str]] = set()
    for src in _sources_in(PLANES):
        for target_plane, target_module in GRAPH[src]:
            if target_plane in TIER2:
                edges.add((f"{src[0]}.{src[1]}", f"{target_plane}.{target_module}"))
    assert edges == PINNED_T1_TO_T2, (
        f"unexpected tier-1→tier-2 edges: {sorted(edges - PINNED_T1_TO_T2)}; "
        f"missing pinned edges: {sorted(PINNED_T1_TO_T2 - edges)}"
    )


def test_apps_contain_no_domain_rules():
    """Rule 8 (rec-8 verbatim) — apps may compose layers but contain no domain rules.

    Enforced as an AST-marker scan: no ``ExperimentSpec(`` / ``RuleSpec(`` / ``Factor(``
    construction anywhere in ``apps/**``. ``apps/`` is created in Stage 5; absent now, so
    this is vacuously green until then.
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
                assert name not in markers, f"{path}: apps contain domain-rule construction {name}(...)"


def test_relative_imports_resolve_across_planes():
    """``from ..control import X`` resolves to ``control`` — no longer ignored (Debt-2).

    The pre-Debt-2 lint skipped every ``level >= 1`` import, so a plane module could reach
    ``control`` via ``from ..control import X`` and dodge the cross-plane assertions. The
    resolver now walks the package layout, so that hole is closed.
    """
    parts = ["agentic_dynamics", "runtime", "foo"]  # src/agentic_dynamics/runtime/foo.py
    assert _resolve_relative(parts, 1, "bar") == ("runtime", "bar")  # `from .bar import …`
    assert _resolve_relative(parts, 1, None) == ("runtime", None)  # `from . import …`
    assert _resolve_relative(parts, 2, "control") == ("control", None)  # `from ..control …`
    assert _resolve_relative(parts, 2, "control.step_routing") == ("control", "step_routing")
    assert _resolve_relative(parts, 2, "measurement") == ("measurement", None)
    # A level that escapes the package entirely is out of scope, not a false edge.
    assert _resolve_relative(parts, 5, "x") is None


def test_module_parts_align_with_the_import_vocabulary():
    """``_module_parts`` maps a source file to the dotted module path ``_resolve_relative`` uses."""
    assert _module_parts(AD / "runtime" / "workflow_runner.py") == [
        "agentic_dynamics", "runtime", "workflow_runner",
    ]
    assert _module_parts(AD / "core" / "paths.py") == ["agentic_dynamics", "core", "paths"]
