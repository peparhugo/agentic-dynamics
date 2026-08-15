"""Tests for multi-language analysis module."""

import tempfile
from pathlib import Path

from instrument.language import (
    _PROFILES,
    detect_language,
    get_parser,
    parse_codebase,
)


class TestDetectLanguage:
    def test_detects_python(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "app.py").write_text("x = 1\n")
            (Path(d) / "test_app.py").write_text("def test(): pass\n")
            profile = detect_language(Path(d))
            assert profile is not None
            assert profile.name == "python"
            assert profile.file_count == 2

    def test_detects_typescript(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "index.ts").write_text("const x = 1;\n")
            (Path(d) / "util.tsx").write_text("const y = 2;\n")
            profile = detect_language(Path(d))
            assert profile is not None
            assert profile.name == "typescript"
            assert profile.file_count == 2

    def test_returns_none_for_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "readme.md").write_text("# hello\n")
            profile = detect_language(Path(d))
            assert profile is None

    def test_all_profiles_have_required_fields(self):
        for name, profile in _PROFILES.items():
            assert profile.name == name
            assert len(profile.extensions) > 0
            assert profile.tree_sitter_id
            assert profile.test_framework
            assert profile.test_file_pattern


class TestParseCodebase:
    def test_parses_python_files(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "main.py").write_text(
                "import os\n\n"
                "def greet(name: str) -> str:\n"
                "    return f'Hello {name}'\n\n"
                "class Calculator:\n"
                "    def add(self, a: int, b: int) -> int:\n"
                "        return a + b\n"
            )
            ast = parse_codebase(dp)
            assert ast is not None
            assert ast.language == "python"
            assert len(ast.files) == 1
            assert ast.function_count == 2
            assert ast.class_count == 1
            assert ast.import_count >= 1

    def test_parses_multiple_files(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "a.py").write_text("import sys\n\ndef foo(): pass\n")
            (dp / "b.py").write_text("from typing import List\n\ndef bar(): pass\n")
            ast = parse_codebase(dp)
            assert ast is not None
            assert len(ast.files) == 2
            assert ast.function_count == 2
            assert ast.import_count >= 2

    def test_skips_non_source_files(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "app.py").write_text("x = 1\n")
            (dp / "readme.md").write_text("# docs\n")
            (dp / "data.json").write_text('{"key": "val"}\n')
            ast = parse_codebase(dp)
            assert ast is not None
            assert len(ast.files) == 1

    def test_returns_none_for_no_source_files(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "readme.md").write_text("# hello\n")
            ast = parse_codebase(dp)
            assert ast is None

    def test_codebase_ast_to_dict(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "app.py").write_text("x = 1\n")
            ast = parse_codebase(dp)
            assert ast is not None
            d = ast.to_dict()
            assert d["language"] == "python"
            assert "app.py" in d["files"]
            assert d["total_loc"] >= 1

    def test_parses_typescript(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "index.ts").write_text(
                "import { readFile } from 'fs';\n\n"
                "function greet(name: string): string {\n"
                "  return `Hello ${name}`;\n"
                "}\n\n"
                "class Calculator {\n"
                "  add(a: number, b: number): number {\n"
                "    return a + b;\n"
                "  }\n"
                "}\n"
            )
            ast = parse_codebase(dp)
            assert ast is not None
            assert ast.language == "typescript"
            assert ast.function_count >= 1
            assert ast.class_count >= 1


class TestGetParser:
    def test_python_parser_works(self):
        parser = get_parser("python")
        tree = parser.parse(b"x = 1\n")
        assert tree.root_node.type == "module"

    def test_typescript_parser_works(self):
        parser = get_parser("typescript")
        tree = parser.parse(b"const x = 1;\n")
        assert tree.root_node.type == "program"
