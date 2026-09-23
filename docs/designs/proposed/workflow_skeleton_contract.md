---
status: proposed
---

# The canonical workflow skeleton — and where each loop concern is enforced

**Origin:** the controller's scan request, 2026-09-21 — *"how do we enforce what a prior run
looks like, where is the research, where is the skill creation, what sources do we use, what
does an execution workflow contain, where is the adversarial check? a lot of the things we
have worked on are getting lost."* This maps each concern to its EXISTING precedent across the
repo's ~230 workflow specs (so nothing already built has to be re-invented), and records the
world-model loop's conformance.

## The skeleton (the `cap_*` family's established shape)

```
p0_pin_*          — the written PRIOR: pin the spec / mandate / preregistration / sources
<build slices>    — the work, decomposed (one concern per phase, evidence per phase)
gN_adversarial    — scope: adversarial_readonly + run_model (a DIFFERENT model) — the
                    adversarial check; the default last review before the gate
gN_test_gate      — kind: test — independent verification by the test runner
(checkpoint)      — the phase key `checkpoint: true` → the run STOPS for an operator approval
```

Evidence: `cap_runner_hardening`, `control_db_publication`, `self_knowledge_layer`,
`control_room_facelift`, the `cap_2a..cap_2f` families, `fleet_launch_*` — 30+ specs carry
`gN_adversarial[adversarial_readonly,run_model]` and `gN_test_gate[test]`.

## Execution granularity — the selection rule (2026-09-23)

Decompose the build whenever it does not fit in one sitting — and treat that as the DEFAULT, not
the exception. The 2026-09-23 evidence (L33's three attempts against one large `execute`) is that
a monolithic execute is the failure factory: a large single concern-count drowns a session, hides
verification gaps, and makes every miss cost a whole attempt. Two triggers, either sufficient:
(a) ≥2 units with INDEPENDENT ACCEPTANCE (a unit's verdict stands on its own gate's targets); (b)
the work has more than one CONCERN, or its diff is not reviewable in one sitting. A single
bounded agent phase remains correct only for ONE concern with a small, single-gate diff.

**The unit-size discipline (applies whenever the build expands).** A unit is ONE concern: a
handful of files, one verifiable change, ONE gate that proves it. Prefer MORE, SMALLER units —
eight small beats three large. If a unit touches more than ~4 files or two concerns, or cannot be
proven by one gate, SPLIT it. `plan_unit_cap` is a ceiling, never a target. A unit that cannot be
accepted independently is not a unit; neither is a unit too large for one gate. Seams are not the
enemy — an unprovable monolith is.

**The two halves (already built; no new mechanism).**

* The SPEC author decides **whether** a phase is expandable: the phase declares
  `expand_from_plan: <units path>`, and exactly ONE phase per spec may declare it — refused at
  validate time (`experiment_spec.validate_spec`, the earliest gate) and again by the runner.
* The PRIOR decides **what the units are**: it writes the machine-readable plan
  (`notes/plan.units.json` — `{id, goal, files, tests, acceptance, budget_usd, depends_on}`)
  during its own phase, so the structure is FIXED before the declaring phase begins. The
  runner then replaces the one phase with one bounded agent slice (`<phase>__<unit>`) plus one
  independent `kind: test` gate (`g_<unit>_test_gate`) per unit, in dependency order, inside
  the SAME run (same ledger, same candidate, same promotion check); `plan_unit_cap` (default
  24) bounds N.
* The prior's units file is therefore LOAD-BEARING structure — its quality decides the run's
  shape. The runner refuses by name (missing/invalid plan, dependency cycle or unknown
  dependency, name collision, over-budget, over-cap) and never repairs; a unit whose
  acceptance is prose-only is a plan miss.
* First candidates: **L34–L36** (harness / wiring / scoping — independent verdicts each)
  once the model-pin sweep (L39) unblocks them; their priors write the units file and their
  executes declare the expansion.

**What is deliberately NOT linted** (evaluated 2026-09-23). *"Multi-unit build without
`expand_from_plan`"* is a judgment about acceptance — no static property of a YAML can decide
it, and a heuristic would manufacture false findings. *"Declares expansion but the prior
writes no units"* is only knowable at run time, where the runner already refuses the declaring
phase by name before that phase spends. The statically checkable half is enforced where it
belongs: `validate_spec` refuses the unsupported combinations and the two-declarer defect, and
the runner refuses the plan's structural defects. Authoring guidance lives here, not as a lint
guess.

## Each concern → its precedent → its enforcement

| concern | precedent (specs/tools) | enforcement |
|---|---|---|
| **prior-run shape** | `p0_pin_spec` / `p0_pin_mandate` / `p0_preregister` / `d0_pin_sources`; world_model_loop `prior` | runner gate: `requires_files` (existence) + **`requires_content` (required SECTIONS — added v1.2)** |
| **research** | `control_room_research` r0→r8 (audit → questions → five acquisition legs → taxonomy → reduce → synthesize → adversaries → verify → tests); `herdr_inspired_ux` h0_pin_sources; `cap_2a_rerun2` p0_research; `cap_site_revamp` p0_research_and_editorial_audit | `research_fetch.py` (provenance: uri/final_url/fetched_at/sha256/text) + the loop's `## Sources` requirement |
| **sources** | `d0_pin_sources`, `h0_pin_sources`; the `sources.jsonl` catalog | prompt-required + recorded in `world_model.md` `## Sources` (shape-gated) |
| **skill creation** | `cap_pattern_minting` (p2_mint_patterns); `kb_produce_skill` (pattern/v1); `claude_tools_to_skills` (scope→build→verify); `control_room_facelift_review` a2_dynamic_workflow | convention: KB pattern record + reviewed promotion (a producer exists; a loop step does not yet) |
| **execution contents** | the slices; world_model_loop `execute` | `requires_content` on the PLAN (`## Files`, `## Tests`, `## Acceptance`); `deviations.md` records drifts |
| **plan-driven expansion** | world_model_loop `execute` (`expand_from_plan`); the static `cap_*` slices it generalizes | runner: `_expand_plan_phases` — ONE declared phase → one agent slice + one `kind: test` gate per plan unit (`notes/plan.units.json`, written at run time); refusals (`PLAN_EXPANSION`) before the declaring phase spends; the single-declarer rule is also refused at validate time — the selection rule is § "Execution granularity" above |
| **adversarial check** | `gN_adversarial` / `adversary_*` with `run_model` (a different model, readonly) | phase presence + the runner's per-phase gates; added to world_model_loop as `g_adversarial` |
| **human gates** | `checkpoint: true` phases (`cap_site_revamp3/4`, `fleet_ladder_implementation`, `control_room_rules_design`) | runner: `awaiting_operator_approval` — the run STOPS |
| **compiled workflows** | `workflows/compile_workflow.py` | refusal-first linter: `refused-*` codes — unsupported semantics refuse before submission |
| **promotion** | `promote.py` gates (candidate / commit / evidence) | the ONE permanence path |

## The world-model loop v1.2 (conformed, `feature/world-model-v1`)

`prior` (required sections, Sources) → `execute` (plan shape-gated) → `posterior` →
**`g_adversarial`** (different model, readonly, falsifiers required) — plus `requires_files`
on posterior and the durable-emission contract (`FINOPS_RESULTS_DIR`).

**v1.3 (`feature/wml-v1.3`) adds the missing pieces below**: fleet scopes, `g_test_gate`
(plan-driven), `p2_mint`, and source forcing.

## Gaps (ranked, honest) — addressed in the loop's v1.3

1. ~~The loop has no `g_test_gate`~~ → **added**: a plan-driven `kind: test` phase
   (`tests_from_plan: notes/plan.md`; an explicit skip when the plan names no targets —
   `test_gate_note`, no fabricated verdict).
2. ~~Skill creation is a convention, not a step~~ → **step added**: `p2_mint` mints the
   posterior's candidates through the existing producer; promotion stays a reviewed commit.
3. ~~Research is prompt-encouraged, not forced~~ → the prior must write
   `notes/sources.jsonl` (provenance + sha256; explicit `none`), the execute gate requires it,
   and `g_adversarial` checks external gaps against it.

**New finding (2026-09-21, from the merge):** the loop's fixed `notes/*.md` paths collide
across runs — two runs' branches conflicted on all four files at merge time (resolved by
namespacing the second run's notes). Next convention: namespace run notes by run/task, or
route them to the durable results dir.

## The loop's open extension (2026-09-21, `loop-execute-as-workflow`)

The gap the enforcement map now closes: a plan WRITTEN AT RUN TIME that compiles into phases.
The loop's `execute` declares `expand_from_plan: notes/plan.units.json`; the runner expands that
ONE phase into one bounded agent slice plus one independent `kind: test` gate per plan unit, in
dependency order, inside the SAME run (same ledger, same candidate, same promotion check). This
generalizes the `cap_*` static slices — the units are authored by the prior at run time, so they
cannot sit in the spec's authored phase list. Refusals (a missing/invalid plan, a cycle or
unknown dependency, a name collision, over-budget units, too many units) fail the declaring
phase with `PLAN_EXPANSION` before any spend. Mechanics and residual gaps:
`world_model_loop.md` → "Open extension: built".
