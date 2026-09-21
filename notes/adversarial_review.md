# Adversarial Review - Close the live-KB test-emission leak

## Scope And Method

This independent review read `notes/world_model.md`, `notes/plan.md`,
`notes/sources.jsonl`, `notes/deviations.md`, `notes/posterior.md`, and
`notes/minted.md`, then inspected commits `b00947b12`, `6985163dd`,
`84a4a56ac`, and `179a28a3b`. It reran the stated test and lint checks. The
scoped KB reader was attempted as required, but ranked retrieval failed because
`agentic_dynamics.knowledge.neo4j_vectors` is unavailable and the deterministic
fallback raised `FileNotFoundError` because this checkout lacks
`experiments/results/registry_index.jsonl`. That is an environment limitation,
not evidence for or against the fix.

## Provenance Audit

`notes/sources.jsonl` contains 15 entries: five KB records, five current source
files, the pre-execute version of the test module, and five archived workflow
reports. Every listed SHA-256 recomputes to the stated value. In particular:

- The five current source-file hashes match the working tree.
- `git show b00947b12:tests/test_world_model_gates.py` hashes to the recorded
  pre-execute test-file digest, so the claimed prior-time file is reproducible.
- The five `/app/experiments/results/...` report digests and five KB-record
  digests match their entries.

No world-model gap is marked external, and `sources.jsonl` contains no external
source entry. The fetched-source requirement is therefore vacuously satisfied;
there is no missing external fetch finding.

The current run's phase-report artifacts used by the posterior
(`014ffbeb...`, `09c552b9...`, and `dc1d8eb...`) are real files under
`/app/experiments/results/kb/`, but they are not listed in `sources.jsonl`.
That does not make the posterior's cited text false, but it weakens the stated
provenance contract: a reader cannot verify those artifacts from the run's
declared source manifest alone. Future posterior claims relying on newly
created KB records should add their record IDs and digests to the manifest.

## Verified Claims

### The execute change is appropriately narrow

`git diff --stat b00947b12 6985163dd` reports one changed path,
`tests/test_world_model_gates.py`, with 101 insertions. The diff adds:

- a module-local autouse fixture that patches the lazy
  `knowledge_ingestion.emit_phase_finding` lookup and redirects
  `FINOPS_RESULTS_DIR` to a temporary directory;
- a regression with a positive control showing that the fixture spec's explicit
  `emit_self: true` still outranks `FINOPS_EMIT_SELF=0`;
- before/after snapshots of the live KB and `t_wml` report paths.

The production precedence remains unchanged. `_finding_emit_enabled` still
returns an explicit `emit_self` value before consulting the process disarm
(`workflow_runner.py:1819-1839`), while both output paths honor the correctly
spelled `FINOPS_RESULTS_DIR` (`knowledge_ingestion.py:421-433` and
`workflow_runner.py:1933-1946`).

Falsifier: changing `_finding_emit_enabled` so the environment disarm wins
would fail the regression's positive control. Removing the fixture's
`emit_phase_finding` patch while retaining its recording list would leave that
list empty and fail the interception assertion. Removing the results redirect
would allow `_emit_research_report`'s direct `write_text` to target the live
report tree and fail the path-set assertion.

### The reported test and count results reproduce

- `python3 -m pytest tests/test_world_model_gates.py -q`: 14 passed.
- `python3 -m pytest tests/test_knowledge_ingestion.py -q`: 49 passed.
- `ruff check tests/test_world_model_gates.py`: all checks passed.
- The checkout's `experiments/results` path-set digest was identical before and
  after the module suite.
- The durable registry has 14 rows containing `self-test_artifact_gate`.
- The durable artifact tree has 9 files whose `repository_id` is
  `self-test_artifact_gate_refuses_wit0` and 9 whose `repository_id` is
  `self-test_artifact_gate_passes_when0`: 18 raw leaked phase-finding artifacts
  in total. A broad text match yields 21 files because it also selects derived
  pattern artifacts; repository-id filtering is required for the claimed raw
  count.

Falsifier: a future raw-artifact recount that includes derived pattern records
would produce 21 rather than 18 and would invalidate the claim if it continued
to call the result a raw phase-finding count. The count must retain the
`repository_id` filter.

## Findings

### High: "byte-for-byte unchanged" is unsupported

`notes/posterior.md:15`, `:34`, `:40`, and the A1 candidate state that the live
tree was "byte-for-byte unchanged." The actual regression at
`tests/test_world_model_gates.py:522-532` snapshots only a set of path strings,
and its final assertion at `:580-581` compares only those sets. The posterior's
probe table likewise describes a sorted file-path listing, not file contents or
digests.

The verified claim is narrower: **no path was added or removed beneath the two
observed live subtrees during the suite run**. This is sufficient to demonstrate
the report-file containment that the regression was designed to test, but it
does not detect an in-place overwrite of an existing file. The distinction
matters because the world model itself identifies idempotent durable artifact
paths as part of the problem space.

Recommendation: replace every "byte-for-byte unchanged" statement with
"path set unchanged" unless the test records a mapping of relative path to
SHA-256 (or equivalent content digest). Do not mint a measured byte-invariance
finding from a path-only observation.

Falsifier: pre-create a file in either observed live subtree and arrange a test
write to overwrite that exact path without creating a new path. The current
test would pass its containment assertion while the bytes changed.

### Medium: the plan and world model use an incorrect environment-variable name

The world model and plan repeatedly spell the output variable
`FINFOPS_RESULTS_DIR` (for example `world_model.md:26`, `:72`, `:91`, and
`plan.md:39-42`, `:105`, `:119-124`). The implementation and the landed fixture
use `FINOPS_RESULTS_DIR`, without the extra `F`:

- `knowledge_ingestion.py:431`
- `workflow_runner.py:1937`
- `tests/test_world_model_gates.py:52`

Consequently, the world model's statement that a `FINFOPS_RESULTS_DIR` redirect
produced clean containment is not supported by the implementation it cites.
The actual execute fix is correct, but the analysis's operational recommendation
is misleading and could cause a future manual verification to leak into the
default results tree.

Recommendation: correct the notes and all future run instructions to
`FINOPS_RESULTS_DIR`. Treat earlier shell-prefix observations using the typo as
invalid unless an independent mechanism demonstrates that the intended variable
was set in-process.

Falsifier: run the real emit path with only `FINFOPS_RESULTS_DIR` set. The code
falls back to its default checkout results path because neither output writer
reads that misspelled variable.

### Medium: the stale-note prescription exceeds the single observed incident

The posterior accurately establishes that this run inherited an Item-4
`notes/deviations.md`: its last modifying commit is `3689fb233`, while the
current execute commit `6985163dd` did not touch it. The current execute phase
report also says "No deviations occurred." That supports an observation about a
fixed shared path in this run.

It does not establish the universal imperative in A2/C1 that execute **must**
write an explicit-empty deviations record. The workflow currently requires a
record only where reality differs (`world_model_loop.yaml:75-76`), and the
evidence is one run with two stale files created by the same missing-reset
mechanism, not two independent occurrences. An explicit-empty record is a
reasonable proposal, but it is a policy choice, not a measured conclusion.

Recommendation: label explicit-empty notes as `[P]` or `[H]`, and compare it
against two alternatives before changing the workflow: clear all per-run note
slots during initialization, or namespace notes by run ID. The posterior's
stronger, evidence-backed recommendation is provenance validation before a
reader relies on a fixed-path note.

Falsifier: execute the same task twice in a shared worktree with a genuinely
current no-deviation note. A note that was not changed by the second run is
stale relative to that run but not necessarily "about another task," disproving
the posterior's broader C4 wording.

### Low: the closure statement needs a scope qualifier

The test-only fix demonstrably contains this module's real workflow emissions
under its autouse fixture. It does not prove that every future test module with
an emitting fixture is protected, and it does not remove historic artifacts
from `/app`. Therefore "the live-KB test-emission leak is CLOSED" is acceptable
only when qualified as **the leak from `tests/test_world_model_gates.py` in the
current suite shape**. The posterior often includes that module qualifier, but
its verdict and minted reusable pattern occasionally read as global closure.

Falsifier: add another test module that supplies `rag.emit_self: true` and runs
a committing workflow without a local guard. The current change will not affect
that module because the fixture is intentionally module-local.

## FINDING

The execute commit is a sound, narrowly scoped test-seam repair: its 14/49 test
passes, lint result, source checksums, and raw-leak recount reproduce. However,
the posterior overclaims byte-level live-tree invariance from a path-set check,
and its workflow recommendation elevates one stale shared-note incident into a
mandatory universal rule without comparative evidence. The immediate correction
is to report path-set containment precisely, use `FINOPS_RESULTS_DIR` (not the
misspelled `FINFOPS_RESULTS_DIR`), and classify explicit-empty note creation as
a proposed policy pending a design decision.
