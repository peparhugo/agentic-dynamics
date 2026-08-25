"""Tests for the typed CodeSnapshot / CodeDelta (design §5.3 — e2 of cap_evidence_integrity).

Covers snapshot construction (qualified names + source spans), the delta computation
(added/removed/changed symbols, imports, call edges), parse-coverage facts (unparseable files
never crash), the two-ID contract, rename-as-new-entity, and the commit_analysis integration
(public API compatible; tree-sitter failures degrade to a recorded parse-coverage fact).
"""

from pathlib import Path

from agentic_dynamics.core import language as lang_mod
from agentic_dynamics.core.language import (
    TESTED_BY_RULE,
    _PROFILES,
    build_code_snapshot,
    compute_code_delta,
    module_entity_id,
    module_path_from_test_file,
    module_version_id,
    smallest_containing_symbol,
    symbol_entity_id,
    symbol_version_id,
)
from agentic_dynamics.measurement.commit_analysis import _read_commit_files, _run_git, compute_ast_diff

PY = _PROFILES["python"]


def _snapshot(files: dict[str, bytes], revision: str = "aaaa"):
    return build_code_snapshot(files, revision=revision, profile=PY)


# ── CodeSnapshot: qualified names + source spans ────────────────


def test_snapshot_has_symbols_with_qualified_names_and_spans():
    src = (
        b"import os\n\n"
        b"def top(a, b):\n"
        b"    return a + b\n\n"
        b"class Calculator:\n"
        b"    def multiply(self, x):\n"
        b"        return x * 2\n"
    )
    snap = _snapshot({"math_utils.py": src})
    symbols = snap.files["math_utils.py"]
    by_qname = {s.qualified_name: s for s in symbols}

    assert set(by_qname) == {"top", "Calculator", "Calculator.multiply"}
    top = by_qname["top"]
    assert top.kind == "function"
    assert top.module_name == "math_utils"
    assert top.source_span.start_line == 3
    assert top.source_span.end_line == 4
    method = by_qname["Calculator.multiply"]
    assert method.kind == "function"
    assert method.source_span.start_line == 7
    assert len(top.content_hash) == 64


def test_snapshot_records_imports_and_file_hashes():
    snap = _snapshot({"a.py": b"import os\nimport sys\n\ndef f():\n    pass\n"})
    assert snap.imports["a.py"] == ["os", "sys"]
    assert "a.py" in snap.file_hashes
    assert len(snap.file_hashes["a.py"]) == 64


def test_parse_coverage_fact_records_unparseable_file():
    snap = _snapshot({"ok.py": b"def f():\n    pass\n", "bad.py": b"def f(:\n"})
    assert snap.unparsed_files == ["bad.py"]
    assert snap.parse_coverage() == 0.5


def test_no_source_files_parse_coverage_none():
    snap = _snapshot({"readme.md": b"# no code\n"})
    assert snap.parsed_files == []
    assert snap.parse_coverage() is None


# ── CodeDelta: added / removed / changed ────────────────────────


def test_delta_added_removed_changed_symbols():
    before_src = b"def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    after_src = b"def foo():\n    return 99\n\ndef baz():\n    return 3\n"
    before = _snapshot({"m.py": before_src}, revision="r1")
    after = _snapshot({"m.py": after_src}, revision="r2")
    delta = compute_code_delta(before, after)

    assert {s.qualified_name for s in delta.added_symbols} == {"baz"}
    assert {s.qualified_name for s in delta.removed_symbols} == {"bar"}
    assert {s.qualified_name for s in delta.changed_symbols} == {"foo"}
    assert delta.changed_files == ["m.py"]
    assert delta.added_files == []
    assert delta.removed_files == []


def test_delta_import_and_call_edge_diffs():
    before_src = b"import os\n\ndef a():\n    os.getcwd()\n"
    after_src = b"import os\nimport sys\n\ndef a():\n    sys.exit(0)\n"
    before = _snapshot({"m.py": before_src}, revision="r1")
    after = _snapshot({"m.py": after_src}, revision="r2")
    delta = compute_code_delta(before, after)

    assert delta.added_imports == {"m.py": ["sys"]}
    assert delta.removed_imports == {}
    assert ("a", "sys.exit") in delta.added_call_edges or ("a", "exit") in delta.added_call_edges
    assert delta.removed_call_edges  # the os.getcwd() call edge went away


def test_rename_is_new_entity_not_change():
    before = _snapshot({"m.py": b"def old_name():\n    pass\n"}, revision="r1")
    after = _snapshot({"m.py": b"def new_name():\n    pass\n"}, revision="r2")
    delta = compute_code_delta(before, after)
    # A rename is a removed + an added symbol — never an implicit "changed".
    assert {s.qualified_name for s in delta.removed_symbols} == {"old_name"}
    assert {s.qualified_name for s in delta.added_symbols} == {"new_name"}
    assert delta.changed_symbols == []


# ── Two-ID contract ─────────────────────────────────────────────


def test_entity_id_stable_version_id_changes():
    rid = "repo-1"
    ent = symbol_entity_id(rid, "m.py", "foo", "function")
    assert ent == symbol_entity_id(rid, "m.py", "foo", "function")  # stable slot
    assert ent != symbol_entity_id(rid, "m.py", "foo", "class")  # kind is in the slot
    assert ent != symbol_entity_id(rid, "m.py", "bar", "function")  # qname is in the slot

    v1 = symbol_version_id(ent, "c1", "hash-1")
    v2 = symbol_version_id(ent, "c1", "hash-2")
    v3 = symbol_version_id(ent, "c2", "hash-1")
    assert v1 == symbol_version_id(ent, "c1", "hash-1")  # deterministic
    assert v1 != v2  # content change -> new version
    assert v1 != v3  # commit change -> new version

    mod_ent = module_entity_id(rid, "m")
    assert mod_ent == module_entity_id(rid, "m")
    assert mod_ent != module_entity_id(rid, "m2")
    assert module_version_id(mod_ent, "c1", "h") != module_version_id(mod_ent, "c1", "h2")


# ── commit_analysis integration (public API compatible) ────────


def _git_repo(tmp_path: Path) -> Path:
    dp = tmp_path / "repo"
    dp.mkdir()
    _run_git(dp, "init")
    return dp


def test_commit_analysis_uses_typed_delta(monkeypatch, tmp_path):
    dp = _git_repo(tmp_path)
    (dp / "app.py").write_text("import os\n\ndef foo():\n    pass\n\nclass Svc:\n    def run(self):\n        pass\n")
    _run_git(dp, "add", "-A")
    _run_git(dp, "commit", "-m", "initial")
    c1 = _run_git(dp, "rev-parse", "HEAD").strip()

    (dp / "app.py").write_text("import os\nimport sys\n\ndef foo():\n    pass\n\ndef bar():\n    pass\n\nclass Svc:\n    def run(self):\n        pass\n")
    _run_git(dp, "add", "-A")
    _run_git(dp, "commit", "-m", "add bar")
    c2 = _run_git(dp, "rev-parse", "HEAD").strip()

    analysis = compute_ast_diff(dp, c1, c2)
    assert analysis.functions_added == 1
    assert analysis.imports_added == 1
    assert analysis.files_modified == 1
    assert analysis.parse_coverage == 1.0
    assert analysis.code_delta is not None
    assert analysis.code_delta["added_symbols"][0]["qualified_name"] == "bar"
    assert analysis.code_delta["added_symbols"][0]["source_span"]["start_line"] == 7


def test_tree_sitter_failure_records_fact_never_crashes(tmp_path):
    dp = _git_repo(tmp_path)
    (dp / "app.py").write_text("def fine():\n    pass\n")
    _run_git(dp, "add", "-A")
    _run_git(dp, "commit", "-m", "initial")
    c1 = _run_git(dp, "rev-parse", "HEAD").strip()

    (dp / "broken.py").write_text("def broken(:\n")
    _run_git(dp, "add", "-A")
    _run_git(dp, "commit", "-m", "add broken")
    c2 = _run_git(dp, "rev-parse", "HEAD").strip()

    analysis = compute_ast_diff(dp, c1, c2)
    assert analysis.functions_added >= 0  # no crash
    assert analysis.parse_coverage is not None and analysis.parse_coverage < 1.0


def test_read_commit_files_materializes_source(tmp_path):
    dp = _git_repo(tmp_path)
    (dp / "app.py").write_text("import os\n\ndef f():\n    pass\n")
    (dp / "notes.txt").write_text("not source\n")
    _run_git(dp, "add", "-A")
    _run_git(dp, "commit", "-m", "init")
    commit = _run_git(dp, "rev-parse", "HEAD").strip()

    files = _read_commit_files(dp, commit, PY)
    assert set(files) == {"app.py"}  # only source extensions, materialized from git
    assert b"def f" in files["app.py"]


# ── Issue→symbol linking (design §5.4) ──────────────────────────


def test_smallest_containing_symbol():
    src = (
        b"class Outer:\n"
        b"    def method(self):\n"
        b"        return 1\n"
        b"def top():\n"
        b"    return 2\n"
    )
    snap = _snapshot({"m.py": src})
    # Line 2 is inside Outer (1-3) and Outer.method (2-3): method is the SMALLEST.
    assert smallest_containing_symbol(snap, "m.py", 2).qualified_name == "Outer.method"
    assert smallest_containing_symbol(snap, "m.py", 4).qualified_name == "top"
    assert smallest_containing_symbol(snap, "m.py", 99) is None  # no symbol -> None, never invented


# ── TESTED_BY rule (design §5.4) ────────────────────────────────


def test_module_path_from_test_file():
    assert module_path_from_test_file("tests/test_math.py") == "tests/math.py"
    assert module_path_from_test_file("app/calc.test.ts") == "app/calc.ts"
    assert module_path_from_test_file("math_test.go") == "math.go"
    assert module_path_from_test_file("math_test.rs") == "math.rs"
    assert module_path_from_test_file("not_a_test.py") is None
    assert TESTED_BY_RULE  # provenance recorded


def test_tested_symbols_via_rule():
    files = {
        "math_utils.py": b"def add(a, b):\n    return a + b\n\ndef unused(x):\n    return x\n",
        "test_math_utils.py": b"def test_add():\n    assert add(1, 2) == 3\n",
        "other.py": b"def lonely():\n    pass\n",
    }
    snap = _snapshot(files)
    tested = lang_mod.tested_symbols(snap)
    assert "add" in tested and "unused" in tested  # whole module is tested
    assert "lonely" not in tested  # no matching test file -> not claimed tested (deferred)
