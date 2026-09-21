# Posterior — Close the live-KB test-emission leak

*Final phase of the world-model loop. Read-only with respect to production code. Every claim
below is grounded in a file, a commit, a KB record, or a command output — never in memory. The
diff is against `notes/world_model.md` (the prior) and `notes/plan.md`; the loop's declared
execute record is `notes/deviations.md`, which — as this posterior establishes — is **stale and
about a different task**.*

## Verdict

The world model was **accurate to the line and to the byte**. Every mechanism it named was
confirmed, every line reference held, every source sha256 matched, and the two-layer fix it
planned is exactly the fix the execute commit landed (`6985163dd`, one file, 101 insertions).
The plan's acceptance criteria all hold: `14 passed`, `ruff check` clean, and the live durable
tree is byte-for-byte unchanged after the module runs.

The consequential finding is **not** in the fix — it is in the loop's own bookkeeping. The
execute phase concluded "No deviations occurred" (its own emitted report says so), but it did
**not** write `notes/deviations.md`; the file the posterior prompt orders read is the
**Item-4 stale-next-action document** from a previous loop (`077ad4837`/`3689fb233`). The loop's
fixed-path conditional note files are never reset between runs, so a no-deviation run leaves the
previous task's document in the slot the next phase is told to trust. `notes/posterior.md` is
itself stale for the same reason. The model did not carry this hazard at prior time.

---

## Verification performed (all read-only; commands in the probe log)

| check | command | result |
|---|---|---|
| module suite | `python3 -m pytest tests/test_world_model_gates.py -q` | **14 passed** (13 + the regression) |
| cross-module safety | `python3 -m pytest tests/test_knowledge_ingestion.py -q` | **49 passed** (the guard is module-local) |
| lint | `ruff check tests/test_world_model_gates.py` | `All checks passed!` |
| live-tree invariance | `find experiments/results -type f \| sort` before/after the module run | **identical** (52 files both times); `experiments/results/kb/` and `.../workflows/t_wml/` do not exist — no record escaped |
| diff scope | `git show --stat 6985163dd` | one path, `tests/test_world_model_gates.py`, **+101** |
| production untouched | `git diff b00947b12 6985163dd` | only the test file changed |
| provenance | `sha256sum` vs `notes/sources.jsonl` | all six file hashes and the prior-time test-file hash (`fb2eee5f…`) match exactly |

The requested property — *running the module writes no new records under the real
`experiments/results/kb/`* — is proven both by the before/after path-set identity above and by
the regression's own two assertions (gate opened **and** live tree unchanged).

---

## 1. VIOLATIONS — where reality differed from the world model

### V1. The loop's own note contract leaves a stale `notes/deviations.md` in the posterior's path

This is the one material difference between the model and reality, and it is a **contradiction
inside the loop**, not an execute error.

- The workflow's execute prompt orders a deviation record:
  `workflows/repository/world_model_loop.yaml:75-76` — *"Where reality differs from the plan or
  the world model, do not silently adapt: record it in `notes/deviations.md`."*
- The workflow's posterior prompt orders the posterior to read it:
  `workflows/repository/world_model_loop.yaml:99` — *"Read `notes/world_model.md`,
  `notes/plan.md`, `notes/deviations.md`, …"*.
- The current plan forbids writing it: `notes/plan.md:29` — *"No other file. `git diff --stat`
  must show a single path."* (and `:24` — "the only file changed"), even while `notes/plan.md:3`
  says *"Deviations go in `notes/deviations.md`."*
- Reality: the execute commit touched **only** `tests/test_world_model_gates.py`; no
  `notes/deviations.md` was written or committed. Its own emitted report states the conclusion
  explicitly — *"No deviations occurred;"* — in
  `/app/experiments/results/kb/09c552b95ab6ae51237848d841cc1ccda4549e36967777e30cdfbaebbd35f05d.json`
  (`phase-report/v1`). The assertion exists, but in the KB, not in the slot the posterior reads.
- Therefore `notes/deviations.md` (last changed by `3689fb233`, the **Item 4** execute) and
  `notes/posterior.md` (last changed by `077ad4837`, the **Item 4** posterior) are documents
  about a *different task*, sitting in the fixed paths this loop reads. The prior phase correctly
  overwrote `world_model.md` / `plan.md` / `sources.jsonl`; it left the two conditional notes.

The world model and plan did not anticipate this (neither mentions `posterior.md` or the
never-reset note slot); the plan even encoded the constraint that *causes* it. The posterior
therefore had to establish provenance before trusting any note — which is exactly the discipline
this section records for the next model.

### V2. The leak is cumulative and unbounded — larger than the "4 records" it was described as

The world model measured "**10 artifacts under `experiments/results/kb/` + 6 report files per
run**" and the task was framed as "4 `self-test_artifact_gate_*` records." Reality in the durable
tree:

```
$ python3 -  # classify /app/experiments/results/kb/*.json by repository_id
count: 18
Counter({'self-test_artifact_gate_refuses_wit0': 9, 'self-test_artifact_gate_passes_when0': 9})
$ grep -c self-test_artifact_gate /app/experiments/results/registry_index.jsonl
14
```

The leak is **not idempotent across runs**: the idempotence key that derives a phase finding
includes `revision` = the phase's commit hash, and every test run creates a *fresh* throwaway git
commit (`_init_repo`), so each run derives a *new* `knowledge_id` and writes a *new* artifact
under the same `self-` entity. The manifest's latest-per-entity compaction hides this, but the raw
append-only store grows without bound. The world model's per-run measurement was right; the
property it implies — the incident compounds on every suite run — was not named.

### V3. The world model's "four leaking tests" and its line-level mechanism map were exact

Recorded as a *positive* violation so the next model does not over-correct: the four leaking
tests are `test_artifact_gate_refuses_without_the_declared_plan` (`:116`),
`test_artifact_gate_passes_when_the_prior_wrote_the_plan` (`:135`),
`test_shape_gate_refuses_an_unsectioned_plan` (`:197`), and
`test_shape_gate_passes_when_the_plan_carries_its_sections` (`:217`) — the only four that run a
committing workflow against `SPEC` (which opts in at `:78-79`) without stubbing the seam. The
world model's cited lines all resolve today: `_finding_emit_enabled`
(`src/agentic_dynamics/runtime/workflow_runner.py:1819-1839`), the emit block (`:5448-5463`),
`_emit_self_finding` (`:1842`), `_emit_research_report` (`:1914`, direct report write at
`:1946`), `emit_phase_finding`
(`src/agentic_dynamics/knowledge/knowledge_ingestion.py:625-668`, artifact write `:661-663`),
`_artifact_path` (`:421-433`), the suite disarm (`tests/conftest.py:15`), and the dead
`_disarm_finding_emit` (`tests/conftest.py:251`). The prior-time file hash
`fb2eee5f9a7e0b61c89955d85ddc97a54c5942897f3e466f0ad2bb72f2489377` reproduces exactly. This
contrasts with the *previous* loop, whose execute reformat invalidated all its line references
(prior `notes/posterior.md` V2/V3) — here nothing drifted because the diff was scoped to one file.

---

## 2. UNKNOWNS DISCOVERED — what the next model must carry

1. **The stale-note hazard is structural, not a one-off.** Fixed-path notes that a phase writes
   *conditionally* (`notes/deviations.md`) have no "explicit empty" reset. A no-deviation run
   leaves the previous run's document where the next phase is instructed to read it, and a
   posterior that trusts it reasons about the wrong task. The absence of a file is a signal; the
   presence of a stale file is a trap. (V1.)
2. **A test-emission leak compounds.** Because the idempotence key carries the commit and the
   fixture commits fresh hashes, every run is a new record set; "10 per run" implies unbounded
   raw-store growth that entity-level compaction conceals. Measure leaks by raw artifact/registry
   counts, not by manifest entities. (V2.)
3. **`kb_read.py`'s degradation path is a crash, not an empty.** With no services, `_ranked`
   returns `None`; the fallback `_contains` then does `REGISTRY.read_text(...)`
   (`scripts/kb_read.py:99`) and raises `FileNotFoundError` when
   `experiments/results/registry_index.jsonl` is absent (reproduced here). A reader sees a
   traceback, not the zero-hit guidance line, and cannot distinguish "registry absent" from "no
   matches." The stale Item-4 posterior (its V4) claims ranked retrieval worked; in *this*
   environment both ranked and `--contains` fail. KB-read availability is environment-dependent —
   probe it, and record which mode ran. (The world model's Gaps item "Blind KB in this checkout"
   was right; this sharpens *how* it fails.)
4. **The loop's legitimate emissions share the leak's destination.** This run's own `prior` and
   `execute` phases emitted successfully into the durable tree — 2 `phase-report/v1` records
   (`014ffbeb…` prior, `09c552b9…` execute) and 2 report files
   (`20260921211003716868_prior.md`, `20260921211222465715_execute.md`) under
   `/app/experiments/results/`. So a before/after "did the tree change?" check alone cannot
   separate a legitimate loop emission from a test leak; the guard must live at the test seam
   (as it now does). This also supersedes the Item-4 posterior's V5 ("the loop's outputs are
   git-only") for the fleet shape, where `FINFOPS_RESULTS_DIR` points at the durable checkout.
5. **The regression's two assertions have asymmetric scope.** The interception assertion
   (`_stub_emit_write_path` non-empty) is what proves the stub; the containment assertion
   (`after == before`) is only falsifiable through `_emit_research_report`'s *direct report-file
   write*, because `_artifact_path` also honors `FINFOPS_RESULTS_DIR` — removing the stub while
   keeping the redirect leaves the live tree untouched but empties the recorded list, so the
   test still fails (correctly). The fix is sound; the plan's falsifier table overstates the
   symmetry (it implies each layer independently defends the live artifact).
6. **A module-local guard is the right seam.** The three existing emit-aware tests
   (`:152`, `:236`, `:487`) override the autouse fixture *after* it runs and still exercise the
   real `_emit_research_report`; the knowledge-ingestion suite is unaffected (49 passed). This
   settles the design question the previous loop left open.

---

## 3. UPDATES — the concrete update set

### A. KB findings to emit (scope `agentic-dynamics`, existing producer path)

- **A1 — the verification outcome [M].** *"The live-KB test-emission leak from
  `tests/test_world_model_gates.py` is CLOSED at the test seam, production precedence untouched.
  A module-local autouse fixture (`tests/test_world_model_gates.py:29-53`) stubs
  `knowledge_ingestion.emit_phase_finding` and redirects `FINFOPS_RESULTS_DIR`; a regression
  (`:534`) asserts interception (non-vacuous) AND live-tree invariance. `14 passed`; the checkout
  `experiments/results/` path set is byte-identical before/after; commit `6985163dd`, one file.
  `_finding_emit_enabled` (workflow_runner.py:1819-1839) still returns the explicit opt-in before
  the `FINFOPS_EMIT_SELF=0` disarm."* Evidence: the commit, the before/after `find` sets, the
  module/KB test runs.
- **A2 — the stale-note hazard [H].** *"A fixed-path conditional note (`notes/deviations.md`)
  is never reset between world-model loops; a no-deviation execute leaves the previous task's
  document in the slot the posterior prompt orders it to read (world_model_loop.yaml:75-76 vs
  :99). Execute must write an explicit-empty deviations record. Measured: execute's own emitted
  report says 'No deviations occurred' (kb:09c552b9…), yet the file present is the Item-4
  document (`3689fb233`)."*
- **A3 — the leak compounds [H].** *"Test-emission leaks are cumulative: a phase finding's
  idempotence key includes the commit hash, and each test run commits a fresh hash, so leaked
  artifacts are new records every run (measured: 18 `self-test_artifact_gate_*` artifacts, 9 per
  scope, in the durable tree; 14 registry rows). Entity-level manifest compaction conceals the
  growth — count raw artifacts/registry rows."*
- **A4 — kb_read degradation [H].** *"`scripts/kb_read.py` turns an unavailable ranked path
  into a hard crash: `_ranked` returns None, the fallback `_contains` reads
  `registry_index.jsonl:99` and raises FileNotFoundError when it is absent. Readers cannot tell
  'no registry' from 'no hits.'"*

Emit A1 through `emit_phase_finding`; A2–A4 are convention/knowledge candidates for the loop's
`p2_mint` step. Do not hand-write records.

### B. Conventions to record

- **C1 (explicit empty over stale).** A phase that writes a conditional note file must write an
  explicit-empty record when the condition is false, *or* the plan's single-path rule must carve
  `notes/*.md` out. A stale conditional note is worse than no note.
- **C2 (the emit-seam test guard).** Any test module whose fixture spec opts into
  `rag.emit_self`/`rag.emit_report` must carry a module-local autouse guard that (i) stubs
  `knowledge_ingestion.emit_phase_finding` and (ii) redirects `FINFOPS_RESULTS_DIR`; its
  regression must assert both interception (non-vacuous) and live-tree invariance (path sets,
  never counts).
- **C3 (never change production precedence for a test defect).** Pin the intentional precedence
  with a positive-control assertion in the test (as `:558-561` does) rather than weakening it.
- **C4 (note provenance).** Before trusting a loop note, check its last commit. A note not
  changed in this run is stale and about another task.

### C. Skills / knowledge to create or amend

- **`run-workflow` skill:** add the emit-seam test-guard pattern (C2) — the module-local autouse
  fixture plus the regression's two-part assertion — as the standard fix for "fixture spec opts
  into emission."
- **`world_model_loop` design doc (`docs/designs/proposed/world_model_loop.md`) and the spec
  (`workflows/repository/world_model_loop.yaml`):** state that execute writes an explicit
  `notes/deviations.md` even when empty (or that the loop clears prior-run notes first), and that
  the posterior verifies each note's provenance commit. Consider namespacing run notes by
  run/task (the doc's own v1.3 collision finding already anticipates this).

### D. What should change in the next loop's prior phase

1. **Audit the fixed notes it inherits.** Before writing `## Files`, `git log -1 -- notes/` each
   note the loop will read; name stale ones as unknowns. The current prior did not, and the
   posterior inherited two Item-4 documents.
2. **Measure the leak by raw counts, not manifest entities.** Baseline `experiments/results/kb/`
   artifact count and `registry_index.jsonl` row count, and state the compounding property.
3. **Probe the KB and record the mode.** `kb_read` availability is environment-dependent; record
   whether ranked or `--contains` answered, or that both failed (as here).
4. **Scope the plan's single-path rule explicitly.** If `notes/deviations.md` is in play, say so
   in `## Files`; do not let "one file" silently contradict the workflow's execute contract.

---

## 4. Probe log (what was read, and why)

| probe | why | result |
|---|---|---|
| `notes/world_model.md`, `notes/plan.md` | the model and plan under test | mechanism accurate to the line; note-contract hazard absent |
| `notes/deviations.md`, `notes/posterior.md`, `git log -1 -- notes/…` | the loop's declared execute record | both stale, from Item 4 (`3689fb233`/`077ad4837`) |
| `git show --stat 6985163dd` / `git diff b00947b12 6985163dd` | what execute actually did | one file, +101, test seam only |
| `workflow_runner.py:1819-1839,1842,1914,1946,5448-5463` | the emit chain | exact match to the world model |
| `knowledge_ingestion.py:421-433,625-668` | the durable write seam | `_artifact_path` honors `FINFOPS_RESULTS_DIR`; write at `:661-663` |
| `tests/conftest.py:15,251` | suite disarm / dead helper | active disarm at `:15`; `_disarm_finding_emit` unused at `:251` |
| `tests/test_world_model_gates.py` (read + run) | the fix and its falsifiability | 14 passed; guard at `:29-53`, regression at `:534` |
| `find experiments/results -type f \| sort` (before/after) | live-tree invariance | identical 52-file sets; no `kb/`, no `t_wml/` |
| `pytest tests/test_knowledge_ingestion.py -q` | cross-module safety | 49 passed |
| `ruff check tests/test_world_model_gates.py` | lint acceptance | clean |
| `sha256sum` vs `notes/sources.jsonl` | provenance fidelity | all hashes match, incl. prior-time test file |
| `/app/experiments/results/kb/*.json` classification | scale/age of the leak | 18 leaked artifacts (9 per scope), 14 registry rows |
| `/app/experiments/results/kb/014ffbeb…,09c552b9…` | did this run emit? | yes — prior + execute reports; execute says "No deviations occurred" |
| `scripts/kb_read.py:80-205` + run | KB availability | ranked unavailable (`neo4j_vectors`), `--contains` crashes (no `registry_index.jsonl`) |
