"""Tests for code-structure ingestion (code_ingestion).

Covers the extractor contract constants, one-record-per-function/class derivation, the
``source_type=code`` / ``Authority.SOURCE`` / ``[C]`` provenance, symbol/language correctness,
the signature-summary text (name + params + docstring head, no full body), identity derivation
(entity_id unique per symbol, knowledge_id folds the injected revision), the reused
artifact/event round-trip, determinism (same revision → same ids), and the
``load_codebase_graph`` wiring (de-orphaned via ``ingest_codebase_graph``).
"""

import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from agentic_dynamics.knowledge import code_ingestion as ci
from agentic_dynamics.knowledge.knowledge import Authority, KnowledgeRecord, compute_entity_id, compute_knowledge_id
from agentic_dynamics.knowledge.knowledge_ingestion import (
    extract_record,
    record_to_artifact,
    record_to_event,
)
from agentic_dynamics.core.language import _PROFILES, parse_codebase

REPO = "test-repo"
REVISION = "abc1234"

# A single module with two top-level functions, one class, and one method (a nested function).
_SRC = '''\
"""Math helpers."""


def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b


def subtract(a: int, b: int) -> int:
    return a - b


class Calculator:
    """A simple calculator."""

    def multiply(self, x, y):
        """Multiply x by y."""
        return x * y
'''


def _write_codebase(root: Path) -> Path:
    """Write a two-file Python codebase and return the root.

    ``math_utils.py`` holds the symbol-rich module above; ``app.py`` is a bare file so the
    file path (``logical_locator``) is exercised across more than one module.
    """
    (root / "math_utils.py").write_text(_SRC)
    (root / "app.py").write_text("import math_utils\n\nx = math_utils.add(1, 2)\n")
    return root


def _records_by_symbol(records):
    """Index records by their single symbol name for focused assertions."""
    return {rec.symbols[0]: rec for rec in records}


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert ci.EXTRACTOR_VERSION == "code/v1"
    assert ci.SOURCE_TYPE == "code"
    assert ci.ACL_SCOPE == "public"


# ── One record per function/class ───────────────────────────────


def test_one_record_per_function_and_class():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    by = _records_by_symbol(records)
    # A record for each function (add, subtract, the nested method multiply) and the class.
    assert set(by) == {"add", "subtract", "multiply", "Calculator"}
    assert all(rec.source_type == "code" for rec in records)


def test_symbols_and_language_correct():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    by = _records_by_symbol(records)
    assert by["add"].symbols == ["add"]
    assert by["Calculator"].symbols == ["Calculator"]
    assert all(rec.language == "python" for rec in records)


def test_authority_source_and_evidence_class_c():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    assert all(rec.authority is Authority.SOURCE for rec in records)
    assert all(rec.evidence_class == "[C]" for rec in records)


def test_logical_locator_is_file_path():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    by = _records_by_symbol(records)
    assert by["add"].logical_locator == "math_utils.py"
    assert by["multiply"].logical_locator == "math_utils.py"
    assert all(rec.logical_locator.endswith(".py") for rec in records)


# ── Signature-summary text ──────────────────────────────────────


def test_text_is_signature_summary_with_docstring():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    by = _records_by_symbol(records)
    assert by["add"].text == "add(a: int, b: int) — Return the sum of a and b."
    # No docstring → signature alone, still no full body.
    assert by["subtract"].text == "subtract(a: int, b: int)"
    # Class record carries just the name (no parameters field).
    assert by["Calculator"].text == "Calculator — A simple calculator."
    # The body is never embedded.
    assert "return a + b" not in by["add"].text


# ── Identity derivation ─────────────────────────────────────────


def test_source_revision_is_injected_head_sha():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    assert all(rec.commit_sha == REVISION for rec in records)
    # knowledge_id folds the injected revision.
    add = _records_by_symbol(records)["add"]
    assert compute_knowledge_id(add.entity_id, REVISION, add.content_hash, ci.EXTRACTOR_VERSION) == add.knowledge_id


def test_entity_id_unique_per_symbol_same_file():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    by = _records_by_symbol(records)
    # add and subtract share the same logical_locator (file) but must be distinct entities.
    assert by["add"].logical_locator == by["subtract"].logical_locator
    assert by["add"].entity_id != by["subtract"].entity_id
    assert by["add"].knowledge_id != by["subtract"].knowledge_id


def test_entity_id_derived_from_repository_source_and_locator():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    add = _records_by_symbol(records)["add"]
    assert add.entity_id == compute_entity_id(REPO, "file://math_utils.py#add", "math_utils.py")


# ── Reused artifact/event round-trip ────────────────────────────


def test_artifact_round_trip_preserves_code_record():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    record = _records_by_symbol(records)["add"]
    artifact = record_to_artifact(record)
    event = record_to_event(record)

    # content_hash is the sha256 of the durable per-record artifact (the reused contract).
    assert record.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.content_hash == record.content_hash

    extracted = extract_record(event, artifact)
    assert extracted.source_type == "code"
    assert extracted.authority is Authority.SOURCE
    assert extracted.evidence_class == "[C]"
    assert extracted.symbols == ["add"]
    assert extracted.language == "python"
    assert extracted.logical_locator == "math_utils.py"
    assert extracted.text == record.text
    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash


def test_artifact_serialization_blanks_derived_ids():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    record = _records_by_symbol(records)["add"]
    # The durable artifact is a pure function of stable content: re-serializing the final record
    # (with real ids/timestamps) hashes to the same bytes.
    assert record_to_artifact(record) == record_to_artifact(KnowledgeRecord.from_dict(record.to_dict()))


# ── Determinism ─────────────────────────────────────────────────


def test_deterministic_across_derivations_and_timestamps():
    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        a = ci.derive_code_records(_PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=root,
                                   now=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc))
        b = ci.derive_code_records(_PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=root,
                                   now=datetime(2026, 8, 16, 9, 30, 0, tzinfo=timezone.utc))
    assert [r.knowledge_id for r in a] == [r.knowledge_id for r in b]
    assert [r.content_hash for r in a] == [r.content_hash for r in b]


def test_revision_change_yields_new_knowledge_id_same_entity():
    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        a = ci.derive_code_records(_PROFILES["python"], repository_id=REPO, revision="abc", repo_root=root)
        b = ci.derive_code_records(_PROFILES["python"], repository_id=REPO, revision="def", repo_root=root)
    add_a = _records_by_symbol(a)["add"]
    add_b = _records_by_symbol(b)["add"]
    assert add_a.knowledge_id != add_b.knowledge_id
    assert add_a.entity_id == add_b.entity_id  # same logical symbol


# ── Input flexibility ───────────────────────────────────────────


def test_accepts_codebase_ast_as_profile():
    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        ast = parse_codebase(root)
        records = ci.derive_code_records(ast, repository_id=REPO, revision=REVISION, repo_root=root)
    assert set(_records_by_symbol(records)) == {"add", "subtract", "multiply", "Calculator"}


def test_empty_codebase_returns_empty():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "readme.md").write_text("# nothing here\n")
        records = ci.derive_code_records(_PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=root)
    assert records == []


def test_build_code_record_matches_derive_content():
    with tempfile.TemporaryDirectory() as d:
        records = ci.derive_code_records(
            _PROFILES["python"], repository_id=REPO, revision=REVISION, repo_root=_write_codebase(Path(d))
        )
    add = _records_by_symbol(records)["add"]
    # Reconstructing the same symbol via the direct builder yields the *same* identity — the
    # durable artifact blanks the volatile timestamps, so content_hash (and knowledge_id) are
    # a pure function of the symbol's stable content, independent of when each was derived.
    direct = ci.build_code_record(
        ci._CodeSymbol(name="add", kind="function", signature="add(a: int, b: int)",
                       docstring_head="Return the sum of a and b."),
        "math_utils.py", "python", repository_id=REPO, revision=REVISION,
        now=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert direct.source_type == "code"
    assert direct.authority is Authority.SOURCE
    assert direct.symbols == ["add"]
    assert direct.logical_locator == "math_utils.py"
    assert direct.content_hash == add.content_hash
    assert direct.knowledge_id == add.knowledge_id


# ── load_codebase_graph wiring (de-orphaned) ────────────────────


def test_ingest_codebase_graph_wires_load_codebase_graph():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def load_codebase_graph(self, graph, worktree_name):
            self.calls.append((graph, worktree_name))
            return {"modules": len(graph.modules)}

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        fake = FakeClient()
        counts = ci.ingest_codebase_graph(fake, root, worktree_name="wt_code")
    # build_graph → load_codebase_graph was invoked exactly once with the worktree name.
    assert len(fake.calls) == 1
    graph, wt = fake.calls[0]
    assert wt == "wt_code"
    assert counts == {"modules": len(graph.modules)}
    assert "math_utils.py" in graph.modules
    assert "app.py" in graph.modules


def test_ingest_codebase_graph_populates_imports():
    class FakeClient:
        def __init__(self):
            self.graph = None

        def load_codebase_graph(self, graph, worktree_name):
            self.graph = graph
            return {}

    with tempfile.TemporaryDirectory() as d:
        root = _write_codebase(Path(d))
        fake = FakeClient()
        ci.ingest_codebase_graph(fake, root, worktree_name="wt_code")
    # app.py imports math_utils — the graph built for the KB carries that edge.
    app = fake.graph.modules["app.py"]
    assert "math_utils.py" in app.imports_from
