---
status: implemented
implemented_by: feature/measurement-bug-fixes
---
# Measurement bug fixes — implementation trace

Traces the three measurement-apparatus fixes from `docs/review/bugs.md` (BUG-3, BUG-5, BUG-6) to
their code changes and test coverage. Each finding re-reads the delivered source and test files at
commit `1b28f2cc5`, not the prior phases' prompts.

---

## 1. Fix-by-fix trace

| Bug | Severity | Source location | Fix location | Test | Result |
|---|---|---|---|---|---|
| BUG-3 | MEDIUM | `scripts/run.py:59-63`, `:374-376` | `scripts/run.py:32-40`, `:75`, `:134`, `:384-387` | `tests/test_pipeline.py:730-752` | **PASS** |
| BUG-5 | LOW | `src/instrument/perturb.py:337-345` | `src/instrument/perturb.py:337-349` | `tests/test_perturb.py:83-104` | **PASS** |
| BUG-6 | LOW | `src/instrument/recovery.py:86-87` | `src/instrument/recovery.py:86-87` | `tests/test_recovery.py:9-13, 72-84` | **PASS** |

---

## 2. BUG-3 — `run.py` model label

**Finding (`bugs.md`):** `run.py` persisted the short config label (`model: deepseek`) instead of
the `provider/model` id that actually executed, and the two invocation paths derived the label
differently — `--model deepseek/deepseek-v4-pro` → `"deepseek-v4-pro"` while the config path →
`"deepseek"`. Same model, two identities, wrong KB lineage.

**Fix:**

1. `scripts/run.py:32-40` — extracted a pure `_model_label(model_id)` helper
   (`model_id.split("/")[-1].replace(" ", "_").lower()`), so the display slug is a deterministic
   function of the canonical id on **both** code paths.

   ```python
   def _model_label(model_id: str) -> str:
       """Derive the deterministic display slug from a canonical ``provider/model`` id.

       Pure function of ``model_id`` (``model_id.split("/")[-1]``, lowercased and
       space-normalized), so the same physical model is labeled identically on every
       invocation path. Used only for display and result filenames — the persisted
       ``model`` field carries the canonical id (see ``_save_results``).
       """
       return model_id.split("/")[-1].replace(" ", "_").lower()
   ```

2. `scripts/run.py:75` — replaced the divergent `if model_override … else …` branch with
   `model_label = _model_label(model_id)`.

3. `scripts/run.py:384-387` — `_save_results` gained a trailing `model_id=None` parameter and now
   persists the canonical id: `"model": model_id or model_label`. The `model_label` slug remains
   only for the result filename (`model_slug`).

4. `scripts/run.py:134` — the call site now passes `model_id` through:
   `_save_results(all_runs, name, model_label, results_dir, model_id)`.

**Design note:** the helper is a free function rather than an inline expression so the
label-derivation contract is testable in isolation (see below) without invoking `run_experiment`'s
full backend. The `model_id or model_label` fallback keeps the existing callers that pass only a
display label (the registry-emission tests) working unchanged.

**Tests** (`tests/test_pipeline.py:730-752`, `TestRunModelLabelCanonicality`):

- `test_model_label_is_pure_function_of_model_id` — locks the slug formula for four models.
- `test_save_results_persists_canonical_model_id` — writes via `_save_results(..., model_id=…)`
  and asserts the persisted JSON `model` field is the canonical `provider/model`, not the slug.

---

## 3. BUG-5 — `_insert_contradiction` first-domain-wins

**Finding (`bugs.md`):** the inner `break` exited only the `for a, b in pairs` loop; the outer
`for domain, pairs` continued, so `all_domains` was overwritten by every later matching domain. A
prompt matching both `api` and `database` got `database`'s pairs despite `api` matching first.

**Fix** (`src/instrument/perturb.py:337-349`) — added a second `break` on the outer loop, guarded
by the now-set `all_domains`:

```python
all_domains = []
for domain, pairs in domain_contradictions.items():
    for a, b in pairs:
        keywords = [w for w in a.lower().split()[:5] if w not in _stopwords]
        if keywords and any(kw.lower() in prompt.lower() for kw in keywords):
            all_domains = pairs
            break
    # First matching domain wins: exit the outer loop too, so a later domain
    # (e.g. "database") cannot overwrite an earlier one (e.g. "api").
    if all_domains:
        break
if not all_domains:
    all_domains = domain_contradictions["general"]
```

**Design note:** a flag-plus-`break` (rather than an `else: continue` / `return` restructure) is
the minimal change that preserves the surrounding `if not all_domains` fallback to `general`
untouched. `all_domains` doubles as the "matched" sentinel, so no new variable is introduced.

**Test** (`tests/test_perturb.py:83-104`, `test_insert_contradiction_first_matching_domain_wins`):

- Feeds `"Build an API backed by a PostgreSQL database. Use REST endpoints."` — matches both `api`
  and `database`.
- Asserts the injected contradiction contains an `api` signature (`stateless`/`GraphQL`/`versioned
  via URL prefix`/`per-IP`/`XML`) and **no** `database` signature (`3NF`/`denormalized`/`MongoDB`/
  `eventual consistency`).

---

## 4. BUG-6 — redundant `tool_call_sequence()` call

**Finding (`bugs.md`):** `baseline_tools_set = set(baseline.tool_call_sequence())` was immediately
followed by a discarded `baseline.tool_call_sequence()` — the baseline tool sequence was
materialized twice.

**Fix** (`src/instrument/recovery.py:86-87`) — deleted the redundant second call:

```python
markers = recovery_markers or _default_recovery_markers()
baseline_tools_set = set(baseline.tool_call_sequence())
perturbed_tool_seq = perturbed.tool_call_sequence()
```

**Design note:** the deleted line had no side effect today (a pure list comprehension), but the
test below encodes the invariant that `classify_trajectory_segments` materializes the baseline
tool sequence exactly once, so a future non-idempotent `tool_call_sequence()` cannot silently
reintroduce the double pass.

**Tests** (`tests/test_recovery.py:9-13, 72-84`):

- `_CountingTrajectory` — a `ReasoningTrajectory` subclass that increments a counter in
  `tool_call_sequence()`.
- `test_baseline_tool_sequence_materialized_once` — runs `classify_trajectory_segments` with a
  `_CountingTrajectory` baseline and asserts `tool_call_sequence_calls == 1`.

---

## 5. Test results

| Command | Result |
|---|---|
| `python3 -m pytest tests/test_pipeline.py tests/test_perturb.py tests/test_recovery.py -q` | **117 passed** |
| `python3 -m pytest tests/ -m "not external" -q` | **1030 passed, 101 deselected, 19 warnings** |

No regressions: the full non-external suite is green, and no test was weakened to accommodate the
fixes (each new test asserts the post-fix invariant directly, and the `_save_results` signature
change is a backward-compatible trailing default).

## 6. Verdict

**PASS** — all three findings traced to their source edits and covered by dedicated regression
tests. Working tree is clean at `1b28f2cc5`; the fixes are committed and the full gate is green.
