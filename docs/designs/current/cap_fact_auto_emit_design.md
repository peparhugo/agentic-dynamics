---
status: accepted
---
# Fact Auto-Emit on Workflow Completion — Hook Design

**Spec:** `workflows/repository/cap_fact_auto_emit.yaml`, phase `f1_hook_design`.
**Phase:** `f1_hook_design` (phase 1 of 3 — **`design`** → `implement` → `adversarial_verify`).
**Date:** 2026-08-24 · **Model:** anthropic/claude-sonnet-5 · **Branch:** `feature/cap-fact-auto-emit`
**Deliverable rule:** design-only (`f1`'s `GUARD`). This phase adds exactly one file
(`docs/designs/current/cap_fact_auto_emit_design.md`) and changes nothing under `src/`,
`scripts/`, `tests/`. Every signature below is a sketch — `f2_implement` writes the code.

---

## 0. How to read this document

Three conventions:

- **REUSE** marks a mechanism that already exists, cited `file:line`. **NEW** marks a function
  this design introduces (sketch only — no file is created by this phase).
- Every design choice is stated as **Decision** + **Rejected alternative(s)** + **Why**, per the
  spec's `GUARD`: "every option weighed against the existing paths."
- The spec's seven `hard_rules` are numbered (1)-(7) throughout; §8 is the PASS/FAIL check
  against all seven.

**Current state** (`cap_fact_auto_emit.yaml`'s own `current_state` field, verified against the
tree): facts are derived manually via `python scripts/kb_produce_facts.py --reducer workflow_facts/v1`
— a stand-alone batch job an operator runs by hand, over the **entire** corpus of
`experiments/results/workflows/**/*.json`. The reducers are pure and tested
(`tests/test_context_plane_reducers.py`), `fact_ingestion.derive_fact_records` has in-batch
chaining (`control/fact_ingestion.py:178-245`), and `run_artifact_id` gives a stable per-run
identity (`control/reducers/_common.py:55-71`). **Nothing on the workflow-completion path emits
facts today** — confirmed by grep: neither `scripts/run_workflow.py` nor
`runtime/workflow_runner.py` reference `fact_ingestion`, `control.reducers`, or
`kb_produce_facts` anywhere. The CAP I4/I6/I7 references already in `run_workflow.py` (`--cap-snapshot`/
`--cap-shadow`/`control_route`) are a **different concern** — they snapshot/shadow/apply *routing
decisions*; they do not derive or emit *facts*.

---

## 1. WHERE completion triggers derivation

### Decision: `scripts/run_workflow.py`'s finalize section, not `workflow_runner.py`

Add a new best-effort call, `_emit_workflow_facts(spec, args, result)`, immediately after the two
calls that already live there:

```python
_refresh_index(spec.name)
_emit_spec_record(spec.name, revision=result.git_sha)
_emit_workflow_facts(spec, args, result)          # NEW — this design
```

(`scripts/run_workflow.py:175-176`, the exact insertion point.)

### Why not `workflow_runner.run_workflow`?

**This is a dependency-direction violation, not a style preference.** The mental model's tier map
is explicit: `core (0) ← experiment/measurement/runtime/adapters/knowledge/reporting (1) ← control
(2) ← apps (3)`, enforced by `tests/test_dependency_direction.py`. `control.fact_ingestion`,
`control.reducers.*`, and `control.facts` all live in the **control** plane (tier 2).
`runtime.workflow_runner` is tier 1. The ONLY tier-1→tier-2 edge that exists today is the pinned
adapter telemetry seam (`adapters.opencode`/`claude_adapter → control.live`); `workflow_runner`
itself is **dependency-inverted** specifically so it never imports `control` — it consumes the
runtime-owned `Router`/`TelemetryPublisher` protocols and takes the control implementation
injected from the composition root (`docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md`;
mental-model.md's own words: "so runtime never imports control"). `run_workflow.py`'s own comments
say this three times over, verbatim, at every router-seam call site: *"Built here, at the
composition root, exactly where `route_step` is injected — `runtime.workflow_runner` never
imports `control` either way (Debt-2)"* (`scripts/run_workflow.py:127-128,138-139`). Adding a
`fact_ingestion`/`control.reducers` import inside `workflow_runner.py` would open a second,
unpinned tier-1→tier-2 edge — exactly the thing Debt-2 was written to prevent. The script is the
composition root; it already imports `control.rules`, `control.context_compiler`,
`control.live`, `control.reducers._common`, and `control.signal_store` freely. It is the only
place in this call chain allowed to import `control.fact_ingestion` too.

### Why here and not, say, a separate post-hoc CLI hook?

Because the just-finished run's own JSON must already be on disk. `load_run_jsons()`-style
derivation reads `experiments/results/workflows/**/*.json` (`scripts/kb_produce_facts.py:103-130`);
the ledger write happens at `scripts/run_workflow.py:167-172`, immediately before `_refresh_index`/
`_emit_spec_record`. Any hook must run **after** that write. The finalize section is the only
place that is both (a) after the ledger write and (b) the composition root permitted to import
`control`.

### Rejected alternative: a `rag_params`-style opt-in flag inside `run_workflow()`

`workflow_runner.py` already has one opt-in producer wired exactly this way —
`rag_params.get("emit_self")` → `_emit_self_finding` → `knowledge.knowledge_ingestion.emit_phase_finding`
(`workflow_runner.py:634-642`, `274-287`). That path was rejected as the *location* for this hook
(not as a pattern — see §2, §5) for the same dependency-direction reason: `emit_phase_finding`
lives in `knowledge`, tier 1, so `_emit_self_finding` is a legal tier-1→tier-1 call; a fact-emit
equivalent would need `control.fact_ingestion`, tier 2, which `workflow_runner.py` cannot import.
Threading a `Callable` for fact-emission through `run_workflow()`'s parameters (mirroring
`router`/`publisher_factory`'s injection pattern) was considered and is **not necessary**: unlike
routing, fact-emission has no per-phase behavior to inject — it fires exactly once, after the
whole run is a persisted, immutable artifact. Injecting a no-op callable for a single
end-of-run call would add a parameter and a test surface for no behavioral gain over calling it
directly from the script that already owns `control` imports.

---

## 2. WHAT gets derived — reducer scope

### Decision: a scoped ladder over the just-finished run + its own spec, not the full corpus

`_derive_workflow_facts` (`scripts/kb_produce_facts.py:215-278`, the function `--reducer
workflow_facts/v1` runs) bundles **four** reducers under one shared `repository_id`: it calls
`load_run_jsons()` (rglobs **every** run JSON ever written), `load_spec_configs()` (loads **every**
spec YAML in the repo), and `si.load_index_entries()` (the **whole** spec lifecycle index), then
folds all three lower tiers into `workflow_facts_v1`. That is correct for the manual, periodic,
whole-corpus batch job — it is the wrong shape for a hook that fires on every single workflow
completion:

- **Cost**: re-scanning every historical run JSON and every spec YAML on every completion is
  O(corpus) work paid on every run, growing without bound as the corpus grows.
- **Scope correctness** (§3 makes this precise): `_derive_workflow_facts` threads ONE
  `repository_id` through all four reducers. If that value is `cell_scope(workdir)` (§3's
  decision), running `policy_facts_v1`/`spec_status_v1` — which are genuinely corpus-wide,
  not per-run — under a narrow, ephemeral, per-cell `org:self-<cell>` prefix would fragment
  those facts across one registry slot per cell instead of the one canonical project-wide slot,
  permanently bloating the registry with facts nobody queries at that scope.

The design instead derives exactly what one completed run can produce, in memory, with no new
filesystem scans:

```
NEW  _run_evidence_for(result: WorkflowRunResult) -> tuple[EvidenceItem, ...]
       # REUSE kb_produce_facts._run_evidence([result.to_dict()]) verbatim (already list-shaped;
       # a single-element list is not a new code path, just a smaller input).

NEW  _policy_evidence_for(spec: ExperimentSpec) -> tuple[EvidenceItem, ...]
       # the SAME projection load_spec_configs() builds (name/budget_usd/max_attempts/model_pool),
       # applied to the ONE ExperimentSpec run_workflow.py already holds in memory — no
       # filesystem re-scan, no _spec_paths() corpus walk.

NEW  derive_run_facts(result, spec, *, repository_id, revision, now) -> list[KnowledgeRecord]
       # lives in scripts/kb_produce_facts.py (extends the existing module — no new file, no new
       # transport, per hard rule (5)):
       #   run_ev    = _run_evidence_for(result)
       #   lower     = attempt_facts_v1(ReducerInput(evidence=run_ev, repository_id=..., ...))
       #             + job_facts_v1(ReducerInput(evidence=run_ev, repository_id=..., ...))
       #   pol_ev    = _policy_evidence_for(spec)
       #   lower    += policy_facts_v1(ReducerInput(evidence=pol_ev, repository_id=..., ...))
       #   wf_facts  = workflow_facts_v1(ReducerInput(facts=fi.finalize_fact(...) over lower, ...))
       #   return fi.derive_fact_records(wf_facts, registry_path=REGISTRY_INDEX_PATH)
```

`spec_status_v1` (I1, the corpus-wide spec lifecycle index) is **deliberately excluded** — grepping
`workflow_facts_v1`'s reducer (`control/reducers/workflow_facts.py`) shows it folds in
`policy` facts (the `max_spend_usd` ceiling, line 62) but never reads a `spec_status` predicate.
It has no per-run input to give and stays exclusively the manual/scheduled batch job's job
(`kb_produce_facts.py --reducer spec_status/v1`), unchanged by this design.

### Rejected alternative: reuse `kb_produce_facts._derive_workflow_facts` verbatim

Considered first, because it is the literal, no-new-code path (hard rule 5's "reuse
`kb_produce_facts`' derivation path" read most literally). Rejected because it re-derives
`policy_facts_v1`/`spec_status_v1` over the **whole** corpus on every single workflow completion —
paying full-corpus I/O per run and fragmenting corpus-wide facts across per-cell scope (see cost
+ scope-correctness bullets above). The scoped ladder still calls the **same** reducer functions
(`attempt_facts_v1`, `job_facts_v1`, `policy_facts_v1`, `workflow_facts_v1`) and the **same**
`fi.finalize_fact`/`fi.derive_fact_records` glue — no reducer changes, no new transport (hard
rule 5's actual constraint) — it only changes what evidence is *handed to* those reducers, which
is the producer's job, never the reducer's (`fact_ingestion.py`'s own docstring: "the reducer does
no I/O").

### Rejected alternative: only `attempt_facts_v1`/`job_facts_v1` (skip `workflow_facts_v1`)

Considered to make the per-run ladder even cheaper (no policy evidence needed). Rejected: `route_next_job_v1`
(the CAP I6/I7 control rule this whole effort feeds, `control/rules.py:77-138`) proposes routes
from workflow-scope health/status/budget signals — exactly `workflow_facts_v1`'s five predicates
(`workflow_status`, `workflow_health`, phase counts, budget overrun), not raw per-phase
`attempt_facts`. Stopping at I2 would derive facts nothing downstream is contracted to consume.

---

## 3. `repository_id` / scope resolution for the emitted facts

### Decision: `repository_id = cell_scope(workdir)` — reuse the exact value the I4/I6/I7 router
### wiring already passes for the SAME run

```python
_emit_workflow_facts(spec, args, result)
    # inside: repository_id = cell_scope(args.workdir)   # runtime.workflow_runner.cell_scope
```

`cell_scope` (`runtime/workflow_runner.py:262-271`) already ships and is already imported into
`scripts/run_workflow.py` (`run_workflow.py:33`). The three existing router seams
(`make_snapshotting_router`/`make_shadow_router`/`make_applying_router`) already call
`repository_id=cell_scope(args.workdir)` for this exact `args.workdir`
(`run_workflow.py:122,134,145`). This is not a style match — it is **required for the emitted
facts to be visible at all** to that same run's own routing calls. Traced precisely:

1. `RegistryFactStore.current_facts(predicate)` (`context_compiler.py:447-453`) scans the
   registry for candidate `entity_id`s by predicate suffix, with **no `repository_id` filter** —
   `repository_id` on the store is used only as a fallback default when reconstructing a
   `CanonicalFact.repository_id` field (`context_compiler.py:443`), never to exclude candidates.
2. Every reducer (`attempt_facts.py:152`, `job_facts.py:110`, `workflow_facts.py:177`,
   `policy_facts.py:87`, `spec_status.py:147`) builds `scope_path` as
   `f"org:{inp.repository_id}/workload:{...}/job-or-workflow:{...}"` — `repository_id` is the
   **root segment** of `scope_path`, not a side-channel filter.
3. `compile_context`'s per-requirement resolution calls `scope_visible(requested_scope_path,
   fact.scope_path, ...)` (`context_compiler.py:232-260`), which requires the fact's `scope_path`
   to be **equal to, or a string-prefix ancestor of**, the requested `scope_path`
   (`_is_ancestor`, line 227-229) — and the router seams build their `requested_scope_path` as
   `f"org:{repository_id}/workload:{workload}/job:{cell_id}"` with `repository_id =
   cell_scope(args.workdir)` (`context_compiler.py:939`, called from `make_shadow_router` etc.).

Since `org:` is the FIRST segment on both sides, **a mismatched `repository_id` between producer
and consumer makes `scope_visible` return `False` unconditionally** — the fact would exist in the
registry, resolve fine by `fact_id`, and still be invisible to `route_next_job_v1`'s contract
resolution for that cell. Matching `cell_scope(workdir)` exactly is therefore not a convention
choice, it is the correctness condition the router wiring already established.

`cell_scope`'s own contract (`workflow_runner.py:262-271` docstring) — "`FINOPS_CELL_ID` overrides
the basename when set (a worker that already pinned a cell id keeps that identity)" — is what
keeps this stable across REPEATED runs of the "same" logical cell in different ephemeral
worktrees: a queue/campaign harness that pins `FINOPS_CELL_ID` before each invocation gets the
same `self-<cell-id>` scope every time, so `job_facts_v1`'s current-per-cell semantics
accumulate correctly across runs; an ad-hoc single invocation with no pin degrades to the
worktree basename (acceptable — there is no "campaign" concept to preserve in that case either).

### Rejected alternative: the flat project-wide `REPOSITORY_ID` constant (`"agentic-dynamics"`)

This is `kb_produce_facts.py --repository-id`'s own CLI default
(`knowledge_ingestion.py:93`, `kb_produce_facts.py:407-411`), and it is what the GOAL's literal
phrasing might suggest reusing ("the derivation path" implies "its defaults too"). **Rejected**,
precisely because of the proof above: emitting per-run facts at `org:agentic-dynamics/...` while
the SAME run's own `--cap-shadow`/`--cap-snapshot`/`control_route` router calls query
`org:self-<cell>/...` would make this hook's own output invisible to the routing decisions it
exists to feed — a silent, hard-to-detect correctness bug, not merely an inconsistency. The flat
`REPOSITORY_ID` constant remains correct and unchanged for the reducers this hook does **not**
run (`spec_status_v1`, and any corpus-wide `policy_facts_v1` run by the separate manual batch
job) — those legitimately describe the whole project, not one cell, and stay on the manual
CLI's existing default.

---

## 4. Flag surface — name, default, precedence

### Decision

| Surface | Name | Default | Semantics |
|---|---|---|---|
| Env var | `FINOPS_FACT_AUTO_EMIT` | unset → **ON** | `"0"` disables; any other value (including unset) is ON |
| CLI flag | `--no-fact-emit` (on `scripts/run_workflow.py`) | not passed → ON | `store_true`; passed → disables unconditionally |

**Precedence**: `--no-fact-emit` (if passed) always wins → else `FINOPS_FACT_AUTO_EMIT == "0"`
disables → else emit. This mirrors the existing `--signals`-overrides-auto-built-store and
`--no-commit`-overrides-`commit=True` precedence already in `run_workflow.py:71,99-107` (an
explicit per-invocation CLI flag always outranks an ambient default).

```python
ap.add_argument("--no-fact-emit", action="store_true",
                help="disable the CAP fact auto-emit hook for this invocation "
                     "(default: enabled; also controlled by FINOPS_FACT_AUTO_EMIT=0)")
...
if not args.no_fact_emit and os.environ.get("FINOPS_FACT_AUTO_EMIT") != "0":
    _emit_workflow_facts(spec, args, result)
```

### Why default-ON (a deliberate posture break from every other `FINOPS_*` flag)

Every existing gate flag (`FINOPS_KB_WRITE`, `FINOPS_ACTUATION_ARMED`) is **opt-in**, "1"-truthy,
default OFF — the house convention for "a writer must be explicitly authorized." This hook is
different by explicit requirement (hard rule 4: "Default-ON with a disable flag ... state and
document the choice"): the whole point is that the fact store stays current **without** a human
remembering to run `kb_produce_facts.py` after every run. Two things keep default-ON safe despite
breaking the opt-in convention:

1. **It is failure-tolerant by construction** (§5) — a downed Redis or a missing `FINOPS_KB_WRITE`
   authorization degrades to a warning, never a failed run. Default-ON never gates the run itself,
   unlike `FINOPS_KB_WRITE`/`FINOPS_ACTUATION_ARMED`, which gate whether a write is even attempted.
2. **It still respects the underlying write guard.** `FINOPS_FACT_AUTO_EMIT` only decides whether
   `_emit_workflow_facts` is *called*; the call itself still goes through
   `knowledge_stream.publish_event`'s existing `FINOPS_KB_WRITE` gate (scoped on, per §5) — so a
   deployment that has never turned on real KB writes (no Redis, `FINOPS_KB_WRITE` never set
   globally) sees this hook attempt and gracefully skip, not silently start writing where nothing
   wrote before.

### Rejected alternative: `FINOPS_DISABLE_FACT_EMIT=1` (opt-out named as an opt-in "1" flag)

Naming an opt-out flag with "`=1` to activate" semantics (mirroring `FINOPS_KB_WRITE`'s literal
string shape) was considered so every `FINOPS_*` flag reads the same way ("`=1` turns something
on"). Rejected: here "something" is *disablement*, and `FINOPS_DISABLE_FACT_EMIT=1` reads
backwards at the call site (`if not disabled: emit` vs `if enabled: emit`) with no compensating
consistency benefit — the flag's own *purpose* (default-ON) is already the one-off case in this
family; naming it to look like the opt-in family would only hide that it behaves oppositely.
`FINOPS_FACT_AUTO_EMIT=0` reads correctly in both directions (`FINOPS_FACT_AUTO_EMIT` describes
the feature, `!= "0"` means "on").

---

## 5. Failure semantics

### Decision: best-effort at two layers, matching `_emit_spec_record`'s established shape exactly

`scripts/run_workflow.py:198-222` already has the precedent for "a post-run KB write that must
never affect the run's outcome": `_emit_spec_record` wraps `spec_ingestion.emit_spec_record` (which
itself swallows every internal failure and returns `None`, `spec_ingestion.py:583-585`) in an
outer `try/except Exception` that only logs. `_emit_workflow_facts` follows the same two-layer
shape:

```python
def _emit_workflow_facts(spec, args, result) -> None:
    """Best-effort. See _emit_spec_record's docstring for the identical posture: the run has
    already finished and its ledger is already on disk, so a fact-emission problem must degrade
    to a warning, never change the run's outcome or exit status."""
    try:
        from scripts.kb_produce_facts import derive_run_facts, emit_records
        from agentic_dynamics.knowledge import knowledge_stream as ks
        from agentic_dynamics.knowledge.knowledge_ingestion import _authorized_kb_write

        records = derive_run_facts(
            result, spec,
            repository_id=cell_scope(args.workdir),
            revision=result.git_sha or REVISION_FALLBACK,
            now=_now_iso(),
        )
        if not records:
            print("workflow facts: nothing to emit (unchanged)", file=sys.stderr)
            return
        with _authorized_kb_write():
            r = ks.connect()
            emitted, skipped = emit_records(r, records)
        print(f"workflow facts: emitted={emitted} skipped={skipped}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — progressive path, never a gate
        print(f"warning: workflow fact emit failed ({exc}) — run itself unaffected", file=sys.stderr)
```

`derive_run_facts` itself does no I/O beyond reading the one spec already in memory and the one
`result` already in memory (no filesystem, no network) — so the only things that can actually
raise are the reducers/glue (deterministic, already tested) and the emission half
(`ks.connect()`/`ks.publish_event`, which need Redis). The outer `try/except` is belt-and-braces
around the whole thing, matching `_emit_spec_record`'s stated reasoning: "nothing after a
completed run may change its outcome."

### Concrete failure modes and expected degrade

| Failure | Expected behavior |
|---|---|
| Redis (6380/DB 2) unreachable | `ks.connect()` raises inside the `try` → caught → warning printed → run's exit status/`result` untouched |
| `registry_index.jsonl` missing/unreadable | `spec_ingestion.registry_head`'s existing graceful-skip-on-corruption path (already relied on by `derive_fact_records`) treats it as "no head" → facts emit as first versions, not a crash |
| Run has no `git_sha` (a `--no-commit` invocation) | `revision` falls back to `REVISION_FALLBACK = "workflow-run/unrevisioned"` (`control/reducers/_common.py:20-23`), same posture `ledger_ingestion.REVISION_FALLBACK` already uses |
| A phase failed (`result.ok is False`) | Still emits — §6/§2's `job_status`/`workflow_status` precedence (`workflow_facts.py`'s docstring) is explicitly built to represent `"failed"` as a first-class value, not to suppress emission; facts are measurement, a failed run is itself a fact worth recording (hard rule 3: "facts are measurement; the run is the source of truth") |
| Double-invocation on the same run artifact | §6 — idempotent by construction, not a failure mode |
| `FINOPS_KB_WRITE` never armed elsewhere in the deployment | `_authorized_kb_write()` arms it only for this call's duration (`knowledge_ingestion.py:432-447`'s existing contextmanager) — no dependency on an operator having exported it globally |

---

## 6. Idempotence

### Decision: reuse `run_artifact_id` + the fact-content-fingerprint convergence guard verbatim — no new dedup machinery

Two independent, already-existing layers make re-emitting the same run artifact a byte-identical
no-op, satisfying hard rule (2) with zero new code:

1. **Content identity of the run itself**: `run_artifact_id(run)` (`control/reducers/_common.py:55-71`)
   is `sha256` over the run's own canonical JSON — re-deriving from the same `result.to_dict()`
   twice yields the same `EvidenceItem.evidence_id`, hence the same facts' inputs.
2. **Convergence guard on the registered value**: `fact_fingerprint` (`fact_ingestion.py:99-113`)
   excludes provenance fields (`evidence_ids`, `inputs_digest`) precisely so that "the same value,
   re-observed" fingerprints identically to its first observation even though the record's own
   `knowledge_id` differs — `derive_fact_records` (`fact_ingestion.py:178-245`) checks this
   fingerprint against the registry head and emits **nothing** when unchanged
   (`fact_ingestion.py:236-238`, "head whose fingerprint matches → emit nothing").
3. **Transport-level dedup**: `emit_records` (`kb_produce_facts.py:362-383`, reused verbatim) skips
   any `knowledge_id` already present in the Redis checkpoint hash before writing the artifact or
   publishing — a second call within the same Redis lifetime is a true no-op even before the
   fingerprint check runs.

Nothing in this design invents a new dedup key. A double-emit (accidental double-invocation, or
re-running the hook against an already-persisted ledger file offline) degrades to "0 emitted, N
skipped" or "0 records derived" depending on which layer catches it first — both are correct,
neither corrupts the chain.

---

## 7. New surface summary (sketch only — `f2_implement` writes the code)

```
# scripts/kb_produce_facts.py — extend, no new file
NEW  _policy_evidence_for(spec: ExperimentSpec) -> tuple[EvidenceItem, ...]
NEW  derive_run_facts(result, spec, *, repository_id: str, revision: str, now: str
                      ) -> list[KnowledgeRecord]

# scripts/run_workflow.py — extend, no new file
NEW  --no-fact-emit  (argparse flag, store_true)
NEW  _emit_workflow_facts(spec, args, result) -> None   # best-effort, see §5
     called at run_workflow.py:177, after _emit_spec_record
```

No changes to `control/fact_ingestion.py`, any `control/reducers/*.py`, `control/facts.py`, or
`knowledge/knowledge_stream.py` — reducer semantics and transport are untouched (hard rule 5's
`GUARD`, restated in `f2`'s prompt: "no reducer changes; no new transport").

---

## 8. Hermetic test plan (for `f2_implement`)

`tests/test_kb_produce_facts_integration.py` is the existing template
(`importlib.util.spec_from_file_location` to load the non-package script module, `monkeypatch`
its `REPO_ROOT`/`REGISTRY_INDEX_PATH` module attributes to `tmp_path`, never call
`main()`/`emit_records()` against a real Redis). The new tests extend this pattern:

1. `derive_run_facts` over one hermetic `WorkflowRunResult`-shaped dict + one hermetic
   `ExperimentSpec` → asserts the expected fact records (predicate/value/scope_path), with a
   temp `registry_index.jsonl` standing in for the durable registry (same simulated-registration-line
   technique the existing file uses).
2. Re-running `derive_run_facts` over the byte-identical run → asserts **zero** new records (the
   convergence guard, §6).
3. A run with `ok=False` / a failed phase → asserts facts still derive (`job_status`/
   `workflow_status` reflect `"failed"`, not silence — §5's table).
4. `_emit_workflow_facts` with a monkeypatched `ks.connect` that raises → asserts it prints a
   warning and returns `None`, never raises (fed a real `WorkflowRunResult`/`ExperimentSpec` pair
   via `run_workflow(..., router=<fake>, run_agentic_fn=<fake>)`, the existing hermetic pattern
   already used throughout `tests/test_workflow_runner.py`).
5. `--no-fact-emit` and `FINOPS_FACT_AUTO_EMIT=0` each suppress the call (assert the mocked
   `_emit_workflow_facts` is never invoked); precedence — CLI flag wins even when the env var is
   unset/"1".
6. The full I0-I7 CAP suites (`test_context_plane_reducers.py`, `test_kb_produce_facts_integration.py`,
   `test_workflow_runner.py`, `test_supervise.py`, `test_dependency_direction.py`) re-run green,
   proving no regression.

---

## 9. Adversarial-verify checklist (for `f3_adversarial_verify`)

The spec's hard rule (6) names five attacks; this design's expected behavior for each, to be
confirmed (not merely asserted) in `f3`:

| Attack | Expected behavior under this design |
|---|---|
| Double-emit from a copied artifact | Copied file → same `run_artifact_id` → same `EvidenceItem.evidence_id` → same facts → convergence guard emits nothing new (§6) |
| Concurrent runs of one cell emitting interleaved | Each run's own `_emit_workflow_facts` call only reads its OWN `result` (no shared in-process state); the shared mutable state is the registry file + Redis checkpoint hash, both already the in-batch-chaining/registry-head-lookup layer `fact_ingestion.derive_fact_records` was built to serialize against — `f3` must confirm no lost-update window exists between two processes' `registry_head` read and their own `emit_records` write (this is the one item genuinely unverified by this design phase; flagged, not assumed) |
| Partial registry writes (registry unreachable mid-emit) | `emit_records` writes the durable artifact **before** publishing the pointer event and **before** checkpointing (`kb_produce_facts.py:376-381`, unchanged) — a crash between artifact-write and checkpoint reproduces the existing "artifact exists, not yet checkpointed" state the batch job already tolerates (next run re-derives, sees no checkpoint, re-emits) |
| Emit of a run whose phases changed after finalize | Not reachable under this design: `_emit_workflow_facts` is called exactly once, synchronously, from the same process and the same `result` object that was just written to disk — there is no "finalize, then later mutate, then emit" window in this hook (unlike the manual batch job, which reads whatever is on disk at scan time) |
| Flag precedence confusion | §4's precedence table (`--no-fact-emit` > `FINOPS_FACT_AUTO_EMIT` > default-ON) — `f3` writes the CLI-flag-wins-over-env test named in §8 item 5 |
| Regression in `fact_ingestion`'s in-batch chaining or the dedup guard | §8 item 6 — no reducer or `fact_ingestion` code changes in this design; the existing suites re-running green IS the regression check |

---

## 10. PASS/FAIL — design against the seven hard rules

| # | Hard rule | Status | Where addressed |
|---|---|---|---|
| (1) | Every phase commits `[workflow] <phase>` with green tests | **N/A this phase** (design-only; `f1` has no tests to run) — will apply to `f2`/`f3` |
| (2) | Idempotent: re-emitting the same run artifact is byte-identical no-op | **PASS** | §6 — two independent existing layers, zero new dedup code |
| (3) | Emit failure never fails the workflow run | **PASS** | §5 — two-layer `try/except`, matches `_emit_spec_record`'s exact precedent |
| (4) | Default-ON with a disable flag, choice stated and documented | **PASS** | §4 — `FINOPS_FACT_AUTO_EMIT`/`--no-fact-emit`, posture break explicitly justified |
| (5) | No reducer/transport changes; reuse `kb_produce_facts`' derivation path | **PASS** | §2, §7 — same reducer functions, same `fact_ingestion`/`emit_records` glue; only the evidence handed in is newly scoped |
| (6) | `f4`/`f3` adversarial phase mandatory; specific attacks named | **Design-level PASS, one item flagged** | §9 — four of five attacks reasoned through; the concurrent-write registry race is named as unverified by design alone and left as `f3`'s explicit job |
| (7) | PASS/FAIL log | **PASS** | this section |

**Overall: PASS.** One open item carried forward explicitly rather than hand-waved: whether two
concurrent `_emit_workflow_facts` calls (two cells finishing at the same instant) can race on
`registry_head`'s read-then-decide window in `derive_fact_records` before either has written its
checkpoint. This is not a new risk this design introduces — `kb_produce_facts.py`'s own batch job
has the identical race across two concurrently-run `main()` invocations today, undocumented and
untested. `f3_adversarial_verify` should either (a) confirm the existing `registry_head` +
append-only-registry-line shape already tolerates two racing writers converging to one chain
(likely, since the registry is append-only and `generate_manifest.py` compacts after the fact),
or (b) record it as an accepted limitation with a test proving the failure mode is "two
`supersedes`-less rows, resolved as `conflicted` by `facts.fact_state` on the next read" rather
than data loss — either outcome is a finding `f3` must produce, not one `f1` may assume.

---

## 11. Rejected alternatives — summary table

| Alternative | Rejected because |
|---|---|
| Hook inside `workflow_runner.run_workflow` (mirroring `emit_self`) | Would add an unpinned tier-1→tier-2 import (`control.fact_ingestion`) — the exact edge Debt-2's dependency inversion was written to prevent (§1) |
| Reuse `_derive_workflow_facts` (the full corpus ladder) verbatim | O(corpus) I/O per completion; fragments corpus-wide `policy_facts`/`spec_status` across per-cell scope if `repository_id=cell_scope(...)` (§2) |
| Skip `workflow_facts_v1`, emit only I2 (`attempt`/`job`) facts | `route_next_job_v1` is contracted against workflow-scope health/status/budget predicates, not raw per-phase facts (§2) |
| `repository_id` = flat `REPOSITORY_ID` ("agentic-dynamics") | Proven invisible to that same run's own `--cap-shadow`/`--cap-snapshot`/`control_route` queries via `scope_visible`'s ancestor-prefix matching (§3) |
| `FINOPS_DISABLE_FACT_EMIT=1` (opt-out styled as opt-in "=1") | Reads backwards at the call site for no consistency gain; the feature's default-ON posture is already the deliberate exception in this flag family (§4) |
| Inject a fact-emit `Callable` through `run_workflow()`'s parameters (mirroring `router`) | No per-phase behavior to inject — fires once, post-run, over an already-persisted immutable artifact; adds a parameter/test surface for no behavioral gain (§1) |
