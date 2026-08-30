---
status: accepted
---

# CAP freeze note — Context Abstraction Plane, I0–I7

**Phase `freeze` of `consolidation_stage_0_architecture_spine`.** Records the Context
Abstraction Plane freeze declared by the consolidation release (rec 1 of
`docs/reviews/semantic_monolith_review.md`), so the pause is a durable, citable artifact rather
than a transient comment.

## What is frozen

`experiments/specs/context_abstraction_implement.yaml` — the eight-increment (I0–I7) CAP
implementation spec — is **PAUSED**: not deleted, not superseded, not tombstoned.

- **freeze_reason:** `consolidation_release/stage_map` — the critique's rec 1 ("freeze
  architectural expansion until structural homes exist") is the gate; the homes are reserved in
  Stage 0 and the release completes at Stage 6.
- **resume_after:** `consolidation S6` — post-consolidation CAP implementation drops into the
  reserved package homes (`docs/release/consolidation/stage_map.md` §6).
- **Mechanism in the spec YAML:** `status: draft` (the schema's "not runnable now" state — the
  only vocabulary value that is not `active`/`superseded`/`tombstoned`), plus the PAUSED note in
  the `question:` text. The derived index therefore renders it `draft`, never `active`.
- **Design survives:** `docs/architecture/current/context_abstraction_design.md` (moved from
  `docs/context_abstraction/design.md` in the lifecycle phase) remains the authority. The spec's
  internal design-path references are re-pointed to the moved locations when the spec resumes.

## Where the homes are reserved

`ARCHITECTURE.md` §4 ("Reserved-but-empty — the Context Abstraction Plane homes") declares the
empty-but-reserved places the CAP increments occupy, so post-consolidation implementation is
drop-in:

| CAP increment | Reserved home (`src/agentic_dynamics/`) |
|---|---|
| I0 | `control/facts.py` |
| I1–I3 | `control/reducers/` |
| I4 | `control/context_compiler.py` |
| I5 | `core/contracts.py` |
| I6 | `control/rules.py` + `control/validator.py` + `control/decisions.py` |
| I7 | `control/` (seam in `run_workflow`) |

The dependency-direction lint (Stage 1) permits `control` to import `core` and `knowledge`, but
nothing imports `control` except the reserved seam — consistent with "control consumes facts"
(rec 8). The homes are placeholders only; no CAP code exists yet.

## Gate stays closed

`context_abstraction_implement` is the one spec explicitly excluded from execution until S6
completes; the stage order never schedules it, and S6's invariant audit asserts it is still
PAUSED (not deleted, not superseded).

## Extraction directive for CAP I5 (from the public-truth closure)

`docs/reviews/public_truth_review.md`'s CAP readiness note, re-recorded here so the future CAP
spec carries it: the generic contracts the public-truth closure hardened —
`ManifestIdentity` / `ResolvedInputIdentity` (fact identity), `ResolutionIssue` /
`ResolutionReport` (fact resolution state), the waiver policy (policy exception), the
semantic lab contract (provenance chain), and record-scope accounting (scope) — are early
forms of CAP contracts. When I0–I4 resumes, extract and generalize them into the reserved
`core/contracts.py` home (I5); do not duplicate them, and leave publication-specific
filesystem joins in `reporting/`.
