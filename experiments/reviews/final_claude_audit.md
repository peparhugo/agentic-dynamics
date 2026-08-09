# Final Soundness Audit (v3) — AI FinOps Framework

**Date:** 2026-08-09
**Auditor:** Third-pass (final) soundness audit
**Scope:** Verify the post-v2 fix batch; classify residual issues as launch-blocking vs shippable
**Prior audits:** v1 (`claude_soundness_audit.md`), v2 (`claude_soundness_audit_v2.md`)
**Audited at:** commit `f108636` (working tree clean for audited files)

---

## Verdict Up Front

**One launch-blocking issue remains: `methodology.html:163` claims "Every term was measured
empirically" — contradicted by line 54 of the same page.** It is a one-line fix.

Everything else verified in this pass is either fixed or shippable with notes. The
evidence.html:121 "near-zero vs 33%" contradiction flagged in v2 **was already fixed in
commit `f108636`** — the summary that prompted this audit is stale on that point.

---

## 1. Verification of Claimed Fixes

All eight items claimed as verified were independently re-checked against the working tree.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | 4 crash bugs fixed | **CONFIRMED** | Fix signatures present: `src/instrument/adapter.py:59` (invoke signature), `src/instrument/lab_book.py:43,65` (attribute paths + getattr fallback), `src/instrument/recovery.py:86-97` (per-trajectory step→tool maps), `src/instrument/opencode.py:408-421` (direct per-event test-count read, fallback only when nothing matched) |
| 2 | 201/227 test_results real | **CONFIRMED** | `experiments/results/_results_summary.json` `_meta`: `total_entries: 227`, `valid_entries: 201`, `narrated: 26`. Programmatic count of non-null `test_results`: 201. The 26 nulls are documented narration failures (no code produced) — nulls are correct there, not missing data |
| 3 | 17 tests passing | **CONFIRMED** | `python3 -m pytest tests/ -q` → `17 passed in 0.15s` (test_adapter, test_pricing, test_recovery, test_perturb) |
| 4 | Operators match docs | **CONFIRMED** | `src/instrument/perturb.py:596-654`: exactly 4 ops classed `manifold` (inject_alien_vocab, shift_framing, reverse_causality, force_abandonment); identical to `_MANIFOLD_OPS` in `src/instrument/lab_book.py:12` |
| 5 | Pricing unified | **CONFIRMED** | `src/instrument/efficiency.py:38-50`: single clean table, consistent keys across deepseek/anthropic/openai; matches figures quoted on evidence.html (cache $0.14 read / $3.75 write, $15/Mtok output) |
| 6 | False claims removed | **CONFIRMED** | Zero grep hits for "executive dash" or "no heuristic" across `firebase/public/`. Hero now says "Correctness uses calibrated heuristics" (`index.html:52`); provenance tags [M]/[C]/[H]/[X] on evidence.html:67 |
| 7 | Terms unified | **CONFIRMED** | v2's LOW issue fixed: `framework.html:312` now reads "Escalation rate 21.4%" (was "Retry rate"), distinct from WOC's r=0.115 (`framework.html:95,127`). Flail/Grit terminology coherent across `glossary.html:33,103`, `framework.html:91`, `evidence.html:110` |
| 8 | Counts unified 249 / $64.98 | **CONFIRMED at runtime, with static residue** | Canonical source `data.js:13,15` (`sessions_total: 249`, `total_cost: 64.9827`). `app.js:30-61` injects into every `[data-stat]` span — all rendered heroes/footers show 249 / $64.98. Residue: static prose and meta tags still say 248 in ~10 places (see §3.2), and `evidence.html:72` carries a $59.45 no-JS fallback |

---

## 2. Re-Check of the Two Reported Remaining Issues

### 2.1 `evidence.html:121` — "near-zero" claim vs 33%

**Verdict: ALREADY FIXED (commit `f108636`). The reported issue does not exist in the
current tree.**

The v2-flagged text read: "Claude burns 44% … Nano hits 100% penalty rate. DeepSeek and
GPT-5.6-fast hit near-zero" — contradicting the table showing GPT-5.6-fast at 33%.

Current `evidence.html:121` reads: "Claude burns 11% … Nano hits 14% penalty rate.
**DeepSeek and GPT-5.6 hit near-zero.**"

Cross-check against `data.js` narration rates: DeepSeek 8%, GPT-5.6 6%, GPT-5.6-fast 33%,
GPT-5.5 50%. The claim now names GPT-5.6 (6%), not GPT-5.6-fast (33%). The table at
lines 112-119 matches data.js exactly for all 8 models. No contradiction remains.

**Residual (non-blocking) wording nit:** "near-zero" for 6-8% is loose — the table
directly above shows the numbers, so a precise reader may object. Recommended:
"DeepSeek and GPT-5.6 post the lowest rates (8% and 6%)." Cosmetic; the directional
claim is now supported by the data beside it.

### 2.2 `methodology.html` — "248" and "every term measured"

**Verdict: CONFIRMED — this is the one remaining launch-blocking item.**

`methodology.html:163` (caption directly under the unified cost equation):

> "C₀ = model choice, ε = cost of verbalized reasoning, β·N² = compounding codebase
> growth, EPM = energy market exposure, v = scaling speed. … **Every term was measured
> empirically from the 248-session experiment corpus.**"

This is contradicted by `methodology.html:54` — **the same page**:

> "Cost drivers (C₀, P, ε, r) are measured from the 227-session corpus. **Modeling
> parameters (β, EPM) are externally calibrated.** Analysis outputs (escape scores,
> strategy) are **heuristically computed**."

Term-by-term: C₀, P, ε, r are measured [M]; β and EPM are external [X]; v is a
user/scenario input; A (architecture multiplier) is assigned. "Every term was measured
empirically" is false for at least β, EPM, v, and A. This is the same claim-class as
the "no heuristic estimation" falsehood removed after v1 — resurrected in one sentence
on the page whose entire purpose is provenance honesty. A technical reader comparing
line 54 to line 163 catches it in seconds. The line also says "248-session" against the
page's own hero stat of 249 (`methodology.html:46`).

**Fix (one line):** replace the final sentence of line 163 with e.g. "Cost drivers
(C₀, P, ε, r) are measured from the experiment corpus; β and EPM are externally
calibrated — see provenance tags [M]/[C]/[H]/[X]." This also removes one 248.

---

## 3. Launch-Blocking vs Shippable

### 3.1 LAUNCH-BLOCKING (1 item)

| # | Issue | Location | Why blocking | Effort |
|---|---|---|---|---|
| B1 | "Every term was measured empirically" — false provenance claim contradicting the same page's TL;DR (β, EPM externally calibrated; v, A not measured) | `methodology.html:163` vs `:54` | Same falsehood class the launch was held for after v1 ("no heuristic estimation"). Self-contradiction within a single page; undermines the framework's core credibility promise (provenance tagging). Trivially checkable by the target audience | One sentence |

### 3.2 SHIPPABLE WITH NOTES (fix cheap, none blocks launch)

| # | Issue | Location | Severity | Note |
|---|---|---|---|---|
| S1 | Static "248" drift vs canonical 249 | `methodology.html:6,54,163`; `framework.html:6,88,127`; `evidence.html:6,67,144`; `index.html:122` | LOW | Rendered `[data-stat]` numbers all show 249 at runtime; the drift is in static prose and `<meta>` descriptions (which JS cannot rewrite — they are what search/social previews show). The prose 248s are internally consistent (227 experiment runs + 21 TS sessions = 248; 203+26+19 = 248 on `evidence.html:144`), so this is a 1-session provenance drift between data.js and prose, not arithmetic error. Pick one number, state its definition once, sweep the 10 spots |
| S2 | "near-zero" describing 6-8% flail rates | `evidence.html:121` | LOW | No longer contradicts the adjacent table (see §2.1); loose wording only |
| S3 | $59.45 no-JS fallback for total cost | `evidence.html:72` | LOW | Has `data-stat="cost"` so runtime shows $64.98; no-JS readers and scrapers see the stale figure. Update the hardcoded fallback to 64.98 |
| S4 | Chart labels "r=21% (measured avg)" / "r=11.4% (Claude)" coexist with WOC r=11.5% | `framework.html:384` | LOW | The v2 table-label fix landed (`:312` says "Escalation rate"); chart legend still mixes escalation r and WOC r without saying which is which. Rename legend entries when convenient |
| S5 | 26/227 entries have null test_results | `_results_summary.json` | ACCEPTED | Correct behavior — these are narration failures with zero code files; a test run would be meaningless. Documented in `_meta` and on evidence.html |

### 3.3 Previously blocking, now resolved

| v2 issue | Status |
|---|---|
| HIGH: $59.45 vs $64.98 across pages | **Resolved at runtime** — all cost displays carry `data-stat="cost"` and render $64.98 from data.js (S3 fallback nit remains) |
| MEDIUM: evidence.html:121 names GPT-5.6-fast (33%) as "near-zero" | **Resolved** in `f108636` (S2 wording nit remains) |
| LOW: "Retry rate: 21.4%" mislabel | **Resolved** — now "Escalation rate" (`framework.html:312`) |

---

## 4. Final Readiness Assessment

| Dimension | v1 | v2 | v3 (this audit) |
|---|---|---|---|
| Crash bugs | 4 | 0 | 0 |
| Measurement bugs | 3 | 0 | 0 |
| Operator/doc mismatches | 4 | 0 | 0 |
| Real test_results | ~0 | 201/227 | 201/227 (confirmed) |
| Passing tests | 0 | 17 (by inspection) | 17 (executed: `17 passed in 0.15s`) |
| False claims | 2 major | 0 | **1** (methodology.html:163) |
| Cross-page numeric contradictions (rendered) | several | 1 HIGH | 0 |
| Static/meta numeric drift | — | — | ~10 spots, 1-session drift (LOW) |

**Readiness: ~95%. Ship after the one-line B1 fix.**

The instrument code, pipeline outputs, pricing, operator taxonomy, and test suite are
sound and mutually consistent. The rendered site tells one coherent numeric story
(249 sessions, $64.98, 224 reports) via data.js injection. The only remaining item that
meets the bar this project set for itself — no claim the data cannot back — is the
"every term was measured" sentence on the methodology page. Fix that sentence, do the
S1 sweep in the same commit if convenient, and launch.
