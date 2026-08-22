---
status: accepted
---
# Investing Domain — Gap Map (Stage-0 seeding, framework mapper)

**Role:** framework mapper. This document maps the two prior audits — `audit_observable.md`
(the signals, "d1") and `audit_policies.md` (the policies, "d2") — onto this repository's actual
machinery, and states exactly what the **new** investing repo must gain to run the RRSP domain as
a measured, policy-driven system. Every mapping below is either a reuse of an existing mechanism
(name + file/line) or an explicit `NEW` kind; nothing is invented silently.

**The machinery being mapped onto** (authority = `docs/designs/current/context_abstraction_design.md`,
the CAP design, frozen I0–I7 + addendum I8–I10):

- **Knowledge plane** — the producer pattern: `build_record` → `record_to_artifact` →
  `record_to_event` → `knowledge_stream.publish_event` → `kb-registry-v1` → manifest compaction.
  Nine producer families exist; the domain needs five (four new + one reuse), § 1.
- **Fact plane (CAP I0, reserved)** — `CanonicalFact` + `FACT_PREDICATES` + `EPISTEMIC_MAP` +
  `verify_chain`, home stubbed at `src/agentic_dynamics/control/facts.py` (zero call sites by
  design). Reducers are pure `Reducer = Callable[[ReducerInput], list[CanonicalFact]]`
  (design § 4). § 2 declares the domain's candidate predicates and reducers.
- **Contracts (CAP I4)** — versioned decision-type contracts in `experiments/contexts/<dt>.yaml`
  (design § 6.1); § 3 declares the domain's two new contracts + one reuse.
- **Adapters plane** — the model backends (`opencode.py`, `claude_adapter.py`); § 4 declares the
  market-data adapter in the same plane.
- **Profiles (CAP I8, addendum A.2)** — `DomainProfile` + `ChallengeProfile`; § 6 writes the
  provisional investing blocks as the static filing that lifts into `declared` profile facts.
- **Transport / scoping** — the two-Redis rule (framework queue `finops-queue` 6380, story agents
  `finops-redis` 6379) and `repository_id` scope; § 7 states the this-repo / new-repo split.

The load-bearing rule binds every section: **a predicate with no `produced_by` is undeclarable, a
contract whose `requires_facts` has no producer is unrefusable-only, and a policy is unwritable
until its information exists.** § 2 records which predicates are blocked and why.

---

## 1. PRODUCERS — the domain's knowledge-producer families

Five families. Each maps to an existing producer pattern or is `NEW`; the "pattern" column names
the concrete module whose contract is reused verbatim.

| Family | `source_type` | authority / evidence | Pattern reused (existing) | New code |
|--------|---------------|----------------------|---------------------------|----------|
| `market/v1` | `market` (**NEW** row) | `MEASURED` `[M]` (observed quote/bar); derived values come from **reducers**, § 2 | `ledger_ingestion` contract: `build_record`→`record_to_artifact`→`record_to_event`→`publish_event`; `derive_*_records(entries, *, repository_id, revision, now)` | **NEW** `knowledge/market_ingestion.py` + `adapters/market_data.py` (§ 4) + one additive `SOURCE_TYPES` row |
| `portfolio/v1` | `portfolio` (**NEW** row) | `MEASURED` `[M]` (statement snapshot) | `ledger_ingestion` — `ledger_job` is the exact analog: one snapshot record per statement-date | **NEW** `knowledge/portfolio_ingestion.py` + additive row |
| `trades/v1` | `trade` (**NEW** row) | `MEASURED` `[M]` (atomic fill/expiry/assignment) | `ledger_ingestion` — `ledger_attempt` is the exact analog: one record per atomic event | **NEW** `knowledge/trades_ingestion.py` + additive row |
| `thesis/v1` | `thesis` (**NEW** row) | `POLICY` `[P]` (operator-declared intent) | `policy_ingestion` (declared, `[P]`) — but the record is *content*, not a rule file; `observation_ingestion`'s declared-shape precedent | **NEW** `knowledge/thesis_ingestion.py` + additive row |
| `policy/v1` | `policy` (**REUSE**) | `POLICY` `[P]` | `policy_ingestion` **verbatim** — add the domain's `account_rules.md` + the two audit files to `discover_policy_paths` | **none** (config only) |

**`source_type` registration** reuses the additive-registration discipline
(`knowledge.SOURCE_TYPES`, `knowledge.py:125-149`): four rows, each `SourceTypeSpec("observation",
…)` — `market`/`portfolio`/`trade` are `MEASURED [M]`, `thesis` is `POLICY [P]`. No new
`message_family`, no new envelope, no new transport (hard rule 2).

**The `[X]` mapping (a finding, stated once).** The domain audits tag market data `[X]` (external
vendor). The knowledge plane has **no EXTERNAL authority tier** — the `Authority` ordering is
`POLICY > SOURCE > MEASURED > DERIVED > ADVISORY` (`knowledge.py:61`). The mapping is therefore:
`[X]` **is provenance-by-locator, not a new authority** — an external observation is recorded as
`observed` → `MEASURED [M]` with the vendor **named in `source_uri`/`logical_locator`**
(e.g. `source_uri = "mx://Bourse_de_Montreal/options_chain"`). A new `EXTERNAL` authority is
explicitly **rejected**: the ordering is load-bearing and fixed. In the fact plane the same value
is `epistemic_status="observed"` (`EPISTEMIC_MAP`, design § 3.4).

**The `[C]` split.** The observable audit tags greeks/IV as `[C]` (computed). Those are **not**
producer records — they are fact-plane **reducers** over `market` records (§ 2). A producer
captures what was observed; a reducer computes what follows. Keeping that split is what makes the
blocked-predicate list (§ 2B) computable.

---

## 2. PREDICATES — `FACT_PREDICATES` candidates and their reducers

Each row is a `PredicateSpec` (design § 3.5) with the load-bearing invariant enforced literally:
**`produced_by` non-empty.** A predicate whose producer is gated on the missing chain (`MD-4`) is
therefore *not declared at all* — it is listed in § 2B as **blocked**, with the producer it
needs. (This is the same discipline that keeps `budget`/`deadline_slack` out of
`FACT_PREDICATES` — design § 3.5 "absent and why".)

The domain introduces **additive** `subject_type`/`scope_type` values — `instrument`, `position`,
`portfolio`, `decision` — because the CAP seed vocabulary is framework-flavored
(`job|workflow|workload|…`, design § 3.1). Additive, mirroring how `policy` is already a
`subject_type`.

### 2A. Declarable once its producer lands (migration phase 1) — none exists in the repo today

| predicate | value_type | subject | scope | level | produced_by | ttl | volatile |
|---|---|---|---|---|---|---|---|
| `last_price` | float (`usd`/`cad`) | instrument | portfolio | fact | `market_facts/v1` | 1 day | yes |
| `daily_ohlcv` | float ×4 | instrument | portfolio | fact | `market_facts/v1` | none | no |
| `realized_vol` | float | instrument | portfolio | fact | `market_facts/v1` (reducer over `daily_ohlcv`) | none | no |
| `position_qty` | float | position | portfolio | fact | `portfolio/v1` | 1 day | yes |
| `avg_cost_basis` | float | position | portfolio | fact | `portfolio/v1` | none | no |
| `cash_balance` | float (`usd`/`cad`) | portfolio | portfolio | fact | `portfolio/v1` | 1 day | yes |
| `buying_power` | float | portfolio | portfolio | fact | `portfolio/v1` | 1 day | yes |
| `contribution_room` | float (`usd`) | portfolio | portfolio | fact | `portfolio/v1` (CRA NOA, `[X]`→observed) | 1 year | no |
| `thesis_exists` | bool | decision | portfolio | fact | `thesis/v1` | none | no |
| `portfolio_value` | float (`usd`) | portfolio | portfolio | job | `portfolio_facts/v1` | none | no |
| `position_weight` | float | position | portfolio | job | `portfolio_facts/v1` | none | no |
| `crypto_weight` | float | portfolio | portfolio | job | `portfolio_facts/v1` | none | no |
| `unrealized_pnl` | float (`usd`) | position | portfolio | job | `portfolio_facts/v1` | none | no |
| `realized_pnl` | float (`usd`) | position | portfolio | job | `trade_facts/v1` | none | no |
| `calls_only_holds` | bool | portfolio | portfolio | policy | `policy_facts/v1` | none | no |

### 2B. Blocked (producer gated on the missing chain `MD-4`) — NOT declared, listed for instrumentation order

| predicate | blocked by | unblocked at |
|---|---|---|
| `option_delta` | needs `MD-4` chain (greeks) | adapter step 1 → reducer step 3 |
| `option_iv` | needs `MD-4` chain | adapter step 1 → reducer step 3 |
| `iv_rank` | needs `option_iv` **time series** — plus ≥52 weeks of *accumulated* history before the rank is non-empty | reducer step 5 + 52-week accumulation (cold start) |
| `dte` | needs `MD-4` chain (expiries) | reducer step 4 |
| `chain_liquidity` | needs `MD-4` chain (OI/volume/spread) | reducer step 4 |
| `net_delta` | needs `option_delta` for the option leg | reducer step 3 |

The instrumentation steps are those fixed in `audit_policies.md` § 3 (1 = `MD-4` adapter,
2 = realized-vol reducer, 3 = greeks/IV, 4 = dte/liquidity, 5 = iv_rank). Note the dependency
shape: **6 blocked predicates, 5 of them gated on a single missing producer** (the chain adapter);
`net_delta` is the one that additionally blocks policy (b) `no_short_delta`.

### 2C. The reducers (deterministic formulas, `ReducerSpec` shape)

The four reducer modules mirror the design's `src/agentic_dynamics/control/reducers/` layout
(spec_status / attempt_facts / job_facts / workflow_facts / policy_facts):

| Reducer | version | consumes | produces | formula (inputs) |
|---|---|---|---|---|
| `market_facts` | `market_facts/v1` | `market` records | `last_price`, `daily_ohlcv`, `realized_vol` | `realized_vol = std(ln(P_t / P_{t-1}))` over a window of `daily_ohlcv` closes |
| `portfolio_facts` | `portfolio_facts/v1` | `portfolio` + `market` | `portfolio_value`, `position_weight`, `crypto_weight`, `unrealized_pnl`, (`net_delta` when unblocked) | `portfolio_value = Σ position_qty·last_price·fx_to_cad + Σ cash·fx_to_cad` (all-in-CAD, fx from PS-10); `position_weight = position_value / portfolio_value`; `unrealized_pnl = qty·(last_price − avg_cost_basis)·fx_to_cad` |
| `trade_facts` | `trade_facts/v1` | `trade` records | `realized_pnl` | `realized_pnl = Σ (sale proceeds − cost − commission)` over fills per position |
| `policy_facts` | `policy_facts/v1` | `portfolio` + `trade` + `policy` | `calls_only_holds` | `calls_only_holds = (no short put) ∧ ∀ short call: shares(underlying) ≥ multiplier·qty` — input contract: `position_qty` is **signed** (short legs negative), `multiplier` is the contract's **deliverable multiplier** (100 standard; non-standard after a corporate action, CX-6), and `EX-4` assignments re-key positions before the reducer runs |

Every reducer is a **pure function** (`determinism="pure"`, injected clock via `ReducerInput.now`)
— the same discipline as `step_routing.route_step` and the design § 4.1. `net_delta` and the
greek predicates are listed in their reducer's `produces` only **after** § 2B unblocks; the
`produced_by` non-empty invariant is what enforces that ordering mechanically.

---

## 3. CONTRACTS — decision-type contracts

Versioned YAML in `experiments/contexts/<decision_type>.yaml` (design § 6.1). Two new, one reuse.

### 3a. `open_long_call/v1` (**NEW**) — the opening decision

```yaml
# experiments/contexts/open_long_call.yaml
decision_type: open_long_call
contract_version: "open_long_call/v1"
decision_scope: portfolio
allowed_actions: [open_long_call, open_covered_call, skip]

invariants:
  - fact: calls_only_invariant      # L5 declared policy fact — the (a) invariant
    scope: portfolio
    on_missing: halt                # no calls-only rule => refuse to open anything
    on_conflict: halt
  - fact: registered_account_limits # L5 — (c) eligibility/margin
    scope: portfolio
    on_missing: halt

requires_facts:
  - fact: calls_only_holds          # derived gate (§ 2A) — proves no naked exposure pre-open
    scope: self
    max_age_seconds: 3600
    on_missing: halt
  - fact: contribution_room         # (c) — do not open beyond registered room
    scope: self
    on_missing: halt
  - fact: portfolio_value           # (d) sizing denominator
    scope: self
    on_missing: halt
  - fact: net_delta                 # (b) — BLOCKED until MD-5; declared here as a *required* fact
    scope: self                     #   so the compiler's R1 refusal is the mechanism that blocks
    on_missing: halt                #   this arm, not a convention. Revisit at § 2B step 3.
```

*Design decision:* `net_delta` is **listed with `on_missing: halt` rather than omitted** — the
contract states the need; the compiler's `R1` (required fact has no declared predicate) is the
*mechanical* refusal. That is the load-bearing rule expressed as a refusal, not a comment.

### 3b. `weekly_review/v1` (**NEW**) — the reconciliation decision

```yaml
decision_type: weekly_review
contract_version: "weekly_review/v1"
decision_scope: portfolio
allowed_actions: [record_finding, adjust_policy, noop]

requires_facts:
  - fact: thesis_exists             # (h) — the thesis → outcome chain (DR-1..DR-5)
    scope: self
    on_missing: classify            # a week with no new thesis is legitimately empty
  - fact: realized_pnl              # outcome leg
    scope: self
    on_missing: classify
  - fact: calls_only_holds          # invariant still held over the week
    scope: self
    on_missing: halt
excludes: [live_telemetry, advisory_facts]
```

### 3c. `session_routing` (**REUSE**) — I10 addendum A.4

The domain does **not** author a session contract. It reuses the CAP I10
`session_routing` decision-type (`allowed_actions: [continue, fork, compress_and_fork,
escalate]`) verbatim. This is the one place the domain deliberately *imports* framework machinery
instead of declaring its own: sessions are disposable; the typed `SessionCheckpoint` is the
handoff. Shadow mode until measured (`audit_policies.md` policy (h) discipline).

---

## 4. ADAPTERS — the market-data adapter (no live trading)

One new adapter in the `adapters` plane, shaped exactly as `opencode.py`/`claude_adapter.py` are:
a thin, deterministic, no-order-emission client over a named source.

```python
# src/agentic_dynamics/adapters/market_data.py  (NEW)
@dataclass(frozen=True)
class MarketSource:
    """A named, unconnected vendor. Naming is the [X] discipline; no keys, no scraping."""
    name: str                 # "mx", "tmx_datalinx", "boc", "kraken"
    uri_template: str         # "mx://Bourse_de_Montreal/options_chain/{symbol}"
    rate_limit_hint: str = "" # advisory only

def fetch(source: MarketSource, symbol: str, kind: str, *, asof: str) -> bytes:
    """Read ONE named snapshot (EOD file / static export). NO network in Stage-0: the operator
    drops vendor files; fetch() is a file-read with a schema guard. Never an order."""

def canonicalize(raw: bytes, schema: str, *, version: str = "market/v1") -> list[MarketRecord]:
    """Deterministic bytes -> typed MarketRecord list. Versioned schema folded into ids."""

def publish(records: list[MarketRecord], *, repository_id: str, revision: str, now) -> int:
    """record_factory.build_record -> record_to_artifact -> record_to_event ->
    knowledge_stream.publish_event. The EXISTING pipe, nothing new."""
```

**The three-stage shape is fixed and each stage has a reason:**

| Stage | Does | Guard |
|---|---|---|
| `fetch` | reads one named source | `asof` pinned; no keys; no scraping; read-only |
| `canonicalize` | bytes → typed records | deterministic, schema-versioned; the schema *is* the extractor |
| `publish` | records → KB stream | existing write guard (`FINOPS_KB_WRITE=1` or `authorized=True`); `source_type="market"` |

**No live trading is structural, not a convention:** the adapter has no `submit`/`route`/`trade`
method, and its output `source_type` is in the `observation` family — `knowledge_stream`'s
actuation gate (`ACTUATION_TYPES = {"actuation"}`, closed-by-default) refuses any action record it
did not emit. The adapter cannot, by construction, write an actuation.

---

## 5. WORKFLOWS / STORIES — the domain's workflow specs

Three `agent_task` workflow specs (the `ExperimentSpec` with `workflow.kind: agent_task`, as
`workflows/repository/context_abstraction_implement.yaml` is). They are **domain** specs and live
in the **new** repo (§ 7), not in this repo's `workflows/`.

### 5a. `research_ticker` (**NEW**) — thesis formation

```yaml
name: research_ticker
artifact_kind: workflow
workflow:
  kind: agent_task
  params:
    language: python
    fork: true
    phases:
      - name: locate_sources    # named sources only — market/v1, issuer IR, CDS calendar
      - name: derive_thesis     # writes thesis/v1 record (DR-1/DR-2), NOT an order
      - name: propose_trade     # proposed order only; execution is the operator's, off-ledger
```

### 5b. `backtest_strategy` (**NEW**) — evidence before policy

```yaml
name: backtest_strategy
workflow:
  kind: agent_task
  params:
    phases:
      - name: load_market_data    # consume `market` records (historical OHLCV)
      - name: define_signal       # a deterministic reducer, unit-tested
      - name: run_backtest        # emit trade_facts/v1 (paper fills) — the evidence seed (§ 7)
      - name: report_metrics      # realized_pnl, max drawdown, hit rate — [C] reducers
```

### 5c. `weekly_review` (**NEW**) — the reconciliation

```yaml
name: weekly_review
workflow:
  kind: agent_task
  params:
    phases:
      - name: reconcile_theses   # bind DR-1 thesis -> DR-3 execution -> DR-5 outcome
      - name: emit_findings      # publish review-family records; contract = weekly_review/v1 (§ 3b)
```

*Why workflows, not stories:* `run_story`'s builtins (`task_manager_api`, …) are software-construction
stories with mutation conditions; the domain's three tasks are deterministic review/research/backtest
tasks with no perturbation operator — the `agent_task` workflow (`run_workflow.py`, per-phase commit
+ ledger) is the exact transport. (`backtest_strategy`'s paper fills *do* produce `trade` records,
which is the bridge to the evidence seed.)

---

## 6. The provisional `DomainProfile` + `ChallengeProfile` blocks (CAP I8 static filing)

These mirror the I8 dataclasses (addendum A.2) field-for-field. They are a **static filing** in
the new repo today; when I8 lands, a `profile_facts/v1` reducer parses them into `declared`
(POLICY) profile facts. Until then they are YAML/markdown, not facts — never measured, never
applied.

```yaml
# docs/domain/investing/profile.yaml   (provisional — lifts into `declared` facts at CAP I8)
domain_profile:
  domain: investing
  canonical_sources:
    - docs/domain/investing/audit_observable.md     # d1 — the signals
    - docs/domain/investing/audit_policies.md       # d2 — the policies
    - docs/domain/investing/audit_gap_map.md        # d3 — this file
    - account_rules.md                              # the [P] invariant/limit source of truth
  predicates:            # a highlighted subset of the domain's § 2A registrations
    - last_price
    - portfolio_value
    - position_weight
    - crypto_weight
    - calls_only_holds
    - contribution_room
    - thesis_exists
  policies:              # L5 policy fact ids (audit_policies.md, the 8 policies)
    - calls_only_invariant
    - no_short_delta
    - registered_account_limits
    - position_size
    - exit_rules
    - expiry_selection
    - crypto_cap
    - weekly_review
  patterns: []           # I9 — empty until a campaign mints a measured pattern (never invented)
  verification: []       # no pytest/ruff analog for the domain yet; reserve the slot

challenge_profiles:
  - challenge: research                # research_ticker
    context_requirements: [last_price, thesis_exists]
    deliberation: [locate_sources, derive_thesis, propose_trade]
    session_policy: continue           # I10 — shadow until measured
    verification_policy: [thesis_has_sources]
  - challenge: backtest                # backtest_strategy
    context_requirements: [daily_ohlcv, realized_vol]
    deliberation: [load_market_data, define_signal, run_backtest, report_metrics]
    session_policy: continue
    verification_policy: [signal_is_pure_function]
  - challenge: review                  # weekly_review
    context_requirements: [thesis_exists, realized_pnl, calls_only_holds]
    deliberation: [reconcile_theses, emit_findings]
    session_policy: continue
    verification_policy: [chain_is_complete]
```

*Discipline (same as every policy):* profile facts are `declared` at construction; their
*performance* is measured by campaigns before any is promoted — the identical ladder
`audit_policies.md` records for the 8 policies. A profile can never widen a controller's view:
its `context_requirements` resolve through the same `requires_facts` mechanism (addendum A.2).

---

## 7. MIGRATION — this repo vs the new repo, and the sequence

### 7a. The split

| Concern | Runs in **this** repo (framework) | Lives in the **new** repo (investing) |
|---|---|---|
| **Code** | the producer machinery (`market/portfolio/trades/thesis` ingestion), the fact-plane reducers, the contracts engine, the adapter, the CLI/analysis | the raw domain data + configs only — broker exports, market EOD files, theses, `account_rules.md`, `profile.yaml`, the three workflow specs |
| **`repository_id`** | framework id (existing `REPOSITORY_ID`) | a **new** `repository_id` (e.g. `org:investing`); every record carries it, so the two corpora never collide. The KB scope default `self-<worktree>` applies; an explicit non-empty `repository_id` is the **shared-scope override** (mental-model two-channel rule) |
| **Redis** | `finops-queue` 6380 (queue) + knowledge stream **DB 2 on 6380** | **reuses the same DB 2 stream**, scoped by `repository_id` — no new Redis. The story-agent `finops-redis` 6379 is **never** touched (AGENTS.md isolation) |
| **Results** | `experiments/results/` = the framework's own research corpus (kb, facts, stories) | its **own** results dir (namespaced), never mixed into the framework corpus — so `analyze_worktrees`/`build_data`/the lab books stay domain-agnostic |

**Rule stated once:** the framework is the *instrument*; the new repo is the *subject*. The only
code that moves is none — the new repo holds data + configs + domain specs; all producers and
reducers run from this repo against the new repo's `repository_id`.

### 7b. The sequence (four seeds → first campaign)

| Phase | What lands | Which mechanism | Exit criterion |
|---|---|---|---|
| **1. context seed** | `market/v1` + `portfolio/v1` + `trades/v1` + `thesis/v1` producers, the adapter, `policy/v1` via existing `policy_ingestion` | § 1, § 4 | named-source observations fill the new `repository_id`; `last_price`…`calls_only_holds` reducers (§ 2A) run green |
| **2. evidence seed** | a **paper-trade ledger** — `backtest_strategy`/paper fills emit `trade` + `portfolio` + `market` records | § 5b, `trade_facts/v1` | every § 2A predicate has a populated slot; the `[H]` hypotheses have `[M]` evidence to be judged against |
| **3. policy seed** | the 8 policies (`audit_policies.md`) run in **shadow mode** — recorded + surfaced, never applied | contracts § 3 + I6 shadow-controller pattern | each policy's outcome measured against the evidence seed; writable-vs-pending reconfirmed with data |
| **4. first campaign** | a grid over one factor (e.g. `calls_only` arm vs a relaxed baseline) | the repo's grid → campaign loop (`compile_experiment`, reuse of `_gen_matrix_cells`/`simulate_strategies`) | one variable tweaked, results compared, `_results_summary` written |

This is the load-bearing rule at the domain scale: **instrument (context seed) → derive (§ 2
reducers) → policy (shadow seed) → grid (campaign)**. Each phase is gated on the previous; a
policy that is still pending-instrumentation (`audit_policies.md`: b/d/e/f) cannot enter phase 3
until its blocked predicates (§ 2B) unblock — which is exactly the § 3a `net_delta on_missing:
halt` refusal.

---

## LOG

**Gap counts per category**

| Category | Reuse | NEW | Blocked |
|---|---|---|---|
| Producers | 1 (`policy/v1`) | 4 (`market`, `portfolio`, `trade`, `thesis`) | 0 |
| Predicates | 0 | 15 declarable-once-produced (§ 2A) | 6 (§ 2B, all gated on `MD-4` except `net_delta`) |
| Contracts | 1 (`session_routing`) | 2 (`open_long_call/v1`, `weekly_review/v1`) | 0 |
| Adapters | 0 | 1 (`market_data`) | 0 |
| Workflows/stories | 0 | 3 (`research_ticker`, `backtest_strategy`, `weekly_review`) | 0 |
| Profiles | 0 | 1 `DomainProfile` + 3 `ChallengeProfile` (static filing) | 0 |
| Migration phases | 0 | 4 (context → evidence → policy → campaign) | 0 |

**Guard checks**

- [x] Every new kind maps to an existing mechanism (module named) or is marked `NEW`. **PASS.**
- [x] Producers map to `ledger_ingestion`/`policy_ingestion` patterns; `policy/v1` is reuse-only. **PASS.**
- [x] Predicates honor the `produced_by` non-empty invariant — blocked predicates are listed, not declared. **PASS.**
- [x] Blocked predicates carry their unblock step (§ 2B) consistent with `audit_policies.md` § 3. **PASS.**
- [x] Profile blocks mirror the I8 `DomainProfile`/`ChallengeProfile` dataclass fields. **PASS.**
- [x] Adapter has no live-trading surface (observation family only; actuation gate closed). **PASS.**
- [x] `[X]` mapped to provenance-by-locator, no new authority tier. **PASS.**

**Result: PASS** — 4 new producers, 21 candidate predicates (15 declarable-once-produced / 6 blocked), 2 new
contracts + 1 reuse, 1 adapter, 3 workflow specs, 4 profile blocks, 4 migration phases; every new
kind traced to a mechanism or marked NEW.

**Commit:** recorded on branch `feature/investing-domain-audit`.
