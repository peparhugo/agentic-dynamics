# Agentic Dynamics: A Measurement Apparatus and Field Program for the Empirical Study of How AI Agents Behave Under Change

**Draft — conference-length preprint (field-defining framing)**

**{Author One}**¹ · **{Author Two}**¹ · **{Author Three}**²

¹{Primary affiliation} &nbsp;·&nbsp; ²{Secondary affiliation}

Correspondence: `{author@example.com}` &nbsp;·&nbsp; Repository: `github.com/peparhugo/agentic-dynamics` (intended slug)

> **Note to authors (remove before submission):** author block is a placeholder. Credit the operator(s) who designed and ran the campaigns and authored the instrument. The model-authored peer reviews in Section 7 are *data*, not authors.

*Abstract.* We introduce **Agentic Dynamics** — the empirical study of how AI agents behave, adapt, interact, recover, and produce outcomes across changing tasks, environments, workflows, and time — and describe an open-source measurement apparatus built to practice it. The apparatus treats an agent as a controllable dynamical object: a bank of ten perturbation operators (four *manifold*, six *semantic*) is applied to coding tasks at controlled strength, and each resulting trajectory is reduced to four measured signal families — correctness, structural divergence from a baseline ("basin escape"), resource consumption (tokens, dollars, joules, cache), and strategy classification. These signals feed an *information-acquisition machine* whose central discipline is encoded in a compiler: a control policy may consume only information that a measurement rule has already produced, so the system refuses to admit a policy whose inputs are unmeasured. We report findings from two corpora — 227 controlled single-task runs across eight models and 34 task families, and 221 five-session multi-turn builds (1,097 sessions) across seven models — spanning twenty lab-book analyses. Headline results include: a *grit matrix* in which a mixture-of-experts model clusters in the high-grit quadrant at ~70× lower cost than a dense SFT model; attractor-basin topologies that are stable under semantic perturbation but collapse under manifold perturbation; a flail signature (overthink / fast-fail / read-without-write) detectable in real time from tool-call sequences; a measured *Snowball Rule* in which per-session cost compounds 2.13× across a build; a verification gap that tracks *vendor*, not *price*; and a routing policy that dominates every single-model strategy by escalating on only three task types. We frame the field's research program, enumerate the still-unmeasured signals (confidence, perturbation strength, verified success, the answer/explanation token split) that the compiler is currently refusing to let any policy consume, and report the peer-review critiques the measured models themselves produced of the apparatus. The instrument, both corpora, the twenty lab books, and the policy layer are released together.

---

## 1. Introduction

The economics of AI agents are being studied backwards. The field's dominant question — *how much does an agent cost?* — is answerable from a rate card and answers almost nothing. The question that matters comes first: *how does an agent behave when the task, environment, or workflow changes underneath it* — and only then, *what does that behavior cost?* Cost is a multiplier on behavior, not a fact about it. A model that is cheap per token but collapses under a changed requirement is not "efficient"; it is expensive in the only sense that matters, which is outcomes-per-dollar under stress.

This paper has two aims. The first is to name and stake out a field: **Agentic Dynamics**, defined as *the empirical study of how AI agents behave, adapt, interact, recover, and produce outcomes across changing tasks, environments, workflows, and time* [P]. The second is to describe a working measurement apparatus for that field — an instrument, two corpora of controlled runs, a set of derived measures, and an architectural discipline — together with the empirical regularities the apparatus has so far produced.

We begin, in Section 2, with a statement of the central methodological problem: that *you cannot write a policy — a rule that routes, escalates, retries, or budgets an agent — before you have measured the signal the policy reads.* A control rule such as "escalate when `confidence < θ`" is literally unwritable until `confidence` exists as a measured quantity. The apparatus makes this a *hard constraint* by encoding it in a compiler (Section 4): a control rule whose `requires` are not produced by the ledger or by a measurement rule is refused at compile time. This converts a methodological preference into an executable research program — the compiler's refusals *are* the list of what to measure next.

Sections 3 and 4 describe the apparatus and the architecture. Section 5 reports the empirical findings, organized by theme across twenty lab-book analyses. Section 6 states the open instrumentation gap. Section 7 reports the peer-review critiques produced by the measured models themselves. Sections 8–11 cover related work, reproducibility, limitations, and the field program.

**The central claim, in one sentence:** *to make policies about agents, we need information about agents; the apparatus is built to acquire that information and to refuse — loudly — any policy that outruns it.*

## 2. Why "measure before policy" is a hard rule

Consider the standard lifecycle of an agent-deployment decision. A team picks a model on price or benchmark reputation. Latency or cost overruns appear. The team adds a retry, or escalates "hard" tasks to a pricier model, on the basis of intuition or a hand-written heuristic. Each such heuristic is a *policy* — a decision rule `decide(job, state) → {route, depth, retry, escalate, budget, deadline}`. And every such policy consumes *signals*: a correctness estimate, a confidence score, a deadline, a budget forecast.

The failure mode is uniform and severe: **the signal the policy reads has never been measured.** "Escalate when confidence is low" presumes a `confidence` quantity exists, is reliable, and varies informatively with outcomes. In practice it is usually a proxy — output length, a self-reported "I'm unsure," a vibe. The policy is then a rule over noise, and its failure is invisible because the signal was never instrumented.

Our response is to make the ordering a property of the *system*, not of the authors' discipline. We define two kinds of rules (Section 4.2): **measurement rules**, which read raw ledger events and *produce* information (`first_pass_rate`, `grit`, `recovery_premium`), and **control rules**, which *consume* information and emit decisions (`escalation_decision`, `admit_or_halt`). A compiler resolves the dependency graph between them and refuses any control rule whose inputs are not produced. The result is that the research agenda — the next thing to measure — is *computed* by the system, not remembered by the researcher. This is the contribution that generalizes beyond our own experiments.

## 3. The measurement apparatus

### 3.1 The experimental unit: cell, grid, campaign

- A **cell** is one controlled trial: a workflow (a single coding task, a five-session build, or a spec-driven agent task), a factor assignment (model, perturbation condition, policy arm, seed), and instrumentation [P].
- A **grid** is the factorial cross-product of the factors — a systematic information-acquisition pass [P].
- A **campaign** is a sequence of grids; between grids, *one* factor is tweaked and the grid re-run [P].

Each cell produces raw events — a session transcript, tool calls, generated code, a git worktree — reduced by measurement rules into information.

### 3.2 Perturbation operators: the experimental lever

Behavior under change is the object of study, so change is the lever. Ten operators act on a coding-task prompt at controlled `strength ∈ [0,1]` [M]:

- **Manifold operators (4)** — `inject_alien_vocab`, `shift_framing`, `reverse_causality`, `force_abandonment` — shift the *linguistic surface* of the task without changing its substance: unfamiliar vocabulary, reframed goals, reversed causal ordering, forced abandonment of a working approach.
- **Semantic operators (6)** — `inject_false_premise`, `invert_constraint`, `insert_contradiction`, `remove_critical_constraint`, `inject_phantom_success`, `inject_competing_goal` — change the *content* of the task: a false premise, an inverted requirement, a contradiction, a removed constraint, a phantom success signal, a competing objective.

The distinction is load-bearing. A manifold perturbation tests whether the agent recognizes *the same problem wearing different words*; a semantic perturbation tests whether it detects that *the problem itself changed*. They expose different failure modes and, as Section 5 shows, separate models in sharply different ways.

Multi-session variants apply the same machinery to **stories** — five-session builds with a git commit between sessions — under four conditions: `clean` (control), `bad_seed` (corrupted starting codebase), `early_degrade` (spec corrupted at session 2, recovery measured across three sessions), and `late_degrade` (corrupted at session 4) [M].

### 3.3 Measured signals: what "behaves well" means

We refuse a single scalar "quality." Four signal families are computed post-hoc by static and test analysis of the produced code [C]:

1. **Correctness** — the generated test suite is executed (pytest / vitest / go test / cargo test / tsc) and constraints met are counted against constraints specified; recorded as a fraction and a `constraints_met/constraints_total` ratio.
2. **Basin escape** — structural divergence of the perturbed solution from the baseline solution, over the code's *architecture* and *structure* (AST-level), **not** text similarity. `escape ∈ [0,1]` is high when the agent left the neighborhood of its unperturbed solution. This is the apparatus's operationalization of *behavioral attraction basins* (see §8): we infer basin topology from output-surface divergence, extending prior work from safety topology to *resilience* topology.
3. **Efficiency** — tokens (in/out/reasoning/cache read/write), dollars (per-model provider pricing), and joules (per-token energy estimates), plus derived ratios (`thinking_ratio`, `output_efficiency`, `solution_density`, `correctness_per_dollar`, `quality_per_joule`).
4. **Strategy classification** — each cell is labeled `CONSERVATIVE` (perturbation handled in-manifold; basin held), `EXPLORATORY` (escaped the attractor and found a novel correct solution), `EFFICIENT`, or `WASTEFUL` (escaped and produced low correctness).

From these we define **grit** as a retention curve over perturbation strength: high correctness *and* low escape — the capacity to stay correct without leaving the basin of the baseline solution, and to recover when pushed, conditioned on verified success [C]. Grit is the quantity a "robust agent" actually has, and the quantity a control policy wants to consume.

Additional cross-cutting measures, described where used in Section 5: a *Think–Do Coupling Index* (cosine similarity between a step's stated reasoning and its subsequent tool call), a reviewer-assigned *architectural fit* score, SonarQube static-quality deltas, LSP diagnostic counts, codebase-entropy deltas, and a cache-economics decomposition.

### 3.4 The corpora

Two corpora, both released:

1. **Single-task corpus.** 227 entries (201 valid, 26 narration-failure), across eight model families and 34 task families spanning Python/Flask, TypeScript/Node, JavaScript frontends, Rust, and Go [M]. Strategy distribution over the valid entries: 141 conservative, 59 exploratory, 3 wasteful, 24 unclassified [M]. Accompanying these are 224+ per-experiment game reports and trajectory summaries.
2. **Story corpus.** 221 five-session builds (1,097 sessions) across seven models, each build spanning greenfield → feature → integration → refactor → cross-cutting sessions, under the four perturbation conditions [M].

**Corpus accounting note.** The counts above are three accounting layers, not three disjoint sets; Table 1 records them side by side so no reader must reconcile them by hand.

**Table 1 — Corpus summary across accounting layers**

| Layer | Unit | Count | Models | Cost scale | Provenance |
|---|---|---|---|---|---|
| Single-task perturbation corpus | runs (entries) | 227 (201 valid + 26 flail) | 8 | $0.006–$2.24 /run | `_results_summary.json` [M] |
| Story corpus | cells → sessions | 221 cells / 1,097 sessions | 7 | $0.159→$0.339 /session (arc) | `stories/*.json` [M] |
| Public data artifact | sessions | 249 | 8 | $64.98 total | `data.js` [M] |

The single-task runs and the story cells are distinct experiment families; the public "249 sessions / $64.98" is the rendered aggregate consumed by the website. The exact reconciliation of 249 to 227 + 221 is a *known provenance drift*, not a contradiction in the underlying measurements: our own soundness audit (Section 7) flagged a one-session discrepancy between `data.js` and static prose, and we surface it here rather than forcing a false sum. A fully normalized corpus ledger (one row per raw attempt) is on the field-program list (Section 11).

## 4. The information-acquisition architecture

### 4.1 The chain

```
instrument (ledger: events, attempts, tokens, timestamps)
   → derive    (measurement rules → information)
   → write policy (control rules consuming that information)
   → grid      (policy as an arm, compared against other arms)
   → campaign  (tweak one variable, repeat)
```

An `ExperimentSpec` — a YAML dataclass — declares a `workflow`, a set of `factors` (where **policy is a first-class factor level** alongside model, condition, and seed), a `design` (factorial), a list of `rules`, metrics, a comparison, a writeup, a stop condition, and an adapt strategy [P].

### 4.2 The load-bearing rule

Each `RuleSpec` declares a `plane` — `measurement` (produces information) or `control` (consumes it) — plus the fields it `requires` and `produces`. The compiler resolves the dependency graph and **refuses a control rule whose `requires` are unmet**:

```
ERROR: policy arm "dynamics" requires [confidence, first_pass, deadline_slack]
       — not produced by the ledger or any rule in this spec. Instrument these first.
```

The worked flagship spec `routing_regret_under_degradation` demonstrates the gate. It declares a `dynamics` control arm (`model_cascade`, escalating on measured confidence) and a `grit` measurement rule. The compiler refuses it *as written*: `model_cascade` requires `confidence`, and `grit` requires `perturbation_strength` and `test_executed_success`, none of which the ledger currently produces. The refusal is the architecture doing its job: it computes the next measurement target.

### 4.3 The compiler: spec → DAG

`compile_spec` turns a spec into a phase DAG — `validate → cells → execute → measure → compare → writeup → adapt` — reusing existing transport rather than building new machinery: `experiment_matrix` generalizes the cell-matrix generator; `experiment_run` is the unchanged enqueue/worker transport; `evaluate_rules` is the lab books driven by `spec.rules`; `compare_arms` generalizes the routing simulator — **arms become data**; `adapt` is the campaign loop (read per-arm regret, tweak one factor, emit the next spec).

Two properties are worth stating. First, *recursion*: `Workflow.kind == "experiment"` makes a campaign an experiment of experiments of cells, and `agent_task` makes the agent itself a measurable workflow — the same interpreter at every level. Second, *the winning arm of a grid is the controller*: there is no separate optimization layer; the campaign loop is sustained acquisition.

## 5. Results

We report the measured regularities across twenty lab-book analyses, grouped by theme. Each is tagged with its evidence class: [M] measured, [C] computed, [H] heuristic, [P] policy/prior.

### 5.1 Cost separates models; correctness mostly does not

**The grit matrix** (lab book 2). Partitioning the correctness–escape plane at the median across 201 valid entries [M]:

| Model | High Grit | Explorative | Consv Fail | Wasteful |
|---|---|---|---|---|
| DeepSeek v4 Pro | **51.4%** | 19.3% | 10.1% | 19.3% |
| GPT-5.6 | 46.7% | 33.3% | 13.3% | 6.7% |
| Claude Fable 5 | 35.9% | 17.9% | 23.1% | 23.1% |
| GPT-5 | 9.1% | 36.4% | 18.2% | 36.4% |
| GPT-5-nano | 0.0% | 0.0% | 16.7% | **83.3%** |

The data is bimodal (most entries sit at perfect correctness or zero escape), and the decisive split is *perturbation class*: **manifold perturbations produced zero high-grit entries** (16/16 explorative or wasteful), while semantic perturbations produced 80 high-grit entries [M]. Linguistic-surface shifts are the harder test.

**The correctness premium** (lab books 1 and 3). Across 15 overlapping task types, the dense SFT model (Claude) leads the mixture-of-experts model (DeepSeek) on exactly **3 of 15** tasks — all perturbation tasks (`invert_constraint`, `data_table`, `inject_alien_vocab`) — while DeepSeek leads on 7 and they tie on 5 [M]. Aggregates:

| Metric | DeepSeek v4 Pro | Claude Fable 5 |
|---|---|---|
| Avg cost/session | $0.015 | $1.08 (73×) |
| Avg correctness | 91% | 86% |
| Cost per correct point | $0.016 | $1.27 |

Claude's ~$47.54 of measured spend is 57% output tokens and 43% cache — a *pricing tax*, not a capability purchase [M]. By perturbation class, DeepSeek dominates semantic tasks (94% vs 85%); Claude's sole advantage is manifold tasks (87% vs 77%) [M]. The premium buys correctness on a narrow set of stress tests, not general coding.

### 5.2 Attractor-basin topology

**Basin volumes** (lab book 7). Inferring basin type from output-surface divergence, with `basin_volume = (1 − escape) × correctness / recovery_multiplier` [C]:

| Model | Class | Basin Type | Escape | Correctness | Volume |
|---|---|---|---|---|---|
| DeepSeek v4 Pro | semantic | wide-shallow | 0.18 | 94% | 0.691 |
| DeepSeek v4 Pro | manifold | **unstable** | 0.76 | 77% | 0.168 |
| Claude Fable 5 | semantic | wide-shallow | 0.21 | 88% | 0.530 |
| Claude Fable 5 | manifold | wide-moderate | 0.62 | 87% | 0.246 |
| GPT-5-nano | semantic | unstable | 0.45 | 70% | 0.234 |
| GPT-5.6 | semantic | wide-shallow | 0.16 | 94% | **1.193** |

The architecture signatures are consistent: the GRPO/MoE model shows a *wide, shallow* basin (efficient exploration, cheap recovery) under semantic load but *collapses* under manifold load; the SFT/dense model holds a shallow basin under semantic load but pays a higher recovery multiplier; small provider-family models are simply unstable.

**Cross-class drift** (lab book 12). Re-implementing the analysis as graph traversals in a Neo4j store reproduces the JSON results and exposes *cross-class basin drift* — the gap between a model's semantic and manifold basin volumes. DeepSeek shows the largest drift (0.691 → 0.168, a 0.523 volume delta, "severe"); Claude is moderate (0.530 → 0.246); nano collapses (0.234 → 0.091) [C]. The graph-native form also maps strategy archetypes to basin types: conservative runs cluster in wide-shallow basins, exploratory in wide-moderate, wasteful in unstable/collapsed [C]. This is a validation of the basin construct from an independent representation.

### 5.3 Flail, tool archetypes, and think–do coupling

**Flail signature** (lab book 4). "Narration failure" — a session that produced reasoning text but no code — is our operational definition of *flail*. Of 26 flail sessions: 14 produced >500 reasoning characters but zero code files (overthink); 19 never wrote a file; 18 took <5 steps (fast-fail) [M]. Flail rates are model-dependent (DeepSeek 8.4%, Claude 11.4%, GPT-5.6 6%, GPT-5-nano ~14%, GPT-5.5 50%) [M]. The practical consequence: a read-only loop, or "long reasoning then no write," is observable *during* a session — a real-time flail signal a control rule could consume (once instrumented).

**Tool archetypes** (lab book 5). Models divide into three archetypes by tool usage [M]: *write-dominant* (DeepSeek 59.9% write, Claude 62.1% write — Claude *never reads files*, relying on training distribution instead), *bash-dominant* (GPT-5-mini 46.2% bash, GPT-5.6 39% bash, via `apply_patch`), and *read-heavy* (GPT-5-nano, 9.9% read, 0% write). Write-dominant models produce 2.3× more lines per session (670 vs 291) at comparable correctness, though with slightly lower static-quality scores. Tool choice is an *architectural fingerprint*: confident generation vs conservative modification vs uncertain exploration.

**Think–Do Coupling** (lab book, script-only). The Think–Do Coupling Index (TDCI) measures, per step, the cosine similarity between the model's stated reasoning and its subsequent tool call; high coupling means the model *narrates what it actually does*, low coupling means narration and action are disconnected [C]. This directly targets the "narration tax" hypothesis: a model that thinks at length but whose thinking does not predict its actions is burning tokens on disconnected prose.

### 5.4 The Snowball Rule and multi-session dynamics

**Cost compounding** (lab book 15). Across 1,097 story sessions in 221 builds, per-session cost is not flat [M]:

| Session | Task | Avg cost | Avg tokens | Avg tests |
|---|---|---|---|---|
| 1 | greenfield | $0.159 | 18.7K | 4.4 |
| 2 | feature | $0.210 | 23.5K | 8.4 |
| 3 | integration | $0.319 | 29.4K | 10.6 |
| 4 | refactor | $0.290 | 30.0K | 10.9 |
| 5 | cross-cutting | $0.339 | 34.9K | 14.8 |

**Snowball factor: 2.13×.** The marginal cost of a change is a function of everything committed before it; a model that prices session 5 like session 1 under-budgets maintenance by ~2×. Cost is a *state of the codebase the agent maintains*, not a per-task constant.

**Condition effects** (lab book 16). Perturbing the seed or the session-1 spec degrades outcomes modestly and monotonically [M]: `clean` 91% success, `bad_seed` 88%, `early_degrade` 85%, with cascade rates 0% / 2% / 4%. The degraded spec *does* leak, but ~85% of cells still recover to passing — degradation raises cost and cascades slightly, but does not dominate the outcome.

**Review-agent findings** (lab book 14). A Flash reviewer scoring architectural fit finds comparable quality across conditions (medians 0.69–0.75), and finds **no cascade**: all 8 `early_degrade` cells maintained 100% test pass from session 1 to session 5 [M]. The agent's default failure modes are condition-independent — infrastructure coupling (18/26 cells), missing type hints (15/26), bare except blocks (12/26), unbounded state (10/26) — they are *the agent's signature*, not degradation artifacts.

### 5.5 Verification economics

**Verification tracks vendor, not price** (lab book 18). Across 221 cells and 7 models [M]:

| Model | Cost/story | Tests/story | Frontier |
|---|---|---|---|
| DeepSeek v4 Flash | $0.068 | 33.5 | ✓ |
| DeepSeek v4 Pro | $0.138 | 34.4 | ✓ |
| GPT-5.6 Luna | $0.091 | 7.3 | |
| GPT-5.6 Terra | $1.021 | 8.8 | |
| Claude Haiku 4.5 | $1.590 | 117.4 | ✓ |
| GPT-5.6 Sol | $3.749 | 12.9 | |
| Claude Sonnet 5 | $4.583 | 122.1 | ✓ |

OpenAI spans a 41× price range with tests flat at 7–13; Claude spans 2.9× with tests flat at ~120. **You do not buy more tests by paying for a pricier sibling; you buy them by switching vendors.**

**Does verification pay?** (lab book 19). Correlation of tests-per-story with reviewer-flagged "worse" commits: **r = −0.226** — more tests predict *slightly* fewer bad commits, but weakly [C]. Verification is weakly protective and does not substitute for architecture quality; tests and reviewer-judged quality are largely independent signals.

### 5.6 Cache and cleanliness are independent cost axes

**Cache economics** (lab book 17). Cache hit rate, context volume, and cost are three independent knobs [M]: Flash (cheapest) hits 96% cache but carries 7.0M context tokens/cell; Luna (also cheap) hits 98% with 1.3M; Claude models read heavily from cache (read/write 32–37) with mid hit rates. Token volume, cache policy, and cost combine in any configuration — a model can be cheap *or* cache-trusting *or* token-hungry independently. The practical lever (already wired into the workflow runner) is session forking: for DeepSeek, cache reads are priced ~120× cheaper than fresh input ($0.0036/K vs $0.435/K), so a routing policy must price a model switch against the lost cache prefix [P][M].

**Quality frontier** (lab book 20). Cleanliness is decoupled from cost [M]: the cheapest model (Flash) has the *most* LSP errors (13.5) and the *lowest* code-quality score (0.035); the cheapest-but-one (Luna) has the cleanest LSP (5.1); Claude Haiku ($1.59) has the best code-quality score (0.167). Paying more buys neither fewer diagnostics nor higher cleanliness.

**Sonar quality** (lab book, script-only). Across SonarQube-analyzed cells, thinking ratio is tested against static quality (bugs, smells, cognitive complexity, duplication) to ask whether *more reasoning correlates with better code* — a measured form of the "does thinking help" question, and whether perturbation degrades maintainability as a *delta* against baseline [C].

### 5.7 Routing and survival: the policy end-state

**Routing** (lab book 6). Simulating three strategies over 17 overlapping task types [C]:

| Strategy | Cost/session | Correctness |
|---|---|---|
| Claude-only | $1.08 | 88% |
| DeepSeek-only | $0.016 | 92% |
| **Grit-routed** | $0.12 | **95%** |

DeepSeek-only already beats Claude-only on *both* axes — the premium model never wins as a default. The grit-routed policy (DeepSeek by default; escalate to Claude only on task types where the escalation model leads by >16pp) reaches the highest correctness at 9× lower cost than Claude-only, and escalates on only **3 of 17 task types** (`data_table`, `inject_alien_vocab`, `invert_constraint`) — all perturbation tasks [M]. The "use the premium model for mission-critical work" heuristic reduces to a narrow, measurable decision table.

**Survival horizons** (lab book 8). Modeling sessions-to-bankruptcy under budget and perturbation rate [C]:

| Scenario | DeepSeek | Claude | GPT-5 | GPT-5-nano |
|---|---|---|---|---|
| Moderate (20%), $10K | 633,771 | 9,154 | 55,590 | ∞ |
| Adversarial (80%), $1K | 56,134 | 670 | 7,707 | 120,531 |

The `∞` for nano is an artifact of its $0.006/session cost — it has 70% correctness and a high flail rate. Survival *without* correctness is cost minimization, not outcome maximization; the metric must be paired. DeepSeek achieves the best balance: order-of-magnitude survival advantages at 92% correctness [C].

### 5.8 Meta-analysis: the model analyzing itself

**opencode meta-analysis** (lab book 13). Closing the loop, the same instrument is used to have a cheap model (DeepSeek v4-flash) analyze the corpus — session deep-dives, pairwise baseline-vs-perturbed comparisons, model profiles, strategy forensics, perturbation-class comparison, cost-anomaly detection, cross-model comparison, and lab-book synthesis [P]. The analysis itself is a measured, cost-tracked cell (~$0.003/session, ~$0.03 for eight analyses against a ~$65 experiment budget), making meta-analysis essentially free relative to the primary corpus and, recursively, itself an object of study. Three earlier embedding-based labs (`reasoning_divergence`, `semantic_clusters`, `cross_model_reasoning`) were superseded by a semantic-validation module and are deprecated.

## 6. The open instrumentation gap

The architecture's end-state is a grid whose arms are policies, compared by regret. Two control rules are currently **gated**, and their gating is the honest summary of the field's frontier:

- **`grit`** requires `perturbation_strength` and `test_executed_success` — the strength axis and a verified-success flag — neither yet written to the ledger. (`test_executed_success` has a designated source-of-truth runner, but it is not yet a ledger field the rule can consume.)
- **`model_cascade` / `dynamics`** requires `confidence` — a per-attempt confidence signal — which is unmeasured.
- The `answer`/`explanation` token split, which would unlock a measured **Explanation Tax** decomposition (the cost of reasoning text that does not become code), is also not yet instrumented.

These are not missing features; they are the *next information the machine should acquire*. The compiler, by refusing the rules that consume them, converts "we don't know this yet" into a precise, executable to-do list. That is the point of the architecture: **the refusal is the research program.**

## 7. Community critique: the measured models review the apparatus

As a meta-experiment in the same spirit as Section 5.8, the measured models were asked to audit the apparatus and its public presentation. Two findings warrant reporting [H]:

- A **soundness audit** (Claude, third pass) confirmed the instrument, pricing, operator taxonomy, and test suite as mutually consistent, and caught a provenance bug the authors had missed: a website page claimed "every term was measured empirically" while the same page listed β and EPM as externally calibrated — a one-line false claim contradicting the apparatus's own provenance discipline. It was fixed.
- A **UX/UI review** (GPT-5.6) found the site "visually credible but not ready for public launch," flagging a dollar-sign duplication in a live KPI and a calculator index bug — interface defects that made the *instrument appear* unreliable even where the *data* were sound.

We report these not as endorsements but as data points about the models: a critique that catches a self-contradiction in provenance is exactly the kind of measured, cost-tracked analysis the apparatus is designed to run on itself.

## 8. Related work

The apparatus sits at the intersection of four lines.

**Behavioral attraction basins.** Prior work formalizes the continuous topology of failure regions in language models under alignment deviation [X: Munshi et al., arXiv:2602.22291]. We extend the construct from *safety* topology (alignment deviation) to *resilience* topology — escape × correctness × recovery cost — and operationalize "basin escape" as structural AST divergence rather than text similarity (§3.3). Our basin claims are behavioral, not latent; we do not assert anything about representation-space geometry.

**Agentic-code eval harnesses.** We inherit test-driven correctness from code-generation benchmarks, but depart in the signal that matters most to us: we measure *divergence from a baseline under perturbation*, not a single pass/fail on a fixed task. The perturbed-baseline contrast is the apparatus's core scientific instrument.

**Agent economics / FinOps.** Work on inference-cost accounting supplies the pricing model; we extend it with the constraint that a cost signal is admissible to a policy only once measured, and with the observation (§5.4) that per-session cost is a function of accumulated state, not a constant.

**Self-analysis.** The meta-analysis loop (§5.8) and the peer-review critique (§7) place this work in the growing line of models-as-analysts, with the distinguishing commitment that the analysis is itself a measured, costed, reproducibility-pinned cell.

## 9. Reproducibility and provenance

Every run pins `git_sha`, `pricing_version`, `dataset_hash`, `seed`, `provider_model_version`, and `instrument_version`; a manifest generator verifies them. Public claims carry provenance tags — [M] measured, [C] computed, [H] heuristic, [X] external, [P] policy/prior — and a data-integrity test guards measured values against drift. The instrument, both corpora, the twenty lab books, and the policy layer are released together under one build.

## 10. Limitations

1. **Narrow task distribution.** Coding tasks in five language families dominate; the canonical definition's "behave, adapt, interact, recover" is only partially exercised. Broad swarm behavior and organizational outcomes are *not* measured and are explicitly out of scope [P].
2. **Behavioral, not latent, basins.** Basin topology is inferred from output-surface divergence; it is descriptive, not mechanistic.
3. **Small manifold sample.** Sixteen manifold entries ground the "zero high-grit under manifold" result; it is suggestive, not conclusive.
4. **Flail-rate noise.** Point estimates vary across partitions (e.g., DeepSeek 2.5% vs 8.4%) depending on how the corpus is split; the qualitative ordering is stable, the numbers are not.
5. **Unmeasured signals.** `confidence`, `perturbation_strength`, `test_executed_success`, and the `answer`/`explanation` split remain open; any policy consuming them is refused by the compiler until instrumented.
6. **Single-vendor cache economics.** The 120× cache-read lever is measured for DeepSeek pricing; cross-provider cache semantics differ and are not yet normalized.
7. **Single-reviewer quality judgments.** Review and audit findings come from single models; inter-reviewer reliability is not assessed.

## 11. The field program

If the apparatus is doing its job, the next experiments are already computed by the compiler's refusals, in order:

1. **Instrument** `confidence` (for the `model_cascade`/`dynamics` arms), `perturbation_strength` + `test_executed_success` (for `grit`), and the `answer`/`explanation` token split (for the Explanation Tax).
2. **Author the gated arms** and run `routing_regret_under_degradation` end-to-end; the validator admits the `dynamics` arm only once its inputs exist.
3. **Widen the task distribution** beyond coding, and **broaden the interaction surface** beyond single- and five-session builds toward the "interact" and "coordinate" terms of the canonical definition.
4. **Close the campaign loop** — `adapt` as coordinate descent, one factor per grid — so that sustained acquisition, not ad-hoc investigation, drives the field forward.

The load-bearing rule remains the field's thesis: *to make policies about agents, we need information about agents.* The apparatus exists to keep acquiring that information — and to keep telling us, in compiler errors, exactly what is missing.

## 12. Conclusion

We have named a field — Agentic Dynamics — and described a working apparatus for practicing it: a perturbation-and-measurement instrument that treats agent behavior as a controllable dynamical object, and an architecture that makes information acquisition the primary product and refuses any policy that outruns it. The measured regularities are preliminary but consistent: cost and escape separate models where correctness does not; manifold perturbation is the hard test; flail is detectable from tool-call sequences; cost compounds with accumulated state; verification tracks vendor, not price; and a narrowly-escalating routing policy dominates every single model. The open instrumentation gap is not a limitation to be papered over — it is the machine's next measurement target, already written into its own compiler as a refusal. To make policies, we need information; the system is built to keep telling us exactly what information is missing.

---

## References

*[X] Munshi, V., et al. "Manifold of Failure: Behavioral Attraction Basins in Language Models." arXiv:2602.22291, 2026.* (cited in the repository; we extend safety-topology to resilience-topology.)

*[X] Chen, M., et al. "Evaluating Large Language Models Trained on Code." arXiv:2107.03374, 2021.* (test-driven correctness convention inherited by the evaluator.)

*[X] Jimenez, C. E., et al. "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?" ICLR 2024.* (agentic-code evaluation lineage.)

*[X] Wei, J., et al. "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models." NeurIPS 2022.* (reasoning-token accounting and the narration/action distinction.)

*[X] Anthropic. "The Anthropic Economic Index." 2025.* (agent-economics cost-accounting lineage.)

*[P] Repository policy, provenance tags, and the Agentic Dynamics field definition — see the project's canonical identity document and `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`.*

---

## Appendix A. Figures and tables plan

The inline tables above are final; the figures below are *planned* — they exist as data (in `_results_summary.json`, `lab_*.json`, and the story corpus) but have not yet been rendered. Each entry lists the figure, its caption, and the exact data source and target rendering.

### A.1 Tables (final, numbered)

| # | Title | Location | Source |
|---|---|---|---|
| T1 | Corpus summary across accounting layers | §3.4 | `_results_summary.json`, `stories/*.json`, `data.js` |
| T2 | Grit-matrix quadrant distribution by model | §5.1 | `lab_grit_matrix.json` |
| T3 | Correctness-premium aggregates (DeepSeek vs Claude) | §5.1 | `lab_claude_audit.json`, `lab_correctness_premium.json` |
| T4 | Basin volumes by model × perturbation class | §5.2 | `lab_basin_topology.json` |
| T5 | Snowball arc (session → cost/tokens/tests) | §5.4 | `lab_story_arc.json` |
| T6 | Condition effects (success / cascade / cost) | §5.4 | `lab_condition_effects.json` |
| T7 | Verification frontier (cost vs tests) | §5.5 | `lab_verification_frontier.json` |
| T8 | Cache-economics decomposition | §5.6 | `lab_cache_economics.json` |
| T9 | Quality frontier (cost vs cleanliness) | §5.6 | `lab_quality_frontier.json` |
| T10 | Routing strategy comparison | §5.7 | `lab_task_routing.json` |
| T11 | Survival horizons by budget/perturbation | §5.7 | `lab_survival_horizon.json` |

### A.2 Figures (to render)

| # | Figure | Caption | Data source → rendering |
|---|---|---|---|
| F1 | Architecture diagram | The information-acquisition chain `instrument → derive → write policy → grid → campaign`, with the requires/produces gate marked at the control-rule boundary. | `code_reviews/2026-08-14_..._design.md` §1, §6 → diagram (Mermaid/draw.io) |
| F2 | Perturbation taxonomy | The ten operators grouped into manifold (4) vs semantic (6), with the two failure modes they target (surface-shift vs content-shift). | `src/instrument/perturb.py` operator registry → simple 2-column schematic |
| F3 | Grit matrix (bubble) | Bubble chart: X = escape, Y = correctness, bubble radius = cost, color = model, split by perturbation class. | `lab_grit_matrix.json` → Chart.js (already deployed on the evidence page) |
| F4 | Basin topology schematic | The wide-shallow vs unstable vs collapsed basin shapes per model × class, annotated with volume values. | `lab_basin_topology.json` → schematic |
| F5 | Snowball curve | Mean session cost and tokens vs session index (1–5), with the 2.13× factor marked. | `lab_story_arc.json` → line/bar chart |
| F6 | Verification Pareto frontier | Cost/story vs tests/story per model, Pareto-frontier models highlighted. | `lab_verification_frontier.json` → scatter + frontier |
| F7 | Routing decision map | Per-task model recommendation (DeepSeek default vs the 3 escalation task types), with the escalation threshold (>16pp correctness gap). | `lab_task_routing.json` → decision table / flow |

### A.3 Rendering pipeline

Figures F3, F5, F6, F7 correspond to charts the project already renders on its public evidence site via `scripts/build_data.py` → `firebase/public/data.js`; the remaining figures (F1, F2, F4) are hand-authored schematics. All figure data traces to the same provenance-tagged [M]/[C] sources as the tables, so a reviewer can regenerate any figure from `_results_summary.json` and the named `lab_*.json` artifacts.
