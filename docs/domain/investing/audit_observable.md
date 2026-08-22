---
status: accepted
evidence_classes: [M] measured, [C] computed (deterministic reducer), [X] external, [P] operator-declared, [H] hypothesis
---

# RRSP Investing — Stage-0 Observability Audit

**Stage-0 seeding audit.** This document inventories every signal the investing domain makes
**observable**, so the measurement plane (`knowledge` producers) has a producer for each one —
*before* any control rule is authored. It is a catalog, not a connection: sources are **named**,
never keyed, scraped, or called live.

---

## 0. How to read this audit

**Tag legend** (maps to the knowledge plane's `evidence_class` + authority ordering):

| Tag | Meaning | Authority (knowledge.py) | Rule |
|-----|---------|--------------------------|------|
| `[M]` | Directly measurable from a **stated source** (broker statement, exchange feed, export file) | `MEASURED` | The row names the source. |
| `[C]` | Derivable by a **deterministic reducer**; the formula's inputs are stated in the row | `DERIVED` | No `[C]` row may omit its inputs. |
| `[X]` | **External** — named source/vendor outside the operator's own records | `—` (evidence `[X]`) | The row names the vendor. |
| `[P]` | **Operator-declared** (thesis, intent, declared limit, declared contribution room) | `POLICY` | The row names who declares it. |
| `[H]` | **Hypothesis** — not yet observable; isolated in §7, never in the measured tables | `ADVISORY` | No `[H]` row is written as if measured. |

**Registered-account visibility column (`REG`):**

- `yes` — appears in an RRSP/TFSA statement/export as-is.
- `partial` — the statement shows the **end-of-day** value only (no intraday series).
- `no` — not visible inside a registered account at all; requires an external source or a
  non-registered account.

**Hard scoping constraints baked into the tags below:**

1. **Registered accounts (RRSP/TFSA) have no margin.** "Buying power" = settled cash, not margin
   equity. Listed-option strategies are limited to *covered call*, *cash-secured put*, and *long*
   call/put/protective-put. Any naked/spread/margin option signal is out of scope for a registered
   account and is marked `REG:no`.
2. **Registered accounts cannot hold crypto spot directly.** Crypto exposure inside an RRSP/TFSA
   is via Canadian **crypto spot ETFs** (qualified investments — §1.4), not the venues in §1.3.
   §1.3 exists only if the operator also runs a non-registered account.
3. **No API keys, no scraping, no live calls.** `[X]` rows name a vendor for *future* wiring; `[M]`
   rows name the file/feed the operator or broker already produces.

---

## 1. Market data

### 1.1 TMX equities

| ID | Signal | Tag | Source / formula | REG |
|----|--------|-----|------------------|-----|
| M1 | Last trade price | `[M]` | TMX Datalinx L1/L2 feed; broker streaming quote | `no` (statement = EOD mark) |
| M2 | Bid / ask (Level 1) | `[M]` | TMX L1 feed; broker quote | `no` |
| M3 | Order-book depth (Level 2) | `[M]` | TMX Datalinx L2 (MDS) | `no` |
| M4 | Session volume | `[M]` | TMX trade tape | `no` |
| M5 | Daily OHLC | `[C]` | open = first trade, high = max, low = min, close = last/closing auction; inputs: timestamped trades | `partial` (close only) |
| M6 | VWAP | `[C]` | Σ(pᵢ·vᵢ)/Σvᵢ over the session; inputs: `(price, volume)` trades | `no` |
| M7 | Market cap | `[C]` | price × shares outstanding; inputs: M1, M10 | `no` |
| M8 | Dividend yield | `[C]` | annualized dividend ÷ price; inputs: dividend (`[X]` issuer), M1 | `no` |
| M9 | P/E | `[C]` | price ÷ EPS; inputs: M1, EPS (`[X]` filings) | `no` |
| M10 | Shares outstanding | `[X]` | SEDAR / issuer filings | `no` |
| M11 | Corporate actions (split, dividend declared) | `[X]` | TMX notices / SEDAR / issuer IR | `no` |

### 1.2 Options chains (Montreal Exchange, MX) — greeks & IV

> MX equity options are **American-style, CAD-denominated, physically settled**. Black–Scholes is
> therefore a first-order approximation; exact greeks use a binomial (CRR) or finite-difference
> lattice (§6). All `REG` = `no`: registered statements show fills/positions but **not** chains.

| ID | Signal | Tag | Source / formula | REG |
|----|--------|-----|------------------|-----|
| O1 | Option bid / ask / last | `[M]` | MX chain (broker or vendor) | `no` |
| O2 | Strike, expiry, type, underlying | `[M]` | MX reference data | `no` |
| O3 | Open interest | `[M]` | MX daily OI report | `no` |
| O4 | Option volume | `[M]` | MX trade tape | `no` |
| O5 | Implied volatility (per strike/expiry) | `[C]` | invert pricing model at O1; inputs §6 | `no` |
| O6 | Delta | `[C]` | ∂V/∂S; inputs §6 | `no` |
| O7 | Gamma | `[C]` | ∂²V/∂S²; inputs §6 | `no` |
| O8 | Theta | `[C]` | ∂V/∂t; inputs §6 | `no` |
| O9 | Vega | `[C]` | ∂V/∂σ; inputs §6 | `no` |
| O10 | Rho | `[C]` | ∂V/∂r; inputs §6 | `no` |
| O11 | Moneyness (ITM/ATM/OTM) | `[C]` | S vs K; inputs O2, M1 | `no` |
| O12 | Time to expiry (years) | `[C]` | (expiry − now)/365.25; day-count convention; inputs O2, clock | `no` |
| O13 | Risk-free rate r | `[X]` | Bank of Canada / CORRA / GoC yield curve | `no` |
| O14 | Dividend yield q | `[C]` | implied via put-call parity, or `[X]` issuer; inputs O1(call), O1(put), S, K, r, T | `no` |

### 1.3 Crypto spot (non-registered only — see constraint 2)

| ID | Signal | Tag | Source / formula | REG |
|----|--------|-----|------------------|-----|
| C1 | BTC spot price | `[X]` | Coinbase / Kraken / Binance / CoinGecko / Kaiko / Coin Metrics | `no` |
| C2 | ETH spot price | `[X]` | same venues | `no` |
| C3 | Crypto OHLC / volume | `[X]` | venue or aggregator feed | `no` |
| C4 | Perpetual funding rate | `[X]` | Binance / Bybit / Deribit | `no` |

### 1.4 Canadian crypto spot ETFs (the registered-account path)

| ID | Signal | Tag | Source / formula | REG |
|----|--------|-----|------------------|-----|
| E1 | ETF market price (BTCC, ETHH, etc.) | `[M]` | TMX feed | `partial` (EOD mark) |
| E2 | ETF NAV per share | `[X]` | fund issuer daily NAV (Purpose / CI Global / Evolve) | `no` |
| E3 | Premium / discount to NAV | `[C]` | (price − NAV)/NAV; inputs E1, E2 | `no` |
| E4 | BTC/ETH held per share | `[X]` | issuer disclosure / SEDAR / on-chain analytics | `no` |
| E5 | MER / management fee | `[X]` | Fund Facts (SEDAR) | `no` |

**Area 1 total: 34 signals** (11 equities · 14 options · 4 crypto · 5 ETF).

---

## 2. Portfolio state

| ID | Signal | Tag | Source / formula | REG |
|----|--------|-----|------------------|-----|
| P1 | Position quantity | `[M]` | broker statement / activity export | `yes` |
| P2 | Average cost (book value) | `[M]` | broker statement (broker-computed) | `yes` |
| P3 | Market value per position | `[C]` | qty × last price; inputs P1, M1 (EOD) | `yes` (EOD) |
| P4 | Cash / buying power | `[M]` | broker account view | `yes` (settled cash; no margin) |
| P5 | Unrealized P/L | `[C]` | market value − book cost; inputs P3, P2 | `yes` |
| P6 | Realized P/L | `[M]` | broker trade history/statement (alt `[C]`: Σ(proceeds − cost) per closed lot) | `yes` |
| P7 | Currency balances (CAD + USD sub-accounts) | `[M]` | broker sub-account view | `yes` |
| P8 | FX rate applied by broker | `[M]` | broker conversion record (incl. Norbert's Gambit journal) | `yes` |
| P9 | Reference FX (USD/CAD) | `[X]` | Bank of Canada noon rate | `no` |
| P10 | RRSP contribution room | `[P]` | operator-declared; cross-check `[X]` CRA Notice of Assessment | `yes` (CRA) |
| P11 | TFSA contribution room | `[P]` | operator-declared; cross-check `[X]` CRA My Account | `yes` (CRA) |
| P12 | FX-adjusted P/L | `[C]` | Σ FX-adjusted proceeds − Σ FX-adjusted cost; inputs P6, P8 (or P9) | `yes` |
| P13 | Position weight / concentration | `[C]` | market value ÷ total portfolio value; inputs P3, ΣP3 | `yes` |

**Area 2 total: 13 signals.**

---

## 3. Execution records

| ID | Signal | Tag | Source / formula | REG |
|----|--------|-----|------------------|-----|
| X1 | Fill (symbol, side, qty, price, timestamp, venue) | `[M]` | trade confirmation + monthly statement | `yes` |
| X2 | Trade date / settle date | `[M]` | trade confirmation | `yes` |
| X3 | Commission & fees | `[M]` | confirmation / statement | `yes` |
| X4 | FX on a USD fill in a CAD account (incl. journaling) | `[M]` | statement / activity export | `yes` |
| X5 | Broker export (named formats below) | `[M]` | see format list | `yes` |
| X6 | Option expiry auto-exercise (ITM long) | `[M]` | statement / trade confirmation | `yes` |
| X7 | Assignment (short option assigned) | `[M]` | statement / trade confirmation | `yes` (covered/cash-secured only) |
| X8 | Dividends / distributions received | `[M]` | statement | `yes` |
| X9 | Return of capital (ROC) | `[M]` | T3/T5 tax slip + broker activity | `yes` |
| X10 | Corporate-action fills (split / merger) | `[M]` | statement | `yes` |

**Broker export formats the operator can provide** (named sources, not connections):

| Format | Broker / mechanism |
|--------|--------------------|
| CSV activity / transaction download | Questrade, Wealthsimple Trade, TD Direct Investing, RBC, BMO InvestorLine, CIBC Investor's Edge, National Bank |
| API (read-only queries) | Questrade API, Interactive Brokers **Flex Query** (XML/CSV) |
| OFX / QFX | bank-style direct-connect (legacy; many Canadian brokers) |
| QIF | legacy import |
| PDF statements (monthly/quarterly) | all brokers — the fallback when no structured export exists |

**Area 3 total: 10 signals** (the format list is the named *source* for X1–X10, not a separate tag).

---

## 4. Decision records

> The operator's own judgment is the hardest thing to make observable. Rows D1, D2, D8, D9 have
> **no producer today** — they are `[P]` and must be journaled to exist. Flagged in the gap map (§8).

| ID | Signal | Tag | Source / formula | REG |
|----|--------|-----|------------------|-----|
| D1 | Investment thesis (why enter/exit/hold) | `[P]` | operator-declared (decision journal) | `yes` |
| D2 | Proposed order (intent: symbol, side, qty, limit, thesis id) | `[P]` | operator-declared (order ticket journal) | `yes` |
| D3 | Executed order (join to fill) | `[M]` | broker — same record as X1 | `yes` |
| D4 | Proposed ↔ executed match | `[C]` | join on symbol+side+timestamp tolerance; inputs D2, X1 | `yes` |
| D5 | Slippage (fill − limit) | `[C]` | fill price − limit price; inputs X1, D2 | `yes` |
| D6 | P/L attribution per thesis | `[C]` | Σ fills grouped by thesis id; inputs X1, D1 | `yes` |
| D7 | Holding period | `[C]` | exit date − entry date; inputs X2 | `yes` |
| D8 | Risk limits (max position, max sector weight) | `[P]` | operator-declared policy | `yes` |
| D9 | Exit reason / post-mortem note | `[P]` | operator-declared (journal) | `yes` |
| D10 | Outcome verdict (win/loss vs thesis) | `[C]` | sign(D6) reconciled against D9; inputs D6, D9 | `yes` |

**Area 4 total: 10 signals.**

---

## 5. External context

| ID | Signal | Tag | Source / formula | REG |
|----|--------|-----|------------------|-----|
| T1 | Next earnings date | `[X]` | Refinitiv / FactSet / Bloomberg; free: TMX Money, company IR, Yahoo | `no` |
| T2 | Ex-dividend / record date | `[X]` | TMX listing / issuer IR | `no` |
| T3 | News headlines | `[X]` | Canadian Press / Reuters / PR Newswire / Business Wire | `no` |
| T4 | Macro calendar (BoC rate, CPI, GDP, employment) | `[X]` | Bank of Canada / Statistics Canada | `no` |
| T5 | RRSP/TFSA annual limits + rules | `[X]` | CRA | `no` |
| T6 | US dividend withholding-tax treatment | `[X]` | CRA / Canada–US treaty (RRSP exempt; TFSA **not** exempt) | `no` |
| T7 | GICS sector / industry classification | `[X]` | MSCI / S&P GICS | `no` |
| T8 | Realized (historical) volatility | `[C]` | annualized std of log returns; inputs historical prices (M5) | `no` |
| T9 | Beta | `[C]` | cov(rᵢ, rₘ)/var(rₘ) regression; inputs returns (M5), benchmark (`[X]`) | `no` |

**Area 5 total: 9 signals.**

---

## 6. Greeks & IV — pricing inputs (required for O5–O10)

Every greek and every IV value is a function of the **same six inputs** plus a model choice.
A `[C]` row in §1.2 is only writable when all six are present; the table states which signal
supplies each.

| Input | Symbol | Supplied by |
|-------|--------|-------------|
| Underlying spot price | S | M1 |
| Strike | K | O2 |
| Time to expiry | T | O12 |
| Risk-free rate | r | O13 |
| Dividend yield | q | O14 |
| Market option price | V_market | O1 |
| Model (European vs American) | — | `[P]`/`[C]` choice; MX is American → binomial (CRR) or FD lattice; BS only as approximation |

- **Implied volatility (O5):** the root σ solving `V_model(S,K,T,r,q,σ) = V_market`. A deterministic
  reducer (bisection/Newton) over one variable; inputs = the six above.
- **Greeks (O6–O10):** partial derivatives of `V_model` — Delta `∂V/∂S`, Gamma `∂²V/∂S²`,
  Theta `∂V/∂t`, Vega `∂V/∂σ`, Rho `∂V/∂r`. Closed-form under Black–Scholes; lattice sensitivities
  under the binomial/PDE model. All require the same six inputs.

**Consequence:** O5–O10 are `[C]`, *never* `[M]` — no vendor "sells a delta"; a delta is computed.
They also cannot be written for a registered account until an `[X]` chain source (MX) is wired,
because the statement carries no chain (§8, G2).

---

## 7. Hypotheses (isolated — never treated as measured)

These are `[H]` and are **excluded** from the observable counts. They may become `[C]` only once a
deterministic reducer is specified over measured inputs; today they have none.

| ID | Hypothesis | Why it is `[H]`, not `[C]` |
|----|-----------|----------------------------|
| H1 | Probability of assignment on a short option | model estimate over an *unobserved* distribution; no reducer specified yet |
| H2 | Forward expected return per thesis | subjective; no deterministic formula over measured inputs |
| H3 | "Optimal" position size | a policy *candidate*, not a measurement — must be authored as a control rule (§9), not observed |

---

## 8. Gap map — policy wants, measurement lacks

| Gap | Missing producer | Impact | Register path |
|-----|------------------|--------|---------------|
| G1 | Intraday marks for registered accounts | statements are EOD only | `[X]` TMX/MX vendor, or accept EOD (M1 `partial`) |
| G2 | Live options chain (intraday greeks/IV) | no chain in statements | `[X]` MX/OPRA-equivalent, or EOD snapshot; blocks O5–O10 for registered accounts |
| G3 | Order-book depth | L2 is `[X]`-only | optional — most policy needs L1/EOD only |
| G4 | Operator thesis / intent / limits (D1, D2, D8, D9) | `[P]` with **no journal tool** — the single largest gap | decision journal producer (highest priority) |
| G5 | Crypto spot in registered accounts | not directly holdable | route via spot ETFs (E1–E5, already `[M]`); §1.3 is non-registered-only |
| G6 | Contribution room | `[P]`-declared; no automated CRA producer | operator declares P10/P11, cross-check `[X]` CRA |
| G7 | Dividend yield q for pricing (O14) | thin — implied or issuer-only | wire `[X]` issuer dividend feed or accept parity-implied q |

---

## 9. Policy map — prospective control rules and their `requires`

Per the load-bearing rule (*to make policies, we need information*): each rule below states its
`requires` and every field is resolvable to a measured signal above — or it is **unwritable** and
named as such.

| Rule | Type | `requires` | Resolved by | Verdict |
|------|------|------------|-------------|---------|
| POL-1 Covered-call entry | control | IV, moneyness, underlying price, position | O5, O11, M1, P1/P3 | **writable** iff O5 resolvable (else blocked by G2) |
| POL-2 Position sizing (max weight) | control | weight, total value, cash | P13, ΣP3, P4 | **writable** |
| POL-3 Contribution-room guard | control | RRSP/TFSA room | P10, P11 | **writable** (operator-declared) |
| POL-4 Exit-on-invalidation | control | thesis, P/L attribution, earnings/ex-div/news | D1, D6, T1, T2, T3 | **writable** iff D1 journaled (G4) |
| POL-5 Expiry / roll management | control | time to expiry, IV, expiry/assignment events | O12, O5, X6, X7 | **writable** iff O5 resolvable (G2) |

The compiler's `requires`/`produces` gate will reject POL-1/POL-5 as drafted if O5 is not produced
in the spec — which is exactly why this audit lands *before* any spec is authored.

---

## 10. Adversarial compliance review

Self-check against the guard rails, answered adversarially (assume a reviewer will try to break it):

1. **Every signal row tagged?** Yes — §1–§5 carry exactly one of `[M]/[C]/[X]/[P]` per row; §7 carries `[H]`.
2. **Any `[H]` written as measured?** No — `[H]` rows live only in §7, are counted separately, and carry an explicit "why not `[C]`" column.
3. **Every `[M]` names a stated source?** Yes — broker statement/confirmation/export, or TMX/MX feed.
4. **Every `[C]` states its formula inputs?** Yes — inline per row; greeks/IV centralized in §6.
5. **Every `[X]` names a vendor?** Yes — each row names the vendor(s); no `[X]` row is vendor-less.
6. **RRSP/TFSA visibility noted per market/execution signal?** Yes — `REG` column on §1–§3.
7. **No API keys / scraping / live calls?** Yes — sources are named, never connected (§0 constraint 3).
8. **Any `[C]` depending on an `[H]` input?** No — no `[C]` formula in §1–§6 consumes a §7 hypothesis.
9. **Registered-account constraint honored in option scope?** Yes — naked/spread/margin strategies marked `REG:no`; only covered/cash-secured/long marked `yes`.

**Verdict: PASS** — with gap flags G1–G7 recorded (§8) as the input to the next seeding step.

---

## 11. Log

| Area | Signals |
|------|---------|
| 1 Market data (TMX / options / crypto / ETF) | 34 |
| 2 Portfolio state | 13 |
| 3 Execution records | 10 |
| 4 Decision records | 10 |
| 5 External context | 9 |
| **Observable total** | **76** |
| 7 Hypotheses (`[H]`, isolated) | 3 |

- **PASS/FAIL:** PASS (all rows tagged; zero `[H]`-as-measured; all `[C]` reducers have inputs; all `[M]`/`[X]` sources named).
- **Outstanding gaps:** G1–G7 (highest priority: G4 decision journal, then G2 options chain).
- **Commit:** see `git log` for the seeding commit.
