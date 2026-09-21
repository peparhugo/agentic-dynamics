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

## Each concern → its precedent → its enforcement

| concern | precedent (specs/tools) | enforcement |
|---|---|---|
| **prior-run shape** | `p0_pin_spec` / `p0_pin_mandate` / `p0_preregister` / `d0_pin_sources`; world_model_loop `prior` | runner gate: `requires_files` (existence) + **`requires_content` (required SECTIONS — added v1.2)** |
| **research** | `control_room_research` r0→r8 (audit → questions → five acquisition legs → taxonomy → reduce → synthesize → adversaries → verify → tests); `herdr_inspired_ux` h0_pin_sources; `cap_2a_rerun2` p0_research; `cap_site_revamp` p0_research_and_editorial_audit | `research_fetch.py` (provenance: uri/final_url/fetched_at/sha256/text) + the loop's `## Sources` requirement |
| **sources** | `d0_pin_sources`, `h0_pin_sources`; the `sources.jsonl` catalog | prompt-required + recorded in `world_model.md` `## Sources` (shape-gated) |
| **skill creation** | `cap_pattern_minting` (p2_mint_patterns); `kb_produce_skill` (pattern/v1); `claude_tools_to_skills` (scope→build→verify); `control_room_facelift_review` a2_dynamic_workflow | convention: KB pattern record + reviewed promotion (a producer exists; a loop step does not yet) |
| **execution contents** | the slices; world_model_loop `execute` | `requires_content` on the PLAN (`## Files`, `## Tests`, `## Acceptance`); `deviations.md` records drifts |
| **adversarial check** | `gN_adversarial` / `adversary_*` with `run_model` (a different model, readonly) | phase presence + the runner's per-phase gates; added to world_model_loop as `g_adversarial` |
| **human gates** | `checkpoint: true` phases (`cap_site_revamp3/4`, `fleet_ladder_implementation`, `control_room_rules_design`) | runner: `awaiting_operator_approval` — the run STOPS |
| **compiled workflows** | `workflows/compile_workflow.py` | refusal-first linter: `refused-*` codes — unsupported semantics refuse before submission |
| **promotion** | `promote.py` gates (candidate / commit / evidence) | the ONE permanence path |

## The world-model loop v1.2 (conformed, `feature/world-model-v1`)

`prior` (required sections, Sources) → `execute` (plan shape-gated) → `posterior` →
**`g_adversarial`** (different model, readonly, falsifiers required) — plus `requires_files`
on posterior and the durable-emission contract (`FINOPS_RESULTS_DIR`).

## Gaps (ranked, honest)

1. The loop has no `g_test_gate`: harmless for analysis-only runs; when `execute` produces
   CODE, a `kind: test` phase is the canonical independent verification and must be added.
2. Skill creation is a convention, not a step: candidates land in the KB; promotion is a
   reviewed commit. A `p2_mint`-style step (the pattern-minting precedent) is the next build.
3. Research is prompt-encouraged, not forced: `## Sources` shape-gating ensures the section
   exists, not that a search happened when a gap demanded one.
