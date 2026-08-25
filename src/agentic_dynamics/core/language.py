"""Multi-language codebase analysis through tree-sitter.

Provides a unified API for parsing and analyzing codebases across
Python, TypeScript, Go, and Rust. The analysis logic is identical
regardless of language — only the grammar changes.
"""

from __future__ import annotations

import hashlib
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


# ── Typed CodeSnapshot / CodeDelta (evidence-integrity e2) ──────
#
# Design: docs/designs/current/cap_evidence_integrity_design.md §5.3. A CodeSnapshot is the
# typed, revision-scoped symbol surface of a codebase (files -> symbols with kind, qualified
# name, and source span); a CodeDelta(before, after) computes added/removed/changed symbols,
# imports, and call edges. This lives in ``core`` (tier 0) so both the measurement plane
# (commit_analysis) and the knowledge plane (code_ingestion / graph) consume the same
# primitives without a measurement<->knowledge cycle. The two-ID contract
# (entity_id/version_id) lands here too — renames are recorded as new entities (no implicit
# matching).


@dataclass(frozen=True)
class SourceSpan:
    """A symbol's 1-based source span in its file (start is inclusive, end exclusive-ish)."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.start_line, self.start_col, self.end_line, self.end_col)

    def to_dict(self) -> dict[str, int]:
        return {
            "start_line": self.start_line,
            "start_col": self.start_col,
            "end_line": self.end_line,
            "end_col": self.end_col,
        }


def _module_slot(file_path: str) -> str:
    """The module slot of a source file: path minus extension, ``/`` → ``.``.

    ``pkg/__init__.py`` → ``pkg``; ``pkg/mod.py`` → ``pkg.mod``. This is the module identity
    slot the two-ID contract hashes (design §5.3).
    """
    p = Path(file_path.replace("\\", "/"))
    if p.name == "__init__.py":
        stem = str(p.parent)
    else:
        stem = str(p.with_suffix(""))
    return stem.replace("/", ".") or p.name


@dataclass(frozen=True)
class CodeSymbol:
    """One function/class with the typed identity surface (design §5.3).

    ``qualified_name`` is the module-relative qualified name (methods become
    ``ClassName.method_name``); ``source_span`` is its 1-based span; ``content_hash`` is the
    sha256 of the node's source bytes (deterministic change detection); ``calls`` are the
    best-effort called names within the body (name-based call edges).
    """

    name: str
    kind: str  # "function" | "class"
    qualified_name: str
    file_path: str
    module_name: str
    source_span: SourceSpan
    content_hash: str
    calls: tuple[str, ...] = ()

    def entity_key(self) -> tuple[str, str, str]:
        """The stable slot identity within a snapshot: (file, qualified name, kind)."""
        return (self.file_path, self.qualified_name, self.kind)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "qualified_name": self.qualified_name,
            "file_path": self.file_path,
            "module_name": self.module_name,
            "source_span": self.source_span.to_dict(),
            "content_hash": self.content_hash,
            "calls": list(self.calls),
        }


@dataclass
class CodeSnapshot:
    """A typed, revision-scoped symbol surface of one codebase revision."""

    revision: str
    language: str
    files: dict[str, list[CodeSymbol]] = field(default_factory=dict)
    imports: dict[str, list[str]] = field(default_factory=dict)
    file_hashes: dict[str, str] = field(default_factory=dict)
    unparsed_files: list[str] = field(default_factory=list)

    @property
    def parsed_files(self) -> list[str]:
        return sorted(self.files)

    @property
    def all_symbols(self) -> list[CodeSymbol]:
        return [sym for path in sorted(self.files) for sym in self.files[path]]

    def symbol_by_key(self) -> dict[tuple[str, str, str], CodeSymbol]:
        return {sym.entity_key(): sym for sym in self.all_symbols}

    def parse_coverage(self) -> float | None:
        """Fraction of source files parsed by tree-sitter, or None when no source files.

        The ``ast_parse_coverage`` fact's source (design §5.6): parsed / (parsed + unparsed).
        """
        total = len(self.parsed_files) + len(self.unparsed_files)
        if total == 0:
            return None
        return len(self.parsed_files) / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "language": self.language,
            "parse_coverage": self.parse_coverage(),
            "files": {
                path: [sym.to_dict() for sym in syms]
                for path, syms in sorted(self.files.items())
            },
            "imports": {path: imps for path, imps in sorted(self.imports.items())},
            "unparsed_files": self.unparsed_files,
        }


@dataclass
class CodeDelta:
    """The typed change between two CodeSnapshots (design §5.3)."""

    before: CodeSnapshot
    after: CodeSnapshot
    added_symbols: list[CodeSymbol] = field(default_factory=list)
    removed_symbols: list[CodeSymbol] = field(default_factory=list)
    changed_symbols: list[CodeSymbol] = field(default_factory=list)
    added_files: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    added_imports: dict[str, list[str]] = field(default_factory=dict)
    removed_imports: dict[str, list[str]] = field(default_factory=dict)
    added_call_edges: list[tuple[str, str]] = field(default_factory=list)
    removed_call_edges: list[tuple[str, str]] = field(default_factory=list)

    @property
    def changed_symbol_count(self) -> int:
        return len(self.added_symbols) + len(self.removed_symbols) + len(self.changed_symbols)

    def to_dict(self) -> dict[str, Any]:
        return {
            "before": self.before.revision,
            "after": self.after.revision,
            "changed_symbol_count": self.changed_symbol_count,
            "added_symbols": [s.to_dict() for s in self.added_symbols],
            "removed_symbols": [s.to_dict() for s in self.removed_symbols],
            "changed_symbols": [s.to_dict() for s in self.changed_symbols],
            "added_files": self.added_files,
            "removed_files": self.removed_files,
            "changed_files": self.changed_files,
            "added_imports": self.added_imports,
            "removed_imports": self.removed_imports,
            "added_call_edges": [list(e) for e in self.added_call_edges],
            "removed_call_edges": [list(e) for e in self.removed_call_edges],
        }


# ── Symbol extraction (pure tree-sitter) ────────────────────────

_NAME_NODE_TYPES = ("identifier", "type_identifier", "field_identifier")


def _node_name_text(node, source_bytes: bytes) -> str:
    """A node's symbol name (its ``name`` field, with an identifier fallback)."""
    name_node = node.child_by_field_name("name")
    if name_node is not None and name_node.text:
        return name_node.text.decode()
    for child in node.children:
        if child.type in _NAME_NODE_TYPES and child.text:
            return child.text.decode()
    return ""


def _call_names_within(node) -> set[str]:
    """Best-effort called names inside ``node`` (last dotted segment of each ``call``)."""
    names: set[str] = set()

    def walk(n) -> None:
        if n.type == "call":
            fn = n.child_by_field_name("function")
            if fn is not None and fn.text:
                last = fn.text.decode().rsplit(".", 1)[-1].strip()
                if last and (last[0].isalpha() or last[0] == "_"):
                    names.add(last)
        for child in n.children:
            walk(child)

    walk(node)
    return names


def _import_names_within(node) -> set[str]:
    """Best-effort imported targets inside an import node (dotted names / strings)."""
    names: set[str] = set()

    def walk(n) -> None:
        if n.type in ("dotted_name", "string", "module_name", "identifier") and n.text:
            names.add(n.text.decode().strip("\"'"))
        for child in n.children:
            walk(child)

    walk(node)
    return names


def _symbol_from_ts_node(
    node, kind: str, source_bytes: bytes, file_path: str, module_name: str, enclosing: list[str]
) -> CodeSymbol | None:
    """Build a :class:`CodeSymbol` from a function/class tree-sitter node, or ``None``."""
    name = _node_name_text(node, source_bytes)
    if not name:
        return None
    qualified_name = ".".join([*enclosing, name])
    span = SourceSpan(
        start_line=node.start_point[0] + 1,
        start_col=node.start_point[1] + 1,
        end_line=node.end_point[0] + 1,
        end_col=node.end_point[1] + 1,
    )
    content = node.text if node.text is not None else b""
    return CodeSymbol(
        name=name,
        kind=kind,
        qualified_name=qualified_name,
        file_path=file_path,
        module_name=module_name,
        source_span=span,
        content_hash=hashlib.sha256(content).hexdigest(),
        calls=tuple(sorted(_call_names_within(node))),
    )


def _extract_symbols_and_imports(
    parser, source_bytes: bytes, file_path: str, profile: LanguageProfile
) -> tuple[list[CodeSymbol], list[str]]:
    """One pass over a parse tree: symbols (with qualified names + spans) and imports."""
    func_types = set(profile.function_node_types)
    class_types = set(profile.class_node_types)
    import_types = set(profile.import_node_types)
    module_name = _module_slot(file_path)
    symbols: list[CodeSymbol] = []
    imports: set[str] = set()
    enclosing: list[str] = []

    def walk(node) -> None:
        if node.type in func_types:
            sym = _symbol_from_ts_node(node, "function", source_bytes, file_path, module_name, enclosing)
            if sym is not None:
                symbols.append(sym)
        elif node.type in class_types:
            sym = _symbol_from_ts_node(node, "class", source_bytes, file_path, module_name, enclosing)
            if sym is not None:
                symbols.append(sym)
                enclosing.append(sym.name)
        elif node.type in import_types:
            imports.update(_import_names_within(node))
        for child in node.children:
            walk(child)
        if node.type in class_types:
            enclosing.pop()

    walk(parser.parse(source_bytes).root_node)
    return symbols, sorted(imports)


def _dominant_profile(files: dict[str, bytes]) -> LanguageProfile | None:
    """Pick the language profile matching the most files in ``files``."""
    counts = {name: 0 for name in _PROFILES}
    for path in files:
        suffix = Path(path).suffix
        for name, profile in _PROFILES.items():
            if suffix in profile.extensions:
                counts[name] += 1
    best = max(counts, key=lambda k: counts[k])
    return _PROFILES[best] if counts[best] > 0 else None


def build_code_snapshot(
    files: dict[str, bytes],
    *,
    revision: str,
    profile: LanguageProfile | None = None,
) -> CodeSnapshot:
    """Build a typed :class:`CodeSnapshot` from ``files`` (repo-relative path -> source bytes).

    Pure tree-sitter: symbols carry ``qualified_name`` and ``source_span``, per-file imports
    and content hashes are recorded, and files that fail to parse are recorded in
    ``unparsed_files`` (the parse-coverage fact) — never a crash. ``profile`` defaults to the
    dominant supported language in ``files``.
    """
    if profile is None:
        profile = _dominant_profile(files)
    if profile is None:
        return CodeSnapshot(
            revision=revision,
            language="",
            files={},
            imports={},
            file_hashes={},
            unparsed_files=sorted(files),
        )
    parser = get_parser(profile.tree_sitter_id)
    extensions = set(profile.extensions)

    symbols_by_file: dict[str, list[CodeSymbol]] = {}
    imports_by_file: dict[str, list[str]] = {}
    file_hashes: dict[str, str] = {}
    unparsed: list[str] = []

    for path in sorted(files):
        p = Path(path)
        if p.suffix not in extensions or _should_skip(p):
            continue
        source = files[path]
        file_hashes[path] = hashlib.sha256(source).hexdigest()
        try:
            tree = parser.parse(source)
        except Exception:
            unparsed.append(path)
            continue
        if tree.root_node.has_error:
            unparsed.append(path)
            continue
        syms, imports = _extract_symbols_and_imports(parser, source, path, profile)
        symbols_by_file[path] = syms
        imports_by_file[path] = imports

    return CodeSnapshot(
        revision=revision,
        language=profile.name,
        files=symbols_by_file,
        imports=imports_by_file,
        file_hashes=file_hashes,
        unparsed_files=sorted(unparsed),
    )


def _file_content_unchanged(before: CodeSnapshot, after: CodeSnapshot, path: str) -> bool:
    """True when ``path``'s symbol surface + imports are identical across the two snapshots.

    Files that failed to parse on either side have no symbol surface (they live in
    ``unparsed_files``, not ``files``), so they compare by content hash instead — hashes are
    recorded for every source file regardless of parseability. This keeps a file that BECOMES
    unparseable (or parseable) in the change universe instead of vanishing from the
    ``changed_files`` list, which would make ``ast_parse_coverage`` structurally 1.0.
    """
    if path in before.files and path in after.files:
        return (
            before.files[path] == after.files[path]
            and before.imports.get(path) == after.imports.get(path)
        )
    return before.file_hashes.get(path) == after.file_hashes.get(path)


def compute_code_delta(before: CodeSnapshot, after: CodeSnapshot) -> CodeDelta:
    """Compute the typed :class:`CodeDelta` between two snapshots.

    Symbols are keyed by ``(file, qualified_name, kind)`` — a rename is a new entity (no
    implicit matching, design §5.3). ``changed`` symbols are present in both with differing
    ``content_hash``. Imports and call edges are set-diffed per file / across the snapshot.
    """
    b_syms = before.symbol_by_key()
    a_syms = after.symbol_by_key()
    b_keys = set(b_syms)
    a_keys = set(a_syms)

    added = [a_syms[k] for k in sorted(a_keys - b_keys)]
    removed = [b_syms[k] for k in sorted(b_keys - a_keys)]
    changed = [
        a_syms[k]
        for k in sorted(a_keys & b_keys)
        if b_syms[k].content_hash != a_syms[k].content_hash
    ]

    b_files = set(before.files) | set(before.unparsed_files)
    a_files = set(after.files) | set(after.unparsed_files)
    changed_files = sorted(
        f
        for f in (a_files & b_files)
        if not _file_content_unchanged(before, after, f)
    )

    added_imports = {
        f: sorted(set(after.imports.get(f, [])) - set(before.imports.get(f, [])))
        for f in sorted(a_files)
    }
    removed_imports = {
        f: sorted(set(before.imports.get(f, [])) - set(after.imports.get(f, [])))
        for f in sorted(b_files)
    }

    def call_edges(snapshot: CodeSnapshot) -> set[tuple[str, str]]:
        return {
            (sym.qualified_name, callee)
            for sym in snapshot.all_symbols
            for callee in sym.calls
        }

    b_edges = call_edges(before)
    a_edges = call_edges(after)

    return CodeDelta(
        before=before,
        after=after,
        added_symbols=added,
        removed_symbols=removed,
        changed_symbols=changed,
        added_files=sorted(a_files - b_files),
        removed_files=sorted(b_files - a_files),
        changed_files=changed_files,
        added_imports={f: v for f, v in added_imports.items() if v},
        removed_imports={f: v for f, v in removed_imports.items() if v},
        added_call_edges=sorted(a_edges - b_edges),
        removed_call_edges=sorted(b_edges - a_edges),
    )


# ── Two-ID contract (design §5.3) ───────────────────────────────

def module_entity_id(repository_id: str, module_name: str) -> str:
    """Stable logical slot for a module: ``f(repository_id, module_name)``."""
    return hashlib.sha256(f"{repository_id}|module|{module_name}".encode()).hexdigest()


def module_version_id(entity_id: str, revision: str, content_hash: str) -> str:
    """Immutable module version: ``f(entity_id, commit, content_hash)``."""
    return hashlib.sha256(f"{entity_id}|{revision}|{content_hash}".encode()).hexdigest()


def symbol_entity_id(repository_id: str, file_path: str, qualified_name: str, kind: str) -> str:
    """Stable logical slot for a symbol: ``f(repository_id, path, qualified_name, kind)``."""
    return hashlib.sha256(
        f"{repository_id}|symbol|{file_path}|{qualified_name}|{kind}".encode()
    ).hexdigest()


def symbol_version_id(entity_id: str, revision: str, content_hash: str) -> str:
    """Immutable symbol version: ``f(entity_id, commit, content_hash)``."""
    return hashlib.sha256(f"{entity_id}|{revision}|{content_hash}".encode()).hexdigest()


# ── Issue→symbol linking + TESTED_BY rule (design §5.4) ─────────

def smallest_containing_symbol(snapshot: CodeSnapshot, file_path: str, line: int) -> CodeSymbol | None:
    """The smallest symbol in ``file_path`` whose source span contains ``line``.

    The issue→symbol link (design §5.4): an issue/diagnostic at a line is attributed to the
    smallest containing symbol — a method over its class over the module. Ties resolve to the
    symbol defined later (more specific). Returns ``None`` when no symbol contains the line
    (the issue stays symbol-less, never invented).
    """
    best: CodeSymbol | None = None
    for sym in snapshot.files.get(file_path, []):
        sp = sym.source_span
        if not (sp.start_line <= line <= sp.end_line):
            continue
        if best is None:
            best = sym
            continue
        size = sp.end_line - sp.start_line
        best_size = best.source_span.end_line - best.source_span.start_line
        if size < best_size or (size == best_size and sp.start_line > best.source_span.start_line):
            best = sym
    return best


#: The TESTED_BY derivation rule, recorded as provenance (design §5.4). Deterministic
#: test-linking: a test file tests the module whose path is derived by stripping the language's
#: test marker from the test file's basename (``test_<m>.py`` → ``<m>.py``,
#: ``<m>.test.ts`` → ``<m>.ts``, ``<m>_test.go`` → ``<m>.go``, ``<m>_test.rs`` → ``<m>.rs``).
#: A symbol is TESTED_BY a test file iff such a match exists in the snapshot. Where the rule
#: cannot derive a match, the symbol is NOT claimed tested — ``changed_symbols_with_tests_ratio``
#: is DEFERRED (fact omitted), never invented.
TESTED_BY_RULE = (
    "test-file->module name matching (deterministic): test_<m>.py -> <m>.py, "
    "<m>.test.ts -> <m>.ts, <m>_test.go -> <m>.go, <m>_test.rs -> <m>.rs; "
    "a symbol in module M is tested iff a matching test file exists in the snapshot; "
    "non-derivable matches are omitted (deferred), never invented."
)


def module_path_from_test_file(test_file_path: str) -> str | None:
    """Apply the TESTED_BY rule: the module file a test file tests, or ``None``.

    Language-aware (matches the profile ``test_file_pattern`` conventions): ``test_<m>.py`` →
    ``<m>.py``; ``<m>.test.ts`` → ``<m>.ts``; ``<m>_test.go`` → ``<m>.go``; ``<m>_test.rs`` →
    ``<m>.rs``. No recognized marker for the file's language → ``None`` (the symbol is not
    claimed tested).
    """
    p = Path(test_file_path.replace("\\", "/"))
    name = p.name
    if name.startswith("test_") and name.endswith(".py"):
        return str(p.with_name(name[len("test_"):]))
    if name.endswith(".ts") or name.endswith(".tsx"):
        if ".test." in name:
            return str(p.with_name(name.replace(".test.", ".", 1)))
        return None
    if name.endswith(".go") or name.endswith(".rs"):
        if "_test" in name:
            return str(p.with_name(name.replace("_test", "", 1)))
        return None
    return None


def tested_symbols(snapshot: CodeSnapshot) -> set[str]:
    """Symbol qualified names whose module has a matching test file (TESTED_BY rule)."""
    module_files = set(snapshot.files)
    tested: set[str] = set()
    for test_file in module_files:
        module_file = module_path_from_test_file(test_file)
        if module_file is None or module_file not in module_files:
            continue
        for sym in snapshot.files[module_file]:
            tested.add(sym.qualified_name)
    return tested
