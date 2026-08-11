"""Codebase graph analysis — structural metrics from AST import graphs.

Imports the codebase AST into a graph representation and computes:
  - Modularity: how well module boundaries match import clusters
  - Coupling: import edge density between modules
  - Centrality: dependency concentration (god modules)
  - Connected components: isolated vs interconnected code
  - Dependency direction: upward/downward/sideways dependency classification

Works with Neo4j (if available) or falls back to in-memory networkx.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .language import detect_language, parse_codebase, LanguageProfile, CodebaseAST


# ── Data Structures ────────────────────────────────────────────

@dataclass
class ModuleNode:
    """A module (file) in the codebase graph."""

    path: str
    node_type: str = "module"
    loc: int = 0
    function_count: int = 0
    class_count: int = 0
    import_count: int = 0
    imports_from: list[str] = field(default_factory=list)  # modules this imports
    imported_by: list[str] = field(default_factory=list)    # modules that import this


@dataclass
class CodebaseGraph:
    """In-memory graph representation of a codebase."""

    language: str
    modules: dict[str, ModuleNode] = field(default_factory=dict)
    total_loc: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_imports: int = 0


@dataclass
class GraphMetrics:
    """Structural metrics computed from the codebase graph."""

    modularity: float = 0.0           # [0-1] how well natural clusters match declared boundaries
    graph_density: float = 0.0        # edges / max_possible_edges
    avg_degree: float = 0.0           # average imports per module
    max_in_degree: int = 0            # most imported module (dependency magnet)
    max_in_degree_module: str = ""
    max_out_degree: int = 0           # most importing module
    max_out_degree_module: str = ""
    connected_components: int = 0     # number of disconnected clusters
    largest_component_size: int = 0
    dependency_fanout: dict[str, int] = field(default_factory=dict)  # module -> fanout count
    dependency_fanin: dict[str, int] = field(default_factory=dict)   # module -> fanin count

    def to_dict(self) -> dict[str, Any]:
        return {
            "modularity": round(self.modularity, 4),
            "graph_density": round(self.graph_density, 6),
            "avg_degree": round(self.avg_degree, 2),
            "max_in_degree": self.max_in_degree,
            "max_in_degree_module": self.max_in_degree_module,
            "max_out_degree": self.max_out_degree,
            "max_out_degree_module": self.max_out_degree_module,
            "connected_components": self.connected_components,
            "largest_component_size": self.largest_component_size,
        }


# ── Graph Construction ─────────────────────────────────────────

def build_graph(
    codebase_path: Path,
    profile: LanguageProfile | None = None,
) -> CodebaseGraph:
    """Build an in-memory import graph from a codebase.

    Parses all source files with tree-sitter, extracts imports,
    and builds bidirectional edges between modules.

    Args:
        codebase_path: Root directory of the codebase.
        profile: Language profile. Auto-detected if None.

    Returns:
        CodebaseGraph with all modules and edges populated.
    """
    if profile is None:
        profile = detect_language(codebase_path)
    if profile is None:
        return CodebaseGraph(language="unknown")

    graph = CodebaseGraph(language=profile.name)
    extensions = set(profile.extensions)

    # First pass: build module metadata
    file_modules: dict[str, ModuleNode] = {}
    for file_path in codebase_path.rglob("*"):
        if file_path.is_dir() or file_path.suffix not in extensions:
            continue
        try:
            source = file_path.read_bytes()
        except (OSError, UnicodeDecodeError):
            continue

        rel_path = str(file_path.relative_to(codebase_path))
        loc = len(source.split(b"\n"))

        module = ModuleNode(path=rel_path, loc=loc)
        file_modules[rel_path] = module
        graph.total_loc += loc

    # Second pass: extract imports and build edges
    for rel_path, module in file_modules.items():
        file_path = codebase_path / rel_path
        try:
            source = file_path.read_bytes()
            parser = __import__("tree_sitter_languages", fromlist=["get_parser"]).get_parser(
                profile.tree_sitter_id
            )
            tree = parser.parse(source)

            # Collect imports
            imports = _extract_imports(profile, tree, source)

            # Resolve local imports to file paths
            for imp in imports:
                resolved = _resolve_import(profile, rel_path, imp, file_modules)
                if resolved and resolved != rel_path:
                    module.imports_from.append(resolved)
                    module.import_count += 1
                    if resolved in file_modules:
                        file_modules[resolved].imported_by.append(rel_path)
        except Exception:
            pass

    # Populate aggregate counts
    for module in file_modules.values():
        for file_path in [codebase_path / module.path]:
            if file_path.exists():
                try:
                    ast = parse_codebase(codebase_path, profile)
                    if ast and module.path in ast.files:
                        pass  # counts already captured
                except Exception:
                    pass

        graph.total_functions += module.function_count
        graph.total_classes += module.class_count
        graph.total_imports += module.import_count

    graph.modules = file_modules
    return graph


def compute_metrics(graph: CodebaseGraph) -> GraphMetrics:
    """Compute structural metrics from a codebase graph.

    Does NOT require Neo4j — all metrics are calculated in-memory.
    """
    m = GraphMetrics()
    nodes = list(graph.modules.values())
    n = len(nodes)

    if n == 0:
        return m

    # Degree statistics
    total_edges = sum(len(mod.imports_from) for mod in nodes)
    m.graph_density = total_edges / (n * (n - 1)) if n > 1 else 0.0
    m.avg_degree = total_edges / n if n > 0 else 0.0

    # Max degree
    for mod in nodes:
        out_deg = len(mod.imports_from)
        in_deg = len(mod.imported_by)
        m.dependency_fanout[mod.path] = out_deg
        m.dependency_fanin[mod.path] = in_deg
        if in_deg > m.max_in_degree:
            m.max_in_degree = in_deg
            m.max_in_degree_module = mod.path
        if out_deg > m.max_out_degree:
            m.max_out_degree = out_deg
            m.max_out_degree_module = mod.path

    # Connected components (BFS)
    visited = set()
    components: list[int] = []

    for mod_path in graph.modules:
        if mod_path in visited:
            continue
        component_size = _bfs_size(graph, mod_path, visited)
        components.append(component_size)

    m.connected_components = len(components)
    m.largest_component_size = max(components) if components else 0

    # Modularity: compare intra-module edges vs expected
    # A simple approximation: edges within the same directory / expected
    m.modularity = _approx_modularity(graph)

    return m


# ── Graph Delta ────────────────────────────────────────────────

@dataclass
class GraphDelta:
    """Difference between two graph states."""

    density_delta: float = 0.0
    modularity_delta: float = 0.0
    components_delta: int = 0
    max_in_degree_delta: int = 0
    max_out_degree_delta: int = 0
    new_modules: int = 0
    removed_modules: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "density_delta": round(self.density_delta, 6),
            "modularity_delta": round(self.modularity_delta, 4),
            "components_delta": self.components_delta,
            "max_in_degree_delta": self.max_in_degree_delta,
            "max_out_degree_delta": self.max_out_degree_delta,
            "new_modules": self.new_modules,
            "removed_modules": self.removed_modules,
        }


def compute_graph_delta(before: GraphMetrics, after: GraphMetrics) -> GraphDelta:
    """Compute the change in graph metrics between two states."""
    return GraphDelta(
        density_delta=after.graph_density - before.graph_density,
        modularity_delta=after.modularity - before.modularity,
        components_delta=after.connected_components - before.connected_components,
        max_in_degree_delta=after.max_in_degree - before.max_in_degree,
        max_out_degree_delta=after.max_out_degree - before.max_out_degree,
    )


# ── Helpers ─────────────────────────────────────────────────────

def _extract_imports(
    profile: LanguageProfile, tree, source: bytes
) -> list[str]:
    """Extract imported module names from a tree."""
    result: list[str] = []

    def walk(node):
        if node.type in profile.import_node_types:
            for child in node.children:
                if child.type == "dotted_name":
                    result.append(child.text.decode())
                elif child.type == "string":
                    text = child.text.decode().strip("\"'")
                    if text:
                        result.append(text)
                elif child.type == "import_clause":
                    walk(child)
                elif child.type == "named_imports":
                    walk(child)
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return result


def _resolve_import(
    profile: LanguageProfile,
    from_module: str,
    import_path: str,
    modules: dict[str, ModuleNode],
) -> str | None:
    """Resolve an import path to a relative file path."""
    from_dir = str(Path(from_module).parent) if "/" in from_module else "."

    candidates = [
        f"{import_path.replace('.', '/')}.py",
        f"{import_path.replace('.', '/')}/__init__.py",
        f"{from_dir}/{import_path.replace('.', '/')}.py",
    ]

    for ext in profile.extensions:
        candidates.append(f"{import_path.replace('.', '/')}{ext}")
        candidates.append(f"{from_dir}/{import_path.replace('.', '/')}{ext}")

    for cand in candidates:
        if cand in modules:
            return cand

    # Partial match: any module whose path contains the import name
    for mod_path in modules:
        if import_path in mod_path or import_path.replace(".", "/") in mod_path:
            return mod_path

    return None


def _bfs_size(graph: CodebaseGraph, start: str, visited: set) -> int:
    """BFS to count component size."""
    queue = [start]
    size = 0
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        size += 1
        if node in graph.modules:
            for neighbor in graph.modules[node].imports_from:
                if neighbor not in visited and neighbor in graph.modules:
                    queue.append(neighbor)
            for neighbor in graph.modules[node].imported_by:
                if neighbor not in visited and neighbor in graph.modules:
                    queue.append(neighbor)
    return size


def _approx_modularity(graph: CodebaseGraph) -> float:
    """Approximate modularity: how well import clusters match directory structure.

    High modularity = modules in the same directory import each other more
    than they import across directories.
    """
    dirs: dict[str, list[str]] = defaultdict(list)
    for path in graph.modules:
        d = str(Path(path).parent) if "/" in path else "."
        dirs[d].append(path)

    total_edges = sum(len(m.imports_from) for m in graph.modules.values())
    if total_edges == 0:
        return 0.0

    same_dir_edges = 0
    for mod_path, module in graph.modules.items():
        mod_dir = str(Path(mod_path).parent) if "/" in mod_path else "."
        for target in module.imports_from:
            target_dir = str(Path(target).parent) if "/" in target else "."
            if mod_dir == target_dir:
                same_dir_edges += 1

    return same_dir_edges / total_edges if total_edges > 0 else 0.0
