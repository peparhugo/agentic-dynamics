---
status: accepted
---

# Stage 0 verification — architecture spine + doc lifecycle + CAP freeze

**Phase `verify` of `consolidation_stage_0_architecture_spine`.** Verifies the three prior phases
(`spine`, `lifecycle`, `freeze`) end to end against the S0 acceptance criteria
(`docs/consolidation/stage_map.md` §4 Stage 0) and the phase `verify` prompt.

**Provenance:** [M] measured this phase (pytest output, `ls`/`grep` ground truth); [C] computed
from the migrated tree; [P] policy invariants; [X] the critique
(`docs/review/semantic_monolith_review.md`).

---

## 1. Doc-lifecycle lint

`python3 -m pytest tests/test_doc_lifecycle.py -v` — **[M] output:**

```
tests/test_doc_lifecycle.py::test_every_document_has_status_field PASSED
tests/test_doc_lifecycle.py::test_archive_entries_are_superseded PASSED
tests/test_doc_lifecycle.py::test_current_designs_are_accepted PASSED
tests/test_doc_lifecycle.py::test_implemented_designs_name_their_branch PASSED
tests/test_doc_lifecycle.py::test_no_blueprint_at_root PASSED
```

**Result: PASS** — 5 passed.

## 2. Exactly one root ARCHITECTURE.md with the six §2 sections

- `ls ARCHITECTURE.md` — one root `ARCHITECTURE.md` exists. [M]
- `grep -n "^## " ARCHITECTURE.md` shows the six required sections: §1 Planes, §2 Package
  boundaries, §3 Dependency direction, §4 Implemented vs proposed, §5 Canonical execution loop,
  §6 Supersession map (plus §7, the load-bearing rule stated verbatim per the `spine` phase). [M]

**Result: PASS.**

## 3. No BLUEPRINT\*.md at the root

`ls BLUEPRINT*.md` — empty. All three (`BLUEPRINT.md`, `BLUEPRINT_v2.md`, `BLUEPRINT_v3.md`) live
in `docs/archive/` with `status: superseded` + `superseded_by: ARCHITECTURE.md`. [M]

**Result: PASS.**

## 4. context_abstraction_implement — PAUSED, not deleted, not superseded

- `grep -n "PAUSED" experiments/specs/context_abstraction_implement.yaml` — 2 matches (comment +
  `question:` text), carrying `freeze_reason: consolidation_release/stage_map` and
  `resume_after: consolidation S6`. [M]
- File still exists (not deleted). [M]
- `load_spec(...)` → `superseded_by: None`; the YAML has `status: draft` and no `superseded_by:`
  key (the sole `superseded_by` string match is a phase-prompt reference to the general
  `spec_status` fields, not a declaration). `validate_spec` returns `[]` (no errors). [M]
- Derived index reflects the freeze: `index.json` + `STATUS.md` show `draft`, never `active`
  (`spec_status.py --dry-run` confirms the derivation). [C]

**Result: PASS.**

## 5. Coverage — rec 1 (freeze) and rec 4 (single authority + lifecycle)

- **rec 1 → freeze declared:** CAP I0–I7 paused; reserved homes declared in `ARCHITECTURE.md` §4;
  freeze note in `docs/consolidation/cap_freeze_note.md`. [P]
- **rec 4 → single authority + lifecycle status:** exactly one root `ARCHITECTURE.md` (§2); a
  status front-matter block on every remaining root + `docs/**` markdown file (§3, and
  `tests/test_doc_lifecycle.py` enforces it). [M]

**Result: PASS.**

## 6. Zero orphan files from the migration

Every moved document appears in its new home, and no source location retains a copy:

- `docs/archive/` — 9 files (3 BLUEPRINT + 2 HANDOFF + 4 dated code reviews). [M]
- `docs/designs/current/` — 4 files (context-abstraction design+verify, `supervisor_design.md`,
  spec/compiler roadmap `2026-08-14_*`). [M]
- `docs/designs/implemented/` — 13 files (9 canonical-state + RAG seam split + 3 website
  repoints). [M]
- `code_reviews/` — empty (all 5 dated files moved). [M]
- `docs/context_abstraction/` — retains only `review.md` (not in the phase's `{design,verify}.md`
  move list). [M]
- `git status` shows every move as a rename (`R`), preserving history. [M]

**Result: PASS.**

## 7. Full suite green (doc-only change)

`python3 -m pytest tests/ -m "not external" -q` — **[M] output:** `1179 passed, 121 deselected,
19 warnings in 19.54s`. No production code was touched by S0 (the only source-tree additions are
`ARCHITECTURE.md`, the doc moves/statuses, and `tests/test_doc_lifecycle.py`).

**Result: PASS.**

## 8. stage_map.md named as the release plan

`ARCHITECTURE.md` §4 ("Implemented vs proposed" → "The release plan") names
`docs/consolidation/stage_map.md` as the dependency-ordered release plan. [M]

**Result: PASS.**

---

## Final result

| # | Check | Result |
|---|---|---|
| 1 | `tests/test_doc_lifecycle.py` green | PASS |
| 2 | Exactly one root `ARCHITECTURE.md` with six §2 sections | PASS |
| 3 | No `BLUEPRINT*.md` at root | PASS |
| 4 | `context_abstraction_implement` PAUSED, not deleted, not superseded | PASS |
| 5 | rec 1 → freeze declared; rec 4 → single authority + lifecycle | PASS |
| 6 | Zero orphan files from the migration | PASS |
| 7 | Full suite green (`-m "not external"`) | PASS |
| 8 | `stage_map.md` named as the release plan | PASS |

**Overall: PASS — 8/8.** Stage 0 (architecture spine + doc lifecycle + CAP freeze) is complete and
gate-green; S1 may proceed.
