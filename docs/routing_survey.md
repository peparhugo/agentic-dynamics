# Routing, Measurement & Session Forking — Survey

Status: survey · Scope: how routing, measurement, and session forking work **today**, and
the gap to per-step model selection + preference-aware routing.

---

## 1. Current routing path, end to end

### 1.1 What `recommend_route()` consumes and emits

`src/instrument/routing.py:21` — `recommend_route(task_type, entries, *, correctness_threshold=0.7, lead_margin=0.05)`.

**Consumes** (per `entries`, each element a dict carrying at least `model`, `correctness`, `cost`):

| Signal | Source | Where read |
|---|---|---|
| `model` | entry dict key | `routing.py:44` |
| `correctness` | scalar per entry (0–1) | `routing.py:56` |
| `cost` | scalar per entry (USD) | `routing.py:57` |
| `correctness_threshold` (0.7) | kwarg default | `routing.py:25`, `routing.py:71` |
| `lead_margin` (0.05) | kwarg default | `routing.py:26`, `routing.py:80` |

**What it computes internally** (not measured, derived): per-model averages and an efficiency
ratio `avg_correctness / max(avg_cost, 1e-6)` at `routing.py:54-64`.

**Emits** (`routing.py:83-95`):

- `default_model` — the cheapest model whose avg correctness ≥ threshold, else best-efficiency, else best-correctness (`routing.py:75`).
- `escalate_model` — the highest-correctness model, unless it *is* the default (`routing.py:76`).
- `routing` — `"escalate"` when `best_correctness - default_correctness > lead_margin`, else `"default"` (`routing.py:77-81`).
- `best_correctness_model`, `best_efficiency_model`, `models_tested`, `models` (per-model stats), and a human `recommendation` string (`routing.py:91-93`).

The decision rule is a fixed two-arm heuristic: **cheapest-qualified vs best-correctness**, with
one hardcoded margin. There is no user preference vector and no measured signal beyond the two scalars.

### 1.2 How entries are gathered and grouped

`src/instrument/routing.py:143` — `compute_routing(entries, *, min_models=2)`:

1. Filter to `valid`: drop `narration_failure` and `correctness < 0` (`routing.py:156`).
2. Group by `normalize_task(experiment)` — strips `_s0.5` / `_r2` suffixes (`routing.py:16-18`, `routing.py:158-161`).
3. Skip empty / `"?"` / `exp_*` tasks and any task with fewer than `min_models` distinct models (`routing.py:164-170`).
4. Call `recommend_route()` per task (`routing.py:171`).
5. `simulate_strategies()` over the valid corpus (`routing.py:173`, `routing.py:98-140`): single-model baselines plus a `grit_routed` strategy that replays each task's recommended model and sums its cost/correctness.

Returns `{_meta, per_task, strategies, routing_distribution}` (`routing.py:179-187`).

### 1.3 Where the output is consumed

- **`scripts/build_data.py:31`** imports `compute_routing`; **`build_data.py:1112`** serializes it into
  `firebase/public/data.js` under the `"routing"` key of `window.DYNAMICS_DATA` (the website's routing section).
- **`admin/server.py:61`** imports `compute_routing`; **`admin/server.py:860-877`** exposes `GET /api/routing`
  returning `jsonify(compute_routing(entries))` for the Control Room.
- **`admin/static/app.js:1358-1398`** fetches `/api/routing` and renders the per-task routing table
  (`task.routing === "escalate" ? "escalate" : "default"`) plus the strategy simulation.

Prior art: the original model-vs-model routing logic lives in `scripts/lab_task_routing.py` (hardcoded
`deepseek_default` / `escalate_to_claude` arms); `routing.py` is the generalized, provider-agnostic
rewrite of that lab (`routing.py:1-7`).

**Bottom line:** today's "routing" is an *offline, descriptive report* over completed experiment
entries — it recommends one model per **task**, not per **step**, and it never steers a live run.

---

## 2. Measured vs unmeasured signals

### 2.1 Measured today (a routing policy may consume these)

| Signal | Where measured | Evidence class |
|---|---|---|
| `correctness` (test pass rate) | `AgenticResult.correctness` `opencode.py:97-101`; `SolutionMetrics.correctness_score` `solution.py:138` | [M] |
| `cost` (USD) | `AgenticResult.estimated_cost_usd` `opencode.py:92` (parsed at `opencode.py:544-548`, fallback `compute_cost_estimate` `opencode.py:314-328`); `compute_efficiency.total_cost_usd` `efficiency.py:358` | [M]/[C] |
| `efficiency` | derived `correctness / cost` `routing.py:58`; `EfficiencyMetrics.efficiency_score` `efficiency.py:373` | [C] |
| `cache_hit_rate` | `AgenticResult.cache_hit_rate` `opencode.py:83-89` | [M] |
| `cache_read_tokens` / `cache_write_tokens` | `AgenticResult` `opencode.py:77-78`, parsed from `step_finish.tokens.cache.{read,write}` `opencode.py:498-501`; Claude: `cache_read_input_tokens` / `cache_creation_input_tokens` `claude_adapter.py:60-61` | [M] |
| token breakdown (in/out/reasoning/total) | `AgenticResult` `opencode.py:71-74`, summed per `step_finish` `opencode.py:494-505` | [M] |
| `SolutionMetrics` quality dims — `correctness_score`, `constraint_score`, `code_quality_score`, `novelty_score`, `composite_score` | `solution.py:41-62`, computed in `evaluate_solution` `solution.py:134-180` | [M]/[H] |
| Sonar static-analysis dims (`sonar_bugs`, `sonar_vulnerabilities`, `sonar_code_smells`, `sonar_cognitive_complexity`, `sonar_duplicated_lines_density`, ratings) | `solution.py:65-76` | [M] (when sonar-scanner present) |
| `test_executed_success`, `tests_passed`, `tests_total` | `PhaseResult` `workflow_runner.py:63-65`, set at `workflow_runner.py:276-278`; `AgenticResult.tests_passed/total` `opencode.py:66-67` | [M] |
| cache economics aggregate (hit rate, read/write split, context volume) | `scripts/lab_cache_economics.py:50-57` (reads `summary.cache_hit_rate`, `total_cache_reads`, `total_cache_writes`, `total_context_tokens`) | [M]/[C] |

Pricing is a single source of truth in `efficiency.py`: `PROVIDER_PRICING` `efficiency.py:41-85`
(incl. DeepSeek `cache_read=0.003625` vs `input=0.435` — cache read ≈ 120× cheaper), the OpenAI
long-context tier `CONTEXT_OVER_200K_PRICING` `efficiency.py:92-101`, and `get_pricing` / `_resolve_pricing_key`
`efficiency.py:153-184`.

### 2.2 NOT yet measured (the gaps)

| Gap | Why it matters | Where it's blocked |
|---|---|---|
| **`confidence`** | `model_cascade` / `dynamics` control arms require it (`experiment_spec.py:36-43`; design doc §7 `AttemptRecord.confidence`). No such field on `AgenticResult` or the ledger. | `validate_rules` refuses any control rule whose `requires` touch it — `experiment_spec.py:396-402`. |
| **edge-case / branch / mutation coverage** | No coverage signal exists anywhere — `solution.py` has `cyclomatic_complexity`, `comment_ratio`, `lines_of_code` (`solution.py:150-155`) but **no** branch coverage, no line coverage, no mutation score. A routing policy that wants to reward "tests that exercise edge cases" has nothing to consume. | Not instrumented; would need a coverage collection step in `validate_session.py` / `test_runner.run_suite`. |
| **`perturbation_strength`** (the `s` axis for `grit`) | `grit` rule requires `perturbation_strength + test_executed_success` (`experiment_spec.py:38-39`); `LEDGER_FIELDS` has `strength` (`experiment_spec.py:63`) but the design doc treats the precise `perturbation_strength` float as unmeasured in the ledger schema. | `experiment_spec.py:44-97` — deliberately absent from `LEDGER_FIELDS`. |
| **`answer` / `explanation` token split** | Unlocks the Explanation Tax decomposition; ledger only carries `tokens_in/out/reasoning` (`experiment_spec.py:88-90`); `AgenticResult` only has prompt/completion/reasoning (`opencode.py:71-74`). | `experiment_spec.py:41`; design doc §7 `tokens{...answer, explanation}`. |

Note the nuance on `test_executed_success`: it **is** captured in the workflow runner
(`workflow_runner.py:63`, `workflow_runner.py:278`) but is **not** a `LEDGER_FIELDS` entry
(`experiment_spec.py:44-97`), so from the compiler's requires/produces gate it is still "unmeasured" —
a measurement rule that `produces` it must be declared before a control rule may consume it.

---

## 3. The fork / cache mechanism

### 3.1 opencode: `--session <id> --fork`

- `run_opencode_agentic(..., session_id, fork)` `opencode.py:192-193`. When both are set, the CLI
  command gains `--session <id> --fork` (`opencode.py:274-275`). The docstring (`opencode.py:220-223`)
  states the intent: fork the given session so the **shared context prefix is served as provider cache reads**.
- The **new** session's id (the fork is a new session, not the parent) is extracted from the first JSONL
  event carrying `sessionID` via `_extract_session_id` (`opencode.py:309`, `opencode.py:390-405`).
- Cache accounting is parsed from `step_finish` events: `tokens.cache.read` → `cache_read_tokens`,
  `tokens.cache.write` → `cache_write_tokens` (`opencode.py:498-501`). `total_tokens` counts only
  billable tokens (`prompt + completion + reasoning`, `opencode.py:503-505`), while
  `context_tokens = total_tokens + cache_read_tokens` (`opencode.py:506`).
- `cache_hit_rate = cache_read_tokens / (total_tokens + cache_read_tokens)` (`opencode.py:83-89`).

### 3.2 Claude CLI: `--resume <id> --fork-session`

- `run_claude_agentic(..., session_id, fork)` `claude_adapter.py:252-253`. When set, the command gains
  `--resume <id> --fork-session` (`claude_adapter.py:307-308`).
- The forked session id is captured from the `session_id` field of the `stream-json` events as they stream
  (`claude_adapter.py:315-323`, written to `result.session_id` at `claude_adapter.py:344`).
- Usage is translated to opencode's token schema in `adapt_usage` (`claude_adapter.py:49-72`):
  `cache_read_input_tokens` → `cache.read`, `cache_creation_input_tokens` → `cache.write`;
  `reasoning` is folded into `output_tokens` and reported as 0.

### 3.3 The already-built cache-aware fork chaining (workflow layer)

`src/instrument/workflow_runner.py` is the reference implementation of cross-step fork chaining:

- `workflow.params.fork` gates it; `fork=None` falls back to `spec.workflow.params.get("fork", False)`
  (`workflow_runner.py:202`, `workflow_runner.py:262`).
- Each **agent** phase, when the model is unchanged, passes the previous phase's session id with `fork=True`
  (`workflow_runner.py:304-310`), via the two backends' `--session/--fork` and `--resume/--fork-session` flags.
- The **model-unchanged guard** is explicit: `prev_model == model` (`workflow_runner.py:307`). A model switch
  between steps **breaks the cache prefix**, so the fork is skipped and the new phase starts a fresh session —
  no cache reads are reaped from the prior phase (`workflow_runner.py:299-303` comment).
- `prev_session_id` / `prev_model` are updated after each phase from `AgenticResult.session_id`
  (`workflow_runner.py:328-332`).
- The per-phase ledger records `cache_read_tokens`, `cache_write_tokens`, `cache_hit_rate`
  (`workflow_runner.py:325-327`; `PhaseResult` fields `workflow_runner.py:55-57`), plus `session_id`
  (`workflow_runner.py:58`) and `tokens` (`workflow_runner.py:318-323`).

### 3.4 Prior art in the story layer

`src/instrument/story.py:660-711` — the timeout **continuation** path (not cross-session reuse):

- Only for the opencode backend; the Claude CLI path is excluded (`story.py:661-668`).
- On timeout, re-invokes `opencode run --session <primary_session_id> --fork ...` (`story.py:674-689`).
- The fork creates a **new** session; the fork's own id (not the primary's) is billed to avoid
  double-counting (`story.py:704-707`).
- `_read_session_id` reads the `sessionID` from the first JSONL line of the transcript (`story.py:762-771`).

Important distinction: the 5 story **sessions are independent** — `run_story` calls `_run_session` per
session with no fork between them (`story.py:510-536`, `_run_session` `story.py:624-637`). Forking there
is only used for timeout recovery, so the story layer currently **forfeits** cross-session cache reuse that
the workflow runner already exploits. `_sum_billed_tokens_from_jsonl` (`story.py:792-817`) and
`_estimate_session_cost` (`story.py:820-842`, exact-id match against `opencode.db`) are the accounting helpers.

---

## 4. The gap: per-step model selection & preference-aware routing

### 4.1 What exists vs what's missing

| Need | Today | Gap |
|---|---|---|
| **Per-step model selection** (`pin` / `allowed_models` / full pool) | `run_workflow` takes **one** `model` for all phases (`workflow_runner.py:190`, used at `workflow_runner.py:290`). No phase-level model override, no per-step pool. | No per-phase `pin`, `allowed_models`, or pool construct. `Factor.model` is a single level per cell (`experiment_spec.py:121-148`). |
| **A user-preference scoring function over measured signals** | `recommend_route` uses two hardcoded scalars + one margin (`routing.py:25-26`, `routing.py:71`, `routing.py:80`). Efficiency is a fixed `correctness/cost` ratio (`routing.py:58`). | No weighted objective mapping `(correctness, cost, cache_hit_rate, efficiency, quality dims) × user weights → per-step score`. |
| **Live control (route while running)** | Routing is an offline report (build_data / `/api/routing`). Nothing steers an in-flight `run_workflow`. | No `decide(job, state) → {route, ...}` hook at enqueue/lease time. |
| **Cache-aware reuse across model boundaries** | Fork only when `prev_model == model` (`workflow_runner.py:307`). | Per-step routing must know that a model switch **forfeits** the cache prefix and price that into the decision. |
| **Admissible control arms** | `model_cascade` requires `confidence` (`experiment_spec.py:163-165` in the design doc example; `experiment_spec.py:396-402` enforces the gate). | `confidence` is unmeasured (§2.2); the validator refuses any routing control rule that consumes it until instrumented. |

### 4.2 What a per-step routing design must respect

1. **The load-bearing rule** (`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md:35-64`):
   measure before policy. A `routing` control rule whose `requires` include `confidence` or any
   unmeasured signal is refused by `validate_rules` (`experiment_spec.py:367-403`). The preference-scoring
   function may only consume signals already in the ledger or `produces`-declared by a measurement rule.
2. **The model-switch cache cliff** (`workflow_runner.py:299-310`): any per-step routing decision that
   changes the model between adjacent steps silently forfeits the DeepSeek cache-read discount
   (`efficiency.py:44`, ~120× cheaper than input). The scoring function must weight `cache_hit_rate`
   against `correctness`/`cost` per step — a cheaper next-step model may lose more in cache re-send than it
   saves in per-token price.
3. **`Factor.policy` is the first-class arm** (`experiment_spec.py:122`, `experiment_spec.py:124`): routing
   should be a `policy` factor level in the grid, compared against `cheapest` / `premium_static` arms via
   `ComparisonSpec` (`routing_regret`, `experiment_spec.py:206-223`), not a side report.

### 4.3 Concrete instrument-first sequencing

To close the gap without tripping the validator, instrument in this order (mirrors
`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md:287-299`):

1. **`confidence`** — emit per attempt (self-assessed correctness / calibration), so `model_cascade`-style
   routing control rules become admissible.
2. **`answer` / `explanation` token split** and attempt/timestamp fields — the token-split feeds the
   Explanation Tax decomposition that a cost-aware preference scorer wants.
3. **Edge-case coverage** — add branch/mutation coverage to the test-runner/`validate_session` path so a
   routing policy can prefer models whose solutions actually exercise edge cases (a signal that today does
   not exist at all).
4. Then author the per-step router: a `decide(job, state)` control rule + a preference-scoring function over
   the *measured* signal set, with per-phase `pin` / `allowed_models` / pool semantics wired into
   `workflow_runner.py` (extending the `prev_model == model` fork guard at `workflow_runner.py:304-310`).

---

## File:line index

| Concern | Location |
|---|---|
| `recommend_route` signal intake + decision | `src/instrument/routing.py:21-95` |
| `compute_routing` grouping + min_models gate | `src/instrument/routing.py:143-187` |
| `simulate_strategies` (single-model + grit_routed) | `src/instrument/routing.py:98-140` |
| backend dispatch `anthropic/* → claude_cli` | `src/instrument/backends.py:14-36` |
| opencode fork flag + session-id extraction | `src/instrument/opencode.py:274-275`, `opencode.py:390-405` |
| opencode cache token parsing | `src/instrument/opencode.py:498-506` |
| `cache_hit_rate` property | `src/instrument/opencode.py:83-89` |
| claude fork flag + session-id capture | `src/instrument/claude_adapter.py:307-308`, `claude_adapter.py:315-323` |
| claude usage → cache mapping | `src/instrument/claude_adapter.py:49-72` |
| workflow fork chaining + model-unchanged guard | `src/instrument/workflow_runner.py:262`, `workflow_runner.py:299-310`, `workflow_runner.py:328-332` |
| per-phase ledger cache/token fields | `src/instrument/workflow_runner.py:41-87` |
| story timeout continuation fork | `src/instrument/story.py:660-711` |
| `_read_session_id` | `src/instrument/story.py:762-771` |
| pricing (deepseek cache_read vs input) | `src/instrument/efficiency.py:41-85` |
| SolutionMetrics quality dimensions | `src/instrument/solution.py:27-105` |
| requires/produces gate | `src/instrument/experiment_spec.py:367-403`, `LEDGER_FIELDS` `experiment_spec.py:44-97` |
| routing → website data.js | `scripts/build_data.py:31`, `scripts/build_data.py:1112` |
| routing → Control Room API | `admin/server.py:61`, `admin/server.py:860-877` |
| cache economics measurement | `scripts/lab_cache_economics.py:50-57` |
| model slug / labels / known cell models | `scripts/_constants.py:5-17`, `scripts/_constants.py:86-94`; `scripts/supervise.py:295-304` |
| design: measure-before-policy + model_cascade arm | `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md:35-64`, `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md:151-189` |
