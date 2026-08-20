---
status: accepted
---
# Per-Step Model Routing + Cache-Aware Forking — Design

Status: design (phase 2 of `experiments/specs/workflow_step_routing.yaml`) · Preceded by
`docs/routing_survey.md` (survey of the current state, all `file:line` citations there still hold).

This document specifies how to add intelligent per-step model routing to the workflow layer.
It does **not** re-implement transport — it layers a decision function on top of the machinery
that already exists (`routing.py`, `workflow_runner.py`, `opencode.py` / `claude_adapter.py`).

---

## 0. Scope and the load-bearing rule

The routing policy is a **control rule**: it *consumes* information. Per
`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md:35-64` and the validator at
`src/instrument/experiment_spec.py:367-403`, a control rule may only consume signals that are
either in `LEDGER_FIELDS` (`experiment_spec.py:44-97`) or `produces`-declared by a measurement
rule in the same spec. Concretely, for this design:

- **Allowed to consume today** (measured): `cost`, `correctness`, `efficiency` (derived),
  `cache_hit_rate`, and the `SolutionMetrics` quality dimensions (`constraint_score`,
  `code_quality_score`, `novelty_score`, `composite_score`) — all present in
  `_results_summary.json` entries / `compute_routing()` / `lab_cache_economics.json`.
- **Must be instrumented before consumption** (`edge_case_coverage`): §5 specifies a measurement
  rule that `produces` it; until that rule ships, any preference objective referencing it is
  refused by the validator (mirror of `experiment_spec.py:396-402`).
- **Must NOT be consumed** (`confidence`): unmeasured, `model_cascade`-only. Excluded from the
  signal vocabulary below; a reference to it is a hard validation error.

---

## 1. The step (phase) schema — per-step model selection

A workflow phase already declares `name`, `kind`, and `prompt` (see
`experiments/specs/workflow_step_routing.yaml:32-187`; consumed at `workflow_runner.py:266-268`).
We add a **model selector** to the phase dict. Each phase declares **exactly one** of three
forms:

```yaml
phases:
  # (1) PIN — this exact model; the router must honor it, no scoring.
  - {name: survey,  kind: agent, model: deepseek/deepseek-v4-pro, prompt: "..."}

  # (2) SUBSET — choose only from this list.
  - {name: design,  kind: agent,
     allowed_models: [deepseek/deepseek-v4-pro, anthropic/claude-sonnet-5],
     prompt: "..."}

  # (3) UNCONSTRAINED — neither key present → full pool.
  - {name: implement, kind: agent, prompt: "..."}
```

The full pool is `workflow.params.model_pool` (already declared in
`experiments/specs/workflow_step_routing.yaml:14-22`). If `model_pool` is absent, it defaults to
the `model` factor's levels; if neither exists, the spec fails validation.

### 1.1 Selection semantics (fixed)

| Step declares | Eligible set `E` | Router behavior |
|---|---|---|
| `model: <id>` | `{<id>}` | return `<id>` verbatim, bypass scoring |
| `allowed_models: [...]` | the declared subset | score only that subset |
| neither | full `model_pool` | score the whole pool |

The choice within `E` (cases 2 and 3) is **always** the argmax of a preference score over
measured signals (§3) with a deterministic tie-break (§6). There is no random selection and no
"first element of the pool" fallback — a first-element pick is explicitly forbidden by the spec
(`workflow_step_routing.yaml:94`).

### 1.2 Load-time validation

Extend `validate_spec` (or a sibling `validate_step_routing`) with these checks, all evaluated
when a spec is loaded / before `run_workflow`:

1. A phase has **at most one** of `model` / `allowed_models`. Both present → error.
2. `allowed_models` is a non-empty list (empty subset → error), with **no duplicate ids**, and
   every id is a member of `model_pool` (unknown id → error).
3. A pinned `model` id is a member of `model_pool` (pin outside pool → error).
4. `model_pool` (when declared) is non-empty and duplicate-free.
5. Every `preferences` objective references a known signal (§3.1); unknown signal → error.
6. A `preferences` objective referencing `edge_case_coverage` or `confidence` passes through the
   requires/produces gate of §5 (refused unless instrumented).

These mirror the existing structural checks in `experiment_spec.py:406-446`.

---

## 2. `route_step` — signature and selection algorithm

### 2.1 Signature

```python
# src/instrument/step_routing.py  (new module)

@dataclass
class Objective:
    signal: str        # one of MEASURED_SIGNALS (or edge_case_coverage once produced)
    direction: str     # "minimize" | "maximize"
    weight: float      # >= 0; all-zero weights = all-equal = tie-break path

@dataclass
class RoutingPreferences:
    objectives: list[Objective]      # parsed from the preferences block

@dataclass
class ModelSignals:
    model: str
    correctness: float = 0.0
    cost: float = 0.0               # USD per unit of work (entry avg)
    efficiency: float = 0.0         # correctness / cost, [C] derived
    cache_hit_rate: float = 0.0     # 0..1
    constraint_score: float = 0.0
    code_quality_score: float = 0.0
    novelty_score: float = 0.0
    composite_score: float = 0.0
    edge_case_coverage: float | None = None   # None until instrumented (§5)

@dataclass
class RouteState:
    pool: list[str]                        # full model pool
    prev_model: str | None                 # model of the completed prior step
    prev_session_id: str                   # "" on the first step
    prev_cache_read_tokens: int            # prior step's cache reads (prefix volume)
    context_tokens: int                    # prior step's context footprint

def route_step(job: dict, state: RouteState, prefs: RoutingPreferences) -> str:
    ...
```

`job` is the phase dict (carrying `model` / `allowed_models` / `kind` / `name`). `state` carries
everything the router needs about the fork chain (§4). `prefs` is the parsed objective set (§3).

### 2.2 Algorithm

1. **Resolve the eligible set** (§1.1). If the phase has `model`, return it immediately
   (pin wins — `workflow_step_routing.yaml:147`).
2. **Load measured signals** for each candidate from the signal store (built from
   `_results_summary.json` entries + `compute_routing()` `models` stats + `lab_cache_economics.json`).
3. **Drop candidates with no measurement** into a "cold" bucket (§6.4); do not fabricate numbers.
4. **Apply the cache-continuity adjustment** (§4.3): fold the model-switch prefix penalty into the
   `cost` signal of any candidate whose model differs from `state.prev_model`, producing an
   *effective cost* per candidate.
5. **Score each candidate** with the preference scoring function (§3.2) over the eligible set.
6. **Select `argmax`**; on a tie, apply the deterministic tie-break (§6.2).
7. Return the winning `model` id.

The router is a **pure function** over `(job, state, prefs)` — no I/O, no RNG — which makes it
unit-testable and keeps the same `route_step` reusable in `run_workflow`, the compiler's
`compare_arms`, and future enqueue-time routing.

---

## 3. Preferences schema + scoring function

### 3.1 Schema

A `preferences` block expresses weighted objectives over **measured** signals:

```yaml
preferences:
  objectives:
    - {signal: cost,              direction: minimize, weight: 1.0}
    - {signal: correctness,       direction: maximize, weight: 1.0}
    - {signal: cache_hit_rate,    direction: maximize, weight: 0.5}
    # edge_case_coverage is gated — see §5. confidence is forbidden — see §0.
```

**Signal vocabulary (measured today):**

| signal | direction | source | provenance |
|---|---|---|---|
| `cost` | minimize | `_results_summary.json` entries (`cost`), `compute_routing` model stats | [M] |
| `correctness` | maximize | entry `correctness` | [M] |
| `efficiency` | maximize | `correctness / cost` | [C] |
| `cache_hit_rate` | maximize | `lab_cache_economics.json`, per-phase ledger | [M] |
| `constraint_score`, `code_quality_score`, `novelty_score`, `composite_score` | maximize | `SolutionMetrics` (`solution.py:41-62`) | [M]/[H] |
| `edge_case_coverage` | maximize | **not yet produced** — §5 | [M] (once instrumented) |

`confidence` is deliberately **absent**; a reference to it is a hard error.

### 3.2 Scoring function

For each candidate `m` in the eligible set `E`:

1. **Normalize** each objective signal into `[0,1]` relative to `E`, honoring direction:

   ```
   minimize:  norm_s(m) = (max_E(s) - s(m)) / (max_E(s) - min_E(s))
   maximize:  norm_s(m) = (s(m) - min_E(s)) / (max_E(s) - min_E(s))
   ```

   If `max_E(s) == min_E(s)` (zero variance), set `norm_s(m) = 0.5` for every candidate — the
   signal carries no information within this step, so it contributes neutrally (§6.3).

2. **Weighted sum**, re-normalized to the objectives actually present:

   ```
   score(m) = Σ_s w_s · norm_s(m) / Σ_s w_s     (over objectives whose signal exists)
   ```

   If all weights are zero, `score(m) = 0.5` for every candidate and the tie-break decides (§6.2).

3. **Missing signal handling** (§6.4): if a signal is absent for *some* candidates, those
   candidates are scored on the *remaining* objectives (their weights re-normalized) and flagged
   with higher uncertainty; if a signal is absent for *all* candidates, that objective is dropped
   from this step entirely. We never impute a value.

The "lowest cost with highest edge-case coverage" example (`workflow_step_routing.yaml:106-109`)
maps to `{cost: minimize, weight: 1.0}` + `{edge_case_coverage: maximize, weight: 1.0}` — and
today that spec is **refused** (edge_case_coverage not produced), which is the correct behavior
per the load-bearing rule; see §5.

### 3.3 Tie and fallback behavior

Deterministic total order on `(score, switch_penalty, cost, model_id)`:

1. Highest `score`.
2. Prefer the candidate whose model equals `state.prev_model` (avoid an unnecessary switch —
   continuity is free when scores are tied).
3. Lower effective `cost`.
4. Lexicographically smallest `model` id (a stable, reproducible final arbiter).

No randomness, no first-element bias.

---

## 4. Cache-aware fork chaining + the model-switch trade-off

### 4.1 What already exists

Fork chaining is implemented in `workflow_runner.py` and must be **extended, not rewritten**:

- `workflow.params.fork` gates it; `fork=None` → spec flag (`workflow_runner.py:262`).
- Each agent phase passes the prior session id with `fork=True` only when `prev_model == model`
  (`workflow_runner.py:304-310`), via `--session <id> --fork` (opencode) or
  `--resume <id> --fork-session` (claude).
- The prior session id is captured from `AgenticResult.session_id` after each phase
  (`workflow_runner.py:328-332`).
- Cache tokens are recorded per phase (`workflow_runner.py:325-327`), parsed from
  `step_finish.tokens.cache.{read,write}` (`opencode.py:498-501`) / Claude usage
  (`claude_adapter.py:49-72`).

### 4.2 The chaining design (per step, now router-driven)

The only change is that the model per step is **chosen by `route_step`** instead of being the
single workflow-level `model`. The loop becomes:

```
prev_session_id = ""; prev_model = None
for phase in phases:
    model_i = route_step(phase, state(prev_model, prev_session_id, prev_cache_read), prefs)
    run phase with model_i
        if prev_session_id and prev_model == model_i:
            fork(prev_session_id)          # --session/--fork or --resume/--fork-session
        else:
            fresh session                  # cache prefix breaks
    capture session_id_i, cache_read_tokens_i, context_tokens_i
    prev_session_id, prev_model = session_id_i, model_i
```

This is exactly the existing `workflow_runner.py:266-332` flow with `model` replaced by
`model_i = route_step(...)`. First step: `prev_session_id == ""` → no fork, no continuity term.

### 4.3 The trade-off: switching model breaks the cache prefix

A fork reuses the prior session's **context prefix as a cache read** (`opencode.py:220-223`).
A model switch breaks that prefix (different model → different cache keys; different provider →
different cache namespace), so the shared prefix must be re-sent at **input** rates on the next
step. The router must price this *before* selecting.

**Model as an effective-cost adjustment.** Fold the switch penalty into the `cost` signal:

```
switch_penalty(m) = 0                                        if m == prev_model
switch_penalty(m) = prev_cache_read_tokens
                    · ( input_rate(prev_provider) − cache_read_rate(prev_provider) )
                    / 1_000_000                               if m != prev_model

effective_cost(m) = cost(m) + switch_penalty(m)
```

The rates come from `PROVIDER_PRICING` (`efficiency.py:41-85`). For DeepSeek the spread is
`0.435 − 0.003625 = $0.431375`/1M tokens — a ~120× re-read penalty (`workflow_step_routing.yaml:24-27`),
so a switch only wins when the target model's cost+quality advantage exceeds the re-read cost.
Cross-provider switches (e.g. `deepseek/* → anthropic/*`) always pay the full penalty; we treat
**any** model change as a full prefix loss (same-provider model changes are conservatively assumed
to invalidate the prefix too — safe default until measured otherwise).

The result: `route_step` sees the switch cost as part of `cost`, so the preference weighting
("lowest cost") naturally punishes unnecessary model churn while still allowing a switch when
the target is materially better. The prior step's `cache_read_tokens` is the only new state the
router needs, and it is already recorded per phase (`workflow_runner.py:325`).

---

## 5. `edge_case_coverage` — instrumentation plan + validator gating

`edge_case_coverage` is **not** in `LEDGER_FIELDS` (`experiment_spec.py:44-97`) and is measured
nowhere. Two paths, one of which must be chosen before any preference may consume it.

### 5.1 Instrument it (recommended): a measurement rule that `produces` it

Add a branch-coverage pass to the independent test harness (`test_runner.py`, which already owns
"run the tests ourselves" — `run_suite` at `test_runner.py:113-135`):

```python
# src/instrument/test_runner.py  (new)
def run_coverage(workdir: Path, language: str, *, timeout: int = 300) -> dict:
    """Run the suite under branch coverage; return branch_coverage (0..1) + branch_total."""
    # python:   coverage run --branch -m pytest ... && coverage json  → branch coverage
    # ts/go/rust: jest --coverage / go test -coverprofile / cargo llvm-cov (best-effort, else None)
```

The coverage fraction over **branch** coverage (not line coverage) is the honest "edge cases are
exercised" signal; line coverage overstates trivial pass-through paths. A stronger future option is
a **mutation-test pass rate** (killed/total mutants) — a better proxy for edge-case detection but
more expensive; specify branch coverage now, mutation score as a `[H]` upgrade later.

Then declare it as a measurement rule in the spec so the validator admits it:

```yaml
rules:
  - {name: edge_case_measure, plane: measurement, evidence_class: "[M]",
     requires: [test_executed_success],        # only meaningful when the suite actually ran
     produces: [edge_case_coverage]}
```

`test_executed_success` is already produced by the workflow's `test` phase
(`workflow_runner.py:278`); a measurement rule that `produces: [edge_case_coverage]` makes the
signal available to any control rule (mirroring the gate mechanics of
`experiment_spec.py:391-402`). The workflow's `verify`-style `test` phase additionally records the
coverage value into the phase ledger, alongside `test_executed_success`.

### 5.2 Gate it until it exists

A preferences objective referencing `edge_case_coverage` is validated the same way the compiler
validates `requires`:

```
validate_preferences(spec):
    produced = LEDGER_FIELDS ∪ {produces of every measurement rule}
    for objective in spec.preferences.objectives:
        if objective.signal not in MEASURED_SIGNALS and objective.signal not in produced:
            error(f"preference objective {signal!r} is not produced by the ledger or any "
                  f"measurement rule. Instrument it first (see docs/routing_design.md §5).")
```

`confidence` is in **neither** set and never will be for this policy — a reference is refused
unconditionally. Until `edge_case_measure` ships, the example objective
`{signal: edge_case_coverage, ...}` is refused exactly as `model_cascade` is refused for
`confidence` (`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md:56-59`).

This is the ordering the validator enforces: **measure (and instrument) → then policy.** The
routing policy may consume `edge_case_coverage` only after a measurement rule produces it.

---

## 6. Edge cases and fallbacks

1. **Pin honored unconditionally.** If a phase has `model`, the router returns it even if the
   model has no measured signal and even if it would lose the cache prefix. Pins are the operator's
   explicit override and are never second-guessed.

2. **Tie on final score.** Deterministic total order (§3.3): highest score → continuity
   (`prev_model`) → lower effective cost → lexicographic id. This is the *only* place ordering
   matters and it is fully deterministic.

3. **Zero-variance signals.** A signal with `max == min` across `E` normalizes to `0.5` for all
   candidates — it contributes no discrimination and is effectively ignored, without dividing by
   zero.

4. **Cold start / no measurement for a candidate or the whole set.** A candidate with no measured
   signals is scored on the objectives it *does* have (weights re-normalized); if **no** candidate
   has any measured signal, fall back to a static default — the `recommend_route` cheapest-qualified
   model over the eligible set (`routing.py:71-75`) if it can be computed, else the spec `model`
   factor's level, else the first model in `model_pool` **only as a last resort** (documented, not
   a random pick). Never `random.choice`.

5. **Empty eligible set.** `allowed_models` validated non-empty at load (§1.2); if runtime
   filtering still empties `E`, raise a spec error rather than silently route to an out-of-subset
   model (a pin violating its own `allowed_models` is a spec bug).

6. **`allowed_models` subset validation.** Unknown id, empty list, or duplicate ids are load-time
   errors (§1.2) — the router assumes a pre-validated subset at runtime.

7. **First step (no prior session).** `prev_session_id == ""` → no fork, no continuity term,
   `switch_penalty = 0` for all candidates (nothing to lose).

8. **Model switch.** Any `m != prev_model` pays the full prefix re-read penalty (§4.3); the fork
   is skipped for that step (`workflow_runner.py:304-310` unchanged) and a fresh session starts.
   Cross-provider switches are treated identically (full loss), and the switch is still allowed if
   the score justifies it.

9. **`confidence` / unknown-signal references.** Hard validation error, never a silent ignore —
   the router is never permitted to consume an unmeasured signal.

10. **`edge_case_coverage` requested but not produced.** Refused at load by the validator (§5.2);
    the operator either ships the coverage measurement rule or drops the objective.

---

## 7. Implementation map (phase 3)

| Change | Location | Notes |
|---|---|---|
| `Objective`, `RoutingPreferences`, `ModelSignals`, `RouteState`, `MEASURED_SIGNALS` | new `src/instrument/step_routing.py` | dataclasses per convention (`AGENTS.md`) |
| `route_step(job, state, prefs)`, `score_candidate(...)`, `validate_preferences(...)`, `validate_step_selector(...)` | `src/instrument/step_routing.py` | pure functions; reuse `recommend_route`/`compute_routing` for the cold-start default |
| phase selector parsing + load-time validation | extend `workflow_runner.py:266-268` and `experiment_spec.validate_spec` (`experiment_spec.py:406-446`) | pin / subset / unconstrained |
| router-driven model selection in the phase loop | `workflow_runner.py:266-332` | replace single `model` with `model_i = route_step(...)`; keep the `prev_model == model` fork guard |
| effective-cost cache adjustment | `step_routing.py` | uses `PROVIDER_PRICING` (`efficiency.py:41-85`) |
| `run_coverage` + branch-coverage result | `test_runner.py` | measurement rule producing `edge_case_coverage` |
| `edge_case_measure` measurement `RuleSpec` | spec YAML `rules:` | `requires: [test_executed_success]`, `produces: [edge_case_coverage]` |
| exports | `src/instrument/__init__.py` | per `src/instrument/CONTEXT.md` |

**Reuse, not re-derive:** `routing.py` stays the per-task signal aggregator; the step router is a
thin eligibility + preference layer on top, and `compute_routing()`/`recommend_route()` remain
intact (their consumers in `scripts/build_data.py:1112` and `admin/server.py:860-877` must keep
working — `workflow_step_routing.yaml:144-146`).
