---
status: accepted
---

# Stage 5 verification — apps/ realignment + dual-Firebase

**Phase `verify` of `consolidation_stage_5_apps_realignment`.** Verifies the two prior phases
(`move_apps`, `reframe_readme`) against the four acceptance metrics the spec declares
(`apps_import_system`, `apps_no_domain_rules`, `dual_firebase_synced`, `readme_reframed`) and the
standing gates.

**Provenance:** [M] measured this phase (pytest output, `grep`/config ground truth, `firebase
deploy --dry-run`); [C] computed from the tree; [P] policy invariants; [X] the critique
(`docs/reviews/semantic_monolith_review.md`).

---

## 1. `apps_import_system` — apps consume the system, never the reverse

- `grep -rn "from apps\|import apps" src/agentic_dynamics/` → **0 matches** (no production module
  imports the application tier). [M]
- `grep -rn "agentic_dynamics" apps/` → 15 matches (the Control Room + website consume the
  system). [M]

**Result: PASS.**

## 2. `apps_no_domain_rules` — the S1 dependency-lint apps-rule stays green

- `tests/test_dependency_direction.py` → **9 passed** (includes rule 8 — no
  `ExperimentSpec(`/`RuleSpec(`/`Factor(` construction in `apps/**` — and rule 6 — nothing below
  tier 3 imports `apps`). [M]

**Result: PASS.**

## 3. `dual_firebase_synced` — both hosts, one public dir

- `firebase/.firebaserc` → `{"projects": {"default": "ai-finops-rulebook",
  "agentic-dynamics": "agentic-dynamics"}}` — both projects present, canonical default preserved. [M]
- `firebase/firebase.json` → `"hosting": {"public": "../apps/website"}` — the public dir points at
  the moved website. [M]
- `firebase deploy --only hosting --dry-run` (from `firebase/`) → `✔ Dry run complete!` against
  `ai-finops-rulebook` — the config validates and resolves `apps/website/` as the hosting source. [M]

**Result: PASS.**

## 4. `readme_reframed` — six systems, perturbation instrument is one

- `README.md` leads with the six-system framing (measurement / experiment / execution / knowledge
  / control / publication) and cites `ARCHITECTURE.md` + the `agentic-dynamics` CLI; the
  perturbation instrument is system 1. [M]
- `apps/website/CONTEXT.md` documents the website source at its new home, keeps the dual-Firebase
  instruction verbatim, and points at `firebase/` for the deploy config. [M]

**Result: PASS.**

## 5. Standing gate

- `pytest tests/ -m "not external"` → **1189 passed, 106 deselected**. [M]

**Result: PASS.**

---

## Final result

| # | Metric | Result |
|---|---|---|
| 1 | `apps_import_system` | PASS |
| 2 | `apps_no_domain_rules` | PASS |
| 3 | `dual_firebase_synced` | PASS |
| 4 | `readme_reframed` | PASS |

**Overall: PASS — 4/4.** Stage 5 (apps/ realignment + public-identity reframe) is complete and
gate-green; S6 may proceed.
