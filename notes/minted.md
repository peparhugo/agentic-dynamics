# Minted — Close the live-KB test-emission leak (p2_mint)

Phase: `p2_mint` of `world_model_loop`, run of 2026-09-21 (posterior commit `84a4a56ac`,
prior `b00947b12`, execute `6985163dd`). Producer: `scripts/kb_produce_skill.py` (the
`pattern/v1` projection — the only existing producer for procedural skill/pattern knowledge).
Every candidate below was written as `notes/skills/<slug>.json` in the producer's shape
(`claim`, `population`, `conditions`, `support`, `uncertainty`, `evidence`, `source_experiment`,
`subject`) and minted through the producer; **no record was hand-written and no generated
surface was hand-edited**.

`support` counts real observed instances (2 for the two stale fixed-path notes, 18 for the raw
leaked artifacts, else 1). `uncertainty` is `null` everywhere because every slice is below the
producer reducer's `MIN_SUPPORT_FOR_UNCERTAINTY = 3` (`src/agentic_dynamics/control/reducers/pattern.py:89`)
— a stated `null`, never a fabricated interval.

## Dispositions

| # | candidate (posterior §UPDATES) | slug | disposition | fact / projection knowledge_id |
|---|---|---|---|---|
| A2 | stale-note hazard [H] | `stale-conditional-note` | minted | `969ad08979cdb9eacf3447d8fd6b68e975d06d5163987f0bf0f13fb808688377` / `50a415c11bf339e5d6bbbeb67c8eb017ef9e446c18fb4858563a2008b9521822` |
| A3 | the leak compounds [H] | `compounding-emission-leak` | minted | `25ebbfadeff4a7e46dd6fddb9c3959ff6c3d8a137c58e2ce2d86c92365c7f14d` / `d6f05b71a1671e8b135a24634d626fbe1a494e5d97a819e75bf709ac50a9cf95` |
| A4 | `kb_read` degradation [H] | `kb-read-degradation-crash` | minted | `3fdb223de5820135de2b3757a529361fca50ca9c2103f7c73671fa89b1993e3a` / `4b902b0914eb9504e7ff72f51a67861e32f8961d3f13b262c4480b6fb2843709` |
| C1 | explicit empty over stale | `explicit-empty-note` | minted | `dcab04590f90f8eb6d28e316bb13d69141899d6f8a3bf9128db6a6f9aa3a77ab` / `7781698644b90e0f5745754bf2478854ef47ea57e7da570ebf36287ccaa93582` |
| C2 | the emit-seam test guard | `emit-seam-guard` | minted | `02d9cc4cb88f30d2780485a6516d2b45c7c2843facf7332c708b16e082af7848` / `5076fe91a6051cd09ee3c439ab0f4fc8146a61ea03c6c88616108b73d38d96fd` |
| C3 | never change production precedence for a test defect | `pin-production-precedence` | minted | `293ab1e634b3c5380a2f63c81c1dbd2cfddcc237fa1091d46814621679f52503` / `a80779b88f53103d1b678917bc65d5530484e08eac773df79b4e1e5e9628b731` |
| C4 | note provenance | `note-provenance` | minted | `6c82666f3cce21b037e4990e5c85193b7f6ee50e0299c20ddba73767c147642e` / `7f64ac204d0abded616d8c8d4ee1b0565ac1255d239c3055385d6abf0a1e78b6` |

All 7 candidates `minted` — 7 `pattern/v1` facts + 7 pattern projections (14 artifacts),
published to `kb:v1:changes` (writes guarded by the producer's `FINFOPS_KB_WRITE=1` opt-in).
Each `notes/skills/<slug>.json` cites the KB record ids it uses as `evidence` (run records
`kb:014ffbeb…` prior, `kb:09c552b9…` execute, `kb:dc1d8eb1…` posterior, plus `kb:2c5995a7…`
the spec and `kb:e6222c1c…` the loop design doc), the run commits, and the file/line or
artifact-count references the posterior established.

## Recorded but NOT minted (never silently dropped)

- **A1 — the verification outcome [M]**: `skipped (one-off measured finding; belongs to the
  finding producer `emit_phase_finding`, not the skill/pattern producer. Every phase of this
  workflow already emits its report as a `finding` record — e.g. the execute finding
  `kb:09c552b9…` — so minting a `pattern/v1` fact for a single run's PASS/FAIL verification
  would model a run, not a reusable pattern.)`
- **§3.C `run-workflow` skill edit (C2 as an agent-facing skill)**: `skipped (generated/reviewed
  surface. Promotion of a KB candidate to an agent-facing skill is a reviewed commit, not a
  phase side effect. The underlying pattern is minted as `emit-seam-guard`; the skill surface
  can be amended from that record under review.)`
- **§3.C `world_model_loop` design doc + spec edit (explicit `notes/deviations.md`, per-note
  provenance check, note namespacing)**: `skipped (reviewed surfaces — a doc edit and a
  workflow-definition edit are reviewed commits, not phase side effects. The underlying patterns
  are minted as `explicit-empty-note` and `note-provenance`; the namespacing suggestion remains a
  design-doc proposal.)`
- **§3.D "what should change in the next loop's prior phase" (items 1–4)**: `skipped (guidance
  for the next prior — auditing inherited notes, counting raw leak artifacts, probing the KB mode,
  and scoping the single-path plan rule. These are operating instructions, not evidence-backed
  skill/pattern claims; the three that do carry a reusable claim are captured by
  `note-provenance`, `compounding-emission-leak`, and `kb-read-degradation-crash`.)`

## Environment note (an unknown discovered while minting — recorded, not minted)

The producer writes its artifact to `KB_ARTIFACT_DIR = PROJECT_ROOT/experiments/results/kb`
(`scripts/kb_produce_skill.py:55,139-143`), where `PROJECT_ROOT` follows the imported package
(`src/agentic_dynamics/core/paths.py:38`). It does **not** consult `FINFOPS_RESULTS_DIR`, unlike
`knowledge_ingestion._artifact_path` (`:421-433`) which the workflow runner uses for phase
findings. In this phase's shell `FINFOPS_RESULTS_DIR` is unset and `_bootstrap` puts the run
worktree first (`/repo/src`), so the producer wrote to the worktree's ignored
`experiments/results/kb/`, while this run's phase findings landed in the durable tree
(`/app/experiments/results/kb/`). **The prior loop's `p2_mint` artifacts are absent from the
durable tree** (no `test-seam-guard`/`skill/*` pattern record exists under
`/app/experiments/results/kb/`), consistent with that same split — i.e. agent-run producers'
records are written to the ephemeral worktree and lost. To keep this phase's knowledge durable,
the 14 byte-identical artifacts were copied into `/app/experiments/results/kb/` after minting, so
the published `file://experiments/results/kb/<id>.json` pointers resolve there. This root split
is left for the next prior to carry (it is a producer-seam unknown, not a candidate this
posterior named).
