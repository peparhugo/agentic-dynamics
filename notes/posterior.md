# Posterior — Pattern surface adoption (Loose-ends L20)

*Posterior phase of `workflows/repository/pattern_surface_adoption.yaml`. Diff of
`notes/plan.md` against the tree at the execute commit, plus the update set. No code changed.*

**Provenance of the inputs (the `note-provenance` lesson, applied to this run).**
`git log -1 -- notes/world_model.md` and `... notes/plan.md` both resolve to
`7dc82f971` — this run's own prior commit — so the two documents diffed here are this run's
reality, not a prior task's. `notes/deviations.md` does not exist for this run: the execute
phase did not write one, and `pattern_surface_adoption` has no deviations step (see V1).

**Acceptance replay (re-run at posterior time, this checkout).** Every command the plan's
`## Acceptance` names exits 0:

| check | command | result |
|---|---|---|
| new guards | `pytest tests/test_world_model_loop_spec.py tests/test_kb_read.py -q` | 6 passed |
| lint | `ruff check scripts/kb_read.py tests/test_kb_read.py tests/test_world_model_loop_spec.py` | clean |
| surface drift | `python3 scripts/_gen_instructions.py --check` | `surfaces OK — 40 files` |
| loop spec loads | `load_spec(workflows/repository/world_model_loop.yaml)` | `world_model_loop` |
| declined guards untouched | `pytest tests/test_world_model_gates.py -q` | 17 passed |
| degraded read (manual) | `python3 scripts/kb_read.py --query test --contains --scope agentic-dynamics` | exit 0, `mode=unavailable` |

All ten files the plan's `## Files` table names are in the execute commit (`9a14d3f6d`); the
three notes are in the prior commit (`7dc82f971`). No planned artifact is missing.

---

## Violations

Where the plan met reality — including promises the tree does not keep.

**V1 — The generalization did not land: `explicit-empty-note` is a spec-local edit, not a
convention.** The plan (#5) and the world model (Gap #4) both frame the fix as a generalizable
"a fixed-path artifact is never left stale" convention. What landed is one spec's prompt line
(`workflows/repository/world_model_loop.yaml:75-79`) plus one `requires_files` entry
(`:98`). `grep -rln "deviations.md" workflows/repository/*.yaml` matches **only** that file, so
the defect class is contained for this loop and unaddressed everywhere else. The plan chose
"spec step" (a legitimate reviewed decision), but the generality claim is unrealized — the next
spec that carries a conditional fixed-path note gets no protection. **No surface corrected
this.**

**V2 — The `.gitignore` tension materialized exactly as Gaps #8 predicted, and the plan
assigned it no surface.** `.gitignore:116` ignores `notes/` (L11: "a loop run's branch now
carries its CODE/TESTS, not its notes"). Reality: the prior phase force-added all three notes
(`7dc82f971` carries `notes/plan.md`, `notes/sources.jsonl`, `notes/world_model.md`), the
execute commit carried none, and this posterior must force-add a fourth (`git add -f
notes/posterior.md`). The branch now carries both its code/tests **and** its notes, contradicting
the documented convention. The plan listed no artifact for this and left it to the posterior;
this posterior records it as a **pending P0-adjacent decision**, not an implemented fix (see
UPDATES → candidates).

**V3 — `scripts/kb_read.py` landed a different shape than the plan specified.** The plan (#7,
Artifact A) named an inline `registry_ok = REGISTRY.is_file()` local resolved once in `main`.
What landed is a module-level helper `registry_present()` (`scripts/kb_read.py:97`) called from
both `_contains` (`:107`) and `main` (`:200`). Behaviour is acceptable — the positive control and
the manual replay both pass — but the plan's "resolve it once" instruction was not followed; the
file stats the path twice on the fallback path. A shape violation, not an acceptance violation.

**V4 — The write side is prompt-only; the enforcement fires after execute spend.** The plan
(#5) calls the posterior `requires_files` entry "the enforcement". It is a real gate
(`_missing_required_files`, `workflow_runner.py:865`), but it refuses the **posterior**, i.e.
after the execute phase's tokens are already spent. Nothing prevents execute from skipping the
write; it only punishes the skip downstream. The plan's framing is honest about the mechanism
yet overstates it as prevention — the write instruction itself remains unenforced.

**V5 — Cited line ranges drifted from the tree and were not corrected.** The world model cites
`_emit_research_report` at `workflow_runner.py:1946`; the tree has it at `:1933`.
`_finding_emit_enabled` is at `:1826` (world model says `:1826-1846`, plan says `:1819-1839`;
the tighter range is correct). The plan reconciled the test-file lines (`:534-581`,
`:554-559` — both exact) but left the source ranges approximate.

---

## Unknowns

What we did not know at prior-time, and still cannot settle from this tree.

**U1 — The seven records' `kb:` evidence is unresolved in this checkout.** There is no
`experiments/results/registry_index.jsonl` and `experiments/results/kb/` is empty. Every record
cites `kb:dc1d8eb1…`, `kb:09c552b9…`, `kb:2c5995a7…` as its evidence; none was independently
read. This adoption inherits the records' own provenance without re-verifying it — a reviewer
should treat the `support` counts as claimed, not confirmed here.

**U2 — The loop's refusal path has not been observed end-to-end.** `test_world_model_loop_spec.py`
asserts the YAML contract (`requires_files` contains `notes/deviations.md`, the prompt carries
the tokens); `_missing_required_files` itself is exercised on synthetic specs in
`tests/test_world_model_gates.py`. No test runs `world_model_loop` with the note absent and
observes the refusal. The gate is real; its wiring to *this* spec is asserted only structurally.

**U3 — Self-referential validation is impossible in the editing run.** The execute phase edited
the spec that governs future world-model runs; that spec was already loaded for this run. The
change is therefore unvalidated by the run that made it — **the next loop run is the first test**
of the explicit-empty write + the provenance check + the new `requires_files`. Until that run,
the fix is a candidate, not a measured outcome.

**U4 — The provenance check is prompt-only and unenforced.** `git log -1 -- notes/` lives in the
posterior prompt (`world_model_loop.yaml:102-105`) and the run-workflow skill; nothing detects a
posterior that skips it. Unlike V4's `requires_files`, there is no artifact gate for a provenance
read. A future run honoring it is hoped for, not proven.

**U5 — Scope of the explicit-empty defect class is unmeasured.** `deviations.md` appears in only
one spec, but a spec could carry an analogous conditional fixed-path artifact under another name
(e.g. a conditional `notes/findings.md`); no scan was run for that shape.

**U6 — `kb_read`'s mode collapses if `_ranked` ever returns `[]` instead of `None`.** The guard
distinguishes "unavailable" from "zero hits" by `_ranked` returning `None`
(`scripts/kb_read.py:200`). If a future `_ranked` returned an empty list on service failure, the
mode would read `ranked, hits=0` and mask the degradation the fix exists to surface. No test pins
the `None` contract directly.

**U7 — `compounding-emission-leak`'s decline rests on an unguarded measurement convention.** The
decline is sound (its containment *is* the landed regression; the registry row is written by the
out-of-process `kb-registry-v1` consumer, not by `emit_phase_finding`,
`knowledge_ingestion.py:649`), but the residual diagnostic — "measure leaks by raw artifact +
registry-row counts, never manifest entities" — is recorded nowhere a future reader would find
it. If a leak recurs, that insight must be re-derived.

---

## UPDATES

### Per-record disposition (final)

| # | record | disposition | landed <where> / declined <why> |
|---|---|---|---|
| 1 | `emit-seam-guard` | **declined — already landed** | Guard `tests/test_world_model_gates.py:29-53`; regression `:534-581`. Re-implementing is the spec's named failure mode. |
| 2 | `pin-production-precedence` | **declined — already landed** | Positive control `tests/test_world_model_gates.py:554-559`; production rule untouched (`workflow_runner.py:1826`). |
| 3 | `stale-conditional-note` | **declined — duplicate** | Same defect, same evidence set as `explicit-empty-note`; the explicit-empty write removes the stale slot. Its distinct angle is `note-provenance` (#6). |
| 4 | `compounding-emission-leak` | **declined — containment = landed regression** | The leak's containment is `test_no_emission_escapes_the_module_under_the_suite_disarm` (`:534-581`); the residual is a measurement footnote with no decision surface (U7). |
| 5 | `explicit-empty-note` | **landed** | `workflows/repository/world_model_loop.yaml:75-79` (unconditional write, `no deviations`) + `:98` (`requires_files` gains `notes/deviations.md`); procedure in `agent_config/skills/run-workflow.md`; guard `tests/test_world_model_loop_spec.py`. |
| 6 | `note-provenance` | **landed** | `workflows/repository/world_model_loop.yaml:102-105` (posterior `git log -1 -- notes/<file>`); procedure in `agent_config/skills/run-workflow.md`; guard `tests/test_world_model_loop_spec.py`. |
| 7 | `kb-read-degradation-crash` | **landed** | `scripts/kb_read.py:97,107,200` (degrade + explicit `unavailable` mode); guard `tests/test_kb_read.py` (positive control included); procedure in `agent_config/skills/knowledge-reader.md`. |

No record was re-landed; no record was silently dropped. The four declines are grounded in the
tree (exact landed lines / overlapping evidence), not in preference.

### Skill / pattern candidates this adoption itself surfaced

These are **candidates for the next prior phase**, not landed here (a phase does not promote its
own pattern to an agent-facing surface — the loop's own `p2_mint` rule: a candidate lands in the
KB, promotion is a reviewed commit).

1. **`skill/workflow-tests/spec-contract-pinning`** — a workflow spec's load-bearing prompt
   contract should be pinned by a test asserting short, stable tokens (a path, a command, a
   phrase), never prose. `tests/test_world_model_loop_spec.py` is a second instance of the shape
   `tests/test_cap_2a_spec.py` established; the reuse is now evidenced (support ≥ 2), so the
   pattern is worth minting.
2. **`pattern/pattern-adoption/decline-already-landed`** — when adopting minted records: first
   locate each claimed enforcement in the tree; a record whose guard already exists is
   **declined with the exact lines**, never re-implemented; two records describing one defect
   from two sides are collapsed, never double-counted. This run is the worked example
   (4 declines, 3 landings, all grounded).
3. **`pattern/world-model-loop/self-referential-adoption`** — an edit to the spec that governs
   the loop cannot be validated by the run that makes it; the next run is the first test, and the
   editing run must record the change as unvalidated (this run's absent `notes/deviations.md` is
   the instance, V1/U3).
4. **Pending convention decision (not a pattern): the notes/.gitignore tension (V2).** Either the
   loop prompts drop their "commit the notes" instruction (letting L11 stand), or `.gitignore`
   carves the loop's `notes/` out. Recorded here; it needs a P0-reviewed change, not a phase
   side effect.

### What the next loop's prior phase should carry

- Re-read this file's U3: the explicit-empty + provenance contract is unvalidated until a
  world-model run completes under it.
- Treat the `kb:` ids in the seven records as **claimed, not confirmed** (U1) — the durable KB is
  absent in this checkout.
- If the notes-commit convention (V2) is changed, update the loop prompts and `.gitignore` in one
  wave and regenerate surfaces in the same commit.
