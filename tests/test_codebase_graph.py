"""Tests for codebase graph analysis."""

import tempfile
from pathlib import Path

import pytest

from instrument.codebase_graph import (
    CodebaseGraph,
    GraphMetrics,
    ModuleNode,
    _approx_modularity,
    _extract_imports,
    _resolve_import,
    build_graph,
    compute_graph_delta,
    compute_metrics,
)
from instrument.language import _PROFILES


class TestBuildGraph:
    def test_empty_codebase(self):
        with tempfile.TemporaryDirectory() as d:
            graph = build_graph(Path(d))
            assert len(graph.modules) == 0

    def test_single_file_no_imports(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "app.py").write_text("x = 1\n")
            graph = build_graph(dp)
            assert len(graph.modules) == 1

    def test_two_files_with_imports(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "app.py").write_text("x = 1\n")
            (dp / "utils.py").write_text("import app\n\ndef helper(): pass\n")
            graph = build_graph(dp)
            assert len(graph.modules) == 2
            # utils imports app
            utils = graph.modules.get("utils.py")
            assert utils is not None
            assert len(utils.imports_from) > 0

    def test_detects_language(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "index.ts").write_text("import { x } from './utils';\n")
            graph = build_graph(dp)
            assert graph.language == "typescript"


class TestComputeMetrics:
    def test_single_module(self):
        graph = CodebaseGraph(
            language="python",
            modules={"app.py": ModuleNode(path="app.py", loc=10)},
        )
        m = compute_metrics(graph)
        assert m.modularity >= 0.0
        assert m.graph_density == 0.0
        assert m.connected_components == 1

    def test_multiple_modules(self):
        graph = CodebaseGraph(language="python")
        mod_a = ModuleNode(path="a.py", imports_from=["b.py"])
        mod_b = ModuleNode(path="b.py", imported_by=["a.py"])
        graph.modules = {"a.py": mod_a, "b.py": mod_b}
        m = compute_metrics(graph)
        assert m.avg_degree > 0
        assert m.connected_components == 1

    def test_to_dict(self):
        m = GraphMetrics(modularity=0.5, graph_density=0.1)
        d = m.to_dict()
        assert d["modularity"] == 0.5


class TestGraphDelta:
    def test_compute_delta(self):
        before = GraphMetrics(modularity=0.5, graph_density=0.1, connected_components=2)
        after = GraphMetrics(modularity=0.6, graph_density=0.15, connected_components=1)
        delta = compute_graph_delta(before, after)
        assert delta.modularity_delta == pytest.approx(0.1)
        assert delta.density_delta == pytest.approx(0.05)
        assert delta.components_delta == -1


class TestApproxModularity:
    def test_high_modularity_when_imports_within_dir(self):
        graph = CodebaseGraph(language="python")
        mod_a = ModuleNode(path="api/views.py", imports_from=["api/models.py"])
        mod_b = ModuleNode(path="api/models.py")
        graph.modules = {"api/views.py": mod_a, "api/models.py": mod_b}
        m = _approx_modularity(graph)
        assert m == 1.0  # all imports within same directory

    def test_low_modularity_when_cross_dir(self):
        graph = CodebaseGraph(language="python")
        mod_a = ModuleNode(path="api/views.py", imports_from=["db/connection.py"])
        mod_b = ModuleNode(path="db/connection.py")
        graph.modules = {"api/views.py": mod_a, "db/connection.py": mod_b}
        m = _approx_modularity(graph)
        assert m == 0.0  # import across directories


class TestExtractImports:
    def test_python_imports(self):
        profile = _PROFILES["python"]
        parser = __import__("tree_sitter_languages", fromlist=["get_parser"]).get_parser("python")
        source = b"import os\nfrom typing import List\nfrom .models import User\n"
        tree = parser.parse(source)
        imports = _extract_imports(profile, tree, source)
        assert len(imports) > 0


class TestResolveImport:
    def test_resolves_relative(self):
        modules = {"api/models.py": ModuleNode(path="api/models.py")}
        resolved = _resolve_import(_PROFILES["python"], "api/views.py", "models", modules)
        assert resolved is not None
        assert "models.py" in resolved
