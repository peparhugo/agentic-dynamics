# Golden-Circle Narrative Design

## 1. Golden-Circle Thesis

**WHY:** We believe success is not value: as AI agents build and operate software at scale, a passing result does not tell us whether the system became more durable, more verified, or merely more expensive to maintain. **HOW:** We turn that invisible gap into information by instrumenting many linked sessions from many measurement angles, analyzing the resulting N x M corpus, and repeating the cycle `instrument -> derive -> write policy -> grid -> campaign`. **WHAT:** That process reveals a field, **AI FinOps Dynamics**, concerned with how cost, verification, maintainability, recovery, routing, and long-horizon value change as agentic work compounds.

The order is deliberate: the site begins with a belief, shows the method that made the gap observable, and only then names the result. The instrument is evidence of the discovery, not the object being sold.

## 2. Page-by-Page Narrative Map

| Page | Golden-circle role | Narrative job | Editorial decision and reason |
|---|---|---|---|
| `index.html` | **WHY -> HOW -> WHAT** | Give the whole discovery in miniature: the unmeasured value gap, the N x M method, and the field that emerged. | Keep the circle explicit on the home page because it is the entry point, but make WHY the center of gravity; corpus statistics are proof, not the opening proposition. |
| `story.html` | **WHY -> HOW -> WHAT** | Tell the chronological discovery: a cost anomaly raised a question, scaling the question required an instrument, and the instrument exposed a broader field. | Reorder the current parts because the page presently reaches WHAT, returns to HOW, and then returns to the author's qualifications; a discovery story should move outward through the circle once. |
| `methodology.html` | **HOW** | Specify how sessions are run, degraded, isolated, traced, evaluated, and reproduced. | Make this the authority for apparatus details so the home and story pages can explain the method without reading like product documentation. |
| `evidence.html` | **WHAT: observed** | Hold the measured, computed, heuristic, and external evidence, with corpus boundaries and provenance intact. | Separate observations from interpretation because the field is credible only if readers can inspect what was measured and what was inferred. |
| `framework.html` | **WHAT: operational** | Show how measured information can become control rules, policy arms, and routing experiments. | Describe routing and decision rules as testable policies where they have not yet been run as arms; this keeps the result scientific rather than promotional. |
| `accelerator.html` | **WHAT: possible applications** | Show what organizations might do with the dynamics once the relevant information exists. | Keep projections and implementation ideas outside the core discovery and retain their modeled or heuristic status; possibility is not measured proof. |
| `databricks.html` | **WHY support / WHAT context** | Place the discovery beside related external work and identify where this corpus adds a different measurement angle. | Use comparison to establish context, not priority or superiority; the narrative is about a need becoming visible, not winning a category claim. |
| `glossary.html` | **Reference across all rings** | Define the vocabulary readers need to move between belief, method, and result. | Keep it outside the linear story so definitions support the circle without interrupting it. |

The intended reading path is `index.html` -> `story.html` -> `methodology.html` -> `evidence.html` -> `framework.html`. The remaining pages are supporting branches: applications, related work, and terminology.

## 3. The N x M Scaling Story

The work began with one bounded question: **how does one model's cost and quality respond when its input is degraded?** A single clean-versus-degraded comparison could answer that question for one task at one moment, but it could not show what happens when agent output becomes the next agent's starting point. Agentic software work is cumulative, so the unit of observation had to expand from a prompt to a session and from a session to a linked story.

That creates the first scaling axis, **N sessions**. Thousands of sessions must be queued, isolated, resumed, and attributed to the correct model, condition, codebase, and point in the story. Each session changes the artifact inherited by the next one, so cost and quality cannot be understood as independent prompt-level snapshots.

The second axis is **M measurement angles**. A passing test is only one view of an outcome. The same sessions must be examined for code quality from different angles, maintainability, cost of maintainability, long-horizon scalability, routing for one-way and two-way doors, verification depth, cache economics, recovery under degraded input, and the cost required to sustain an accepted outcome. No single score can stand in for that set because correctness is not verification and immediate success is not durable value.

The experiment is therefore an **N x M instrumentation problem**: N linked sessions multiplied by M ways of asking whether the resulting work created value. Collection is only half of the scaling problem. Every measurement angle must then be evaluated across models, conditions, tasks, tiers, commits, and positions in the story, which makes analysis itself another N x M problem. Running more sessions without analysis produces volume, not information; adding more metrics without consistent event capture produces incomparable claims.

The answer is an architecture for repeated information acquisition:

1. **Instrument:** capture the events and fields that later rules require, including attempts, timing, tokens, cost, tests, cache behavior, code changes, reviews, and perturbation context.
2. **Derive:** apply measurement rules that turn those events into information such as first-pass quality, verification depth, recovery, maintainability, or cost per accepted outcome.
3. **Write policy:** allow control rules to consume only information the instrument actually produces; an unmeasured input cannot support a defensible policy.
4. **Grid:** run policy choices as experimental arms across controlled factor combinations rather than presenting a preferred rule as a conclusion.
5. **Campaign:** change one variable, repeat the grid, compare the result, and use the remaining uncertainty to choose the next measurement.

This sequence is the bridge from HOW to WHAT. It turns one model-comparison question into a repeatable way to study the dynamics of agentic work. **AI FinOps Dynamics** is the name for the resulting field of inquiry, not the name of a product: it asks how cost, quality, verification, and future maintenance move together, where they separate, and which policies improve value under measured conditions.

## 4. Required Home and Story Changes

### `index.html`

The page should retain its current WHY/HOW/WHAT order, but each section needs to move from “we built a tool” to “we found an unmeasured gap, built the means to observe it, and discovered a field.”

| Location | Current text | Required replacement | Design reason |
|---|---|---|---|
| `<title>` | “AI FinOps Dynamics — Does your AI assistant make your system better, or just bigger?” | **“AI FinOps Dynamics — Success Is Not Value”** | State the central belief before naming any apparatus. |
| Hero kicker | “Why — AI FinOps Dynamics” | **Keep unchanged.** | It already locates the reader at the center of the circle. |
| Hero headline | “Does your AI coding assistant make your system better, or just bigger?” | **“Agentic AI is scaling faster than our ability to measure its value.”** | Move from a tool-level question to the systemic need that initiated the discovery. |
| Hero lead | Current paragraph ending “so we built the measurement.” | **“AI agents can pass their own tests, complete a session cheaply, and still leave behind code that is harder to verify and more expensive to maintain. At scale, cost compounds every session whether the code improves or not. Success is observable; durable value usually is not. That is the gap we set out to measure.”** | End WHY with the research need, not with the thing built to address it. |
| Hero evidence card | “Measured Corpus” beside the WHY | **Keep the card and all values, but relabel it “Evidence behind the discovery” and visually subordinate it to the belief.** | Numbers establish that the belief was investigated; they should not replace the belief. |
| First HOW kicker | “How — the instrument” | **“How — the question scaled”** | Introduce the N x M problem before presenting its solution. |
| First HOW headline | “Multi-session builds under controlled degradation.” | **“One question became an N x M measurement problem.”** | Make the scaling problem the heart of HOW, as required by the discovery arc. |
| First HOW lead | Current benchmark-versus-story paragraph | **“The original question compared one model's cost and quality under degraded input. Answering it properly required N linked sessions, because each output becomes the next session's codebase, and M measurement angles, because passing tests cannot stand in for verification, maintainability, cache economics, routing risk, or long-horizon cost. The corpus is the product of that multiplication, not a larger benchmark.”** | Explain why the apparatus had to exist rather than advertising its features. |
| HOW cards | “Five-session story arc,” “Perturbation conditions,” and “Full quality stack” | **Rename the cards “N — linked sessions,” “Controlled variation,” and “M — measurement angles.”** Preserve the existing session and condition details; expand the third card's prose to name maintainability, cost of maintainability, long-horizon scalability, one-way/two-way-door routing, verification depth, and cache economics. | Make the two scaling axes visible without discarding the concrete experimental design. |
| Second HOW kicker | “How — the pipeline” | **“How — from events to policy”** | Distinguish raw collection from the information and control layers. |
| Second HOW headline | “The measurement pipeline.” | **“Instrument, derive, write policy, grid, campaign.”** | Put the load-bearing architecture in the public narrative verbatim. |
| Pipeline steps | Seven implementation-oriented steps from story config through cost and value | **Replace the top-level sequence with five steps: “Instrument — capture events,” “Derive — turn events into information,” “Write policy — consume measured information,” “Grid — test policy as an arm,” and “Campaign — change one variable and repeat.”** Session traces, static analysis, tests, and reviews remain as examples under Instrument and Derive. | Show how the machine creates knowledge, not merely how jobs move through software. |
| WHAT evidence headline | “Four findings from 1,097 instrumented story sessions.” | **“The unmeasured gap became visible.”** Keep the corpus count in the supporting sentence. | Lead with the discovery while preserving the measured scope. |
| Finding 1 | “Verification is a vendor behavior, not a price point.” | **“Price and verification depth do not move together in this corpus.”** | Keep the finding inside the observed sample rather than universalizing it. |
| Finding 2 | “Cost compounds across the five-session arc.” | **“Later sessions cost more across the five-session arc.”** | Preserve the measured endpoint change while leaving the generalized N² mechanism explicitly modeled. |
| Finding 3 | “Cache behavior is a hidden cost lever, not a capability signal.” | **“Cache behavior separates token volume from session cost.”** | State the measured separation without claiming that cache carries no capability information. |
| Finding 4 | “Degradation leaks — but models recover.” | **“Degradation can leak across sessions, and recovery can be measured.”** | Tie the observation back to the reason linked sessions are necessary. |
| Concept kicker | “What — the concept” | **“What — the durable-value gap”** | Name the discovery before naming the field. |
| Concept headline | “Correctness is not verification.” | **Keep unchanged.** | This is the clearest expression of the observed gap between passing available tests and having enough tests to expose important failures. |
| Final WHAT kicker | “What — this means” | **“What — the field”** | The outside of the circle is the result of the inquiry. |
| Final WHAT headline | “If you can measure it, you can route on it.” | **“A measurement question became AI FinOps Dynamics.”** | Routing is one policy to test, not the total result and not yet a universal conclusion. |
| Final WHAT lead | Current prescriptive routing paragraph | **“The evidence points beyond cost per prompt or success per session. AI FinOps Dynamics studies how agentic cost, verification, maintainability, recovery, and long-horizon value change together, then tests policies against those measurements. Routing is one possible policy arm: its value must be demonstrated in a controlled grid, not assumed from a price sheet.”** | Define the field as an ongoing information-acquisition discipline and keep policy claims falsifiable. |

The metadata descriptions should be rewritten to match the new thesis, but their current corpus numbers must remain exactly as registered below. Calls to action should use research verbs such as “Examine the method,” “Inspect the evidence,” and “Follow the discovery,” avoiding product verbs such as “get,” “buy,” or “adopt.”

### `story.html`

The page should become the canonical discovery narrative and should be reordered once, from WHY through HOW to WHAT. The proposed order is: current lines 51-97; current lines 99-123; current lines 154-191; current lines 125-152; then current lines 194-206. This order keeps the personal trigger, experiment, instrument, and implication while removing the present backward movement through the circle.

| Location | Current text | Required replacement | Design reason |
|---|---|---|---|
| Main headline | “How a $20 API key became an experimental instrument.” | **“A $20 API key exposed a value-measurement gap.”** | Open with the discovery that demanded explanation, not the artifact eventually built. |
| Subtitle | “I wasn't trying to build a research instrument…” | **“I was trying to spend less while I was away. The unexplained difference between cost, output, and durable value turned a personal budget experiment into a measurement question.”** | Preserve the personal origin while making curiosity, rather than invention, the causal force. |
| Part 1 label | “Part 1 · The Discovery” | **“Part 1 · Why — The Anomaly”** | Locate the origin story explicitly at the center of the circle. |
| First Part 1 headline | “The subscription problem.” | **“The cost anomaly.”** | The subscription is context; the unexplained outcome is what starts the inquiry. |
| Second Part 1 headline | “What $12.73 built.” | **“The cost gap demanded an explanation.”** | Avoid framing spend as a product-building boast; make the same facts evidence for the research question. |
| Part 2 label | “Part 2 · The Insight” | **“Part 2 · How — The Question Scaled”** | The first response to the anomaly was experimental design, not a finished framework. |
| Part 2 headline | “So I started researching.” | **“One comparison became an N x M experiment.”** | Put the scaling story at the center of the personal narrative. |
| New subsection after the current perturbation discussion | No current equivalent | **“Scaling the question changed the problem.”** Explain N linked sessions, M measurement angles, and the second N x M burden of analyzing the resulting sessions. | The existing story jumps from perturbation findings to implications; this subsection explains why an architecture was necessary. |
| Current Part 4 label, moved before current Part 3 | “Part 4 · Instrumentation, Not Benchmarks” | **“Part 3 · How — The Instrument”** | Complete the HOW ring before presenting implications. |
| Instrument headline | “What I built is instrumentation.” | **“The question required instrumentation, not another benchmark.”** | Retain the distinction while keeping the instrument subordinate to the question. |
| Instrument body structure | Queue, chained sessions, routing module, operational failures | **Reframe under the five-stage sequence `instrument -> derive -> write policy -> grid -> campaign`; keep queue isolation, resumability, chained sessions, and analysis concurrency as the operational evidence for why scale is hard.** | Connect the personal engineering story to the architecture that turns volume into information. |
| Qualifications headline | “Why I was the person who could build this.” | **“The question crossed four disciplines.”** | Preserve the economics, physics, energy-market, and software-system perspectives while removing founder-pitch language. Career experience can remain as context, not proof of uniqueness. |
| Current Part 3 label, moved after the instrument | “Part 3 · What This Means” | **“Part 4 · What — The Field”** | Name the result only after readers understand the method. |
| Current Part 3 headline | “From ‘DeepSeek is cheaper’ to ‘here are the dynamics.’” | **“The result was not a cheaper-model verdict.”** | Prevent the story from collapsing back into vendor comparison. |
| Part 4 body | Current operational, policy, long-term, business, and energy implications | **Organize these as dimensions of AI FinOps Dynamics: immediate cost, durable verification, maintainability, recovery, one-way/two-way-door routing, and long-horizon economics. Mark measured observations, computed results, heuristic interpretations, and external inputs exactly as they are marked now.** | The field is the outside of the circle; its dimensions are results and open questions, not sales claims. |
| Benchmarks headline | “Why benchmarks failed. Why buzzwords don't help.” | **“The field starts where benchmarks stop.”** | State the boundary positively and avoid claiming that all benchmarks failed. |
| Closing proposition | “This project gives AI FinOps a foundation.” | **“The discovery defines a research program: measure the events, derive the information, test the policy, and repeat.”** | End with an invitation to inquiry rather than ownership of a category. |

## 5. Measurement and Provenance Preservation Register

This refresh changes framing only. Implementation must not hand-edit `firebase/public/data.js`, change a `data-stat` binding, round a generated value differently, move a claim between provenance classes, merge the story and perturbation corpora, or silently “correct” a literal/live conflict. If a measurement is changed later, it must change through the data pipeline, not through this narrative refresh.

### Provenance tags that must not change

| Tag | Existing meaning | Preservation rule |
|---|---|---|
| `[M]` | Measured directly from API/session data or the filesystem: tokens, costs, tests, LOC, cache tokens, exit codes, and duration. | Do not recast a measured observation as a conclusion, and do not remove the tag when prose changes. |
| `[C]` | Computed from measurements: ratios, aggregates, confidence intervals, density, and other derived values. | Keep the underlying operands and computation aligned with `data.js`; do not present `[C]` as directly observed. |
| `[H]` | Heuristic: author-chosen thresholds or classifications such as quality, novelty, escape, correctness estimates, and strategy. | Preserve the uncertainty and do not promote a heuristic to `[M]`. |
| `[X]` | External: provider pricing, energy estimates, projections, or other cited sources. | Preserve the source boundary and citation; do not imply the experiment measured the external quantity. |

There is no `[P]` tag in the current public HTML or JavaScript. The word “policy” in the new narrative describes a control-rule stage and must not introduce a new provenance tag during this prose-only refresh.

### Canonical live values from `data.js`

These values and their existing provenance assignments must remain unchanged:

- `[M]` summary values: **80 worktrees**, **1,097 sessions**, **224 game reports**, **$288.6909 total cost**, **3 architectures**, **7 variants**, and **35 configs**.
- `[C]` summary values: **221 total stories**, **210 unique stories**, **11 reruns**, **1,097 story sessions**, and **$288.6909 story cost**.
- `[C]` cost gap: **23x**, computed as **$1.590337 / $0.068166 = 23.3x**.
- `[C]` overall pass rate: **99.9% (10,726/10,738)**.
- `[M]` test totals: **10,726 passed** and **10,738 run**.
- `[M]` model-family costs: **$6.8678 DeepSeek** and **$135.6352 Claude**.
- `[M]` corpus totals: **0 narrated**, **221 valid reports**, and **221 reports analyzed**.
- Existing displayed rounding must remain where already used: **1,097**, **224**, **$288.69**, **23x**, **$6.87**, **$135.64**, and **99.9%**.

### `index.html` numbers that must not change

- Metadata and corpus scope: **1,097 sessions**, **7 models**, **10,535 tests** in the current OpenGraph description, **221 stories**, **3 codebases**, and **2 tiers**.
- Story design: **five consecutive sessions**, including the numbered **Sessions 1-5** and their existing greenfield, feature, integration, refactor, and cross-cutting labels.
- Finding 1: **41x**, **$0.09**, **$3.75**, approximately **10 tests**, **2.9x**, **$1.59**, **$4.58**, approximately **120 tests**, and the **10x verification gap**.
- Finding 2: **$0.16 -> $0.34**, **18.7K -> 34.9K tokens**, and approximately **2x**.
- Finding 3: approximately **47K tokens per session**, **$0.07**, **$3.75**, **98% cache hit**, **6.3K tokens**, and **three independent knobs**.
- Finding 4: **85%**, **$1.48 per story**, and **88%**.
- Tests per story: **Luna 7, Terra 9, Sol 13, Flash 34, Pro 34, Haiku 117, Sonnet 122**.
- Footer and proof-ledger values: **1,097 story sessions**, **7 models**, **221 stories**, and **$288.69 measured**.
- Release identity: **v0.9** and **August 2026**.

### `story.html` numbers that must not change

- Origin: **2026**, approximately **$700/month**, the **$20 USD** API key, and **under $13 total**.
- Current literal cards and historical statements: **3 models**, **347 instrumented/total sessions**, **$12.73**, **224 game reports**, and **8 models**. These currently coexist with live substitutions and must not be reconciled as part of a prose-only narrative change.
- Current live substitutions: **$6.87 DeepSeek cost**, **$288.69 total research/all-model cost**, **23x measured cost gap**, and **$135.64 Claude cost**.
- Perturbation corpus: **11% Claude flail**, **8% DeepSeek flail**, **14% GPT-5-nano flail**, **227 runs**, and **8.5% Claude narration penalty**.
- Pricing and cache claims: **11.5x**, **$10.00 versus $0.87 per 1M output tokens `[X]`**, **78%**, approximately **35K tokens**, **97-98%**, and approximately **6K tokens**.
- Long-horizon claims: the **N²** term, **4Ms**, **1.8x by 2050**, **2035**, **2%**, and the **three-year** horizon. The N² relationship must remain labeled as modeled wherever it is generalized beyond the measured five-session endpoints.
- Verification examples: **Luna 7 tests for $0.09** and **Sonnet 5 73 tests for $2.32**.
- Instrument operations: the queue was wiped **twice** and analysis concurrency moved from **one to four**.
- Scale statement: **over 2,000 sessions**, comprising **1,097 story-building runs**, **221 cells**, **7 models**, and **911 independent reviews**.
- External energy claims: **700W**, **220% growth**, and **6.7-12% of US generation**; their external-source status must remain explicit.
- Footer values, including their live replacements: **347/1,097 sessions**, **3/7 models**, **71/221 stories**, **$12.54/$288.69 measured**, plus **v0.9** and **August 2026**.

### Site-wide preservation boundary

No numerical or provenance-bearing content is proposed to change in `methodology.html`, `evidence.html`, `framework.html`, `accelerator.html`, `databricks.html`, or `glossary.html`. Their formulas, thresholds, corpus counts, prices, model counts, test counts, projections, citations, chart inputs, calculator defaults, generated tooltips, and `[M]/[C]/[H]/[X]` tags remain byte-for-byte outside the scope of the narrative implementation. In particular, the **227-worktree perturbation corpus** must remain distinct from the **1,097-session, 221-story corpus**; neither may be added to, divided by, or described as the other.
