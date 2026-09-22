# Adversarial Review - Pattern Surface Adoption

## Scope and Recomputed Checks

This review checked the three workflow commits (`7dc82f971`, `9a14d3f6d`, and
`b450c831`) against the current implementation, rather than treating the plan or posterior as
proof. The claimed acceptance commands do pass in this checkout:

```text
python3 -m pytest tests/test_world_model_loop_spec.py tests/test_kb_read.py -q -p no:cacheprovider
6 passed

ruff check scripts/kb_read.py tests/test_kb_read.py tests/test_world_model_loop_spec.py
All checks passed!

python3 scripts/_gen_instructions.py --check
surfaces OK - 40 generated files match agent_config/

python3 -m pytest tests/test_world_model_gates.py -q -p no:cacheprovider
17 passed
```

I also replayed the manual degraded-read check. It exits zero and reports
`mode=unavailable`, which is the claimed repaired behavior for an absent registry.

The passed checks do not establish the central workflow behavior. In particular,
`tests/test_world_model_loop_spec.py` checks YAML membership and prompt substrings only; it does
not execute the real loop with a missing or inherited deviations note.

## Findings

### 1. The explicit-empty and provenance landings are not enforced

`workflows/repository/world_model_loop.yaml:98` makes the posterior require that
`notes/deviations.md` exists. The runner implementation at
`src/agentic_dynamics/runtime/workflow_runner.py:865-883` performs only
`Path.is_file()`. It neither verifies that execute wrote the file nor checks its commit,
contents, timestamp, or run identity. A stale deviations note therefore satisfies the purported
gate exactly as well as a fresh explicit-empty note.

The commit convention makes the provenance instruction internally inconsistent. `notes/` is
ignored, and the runner stages phases with `git add -A` at
`workflow_runner.py:983-989`; ignored notes are not staged. In this checkout,
`git ls-files -v notes` lists only the four force-added review notes and not
`notes/deviations.md`; `git log -1 -- notes/deviations.md` resolves to the old
`f173d1c6e` hygiene commit; and `git check-ignore -v notes/deviations.md` identifies
`.gitignore:116:notes/`. A normal execute can write the new note into the worktree, but its
ordinary phase commit cannot make that write the note's provenance. The posterior instruction at
`world_model_loop.yaml:102-105` therefore either sees an old tracked history entry or no
history, not evidence that the current execute phase wrote the ignored file.

This is more than the posterior's acknowledged "after execute spend" limitation. The stated
read-side enforcement does not distinguish fresh from stale data at all, and the stated
provenance check has no coherent success condition under the documented ignored-notes convention.

Falsifier: seed a worktree with an old `notes/deviations.md`, make execute skip the write, and
run the posterior. The current `requires_files` gate passes because the file exists. A real
acceptance test must assert refusal or a named stale verdict for that case. A separate test must
run execute through the normal commit path and prove the provenance contract it asks posterior to
use, or the spec must adopt an explicitly different freshness witness.

### 2. `note-provenance` remains a procedure, not a guarded workflow property

The only automated assertion for this landing is
`tests/test_world_model_loop_spec.py:53-56`, which searches the posterior prompt for
`git log -1 -- notes/`. It cannot observe whether the agent ran that command, compared its result
with this run's commits, or named stale material as unknown. The skill repeats the same
instruction at `agent_config/skills/run-workflow.md:206-210`; it adds no verifier.

The plan correctly says a rule nothing checks is not enforcement, but calls this prompt-only
check "landed" and describes the `requires_files` test as the enforcement. Those are different
properties: file presence cannot prove provenance.

Falsifier: a posterior agent can omit `git log`, cite an inherited note as current, write a
well-formed posterior, and pass every current test and gate. A verifier must consume a durable
freshness witness, not merely pin the command text.

### 3. The `compounding-emission-leak` decline is too broad for the evidence

`tests/test_world_model_gates.py:29-53` and `:534-581` enforce containment for this one test
module and its `t_wml` fixture. They do not enforce the record's general claim that *any* test
module opting into `rag.emit_self` or `rag.emit_report` has both containment layers. Nor do they
preserve the record's diagnostic rule to measure a recurrence by raw artifact and registry-row
counts. The posterior itself records that this residual is unguarded (U7), but still calls the
decline "enforcement already landed."

The local regression is valuable and the decline is valid only if narrowed to the existing
`tests/test_world_model_gates.py` leak. It is not evidence that the suite-wide pattern has been
adopted or that the compounding observation has no decision surface.

Falsifier: add a second workflow test module with an emission-enabled fixture and no local stub
or `FINOPS_RESULTS_DIR` redirect. The existing 17-test gate can remain green while that module
writes to the live durable tree. A suite-wide static guard, or a deliberately scoped rule that
documents this as a module-local pattern, would resolve the mismatch.

### 4. The KB mode wording overclaims for explicit `--contains`

The crash repair itself is supported: `_contains` returns an empty list when the registry is
absent (`scripts/kb_read.py:115-126`), and the reproduced command now reports unavailable instead
of raising. However, `main()` sets `ranked = None if args.contains else _ranked(args)` at `:197`.
For an explicit `--contains` call, ranked retrieval is deliberately not attempted, yet an absent
registry is reported as `unavailable` with the human explanation that "neither ranked retrieval
nor the deterministic scan could answer" (`:226-230`). In that invocation, neither-path failure
was not established; one path was skipped by request.

Falsifier: make ranked retrieval available, invoke `--contains` with the registry absent, and
the command still reports `unavailable` without probing the available ranked path. The CLI should
say that the requested deterministic scan is unavailable, or reserve "both" for the automatic
fallback path.

## Claim/Falsifier Matrix

| Major claim | What is actually checked | Falsifier |
|---|---|---|
| Explicit-empty note prevents stale input | Posterior file existence only | Pre-existing stale file lets posterior start after execute skips its write. |
| Provenance check protects the posterior | Prompt contains one command substring | Agent skips the command or gets ignored-file history; all gates still pass. |
| Emission leak is fully covered, so decline is complete | One module's emit seam and paths | A different emission-enabled module leaks while this module's regression passes. |
| KB reports both paths unavailable | Absent-registry `--contains` path | Ranked may be available but is skipped under `--contains`; the claim is still printed. |
| Pin-production-precedence is landed | One positive control for explicit emit_self | A distinct precedence rule can regress without this test changing; the test pins only this relation. |

## FINDING

The capability repair for an absent KB registry is real, and the existing emit-seam regression is
real for its module. The principal "landed" workflow claims are overstated: explicit-empty and
provenance are prompt/file-presence conventions, not freshness enforcement, and the ignored-notes
commit path makes their asserted provenance witness unavailable in normal execution. Treat the
two note patterns and the broad compounding-leak decline as unresolved until an end-to-end stale
note test and a durable freshness witness are implemented.
