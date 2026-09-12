---
status: accepted
---

# Control Room repair2 — verification and brief handoff (campaign `control_room_research_repair2`, phase `q6_verify_brief`)

**Date:** 2026-09-11
**Pass:** final synthesis; brief refresh + endpoint/disposition verification
**Inputs:** the six repair2 work products — q0 quoted-evidence crosswalk
(`docs/reviews/control_room_repair2_entailment.md`), q1/q4 direction
(`docs/research/control_room_direction.md`), q2/q5 one-resting-screen IA
(`docs/research/control_room_ia.md` + `docs/reviews/control_room_repair2_ia.md`), and the q4 design
verdict (`docs/reviews/control_room_repair2_design.md`).
**Outputs:** the refreshed facelift brief (`docs/research/control_room_direction.md` §15–§19) and this
verification record.

## Verdict

**PASS — the three verdict blockers are repaired and the three re-run adversaries all returned PASS.
The facelift brief is unconditional except for four explicit waivers (W1–W4).**

The prior campaign handed off a *conditional* brief: zero-promotion support and the universal
no-interaction glance contract were not clean, and seven design/entailment blockers remained open. The
repair2 campaign closes all of them:

1. **Quoted-evidence support** — every positive support now carries a verbatim, technique-stating
   sentence; structural totals no longer masquerade as source support; unsupported candidates are
   excluded (verdict PASS).
2. **Distinctive, exemplar-grounded direction** — eight moves each name an exemplar, the changed
   agent-run behavior, and a visible screenshot carrier; the resting screen is a run ledger, not a
   dashboard shell (verdict PASS).
3. **Canonical one-screen glance contract** — one single-valued `ON-G1..G7` map, every need in one
   budgeted non-scrolling region, both required viewports fit, and the render-gate checks are
   implementable (verdict PASS).

No design question is left to the facelift. The facelift and its render gate are the graded *work*, not
open questions, and are the subject of the brief's acceptance criteria.

## 1. Endpoint status

### 1.1 Campaign delivery endpoints

| Endpoint | Artifact | sha256 (16) | Commit | Status |
|---|---|---|---|---|
| Taxonomy repaired (quoted evidence) | `experiments/research/control_room/taxonomy.json` | `cf988d3d6b0861a6` | q3 `f7ffa756f` | Delivered — 44 technique leaves, all `PASS`, exclusions recorded |
| Catalogs regenerated | `experiments/research/control_room/catalogs.json` | `b88c462916ea961c` | q3 `f7ffa756f` | Delivered — 27 `[P]` items with policy reasons |
| Skills regenerated | `experiments/research/control_room/skills.json` | `b73d6b69ff30bd99` | q3 `f7ffa756f` | Delivered — 7 policy blocks |
| Entailment verdict | `docs/reviews/control_room_repair2_entailment.md` | `87f164ec7c9c9d5d` | q3 `f7ffa756f` | Delivered — **PASS** |
| Design verdict | `docs/reviews/control_room_repair2_design.md` | `65a2fd02f53c6a55` | q4 `998bb4788` | Delivered — **PASS** |
| Canonical glance IA | `docs/research/control_room_ia.md` + `docs/reviews/control_room_repair2_ia.md` | (q5/q6 commits) | q5 `bf0280d62` | Delivered — **PASS** |
| Facelift brief refreshed | `docs/research/control_room_direction.md` §15–§19 | (this commit) | q6 | Delivered — unconditional except W1–W4 |
| Verification record | this file | (this commit) | q6 | Delivered |

The three repair2 adversaries each ran a distinct pass and all three returned PASS, unlike the prior
campaign where all three returned blocking verdicts.

### 1.2 Control Room runtime endpoint status

The design is complete but the facelift has not been implemented; this is the expected state of a
documentation campaign and is not a design blocker.

| Surface | Current state | Required by the brief |
|---|---|---|
| `/api/glance` additive read-only projection | **ABSENT** — `apps/control_room/routes/telemetry.py` registers `/api/matrix`, `/api/status`, `/api/projections`, `/api/events/<cell_id>`, `/api/routing`, `/api/subscription-usage` only | Additive projection carrying the IA §10.6 schema when `/api/matrix` cannot supply it; must derive from the existing control packet/ledger |
| `[data-region]` / `[data-answer]` / `[data-field]` anchors | **ABSENT** — the current `apps/control_room/static/` is the pre-facelift portal | IA §10.2 selector contract |
| `verify_control_room_rendering.py` | **ABSENT** — only `apps/website/verify_svg_rendering.py` exists | Three-viewport, three-theme render gate (acceptance criterion 1) |
| Facelift (`a1`–`a7`) | **NOT STARTED** | The graded work of §18 |

The render gate is fixture-driven by design (waiver W2), so it can be implemented and pass before the
production projection exists; the projection remains required for the portal to serve real data.

## 2. The three adversary verdicts

| # | Adversary | Pass condition | Verdict | Evidence |
|---|---|---|---|---|
| 1 | Entailment (`control_room_repair2_entailment.md`) | Every support has a stored `evidence_quotes` entry; each quote is a real sentence from the cited stored source that states the technique; no `PROMOTION`/`ABSENT` node survives; ≥15 nodes independently sampled | **PASS** | 44 leaves all `semantic_verdict: PASS`; quote cardinality equals support throughout taxonomy/catalogs/skills; excluded former failures remain absent; independent 15-node sample verified |
| 2 | Design (`control_room_repair2_design.md`) | Direction names ≥6 exemplar-grounded distinctive moves, none generic dashboard grammar; recognizability test is concrete and stranger-holdable; if it reads as a monitoring console, name the elements to kill | **PASS** | Eight moves with current supports; resting run-ledger carriers; no-selection 10-second five-statement protocol with a generic comparator; explicit kill list |
| 3 | IA (`control_room_repair2_ia.md`) | One single canonical glance contract; each need maps to a budgeted region; both viewports fit; checks implementable; fail on any scroll, split answer, or below-fold placement | **PASS** | `G1→R0, G2→R2, G3→R1, G4→R3a, G5→R1, G6→R0, G7→R3c`; 884≤900 and 760≤844 (760≤768 narrow); exact selector/schema/fixture/contrast contract |

Each verdict's pass conditions were re-checked by an independent adversarial pass against the edited
artifacts, not asserted from the earlier draft.

## 3. Closed/waived disposition ledger (25)

All 25 p3/p4/p5 findings are **CLOSED**. No finding is `OPEN` or `SPECIFIED`. The four waivers after the
table are the only non-requirements in the entire brief.

| ID | Severity | Status | Fix |
|---|---|---|---|
| E1 | BLOCKER | **CLOSED** | q0 quoted-evidence crosswalk rebuilt from record-level direct evidence; taxonomy/catalogs/skills/direction/IA regenerated; unsupported moves demoted to `[P]` (§4). |
| E2 | HIGH | **CLOSED** | §2.2 uses the real `RunState` graph and states the UX label maps exhaustively to it. |
| E3 | MEDIUM | **CLOSED** | IA §4 answers all seven needs at 1024×768; ticker withdrawn. |
| E4 | MEDIUM | **CLOSED** | q0 enforces one direct leaf per label; `tests/test_control_room_research_evidence.py` guards it. |
| E5 | MEDIUM | **CLOSED** | §4.0 claim classes `[M]`/`[X]`/`[P]`; composition forced `[P]`; no count presented as composition proof. |
| D1 | BLOCKER | **CLOSED** | §4 session-first moves + §4.3 removed list + §4.5 blind comparator replace the dashboard axis. |
| D2 | BLOCKER | **CLOSED** | §4.1 Move 1 + §4.4 identity band + IA §10.2 row-field selectors make agent/session/worktree/command identity primary and gated. |
| D3 | HIGH | **CLOSED** | IA §3.2 pixel budget + §10 geometry/schema checks are measurable and comprehension-tested. |
| D4 | HIGH | **CLOSED** | §4.0 separates pattern `[X]` from composition `[P]`; §4.1 re-grounded to q0 supports. |
| D5 | HIGH | **CLOSED** | §4.4 defines the run/evidence/action visual grammar; tokens remain hygiene. |
| D6 | MEDIUM-HIGH | **CLOSED** | §4.1 Move 4 + §8 provenance inventory + IA G-4/G-13/B-10 enforce tiered provenance and the scan path. |
| D7 | MEDIUM-HIGH | **CLOSED** | §4.1 Move 3 + IA §2 reserved decision answer + eligibility enum surface action eligibility without actuation. |
| D8 | MEDIUM | **CLOSED** | §16 pointer + IA breakpoint contracts for desktop/narrow/mobile; blind screenshot set specified. |
| D9 | MEDIUM | **CLOSED** | §4.5 restraint budget + hard kill rule + §4.3 removed list; blind generic-dashboard comparison. |
| IA1 | BLOCKER | **CLOSED** | IA §4 is the single authoritative `ON-G1..G7` list; direction §16 holds no second table. |
| IA2 | BLOCKER | **CLOSED** | No resting region scrolls; full lists are lenses; ticker withdrawn (IA §3.1/§10). |
| IA3 | CRITICAL | **CLOSED** | All five `ON-G4` values at rest at 1440×900 and 390×844 (IA §4/R3a). |
| IA4 | CRITICAL | **CLOSED** | Bounded `R3c` with exactly four marginals/top-other-unknown, at every viewport; no mobile omission. |
| IA5 | HIGH | **CLOSED** | Complete single-region answers; mirrors omit `data-answer`; IA §4/§8. |
| IA6 | HIGH | **CLOSED** | Reserved risk/all-clear and decision/none rows + global ranking; saturated fixture F-1. |
| IA7 | HIGH | **CLOSED** | Exact pixel/row/line budgets, type floor, truncation rules, bounded cardinality (IA §3.2/§10). |
| IA8 | HIGH | **CLOSED** | Acceptance split into G geometry, B blind, A browser/a11y, E event/state with five primitives (IA §10). |
| IA9 | MEDIUM-HIGH | **CLOSED** | Reserved R1 decision answer with eligibility enum; R2 mirror non-authoritative; full preview in R4. |
| IA10 | MEDIUM | **CLOSED** | IA §3.3 fixes one selected-state arrangement per breakpoint and tests region persistence. |
| IA11 | MEDIUM | **CLOSED** | IA §8 enumerates per-region provenance fields; G-4/G-13 aligned. |

**Totals: 25 CLOSED, 0 WAIVED, 0 OPEN, 0 SPECIFIED.**

### Explicit waivers (the only non-requirements)

| # | Waived item | One-line reason |
|---|---|---|
| W1 | External push/notification delivery | No delivery channel exists; the durable in-room inbox with transition-only polite announcements is the whole promise (r6c IA6). |
| W2 | Live-production data inside the render gate | The gate is deterministic fixture-driven by design, so it neither starts a deployment nor requires the glance endpoint running; production wiring is graded by scope + acceptance criteria. |
| W3 | Per-projection rows for registry/ledger/chroma/neo4j at rest | `ON-G1`/`ON-G6` are complete in `R0`; `R3b` needs only the aggregate worst lag/age, and per-projector detail is drill-down. |
| W4 | Mobile `ON-G7` omission or narrow-desktop ticker | Both were withdrawn because they broke the single contract; all seven answers at all three viewports is cheaper than a second fallback schema. |

## 4. Repaired supports (what §4/§7 now rest on)

The q0 crosswalk replaced label-level allocation with quoted, pattern-gated evidence:

- **44 technique leaves**, all `semantic_verdict: PASS`; seven former false positives (including
  `request logged`, `predictable`, navigation `Log`, and print-safe SVG) are excluded, not promoted.
- **Current groundings used by §4.1:** session grouping 7, trace tree 17, waterfall timeline 3,
  alerting 6, keyboard-first 6, direct command palette 1, eval loop 21, cost attribution 4,
  live-follow 10. Single-family/agentops-only leaves are labelled with the caveat.
- **Structural totals** (category/stack/aesthetic/union) are `record_count`, not `support`, so no
  annotation total is presented as source evidence.
- **Verifier + regression:** `build_taxonomy.py` fails on a non-verbatim or off-pattern quote;
  `tests/test_control_room_research_evidence.py` pins cardinality, verbatim text, PASS verdicts, and
  excluded-node absence.

## 5. Brief acceptance criteria (the facelift is graded against these)

The full brief is `docs/research/control_room_direction.md` §18; the canonical glance contract is
`docs/research/control_room_ia.md` §4/§10.

1. **Render gate** at 1440×900, 1024×768, 390×844 in dark/light/forced-colors, zero failures.
2. **One-resting-screen glance check**: all seven anchors visible, non-zero, in-viewport, no page or
   region scroll; the IA §10 primitives are the contract.
3. **Contrast**: WCAG 2.2 AA (≥4.5:1 body, ≥3:1 large) via the effective-background HTML probe.
4. **Accessibility**: non-colour status, semantic controls, one transition-only live region, focus
   containment/return, keyboard operation.
5. **No regressions**: the r0 §9 guardrails, control-packet authority, mutation/idempotency, keyed
   write-on-change, no-build.
6. **Adversary closure**: all 25 dispositions CLOSED; only W1–W4 waived.
7. **Recognizability**: a blind reviewer states all five §4.2 sentences from the resting desktop and
   mobile screenshots and points to the carrying element, with the generic comparator failing 1/4/5.

## 6. Reproduce

```bash
# 1. Rebuild the taxonomy and regenerated reduction (deterministic; prints "unresolved refs: 0")
python3 experiments/research/control_room/build_taxonomy.py
python3 experiments/research/control_room/reduce_knowledge.py

# 2. Re-run the evidence regression + the docs rails
python3 -m pytest tests/test_control_room_research_evidence.py \
  tests/test_docs_drift_watchdog.py tests/test_stale_path_guard.py \
  tests/test_control_room_paths.py tests/test_research_fetch.py -q

# 3. Inspect the three verdicts and the canonical contract
sed -n '1,40p' docs/reviews/control_room_repair2_entailment.md
sed -n '1,40p' docs/reviews/control_room_repair2_design.md
sed -n '1,40p' docs/reviews/control_room_repair2_ia.md
sed -n '210,300p' docs/research/control_room_ia.md
```

**Doc lifecycle.** The brief, the IA, this record, and the three repair2 review docs carry
`status: accepted` (`tests/test_doc_lifecycle.py`). Two lifecycle failures are pre-existing and
unrelated to repair2: `docs/reviews/flash_ladder_score_review.md` lacks a status field, and the
README's spec count is stale against `experiments/specs/index.json`. Neither file is touched here.

## 7. Deviations and notes

| # | Item | Status |
|---|---|---|
| 1 | Facelift implementation (`a1`–`a7`) | NOT STARTED — graded by §18; not a brief condition |
| 2 | Render gate script | NOT STARTED — specified implementably by IA §10; not a brief condition |
| 3 | Production glance projection | REQUIRED for live data; gate uses fixtures (W2) |
| 4 | External notifications | WAIVED (W1) |
| 5 | Per-projection rest rows | WAIVED (W3) |
| 6 | Mobile `ON-G7` omission / ticker | WAIVED (W4) — all seven answers required everywhere |
