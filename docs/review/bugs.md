# Code review — concrete bugs

Phase 2 (bugs) of `repo_review_fable`. Each finding carries `file:line`, a one-line
description, a reproduction sketch, expected-vs-actual, and a suggested fix, severity-tagged
CRITICAL / HIGH / MEDIUM / LOW. Priority areas: the measurement apparatus, the KB ingestion path
(`record_to_artifact → record_to_event → stream → extract_record`), the workflow runner, and the
newly-merged consumer/projection layer (`kb_worker.py`, `generate_manifest.py`). All line numbers
re-read from source at commit `1baff2a6f`.

---

## BUG-1 — HIGH — `observed_at` (the real measurement timestamp) is silently dropped on the stream round-trip

- **Location:** `src/instrument/knowledge_ingestion.py:392` (`record_to_event` sets
  `occurred_at=_now_iso(now)`), `:248` (`record_to_artifact` blanks `observed_at`), and
  `:417-424` (`extract_record` reconstructs `observed_at=event.occurred_at`).
- **Description:** The producer goes to deliberate lengths to preserve a finding's *actual*
  observation timestamp (`_observed_at`, `:179-191`, probes `ended_at`/`observed_at`/`timestamp`/
  `run_at`/`finished_at`/`created_at`/`started_at` and falls back to producer-now "so we never
  fabricate a timestamp the summary does not actually carry"). But that value never survives the
  pointer contract: `record_to_artifact` blanks `observed_at` from the durable artifact, and
  `extract_record` reattaches `event.occurred_at` (the producer wall-clock) in its place.
- **Reproduction:**
  1. `rec = build_record({"worktree_name": "c1", "correctness": 1.0, "ended_at": "2026-08-01T00:00:00+00:00"}, repository_id="agentic-dynamics")` → `rec.observed_at == "2026-08-01T00:00:00+00:00"`.
  2. `ev = record_to_event(rec, now=datetime(2026,8,19,tzinfo=timezone.utc))` → `ev.occurred_at == "2026-08-19T…"`, and `ev.content_hash` covers bytes in which `observed_at` is `""`.
  3. `rec2 = extract_record(ev, record_to_artifact(rec))` → `rec2.observed_at == "2026-08-19T…"` (producer clock), **not** `"2026-08-01T00:00:00+00:00"`.
- **Expected vs actual:** expected `observed_at` to round-trip as the entry's own run timestamp
  (the whole point of `_observed_at`); actual — the entry timestamp is irrecoverably replaced by
  the producer's `occurred_at`. `valid_from` and `indexed_at` round-trip correctly; `observed_at`
  is the one field lost.
- **Impact:** wrong lineage/freshness. `observed_at` feeds `retrieval`'s freshness multiplier,
  `scripts/registry.py --since` filtering, and `generate_manifest._derive_lifecycle`'s `valid_to`
  computation — every downstream consumer sees "when the producer ran" instead of "when the cell
  was actually measured." Latent for the *current* `_results_summary.json` (no per-entry
  timestamp today, so `_observed_at` returns producer-now and the bug is invisible), but the code
  exists specifically to support stamped entries, and this silently defeats it the moment one
  appears.
- **Fix:** carry the entry timestamp through the pointer. Either (a) stop blanking `observed_at`
  in `record_to_artifact` (fold it into `content_hash`; it is already excluded from idempotence
  only because it is "volatile", but a real run timestamp is a stable fact), or (b) add an
  `observed_at` field to `KnowledgeEvent` and have `extract_record` prefer it over `occurred_at`.
  Option (a) is smaller and matches the "revision/commit" precedent already folded into the hash.

---

## BUG-2 — MEDIUM — `classify_session`'s `EXPERIMENT_SESSION_PATTERNS` branch is dead code, but its loader is a fragile import-time `scripts/` exec

- **Location:** `src/instrument/ledger_ingestion.py:79-103` (`_load_experiment_session_patterns`
  exec's `scripts/_constants.py` via `importlib.util.spec_from_file_location` at module import),
  `:103` (module-level call), `:106-126` (`classify_session`).
- **Description:** `classify_session` is
  `if meta_: return META; if any(p in title for p in PATTERNS): return ATTEMPT; return ATTEMPT`.
  Both the middle branch and the fallthrough return `SOURCE_TYPE_ATTEMPT`, so the
  `EXPERIMENT_SESSION_PATTERNS` list has **no effect on any output** — it is dead. Yet the module
  still runs `_load_experiment_session_patterns()` at import time, which `exec_module`s a file in
  `scripts/` (the only `src/instrument → scripts` edge in the package).
- **Reproduction:**
  1. `python -c "import instrument"` from a checkout where `scripts/_constants.py` has been
     moved/renamed → the `assert spec is not None and spec.loader is not None` at `:94` raises
     `AssertionError`, so **the whole instrument package fails to import** because of a list that
     is never used.
  2. Grep confirms no behavior depends on the branch: `classify_session("batch_042")` and
     `classify_session("some_random_title")` both return `"ledger_attempt"`; only `"meta_*"`
     differs.
- **Expected vs actual:** expected `classify_session` to use the patterns to discriminate
  something (per its own "identical list" guarantee, `:80-88`); actual — the pattern list is
  loaded, executed, and then never changes the return value.
- **Impact:** a hard import-time coupling to the `scripts/` directory layout and to
  `_constants.py`'s own importability, plus dead code that misleads readers into believing the
  gap-(b) fix is doing more than the `meta_` prefix check. `import instrument` also pays an
  unnecessary module exec on every process start (including every script that merely imports the
  package).
- **Fix:** move `EXPERIMENT_SESSION_PATTERNS` into `src/instrument/` (or `experiment_spec`) and
  have `scripts/_constants.py` import it from there (reversing the edge to the correct direction);
  then collapse `classify_session` to the `meta_` prefix check it actually is, or give the
  pattern branch a real second return value.

---

## BUG-3 — MEDIUM — `run.py` records the short config label (`model: deepseek`), not the model that actually executed

- **Location:** `scripts/run.py:59-63` (label derivation) vs `:90-96`/`:106-109` (the `model_id`
  actually passed to the backend), and `:374-376` (`out["model"] = model_label`).
- **Description:** the run executes `model_id = model_override or cfg.get("model_id",
  "deepseek/deepseek-v4-pro")` (full `provider/model`), but the result JSON's `model` field is
  `model_label`, which comes from `cfg.get("model", ...)` — and the configs carry `model:
  deepseek` (a short label, e.g. `experiments/configs/baseline.yaml:27`). The saved result, and
  therefore the KB finding derived from it, records `"deepseek"` rather than
  `"deepseek/deepseek-v4-pro"`. The same physical model is also labeled differently by invocation
  path: `--model deepseek/deepseek-v4-pro` → `model_label = "deepseek-v4-pro"` (`:61`), while the
  config path yields `"deepseek"` (`:63`) — so two runs of the same model write to two different
  result filenames (`{name}_deepseek-v4-pro.json` vs `{name}_deepseek.json`).
- **Reproduction:** `python scripts/run.py experiments/configs/baseline.yaml` → inspect
  `experiments/results/baseline_deepseek.json`; `"model"` is `"deepseek"`, while the run's own
  log line (`:81`) prints `Model: deepseek/deepseek-v4-pro`.
- **Expected vs actual:** expected the persisted `model` to be the canonical `provider/model` id
  that ran; actual — a short config label, which downstream `story_ingestion.
  derive_story_records_from_run_output` (`src/instrument/story_ingestion.py:261`) folds into the
  record identity, so the KB's story-level model attribution is the label, not the model.
- **Impact:** wrong lineage in the `run.py` → KB path; and a silent corpus-fragmentation hazard
  (same model, two identities) if a cell is ever run once via `--model` and once via config.
- **Fix:** persist `model_id` (canonical) as `out["model"]` and derive the display slug
  separately; make `model_label` a pure function of `model_id` (`model_id.split("/")[-1]`) on both
  code paths so the label is deterministic regardless of invocation.

---

## BUG-4 — MEDIUM — flag auto-clear re-parses producer prose, so any render change silently disables it

- **Location:** `scripts/kb_worker.py:128-158` (`_cell_id_and_status_from_observation_text`) and
  the only producer of that text, `src/instrument/observation_ingestion.py:108`
  (`text = f"{cell_id} [{model}]: {status}" + (f" — {why}" if why else "")`).
- **Description:** the kb-registry-v1 consumer recovers `(cell_id, status)` for the auto-clear
  rule (`_maybe_autoclear_flag`, `:188-250`) by string-splitting the rendered one-line `text`.
  The observation record deliberately folds `cell_id` into a one-way hash (`_assessment_id`,
  `observation_ingestion.py:67-75`), so the rendered text is the *only* durable field the
  consumer can correlate on — and it has no schema guard.
- **Reproduction:** change `observation_ingestion.build_observation_record` to render
  `f"{cell_id} {status}"` (drop the `[model]` bracket). Then
  `_cell_id_and_status_from_observation_text` hits the `" [" not in text or "]: " not in text`
  guard at `:153` and returns `(None, None)`; `_maybe_autoclear_flag` returns at `:222-223`
  without clearing — flags stop being auto-cleared with **no error and no log**.
- **Expected vs actual:** expected the flag lifecycle to be driven by structured state; actual —
  a downstream consumer hard-depends on a producer's prose format, and the failure mode is a
  silent no-op (a `healthy` observation no longer clears a stale flag).
- **Impact:** silent lineage drift — tombstoned/cleared flags stop being produced if either the
  producer's render string or the consumer's split heuristic changes. This is a data-plane rule
  whose correctness rests entirely on an untyped string contract.
- **Fix:** carry `cell_id`/`status` structurally on the `KnowledgeRecord` (a trailing-default
  `subject_id`/`subject_status` field, the same backward-compat pattern as `causes`/`supersedes`
  at `src/instrument/knowledge.py:285-290`), and have the auto-clear rule read those fields
  instead of parsing `text`.

---

## BUG-5 — LOW — `_insert_contradiction` picks the *last* matching domain, not the first

- **Location:** `src/instrument/perturb.py:337-345`.
- **Description:**
  ```python
  for domain, pairs in domain_contradictions.items():
      for a, b in pairs:
          keywords = [w for w in a.lower().split()[:5] if w not in _stopwords]
          if keywords and any(kw.lower() in prompt.lower() for kw in keywords):
              all_domains = pairs
              break
  ```
  The `break` exits only the inner `for a, b` loop; the outer `for domain, pairs` continues, so
  `all_domains` is overwritten by every subsequent matching domain. With fixed dict order
  (`api, database, security, general`), a prompt that matches both "api" and "database" ends up
  with `all_domains == database`'s pairs.
- **Reproduction:** `perturb_prompt("Build an API backed by a PostgreSQL database. Use REST.", "insert_contradiction", strength=0.5, rng_seed=0)` repeatedly; the injected contradiction is
  drawn from the `database` set even though `api` matched first.
- **Expected vs actual:** expected the first matching domain to win (the loop reads as
  first-match-wins); actual — the last matching domain in iteration order wins.
- **Impact:** minor measurement variance — the contradiction is still a valid contradiction, so
  no measurement is *wrong*, but the domain selection is nondeterministic-by-accident with
  respect to which constraint axes get perturbed across prompts.
- **Fix:** `return`/`break` out of both loops (e.g. `for domain, pairs in …: …; else: continue;
  break`), or set a flag and exit the outer loop.

---

## BUG-6 — LOW — redundant `tool_call_sequence()` call in `recovery.py`

- **Location:** `src/instrument/recovery.py:86-87`.
- **Description:** `baseline_tools_set = set(baseline.tool_call_sequence())` is immediately
  followed by `baseline.tool_call_sequence()` with the result discarded. The second call is dead.
- **Reproduction:** run `classify_trajectory_segments(baseline, perturbed)`; the baseline
  tool sequence is materialized twice.
- **Expected vs actual:** expected one materialization; actual — two (wasted work, and a latent
  hazard if `tool_call_sequence()` ever gains non-idempotent behavior).
- **Impact:** none today beyond a wasted pass over the baseline steps; a trap for future readers.
- **Fix:** delete line 87.

---

## BUG-7 — LOW — `perturbation_strength` fabricated as `0.0` (baseline) in the summary-recovery migration

- **Location:** `scripts/kb_produce_registry.py:243`
  (`"perturbation_strength": entry.get("perturbation_strength", 0.0)`).
- **Description:** the recovered historical `_results_summary.json` entry is adapted into a
  `StoryResult`-shaped dict with a default of `0.0` for `perturbation_strength`. Every other
  producer in the package honors the `None ≠ 0.0` rule (unmeasured must stay `None`, never a
  fabricated baseline — `story_ingestion.build_story_record` at `:203` passes
  `story_result.get("perturbation_strength")` with no default). A historical entry that genuinely
  lacks the field is stamped as a *baseline* (strength 0.0) cell.
- **Reproduction:** run `kb_produce_registry.py --source summary-recovery --since-sha <pre-shrink>`
  for an entry that has no `perturbation_strength` key; the emitted story record carries
  `perturbation_strength=0.0` instead of `None`.
- **Expected vs actual:** expected `None` (unmeasured); actual — `0.0`, which downstream
  consumers interpret as "this was a baseline cell."
- **Impact:** wrong lineage in the one-time migration — a perturbed-but-unlabeled historical cell
  is recorded as baseline, which can corrupt any grit/strength-axis aggregation that reads the
  recovered story records.
- **Fix:** use `entry.get("perturbation_strength")` (no default), so an absent field stays `None`
  and flows through as unmeasured.

---

## Severity summary

| # | Severity | Area | Finding |
|---|---|---|---|
| BUG-1 | HIGH | KB ingestion round-trip | `observed_at` measurement timestamp dropped on `extract_record` |
| BUG-2 | MEDIUM | KB ingestion / orchestration | dead `EXPERIMENT_SESSION_PATTERNS` branch + import-time `scripts/` exec |
| BUG-3 | MEDIUM | measurement metadata | `run.py` persists short `model` label, not executed `model_id` |
| BUG-4 | MEDIUM | consumer/projection layer | flag auto-clear re-parses producer prose (silent no-op on drift) |
| BUG-5 | LOW | measurement apparatus | `_insert_contradiction` selects last matching domain |
| BUG-6 | LOW | measurement apparatus | redundant `tool_call_sequence()` call |
| BUG-7 | LOW | KB migration | `perturbation_strength` defaulted to `0.0` (fabricated baseline) |

No CRITICAL (data corruption / security / unbounded spend) was found in the prioritized areas:
the `publish_event` three-gate write guard, the per-cell `repository_id` scope, the
`test_runner.run_suite` independent-verification invariant, and the `None ≠ 0.0` convention are
all intact outside the specific call sites flagged above. The two highest-signal findings (BUG-1,
BUG-4) are both instances of the same root cause — structured facts (a timestamp, a cell/status
pair) being flattened into a field that a later stage must reconstruct or drop — and both are
fixed by promoting those facts to first-class record fields.
