"""Multi-language codebase analysis through tree-sitter.

Provides a unified API for parsing and analyzing codebases across
Python, TypeScript, Go, and Rust. The analysis logic is identical
regardless of language — only the grammar changes.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)
    import tree_sitter_languages
    from tree_sitter import Node, Parser, Tree


@dataclass
class LanguageProfile:
    """Everything the analyzer needs to know about a language."""

    name: str
    extensions: list[str]
    tree_sitter_id: str
    test_framework: str
    test_file_pattern: str
    # Per-language file counts (populated after scan)
    file_count: int = 0
    total_loc: int = 0
    functions: int = 0
    classes: int = 0
    imports: int = 0

    # tree-sitter node type names vary by language grammar
    @property
    def function_node_types(self) -> list[str]:
        return {
            "python": ["function_definition"],
            "typescript": ["function_declaration", "method_definition"],
            "go": ["function_declaration"],
            "rust": ["function_item"],
        }.get(self.name, ["function_definition"])

    @property
    def class_node_types(self) -> list[str]:
        return {
            "python": ["class_definition"],
            "typescript": ["class_declaration"],
            "go": ["type_declaration"],
            "rust": ["struct_item", "impl_item"],
        }.get(self.name, ["class_definition"])

    @property
    def import_node_types(self) -> list[str]:
        return {
            "python": ["import_statement", "import_from_statement"],
            "typescript": ["import_statement", "lexical_declaration"],
            "go": ["import_declaration"],
            "rust": ["use_declaration"],
        }.get(self.name, ["import_statement"])


# Registry of supported languages.
_PROFILES: dict[str, LanguageProfile] = {
    "python": LanguageProfile(
        name="python",
        extensions=[".py"],
        tree_sitter_id="python",
        test_framework="pytest",
        test_file_pattern="test_*.py",
    ),
    "typescript": LanguageProfile(
        name="typescript",
        extensions=[".ts", ".tsx"],
        tree_sitter_id="typescript",
        test_framework="jest",
        test_file_pattern="*.test.ts",
    ),
    "go": LanguageProfile(
        name="go",
        extensions=[".go"],
        tree_sitter_id="go",
        test_framework="go test",
        test_file_pattern="*_test.go",
    ),
    "rust": LanguageProfile(
        name="rust",
        extensions=[".rs"],
        tree_sitter_id="rust",
        test_framework="cargo test",
        test_file_pattern="*_test.rs",
    ),
}


# Directories to skip when walking codebases
_SKIP_DIRS = {"__pycache__", "node_modules", ".git", "dist", "build", "venv", ".venv", ".pytest_cache"}


def _should_skip(path: Path) -> bool:
    """Check if a path should be skipped during codebase analysis."""
    return any(skip in path.parts for skip in _SKIP_DIRS)


def detect_language(path: Path) -> LanguageProfile | None:
    """Detect the dominant programming language in a directory.

    Scans files by extension and returns the profile for the
    language with the most files. Returns None if no supported
    language is found.
    """
    counts: dict[str, int] = {}
    for profile in _PROFILES.values():
        for ext in profile.extensions:
            # Use glob for performance on large directories
            count = len(list(path.rglob(f"*{ext}")))
            if count > 0:
                counts[profile.name] = counts.get(profile.name, 0) + count

    if not counts:
        return None

    dominant = max(counts, key=lambda k: counts[k])
    profile = _PROFILES[dominant]
    profile.file_count = counts[dominant]
    return profile


def get_parser(language_id: str) -> Parser:
    """Get a tree-sitter parser for the given language."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        return tree_sitter_languages.get_parser(language_id)


@dataclass
class ASTNode:
    """A lightweight AST node for analysis."""

    type: str
    text: str
    start_line: int
    end_line: int
    children: list[ASTNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "text": self.text[:200],
            "start_line": self.start_line,
            "end_line": self.end_line,
            "children": [c.to_dict() for c in self.children],
        }


def _ts_to_ast(node: Node, source: bytes) -> ASTNode:
    """Convert a tree-sitter Node to our lightweight ASTNode."""
    text = node.text.decode() if node.text else ""
    children = [_ts_to_ast(c, source) for c in node.children]
    return ASTNode(
        type=node.type,
        text=text,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        children=children,
    )


@dataclass
class CodebaseAST:
    """Parsed representation of an entire codebase."""

    language: str
    files: dict[str, ASTNode] = field(default_factory=dict)
    total_loc: int = 0
    function_count: int = 0
    class_count: int = 0
    import_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "files": {f: n.to_dict() for f, n in self.files.items()},
            "total_loc": self.total_loc,
            "function_count": self.function_count,
            "class_count": self.class_count,
            "import_count": self.import_count,
        }


def parse_codebase(path: Path, profile: LanguageProfile | None = None) -> CodebaseAST | None:
    """Parse all source files in a directory using tree-sitter.

    Args:
        path: Root directory of the codebase.
        profile: Language profile. Auto-detected if None.

    Returns:
        CodebaseAST with parsed files and aggregate statistics,
        or None if no supported files found.
    """
    if profile is None:
        profile = detect_language(path)
    if profile is None:
        return None

    parser = get_parser(profile.tree_sitter_id)
    ast = CodebaseAST(language=profile.name)
    extensions = set(profile.extensions)
    func_types = profile.function_node_types
    class_types = profile.class_node_types
    import_types = profile.import_node_types

    for file_path in path.rglob("*"):
        if file_path.is_dir():
            continue
        if _should_skip(file_path):
            continue
        if file_path.suffix not in extensions:
            continue
        try:
            source = file_path.read_bytes()
        except (OSError, UnicodeDecodeError):
            continue

        tree = parser.parse(source)
        root = _ts_to_ast(tree.root_node, source)
        ast.files[str(file_path.relative_to(path))] = root

        # Count structural elements
        ast.total_loc += len(source.split(b"\n"))
        for node in _walk_collect(tree.root_node):
            if node.type in func_types:
                ast.function_count += 1
            elif node.type in class_types:
                ast.class_count += 1
            elif node.type in import_types:
                ast.import_count += 1

    return ast


def _walk_collect(node: Node) -> list[Node]:
    """Collect all nodes in a tree for counting."""
    result = [node]
    for child in node.children:
        result.extend(_walk_collect(child))
    return result


def collect_imports(tree: Tree, source: bytes) -> list[str]:
    """Extract all imported module names from a tree."""
    imports: list[str] = []
    _collect_imports(tree.root_node, imports, source)
    return imports


def _collect_imports(node: Node, imports: list[str], source: bytes) -> None:
    """Recursively collect import targets."""
    if node.type in ("import_statement", "import_from_statement",
                     "import_declaration"):
        for child in node.children:
            if child.type == "dotted_name" or child.type == "string":
                text = child.text.decode().strip("\"'")
                if text:
                    imports.append(text)
    for child in node.children:
        _collect_imports(child, imports, source)


def collect_functions(tree: Tree, source: bytes) -> list[dict[str, Any]]:
    """Extract all function definitions with metadata."""
    funcs: list[dict[str, Any]] = []
    _collect_functions(tree.root_node, funcs, source)
    return funcs


def _collect_functions(node: Node, funcs: list[dict[str, Any]], source: bytes) -> None:
    if node.type == "function_definition":
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break
        funcs.append({
            "name": name_node.text.decode() if name_node else "unknown",
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "loc": node.end_point[0] - node.start_point[0] + 1,
        })
    for child in node.children:
        _collect_functions(child, funcs, source)
