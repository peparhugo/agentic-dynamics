# AI FinOps Framework — UX Re-Review (v2)

**Date:** August 9, 2026
**Scope:** All 8 HTML pages + base.css, app.js, data.js
**Context:** Second-pass review after ~20 structural/content fixes applied

---

## 1. What Improved From the Previous Review

- **Consistent design tokens across all pages.** `base.css:5-21` defines a full dark-theme palette (`--bg`, `--bg2`, `--ac`, `--am`, `--cy`) with a light-theme path (`base.css:24-25`). Every page now inherits from a shared stylesheet rather than duplicating inline styles.

- **Data-driven stat injection works.** `app.js:48-69` populates `data-stat` elements from `data.js`. Footer session counts, cost totals, and the cost-gap multiplier are no longer hardcoded dead numbers — they reflect the live data (`data.js:537-538`).

- **Navigation is consistent.** All 8 pages use the identical 7-link topbar (`index.html:47`, `framework.html:82`, etc.), with the active page highlighted via `style="color:var(--ac)"`.

- **TL;DR disclosure toggles** added on `evidence.html:76-81` and `methodology.html:51-57`. These provide a skimmable entry point before the wall of tables.

- **Model cards now exist.** `evidence.html:260-265` renders per-model cards dynamically from `data.js:20-393` (merged with hardcoded fallbacks). This filled a major gap from the prior review.

- **Charts render** (cost bar, narration, LOC-vs-cost scatter, Grit matrix bubble) on `evidence.html:277-466` and the projection chart on `framework.html:384-385`.

- **The Databricks comparison page** (`databricks.html`) now has its own dedicated page with side-by-side claim boxes. Strong content, good layout.

---

## 2. What's Still Broken or Problematic

### 2.1 Conflicting Session/Experiment Counts

The site uses at least **four different numbers** to describe the same corpus:

| Number | Where | Reference |
|--------|-------|-----------|
| 248 | Hero, footer, nav, everywhere | `index.html:50`, `framework.html:88` |
| 249 | `data.js:13` | `sessions_total: 249` |
| 227 | `evidence.html:79` | "227 experiments with 10 stress tests" |
| 224 | `data.js:14` | `game_reports: 224` |

`index.html:50` says `<span data-stat="sessions">248</span> Experiments` — but `app.js:30` maps `sessions → D.summary.sessions_total` which is **249**. Every page uses data-stat="sessions" so it shows 249 after JS runs, but the fallback HTML text reads "248." The hero subtitle (`index.html:52`) *also* says "248 instrumented experiment sessions" in the prose fallback text. Both conflict.

**Fix:** Pick one number (248, plus a note that 1 is exploratory/not counted) and hardcode it consistently. Or have the fallback text match what data.js will inject.

### 2.2 framework.html: Calculator Hardcoded Model Data Diverges from data.js

`framework.html:341` defines a fallback `models` array with pass rates that don't match `data.js:20-393`:

| Model | Fallback (line 341) | data.js | Delta |
|-------|---------------------|---------|-------|
| DeepSeek v4 Pro | `p: 0.95` | `pass_rate: "84% (976/1163)"` | 11% off |
| GPT-5-mini | `p: 1.0` | `pass_rate: "94% (30/32)"` | 6% off |
| GPT-5 | `p: 1.0` | `pass_rate: "70% (16/23)"` | 30% off |
| Claude Fable 5 | `c: 1.01` | `avg_cost: 1.0847` | $0.075 off |

The fallback would produce incorrect calculator outputs when data.js fails to load. The values should match.

### 2.3 evidence.html: Hardcoded `fb` Array Conflicts with data.js

`evidence.html:538-596` defines a hardcoded model array (`fb`) used for model-card rendering. Key mismatches with `data.js`:

- `fb` DeepSeek: `sessions:133, total:2.04, grit:8, locPerSes:706`
- data.js DeepSeek: `sessions:133, total_cost:2.0427, narration_rate:8, avg_loc:706`

The merge logic (`evidence.html:601-611`) tries to overlay `data.js` fields onto `fb` entries by fuzzy-matching IDs. This is fragile — it matches on substring (`f.id.indexOf(dm.id) >= 0`), which would match `gpt-5` against both `gpt-5` and `gpt-5-mini`.

### 2.4 "Grit" Has Two Meanings — And One Is Wrong

`glossary.html:32-33` defines **Grit** as "Ground-Truth Integrity" — a *positive* quality metric measuring how well a model maintains correctness under degraded input.

But in the hardcoded `fb` array (`evidence.html:546`), `grit:8` for DeepSeek is actually the *narration/failure rate* (8% of sessions produce zero code) — a *negative* metric. The rendered model card (`evidence.html:639`) labels this as "Narration Rate" with subtitle "Failure rate under perturbation (lower = better grit)."

- `evidence.html:556`: GPT-5-mini has `grit:8` (8% failure rate)
- `evidence.html:565`: GPT-5 has `grit:15` (15% failure rate)
- `evidence.html:569`: GPT-5.5 has `grit:50` (50% failure rate)

The column is called `grit` but rendered as "Narration Rate." A new visitor reading "GPT-5.5: 50% grit" would think it means the model has good grit, while actually it has the *worst* failure rate. The variable should be renamed to `narration_rate` or `flail_rate` throughout.

### 2.5 story.html: DeepSeek Spending Figure Is Wrong

`story.html:57` states "I burned through $12.73 in DeepSeek compute." But `app.js:41` maps `deepseek_cost → fmtUSD(D.derived.total_cost_deepseek)` which returns **$2.04** (from `data.js:544`). The hardcoded fallback text says $12.73; the live data says $2.04. The $12.73 may include non-experiment personal sessions, but the data.js value (derived from `total_cost_deepseek: 2.0427`) only covers experiment sessions.

**Fix:** Either expand `total_cost_deepseek` in data.js to include non-experiment sessions or change `story.html:57` to use a different data-stat key.

### 2.6 Shared CSS Classes Missing from base.css

- `.trust-grid` is defined inline on `index.html:33-37` but used on `accelerator.html:159` and `accelerator.html:364`. If accelerator.html is loaded directly (not through a navigation path that loaded index.html), the grid styling is absent. Same for `.entry-cards`, `.entry-card`, `.link-grid`.

- `.wtm` is defined in duplicate: `index.html:26` and `framework.html:34` and `methodology.html:26`, each with nearly identical CSS. One definition should exist in `base.css`.

### 2.7 accelerator.html: Unstyled Card Elements

`accelerator.html:315-331` uses `<div class="card">` inside a `<div class="row">` for WOC ratio thresholds. But `accelerator.html` doesn't inherit `.card` styling from `base.css:108-116` — the `base.css` card styles require the parent `.cards` grid wrapper for layout. These three cards render with no background, no border, and no padding because the `.sec` class on `accelerator.html:17` overrides `base.css` section styles.

Same issue at `accelerator.html:316` where `<h4>` inside card has no styling.

### 2.8 "What Changed" Editorial Content Left In

`evidence.html:238` has an editorial note: "What changed: The original cross-domain table used single-run costs..." This is internal changelog content and should not appear in the public-facing page. Visitors don't need to know what the table looked like before.

### 2.9 TL;DR Disclosure Arrows Don't Rotate on Open

`evidence.html:77` and `methodology.html:52` use `<span style="font-size:1.2rem">&#9654;</span>` as a disclosure triangle. There's no JS to toggle this to `&#9660;` (▼) when the `<details>` is open. It stays as ▶ regardless of open/closed state.

---

## 3. First-Impression Test (3-Second Rule)

**Loading `index.html`:** The hero section communicates this well in under 3 seconds:
- Pulse badge: "v0.4 · Open Framework · 248 Experiments · 3 Architectures, 8 Variants"
- H1: "Your AI bill is a black box. This framework opens it."
- Stats row: 10 Rules, 69× Cost Gap, 93.2% Pass Rate, $59.45 Total Cost

**Verdict: Pass.** A visitor immediately knows: (1) this is about AI costs, (2) it's data-backed, (3) there's a measurable value proposition (69× gap). The follow-up subheader ("Not a benchmark. A measurement instrument.") adds credibility.

**Loading `accelerator.html`:** Less clear. The H1 "The FinOps engine that turns AI investment into enterprise acceleration" is corporate-speak. The "What is the Accelerator?" section (`accelerator.html:114-116`) explains it's "an implementation guide and measurement harness — open-source Python tooling" — good, but it takes scrolling past the hero to get that. The hero should state what the Accelerator is (a downloadable tool, not a service) in the first paragraph.

**Verdict: Weak.** Fix by rewriting the hero subhead to include "open-source measurement harness" or "Python tooling."

---

## 4. Narrative Coherence Across Pages

**The core narrative arc is strong:**
1. `index.html` → Problem (black-box costs) + solution teaser
2. `story.html` → Origin (personal discovery creating the instrument)
3. `framework.html` → Solution (10 rules, equations, calculator)
4. `evidence.html` → Proof (all data, tables, charts)
5. `methodology.html` → How it was built (operators, pipeline)
6. `accelerator.html` → Apply it (implementation guide)
7. `glossary.html` → Reference (terminology)

**But contradictions undermine coherence:**

- `evidence.html:79` says "227 experiments" while `index.html:50` says "248." Different pages tell different stories about the N.
- The "69×" gap is consistent everywhere (good), but the Claude cost varies: `index.html:77` shows `$1.01`, `data.js` shows `$1.0847`, evidence page hardcoded tables show `$1.06`.
- `story.html:57` says DeepSeek cost was $12.73; data.js says $2.04. A reader who checks both pages will question which number is real.
- The `framework.html:114` cache sub-lever description conflates Anthropic's cache-write with DeepSeek's cache-read — it reads like they're the same concept ("Cache write strategy: Store context at $3.75/Mtok (Anthropic). Cache read strategy: Retrieve existing context at $0.14/Mtok (DeepSeek default)") when they're actually two different provider economies.

**Verdict: Data inconsistencies across pages damage trust.** The narrative is good but the numbers need to be unified.

---

## 5. Visual Hierarchy

**Improved but uneven:**

- **Hero sections** (`index.html:49`, `evidence.html:65`, `framework.html:85`) are visually dominant — gradient backgrounds, large headings, pulse badges. Good.
- **Section alternation** (`framework.html:12`: `nth-child(even) → bg2, odd → bg`) creates visual rhythm.
- **Tables** are readable with zebra striping from borders, but the dense evidence tables (`evidence.html:157-167`) have 9 columns in some rows — at mobile widths these are unreadable.
- **CTA buttons** have consistent style (`base.css:178-189`) with proper hover states.
- **The gaps:**
  - `accelerator.html` has no hero-style opening — its `.sec.alt` header uses a flat layout with no gradient or visual punch (`accelerator.html:101`).
  - `story.html:10` uses `article{max-width:720px}` but has no visual section breaks. The three-part structure relies entirely on centered mono text (`story.html:47`) with no visual separation between Parts 1, 2, and 3.
  - The "same output, 69× different cost" section on `index.html:71` has a 3-row table but no chart — a bar chart here (like the one on `evidence.html:297`) would provide visual reinforcement.
  - Footer variation: `framework.html:335` and `evidence.html:270` use `&middot;` separators; `index.html:133` uses `<br>` + inline links. Inconsistent.

**Verdict: The skeleton is good. Story and Accelerator pages need section visual breaks.**

---

## 6. Remaining Confusing or Contradictory Sections

### 6.1 framework.html:114 — Cache Write vs Read Description

```
Cache write strategy: Store context at $3.75/Mtok (Anthropic).
Cache read strategy: Retrieve existing context at $0.14/Mtok (DeepSeek default).
```

This juxtaposes *two different providers* as if they're interchangeable strategies within a single provider. A reader thinks: "I can choose cache-write or cache-read on any provider." That's false. Anthropic's cache-write is $3.75; Anthropic's cache-read is $0.30 (`framework.html:265`). DeepSeek's cache-read is $0.14. The description should say: "Anthropic cache-write: $3.75. Anthropic cache-read: $0.30. DeepSeek cache-read (default): $0.14."

### 6.2 evidence.html:109 — "Grit: The Flail Rate"

The section is titled "Grit: The Flail Rate" but presents a table of "Narration Penalty" rates. The word "Grit" is used as a section header for a table that measures failure rates. This is the naming confusion from section 2.4 above. The table is actually about *narration penalty / flail rate*, not Grit (which is integrity under degradation).

### 6.3 index.html:73 — "69× different cost" But Shows 3 Models, Not 8

The claim: "We tested 8 models across 227 experiments." The visible comparison table: 3 models (DeepSeek, Claude, GPT-5.6). The reader expects to see all 8.

### 6.4 framework.html:193 — "Toggle to DS Scenarios" Has Two Options But Description Mentions Three

Line 193 says: "Toggle to DS Scenarios for aggressive (2.5%) and optimistic (0.8%) energy paths." But the chart toggle row only has two EPM options: "Baseline" and "DS Scenarios." There's no separate "Optimistic" toggle. The DS Scenarios toggle appears to only show aggressive.

### 6.5 glossary.html:88-89 — Strategy Archetypes Definitions Are Cyclic

The "Strategy Archetypes" definition uses the archetype names in the descriptions: "CONSERVATIVE (low explore, high recover — Claude, GPT-5.6)" vs "EXPLORATORY (high escape, low recover — DeepSeek)." But earlier, the methodology (`methodology.html:120`) shows Manifest escape=0.76 for DeepSeek and 0.62 for Claude — meaning DeepSeek escapes MORE, not less. So how is DeepSeek classified as "EXPLORATORY (low recover)" if it has 0.18 escape on semantic? The meaning of "recover" and "escape" isn't consistently defined.

### 6.6 evidence.html:617 — Pass Rate Parsing Bug

```javascript
var passRate = (d.pass_rate || m.pass).replace(/[ \[\]H]/g,'');
```

The regex `[ \[\]H]` strips spaces, brackets, and the letter 'H'. This means if a pass rate string is "88.7% (1572/1772)", after replacement it becomes "88.7%1572/1772". Then `parseFloat()` on line 632 would get `88.7` — which works by accident. But it also strips every 'H' character, which could corrupt model identifier strings if used elsewhere.

---

## 7. If Launching Tomorrow: Top 3 Must-Fix Items

### Fix 1: Unify Session Count Across All Pages

Every page must use the same number. Root cause: `data.js:13` says 249 sessions, hardcoded fallbacks say 248, TL;DR says 227. Change the hardcoded `data-stat` fallback values to 248 everywhere (or update data.js build to produce 248) and add a brief note on `evidence.html:67` and `methodology.html:54` explaining the breakdown: "248 sessions (227 experiment runs, 21 cross-model TS runs, plus exploratory)."

**Files:** `index.html:50,52,55,56,131,132`, `framework.html:88,334`, `evidence.html:79`, `accelerator.html:105`, plus anywhere else using hardcoded "248" or "227" in prose.

### Fix 2: Fix story.html DeepSeek Cost Display

`story.html:57` hardcodes "$12.73" but `data.js:544` returns $2.04. Either:
- Add a `deepseek_all_sessions_cost` field to `data.js` that includes non-experiment sessions
- Or change the story text to use `data-stat="deepseek_cost"` with correct markup: "I burned through <span data-stat="deepseek_cost">$2.04</span> in experiment costs alone."
- Change the fallback text from $12.73 to $2.04 to match data.js.

### Fix 3: Resolve "Grit" Naming Collision in evidence.html Model Cards

`evidence.html:546,556,565,569,573,578,584,590` — rename `grit` field to `narration_rate` or `flail_rate`. The rendered model card (`evidence.html:639`) correctly labels it "Narration Rate" but the source variable name `grit` creates confusion with the positive metric defined in `glossary.html:32`. While you're there, verify the `evidence.html:617` pass-rate regex doesn't strip meaningful characters.

---

## Summary

| Dimension | Rating | Notes |
|-----------|--------|-------|
| First impression | **B+** | Hero is strong. Accelerator page needs clearer value prop. |
| Narrative coherence | **B-** | Arc is good; inconsistent numbers across pages erode trust. |
| Visual hierarchy | **B** | Solid on main pages; story/accelerator pages are flat. |
| Data integrity | **D** | Conflicting session counts, wrong DS cost, calculator mismatch. |
| Terminology consistency | **C** | "Grit" means two things. Cache strategy descriptions misleading. |
| Cross-page CSS | **C** | `.trust-grid` and friends only in index.html's inline `<style>`. |
