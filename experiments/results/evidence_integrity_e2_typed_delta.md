# e2 — Typed CodeSnapshot + CodeDelta (cap_evidence_integrity)

Date: 2026-08-25 · Branch: feature/cap-evidence-integrity

## The implementation (design §5.3)

1. **Typed primitives in `core/language.py`** (tier 0 — consumed by both measurement and
   knowledge without a cycle):
   - `SourceSpan` — 1-based `(start_line, start_col, end_line, end_col)`.
   - `CodeSymbol` — `name`, `kind`, `qualified_name` (methods → `ClassName.method_name`),
     `file_path`, `module_name`, `source_span`, `content_hash` (sha256 of node bytes for
     deterministic change detection), `calls` (best-effort called names).
   - `CodeSnapshot` — per-revision typed surface: `files -> symbols`, per-file `imports` and
     `file_hashes`, `unparsed_files` + `parse_coverage()` (the `ast_parse_coverage` fact's
     source; `None` when no source files — no denominator).
   - `CodeDelta(before, after)` — `added/removed/changed` symbols (keyed by
     `(file, qualified_name, kind)`; rename = new entity, no implicit matching), added/removed
     files, changed files, import diffs, and call-edge diffs.
   - `build_code_snapshot(files, revision, profile)` — pure tree-sitter; parse failures are a
     recorded `unparsed_files` fact, never a crash.
   - `compute_code_delta(before, after)`.
   - **Two-ID contract**: `module_entity_id` / `module_version_id` and `symbol_entity_id` /
     `symbol_version_id` — `entity_id = f(repository_id, path, qualified_name, kind)`,
     `version_id = f(entity_id, commit, content_hash)`.
2. **`_CodeSymbol` extended** (`knowledge/code_ingestion.py`): gains `qualified_name` +
   `source_span`, populated during extraction with enclosing-class tracking.
3. **`commit_analysis.compute_ast_diff`** — the regex diff-stat heuristic is REPLACED by the
   typed snapshot/delta: both revisions are materialized from git (`git ls-tree` + `git show`,
   no temp worktrees) via `_read_commit_files`, snapshots built, `compute_code_delta` diffed.
   Public API unchanged; `CommitAnalysis` gains `parse_coverage` (recorded fact) + `code_delta`
   (typed summary) in `to_dict()`.

## The tests

- `tests/test_code_delta.py` (new, 11 tests): snapshot qualified names/spans, imports +
  file hashes, parse-coverage facts (unparseable file, no-source None), delta added/removed/
  changed symbols, import + call-edge diffs, rename-is-new-entity, two-ID stability/version
  semantics, `compute_ast_diff` typed-delta integration, tree-sitter failure degrades to a
  parse-coverage fact, `_read_commit_files` materialization.
- `tests/test_data_integrity.py::test_go_rust_patterns_in_ast_diff` — updated guard: the
  P0-10 Go/Rust coverage guarantee now comes from the tree-sitter profile node types
  (`go.function_declaration`, `rust.function_item`); asserts the regex heuristic is gone.

Full suite: 2013 passed. The 5 `test_lab_*` / `test_publication_singular_door` failures are
**pre-existing** (identical on the parent checkout without these changes — published-artifact
staleness vs the registry, unrelated to e2).

## Verdict

**PASS** — known change → expected delta with qualified names + spans; CommitAnalysis callers
still pass; tree-sitter failures degrade to a recorded parse-coverage fact, never a crash.
