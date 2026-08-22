---
status: accepted
---
# Investing Domain — Observability Audit

**Role:** domain auditor. This document inventories every signal the investing domain makes
*observable*, so the measurement plane can attach one producer to each. It is a source
inventory, not a connector: every source is **named, never connected** — no API keys, no
scraping, no live calls. A downstream instrument step decides *how* to pull each named source;
this step only establishes *what exists* and *what provenance class it carries*.

**Scope.** Canadian retail / registered-account investing, per the constraint set:

- **Market data** — TMX (Toronto Stock Exchange / TSX Venture) equities; options chains with
  greeks and implied volatility (single-name Canadian equity options trade on the **Montréal
  Exchange (MX)**); crypto spot; Canadian crypto spot ETFs (listed securities on TSX).
- **Portfolio state** — positions, buying power, realized/unrealized P/L, currency.
- **Execution records** — fills, expiries, assignments, plus the broker export formats the
  operator can produce.
- **Decision records** — theses, orders proposed vs executed, outcomes.
- **External context** — earnings dates, ex-dividend dates, news.

---

## How to read this document

### Provenance tags

Each signal row carries exactly one primary provenance tag. The tag describes the **strongest
claim we can make about that signal** given the stated source:

| Tag | Meaning (per this audit's contract) |
|-----|-------------------------------------|
| `[M]` | **Measured** — directly readable from a stated source (a broker statement, a confirmation, an export file). No derivation. |
| `[C]` | **Computed** — derivable by a deterministic reducer. The row states the formula and its inputs. |
| `[X]` | **External** — sourced from a named third-party vendor/exchange/issuer, consumed as published. |
| `[P]` | **Operator-declared** — stated by the operator (thesis, proposed order, risk limit, journal). Not measured. |
| `[H]` | **Hypothesis** — an estimate or subjective score with no primary measurement behind it. Never written as if measured. |

A row may carry a *secondary* tag in parentheses (e.g. `[X] (recomputable [C])`) where a vendor
publishes a value that can also be reproduced locally. The **primary tag governs**: a signal is
only `[M]` if the stated source itself records it.

### Registered-account visibility convention

Every signal is annotated for visibility inside a **RRSP / TFSA** (registered) account. The
governing fact: registered-account statements (monthly/quarterly) provide **fills, positions,
dividends, contributions, and book values — but not intraday data**. There is no live quote
stream, no intraday options chain, and no margin buying power in a registered account (TFSA and
RRSP do not permit margin). Options activity in a registered account is restricted to the
permitted strategies (covered calls, protective puts, cash-secured puts where offered); only
**fills of executed, permitted trades** appear on the statement — never a live chain of
unexecuted strikes. Each row states one of:

- `RRSP/TFSA: visible` — appears on the statement.
- `RRSP/TFSA: partial` — appears only as a point-in-time snapshot (e.g. statement-date valuation).
- `RRSP/TFSA: not visible` — requires an intraday/live feed or a margin account.
- `RRSP/TFSA: n/a` — asset class ineligible in the account (direct crypto) or not account-scoped.

### The load-bearing rule, restated for this domain

> To make a control rule (a trading policy arm) writable, every signal its `requires` clause
> names must have a producer. A row below that carries no producer — only an `[H]` hypothesis —
> is **not instrumentable as-is** and must be downgraded to a proxy or measured first.

---

## 1. Market data

Sources named, not connected: **TMX Datalinx** (end-of-day and real-time Toronto feeds),
**Montréal Exchange / Cboe** (options chains, greeks, IV, VIXC), **Bank of Canada** (CORRA,
government yield curve), **issuer IR pages**, and **named crypto spot exchanges** (Coinbase,
Kraken, Binance — public tickers only).

| ID | Signal | Tag | Source (named) | RRSP/TFSA | Notes / reducer inputs |
|----|--------|-----|----------------|-----------|------------------------|
| MD-1 | Equity last / settlement price | `[X]` | TMX Datalinx EOD file; broker quote | partial (statement-date valuation only) | Settlement is the official close; `[C]` cross-check = last traded price. |
| MD-2 | Equity daily OHLCV bar | `[X]` | TMX Datalinx historical; broker chart data | partial | Open/high/low/close/volume per trading day. |
| MD-3 | Equity bid/ask + depth (Level 1/2) | `[X]` | TMX Datalinx real-time feed | not visible (no live quotes in registered accounts) | Level 1 top-of-book; Level 2 full book depth. |
| MD-4 | Options chain: strike, expiry, bid/ask, last, open interest, volume | `[X]` | Montréal Exchange / Cboe options feed | not visible (no intraday chain; only executed fills appear) | Chain is the price surface the greeks and IV are computed over. |
| MD-5 | Option greeks — delta, gamma, theta, vega, rho | `[C]` (published `[X]`) | MX/Cboe publish; recompute from pricing inputs (§ 6) | not visible | Inputs: S, K, T, r, q, σ — see § 6 for the closed forms. |
| MD-6 | Implied volatility (per strike/expiry) | `[C]` (published `[X]`) | MX/Cboe publish; recompute by inverting the model | not visible | Inputs: market option price + S, K, T, r, q — see § 6. |
| MD-7 | Crypto spot price (BTC, ETH, …) | `[X]` | Named exchanges: Coinbase, Kraken, Binance public tickers | n/a (direct crypto ineligible) | Per-exchange ticker; cross-exchange `[C]` = volume-weighted mid. |
| MD-8 | Canadian crypto spot ETF NAV + market price | `[X]` | Market price from TMX; NAV published daily by issuer (Purpose BTCC, CI Galaxy ETHX, Evolve EBIT) | visible (ordinary listed security) | Premium/discount `[C]` = (market − NAV) / NAV; inputs MD-8 both legs. |
| MD-9 | Risk-free rate (term-matched) | `[X]` | Bank of Canada: CORRA + government bond yield curve | n/a (pricing input, not a position) | CDOR discontinued 2024; CORRA is the current risk-free benchmark. |
| MD-10 | Forward dividend yield / declared dividends | `[X]` | Issuer IR; TMX; CDS dividend calendar | visible (dividends appear on statement as cash) | Dividend yield `[C]` = annualized dividends / price (inputs MD-10 + MD-1). |

---

## 2. Portfolio state

Sources named, not connected: **broker monthly/quarterly statements**, **account activity CSV
exports**, **broker account-summary / buying-power reports**, **Bank of Canada** noon FX rates,
and **T5008 / T5 / T3** tax slips.

| ID | Signal | Tag | Source (named) | RRSP/TFSA | Notes / reducer inputs |
|----|--------|-----|----------------|-----------|------------------------|
| PS-1 | Position quantity (shares / contracts) | `[M]` | Broker statement holdings page | visible | Current held quantity per security. |
| PS-2 | Average cost basis (book value) | `[M]` | Broker statement (broker-tracked) | visible | Broker computes; `[C]` recompute = Σ(fill cost) / Σ(qty) over fill history (§ 3). |
| PS-3 | Position market value | `[C]` | = PS-1 × MD-1 | partial (statement-date) | Inputs: quantity `[M]`, last price `[X]`. |
| PS-4 | Cash balance (per currency) | `[M]` | Broker account summary | visible | CAD and USD sub-ledgers separately. |
| PS-5 | Buying power | `[M]` | Broker buying-power report (margin account) | n/a (registered accounts have no margin BP) | Broker's own formula; in RRSP/TFSA the analog is available cash + contribution room (CX-7). |
| PS-6 | Realized P/L (per position / aggregate) | `[C]` | = Σ(sale proceeds − cost basis − commissions) over fills | visible (realized gains reported) | Inputs: execution fills `[M]` (§ 3). Tax-cost basis in registered accounts differs (see T5008 note). |
| PS-7 | Unrealized P/L (per position / aggregate) | `[C]` | = PS-1 × (MD-1 − PS-2) | partial (statement-date) | Inputs: quantity `[M]`, mark `[X]`, cost basis `[M]`. |
| PS-8 | Account equity / net asset value | `[C]` | = Σ(PS-3) + PS-4 | visible (statement total) | Broker also reports it `[M]`; `[C]` recompute is the cross-check. |
| PS-9 | Time-weighted return | `[C]` | = Π(1 + rᵢ) − 1 over cash-flow-dated sub-periods | visible (inferred from statement history) | Inputs: dated contributions/withdrawals + period-end NAVs (PS-8). |
| PS-10 | Currency balances + FX rate | `[M]` (balances) `[X]` (rate) | Broker statement; Bank of Canada noon rate | visible | FX rate source is `[X]`; CAD-equivalent value `[C]` = balance × rate. |
| PS-11 | Contributions / withdrawals | `[M]` | Broker statement; RRSP contribution receipt | visible | Feeds PS-9 and contribution-room tracking. |

---

## 3. Execution records

Sources named, not connected: **broker trade confirmations**, **monthly/quarterly activity
statements**, **account activity CSV / Flex-Query exports**, **options expiry & assignment
notices**, and **T5008** (disposition slip). The export formats below are the canonical
operator-produced files a reducer can parse.

| ID | Signal | Tag | Source (named) | RRSP/TFSA | Notes / reducer inputs |
|----|--------|-----|----------------|-----------|------------------------|
| EX-1 | Fill record (ticker, side, qty, price, commission, time, currency, venue) | `[M]` | Broker trade confirmation; activity CSV | visible | The atomic execution unit. |
| EX-2 | Order lifecycle (submitted → partial → filled / cancelled) | `[M]` | Broker order ticket / activity log | visible (final state; not intraday tick stream) | Enables fill-rate `[C]` = filled / submitted. |
| EX-3 | Option expiry (expired worthless / auto-exercised) | `[M]` | Broker expiry notice; activity statement | visible (as a fill/expiry line, not a live chain) | Distinguishes ITM auto-exercise from OTM worthless expiry. |
| EX-4 | Assignment / exercise notice | `[M]` | Broker assignment notice; MX/OCC assignment report | visible | Short-option assignment is only possible in permitted registered strategies. |
| EX-5 | Dividends / distributions received | `[M]` | Broker statement; CDS dividend ledger; T5/T3 | visible | Cash (and DRIP) distribution events. |
| EX-6 | Broker export format inventory | `[M]` | Questrade activity CSV; Interactive Brokers Flex Query (XML/CSV); TD/Scotia monthly statement PDF; T5008 slip | visible | Meta-signal: *which* parseable formats the operator can produce. |
| EX-7 | Fees / commissions / ECN charges | `[M]` | Broker trade confirmation | visible | Per-fill cost; feeds PS-6 cost basis. |
| EX-8 | Settlement date + settlement currency | `[M]` | Broker confirmation | visible | T+2 equity (T+1 post-2024 for many); distinct from trade date. |
| EX-9 | Book-value adjustments (DRIP, return-of-capital, ROC) | `[M]` | Broker statement; T3 (ROC) | visible | ROC lowers book value; `[C]` recompute = book value − ROC distributions. |

---

## 4. Decision records

These are the *thesis-side* signals — what the operator intended and believed, before the market
answered. By construction most are `[P]` (operator-declared) or `[H]` (subjective). The guard
below is enforced: **no `[H]` row is written as if measured.**

| ID | Signal | Tag | Source (named) | RRSP/TFSA | Notes / reducer inputs |
|----|--------|-----|----------------|-----------|------------------------|
| DR-1 | Thesis (entry/exit rationale, target, stop, horizon) | `[P]` | Operator journal / trade note | n/a (operator-scoped) | Free text; only taggable by operator policy. |
| DR-2 | Proposed order (ticker, side, qty, limit, TIF) | `[P]` | Operator order ticket at decision time | n/a | The *intended* execution, recorded before submission. |
| DR-3 | Executed order (what actually filled) | `[M]` | = EX-1 (execution record) | visible | The *actual* execution, cross-checked against DR-2. |
| DR-4 | Proposed-vs-executed delta (slippage, partial fill, cancelled) | `[C]` | = DR-3 − DR-2 | visible (via the two inputs) | Inputs: proposed order `[P]`, executed fill `[M]`. |
| DR-5 | Outcome vs thesis (realized P/L vs target/stop) | `[C]` | = PS-6 vs DR-1 target/stop | visible | Inputs: realized P/L `[C]`, thesis `[P]`. |
| DR-6 | Decision timestamp + review notes | `[P]` | Operator journal | n/a | Anchors DR-2 to a clock; enables latency-to-decision measures. |
| DR-7 | Risk limits / position-sizing rules | `[P]` | Operator policy document | n/a | A control rule; becomes a *factor level* in the grid once instrumented. |
| DR-8 | Confidence at decision time | `[H]` | Operator self-report (recalled) | n/a | **Subjective.** Not a measurement; usable only as a hypothesis axis, never as a measured input. |

---

## 5. External context

Sources named, not connected: **issuer IR calendars**, **CDS corporate-action / dividend
calendar**, **TMX corporate-action feed**, **Statistics Canada**, **Bank of Canada**, **Cboe**
(VIXC), and **named newswires** (Reuters, Bloomberg, Globe Investor, PR Newswire).

| ID | Signal | Tag | Source (named) | RRSP/TFSA | Notes / reducer inputs |
|----|--------|-----|----------------|-----------|------------------------|
| CX-1 | Next earnings date (announced / confirmed) | `[X]` | Issuer IR calendar; TMX corporate calendar | n/a (context, not position) | Announced dates are firm; estimates are `[H]`. |
| CX-2 | Ex-dividend date, record date, pay date, amount | `[X]` | Issuer IR; CDS dividend calendar | visible (payments land on statement) | Ex-div is the entitlement trigger. |
| CX-3 | Ticker-tagged news / headlines | `[X]` | Reuters, Bloomberg, Globe Investor, PR Newswire | n/a | Raw headlines are `[X]`; a sentiment score over them would be `[H]`. |
| CX-4 | Analyst consensus rating / price target | `[X]` | Refinitiv / Bloomberg consensus | n/a | Vendor consensus is `[X]`; the operator's own target is `[P]` (DR-1). |
| CX-5 | Economic calendar (BoC rate decisions, CPI, GDP) | `[X]` | Statistics Canada; Bank of Canada | n/a | Scheduled releases; surprises `[C]` = actual − consensus. |
| CX-6 | Corporate actions (splits, mergers, ticker changes) | `[X]` | CDS; TMX corporate-action feed | visible (post-action on statement) | Feeds PS-2 book-value adjustments. |
| CX-7 | Registered-account contribution room (TFSA/RRSP) | `[X]` | CRA Notice of Assessment / My Account | visible (statement side) | Operator-tracked remaining room is `[P]`. |

---

## 6. Greeks and IV — the pricing inputs they require

Every option greek and the implied volatility are **deterministic reducers over the
Black–Scholes–Merton (dividend-adjusted) model** (European closed form; American single-name
equities on MX require a binomial/trinomial tree or PDE — which is why vendor-published values
are the `[X]` primary and local recomputation is the `[C]` cross-check).

**Model inputs (the observable prerequisites for any `[C]` greek/IV):**

| Symbol | Input | Provenance of the input |
|--------|-------|-------------------------|
| `S` | Underlying spot price | `[X]` MD-1 |
| `K` | Strike price | `[X]` MD-4 (chain) |
| `T` | Time to expiry (years) | `[C]` = (expiry − now) in the option's day-count convention (calendar vs trading days affects theta) |
| `r` | Risk-free rate | `[X]` MD-9 (CORRA / bond yield, term-matched) |
| `q` | Dividend yield (continuous, or discrete dividends) | `[X]` MD-10 |
| `σ` | Volatility | for greeks: the IV (`[C]` MD-6); for IV itself: the *unknown* to solve |

**Closed forms** (with `d₁ = [ln(S/K) + (r − q + σ²/2)T] / (σ√T)`, `d₂ = d₁ − σ√T`,
`N(·)` the standard-normal CDF, `N′(·)` its density):

| Quantity | Formula |
|----------|---------|
| Call price | `C = S·e^(−qT)·N(d₁) − K·e^(−rT)·N(d₂)` |
| Put price | `P = K·e^(−rT)·N(−d₂) − S·e^(−qT)·N(−d₁)` |
| Delta | `∂V/∂S = e^(−qT)·N(d₁)` (call) / `e^(−qT)·(N(d₁) − 1)` (put) |
| Gamma | `∂²V/∂S² = e^(−qT)·N′(d₁) / (S·σ·√T)` |
| Theta | `−S·e^(−qT)·N′(d₁)·σ/(2√T) − r·K·e^(−rT)·N(d₂) + q·S·e^(−qT)·N(d₁)` (call) |
| Vega | `∂V/∂σ = S·e^(−qT)·N′(d₁)·√T` (per 1.0 vol; scale by 0.01 for per-point) |
| Rho | `∂V/∂r = K·T·e^(−rT)·N(d₂)` (call) / `−K·T·e^(−rT)·N(−d₂)` (put) |

**Implied volatility** is the inverse: solve `σ` such that the model price equals the observed
**market option price** (bid/ask midpoint or last trade). It has no closed form — it is a
numerical root-find (bisection / Newton). Its required inputs are therefore `{market option
price, S, K, T, r, q}` — all of which this audit tags `[X]` (MD-1, MD-4, MD-9, MD-10) except
`T`, which is a `[C]` time difference. A producer for IV therefore needs a market-option-price
producer first; without one, IV (and every `[C]` greek built on it) is unmeasurable and must not
be written as measured.

---

## LOG

**Signal counts per area**

| Area | Signals |
|------|---------|
| 1. Market data | 10 |
| 2. Portfolio state | 11 |
| 3. Execution records | 9 |
| 4. Decision records | 8 |
| 5. External context | 7 |
| **Total** | **45** |

**Guard checks**

- [x] Every signal row carries exactly one primary provenance tag. **PASS.**
- [x] No `[H]` row is written as if measured — the only `[H]` signal (DR-8, decision confidence)
      is explicitly marked subjective and excluded from the measured-input set. **PASS.**
- [x] Registered-account visibility annotated per signal (visible / partial / not visible / n/a). **PASS.**
- [x] Sources are named, not connected — no API keys, no scraping, no live calls. **PASS.**
- [x] Greeks and IV carry their pricing inputs and the closed-form reducers. **PASS.**
- [x] Instrumentation gap flagged: a market-option-price producer (MD-4) is a prerequisite for
      any `[C]` IV/greek producer (§ 6). **PASS — flagged, not blocked.**

**Result: PASS** — 45 signals inventoried, 0 unguarded `[H]` rows, all reducers stated with
inputs.
