---
status: accepted
---

# Control Room research repair — verification and brief handoff (campaign `control_room_research_repair`, p6)

**Date:** 2026-09-11
**Pass:** final synthesis; brief refresh + endpoint/disposition verification
**Inputs:** the five repair-phase work products — p0 taxonomy repair
(`docs/reviews/control_room_taxonomy_repair.md`), p1 reworked direction, p2 one-resting-screen IA
(`docs/research/control_room_ia.md`), and the three repair adversaries p3/p4/p5 — plus the prior
campaign's r7 verification (`docs/reviews/control_room_research_verify.md`).
**Outputs:** the refreshed facelift brief (`docs/research/control_room_direction.md` §16–§19) and this
verification record.

## Verdict

**CONDITIONAL PASS — all campaign delivery endpoints are met; the two central acceptance claims are
not yet clean; the brief is refreshed and explicitly conditional on closing the open blockers.**

The repair campaign did what it set out to do: it rebuilt the taxonomy from the corpus with direct-label
crosswalks, regenerated the catalogs and skills, re-centered the direction on the live run, produced a
one-resting-screen IA, and re-ran all three adversaries as independent passes. The brief now
incorporates the glance mapping and a 25-finding disposition ledger.

Two claims remain unresolved and must not be presented as met:

1. **Zero-promotion support.** p3 found the rebuilt crosswalk still promotes adjacent labels into
   narrower techniques (E1/E4). The counts are arithmetically reproducible but not semantically clean.
2. **One-resting-screen glance contract.** p5 found the IA proves co-location at 1440×900 but not at
   narrow desktop/mobile, and that the acceptance suite tests DOM presence rather than visibility.

The brief therefore fixes the authoritative glance contract by decision (§16) and records every
disposition with an explicit status (§17). It is a fail-closed handoff, not a clean acceptance.

## 1. Campaign endpoints

| Endpoint | Artifact | sha256 (16) | Commit | Status |
|---|---|---|---|---|
| Taxonomy repaired (zero-promotion) | `experiments/research/control_room/taxonomy.json` | `316d71062a360028` | p0 `1554094d7` | Delivered; **E1/E4 open** |
| Supports audited (before/after) | `docs/reviews/control_room_taxonomy_repair.md` | `4e903e393f61b40d` | p0 | Delivered |
| Catalogs regenerated | `experiments/research/control_room/catalogs.json` | `be673013d1493524` | p0 | Delivered; 10 `[P]` items |
| Skills regenerated | `experiments/research/control_room/skills.json` | `c995b681f8d29e89` | p0 | Delivered; 7 policy blocks |
| Direction re-centered on the live run | `docs/research/control_room_direction.md` | `90e9fd4ef42976ea` | p1 `0885cb02e` | Delivered |
| One-resting-screen IA | `docs/research/control_room_ia.md` | `3e919f1dda2a1c7b` | p2 `6a8dcf16a` | Delivered |
| Adversary 1 — entailment | `docs/reviews/control_room_repair_entailment.md` | `683c1aded43368d9` | p3 `02374fbb3` | NOT CLEAN |
| Adversary 2 — design | `docs/reviews/control_room_repair_design.md` | `c58ffadf6b366aa9` | p4 `f0c8d18da` | REWORK REQUIRED |
| Adversary 3 — IA | `docs/reviews/control_room_repair_ia.md` | `ff7153b05be76879` | p5 `5a50f085e` | FAIL |
| Brief refreshed + verified | `docs/research/control_room_direction.md` §16–§19 + this file | (p6 commit) | p6 | Delivered |

Every adversary ran a distinct pass; all three returned a blocking verdict, as the campaign design
required.

## 2. Repaired supports — verification

**What p0 fixed (verified in `control_room_taxonomy_repair.md`):** seven inflated nodes were deleted
(`board-per-domain` 55, `source-provenance` 40, `budget-thresholds` 19, `audit-trail` 14,
`degraded-banner` 11, `quota-wallet` 7, `uncertainty` 3); four were recast to the technique the labels
actually state; eight honest thin leaves remain below the bar. 10 catalog items and 7 skills carry
explicit `[P]` policy statements with reasons.

**What remains open (p3 E1/E4):** the rebuilt crosswalk still maps adjacent labels into narrow nodes.
Literal-label lower bounds differ materially from reported support — command palette 11→8, tab bar 8→5,
density ladder 8→3, log stream 32→25, skeleton loading 5→2, colorblind-safe status 12→7, prompt
registry 3→0, release feed 26→17. Eight labels are also shared across multiple leaves, contradicting
the documented "at most one canonical leaf" method.

**Artifact-transport checks (clean):**

| Check | Result |
|---|---|
| Persisted support arithmetic | PASS — all 57 non-group leaves reproduce from the persisted crosswalk |
| Builder reproducibility | PASS — in-memory rebuild equals the committed taxonomy |
| Taxonomy example refs | PASS — 922 resolve exactly |
| Catalog / skill refs | PASS — 276 / 72 resolve exactly; all cited node ids exist |
| Direction source refs | PASS — 76 appendix rows and 25 catalog refs resolve |

**Disposition in the brief:** surviving counts that p3 disputes are provisional `[P]`/`[X]`; the brief
does not present them as external consensus.

## 3. One-resting-screen IA — verification

p5 walked every need: **PASS 1, PARTIAL 4, FAIL 2.**

| Need | Verdict | Core gap |
|---|---|---|
| `ON-G1` | PARTIAL | health split between R0 and scroll-prone R3b |
| `ON-G2` | PASS | roster placement is sound |
| `ON-G3` | PARTIAL | fixed inbox categories can bury a critical failure |
| `ON-G4` | FAIL | five money values can scroll or move below the fold |
| `ON-G5` | PARTIAL | decision existence visible; action eligibility not standardized |
| `ON-G6` | PARTIAL | distributed freshness; coverage undefined |
| `ON-G7` | FAIL | composition unbounded/scroll-prone and absent on mobile |

**Resolved by the brief (§16):** the authoritative per-breakpoint contract (desktop ≥1440 all seven
no-scroll; narrow ≥1024 all seven via a bounded ticker; mobile `ON-G1..G6` with `ON-G7` deferred),
global attention ordering, bounded composition marginals, at-rest action eligibility, tiered
provenance with a shared epoch, and selected-state persistence. **Still required in the artifact:** the
p2 IA document must be regenerated to match, and the acceptance tests split into geometry,
comprehension, browser/a11y, and event/state classes.

## 4. Adversary dispositions (25)

The refreshed brief §17 carries every finding. Status: **CLOSED (brief)** = corrective contract now in
the brief; **SPECIFIED** = required disposition + acceptance check recorded, artifact/implementation
pending; **OPEN** = remaining blocker.

| Adversary | Findings | Closed (brief) | Specified | Open |
|---|---:|---:|---:|---:|
| p3 entailment | 5 (E1–E5) | 2 (E2, E3) | 0 | 3 (E1, E4, E5) |
| p4 design | 9 (D1–D9) | 2 (D3, D8) | 3 (D2, D6, D7) | 4 (D1, D4, D5, D9) |
| p5 IA | 11 (IA1–IA11) | 5 (IA1, IA2, IA3, IA4, IA8) | 6 (IA5, IA6, IA7, IA9, IA10, IA11) | 0 |
| **Total** | **25** | **9** | **9** | **7** |

**Open blockers (7):** E1 (crosswalk promotion), E4 (one-leaf rule), E5 (claim-class leakage),
D1 (dashboard costume), D4 (exemplar ≠ distinctiveness), D5 (non-differentiating visual grammar),
D9 (restraint/datedness budget). None can be closed by a prose edit to the brief; each needs the
artifact repair (E1/E4/E5) or a design pass with blind screenshot review (D1/D4/D5/D9).

## 5. Brief acceptance criteria (the facelift is graded against these)

The full brief is `docs/research/control_room_direction.md` §18. Its acceptance criteria are:

1. **Render gate (desktop + mobile).** `verify_control_room_rendering.py` (patterned on the website's
   `verify_svg_rendering.py`) runs Playwright screenshots and size/overflow/aspect/contrast/first-paint/
   console checks at both breakpoints, **zero failures**, per-page screenshots, no regressions.
2. **One-resting-screen glance check (new).** Every required `ON-G*` answer visible at rest per §16,
   with no page/region scroll; blind reviewers identify each answer and the correct next action.
3. **Contrast.** WCAG 2.2 AA (≥ 4.5:1 body, ≥ 3:1 large) in both themes and forced-colors.
4. **Accessibility.** Non-colour status, semantic table controls, one transition-only live region,
   labelled dialogs with focus containment/return, keyboard operation.
5. **No regressions.** The eight r0 §9 guardrails plus control-packet authority, mutation/idempotency,
   keyed write-on-change rendering, and no-build.
6. **Adversary closure.** All `OPEN` dispositions in §17 closed or explicitly downgraded with the open
   item recorded.

## 6. Deviations and open items

| # | Item | Status | Owner |
|---|---|---|---|
| 1 | E1/E4 taxonomy crosswalk semantic repair (record-level evidence) | **OPEN — blocker** | future p0-style repair pass; controller decides |
| 2 | E5 claim-class normalization across p1/p2 prose | **OPEN** | next direction/IA revision |
| 3 | D1/D4/D5/D9 design identity, distinctiveness, visual grammar, restraint | **OPEN** | next direction revision + blind screenshot gate |
| 4 | p2 IA artifact regenerated to the §16 contract | **SPECIFIED** | next IA revision |
| 5 | Render gate script not yet implemented | **NOT STARTED** | facelift a5 |
| 6 | Facelift implementation (a1–a7) | **NOT STARTED** | facelift workflow |
| 7 | Mobile `ON-G7` deferral | **ACCEPTED (documented)** | kept with the §16 contract |
| 8 | Deferred external notifications | **ACCEPTED (documented)** | unchanged |

## 7. Reproduce

```bash
# 1. Rebuild the taxonomy and regenerate the reduction with the committed builders
python3 experiments/research/control_room/build_taxonomy.py
python3 experiments/research/control_room/reduce_knowledge.py   # prints "unresolved refs: 0"

# 2. Re-check support arithmetic and reference resolution
python3 - <<'PY'
import json, glob
root='experiments/research/control_room'
t=json.load(open(f'{root}/taxonomy.json'))
recs=[]
for p in glob.glob(f'{root}/corpus/*.jsonl'):
    recs += [json.loads(l) for l in open(p) if l.strip()]
for n in t['nodes']:
    if n['id'] in t['crosswalk'] and n['kind']!='group':
        labels=set(t['crosswalk'][n['id']])
        got=sum(1 for r in recs if labels & set(r.get('techniques',[])))
        assert got==n['support'], (n['id'], got, n['support'])
print('support arithmetic: OK')
PY

# 3. Guard the docs + research rail
python3 -m pytest tests/test_docs_drift_watchdog.py tests/test_research_fetch.py -q
```

**Doc lifecycle.** The brief, the IA, and all four repair review docs carry `status: accepted`
(`tests/test_doc_lifecycle.py`). The pre-existing, unrelated `flash_ladder_score_review.md`
missing-status failure is the only lifecycle failure in the tree.

## 8. Verdict

The repair campaign delivered every endpoint and re-ran all three adversaries. The brief now carries
the repaired supports (with the E1/E4 caveat), the reworked run-first direction, the glance IA
mapping, the render gate and one-resting-screen glance check, and a complete 25-finding disposition
ledger. On the campaign's two central acceptance claims it is **CONDITIONAL**: zero-promotion support
and the universal no-interaction glance contract are not yet clean. The correct next step is a
repair pass for E1/E4/E5 and a design revision that closes D1/D4/D5/D9, followed by the render gate —
not acceptance of this brief as design-complete.
