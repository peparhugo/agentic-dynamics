# GPT-5.6 UX/UI Review — AI FinOps Framework Website

**Reviewer:** GPT-5.6 (via opencode session `ses_0186fb0daffeStOqRHZxlUQhL2`)  
**Date:** August 9, 2026  
**Scope:** All 8 HTML pages, `base.css`, `app.js`, `data.js`  
**Verdict:** The experiment has a compelling story. The site is not currently credible enough to publish as research or mature enough to sell as an enterprise accelerator. It conflates three things: a model-cost experiment, a speculative cost framework, and an undefined enterprise product. The measured experiment is the strongest asset; the other two repeatedly overstate what that experiment proves.

---

## STOP-SHIP ISSUES

These must be fixed before public launch.

### 1. No canonical corpus — every page has different numbers

| Page | Sessions | Experiments | Reports | Total Cost |
|------|----------|-------------|---------|-------------|
| `index.html:51` | "248 Experiments" | — | "203 game reports" | — |
| `index.html:63` | — | — | "203 reports" | "$59.45" (hero stats) |
| `index.html:136` | "248 experiment sessions" | — | "224 game reports" | "$64.98" (footer) |
| `evidence.html:68-73` | "251 worktrees" | "227 runs" | "203 analyzed" | — |
| `evidence.html:145` | "248 sessions + 21 TS" | — | "224 reports" | — |
| `data.js:11-18` | "249" | — | "224" | "$64.98" |

**A reader cannot tell what the sample actually is.** Pick one canonical corpus and propagate it everywhere via `data.js`. Every page that hardcodes numbers should use `data-stat` attributes instead.

### 2. `app.js` loads in `<head>` but accesses `document.body` immediately — broken

`app.js:6-20` runs an IIFE on load that calls `document.body.appendChild(toggle)`. But `app.js` is loaded in `<head>` (e.g., `index.html:43-44`), before `<body>` exists. This throws an exception, preventing the theme toggle AND the data-stat injection from working. Move `<script src="app.js"></script>` to just before `</body>` on every page.

### 3. Evidence page contradicts its own live tables

- Narration table shows Claude at 11% and nano at 14%, but the adjacent prose says 44% and 100% (`evidence.html:112-122` vs `data.js:49,89,329`).
- Cost table shows Claude at $47.54, but the insight copy says $42.52 (`evidence.html:134-145` vs `data.js:302-339`).
- When `build_data.py` regenerates `data.js`, the tables update but surrounding prose does not. Either regenerate prose from data or remove hardcoded numbers from prose entirely.

### 4. Provenance is promised then erased

- Homepage says numbers are "not estimates" (`index.html:54`).
- Methodology acknowledges heuristic `[H]` and external `[X]` sources (`methodology.html:55,82-87`).
- `data.js:31,487-489` shows generated pass rates are `[H]`, overall pass rate is `90.3% [H]`, test totals are `0/0`.
- Evidence nonetheless calls 93.2% a measured pytest/jest result (`evidence.html:144,231`).
- Model-card code strips the `[H]` provenance marker before displaying "Correctness" (`evidence.html:632-654`).

**Fix:** Every number displayed publicly must carry its provenance tag. If it's `[H]`, say it's heuristic. If it's `[M]`, show the measurement. The credibility of the entire project depends on not erasing provenance.

### 5. Core terminology has incompatible definitions

| Term | Contradiction |
|------|---------------|
| **Grit** | Presented as a positive quality (lower escape = better) on homepage (`index.html:84-85`) and evidence (`evidence.html:87-104`), but model cards equate it with a failure rate where higher is worse (`evidence.html:633-654`). |
| **Explanation Tax** | Defined as explanatory-to-code tokens at 3% vs 50% (`framework.html:93`), as narration failure elsewhere (`evidence.html:110-122`), and as thinking ratio in model cards where Claude becomes 0% (`evidence.html:652`, `data.js:317`). |
| **WOC** | Higher is healthy in framework and glossary (`framework.html:96`, `glossary.html:58-59`), but lower is healthy in Accelerator (`accelerator.html:340-362,415-423`). How can a reader act on a metric whose direction flips? |
| **First-pass** | Formula is `1/(1+r)`. With `r=11.5%`, actual first-pass success is 88.5%, not the 90% displayed everywhere (`framework.html:96`, `accelerator.html:211,372`). |

### 6. Accelerator projections fail basic arithmetic

- Augmented scenario: 50 engineers × 20 sessions/day × 20 days × $0.016/session = **~$320/month**, not the claimed $640 (`accelerator.html:273-274`). The Claude comparison at $1.08/session gives ~$21,600/month — this part checks out.
- Autonomous formula: 5000 jobs/day × 30 days × $0.016 × (1 + 0.115 × 28.3) = **~$7,147/month**, not the claimed $3,360 (`accelerator.html:285-287`).
- Even if the math is correct with unshown parameters, publish the actual formula with every term so readers can verify.
- The capacity table uses 11.5% retry rate but produces results matching ~21.4% (`accelerator.html:374-384`).

### 7. "Same output" claim is unsupported

The homepage states both models produce "~11,000 tokens per session of generated output — same computational effort" (`index.html:93`). But the same page's table shows:
- DeepSeek: 691 LOC/session
- Claude: 412 LOC/session  
- GPT-5.6: 367 LOC/session

Similar token counts ≠ same output. LOC differ by 40-47%. Correctness differs. File counts differ. Either qualify heavily or remove this framing.

### 8. Central constraint claim conflicts with aggregate evidence

AST results show average constraint scores of 3.2/7 and 2.3/6. The next section claims both models "implemented every constraint" (`evidence.html:166,174-185`). A score of 3.2/7 is not "every constraint."

### 9. "Persistent memory" story contradicts the Snowball Rule

- Homepage/Accelerator promise every session becomes cheaper through retained context (`index.html:76-86`, `accelerator.html:177,203,543`).
- Framework says every generated line makes future sessions quadratically more expensive (`framework.html:94`).
- These may describe different mechanisms (organizational memory vs. codebase growth), but the site never reconciles them. This is a one-way-door credibility issue.

### 10. Databricks framing is borrowed authority, not evidence

- "Efficiency Frontier" and "Grit" are defined differently, then the page declares them "the same concept" (`databricks.html:49-53`). They are not the same. Efficiency Frontier is price at given intelligence level. Grit is resilience under degraded input.
- The page claims to map "every claim" to measurements but omits major Databricks topics: harness flexibility, AI Gateway details, internal tooling.
- "What Databricks misses entirely" (`databricks.html:133-159`) overreaches — several of the "missed" items are outside the scope of their blog post.
- This page should be positioned as supporting analysis, not the homepage's primary validation hook.

### 11. Model profile cards render blank

`data.js:693-700` uses snake_case fields (`avg_correctness`, `avg_escape_score`), but the renderer in `evidence.html:618-668` expects camelCase (`avgCorrectness`, `avgEscapeScore`). The entire "Model Cards" section on both evidence.html and framework.html renders only its heading. This is one of the most important sections for readers evaluating model choices — it must work.

### 12. Navigation is disorienting

- Nav labels `/` as "Framework" even though `framework.html` is the actual rules page.
- The "Apply" page is called "Deploy" in its `<title>`, "Apply" in the nav, and "Accelerator" in its H1. Three names for one destination.
- Only `framework.html` visibly marks an active nav state (`style="color:var(--ac)"`). No other page does.
- No breadcrumbs, no "you are here" indicator.

---

## PAGE-BY-PAGE ANALYSIS

### `index.html` — Homepage

**3-second comprehension: FAIL.** "The AI FinOps Framework" — what does it do? Who is it for? What changes for me? None of this is answerable in 3 seconds.

**Problem:** Seven things compete in the hero: Databricks validation, 69× cost gap, a comparison table, four stat cards, a Rome-to-Naples origin story, and three CTAs. Pick one. Make it land. Then layer.

**Sequence issues:**
- Proof (69×, Databricks) appears before the problem. Readers need to feel the pain before they trust the solution.
- "How the framework works" section mixes pain and solution in the same cards.
- "Same output" section repeats the hero's cost comparison instead of advancing the story.

**Scrolling hook problem:** The hero gives away every claim. Everything below is restatement. There is no "wait, there's more" — every section after the hero is redundant for anyone who read the hero.

**CTA overload:** Three equal hero CTAs, another pair below, then another choice architecture near the bottom. There is no primary journey. Most visitors will choose nothing.

**Malformed footer:** `index.html:134-140` has empty separators and missing link destinations.

### `framework.html` — The 10 Rules

**3-second comprehension: PARTIAL FAIL.** No page-level H1. No concise definition of what the framework is. Opens directly into dense rules with unexplained symbols (β, v, ε, C₀).

**Sequence issues:**
- Rules precede definitions. C₀, β, v, EPM are introduced without any glossary or grounding.
- The call-center analogy interrupts between levers and the cost model.
- Calculator is below the chart, but chart copy says "Use calculator above."
- The practical decision framework (two-way/one-way doors) is the strongest action-oriented section but arrives after heaviest math.
- Blank model-card section kills momentum entirely.

**CTA problem:** No clear ending. The page trails off after the provider playbook with a malformed footer.

### `evidence.html` — The Data

**3-second comprehension: FAIL.** Opens with a dense census of worktrees, sessions, architectures, and provenance codes. The useful TL;DR summary is collapsed in a `<details>` element.

**Sequence issues:**
- Begins with the most abstract construct (Grit) instead of the most intuitive (cost vs. output).
- Limitations and scope appear 258 lines in, after most confident conclusions.
- DeepSeek/Claude manifold-semantic table appears twice with nearly identical conclusions.
- 69× claim is repeated through almost every section — it becomes wallpaper.

**Typography problem:** Evidence tables are rendered at 0.65-0.78rem — punishingly small for data that is supposed to build trust.

**Dead end:** Final model-profile section is blank. No next-step CTA.

### `story.html` — Origin Narrative

**3-second comprehension: PASS.** The clearest, most human opening on the site.

**Issues:**
- "What $12.73 built" conflates personal DeepSeek spend with all-model research spending.
- "Why I was the person" section is self-validating, not evidentiary.
- Only CTA sends readers back to the overview, not to the evidence they've been primed to trust.

### `methodology.html` — Research Design

**3-second comprehension: FAIL.** Opens with "reasoning topologies" instead of the research question.

**Issues:**
- TL;DR is collapsed behind a `<details>` while an install command is promoted.
- Pipeline step 5 has no title.
- Limitations appear after conclusions — they should precede them.
- "Every run is seeded for reproducibility" overstates what a random seed guarantees with changing hosted models.

### `accelerator.html` — The Product

**3-second comprehension: FAIL.** "FinOps engine" and "enterprise acceleration" are abstractions. The page never states what the Accelerator actually is: software, consulting, a guide, or a future product.

**Critical issues:**
- The measurement harness (the actual thing that exists) doesn't appear until line 492.
- Maturity ladder is previewed then repeated in full.
- Executive dashboard values have no provenance — they look like customer data but where did they come from?
- 50-70% savings, 10× throughput, and "pays for itself in month 1" are not demonstrated by the experiment.
- **There is no CTA.** No install instructions, no contact form, no demo request, no email. A page called "Apply" ends with links back to content.

### `databricks.html` — Comparison

**Issues documented in stop-ship #10 above.** The four-lever structure provides the best scrolling rhythm on the site. Should be secondary navigation, not the homepage's centerpiece.

### `glossary.html`

**Issues:** 15 terms, unordered, no search, no anchor links, no cross-references to rules or evidence. Missing key terms: Batch Discount, Budget Ceiling, Cascade Rule, SLA Buffer.

---

## VISUAL DESIGN CRITIQUE

### What works

- **Dark theme is appropriate** for an analytical/technical audience. The `#0D1117` background and `#E6EDF3` text provide good contrast. Light theme toggle is a thoughtful addition.
- **JetBrains Mono** is the right monospace font — legible at small sizes, distinctive character.
- **CSS custom properties** are well-organized and make theming straightforward.
- **Color system** (accent indigo, amber warnings, cyan highlights, green success, red danger) is disciplined and consistent.
- **Card grid pattern** provides visual consistency across all pages.
- **Stat cards** are effective for key metrics — the `hover:translateY(-2px)` micro-interaction is tasteful.

### What doesn't work

- **Homogeneous visual weight.** Cards, stat cards, highlight boxes, note boxes, and callout boxes all look nearly identical (same background, same border, same padding, same radius). Critical proof, secondary caveats, and decorative elements have equal visual presence. A reader cannot distinguish "read this" from "this is context" without reading everything.
- **No visual hierarchy within pages.** Every section uses the same card grid pattern. There is no hero/featured/standard/minor progression. The result is monotonous — the eye finds no anchor point.
- **Tables at 0.65-0.78rem are hostile to reading.** Evidence tables, the framework calculator, provider playbook — these are the most important content on the site, rendered at a font size that communicates "you don't need to read this."
- **The indigo accent `#6366F1` is muted on dark backgrounds.** It doesn't "pop" — links and CTAs blend into the background more than they should. Consider a slightly brighter accent for interactive elements.
- **JetBrains Mono at 0.72rem body text** (used in some cards) is uncomfortable for extended reading. Monospace is for code, not prose. The framework cards on `framework.html` use mono for metric values — good. But when used for paragraph text, it fights readability.
- **No illustrations, no diagrams, no visual metaphors.** For a framework that introduces complex concepts (attractor basins, cascade routing, N² curves), the absence of explanatory visuals is a barrier to comprehension. Even simple SVG diagrams or ASCII-art style illustrations would significantly improve understanding.
- **The site looks like documentation, not a product.** This is fine if the audience is researchers. It's a problem if the audience is engineering leaders evaluating a framework or product. Compare to: Vercel's analytics dashboard, Datadog's cost pages, Linear's method pages. All use dark themes with technical content but employ visual hierarchy, illustration, and breathing room.

### Comparison to DeepSeek/competitor sites

| Aspect | AI FinOps | DeepSeek | Anthropic | OpenAI |
|--------|-----------|----------|-----------|--------|
| Visual hierarchy | Flat — everything same weight | Strong — hero → features → details | Strong — narrative-led | Product-led with clear sections |
| Illustrations | None | AI diagrams, architecture graphics | Conceptual illustrations | Product screenshots, animations |
| Typography scale | 2 levels (heading, body) with occasional mono | 3-4 levels with clear differentiation | 3-4 levels | 4+ levels |
| Breathing room | Tight — dense card grids | Generous sections with whitespace | Generous with interleaved quotes | Spacious, marketing-oriented |
| CTA clarity | Multiple, equal weight, no primary | Single primary per page | Clear primary + secondary | Strong primary with urgency |

**Recommendation:** The analytical, data-driven aesthetic is the right identity. But it needs breathing room between ideas, a clear typographic scale (at least 3 levels: hero headlines, section labels, body), and simple conceptual diagrams for the 10 rules and cost models. You don't need illustrations like Anthropic — you need explanatory diagrams like Stratechery or The Pragmatic Engineer use.

---

## NARRATIVE COHESION

### The intended story vs. the delivered story

**Intended:** Surprising result → proof → method → decision rules → implementation  
**Delivered:** Third-party authority → repeated claim → speculative theory → undefined product

### Where the narrative breaks

1. **The Databricks lead buries the real story.** The most compelling hook is "I spent $20 on a train ride and discovered a 69× cost gap through 227 controlled experiments." That's a human story with a surprising result. Instead, the hero leads with a $40B company's blog post. The Databricks validation is supporting evidence, not the headline.

2. **The Rome-to-Naples story is buried in a single sentence** (`index.html:68`) in 0.8rem text below the hero stats. This is the emotional core of the project — it should be prominent, not an afterthought.

3. **`story.html` is the best page on the site** and it's hidden in the nav as fifth item. It contains the narrative thread that makes the data meaningful. Consider whether it should be the homepage, or at least the second item in nav.

4. **No page answers "what should I do next?"** Framework has no end. Evidence has no end. Accelerator has no CTA. Every page is a dead end that requires the reader to navigate back to the nav bar and guess.

### The gap between what's proven and what's claimed

The 227 experiments prove:
- DeepSeek is 69× cheaper than Claude per session
- DeepSeek is as good or better on most tasks
- Some models flail under perturbation

The experiments do NOT prove:
- 50-70% cost reduction for your organization
- 10× throughput increase
- That persistent memory makes sessions cheaper (it contradicts the Snowball Rule)
- That the cascade routing model works at enterprise scale

The site repeatedly claims the second set with the evidence of the first. This gap is the single biggest credibility risk at launch.

---

## ANALYTICS RECOMMENDATION

### Approach: Firebase Cloud Function + Firestore (recommended)

A server-side hit counter with zero client-side tracking:

```
Visitor → Firebase Hosting → Cloud Function (onRequest) → Firestore increment
```

**Architecture:**
- Deploy a single Cloud Function that fires on each page request
- Write a counter document to Firestore: `{path: "/", timestamp: ..., user_agent_hash: ...}`
- Aggregate via scheduled function: daily/weekly unique visitors, page views, referrers
- Zero cookies, zero localStorage, zero front-end JS
- GDPR-compliant by default (no PII, no consent needed)

**What you can measure (without cookies):**
- Page views per path
- Unique visitors (hash IP + user agent, rotated daily)
- Referrer (from `Referer` header)
- Time of day distributions
- Geographic distribution (from `X-Forwarded-For` or Cloudflare headers)

**What you can't measure (and shouldn't):**
- Session duration
- Scroll depth
- Conversion funnels
- Return visitor identity

**Cost:** Essentially free at any reasonable traffic level. Firestore free tier: 50K reads/day, 20K writes/day. Cloud Functions free tier: 2M invocations/month.

### Additional considerations

1. **Firebase Hosting already logs requests** in Cloud Logging (30 days retention). You could skip the Cloud Function entirely and query Cloud Logging with BigQuery. This means zero additional infrastructure. The tradeoff: no real-time dashboard, query latency of hours.

2. **Add a privacy page** (`privacy.html`) stating: "This site performs no client-side tracking. Server-side access logs are retained for 30 days for operational purposes. No cookies are set. No personal data is collected." This builds trust and covers regulatory requirements.

3. **Consider Cloudflare Web Analytics** as an alternative — also cookie-free, also server-side, but provides a pre-built dashboard. Requires pointing your domain through Cloudflare.

4. **The Firebase approach keeps everything in one platform.** Given this is already a Firebase project, the Cloud Function + Firestore approach is the natural choice.

---

## RANKED IMPROVEMENTS

Ranked by impact on credibility and usability. #1-#4 are launch-blocking.

| Rank | Change | Pages affected | Effort |
|------|--------|---------------|--------|
| **1** | Fix the canonical corpus — single source of truth in `data.js`, all pages consume via `data-stat`. Eliminate every hardcoded number in HTML prose. | All | Medium |
| **2** | Move `app.js` to before `</body>` on every page. This fixes the theme toggle and data-stat injection. | All 8 HTML | Low |
| **3** | Fix evidence.html contradictions — prose must match live table values, provenance tags must be preserved in model cards, model card field names must match `data.js`. | evidence.html | Medium |
| **4** | Fix WOC direction, Grit definition, and First-Pass arithmetic across all pages. Pick ONE definition per term and propagate it everywhere. | framework.html, accelerator.html, glossary.html | Medium |
| **5** | Add a primary CTA to every page. Framework → "Calculate your costs." Evidence → "Run the instrument on your data." Accelerator → "Get in touch" or "Deploy the harness." Every page must answer "what now?" | All | Low |
| **6** | Restructure homepage narrative: Story → Problem → Key result (69×) → How it works → Evidence preview → CTA. Databricks comparison moves to a validation badge, not the hero. | index.html | High |
| **7** | Add visual hierarchy — introduce a "featured section" style (larger, with accent border), a "secondary section" style (subtler), and a "detail section" style (small, collapsed). Not everything can be the same card grid. | base.css, all pages | Medium |
| **8** | Add simple diagrams for: the 10 rules flow, the N² curve, cascade routing, attractor basins. ASCII-art style or minimal SVG. One diagram per page changes comprehension dramatically. | framework.html, evidence.html, methodology.html | High |
| **9** | Increase evidence table font size to minimum 0.82rem. These tables are the proof — don't render them at footnote size. | evidence.html, base.css | Low |
| **10** | Fix Accelerator page — either define what the product IS (software? guide? consulting?) or restructure as "implementation guide" with concrete steps. Add a real CTA. | accelerator.html | High |

---

## SUMMARY

The core asset — 227 controlled experiments proving a 69× cost gap — is strong. The website undermines it with inconsistent numbers, contradictory definitions, broken JavaScript, blank sections, and claims that outrun the evidence.

**Before launching publicly:**
1. Fix the 4 launch-blocking issues (canonical corpus, app.js placement, evidence contradictions, terminology)
2. Restructure the narrative to lead with the story, not the Databricks validation
3. Add CTAs to every page
4. Consider whether the Accelerator page should exist in its current form — it claims too much and proves too little

The framework is sound enough to publish. The website is not yet ready.
