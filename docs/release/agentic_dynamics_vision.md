---
status: accepted
---
# Agentic Dynamics — Vision, Positioning, and State (v0.1)

## 1. What this is — and what it is not

**Not a SaaS product.** There is nothing to buy, no tier to sell, no "platform" pitch. The
repo is a measurement instrument, a method, and an open corpus.

**Not abstract theory.** The moment the dynamics become abstract, the message fails. Agentic
Dynamics only matters because the dynamics *are* business outcomes.

**Agentic Dynamics is the empirical study of how AI agents behave under change — measured as
business outcomes.** The instrument perturbs the agent's task/environment, measures how it
recovers, adapts, flails, and compounds cost, and turns those behaviors into numbers a
business can act on.

## 2. The core reframe: the dynamics are the business

Each "dynamic" maps one-to-one onto an operational number:

| Dynamic | Business outcome |
|---|---|
| Basin escape | cost of *change* — how an agent handles churn, requirement drift, spec rot |
| Recovery cost | cost of a *regression* — what an incident costs before it's fixed |
| Snowball (cost compounding) | *maintenance* growth — why the 5th change costs more than the 1st |
| Flail | *wasted spend* — runs that produce reasoning but no deliverable |
| Survival horizon | *runway* — how far a budget lasts before bankruptcy |
| Grit | *reliability under stress* — does it stay correct when the task shifts under it |
| Technical debt (review) | *maintenance liability* — what the agent leaves behind |

This is the whole point: **you cannot buy agent reliability as a fixed price. Cost, correctness,
and debt are functions of how the agent behaves, not a rate card.** We built the instrument that
measures that function.

## 3. The one-sentence thesis (for the front page and the LinkedIn post)

> **AI agents don't have a price — they have dynamics.** Cost, reliability, and debt are
> properties of how the agent behaves under change, and we measured them.

Measured, defensible headlines that back it (all [M]/[C]):
- The same codebase built **100% correct at $0.014/run vs $0.44/run** — a ~30× cost spread with
  equal outcome (process_perturbation resample).
- Recovery from real degradation is **real but expensive** — 100% pass yet **4.6× cost
  compounding** (vs 2.13× clean).
- The "premium" model **fails where the cheap one doesn't** (Claude 60% on `shift_framing` vs
  DeepSeek 100%).
- The instrument **self-heals**: an async worker diagnosed its own corrupted data and re-ran the
  experiments to fix it — the `adapt` loop emerging on its own.

## 4. Where the codebase is

The instrument is built and the load-bearing discipline is enforced by a compiler:

1. **Measurement apparatus** — 10 perturbation operators (3 classes: `specification_corruption`,
   `objective_mutation`, `process_perturbation`), seeded + deterministic, plus 4 signal families
   (correctness, basin escape, efficiency, strategy).
2. **Information-acquisition machine** — `spec → DAG → cells → information → policy → grid →
   campaign`. The `requires`/`produces` gate refuses any policy whose inputs aren't yet measured
   ("measure before policy").
3. **Instrumented ledger** — `confidence`, `perturbation_strength`, `test_executed_success`
   (independent), and the `answer`/`explanation` token split are now *measured*, not absent.
4. **Queue-driven pipeline** — `execute → analyze (AST+SonarQube) → review (DeepSeek flash) →
   regenerate`, now auto-triggered per worktree.
5. **Emergent self-healing** — the 2026-08-15 finding: an async worker diagnosed contamination,
   authored a re-run, and executed it. Captured in `self_recommending_experiment`.
6. **Control Room** — three-stage observability (`execute/analyze/review`) + live workflow phase
   badges.

## 5. Where the website is

8 pages + generated `data.js` (provenance-tagged). **Good:** the front page (hero + diagram) and
the framework-page SVG are worth keeping. **Everything else is out of date or a mess:**

- **Taxonomy** — `manifold`/`semantic` (dead 2-way) on 5–6 pages; must be 3-way.
- **Corpus numbers** — `227`/`249` (stale) on 5–6 pages; now 144 single-task + 156 story.
- **"Explanation Tax"** on 6 pages — the framing we already corrected to *output decomposition*
  (reasoning is the cost, not narration; reasoning is DeepSeek-only).
- **"100% pass rate"** on 5 pages — self-reported; must be split from independent `[tests]`.
- **Missing entirely** (0 pages): `test_executed_success`, `perturbation_strength`, the
  self-healing finding; `confidence` on only 2 pages.
- **Provenance overclaim** (peer-review flag) — "every term measured" while β/EPM are external.

## 6. The rewrite, top-to-bottom

The site must read as "a field and an instrument, expressed as business outcomes" — not a tool
pitch, not an academic abstract.

- **index.html** (keep the diagram) — the thesis up top; the four measured headlines as the body.
- **evidence.html** (full rewrite) — cost spread, recovery cost, premium-failure, verification
  correlation −0.077, `static_site_gen` 0.39, the instrumented fields.
- **methodology.html** (refresh) — 10 operators (3-way), the measured ledger fields, the
  measure-before-policy gate, the queue pipeline.
- **framework.html** (clean up, keep the SVG) — reorganize the "mess of information" around the
  dynamics→business-outcome table; drop the SaaS/playbook framing.
- **story.html** (extend) — the narrative through the remediation + self-healing arc.
- **accelerator.html / databricks.html** — refresh numbers; frame as "operational hypotheses" +
  "related work", not product applications.
- **glossary.html** — drop `manifold`/`semantic`; add `grit`, `perturbation_strength`, `output
  decomposition`, `self-healing`.

Every number provenance-tagged [M]/[C]/[H]/[X]/[P]. Deploy to both projects.
