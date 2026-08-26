---
status: accepted
---
# cap_session_routing_prospective — adversarial verification

**Role:** adversarial verifier (p5). **Source revision:** `6f27cc21e` (p4 verdict committed).
**Score JSON:** `experiments/results/cap_session_routing_prospective/cap_session_routing_prospective_score_20260826T160605Z.json`
(sha256 `288e0486d684b4f5f8809f626297ce521848de47e233d9482600dd06ae1a4402`).
**Validation trace:** `cap_session_routing_prospective_p3_validation.json` (sha256 `82563a32…`).
**Ledgers:** `cap_session_policy_phase_ledger_<cell>.json` (+ `_escalated.json` for the escalate
mechanism proof). **Retro:** `experiments/results/session_routing_retrospective.json`.

## Findings table

| # | Attack (order) | Result | Disposition |
|---|---|---|---|
| F1 | (1) arm integrity — session lineage proves the assigned arm | **FINDING** | accepted limitation: `continue` and `fork_cached` executed the SAME chained-session mechanism — no cell reuses a session_id; the "reused session_id = continue" discriminator does not hold; 0 mislabeled cells but the two arms are mechanically indistinguishable |
| F2 | (2) escalate provability — failed phase → new session → other model in the ledger | **PASS** | mechanism proven in a real ledger chain (forced-failure proof cell); accepted limitation: 0/6 grid cells triggered, so grid escalate numbers are the no-escalation case and the 3.1× premium is untestable |
| F3 | (3) cache semantics — fork_cached cache reuse is real, not asserted | **PASS** | fork_cached follow-up cache_read_tokens > 0 is measured; accepted limitation: cache reads are not arm-discriminating (fork_blind also > 0 — provider prefix caching) |
| F4 | (4) retro comparison apples-to-apples — same metrics, n stated | **FINDING** | accepted limitation: retro "verified" = per-phase commit-ok gate, live "verified" = test_executed_success; different gates + ~200× cost-base mismatch; only the within-regime ratio is a proxy |
| F5 | (5) randomization honesty — cells listed before running | **FINDING** | accepted limitation: no committed pre-run candidate snapshot exists; the execution manifest was rewritten at p2 end (mtime after the first run); candidate-first rests on the driver's read-only-from-manifest enforcement + p2 log assertion |
| F6 | (6) usual suite — credentials/hashes/not-run/fabricated numbers/actuation | **PASS** | no finding: all 5 cited hashes verify, no secrets, 24 scored = 24 listed (0 not-run), per-arm aggregates recomputed from raw ledgers (continue-arm 1e-6 delta is a rounding-order artifact, cpvo agrees to 6dp), no actuation applied |

**No attack falsified the campaign's core claim** (the descriptive per-arm table and the
"3.1× premium untestable" verdict stand). Three accepted limitations sharpen the verdict:
F1 (continue ≡ fork_cached mechanically), F4 (retro/live verified gates differ), F5 (candidate
listing not independently auditable from committed artifacts).

---

## Attack-by-attack

### (1) Arm integrity — does the session lineage prove the assigned arm? — **FINDING** (F1)

**Attack:** the acceptance criterion is "reused session_id = continue; new session + cache =
fork_cached; model switch after a failed phase = escalate". If a cell's recorded session
behavior mismatches its assigned arm, it must not be scored under that arm.

**Evidence (re-derived from the ledgers + the opencode session store):**

| cell | arm | implement session | verify session | session_id reused? | verify fork marker |
|---|---|---|---|---|---|
| `cap_sesspol_continue_pro_r2` | continue | `ses_fc1658944ffeX6…` | `ses_fc163c66effeTa…` | **No** | `(fork #1)` → chained |
| `cap_sesspol_fork_cached_pro_r1` | fork_cached | `ses_fc14f152effeAW…` | `ses_fc14d6a0fffeim…` | **No** | `(fork #1)` → chained |
| `cap_sesspol_fork_blind_pro_r1` | fork_blind | `ses_fc16b9192ffeyk…` | `ses_fc169da87ffeQG…` | No | plain → cold |

The runner's `fork=True` passes `--session <prev> --fork`, which creates a **new** forked
session per phase. Consequently **no cell in the grid reuses a session_id** — including every
`continue` cell. The `continue` and `fork_cached` arms therefore executed **identical
mechanics**: a fresh forked session per phase carrying the prior context prefix (fork marker
`[false, true]`). Only `fork_blind` is mechanically distinct (`[false, false]`), and `escalate`
equals `continue` until a failure fires (none did).

**Result:** 0 mislabeled cells (p3 validation: `cells_invalid_excluded` = `[]`) — no cell was
scored under an arm it didn't execute. But the specific discriminator the design asked for
("reused session_id = continue") is **unsatisfied as written**: `continue` did not run as "one
session for the whole cell"; it ran as the same chained-session mechanism as `fork_cached`.

**Fix/limitation (accepted):** fixing this requires a runner capability that does not exist —
a resume-the-same-session (no-fork) mode. The campaign flagged the sharing
(`continue`/`fork_cached` share the chained-session mechanism) but the review sharpens it: the
**continue-vs-fork_cached cpvo contrast ($0.005921 vs $0.006093, a 2.8% gap at n=6) is label
noise, not a causal policy contrast.** Residual risk: a reader could take the per-arm ranking
at face value; it must be read as three behaviors — `fork_blind` (cold) vs the chained cluster
(continue/fork_cached/escalate) vs escalate (chained + untriggered escalation).

**Re-test:** the fork markers are re-derived from the committed ledgers + session store
(independent of the manifests); re-running this check reproduces the table above.

**Re-stated verdict (F1):** the meaningful live contrast is `fork_blind` (cold sessions,
$0.005322, lowest context growth 1.357) vs the chained mechanism; the continue/fork_cached
rank positions are not a policy finding.

### (2) Escalate provability — is the chain in the ledger, not narration? — **PASS** (F2)

**Attack:** "the failed phase → new session → other model chain is in the ledger, not
narration"; a narrated-but-unexecuted escalation is a failed finding.

**Evidence (merged ledger of the escalate mechanism proof — real run ledgers, not prose):**

| phase | kind | status | model | session | error |
|---|---|---|---|---|---|
| implement | agent | **failed** | `deepseek/deepseek-v4-flash` | — | `Timeout after 1s` |
| implement | agent | **ok** | `deepseek/deepseek-v4-pro` | `ses_fc132621fffe…` (NEW) | — |
| test | test | ok | — | — | — |
| verify | agent | ok | `deepseek/deepseek-v4-pro` | `ses_fc130a127ffe…` | — |

`run1_ok=False`, `run2_ok=True`; the failed flash phase is followed by a **new** session on the
**other** model in the **same worktree** — the exact failed-phase → new-session → other-model
chain, in `cap_session_policy_phase_ledger_cap_sesspol_escalate_mechanism_proof.json` +
`_escalated.json`.

**Result:** PASS — the escalation mechanism is executable and ledger-provable. **Accepted
limitation:** **0/6 grid escalate cells triggered** (all completed on the assigned model's
first attempt), so the grid's escalate numbers measure the no-escalation-needed case, the live
0.976× is a parity statement, and the 3.1× premium is **untestable** — exactly as the verdict
states. Residual risk: the proof forced the failure (proof-harness spec variant, 1s implement
timeout) rather than a natural grid failure; it demonstrates the mechanism, never the premium.

**Re-test:** re-run the escalate arm against a failing first attempt (a defect-bearing cell)
and confirm the resumed ledger shows the model switch; the proof cell already demonstrates the
path.

### (3) Cache semantics — is fork_cached's cache reuse real, not asserted? — **PASS** (F3)

**Attack:** fork_cached's cache reuse must be measured (`cache_read_tokens > 0`), not asserted.

**Evidence (ledger `cache_read_tokens` / `cache_hit_rate` on the follow-up verify phase):**
`fork_cached_pro_r1` verify `27264` (0.70); `fork_cached_flash_r1` verify `14208` (0.56). Real,
positive, measured.

**Result:** PASS — the reuse is real. **Accepted limitation:** the same measure is **not**
arm-discriminating: `fork_blind_pro_r1` verify `45184` (0.82) — provider prefix caching (system
prompt + tools) serves cache reads even in cold sessions. The arm discriminator is the session
fork marker, not cache_read_tokens (the campaign flagged this in the verdict; the review
confirms it). Residual risk: low — no claim in the verdict rests on cache_read_tokens as an arm
signal; the per-arm cache utilization figures are reported descriptively.

### (4) Retrospective comparison — apples-to-apples, same metrics, n stated? — **FINDING** (F4)

**Attack:** the retro numbers and the live numbers must measure the same thing, with n on both
sides.

**Evidence:** the retro's own definition (retro `notes[0]`): *"verified success = the phase
committed with status ok (the per-phase gate)"*. The live scoring used **test phase
`test_executed_success`** (pytest pass). These are **different verified gates**. The cost base
also differs by ~200× (retro = full-size workflow cells averaging $1.2–3.9/run; live = a tiny
calibration cell at $0.003–0.009). n is stated on both sides (retro fork_cached n=246, escalate
n=7; live n=6 per arm) — the n-stating requirement holds.

**Result:** **FINDING** — the comparison is not metric-identical. The verdict flagged the
cost-base mismatch but not the verified-gate mismatch; this review adds it. Both gates happen
to yield 100% here, so the direction is unchanged, but "verified" means something different on
each side, and absolute cpvo ($1.2658 vs $0.0061) is not comparable across regimes.

**Fix/limitation (accepted):** the retro corpus cannot be re-scored with a pytest gate (its
ledgers predate `test_executed_success`), and the live cells cannot be scored with the retro
commit gate retroactively. The honest statement — already in the verdict, now with the gate
caveat — is that only the **within-regime ratio** (3.10× retro, 0.976× live) is a comparison
object, and even that is compromised by the untriggered escalate arm. Residual risk: a reader
quoting "$1.2658 vs $0.0061" without the gate/base caveat would over-read the difference.

**Re-test:** not re-runnable; the caveat is recorded in both this review and the verdict.

### (5) Randomization honesty — were the cells listed before running? — **FINDING** (F5)

**Attack:** the cells must have been listed in the manifest before running — no cherry-picking
after the fact.

**Evidence:**
- The p2 execution manifest lists **23** cells; exactly **23** per-cell manifests exist (plus
  E4 from p1) → the scored set equals the manifest set (24). No unlisted cell was scored.
- **But** no committed artifact shows the manifest in a pre-run "candidate" state: the p2
  commit (`0f015fe1e`) contains the execution manifest already updated to `completed` statuses,
  and the p1 candidate manifest was likewise committed post-update.
- The execution manifest's working-tree mtime (18:04) **postdates** the first cell manifest
  (17:12) because the file was rewritten at p2 end (status update) — so mtime is not evidence
  of candidate-first.
- The mechanism-proof cell (`escalate_mechanism_proof`) ran **without** being in the manifest —
  correctly excluded from scoring and labeled "NOT a scored grid cell", but it is a real
  non-manifest execution.

**Result:** **FINDING** — candidate-first is asserted (p2 log check: "execution manifest written
BEFORE any cell ran") and mechanically enforced (the driver reads cells only from the manifest),
but it is **not independently auditable** from committed artifacts.

**Fix/limitation (accepted):** the pre-run snapshot should have been committed before execution
(an immutable `candidate`-state manifest). Not retroactively fixable. Residual risk: **low** —
the enforcement is structural (the driver refuses unlisted cells; the scored set exactly equals
the manifest set), so the candidate-first claim is credible even though its audit trail is
weaker than it could be. The mechanism-proof cell is documented and unscored.

**Re-test:** a future campaign must commit the candidate manifest before the first cell; this
campaign's evidence rests on the driver contract + the equality of listed-vs-scored cells.

### (6) Usual suite — credentials, hashes, not-run, fabricated numbers, actuation — **PASS** (F6)

- **Credentials:** regex scan of all 60 campaign JSON artifacts + the verdict doc for
  `sk-*`/`AKIA*`/`ghp_*`/`password=`/`api_key=` patterns → **0 hits**.
- **Hashes:** all five SHA256s cited in the verdict (cell spec, p1 candidate manifest, p2
  execution manifest, p3 score JSON, p3 validation JSON) recompute to the exact committed
  files and are correctly cited → **PASS**.
- **Not-run cells:** 24 scored = 24 listed (E4 + 23); the mechanism-proof cell is explicitly
  excluded from scoring → **PASS**.
- **Fabricated numbers:** every per-arm aggregate was independently recomputed from the raw
  phase ledgers (sum of `phases[].cost_usd`, `test_executed_success` on the test phase). All
  four arms match the score JSON to 6dp. The lone continue-arm delta (0.035525 vs 0.035524) is
  a **rounding-order artifact** — the score JSON rounds each cell then sums, the recomputation
  sums then rounds (`0.035524687`); cpvo agrees to 6dp on both → **PASS**.
- **Actuation:** no control action was applied — the campaign is measurement-only; no
  `actuation` knowledge envelope was written (actuation_ingestion still has zero call sites);
  `session_routing_v1` remains proposal-only → **PASS**.

---

## Re-stated verdict

The verdict document stands with three recorded limitations:

1. **F1 — the live grid measured three mechanisms, not four:** `fork_blind` (cold sessions) is
   the only mechanically distinct arm; `continue` and `fork_cached` share the chained-session
   mechanism, so their 2.8% cpvo gap is not a policy contrast.
2. **F4 — retro vs live "verified" use different gates**, so the comparison is a within-regime
   ratio (3.10× vs 0.976×), not an absolute-cost comparison, and the premium is compromised by
   the untriggered escalate arm.
3. **F5 — the escalation premium (3.1×) remains untestable in this grid** (0/6 escalate cells
   triggered; mechanism proven, not estimated), and candidate-first listing is not auditable
   from committed artifacts (driver-enforced, low residual risk).

The descriptive per-arm finding — `fork_blind` lowest cost ($0.005322) and lowest context-token
growth (1.357) at n=6, flash ~3× cheaper than pro, no arm authorized — survives every attack.

**LOG: PASS** (no falsification; three accepted limitations sharpened).
