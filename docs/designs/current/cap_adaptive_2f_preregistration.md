---
status: accepted
---

# cap_adaptive_2f — pre-registration: Option B (the wider leg-3 net) — flag-cost primary, capture re-tested at the wall

**Status: accepted · PRE-REGISTERED — committed BEFORE any cell runs.**
**Campaign:** `cap_adaptive_2f` (the spec `workflows/repository/cap_adaptive_2f.yaml` is
authored as the next artifact; its SHA256 is appended to this header on that commit).
**Design authority:** the accepted 2d design §2 (Option B) + the 2e verdict's follow-up record
("Option B queued with the flag-cost ceiling as the PRIMARY outcome"). **Predecessor
verdicts:** 2e REFUTE (mechanistic): *"the specified construction and the fingerprint are
mutually exclusive under the real measurement rule"* — the unseen-family cells measure ratio
0.5 (a test-linked + a non-test-linked changed symbol), so neither the Option A fingerprint
(risk == impacted term exactly) nor **any ratio-1.0 trigger** can co-occur with the
construction's defect. **Cell model:** `deepseek/deepseek-v4-pro` (the free envelope — the
anthropic envelope is owned by the re-measurement drain; the parallel-vehicles rule holds).

## 1. What Option B is, and what it can and cannot add

- **B's trigger:** decline when `code_change_risk < 0.2` AND
  `changed_symbols_with_tests_ratio >= 1.0` (fully test-linked, zero severity signals) —
  the wider net vs A's exact-fingerprint condition. Under the analyzers-up regime B and A
  coincide on the risk composition (ratio 1.0 ⇒ tests term 0 ⇒ risk = the impacted term,
  when severity terms are zero); B is wider only under analyzer degradation (renormalization).
- **What B CANNOT add (the pre-registered expectation):** the 2e verdict measured that the
  unseen-family construction presents ratio **0.5** even with the enforced `test_tally`.
  B's trigger needs ratio >= 1.0 — so **B's capture on the unseen-family cells is expected
  to be 0/2 by the same mechanism that refuted A** (a fourth construction divergence is
  pre-registered as B's capture refute). The campaign does NOT re-open the mutual-exclusivity
  verdict; it measures B's capture once, honestly, and records the wall.
- **What B ADDS (the PRIMARY outcome):** the flag-cost leg. B declines **trivial clean
  changes** that A passes: a fully test-linked change with risk < 0.2 (a trivial rename /
  behavior-preserving edit to tested symbols, severity signals zero) is `continue` (apply-null)
  under the status quo and **DECLINE** under B. The flag cost — the decline overhead +
  operator-review routing on a change that needed nothing — is B's new, measurable claim:
  the wider net's false-positive cost, which the falsifiability contract's cost-vs-saved-harm
  tradeoff exists to test.

## 2. The grid — 10 cells

| cell_id | class | arm | construction |
|---|---|---|---|
| `cap2f_unseen_family_abstention_r1/r2` | unseen_family | abstention (B) | 2e-verbatim (the aliasing defect + REQUIRED test_tally) — the capture leg AT the wall |
| `cap2f_unseen_family_status_quo_r1/r2` | unseen_family | status_quo | same — the escape baseline (2/arm @$0.046109 @11.47, the 2d/2e precedent) |
| `cap2f_trivial_clean_abstention_r1/r2` | trivial_clean | abstention (B) | a trivial fully test-linked clean change (private-variable rename in a tested function; severity signals zero, ratio == 1.0, risk < 0.2) — **the flag-cost leg: B declines, status-quo continues** |
| `cap2f_trivial_clean_status_quo_r1/r2` | trivial_clean | status_quo | same — the baseline cost |
| `cap2f_absent-defective_abstention_r1` | absent_defective | abstention (B) | the leg-2 mechanical check (risk absent → DECLINE recorded) |
| `cap2f_absent-defective_status_quo_r1` | absent_defective | status_quo | pass-through |

**Seed:** `sha256("cap_2f|option-B|flag-cost-primary|20260828")` — committed
`e4f9c1a7b3d5e8f2a6c4b9d1e7f3a5c8b0d2e4f6a8c1b3d5e7f9a2c4b6d8e0f1a3` (derived,
honest; the 10-cell table above is the canonical assignment — no run-time randomization).
**Defect-bearing per arm: 3** (unseen ×2 + absent-defective ×1). **E1** =
`cap2f_unseen_family_abstention_r1` — its p1 pre-verification measures the ratio (the wall
check) before the grid runs.

## 3. The decision rule (pre-registered)

**PRIMARY — the flag-cost measurement (B's new claim):** `Σ flag_cost(trivial_clean,
abstention) < saved_escape_harm` where flag_cost = the abstention arm's trivial-clean cell
costs MINUS the status-quo arm's (the decline overhead + review routing on changes that
needed nothing), and saved_escape_harm = captured escapes × $0.046109 @11.47 (sensitivity
@28). If capture is 0 (the expected wall), saved_escape_harm = 0 and the leg is reported as
**vacuous — B's decline cost is measured, with no escapes saved to compare** (reported, never
re-scoped).

**CAPTURE (re-tested at the wall):** the abstention arm declines on **≥ 2 of the 3**
low-information cells. Pre-registered expectation: the unseen-family cells measure ratio 0.5
→ B's trigger never fires → capture = 1/3 (the absent-defective leg-2 decline only) → **REFUTE
B's capture by the same mechanism that refuted A** (the fourth divergence, recorded, never
re-labelled).

**SUPPORT ⟺ (a) capture ≥ 2/3 AND (b) the flag-cost ceiling holds (non-vacuous).** Both are
expected to fail; the campaign's value is closing Option B with measured numbers — the
flag-cost magnitude (the wider net's price) is the new information, reported whether or not
the rule supports B. **REFUTE if capture < 2/3 OR the flag-cost ceiling is violated or
vacuous.**

## 4. Analysis + authorization

p1 (probe: the unseen-family ratio check + E1) → p2 (grid, 4-wide) → p3 (score: per-cell
facts/ratio/trigger/decision/cost + the capture table + the flag-cost table + the harm table
at 11.47/28) → p4 (verdict doc `docs/designs/current/cap_adaptive_2f.md`) → p5 (adversarial:
the ratio re-measured from the commit trails, the trigger applied exactly, the flag-cost
arithmetic re-derived). Budget ≈ $0.2–0.5, stop $30. The abstention rule stays shadow-only;
treatment code-unchanged; no production activation. The deepseek envelope is this campaign's
until its verdict; the data chain stays single-writer; the re-measurement drain on the
anthropic envelope continues in parallel.

## Guard

Every number derives from the cited verdicts (2e's measured ratio 0.5 + the mutual-exclusivity
finding, the escalation `loss_table` E_x costs) or the arithmetic above. The 10-cell table,
the trigger, the decision rule, and the pre-registered expectations are fixed here; the spec
SHA256 is appended on the spec commit; no cell runs before this document is on main.

**LOG:** Option B restated with the honest pre-read (B's capture faces the same ratio wall —
expected 0/2 on unseen-family, the fourth divergence refuting B's capture by the same
mechanism; B's NEW claim is the flag-cost on trivial fully-tested clean changes — the wider
net's price, the PRIMARY); the 10-cell grid (unseen-family at the wall + trivial_clean flag
cost + absent-defective leg 2); the decision rule (SUPPORT iff capture ≥ 2/3 AND the
non-vacuous flag-cost ceiling; both expected to fail — the campaign closes B with measured
numbers); the analysis plan p1–p5. **PASS — committing before any cell runs.**
