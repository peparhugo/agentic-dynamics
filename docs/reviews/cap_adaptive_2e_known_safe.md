# cap_adaptive_2e — known-safe list

**Campaign:** `cap_adaptive_2e` (`cap_adaptive_2e@0.1`). **Adversarial phase p5.**
Every item below was verified mechanically (commits, hashes, diffs, re-derivations) during the
adversarial review (`docs/reviews/cap_adaptive_2e_adversary.md`). Nothing in this list is assumed.

| # | item | evidence |
|---|---|---|
| K1 | Preregistration committed before any cell ran | `docs/designs/current/cap_adaptive_2e_preregistration.md` @ `d1a0ad777`, on main before the spec commit `3458f916d`; no `cap_adaptive_2e` results existed at that commit |
| K2 | Spec SHA pinned in the preregistration header | `sha256sum workflows/repository/cap_adaptive_2e.yaml` = `b0ad1c4f…` matches the header |
| K3 | Exactly the 6 pre-registered cells ran, nothing unlisted | `cells/` holds exactly the §3 table's 6 cell ids |
| K4 | Fingerprint divergence is real (not a scoring artifact) | raw facts in every cell record + the p1 probe: ratio 0.5, risk 0.18, expected 0.08; risk re-derived as `0.20·0.5 + 0.20·0.4` |
| K5 | `test_tally` present in every unseen-family implement commit | `git log -S'test_tally'` on all 4 unseen-family worktrees |
| K6 | Absent cells refused (leg-2 mechanical path) | `seam.refused = true`, `code_change_risk` absent in both absent cells |
| K7 | Abstention DECLINE legs provable in commit trails | no apply/rework commit exists; decline = provable-null (apply skipped) |
| K8 | Status_quo applied exactly as proposed | continue = null; final commits still carry the defect (escape baseline intact) |
| K9 | Treatment code untouched (shadow-only rule) | `git diff 3458f916d..HEAD -- src/agentic_dynamics/` empty |
| K10 | Generated surfaces untouched | no `.opencode/` / `.claude/` changes in the campaign commits |
| K11 | No secrets introduced | grep of the campaign diff for key/password/secret/token: clean |
| K12 | Harm arithmetic | 3 escaped × $0.046109 = $0.138327 @11; × $0.112588 = $0.337764 @28; E_x 11.4671 (sol, n=1) + E_x 28 sourced, both cited |
| K13 | Budget within the $30 stop | measured campaign cost ≈ $0.052 total (6 cells + probe), far under the stop |
| K14 | Outcomes independent | runtime pytest on immutable final commits + post-hoc evaluator, per cell |
| K15 | Decision rule computed from recorded fields, nothing imputed | validation JSON traces every verdict number to a record field |

**Not known-safe** (deliberately flagged, see the adversary): the preregistration's committed seed
hash (K-not-safe-1: `0f3e7c1b…` ≠ `sha256("cap_2e|reconstruct-unseen-family|fingerprint|20260828")`
= `d8f9bb19…`) and the §1 construction premise (K-not-safe-2: claims 2c measured ratio 1.0; the
recorded 2c facts measure ratio 0.5). Both are preregistration-integrity defects, recorded as
FAILED findings, and neither affects the enumerated grid, arms, or thresholds.
