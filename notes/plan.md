# Plan — Pattern surface adoption

*Execute phase follows this file. The task: disposition the seven `pattern/v1` records minted by
the world-model loop's promoted run (`1217356c4`) onto their correct surfaces — enforcement → a
guard test; procedure → a skill/command or a spec step; convention → a rule or spec step;
capability → a tool/CLI; delegated role → an agent — or **decline with a reason**. Two records
already landed as guard tests in the same promoted change (`tests/test_world_model_gates.py`):
repeating that work is the failure mode.*

Every disposition below names its surface, the **exact artifact**, and the **acceptance check**,
or a **DECLINE** with the evidence that makes the decline honest. Prompt-based procedures are
enforced by an assertion on the **spec file** (`tests/test_world_model_loop_spec.py`); a rule that
nothing checks is not enforcement, so where a guard is claimed, a test asserts it.

## Disposition summary

| # | record | disposition | surface |
|---|---|---|---|
| 1 | `emit-seam-guard` | **DECLINE** — already landed (fixture `:29-53` + regression `:534-581`) | — |
| 2 | `pin-production-precedence` | **DECLINE** — already landed (positive control `:554-559`) | — |
| 3 | `stale-conditional-note` | **DECLINE** — duplicate of `explicit-empty-note` (same defect, same evidence) | — |
| 4 | `compounding-emission-leak` | **DECLINE** — enforcement already landed (containment regression); measurement footnote has no decision surface | — |
| 5 | `explicit-empty-note` | **LAND** | spec step (`world_model_loop.yaml`) + procedure (`agent_config/skills/run-workflow.md`) |
| 6 | `note-provenance` | **LAND** | spec step (`world_model_loop.yaml`) + procedure (`agent_config/skills/run-workflow.md`) |
| 7 | `kb-read-degradation-crash` | **LAND** | capability fix (`scripts/kb_read.py`) + guard test (`tests/test_kb_read.py`) + skill (`agent_config/skills/knowledge-reader.md`) |

Three land; four decline. The four declines are grounded in the tree (the exact landed lines, the
exact duplicate evidence), not in preference.

---

## Declines (with evidence)

### 1. `emit-seam-guard` — DECLINE (already landed)

The record's own verification names `tests/test_world_model_gates.py:29-53` (guard) + `:534`
(regression) at `commit 6985163dd`; both are present in the current tree and were added by the
promoted commit (`git show 1217356c4 -- tests/test_world_model_gates.py`). The guard is the
`@pytest.fixture(autouse=True) _stub_emit_write_path` (`:29-53`); the regression is
`test_no_emission_escapes_the_module_under_the_suite_disarm` (`:534-581`), which asserts
interception (`assert _stub_emit_write_path`, `:576`) AND live-tree path-set invariance
(`before == after`, `:580-581`). Re-writing it is the spec's named failure mode. No new artifact.

### 2. `pin-production-precedence` — DECLINE (already landed)

The record's verification is the positive control at `tests/test_world_model_gates.py:558-561`.
In the current tree that is `:554-559`:
`assert os.environ.get("FINOPS_EMIT_SELF") == "0"` then
`assert wr._finding_emit_enabled(resolved, {}) is True`. Production precedence is untouched and
pinned (`_finding_emit_enabled`, `workflow_runner.py:1826-1846`, returns the explicit opt-in before
the env default). The principle is already enforced by the assertion the record cites. No new
artifact.

### 3. `stale-conditional-note` — DECLINE (duplicate of `explicit-empty-note`)

The two records describe one defect from two sides, over the same file, the same population, and
an evidence set that overlaps almost entirely (`kb:09c552b9…`, `commit:3689fb233`,
`file:notes/deviations.md`, `file:notes/posterior.md`). The `explicit-empty-note` fix — execute
ALWAYS writes `notes/deviations.md`, explicit-empty when nothing deviated — removes the stale slot
that `stale-conditional-note` measures. Landing both against two artifacts would double-count one
change. The record's distinct contribution (do not *trust* an inherited fixed-path note without
checking) is `note-provenance`, which lands (#6). **Resolved by #5 + #6.**

### 4. `compounding-emission-leak` — DECLINE (enforcement already landed)

The record's actionable claim is "the leak is real and unbounded — contain it", and that
containment IS the landed regression `test_no_emission_escapes_the_module_under_the_suite_disarm`
(`:534-581`), which holds the live `experiments/results/kb` + `experiments/results/workflows/t_wml`
path sets invariant across a run. The residual content is a **measurement footnote** — measure a
leak by raw artifact + registry-row counts, never manifest entities (compaction hides growth) —
which adds no decision surface: it is a diagnostic that only matters if a leak exists, and after
the guard none does. A registry-count assertion added to the module test would be vacuous: the
registry row for a phase finding is appended by the out-of-process `kb-registry-v1` consumer, not
by `emit_phase_finding` (`knowledge_ingestion.py:649-692` writes the artifact and publishes only),
so an in-process run cannot produce one. No new artifact.

---

## Landings (exact artifacts + acceptance)

### 5. `explicit-empty-note` — spec step + procedure

**Artifact A — `workflows/repository/world_model_loop.yaml` (spec step; the enforcement):**

1. **execute prompt** — replace the conditional write with an unconditional one plus an
   explicit-empty branch. Required contract tokens (see Tests):
   * the phrase `notes/deviations.md` (already present), and
   * an unconditional-write instruction containing `no deviations` (the explicit-empty record).
2. **posterior `requires_files`** — add `notes/deviations.md`:
   `requires_files: [notes/world_model.md, notes/plan.md, notes/deviations.md]`.
   This turns the convention into a **gate**: if execute skipped the file, the posterior REFUSES
   before spend (the `_missing_required_files` gate, `workflow_runner.py:865-883`, reads the
   clone-aware worktree) instead of silently trusting a stale document.

**Artifact B — `agent_config/skills/run-workflow.md` (procedure):** a new subsection "Run notes in
world-model loops" documenting (a) the fixed-path rule (always write the conditional note,
explicit-empty when the condition is false) and (b) that generated surfaces are untouched. The
skill is a rendered surface: after the edit run `python3 scripts/_gen_instructions.py`.

**Acceptance:** `tests/test_world_model_loop_spec.py` asserts the posterior's `requires_files`
contains `notes/deviations.md` and that the execute prompt carries the explicit-empty instruction;
`python3 scripts/_gen_instructions.py --check` exits 0.

### 6. `note-provenance` — spec step + procedure

**Artifact A — `workflows/repository/world_model_loop.yaml` (spec step):** add the provenance
check to the **posterior** prompt (the measured failing reader): before trusting any of
`notes/world_model.md`, `notes/plan.md`, `notes/deviations.md`, run `git log -1 -- notes/<file>`;
a note whose last commit is not a commit of THIS run is stale and must be named as an unknown, not
treated as this run's reality. Required contract token: `git log -1 -- notes/`.

**Artifact B — `agent_config/skills/run-workflow.md`:** the "Run notes in world-model loops"
subsection (#5) also carries the provenance check (`git log -1 -- notes/<file>`), so the procedure
travels with the skill, not only the one spec.

**Acceptance:** `tests/test_world_model_loop_spec.py` asserts the posterior prompt contains
`git log -1 -- notes/`; the generated-surface check stays green.

### 7. `kb-read-degradation-crash` — capability fix + guard test + skill

**Artifact A — `scripts/kb_read.py` (capability fix; never a traceback):**

* `_contains` (`:93-137`) must treat an **absent** registry as zero hits, not an exception:
  guard the `REGISTRY.read_text(...)` at `:99` (return `[]` when `not REGISTRY.is_file()`, and
  catch `OSError` around the read) — the function is also called directly by tests.
* `main` (`:164-169`) must record **which mode answered**. Resolve `registry_ok = REGISTRY.is_file()`
  once; when `_ranked` returns `None` and the registry is absent, the mode is an explicit
  `unavailable` (both paths failed) rather than a misleading `contains`; when the registry is
  present, mode stays `contains`. The `--json` `mode` field and the human line both carry it, and
  the human path prints the degraded reason. An absent registry must read as "degraded", never as
  "no matches".

**Artifact B — `tests/test_kb_read.py` (guard test; new file):**

* `test_contains_returns_empty_when_registry_absent` — monkeypatch `kb_read.REGISTRY` to a
  nonexistent path; `_contains` returns `[]` and does not raise.
* `test_main_reports_unavailable_when_the_registry_is_absent` — monkeypatch `kb_read.REGISTRY` and
  `sys.argv` to `--contains`; assert `main()` returns 0, the reported mode is `unavailable`, and
  no traceback is emitted (capsys).
* `test_contains_finds_a_row_against_a_tmp_registry` — **positive control**: write a minimal
  `registry_index.jsonl` + one `kb/<id>.json` into a tmp dir and monkeypatch `REGISTRY`/`KB_DIR`;
  assert the row is found (proves the test is not vacuous — it fails if `_contains` is stubbed to
  return `[]` unconditionally).

**Artifact C — `agent_config/skills/knowledge-reader.md`:** document the three read modes (ranked /
`--contains` / both-failed) and the rule "record which mode answered"; regenerate surfaces.

**Acceptance:** `python3 -m pytest tests/test_kb_read.py -q` green — including the positive control;
`ruff check scripts/kb_read.py tests/test_kb_read.py`; the generated-surface check green.

---

## Files

| file | change | why |
|---|---|---|
| `notes/world_model.md` | written (this phase) | the prior artifact |
| `notes/plan.md` | written (this phase) | this plan |
| `notes/sources.jsonl` | written (this phase) | per-source provenance |
| `workflows/repository/world_model_loop.yaml` | edit execute prompt (explicit-empty); add `notes/deviations.md` to posterior `requires_files`; add the provenance check to the posterior prompt | lands #5 + #6 |
| `scripts/kb_read.py` | guard `_contains` against an absent registry; `main` records `unavailable`/`contains`/`ranked` | lands #7 (capability) |
| `tests/test_world_model_loop_spec.py` | **new** — loop-spec contract assertions | enforces #5 + #6 |
| `tests/test_kb_read.py` | **new** — degradation guard + positive control | enforces #7 |
| `agent_config/skills/run-workflow.md` | new "Run notes in world-model loops" subsection | procedure for #5 + #6 |
| `agent_config/skills/knowledge-reader.md` | document the three read modes | procedure for #7 |
| `.opencode/skills/run-workflow/SKILL.md`, `.opencode/skills/knowledge-reader/SKILL.md` (+ `.claude/` mirrors) | regenerated | never hand-edit generated surfaces |

Explicitly NOT touched: `tests/test_world_model_gates.py` (already landed — #1/#2);
`agent_config/rules.md` (no always-on rule is warranted — the loop convention is enforced by the
spec gate, and no rule surface would check it); `.opencode/tools/` (no new capability is needed —
the `knowledge read` CLI already exists and is what the fix repairs).

## Tests

The execute phase creates both files; the `g_test_gate` reads this section and runs the existing
`tests/` paths it names.

- `tests/test_world_model_loop_spec.py`
- `tests/test_kb_read.py`

Both name real `tests/` paths so the plan-driven gate targets them (the parser
`_test_targets_from_plan`, `workflow_runner.py:1450-1475`, keeps only existing paths).

## Acceptance

Run from the worktree root; every command is expected to exit 0:

```bash
# 1. the new guards (the plan-driven test gate runs exactly these)
python3 -m pytest tests/test_world_model_loop_spec.py tests/test_kb_read.py -q -p no:cacheprovider

# 2. the changed CLI is lint-clean
ruff check scripts/kb_read.py tests/test_kb_read.py tests/test_world_model_loop_spec.py

# 3. generated surfaces match their agent_config/ source (no hand-edit drift)
python3 scripts/_gen_instructions.py --check

# 4. the loop spec still loads and passes the compiler's requires/produces gate
python3 -c "from pathlib import Path; from agentic_dynamics.experiment.experiment_spec import load_spec; s=load_spec(Path('workflows/repository/world_model_loop.yaml')); print(s.name)"
```

Per-landing acceptance, restated:

* **#5** — `tests/test_world_model_loop_spec.py::test_posterior_requires_the_deviations_note`
  (posterior `requires_files` contains `notes/deviations.md`) and
  `::test_execute_prompt_orders_an_explicit_empty_deviations_note` (execute prompt contains
  `no deviations` and `notes/deviations.md`).
* **#6** — `::test_posterior_prompt_requires_note_provenance` (posterior prompt contains
  `git log -1 -- notes/`).
* **#7** — the three tests in `tests/test_kb_read.py` (positive control included), and a manual
  sanity run of the reproduced crash command, which must now exit 0 with mode `unavailable`
  instead of a traceback:
  `python3 scripts/kb_read.py --query test --contains --scope agentic-dynamics`.
* **#1/#2/#3/#4 (declines)** — no artifact; the acceptance is that the decline reasons above
  name the exact landed lines / duplicate evidence, and that `tests/test_world_model_gates.py`
  still passes unchanged (the landed guards are not disturbed).

## Risks

- **Prompt-string tests are brittle.** `tests/test_world_model_loop_spec.py` asserts stable tokens
  (`notes/deviations.md`, `no deviations`, `git log -1 -- notes/`), not prose. Keep the tokens
  verbatim in the spec or the test fails. Mitigation: choose short, unambiguous tokens and state
  them in the prompt as the required instruction.
- **The prior prompt vs L11 (`.gitignore notes/`).** The prior prompt orders "Commit all three
  files" while `notes/` is ignored (`.gitignore:107-116`). Forcing the notes into the commit
  re-tracks process records the convention deliberately untracked. This phase obeys the explicit
  instruction but records the gap (world model §Gaps #8); the posterior should decide whether the
  loop spec drops the note-commit requirement or the convention carves this spec out.
- **Editing a shared loop spec affects in-flight/next runs.** `world_model_loop.yaml` is the live
  loop contract; the change is additive (a requires_files entry + prompt lines) and must not alter
  phase names, kinds, scopes, or order. Re-load the spec after editing (acceptance command 4).
- **Generated-surface drift.** `run-workflow.md` and `knowledge-reader.md` are sources for
  `.opencode/`/`.claude/`; editing them without regenerating reddens `--check`. Run
  `python3 scripts/_gen_instructions.py` in the same commit.
- **The kb_read fix could mask a real error.** Guarding `_contains` must distinguish an absent
  registry (degrade) from a corrupt one (still report). The fix returns `[]` only for a missing
  file/`OSError`; a JSON parse error per row is already skipped. The positive-control test keeps the
  happy path honest.
- **Gate skip risk.** If the execute phase does not create the two test files, `_test_targets_from_plan`
  drops them and the `g_test_gate` SKIPS explicitly (recorded, no fabricated verdict). The plan
  names them as required deliverables so that is a visible failure, not a silent pass.
- **Declines could be judged lazy.** Each decline cites the exact landed lines / overlapping
  evidence; the adversarial phase is instructed to attack lazy declines. If it falsifies one, the
  record is re-landed with an artifact, not argued.
