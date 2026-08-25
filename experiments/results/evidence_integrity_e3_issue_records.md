# e3 — Issue-level records for Sonar AND Pyright (cap_evidence_integrity)

Date: 2026-08-25 · Branch: feature/cap-evidence-integrity

## The implementation (design §5.4)

1. **Sonar issue-level records** (`sonar.py` + `quality_ingestion.py`):
   - `SonarIssue` dataclass + `fetch_sonar_issues(project_key, ...)` (paged
     `/api/issues/search`; returns `[]` on failure — absent issues stay absent).
   - `derive_quality_records` emits ONE `source_type=report` record per Sonar issue
     (file/line/rule/severity/message/remediation_effort as a typed JSON payload in `text`;
     `ISSUE_EXTRACTOR_VERSION = "quality-issues/v1"`). The 93-issue collapse to one sentence is
     retired for the issue surface.
2. **Pyright diagnostic-level records**: ONE record per `LSPDiagnostic`
   (file/line/column/rule/severity/message, typed JSON payload). Pyright is pinned in
   `pyproject.toml [lsp]` (`pyright==1.1.390`).
3. **Durable availability probe**: when a real tool (e.g. pyright) is selected but cannot run,
   the LSP status record is emitted with `lsp_analysis_status: unavailable` and **zero
   dependent counts** (counts OMITTED, never None-as-zero). `_lsp_text` is now a typed JSON
   payload carrying the measured enum.
4. **Symbol linking**: each issue/diagnostic is linked to the SMALLEST CONTAINING SYMBOL via
   `core.language.smallest_containing_symbol` (method over class over module; `None` → no link,
   never invented). File paths are normalized to the repo-relative snapshot keys.
5. **TESTED_BY rule** (`core.language`): `TESTED_BY_RULE` provenance + deterministic
   `module_path_from_test_file` (language-aware: `test_<m>.py`, `<m>.test.ts`, `<m>_test.go`,
   `<m>_test.rs`) + `tested_symbols(snapshot)`. Non-derivable matches are NOT claimed tested —
   `changed_symbols_with_tests_ratio` is DEFERRED (fact omitted), never invented.

## The tests

- `tests/test_quality_ingestion.py`: +3 — per-Sonar-issue records with smallest-symbol links
  (line 3→`add`, line 11→`Calculator.multiply`), per-LSP-diagnostic records with links, absent
  issues stay absent (no empty-file fabrication). Updated: LSP typed payload; unavailable
  pyright → durable probe with zero dependent counts.
- `tests/test_code_delta.py`: +3 — `smallest_containing_symbol` (method over class), TESTED_BY
  rule language-aware matching + `tested_symbols`.
- `tests/test_sonar.py` unchanged (sonar revision identity from e1).

Full suite: **1923 passed** (excluding pre-existing environmental hangs — Chroma, Ollama — and
the pre-existing lab-output failures on the parent checkout).

## Live probes

```
probe A — framework run_diagnostics(pyright fixture):
  available=False tool='pyright' total=0
  => durable lsp_analysis_status: unavailable probe with zero dependent counts (the honest
     production state: pyright's bundled node cannot load libatomic.so.1 here).

probe B — fetch_sonar_issues('exp_src_4eb563816f00'): 133 issues
  CRITICAL python:S3776  agentic_dynamics/adapters/claude_adapter.py:243 effort=19min ...
  MAJOR    python:S107   agentic_dynamics/adapters/claude_adapter.py:244 effort=20min ...
  CRITICAL python:S3776  agentic_dynamics/adapters/opencode.py:219 effort=24min ...
  => one-record-per-issue surface works against the live server.

probe C — pinned pyright fixture proof (LD_LIBRARY_PATH provides libatomic for node):
  pyright 1.1.390 --outputjson broken_math.py -> summary errors=2:
  reportReturnType            error  line 8
  reportAttributeAccessIssue  error  line 13
  => the pinned version parses the fixture into real per-diagnostic records.
```

## Verdict

**PASS** — a fixture with N diagnostics + M Sonar issues produces N+M records with symbol
links (hermetic tests + live issue fetch); the pyright pin is installed and proven on a fixture
AND the unavailable-safe scope is recorded durably (both EITHER branches satisfied); TESTED_BY
rule defined, recorded, and non-derivable matches are deferred, never invented.
