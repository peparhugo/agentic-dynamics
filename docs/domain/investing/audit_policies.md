---
status: accepted
---
# Investing Domain — Policy Audit (Stage-0 seeding)

**Role:** policy auditor. This document enumerates the candidate investing policies for the RRSP
domain and applies the load-bearing rule **literally**: a control rule (policy arm) is writable
only when every signal its `requires` names has a producer. It is the policy-side twin of
`audit_observable.md` (the observable-side audit), and every producer referenced below is one of
that document's signal IDs — a `requires` that names a signal the observable audit does not produce
is recorded `UNINSTRUMENTED`, never silently assumed.

**Scope.** Eight candidate policies, in two layers:

- **Constraint / invariant layer** — the "contract" rules that must hold before any tactical arm
  runs: `calls_only_invariant`, `no_short_delta`, `registered_account_limits`.
- **Tactical / control layer** — sizing, exits, selection, allocation, and review rules:
  `position_size`, `exit_rules`, `expiry_selection`, `crypto_cap`, `weekly_review`.

The observable audit's § 7 already mapped tactical arms P-1…P-11; this audit enumerates the
**invariant layer** (a–c) plus a stricter, operator-specific re-statement of four tactical rules
(d–h), and asks the harder question: *which of these can the decision engine actually enforce
today?*

---

## 1. How to read this document

### Provenance tags

Identical to `audit_observable.md` § "How to read":

| Tag | Meaning |
|-----|---------|
| `[M]` | **Measured** — directly readable from a stated source (broker statement, confirmation, export). |
| `[C]` | **Computed** — a deterministic reducer; inputs are stated. |
| `[X]` | **External** — a named third-party source (exchange, CRA, CIRO, CDS), consumed as published. |
| `[P]` | **Policy / operator-declared** — a rule the operator asserts, or data the operator records (thesis, proposed order, risk limit). |
| `[H]` | **Hypothesis** — subjective; never a measured input. |

An account rule (a "thou shalt / thou shalt not" the operator asserts) is `[P]` and, where it
rests on regulation, carries the `[X]` authority it leans on with the rule class named.

### Producer-status notation (the guard)

Every `requires` cell resolves to exactly one of:

- `✓ <producer>` — a producer exists: either a signal ID from `audit_observable.md` (e.g. `PS-8`),
  or a named `[C]` reducer over produced signals whose inputs are stated.
- `✗ UNINSTRUMENTED (→ <missing upstream>)` — no producer exists; the upstream producer that would
  unblock it is named, and the policy is recorded **pending-instrumentation** with its order.

**Guard:** a policy is `writable` **only** if every one of its `requires` resolves to `✓`. No
policy below is marked writable while any of its `requires` is `UNINSTRUMENTED`.

### The load-bearing rule, restated

> To make a policy, we need information. A control rule whose `requires` are not produced is
> unwritable; the compiler refuses it. An unwritable policy is recorded here as
> *pending-instrumentation*, with the producer chain that would unblock it, in dependency order.

---

## 2. Producer ground-truth (from `audit_observable.md`)

The only producers that matter for this audit are the ones the eight policies consume. The
observable audit established 45 signals; the subset relevant here, and their status:

| Producer | Meaning | Status today |
|----------|---------|--------------|
| `PS-1` | Position quantity, signed (shares/contracts) | `[M]` produced |
| `PS-3` | Position market value | `[C]` produced (= PS-1 × MD-1) |
| `PS-7` | Unrealized P/L per position | `[C]` produced (= PS-1 × (MD-1 − PS-2)) |
| `PS-8` | Account equity / NAV | `[C]` produced |
| `EX-1` | Fill record with side, qty, price, time, venue | `[M]` produced |
| `EX-4` | Assignment / exercise notice | `[M]` produced |
| `DR-1…DR-5` | Thesis → proposed → executed → delta → outcome | `[P]`/`[M]`/`[C]` produced (DR-1, DR-2 operator-declared) |
| `CX-7` | Registered-account contribution room | `[X]` produced (CRA NOA) |
| `MD-2` | Daily OHLCV bar | `[X]` produced (feeds a realized-vol reducer) |
| `MD-4` | Options chain (strikes, expiries, bid/ask, OI, volume) | `[X]` **not visible in registered accounts — UNINSTRUMENTED** |
| `MD-5` | Option greeks (delta…) | `[C]` gated on `MD-4` — **UNINSTRUMENTED** |
| `MD-6` | Implied volatility | `[C]` gated on `MD-4` — **UNINSTRUMENTED** |

This is the whole story: every `UNINSTRUMENTED` below traces to the **chain producer (`MD-4`)**
or, once, to a realized-vol reducer over `MD-2`. Those two gaps determine the writability split.

---

## 3. Instrumentation order (dependency-sorted)

Because an unwritable policy is recorded *with its instrumentation order*, the shared order is
fixed here once and referenced by step number:

| Step | Producer to instrument | Kind | Unblocks |
|------|------------------------|------|----------|
| **1** | `MD-4` — options-chain producer (named `[X]` MX/Cboe feed) | external, named-not-connected | steps 3 and 4 |
| **2** | `realized_vol` — `[C]` reducer over `MD-2` (std of daily log returns) | local reducer, no external dep | `position_size` |
| **3** | `MD-5` greeks + `MD-6` IV — `[C]` reducers over `MD-4` + pricing inputs | reducer over step 1 | `no_short_delta` |
| **4** | `dte` + `chain_liquidity` — `[C]` reducers over `MD-4` | reducer over step 1 | `expiry_selection` |
| **5** | `iv_rank` — `[C]` reducer over the `MD-6` IV time series | reducer over step 3 | `exit_rules` |

Step 2 is independent of the chain and is the cheapest win; steps 1→3→5 and 1→4 are chains off a
single missing producer (`MD-4`).

---

## 4. Candidate policies — one row per policy

| # | Policy | `requires` → producer status | Writable now? | Instrumentation order |
|---|--------|------------------------------|---------------|-----------------------|
| a | `calls_only_invariant` — long calls + covered calls only; no naked puts/calls | `open_option_positions(side,type,qty)` → `✓ PS-1` (signed) ⊕ `EX-1`/`EX-4`; `underlying_share_holdings` → `✓ PS-1`; `covered(short_call)` → `✓ [C]` reducer | **yes** | — |
| b | `no_short_delta` — net short delta is a contract invariant | `portfolio_net_delta` → `✓ [C]` reducer; `option_delta` → `✗ UNINSTRUMENTED (→ MD-5 → MD-4)` | **no** | step 3 |
| c | `registered_account_limits` — RRSP/TFSA eligibility, no margin | `account_type` → `✓ [M]` statement header; `contribution_room` → `✓ CX-7 [X]`; eligibility/margin → `[P]` constants (rest on `[X]` CRA/CIRO) | **yes** | — |
| d | `position_size` — size ∝ portfolio_value / vol | `portfolio_value` → `✓ PS-8 [C]`; `vol` → `✗ UNINSTRUMENTED (→ realized_vol over MD-2, or MD-6)` | **no** | step 2 |
| e | `exit_rules` — exit on iv_rank or pnl_since_entry | `iv_rank` → `✗ UNINSTRUMENTED (→ MD-6 → MD-4)`; `pnl_since_entry` → `✓ PS-7 [C]` (or `[C]` lot-reducer over `EX-1`) | **no** | step 5 |
| f | `expiry_selection` — pick expiry by dte + liquidity | `dte` → `✗ UNINSTRUMENTED (→ MD-4)`; `chain_liquidity` → `✗ UNINSTRUMENTED (→ MD-4)` | **no** | step 4 |
| g | `crypto_cap` — cap crypto weight | `portfolio_weights` → `✓ [C]` (= PS-3 ÷ PS-8); `crypto_asset_class` → `✓ [P]` symbol→class mapping | **yes** | — |
| h | `weekly_review` — reconcile thesis → outcome | `thesis→outcome chain` → `✓ DR-1…DR-5` (DR-1, DR-2 are `[P]`) | **yes** (conditional on `[P]` discipline) | — |

**Read:** 4 of 8 writable today (a, c, g, h); 4 pending-instrumentation (b, d, e, f), all but one
blocked by the single missing chain producer `MD-4` (`position_size` is blocked by the independent
`vol` gap).

---

## 5. Policy details and compliance

### (a) `calls_only_invariant` — long calls and covered calls only

**Invariant (`[P]`):** no naked calls, no naked puts; long calls and covered calls only.

- `requires:`
  - `open_option_positions(underlying, side ∈ {long, short}, type ∈ {call, put}, qty)` →
    `✓ PS-1` (signed position snapshot, `[M]`; contract: a short leg is a **negative** quantity)
    cross-checked by a `[C]` reduction over `EX-1` fill history (`[M]`, side-qualified) and `EX-4`
    assignment notices (`[M]`, which turn short legs into long/short share positions).
  - `underlying_share_holdings(symbol, qty)` → `✓ PS-1` (`[M]`).
  - `covered(short_call)` → `✓ [C]` reducer: `shares(symbol) ≥ 100 × qty(short_call)`.
- **Writable: yes.**

**Enforcement question (answered literally).** The `calls_only` invariant is enforceable **only if
the decision engine can see short exposure**. The producer that supplies that sight is the
**signed open-position record** — `PS-1` interpreted with sign (short option legs negative), ⊕ the
`[C]` reduction over `EX-1` fills, ⊕ `EX-4` assignment notices. If the operator's broker export
flattens option legs without a long/short sign (some CSV exports list contracts unsigned), the
invariant degrades to unverifiable: that is a **producer-contract requirement** on `PS-1`, not a
new signal. `[P]` authority: operator rule, *stricter than* the CIRO options-level floor — CIRO
level 2 already permits covered calls, protective puts, and long puts in a registered account; this
policy deliberately narrows to calls only.

### (b) `no_short_delta` — net short delta is a contract invariant, not a convention

**Invariant (`[P]`):** the portfolio's net delta (Σ position deltas) must never be negative.

- `requires:`
  - `portfolio_net_delta` → `✓ [C]` reducer `Σ share_qty·(+1) + Σ option_qty·100·delta(side)`.
  - `option_delta` → `✗ UNINSTRUMENTED` — `MD-5` greeks, itself gated on `MD-4` (the chain), which
    is **not visible in registered accounts** (`audit_observable.md` § 1 MD-5, § 8 G-1).
- **Writable: no → pending-instrumentation, step 3.**

**Reasoning (why this is not the same as (a)).** Under (a) alone the book is restricted to long
calls (delta ∈ (0, 1]) and covered calls (+100 shares − 100·Δ_call ∈ (0, 100)), so net delta is
*automatically* non-negative — but (b) is asserted as an **independent** invariant (defence in
depth). Enforcing it independently requires reading `option_delta`, which no producer supplies
today. Until `MD-5` exists, the only enforceable surrogate is to rely on (a) holding — a
substitution the load-bearing rule forbids: (b) is recorded `UNINSTRUMENTED`, not "writable via
(a)".

### (c) `registered_account_limits` — RRSP/TFSA eligibility, no margin

**Rule (`[P]`), resting on `[X]` CRA and `[X]` CIRO.** This is the one policy whose `requires` are
mostly *regulatory constants*, not market signals.

- `requires:`
  - `account_type ∈ {RRSP, TFSA, non-registered}` → `✓ [M]` broker-statement header (or `[P]`
    operator-declared).
  - `contribution_room` → `✓ CX-7 [X]` (CRA Notice of Assessment).
  - `qualified_investment_class` → `[P]` policy constant resting on `[X]` **CRA** — *Income Tax
    Act* ss. 146 / 146.2 (RRSP/TFSA), s. 207.01 (prohibited investments), and Reg. 4900
    (qualified investments). Consequence: **direct crypto is not a qualified investment** in a
    registered account; crypto *spot ETFs* (MD-8) are.
  - `margin_prohibition` → `[P]` constant resting on `[X]` **CIRO** margin rules and the account
    agreement — registered accounts are cash accounts; RRSP/TFSA assets cannot be pledged as
    margin collateral. **Structural** — no signal, enforced by `account_type` alone.
- **Writable: yes.**

**Compliance / external-authority tags:**

| Rule class | Authority (`[X]`) | Verification |
|------------|-------------------|--------------|
| RRSP contribution limit + over-contribution penalty (1%/mo) | CRA, ITA s. 146(5) | `[X]` **to-verify** current-year dollar figure |
| TFSA contribution limit + over-contribution penalty | CRA, ITA s. 146.2, 207.02 | `[X]` **to-verify** current-year dollar figure |
| Qualified / prohibited investments | CRA, ITA s. 207.01, Reg. 4900 | `[X]` **to-verify** per issuer (do not assert universality) |
| No margin / no pledging in registered accounts | CIRO margin rules + account agreement | `[X]` **to-verify** per broker/account |
| Options account levels (1–4) | CIRO/IROC Rule 3200 | `[X]` **to-verify** per broker (TFSA levels vary) |

Anything in the "verification" column that this audit has not confirmed is tagged `[X]` **to-verify
— never asserted.**

### (d) `position_size` — size ∝ portfolio_value / vol

- `requires:`
  - `portfolio_value` → `✓ PS-8 [C]` (broker also reports `[M]`).
  - `vol` → `✗ UNINSTRUMENTED`. Two candidate producers, neither produced as a named signal:
    (i) **realized vol** = std of daily log returns over a window → `[C]` reducer over `MD-2`
    (OHLCV, produced) — but the reducer is not written; (ii) **IV** → `MD-6`, gated on `MD-4`.
- **Writable: no → pending-instrumentation, step 2** (independent of the chain; cheapest win).

### (e) `exit_rules` — exit on iv_rank or pnl_since_entry

- `requires:`
  - `iv_rank` → `✗ UNINSTRUMENTED` — needs the `MD-6` IV **time series**, gated on `MD-4`.
  - `pnl_since_entry` → `✓ PS-7 [C]` (avg-cost unrealized P/L) or a `[C]` lot-reducer over `EX-1`
    (entry-price-per-lot → P/L since that entry).
- **Writable: no → pending-instrumentation, step 5.**

### (f) `expiry_selection` — pick expiry by dte + chain liquidity

- `requires:`
  - `dte` (days-to-expiry) → `✗ UNINSTRUMENTED` — needs an expiry date from the chain `MD-4`
    (selecting a *new* expiry cannot read it off an existing position).
  - `chain_liquidity` (bid/ask spread, open interest, volume) → `✗ UNINSTRUMENTED` — `MD-4`.
- **Writable: no → pending-instrumentation, step 4** (both inputs are the same missing producer).

### (g) `crypto_cap` — cap crypto weight

- `requires:`
  - `portfolio_weights` → `✓ [C]` reducer `PS-3 ÷ PS-8` (both produced).
  - `crypto_asset_class` (identify which positions are crypto) → `✓ [P]` operator-declared
    symbol→asset-class mapping (or `[X]` CDS/issuer classification). Note: in-registered, only
    crypto *spot ETFs* (MD-8) are eligible; direct crypto is excluded by (c).
- **Writable: yes.**

### (h) `weekly_review` — reconcile the thesis → outcome chain

- `requires` (the chain, `audit_observable.md` § 4): `thesis` → `✓ DR-1 [P]`; `proposed_order` →
  `✓ DR-2 [P]`; `executed_order` → `✓ DR-3 [M]`; `proposal_vs_executed_delta` → `✓ DR-4 [C]`;
  `outcome_vs_thesis` → `✓ DR-5 [C]`.
- **Writable: yes — conditional.** `DR-1`/`DR-2` are `[P]` operator-declared: the policy is
  writable only if the operator records theses and proposed orders *prospectively* (the same
  discipline caveat the observable audit attached to its P-10 arm). A weekly cadence in a TFSA
  additionally brushes the CRA "carrying on a business" rule (ITA s. 146.2(6)) — `[X]`
  **to-verify** whether the operator's frequency crosses that line.

---

## 6. Compliance and enforcement notes

1. **Account rules are tagged `[P]` with their `[X]` authority.** (c) is tagged against CRA
   (ITA ss. 146, 146.2, 207.01, 207.02, 207.04, Reg. 4900) and CIRO (margin rules, options-level
   Rule 3200); (a) and (b) are `[P]` operator invariants that sit *above* the CIRO options-level
   floor. See § 5(c) table.
2. **Unverifiable rules are `[X]` to-verify, never asserted.** Annual contribution limits,
   per-issuer qualified-investment status, per-broker options levels, and the TFSA
   carrying-on-a-business threshold are all marked `[X]` to-verify where this audit could not
   confirm them.
3. **The `calls_only` enforcement producer is named.** Short exposure is seen via the **signed
   open-position record** (`PS-1` sign convention, ⊕ `EX-1` reduction, ⊕ `EX-4` assignments);
   the one way this fails is a broker export that drops the long/short sign — a producer-contract
   requirement on `PS-1`, stated in § 5(a).
4. **No policy is writable on an unproduced `requires`.** Every `✓` resolves to a produced signal
   or a named reducer over produced signals; every `✗` names the missing upstream producer and the
   instrumentation step that unblocks it.

---

## LOG

**Policy count**

| Metric | Count |
|--------|-------|
| Candidate policies | 8 |
| Writable now | 4 — (a) `calls_only_invariant`, (c) `registered_account_limits`, (g) `crypto_cap`, (h) `weekly_review` |
| Pending-instrumentation | 4 — (b) `no_short_delta` (step 3), (d) `position_size` (step 2), (e) `exit_rules` (step 5), (f) `expiry_selection` (step 4) |

**Guard checks**

- [x] Every `requires` cell names a producer or says `UNINSTRUMENTED`. **PASS.**
- [x] No policy is marked writable with an unproduced `requires`. **PASS** (verified per policy in § 5).
- [x] Account rules tagged `[P]` with external authority `[X]` CRA/CIRO and rule classes named. **PASS.**
- [x] Unverifiable rules marked `[X]` to-verify; none asserted. **PASS.**
- [x] `calls_only` enforcement producer (the "see short exposure" requirement) stated. **PASS.**
- [x] Unwritable policies recorded pending-instrumentation with dependency-sorted order (§ 3). **PASS.**

**Result: PASS** — 8 policies enumerated, 4 writable / 4 pending-instrumentation, 0 writable with
an unproduced `requires`, all regulatory authority tags and to-verify marks in place.

**Commit:** recorded on branch `feature/investing-domain-audit`.
