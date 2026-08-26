---
status: accepted
---

# cap_2a_rerun2 — measurement design (p0_research deliverable)

**Status: accepted** · Authority this document executes: `cap_2a_rerun2_design.md` §4 (p0_research).
· Produced by the p0_research phase — every server/API claim below is backed by a recorded probe
(§1). No implementation lives in this document; it pins the semantics and transport that p1
implements.

---

## 1. Probe log (R1–R4) — recorded endpoints and response shapes

Every probe ran against the local server with the scanner env credentials
(`sonar.py`: `SONAR_URL_DEFAULT=http://localhost:9000`, user `admin`, password `admin`), on
2026-08-26, server `10.7.0.96327`.

### R1 — SonarQube server. **PASS** (option A feasible).

| # | Probe | Result |
|---|---|---|
| 1.1 | `GET /api/system/status` (Basic `admin:admin`) | `{"id":"147B411E-AZ_rvmwPYHQ6CjZE5zJU","version":"10.7.0.96327","status":"UP"}` |
| 1.2 | `GET /api/authentication/validate` | `{"valid":true}` — the `admin:admin` scanner credentials authenticate |
| 1.3 | `GET /api/server/version` | `10.7.0.96327` |
| 1.4 | `GET /api/projects/search?ps=20` | `paging.total=1051` components — the rerun's fetch-first cache (1051 prior analyses) is present on-disk in the server |
| 1.5 | `GET /api/issues/search?componentKeys=exp_cap2a_cell_p3b_e136ce25dbfa&ps=50` | `total=1`, one issue: `severity=MAJOR, rule=python:S1244, component=exp_cap2a_cell_p3b_e136ce25dbfa:test_calc.py, line=18` |
| 1.6 | same + `&severities=BLOCKER,CRITICAL` | `total=0` — **server-side severity filter works** |
| 1.7 | same + `&sinceLeakPeriod=true` | `total=1` (the S1244 MAJOR) — param accepted, but see R1.9: it is **not** a per-revision "introduced by this change" filter here |
| 1.8 | `GET /api/issues/search?severities=BLOCKER,CRITICAL&ps=3` (global) | `total=2700`; issues carry `key, rule, severity, component, project, line, textRange, message, flows` — the first issues are `python:S3776` CRITICAL and `python:S1192` CRITICAL |
| 1.9 | `GET /api/project_analyses/search?project=exp_cap2a_cell_p3b_e136ce25dbfa&ps=3` | one analysis; `events=[SQ_UPGRADE, VERSION]`, `projectVersion="not provided"`, **no `revision` field** — because `sonar.scm.disabled=true` (`sonar.py:278`) records no SCM revision |
| 1.10 | `GET /api/rules/show?key=python:S1244&actives=true` | `severity=MAJOR, type=BUG`, active in profile `e7d9fbf7…` (Sonar way, py) at `MAJOR` |
| 1.11 | `GET /api/rules/show?key=python:S3776&actives=true` | `severity=CRITICAL, type=CODE_SMELL`, active at `CRITICAL`, param `threshold=15` |
| 1.12 | `GET /api/rules/show?key=python:S1192&actives=true` | `severity=CRITICAL, type=CODE_SMELL`, active at `CRITICAL`, param `threshold=3` |
| 1.13 | `GET /api/rules/show?key=python:S1523&actives=true` | `severity=CRITICAL, type=SECURITY_HOTSPOT`, **`actives=[]`** — `eval` is NOT active in the default Python profile |
| 1.14 | `GET /api/issues/search?rules=python:S1523&ps=5` | `total=0` — SECURITY_HOTSPOT findings are **not** returned by `api/issues/search` |
| 1.15 | `GET /api/hotspots/search?project=exp_src_96301d90ca39&ps=3` | `paging.total=14` hotspots (e.g. `python:S2068` auth, `python:S5852` dos) — security hotspots live in a **separate** API |
| 1.16 | `GET /api/rules/search?languages=py&types=VULNERABILITY&ps=100` | `total=None` — no Python VULNERABILITY rules surfaced by the search endpoint; `python:S4426` (crypto key gen) and `python:S5542` (encryption mode) exist as CRITICAL VULNERABILITY via `rules/show`, but require crypto libraries to trigger |

**R1 conclusions (each backed by the probe above):**

* `api/issues/search` **exists** and returns per-issue records with `rule`, `severity`,
  `component`, `line` (probes 1.5, 1.8). It pages (`ps` ≤ 500).
* `severities=BLOCKER,CRITICAL` **is a server-side filter** (probe 1.6 vs 1.5).
* The existing analyses carry **issue records**, not measures only (probes 1.5, 1.8) — the rerun's
  fetch-first used `api/measures/component` (measures only), but the issue surface is independently
  queryable.
* The server can report issues **per analysis revision** via revision-scoped project keys
  (`exp_<name>_<rev[:12]>`), but the rerun analyzed only the *after* (phase-commit) revision; the
  *before* (parent) project does not exist (see R2) — so before/after novelty needs a fresh parent
  scan.
* `sinceLeakPeriod=true` is **rejected** as the novelty mechanism: with `sonar.scm.disabled=true`
  the server records no SCM revision (probe 1.9), so the leak period is not pinned to a git
  revision — it cannot mean "introduced by *this change*".
* **Measured instrument property (must not be papered over):** on this server's default "Sonar way"
  Python profile, the BLOCKER/CRITICAL issue surface reachable through `api/issues/search` is
  **CODE_SMELL-only** — `python:S3776` (cognitive complexity, CRITICAL, threshold 15) and
  `python:S1192` (duplicated string literals, CRITICAL, threshold 3). Release-blocking *defect*
  rules (`eval`→`python:S1523`, hard-coded credentials→`python:S2068`) are SECURITY_HOTSPOTs that
  are either inactive (`S1523`, probe 1.13) or surfaced only by `api/hotspots/search` (probe 1.15),
  not by `api/issues/search`. The design doc's §RC5 example "unguarded `eval`" therefore does **not**
  mint an issue through the option-A transport; the critical-cell stimulus is pinned to the
  reachable CRITICAL issue instead (§4).

### R2 — scanner. **PASS** (fresh analyses producible).

| # | Probe | Result |
|---|---|---|
| 2.1 | `which sonar-scanner` | not on PATH |
| 2.2 | `ls /tmp/sonar-scanner-6.2.1.4610-linux-x64/` | `bin/ conf/ jre/ lib/` — scanner present at `/tmp/sonar-scanner-6.2.1.4610-linux-x64/bin/sonar-scanner` |
| 2.3 | `/tmp/sonar-scanner-6.2.1.4610-linux-x64/bin/sonar-scanner -v` | `SonarScanner CLI 6.2.1.4610`, `Java 17.0.12 Eclipse Adoptium (64-bit)`, `Linux 5.15.0-186-generic amd64` |
| 2.4 | `which java` | not on PATH — but `_find_java` (`sonar.py:69`) locates the bundled JRE at `<scanner>/jre/bin/java` (present, probe 2.2) |

**R2 conclusions:** a fresh analysis **can** be produced: scanner CLI 6.2.1.4610 + bundled JRE 17
are present and execute, the server is UP and authenticates, and the rerun's own ledgers record the
scanner at this path producing analyses in ~24 s (`cap_2a_rerun/p2_phase_ledger.json`
`analyzer_reachability.sonar.scanner`). Rerun2 cells can therefore get fresh **per-revision**
analyses (parent + phase commit), which is exactly what the before/after novelty rule requires.

### R3 — LSP tool. **PASS** (mypy pinned).

| # | Probe | Result |
|---|---|---|
| 3.1 | `which pyright` | not installed (the rerun's `lsp_status=unavailable` root cause is unchanged) |
| 3.2 | `python3 -m mypy --version` | `No module named mypy` — not pre-installed |
| 3.3 | `python3 -m pip install --dry-run mypy` | resolves to `mypy 2.3.1` (+ `mypy_extensions`, `pathspec`, `librt`, `ast-serialize` prebuilt wheels) — pip-installable |
| 3.4 | `python3 -m pip install --target /tmp/opencode/mypy_probe_target mypy` | `Successfully installed … mypy-2.3.1` |
| 3.5 | `python3 -m mypy --version` | `mypy 2.3.1 (compiled: yes)` |
| 3.6 | `python3 -m mypy --no-error-summary --show-error-codes smoke.py` | output `…/smoke.py:2: error: Incompatible return value type …` — **no column number** in default output |
| 3.7 | `python3 -m mypy --show-column-numbers --no-error-summary --show-error-codes smoke.py` | `…/smoke.py:2:12: error: Incompatible return value type (got "int", expected "str")  [return-value]` |

**R3 conclusions — the LSP tool pin (deliverable 3):**

* **Tool: mypy**, run as `python3 -m mypy` (module invocation; no PATH entry needed). mypy 2.3.1 is
  pure-python + prebuilt wheels and is pip-installable (probes 3.3–3.5). pyright remains broken
  here (probe 3.1) — confirmed, not assumed.
* **The exact invocation must include `--show-column-numbers`.** mypy 2.3.1's default output omits
  the column (`file:line: error:` — probe 3.6), which `lsp_diagnostics._parse_mypy`
  (`lsp_diagnostics.py:234`) mis-parses: its `line.split(":", 3)` puts the severity word into the
  column slot, so `severity` falls back to `"warning"` and every error is misclassified as a
  warning. With `--show-column-numbers` (probe 3.7) the output is `file:line:col: error: message
  [code]`, which `_parse_mypy` parses correctly (`severity="error"`, `code="return-value"`). This is
  a **measured** finding, not a guess: p1 must change the `python_mypy` `diag_cmd`
  (`lsp_diagnostics.py:96`) from `["mypy","--no-error-summary","--show-error-codes","{path}"]` to
  `["mypy","--show-column-numbers","--no-error-summary","--show-error-codes","{path}"]`.

### R4 — pinned semantics (read; no code change). **PASS** (all artifacts located).

* `code_change_facts.py` — `RISK_WEIGHTS = (("new_sonar_critical",0.35),("new_lsp_error",0.25),
  ("tests_ratio",0.20),("impacted",0.20))`; `VERSION="code_change_facts/v1"`; risk is
  `sum(w·term)/sum(w)` over measurable terms, renormalized. The `sonar_analysis` evidence shape is
  `{"status","revision_matches"|None,"new_critical_count"|None,"analyzed_sha"}`; `lsp_analysis` is
  `{"status","new_error_count"|None,"tool"}` (`code_change_facts.py:12-14`).
* `verify_proposal.py` — the **treatment, code-unchanged this campaign**: `VERIFY_RISK_THRESHOLD=0.2`
  (`:61`), `_risk_depth` 0.15/0.3 → depth 1/2/3 (`:143`), `build_verify_proposal` action rule
  (`:169`): `new_sonar_critical_count>0 ∨ new_lsp_error_count>0 → rework/depth3`, else
  `changed==0 → continue`, else `risk≥0.2 → verify/depth(_risk_depth)`, else `continue`.
* `sonar.py` — `compute_sonar_diff` (`:162`) diffs **counts only** (`bugs`, `vulnerabilities`,
  `code_smells`, ratings) — it is the model for the before/after idea but carries no per-issue
  identity, so v2 must diff **issue sets** (`fetch_sonar_issues`, `sonar.py:505`, already returns
  per-issue `(key,rule,severity,file_path,line)` and is the surface v2 extends with a `severities`
  param).
* Rerun p4 rows (from `feature/cap-2a-rerun` commit `fae8ef2d2`, file
  `experiments/results/cap_2a_rerun_score_20260826T001107Z.json`, SHA256 `59bd15d8…`):

  | cell | risk | action/depth | new_sonar_critical | new_lsp_error | realized | hit |
  |---|---|---|---|---|---|---|
  | `cap2a_p2_bespoke` | 0.24 | verify/2 | 0 | omitted (unavailable) | no_rework | 0 |
  | `cap2a_p3a` | 0.24 | verify/2 | 0 | omitted | no_rework | 0 |
  | `cap2a_p3b` | 0.3311 | rework/3 | 1 (python:S1244 MAJOR — probe 1.5) | omitted | no_rework | 0 |

  `risk_calibration`: `[0.15,0.30)→no_rework×2`, `[0.30,0.60)→no_rework×1`; `risk_mint_rate=1.0`;
  `hit_rate=0/3` (Wilson `[0, 0.5615]`). The p3b `new_sonar_critical_count=1` was `python:S1244`
  (MAJOR) — under the v2 severity filter that same tree mints `0` (probe 1.6). These three rows are
  the calibration table's first three entries (they carry over into p4's table, §5).

---

## 2. Deliverable 1 — chosen transport: **Option A (server-native), before/after identity diff**

**Decision: option A.** Server-native `api/issues/search` supplies the per-issue surface and the
severity filter; novelty is computed as a before/after **set difference by issue identity** across
the two revision-scoped project keys. `sinceLeakPeriod` is **rejected** (probe 1.9: scm disabled →
un-pinned leak period). Option B (client diff over `SonarMetrics`) is **not chosen** because it
diffs counts, not issue sets, and would reimplement the severity filter the server already does
natively.

### Exact calls and signatures

The seam already materializes the before/after trees and knows both revisions
(`workflow_runner._run_change_analysis`, current tree `:265`; the rerun branch's p1 added the
sonar/lsp legs at `:384-430`). v2 replaces the rerun's count-based `_sonar_evidence` with a
before/after issue-set leg:

```
# 1. Fresh per-revision analyses (R2-confirmed feasible, ~24s each, under ANALYZER_LEG_TIMEOUT_SECONDS=360):
run_sonar_analysis(str(materialized_parent_tree), revision=parent_full_sha)   # -> project key exp_<name>_<parent[:12]>
run_sonar_analysis(str(wd),                       revision=full_sha)          # -> project key exp_<name>_<rev[:12]>
#   The parent tree must be materialized ON DISK (the in-memory before_files from
#   _read_commit_files are insufficient for the scanner). Both analyses use sonar.scm.disabled=true.

# 2. Per-issue records, severity-filtered server-side (extend fetch_sonar_issues with a severities param):
sonar.fetch_sonar_issues(project_key_parent, severities="BLOCKER,CRITICAL", ps=500)  # -> list[SonarIssue]
sonar.fetch_sonar_issues(project_key_after,  severities="BLOCKER,CRITICAL", ps=500)
#   underlying call: GET /api/issues/search?componentKeys=<project_key>&severities=BLOCKER,CRITICAL&ps=500&p=<page>

# 3. Identity rule + set difference:
issue_identity(i) = (i.rule, i.file_path, i.line)      # file_path = component.split(":", 1)[1] (repo-relative)
new_sonar_critical_count = len({issue_identity(i) for i in after} - {issue_identity(i) for i in before})
```

### Output shape of `api/issues/search` (probe 1.8), per issue

```
{ "key": "dbc56d6e-3534-4748-bd14-484764e4a736", "rule": "python:S3776", "severity": "CRITICAL",
  "component": "exp_src_96301d90ca39:agentic_dynamics/adapters/claude_adapter.py", "project": "…",
  "line": 243, "textRange": {"startLine":243,"endLine":243,"startOffset":4,"endOffset":22},
  "message": "…", "hash": "…", "flows": [ … ] }
```
`paging: {pageIndex, pageSize, total}`. `SonarIssue` (`sonar.py:480`) already carries
`key, rule, severity, message, file_path, line, effort, status`; v2 needs only `rule`, `file_path`
(stripped of the `project_key:` prefix), `line`.

### The evidence payload shape is unchanged

The reducer's `sonar_analysis` payload stays `{"status","revision_matches"|None,
"new_critical_count"|None,"analyzed_sha"}`; only the *producer* of `new_critical_count` changes to
the v2 rule. `status` is `available` iff **both** analyses are confirmed to cover their revisions
(the revision-scoped key contract, `sonar.py:_revision_confirmed`); otherwise `unavailable`/
`stale-refused` and `new_critical_count=None` (null-not-zero).

---

## 3. Deliverable 2 — reducer v2: term definitions, weight table, version bump

### Term definitions (verbatim — `code_change_facts/v2`)

```
new_sonar_critical_count :=
  |{ i : i ∈ issues(after) ∧ i ∉ issues(before) ∧ i.severity ∈ {BLOCKER, CRITICAL} }|

  issues(R)   = the per-issue records for the revision-scoped project key of revision R,
                fetched via GET /api/issues/search?componentKeys=<key>&severities=BLOCKER,CRITICAL
  identity(i) = (rule, file_path, line); file_path is repo-relative (component minus the key prefix)
  "new"       = present in issues(after) and absent from issues(before) under that identity
  severity filter = BLOCKER + CRITICAL only, across all rule types reachable via api/issues/search;
                    a MAJOR finding (including bug-type rules like python:S1244) NEVER counts.
                    [P] provenance: cap_2a_rerun2_design.md §2 RC1.
```

```
new_lsp_error_count :=
  |{ d : d ∈ diags(after) ∧ d ∉ diags(before) ∧ d.severity == "error" }|

  diags(R)     = mypy diagnostics at revision R via run_diagnostics(materialize(R), profile,
                 tool_name="python_mypy") — see §4 of this doc for the pinned invocation
  identity(d)  = (file, line, code); severity "error" only (warnings excluded)
```

All other term definitions (the eight remaining `CODE_CHANGE_PREDICATES` and the
`code_change_risk` renormalization over measurable terms) are **unchanged** from
`code_change_facts.py` — they are not re-specified here; the semantics change is confined to the
two analyzer-count terms above.

### `[P]` weight table — **UNCHANGED** (no §RC6 fallback triggered)

Option A is feasible (R1+R2 PASS), so the weights are not renormalized. Recorded verbatim as the
`[P]` provenance:

```
RISK_WEIGHTS = (("new_sonar_critical", 0.35), ("new_lsp_error", 0.25),
                ("tests_ratio", 0.20),            ("impacted", 0.20))
```

### Version bump

`code_change_facts/v1 → code_change_facts/v2`:
* `code_change_facts.py`: `VERSION = "code_change_facts/v2"`; `CODE_CHANGE_FACTS_V1` →
  `CODE_CHANGE_FACTS_V2`; `code_change_facts_v1` → `code_change_facts_v2`; the module + reducer
  docstrings restate the v2 term semantics above (with this doc as provenance). The risk formula
  and renormalization logic are byte-identical to v1 — only the *meaning* of the two analyzer
  inputs changed, which is exactly why the version must bump (a v1 fact and a v2 fact with the
  same predicate name are not interchangeable).
* `verify_proposal.py` is **untouched** (the treatment): `VERIFY_RISK_THRESHOLD=0.2`, `_risk_depth`
  0.15/0.3, `build_verify_proposal` stay code-unchanged.

---

## 4. Deliverable 3 — LSP tool pin and diagnostics delta rule

**Pin:** `mypy` (2.3.1), invoked as `python3 -m mypy --show-column-numbers --no-error-summary
--show-error-codes <codebase_path>`, selected via `run_diagnostics(codebase_path, profile,
tool_name="python_mypy")`. The `--show-column-numbers` flag is **required** (probe 3.6/3.7) — it is
the difference between `_parse_mypy` correctly classifying errors vs misclassifying every error as
a warning. p1 makes one edit to `lsp_diagnostics.py:96` (add `--show-column-numbers` to the
`python_mypy` `diag_cmd`); no change to `_parse_mypy` is needed.

**Diagnostics delta rule (verbatim):**

```
new_lsp_error_count = |{ (file, line, code) : (file,line,code) ∈ ids(after) ∧ (file,line,code) ∉ ids(before) }|
  over error-severity mypy diagnostics only; ids(R) = the set of (file, line, code) triples from
  run_diagnostics at revision R. warnings/info/hints never count. When the tool cannot run on a
  revision, its diagnostics are unavailable and the term is OMITTED (null-not-zero).
```

The before revision is materialized the same way the sonar leg materializes it (the parent tree on
disk), so `(file, line, code)` identities are comparable across the two revisions.

---

## 5. Deliverable 4 — the three cell-variant prompts (exact stimulus per design §RC5)

All three variants share the rerun's skeleton: `workflow.kind=agent_task`, seeded calc app
(`calc.py` = `add`/`subtract`, `test_calc.py` = `test_add`/`test_subtract`), `language: python`,
`fork: true`, phases `implement (agent) → test (kind:test) → verify (agent)`. Only the `implement`
prompt differs. The expected realized class is the *prediction* the cell is scored against — if a
variant realizes differently, that is DATA (recorded), not a rerun.

### 5.1 `cap_2a_cell_clean.yaml` — expected realized `no_rework`, `new_sonar_critical_count=0`

```
Implement a small pure helper function in the seeded calc app.

GOAL: {goal}

READ FIRST:
- calc.py        (the existing add / subtract functions)
- test_calc.py   (the existing test_add / test_subtract)

DO:
- Add a `product(values)` function to calc.py that returns the product of a non-empty list of
  numbers, raising ValueError("empty values") on an empty list.
- Add a `test_product` function to test_calc.py that asserts product([1, 2, 3, 4]) == 24 and that
  product([]) raises ValueError.
- Do not change add / subtract or their tests.

VERIFY: `python -m pytest test_calc.py -q` passes.

DELIVER the changed calc.py and test_calc.py.
```

Rationale (recorded): a small single-purpose function with a single guard — no float `==`, no
dynamic execution, cognitive complexity ~1 (≪ S3776's 15) — mints **zero** issues, hence
`new_sonar_critical_count=0`.

### 5.2 `cap_2a_cell_critical.yaml` — expected realized `targeted_rework`, `new_sonar_critical_count ≥ 1`

```
Implement a classifier function with a deep nested decision tree, containing one real defect.

GOAL: {goal}

READ FIRST:
- calc.py        (the existing add / subtract functions)
- test_calc.py   (the existing test_add / test_subtract)

DO:
- Add a `classify(value)` function to calc.py that maps a numeric value to a label through a
  nested conditional structure with at least 20 branches across 4 or more nesting levels
  (a long if/elif/else chain over disjoint ranges, plus nested sub-branches). This makes the
  function's cognitive complexity exceed SonarQube's CRITICAL threshold of 15.
- Introduce ONE real defect in the range [10, 20): use `>` in place of `>=` at that boundary so
  that the value 10.0 is misclassified relative to the documented "value in [10, 20)" contract.
- Add a `test_classify` function to test_calc.py that asserts the documented contract for the
  boundary values, including classify(10.0) mapping to the [10, 20) label.
- Do not change add / subtract or their tests.

VERIFY: `python -m pytest test_calc.py -q` reports the boundary assertion result exactly as it is
(do not weaken the test to make it pass).

DELIVER the changed calc.py and test_calc.py.
```

Rationale (recorded, probe-backed): the design doc's §RC5 `eval` example is a SECURITY_HOTSPOT
(`python:S1523`) that is inactive in the default profile (probe 1.13) and not returned by
`api/issues/search` (probe 1.14); the reachable BLOCKER/CRITICAL issue in that surface is
`python:S3776` (cognitive complexity, CRITICAL, threshold 15 — probes 1.11, 1.8). So the critical
stimulus mints the sonar signal via **S3776** and realizes `targeted_rework` via the **inverted
boundary comparison** (a real defect the independent test_runner + post-hoc evaluator confirm).

### 5.3 `cap_2a_cell_style.yaml` — expected realized `no_rework` (or `verification_only`), `new_sonar_critical_count=0`

```
Implement a small function in the seeded calc app that compares floating-point values directly.

GOAL: {goal}

READ FIRST:
- calc.py        (the existing add / subtract functions)
- test_calc.py   (the existing test_add / test_subtract)

DO:
- Add a `rate_for(score)` function to calc.py that returns a rate by comparing `score` to the
  thresholds 1.0, 2.0, and 3.0 with direct `==` equality checks (e.g. `if score == 1.0: return 0.1`),
  falling through to a default rate otherwise.
- Add a `test_rate_for` function to test_calc.py that asserts rate_for(1.0) == 0.1 and
  rate_for(0.0) == <default>, using values the direct comparison resolves deterministically.
- Do not change add / subtract or their tests.

VERIFY: `python -m pytest test_calc.py -q` passes.

DELIVER the changed calc.py and test_calc.py.
```

Rationale (recorded): the float `==` comparisons mint `python:S1244` (MAJOR, bug-type — probe 1.10,
the same finding that falsely drove the rerun's p3b `rework`). Under the v2 severity filter this
mints `new_sonar_critical_count=0` (probe 1.6) — the regression the whole campaign exists to prove.

---

## 6. Deliverable 5 — p4 calibration-table JSON schema

The score JSON stays `cap_2a_score/v1` and adds a `calibration` block. Field names (exact):

```
"calibration": {
  "schema_version": "cap_2a_calibration/v1",
  "per_cell_rows": [                       // one row per scored+ran cell (design §F2.1)
    {
      "cell_id":            "cap2a_cell_<variant>",
      "action":             "verify" | "rework" | "continue",
      "depth":              2,
      "scope_size":         4,
      "code_change_risk":   0.24,
      "new_sonar_critical_count": 0,       // int | null (null = analyzer unavailable)
      "new_lsp_error_count":       null,   // int | null
      "changed_symbols_with_tests_ratio": 0.5,   // float | null
      "impacted_symbol_count":  4,         // int | null
      "sonar_analysis_status": "available" | "unavailable" | "stale-refused",
      "lsp_analysis_status":   "available" | "unavailable",
      "realized_outcome": "no_rework" | "verification_only" | "targeted_rework" | "broad_rework" | "unknown",
      "realized_depth":    0,
      "hit":               false
    }
  ],
  "risk_buckets": [                        // design §F2.2 — risk→outcome
    {"bucket": "[0,0.15)", "no_rework": 0, "verification_only": 0, "targeted_rework": 0, "broad_rework": 0},
    {"bucket": "[0.15,0.3)", "no_rework": 0, "verification_only": 0, "targeted_rework": 0, "broad_rework": 0},
    {"bucket": "[0.3,inf)",  "no_rework": 0, "verification_only": 0, "targeted_rework": 0, "broad_rework": 0}
  ],
  "finding_outcome": [                     // design §F2.3 — finding→outcome
    {"new_sonar_critical_count": 0,  "no_rework": 0, "verification_only": 0, "targeted_rework": 0, "broad_rework": 0},
    {"new_sonar_critical_count": 1,  "no_rework": 0, "verification_only": 0, "targeted_rework": 0, "broad_rework": 0}
  ],
  "severity_strictness": [                 // design §F2.5 — the conflation fix is data, not prose
    {"cell_id": "cap2a_cell_critical", "blocker_critical_introduced": ["python:S3776:calc.py:12"],
     "major_excluded": []},
    {"cell_id": "cap2a_cell_style", "blocker_critical_introduced": [],
     "major_excluded": ["python:S1244:calc.py:7"]},
    {"cell_id": "cap2a_cell_clean", "blocker_critical_introduced": [], "major_excluded": []}
  ],
  "risk_mint_rate": 1.0
}
```

`risk_buckets` and `finding_outcome` seed from the rerun's three rows (§1 R4): the table does not
start from zero. `severity_strictness.blocker_critical_introduced` lists each change-introduced
BLOCKER/CRITICAL issue as `rule:file:line`; `major_excluded` lists each MAJOR (or lower) finding
that v1 would have counted and v2 does not.

---

## 7. Decisions and gate summary

| Deliverable | Decision | Basis |
|---|---|---|
| Transport | **Option A** (server-native `api/issues/search` + `severities=BLOCKER,CRITICAL` + before/after `(rule,file,line)` set diff); `sinceLeakPeriod` rejected | probes 1.5–1.9, 1.16; R2 fresh-scan feasibility |
| Reducer v2 | term defs §3; weights **unchanged**; `code_change_facts/v1 → /v2` | R4 read; R1/R2 feasibility (no §RC6) |
| LSP | **mypy** `python3 -m mypy --show-column-numbers --no-error-summary --show-error-codes <path>`, `tool_name="python_mypy"` | probes 3.1–3.7 |
| Cell variants | §5.1/5.2/5.3 prompts; critical stimulus pinned to `python:S3776` (CRITICAL) + inverted-boundary defect, NOT `eval` | probes 1.10–1.15 |
| Calibration schema | §6 | design §F2 + rerun score JSON fields |

**§RC6 fallback:** **NOT triggered.** Option A is feasible (R1+R2 PASS), so the sonar term is kept,
weights unchanged, no capability-gap renormalization.

**Recorded capability boundaries (measured, not invented):** (1) SECURITY_HOTSPOT rules (eval,
hard-coded credentials) are not reachable through `api/issues/search` (separate
`api/hotspots/search`; probes 1.14–1.15), so they are out of scope for v2's `new_sonar_critical_count`;
(2) the default Python profile's reachable BLOCKER/CRITICAL surface is CODE_SMELL-only (S3776/S1192),
which is *why* the critical stimulus is S3776-based. Both are properties of the instrument this
campaign measures with, and are recorded so p5/p6 can state the fitted mapping's reach honestly.

---

## 8. Provenance

* Authority: `docs/designs/current/cap_2a_rerun2_design.md` (accepted, §4 p0_research).
* Rerun data (R4): `feature/cap-2a-rerun` @ `fae8ef2d2` — `experiments/results/cap_2a_rerun_score_20260826T001107Z.json`
  (SHA256 `59bd15d8…`), `cap_2a_rerun/p2_phase_ledger.json`, `cap_2a_rerun/cap2a_p3{a,b}_phase_ledger.json`.
* Read surfaces: `src/agentic_dynamics/control/reducers/code_change_facts.py`,
  `src/agentic_dynamics/control/verify_proposal.py`, `src/agentic_dynamics/measurement/sonar.py`,
  `src/agentic_dynamics/measurement/lsp_diagnostics.py`,
  `src/agentic_dynamics/runtime/workflow_runner.py`, `src/agentic_dynamics/runtime/change_analyzer.py`,
  `src/agentic_dynamics/control/evidence_analyzer.py`.
