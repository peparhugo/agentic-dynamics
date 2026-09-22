# World model — Pattern surface adoption

*Prior phase of the `pattern_surface_adoption` loop (`workflows/repository/pattern_surface_adoption.yaml`).
Read-only: no production or test code touched. Every claim below is grounded in a file, a git
blob, or a command output — never in memory.*

The seven minted records are read from git history (`git show 1217356c4:notes/skills/<slug>.json`);
the already-landed guards are read from the working tree. The live durable KB is **absent in this
checkout** — there is no `experiments/results/registry_index.jsonl`, `experiments/results/kb/` is
empty, and `scripts/kb_read.py` cannot answer (see the reproduced crash below). So the `kb:` ids
that the records cite as `evidence` are **not** independently resolved here: they are carried by
the record blobs and are named as the records' own provenance, not re-verified by this phase.

Command outputs this document rests on (all run at prior time in this checkout):

```
$ ls experiments/results/registry_index.jsonl
ls: cannot access 'experiments/results/registry_index.jsonl': No such file or directory
$ ls experiments/results/kb/ | wc -l
0
$ python3 scripts/kb_read.py --query "test" --contains --scope agentic-dynamics
Traceback (most recent call last):
  ...
  File "/repo/scripts/kb_read.py", line 99, in _contains
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
FileNotFoundError: [Errno 2] No such file or directory: '/repo/experiments/results/registry_index.jsonl'
$ python3 scripts/_gen_instructions.py --check
surfaces OK — 40 generated files match agent_config/          # exit 0
$ git rev-parse HEAD ; git symbolic-ref -q HEAD || echo "(detached)"
3ebe15e77d1cf5918be59ab6b17d945e6f2c1a40
(detached)
```

## Problem

The world-model loop's promoted run (`run-79fbc7f23d61`, candidate `400f50da2`, promoted to `main`
as `1217356c4`) **minted seven `pattern/v1` records** and recorded their JSON under
`notes/skills/`. Minting a pattern is the producer half; *adopting* it is a separate, reviewed
decision: a pattern that claims an enforcement must be pinned by a guard test, a claim that
describes a procedure must land in a skill/command or a spec step, a convention in a rule, a
capability in a tool/CLI, a delegated role in an agent spec — or be **declined with a reason**
(already covered, or too thin). `pattern_surface_adoption` is that review.

The loop names the failure mode explicitly (its `domain_context`):

> TWO already landed as guard TESTS in that same promoted change (the emit-seam guard + its
> containment regression) — read `tests/test_world_model_gates.py` first: **repeating landed work
> is the failure mode here.**

So the problem is not "implement seven things"; it is "disposition seven records honestly, and
prove — from the tree, not from the record's own prose — which are already enforced". A record
whose claimed guard already exists must be **declined**, not re-implemented; a record whose fix is
already the landed fix must be declined; two records that describe one defect from two sides must
not be double-counted.

## What Exists

### 1. The seven minted records (git blobs at `1217356c4:notes/skills/*.json`)

| slug | subject | claim (compressed) | support | cited evidence (as carried by the record) |
|---|---|---|---|---|
| `compounding-emission-leak` | `pattern/test-suite/compounding-emission-leak` | Test-emission leaks are **cumulative/unbounded**: the phase-finding idempotence key includes the commit hash (`revision`), and each pytest run commits a fresh throwaway hash via `_init_repo`, so every run derives a new `knowledge_id`. Durable tree measured: 18 `self-test_artifact_gate_*` raw artifacts + 14 registry rows; entity-level manifest compaction **hides** the growth — measure leaks by raw artifact + registry-row counts, never manifest entities. | 18 | `kb:dc1d8eb1…`, `kb:09c552b9…`; `artifact:self-test_artifact_gate_refuses_wit0@9`; `registry-row:self-test_artifact_gate@14` |
| `emit-seam-guard` | `skill/workflow-tests/emit-seam-guard` | A test module whose fixture spec opts into `rag.emit_self`/`rag.emit_report` must carry a module-local autouse guard that stubs `knowledge_ingestion.emit_phase_finding` **and** redirects `FINOPS_RESULTS_DIR`; its regression must assert BOTH interception (non-vacuous) AND live-tree invariance (path sets, not counts). The suite-level `FINOPS_EMIT_SELF=0` does not protect it (explicit opt-in outranks env, `workflow_runner.py:1819-1839`); a stub alone misses `_emit_research_report`'s direct `write_text` (`workflow_runner.py:1946`). | 1 | `commit:6985163dd`, `test:tests/test_world_model_gates.py:29-53`, `test:…:534`, `src:workflow_runner.py:1819-1839` |
| `explicit-empty-note` | `pattern/world-model-loop/explicit-empty-note` | A phase that writes a **conditional** note must write an explicit-empty record when the condition is false (or the plan's single-path rule must carve `notes/*.md` out): a stale conditional note is worse than none. The execute prompt orders `notes/deviations.md` (`world_model_loop.yaml:75-76`) but a no-deviation run omits the file, leaving the prior run's document in the slot the posterior trusts. | 2 | `kb:dc1d8eb1…`, `kb:2c5995a7…`, `kb:09c552b9…`, `file:notes/plan.md`, `commit:3689fb233` |
| `kb-read-degradation-crash` | `pattern/kb-read/degradation-crash` | `scripts/kb_read.py` turns an unavailable ranked path into a **hard crash** rather than an empty result: with no services `_ranked` returns `None`, the `_contains` fallback reads `registry_index.jsonl` at `kb_read.py:99` and raises `FileNotFoundError` when the registry is absent. A reader cannot distinguish "registry absent" from "no matches"; KB-read availability is environment-dependent, so each run must probe it and record which mode answered (ranked / `--contains` / both failed). | 1 | `kb:dc1d8eb1…`, `script:scripts/kb_read.py:99`, `traceback:FileNotFoundError:/repo/experiments/results/registry_index.jsonl` |
| `note-provenance` | `skill/world-model-loop/note-provenance` | Before trusting a loop note, check its **last commit**: a note not changed in the current run is stale and about another task. Measured 2026-09-21: `notes/deviations.md` last changed by `3689fb233` and `notes/posterior.md` by `077ad4837` while the run's own commits were `b00947b12`/`6985163dd` — the posterior's ordered inputs were two documents about a different task. `git log -1 -- notes/<file>` per inherited note is the cheap check; an untouched note must be named as an unknown, not trusted. | 2 | `commit:3689fb233`, `commit:077ad4837`, `commit:b00947b12`, `commit:6985163dd`, `file:notes/deviations.md`, `file:notes/posterior.md` |
| `pin-production-precedence` | `skill/workflow-tests/pin-production-precedence` | Never change production precedence to satisfy a test defect: where a production rule is intentional and pinned (the explicit `rag_params['emit_self']` opt-in outranking the `FINOPS_EMIT_SELF=0` disarm), the test must pin it with a **positive-control** assertion, not weaken it. The rule stayed untouched (`workflow_runner.py:1819-1839`); the test asserts the gate OPENS (`tests/test_world_model_gates.py:558-561`). | 1 | `commit:6985163dd`, `test:tests/test_world_model_gates.py:558-561`, `src:workflow_runner.py:1819-1839` |
| `stale-conditional-note` | `pattern/world-model-loop/stale-conditional-note` | A loop's **fixed-path conditional** note is never reset between runs: `notes/deviations.md` is ordered by execute (`:75-76`) and read by posterior (`:99`), but a no-deviation run omits it, leaving the previous task's document. Measured: the execute report says "No deviations occurred" (`6985163dd`) yet the deviations file present is the Item-4 document from `3689fb233`, and `notes/posterior.md` was likewise the Item-4 posterior (`077ad4837`). | 2 | `kb:dc1d8eb1…`, `kb:09c552b9…`, `kb:2c5995a7…`, `commit:3689fb233`, `commit:077ad4837`, `file:notes/deviations.md`, `file:notes/posterior.md` |

### 2. The two already-landed guards (working tree, `tests/test_world_model_gates.py`)

Both halves of the emit-seam fix are present in the current tree and were added by the promoted
commit itself (`git show 1217356c4 -- tests/test_world_model_gates.py`):

* **The module-local guard** — `_stub_emit_write_path`, an `@pytest.fixture(autouse=True)` at
  `tests/test_world_model_gates.py:29-53`. It (1) `monkeypatch.setattr(ki, "emit_phase_finding",
  ...)` and (2) points `FINOPS_RESULTS_DIR` at a tmp tree, and returns the recording list.
* **The containment regression** — `test_no_emission_escapes_the_module_under_the_suite_disarm`,
  `tests/test_world_model_gates.py:534-581`. It asserts the positive control (the suite disarm
  `FINOPS_EMIT_SELF == "0"` is set YET `_finding_emit_enabled(resolved, {}) is True`, `:556-559`),
  non-vacuity (`assert _stub_emit_write_path`, `:576`), and live-tree invariance by **path sets**
  (`before == after`, `:580-581`).

Two records therefore point at assertions that already exist:
`emit-seam-guard` (the fixture + the regression) and `pin-production-precedence` (the
positive-control lines `:554-559`). The spec's "TWO already landed" is these two.

### 3. Candidate surfaces that exist

| surface | location | state |
|---|---|---|
| guard tests | `tests/test_*.py`; runner gates `requires_files`/`requires_content`/`tests_from_plan` at `workflow_runner.py:865-907`, `:1450-1475` | exists |
| skill (generated) | `agent_config/skills/<name>.md` → `.opencode/skills/<name>/SKILL.md` + `.claude/skills/<name>/SKILL.md` (`scripts/_gen_instructions.py:275-292`, `:351-353`) | 8 skills; `--check` green (40 files) |
| agent (generated) | `agent_config/agents/<name>.md` | 4 agents |
| rule (generated root) | `agent_config/rules.md` → `AGENTS.md` / `CLAUDE.md` | exists |
| spec step | `workflows/repository/<name>.yaml` phase prompts + `requires_files`/`requires_content` | the loop spec is here |
| tool adapter (hand-authored) | `.opencode/tools/*.ts` | 27 tools; `kb_read` has NO tool adapter (agents shell out) |

### 4. The loop's current contract (`workflows/repository/world_model_loop.yaml`)

* `execute` prompt (`:72-78`): records deviations in `notes/deviations.md` **only when they occur**
  — "Where reality differs … do not silently adapt: record it" — with no explicit-empty branch.
* `posterior` `requires_files: [notes/world_model.md, notes/plan.md]` (`:95`) — **not**
  `notes/deviations.md`.
* `posterior` prompt (`:99`): "Read `notes/world_model.md`, `notes/plan.md`, `notes/deviations.md`,
  and the run's commits" — it trusts the fixed paths with no provenance check.
* `notes/` is **gitignored** (`.gitignore:107-116`, L11): notes are process records that travel via
  the phase reports + KB; a run's branch carries its code/tests, not its notes. The gates read the
  **worktree** paths, so ignoring affects only what a commit carries.

## Gaps

Per record, the gap between "the claim" and "what the tree actually enforces today".

1. **`compounding-emission-leak` — no new enforcement gap; the diagnostic is already the landed
   regression.** The record's actionable content ("contain the leak") IS
   `test_no_emission_escapes_the_module_under_the_suite_disarm` (`:534-581`), which snapshots the
   live `experiments/results/kb` and `experiments/results/workflows/t_wml` path sets before/after a
   run and asserts no escape. The record's residual — the *measurement convention* (raw artifacts +
   registry rows, never manifest entities) — is a diagnostic footnote, not a control: (a) it only
   matters if a leak exists, and the guard's job is that none does; (b) the registry row for a
   phase finding is written by the out-of-process `kb-registry-v1` consumer, not by
   `emit_phase_finding` (`knowledge_ingestion.py:649-692` writes the artifact + publishes; it does
   not append a registry row), so an in-process test cannot produce a registry row and an
   assertion on one would be vacuous. No decision surface is added by re-landing it.

2. **`emit-seam-guard` — already covered, verbatim.** The guard (`:29-53`) and its regression
   (`:534-581`) are in the tree. Re-implementing is the named failure mode. **Decline.**

3. **`pin-production-precedence` — already covered, verbatim.** The positive control
   (`_finding_emit_enabled(resolved, {}) is True` while `FINOPS_EMIT_SELF == "0"`, `:556-559`) is
   in the same regression, and `_finding_emit_enabled` (`workflow_runner.py:1826-1846`) still
   returns the explicit opt-in before the env. The production rule is pinned. **Decline.**

4. **`explicit-empty-note` — real gap.** The execute prompt has no explicit-empty branch and the
   posterior gate does not require `notes/deviations.md`, so a no-deviation run can leave the
   prior task's document in the slot the posterior is instructed to trust. The fix is a **spec
   step** (write-side prompt + read-side `requires_files`), generalizable as a "fixed-path artifact
   is never left stale" convention.

5. **`stale-conditional-note` — the same defect seen from the reading side.** Its evidence set is a
   subset of `explicit-empty-note`'s (`kb:09c552b9…`, `commit:3689fb233`, `file:notes/deviations.md`,
   `file:notes/posterior.md`), its population and conditions are identical, and the single
   explicit-empty fix (always write `notes/deviations.md`) removes the stale slot. Listing it as a
   second landing would double-count one artifact. Its distinct angle — "check provenance before
   trusting" — is exactly `note-provenance`. **Decline as covered by `explicit-empty-note` (+ the
   provenance check).**

6. **`note-provenance` — real gap.** No phase in the loop checks whether an inherited fixed-path
   note was written by THIS run; the posterior prompt trusts the paths. The cheap check
   (`git log -1 -- notes/<file>`) is named by the record and is absent from the spec. Fix:
   posterior prompt step + the run-workflow skill.

7. **`kb-read-degradation-crash` — real gap, reproduced above.** `scripts/kb_read.py:99` reads
   `REGISTRY` unguarded; the registry is absent in this checkout and the verb crashes with a
   traceback instead of reporting a degraded mode. `_ranked` already degrades to `None` and prints
   the fallback reason, but `main` (`:164-169`) has only two modes (`ranked`/`contains`) and cannot
   express "both failed", and the `knowledge-reader` skill claims the fallback works. The fix is a
   **capability fix + guard test** (CLI), plus documenting the modes in the skill.

8. **The commit convention is itself a gap (not one of the seven records, but forced by this
   phase).** The prior prompt orders "Commit all three files", while L11 (`.gitignore:107-116`)
   makes `notes/` ignored, so a plain `git add` stages nothing and a forced add re-tracks process
   records the convention deliberately untracks. This phase obeys the explicit instruction (commit
   the three files) and records the tension here: the loop's prior prompt should drop the commit
   requirement for notes (or the convention should carve this spec out). Left as a finding for the
   posterior.

9. **No test currently pins the loop spec's own contract.** Nothing loads
   `workflows/repository/world_model_loop.yaml` and asserts the posterior gate / prompt contents;
   the runner gates are tested on synthetic specs
   (`tests/test_world_model_gates.py`), not on the loop spec. New acceptance checks belong in a new
   `tests/test_world_model_loop_spec.py`.

## Sources

KB records: **none resolvable in this checkout** — `experiments/results/registry_index.jsonl` is
absent and `experiments/results/kb/` is empty, so the `kb:` ids carried by the records
(`kb:dc1d8eb1…`, `kb:09c552b9…`, `kb:2c5995a7…`) were not independently read. They are named in
the table above as the records' own evidence, not as sources this phase resolved.

Files (+sha256, at prior time). The seven minted records were read from git, at
`1217356c4:notes/skills/<slug>.json`:

- `notes/skills/compounding-emission-leak.json` @ `1217356c4` — `7c182640de6d043d37ed9f0295af16eefe3f95a8b15b22960668476a66562429`
- `notes/skills/emit-seam-guard.json` @ `1217356c4` — `6422e70f46348dadd8abcfe3033c3a1642072de06470dbdb7a4eeecf1015b23a`
- `notes/skills/explicit-empty-note.json` @ `1217356c4` — `9f9c09c27796f3d2aac3c4bafb285bb53e8cc5467e6674e88ff53b3f9ac22462`
- `notes/skills/kb-read-degradation-crash.json` @ `1217356c4` — `4cb1cd169bac91f05a18d1a756a664a3b7756be0c60b2c9c6ebf4ba4d8f8a5e1`
- `notes/skills/note-provenance.json` @ `1217356c4` — `a8fad6401a0d2952aa03bd1e5f03ae5ef262713e6c624fd7214c59e0970dcc69`
- `notes/skills/pin-production-precedence.json` @ `1217356c4` — `c8490fd0977f2da9d9117b4453de28d49102615468d61e1b9641bf849a43708b`
- `notes/skills/stale-conditional-note.json` @ `1217356c4` — `728422cffa723cbcff85ce154efb6acf40addfb35ad2d8406f2387a030ae0f95`

- `tests/test_world_model_gates.py` — `28ea3f7bc4042ba515ff619d22c9c50d7f83f38a42d8e45ac252bfaa31449838`
- `workflows/repository/pattern_surface_adoption.yaml` — `badba92487e1eef2c331532098ad2eaf93c65fcfd91f69ba98518352596d561d`
- `workflows/repository/world_model_loop.yaml` — `c49a4dd5119ea47cec665715d94a7aa15b99832c8e480c76715e7d3cce0b3f4a`
- `scripts/kb_read.py` — `516b463e791dfef48ec09fb01d834515391470261fd0a370d09c2c85a433cedd`
- `agent_config/rules.md` — `54ffa49313400fa7cf6b8b5c008e042ad402493fa5aa430d30eb56826b22abd1`
- `agent_config/skills/run-workflow.md` — `0194f2c552fd8c26a42031eb4961bed748aea65b66fabb55eeab84576887334b`
- `agent_config/skills/knowledge-reader.md` — `6d48fc532b530fa83fd57b48f60540dc6a1068b1d27ed0fd85a1baabe792b3fc`
- `tests/conftest.py` — `0282bbe2b1c3ce3f5dea7604ea8fdbce83e0f49523625a90319ad08cb690e41e`
- `src/agentic_dynamics/runtime/workflow_runner.py` — `414d2a7a5801fa5e6cf7327f37eefab9c2be10c05b75777b569658f99e4c5d99`
- `src/agentic_dynamics/knowledge/knowledge_ingestion.py` — `d3d70b2f98968935b88202197c53b7bf434430b78355e2827ac18ea754381a58`
- `docs/architecture/current/cap_pattern_minting.md` — `bfdb3d4172c968c76fda77f2d29a0eb420643816b6296d99031e21ca362c6a1b`
- `docs/designs/proposed/world_model_loop.md` — `028e9f21e798849802d6cee4a933d6df27358631fd26809681b538520ba1ac38`
- `docs/reviews/loose_ends_register.md` — `cd94741f580a559cfe16aa5554488f3bdc931781135f9a31c16a5eb7dba678a0`
- `.gitignore` — `20a90e8500ea3be47baf52496cd30c4a152127ef5ec6f4b9e22941ba26d983a9`

No external URL was fetched — no fact required the open web.
