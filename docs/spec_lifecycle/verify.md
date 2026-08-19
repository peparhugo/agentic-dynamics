# Spec lifecycle — verification report

**Spec:** `experiments/specs/spec_lifecycle.yaml` (v0.1)
**Arm:** `anthropic/claude-opus-5`, branch `feature/spec-lifecycle-opus`
**Phases verified:** `core_status` (ok) → `kb_registry` (ok) → `verify` (this document)
**Repo revision at verification:** `37de41417` (`[workflow] kb_registry — …`)

Every command below was run from the repo root with `python3` (this checkout has no `python`
alias). No bare `pytest` was ever invoked — every run names its test files explicitly.

---

## Result summary

| # | Check | Result |
|---|---|---|
| 1 | Targeted test suite (8 files, exact names) | **PASS** — 255 passed |
| 2 | `scripts/spec_status.py` regenerates the real index over all 64 committed specs | **PASS** |
| 3 | Spot-check of 5 index/STATUS.md rows | **PASS** |
| 4 | Supersede chains, em-dash rendering, all four statuses | **PASS** (controlled corpus — see caveat) |
| 5 | Legend explains every column and every status; `generated_at` present | **PASS** |
| 6 | Producer dry-run lists every spec, zero errors | **PASS** — 64 records |
| 7 | Authorized producer run → 64 events on `kb:v1:changes` | **PASS** |
| 8 | Registry append: `source_type: "spec"`, correct entity keys | **PASS** — real `kb-registry-v1` handler |
| 9 | Supersede link + `generate_manifest.py` `current`/`superseded` derivation | **PASS** |
| 10 | Producer idempotence (re-run is a no-op) | **PASS** — emitted=0, skipped=64 |
| 11 | Regression: `validate_spec` still gates unmet `requires` | **PASS** |
| 12 | Regression: `run_workflow` writes the ledger; the hooks refresh/emit without failing | **PASS** |
| 13 | Regression: 14 further suites touching the changed modules | **PASS** — 226 passed |

No FAILs. Two things the operator should read before merging are in
[Caveats and operator notes](#caveats-and-operator-notes).

---

## 1. Targeted test suite — PASS

```
$ python3 -m pytest tests/test_experiment_spec.py tests/test_spec_status.py \
    tests/test_spec_ingestion.py tests/test_knowledge.py tests/test_knowledge_ingestion.py \
    tests/test_knowledge_stream.py tests/test_compile_experiment.py \
    tests/test_workflow_runner.py -q

255 passed in 10.69s
```

Breakdown of what is new in that number: `test_experiment_spec.py` +19 (lifecycle round-trip,
unknown-key warning, status validation, whole-corpus load), `test_spec_status.py` 37 (new),
`test_spec_ingestion.py` 36 (new), `test_workflow_runner.py` +5 (`spec_id` on the ledger, the
four `--resume` index-fallback behaviours), `test_knowledge.py` +1 (the `spec` source type).

## 2. Index regeneration — PASS

```
$ python3 scripts/spec_status.py
64 spec(s) indexed
index:  /tmp/exp_spec_lifecycle_opus/experiments/specs/index.json
status: /tmp/exp_spec_lifecycle_opus/experiments/specs/STATUS.md
```

`index.json` header: `{'schema_version': 'spec-status/v1', 'generated_at':
'2026-08-19T22:…+00:00', 'n_specs': 64}` — one entry per committed spec, no exceptions.

`git ls-files experiments/specs/ | wc -l` → 64. The spec prompt says "63 committed specs";
the corpus is in fact 64, because `spec_lifecycle.yaml` itself was committed in `49df49f6e`.
All 64 are present.

## 3. Spot-check, real corpus — PASS

```
| `control_room_portal`   | active | 0.2 | — | — | — | — | — | 0 |
| `rag_knowledge_base`    | active | 0.1 | — | — | — | — | — | 0 |
| `spec_lifecycle`        | active | 0.1 | — | — | — | — | — | 0 |
| `website_rewrite`       | active | 0.3 | — | — | — | — | — | 0 |
| `workflow_step_routing` | active | 0.2 | — | — | — | — | — | 0 |
```

Correct for the current tree, and worth stating plainly rather than glossing:

* **All 64 rows are `active`.** None of the committed YAMLs carries a `status:` or
  `superseded_by:` key, so the index derives `active` for every one. There are **zero real
  supersede chains in the corpus today.**
* **Every run-derived column is an em-dash.** `experiments/results/workflows/` is untracked and
  empty in this checkout, so there is no measured evidence to report. That is the "no evidence"
  rendering, not a failure — exactly the case the em-dash exists for.

Because the real corpus cannot exercise the interesting rendering paths, they are verified
against a controlled corpus in check 4.

## 4. Supersede chains, statuses, em-dash vs failure — PASS (controlled corpus)

A five-spec synthetic corpus in `tmp_path` covering every path, rendered through the same
`collect_entries` / `render_status_md`:

```
| name         | status      | version | supersedes | last_run         | ok   | model                    | cost    | n_runs |
| `chain_v2`   | active      | 0.2     | chain_v1   | 2026-08-18 15:30 | ok   | anthropic/claude-opus-5  | $2.5000 | 1      |
| `never_run`  | active      | 0.1     | —          | —                | —    | —                        | —       | 0      |
| `sketch`     | draft       | 0.1     | —          | —                | —    | —                        | —       | 0      |
| `chain_v1`   | superseded  | 0.1     | —          | 2026-08-10 09:00 | fail | deepseek/deepseek-v4-pro | $0.5000 | 1      |
| `retired`    | tombstoned  | 0.9     | —          | —                | —    | —                        | —       | 0      |
```

* **Chain correct in both directions.** `chain_v2.supersedes == ['chain_v1']`;
  `chain_v1.superseded_by == 'chain_v2'`, and `chain_v1`'s status was *derived* `superseded`
  from that pointer (its YAML asserts no status).
* **Sort order** is status rank then name: `active` → `draft` → `superseded` → `tombstoned`.
* **`fail` and `—` are distinguishable.** `chain_v1`'s run failed and renders `fail`;
  `never_run` has no run at all and renders `—`. Collapsing the two would be the single most
  misleading thing this table could do.
* **`results_pointer`** in `index.json` points at the exact latest run ledger per spec.

## 5. Legend and header — PASS

Programmatic check over the generated `STATUS.md`:

```
columns: ['name', 'status', 'version', 'supersedes', 'last_run', 'ok', 'model', 'cost', 'n_runs']
columns explained: True | missing: []
  status `active` explained: True
  status `draft` explained: True
  status `superseded` explained: True
  status `tombstoned` explained: True
em-dash convention explained: True
generated_at line present: True
results_pointer mentioned: True
```

(`name`/`version` and `model`/`cost` are explained as paired legend rows, which the check
accounts for.) The legend also states the derivation rule for `status` and points at
`index.json` for the machine-readable form including `results_pointer`.

## 6-7. Producer: dry-run then authorized run — PASS

```
$ python3 scripts/kb_produce_sources.py --source spec --dry-run
spec: derived 64 record(s)
dry-run: would emit 64 record(s) (revision=37de41417444, repository-id='agentic-dynamics',
         limit=none) — by source_type: {'spec': 64}
  09eccf5177a1  [spec/upsert]  spec agentic_dynamics_rebrand@0.1 — active
  908527473b2f  [spec/upsert]  spec auto_posthoc_wiring@0.1 — active
  …
```

Every spec in `index.json` is listed; zero errors. The KB stream was reachable
(`127.0.0.1:6380` up), so the authorized run followed:

```
$ python3 scripts/kb_produce_sources.py --source spec
spec: derived 64 record(s)
emitted=64 skipped=0 (already checkpointed) total=64
```

Stream state afterwards (DB 2 on 6380):

```
stream length:                64
operations:                   {'upsert': 64}
kb:v1:source_type_index:      {'spec': 64}
kb:v1:checkpoints:            64
artifacts verified:           64 ok, 0 hash-mismatch, 0 missing
```

The last line re-reads each event's `source_uri` artifact off disk and recomputes
`sha256(bytes)` against the event's `content_hash` — the pointer contract holds for all 64.
All 64 are `upsert` because the registry holds no prior `spec:*` entity (no consumer has run
in this checkout).

Sample event:

```json
{
  "knowledge_id": "09eccf5177a12b5f…",
  "entity_id": "spec:agentic_dynamics_rebrand",
  "operation": "upsert",
  "source_uri": "file://experiments/results/kb/09eccf5177a12b5f….json",
  "source_revision": "37de41417444e6c55b13551c04c874bee0efcaf5",
  "content_hash": "1c3e7e7999708315…",
  "schema_version": "kb/v1",
  "reason": "spec-lifecycle-content=824bc9e0f3e6de60…"
}
```

## 8-9. Registry append and lifecycle derivation — PASS

No `kb_worker.py` consumer is running in this checkout, so nothing drained the stream into
`experiments/results/registry_index.jsonl` on its own. Rather than assert the append shape
from the producer side alone, the **real** `kb-registry-v1` handler from `scripts/kb_worker.py`
was imported and driven over the 64 published events, with `kb_worker.REGISTRY_INDEX_PATH`
redirected to a temp file so the repo's live 296 KB registry was not mutated.

```
registry lines appended:   64
source_type values:        {'spec'}
lifecycle_state values:    {'current'}
entity_id all 'spec:*':    True
```

```json
{
  "knowledge_id": "09eccf5177a12b5f…",
  "entity_id": "spec:agentic_dynamics_rebrand",
  "source_type": "spec",
  "logical_locator": "agentic_dynamics_rebrand",
  "source_uri": "file://experiments/specs/agentic_dynamics_rebrand.yaml",
  "lifecycle_state": "current",
  "supersedes": null,
  "reason": "spec-lifecycle-content=824bc9e0f3e6de60…"
}
```

Then round 2 against those real registry lines — an unchanged re-derivation, a changed one,
and the manifest compaction:

```
(a) unchanged re-derivation emits: 0 record(s)          [convergence guard]
(b) round-1 head        : 4a0130b0abd6bb11
    round-2 knowledge_id: e48480300b32f208
    round-2 supersedes  : 4a0130b0abd6bb11   link correct: True
    operation           : supersede  (event: supersede)
(c) compacted rows      : 64  (one per entity_id)
    spec:spec_lifecycle -> lifecycle_state=current  knowledge_id=e48480300b32f208 (= v2)
    predecessor marker line appended: True
    predecessor derived state: superseded (valid_to=2026-08-19T22:47:26)
```

That is the whole point of the phase, confirmed live: a changed lifecycle produces a
`supersede` event linking the predecessor `knowledge_id`, `kb_worker` appends both the new
line and the predecessor marker, and `generate_manifest.py`'s `_compact_registry_index` /
`_derive_lifecycle` roll it into exactly one `current` row per entity with the predecessor
derived `superseded`.

## 10. Producer idempotence — PASS

```
$ python3 scripts/kb_produce_sources.py --source spec --dry-run
dry-run: would emit 0 record(s) … — by source_type: {'spec': 0}

$ python3 scripts/kb_produce_sources.py --source spec
emitted=0 skipped=64 (already checkpointed) total=64
```

Two mechanisms make this true and they are worth distinguishing. The checkpoint hash skips an
already-emitted `knowledge_id`; separately, `derive_spec_records` skips a spec whose
**lifecycle fingerprint** matches the registry head, which is what stops the supersede chain
growing a link on every run (linking a predecessor changes `supersedes` → `content_hash` →
`knowledge_id`, so an id-only comparison would make every re-run look like a change).
`test_chain_converges_over_repeated_rounds` pins the second one.

## 11. Regression — the requires/produces gate — PASS

```
$ python3 -c "…"   # see below
unmet control rule refused: True
  -> rule "ctrl" requires 'not_measured_yet' — not produced by the ledger or any
     measurement rule in this spec. Instrument it first.
committed spec validates clean: True
compile_spec still produces a DAG: DAG | phases: ['validate', 'cells', 'execute',
                                                  'measure', 'compare', 'writeup', 'adapt']
committed specs failing validation: 0 of 64
```

The load-bearing rule is intact: a control rule with an unmet `requires` is still refused, the
compiler still emits the seven-phase DAG, and adding six lifecycle fields to `ExperimentSpec`
loosened nothing — all 64 committed specs still validate clean.

## 12. Regression — `run_workflow` end-of-run path — PASS

`run_workflow()` was driven through all three phases of `spec_lifecycle.yaml` in a throwaway
git worktree with a stub agent (no LLM), then `scripts/run_workflow.py`'s tail was executed
exactly as `main()` does it:

```
run completed. ok: True | spec_id: spec_lifecycle@0.1
  phases: [('core_status', 'spec_lifecycle@0.1'),
           ('kb_registry',  'spec_lifecycle@0.1'),
           ('verify',       'spec_lifecycle@0.1')]
ledger written: 20260819T224804Z.json | spec_id in json: spec_lifecycle@0.1
spec index: …/experiments/specs/index.json (64 specs)
spec record: spec:spec_lifecycle 0f229dafb638 (upsert)

index row after the hook:
  {'status': 'active', 'last_run_at': '2026-08-19T22:48:04…', 'latest_ok': True,
   'latest_model': 'anthropic/claude-opus-5', 'n_runs': 1,
   'results_pointer': 'experiments/results/workflows/spec_lifecycle/20260819T224804Z.json'}
STATUS.md row:
  | `spec_lifecycle` | active | 0.1 | — | 2026-08-19 22:48 | ok | anthropic/claude-opus-5 | $0.0030 | 1 |
```

So: the run json is still written, `spec_id` is on the job record **and** every attempt record,
the index hook picks the run up immediately, and the KB hook emits. This ledger was synthetic,
so it and its emitted record/event/artifact were removed afterwards and the index regenerated —
`spec_lifecycle` is back to `n_runs: 0` and the stream is back to 64 events.

Both hooks were also fault-injected and confirmed non-fatal:

```
warning: spec index refresh failed (read-only fs) — run itself unaffected
spec record: nothing to emit (unchanged or KB unreachable)     # stream down
warning: spec record emit failed (disk full) — run itself unaffected
```

## 13. Regression — wider sweep — PASS

```
$ python3 -m pytest tests/test_policy_ingestion.py tests/test_registry_cli.py \
    tests/test_kb_worker.py tests/test_knowledge_isolation.py tests/test_code_ingestion.py \
    tests/test_quality_ingestion.py tests/test_story_ingestion.py tests/test_review_ingestion.py \
    tests/test_ledger_fields.py tests/test_actuation_ingestion.py \
    tests/test_observation_ingestion.py tests/test_data_integrity.py \
    tests/test_step_routing.py tests/test_auto_posthoc.py -q

226 passed, 13 warnings in 4.39s
```

Notably `test_policy_ingestion.py` and `test_registry_cli.py` are green: the new `spec` source
type sits alongside `policy` (which still globs the same YAMLs for their text excerpt) without
either displacing the other, and `record_factory`'s new `entity_id` seam did not re-key any
existing producer's artifacts.

---

## Caveats and operator notes

**1. A pre-existing test bug flushes the live KB stream — fixed here.**
`tests/test_knowledge_stream.py` set `FINOPS_KB_DB=15` at module top, but `connect()`'s `db`
default binds when `instrument.knowledge_stream` is *first* imported. Any sibling test module
that imports from `instrument` pulls it in through the package `__init__` first, so in a
combined pytest invocation the default was already bound to the production value (2) before
`os.environ.setdefault` ran — and the `redis2` fixture therefore `flushdb()`'d **production
DB 2**. This reproduces on a clean checkout at `37de41417`, so it predates this work; it was
hit once during the `kb_registry` phase's first combined run. The fixture now passes
`db=TEST_DB` explicitly and `test_contract_constants` asserts the invariant that actually
protects the corpus. Nothing authoritative was lost — the durable state is
`experiments/results/kb/` plus `registry_index.jsonl`, both intact and unmodified; the stream
is transport only.

**2. This phase leaves 64 new KB artifacts in a tracked directory.**
The authorized producer run wrote `experiments/results/kb/<knowledge_id>.json` × 64 (1913 →
1977 files). `experiments/results/kb/` is git-tracked, so they appear as untracked files in
`git status`. They are the durable half of the pointer contract — a consumer cannot verify an
event without them — so they should be committed alongside this phase, but that is the
operator's call. The 64 corresponding events sit on `kb:v1:changes` (DB 2) awaiting a
`kb_worker.py` consumer; until one runs, `registry_index.jsonl` will not gain its `spec` rows.

**3. A parallel arm of this spec is running.**
`deepseek/deepseek-v4-pro` is executing the same spec in `/tmp/exp_spec_lifecycle_dspro`
against the same Redis on 6380. `knowledge_id` is the idempotence key, so concurrent producers
converge rather than conflict, but expect interleaved events on the shared stream when
diffing the two arms.

**4. The real corpus has no lifecycle data yet.**
All 64 rows are `active` with no runs, so the merged `STATUS.md` will look sparse until specs
start carrying `status:`/`supersedes:` keys and runs start landing in
`experiments/results/workflows/`. The plumbing is verified against controlled corpora
(check 4) and by 73 unit tests across the two new modules.

---

## What changed

Three layers, added in phase order.

**1. Lifecycle on the spec (`core_status`).** `ExperimentSpec` gained `status`, `supersedes`,
`superseded_by`, `completed_at`, `last_run_at`, `results_pointer`, round-tripping through
`to_dict`/`from_dict` and preserved by `load_spec`. `validate_spec` restricts `status` to the
four `SPEC_STATUSES` (`""` means unset — which is how all 64 committed specs load) and rejects
self-referential lineage. Unknown top-level keys now raise a visible `UserWarning` instead of
vanishing, which is what a typo'd `supercedes:` used to do. `ExperimentSpec.spec_id` is the one
canonical builder for the long-declared-but-never-emitted `LEDGER_FIELDS` entry.

**2. The derived index (`core_status`).** `src/instrument/spec_status.py` joins the spec corpus
with the run ledgers and emits `experiments/specs/index.json` (machine schema
`spec-status/v1`) and `experiments/specs/STATUS.md` (agent-facing table + legend).
`scripts/spec_status.py` is a thin CLI over it. The index is derived, never hand-maintained:
the YAML's lifecycle keys are the *seed*, the run JSONs are the *measured evidence* and win
where both speak. Missing data renders as an em-dash and never raises — a missing run
directory, a corrupt ledger, or an unloadable spec each warns and skips.

**3. Hooks and lineage (`core_status` + `kb_registry`).**
`scripts/run_workflow.py` now refreshes the index and emits the spec's KB record after writing
the run ledger, both best-effort. `workflow_runner` stamps `spec_id` onto the job record and
every attempt record, and `--resume` gained an index fallback that fires *only* when the
git-log path finds no `[workflow]` commit (guarded on the run's goal prefix and on per-phase
`status == "ok"`). `src/instrument/spec_ingestion.py` (`spec-lifecycle/v1`) derives one
`source_type="spec"` record per index entry — `entity_id = "spec:<name>"`, `POLICY`/`[P]`,
observation family — and links the predecessor `knowledge_id` when the registry already holds
that entity, which is what drives `generate_manifest.py`'s `current`/`superseded` derivation.
`scripts/kb_produce_sources.py --source spec` is the batch producer. `record_factory.build_record`
gained an optional `entity_id` parameter (a function parameter, not an `extra_fields` key, so
the override reaches both the record field and the `compute_knowledge_id` input).

**Pointers.** `experiments/CONTEXT.md`, `.opencode/instructions/conventions.md`, `AGENTS.md`
— and `.claude/rules/conventions.md`, the hand-synced port — all now tell an authoring agent to
read `experiments/specs/STATUS.md` first. `src/instrument/CONTEXT.md` and `scripts/CONTEXT.md`
gained rows for the two new modules and the extended producer.

**Diffstat** (feature branch vs `main`): 24 files, +4190 / −26, of which 1031 lines are the
generated `index.json` and 101 the generated `STATUS.md`.
