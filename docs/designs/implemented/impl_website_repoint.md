---
status: implemented
implemented_by: feature/website-repoint
---
# Website repoint (S3 + C1 + C2 + C3/C4) — implementation trace & verification

**Status:** implemented and verified. Every finding in `docs/reviews/website.md` §2–3 is
traced below to its file + line, with PASS/FAIL, the verification greps, and the pytest
result. This document is the proof that the site now resolves models by explicit id,
labels the fable-5 alias correctly, quotes the rebased DeepSeek pricing, and reports
canonical-registry counts.

**Phases traced:** `repoint_ui` (S3) and `fix_content` (C1 + C2 + C3/C4) of
`experiments/specs/website_repoint.yaml`.

**Re-run the whole thing (all commands from scratch):**

```bash
python scripts/build_data.py                 # -> firebase/public/data.js
python scripts/generate_manifest.py          # -> experiments/data_manifest.json
pytest tests/test_build_data.py tests/test_generate_manifest.py -q
```

---

## 1. S3 — rewire `statMap`/`findModel` to explicit model ids (never `indexOf`)

**Finding.** `app.js:30` resolved models with `ms[mi].id.indexOf(idPart) >= 0` over the
story corpus `D.models`, which is ordered by `avg_cost` (`compute_story_models`,
`build_data.py:1079`). So `findModel('deepseek')` returned Flash (first hit), `'claude'`
returned Haiku, `'gpt-5.6'` returned Luna — the *cheapest* substring match, not the model
the stats intend.

**Fix.** `firebase/public/app.js:46–60`:

- A declared `MODEL_RESOLUTION` map keys each lookup to one explicit provider/model id
  (`app.js:46`):

  ```js
  var MODEL_RESOLUTION = {
    'deepseek': 'deepseek/deepseek-v4-pro',   // flagship, not Flash
    'claude':   'anthropic/claude-sonnet-5',  // flagship, not Haiku
    'gpt-5.6':  'openai/gpt-5.6-sol',         // declared GPT-5.6 family default
    'nano':     'openai/gpt-5-nano',
  };
  ```

- `findModel(D, key)` (`app.js:53`) resolves the key through the map and then matches by
  **exact `id` equality** (`ms[mi].id === id`) — no `indexOf` anywhere.

**Declared-default decision (gpt-5.6).** The GPT-5.6 family has three members in the story
corpus (`luna`/`terra`/`sol`) and no plain `gpt-5.6`. By symmetry with the other two
provider defaults — both resolve to the flagship tier (DeepSeek **Pro**, not Flash; Claude
**Sonnet**, not Haiku) — the declared default is the flagship **Sol** tier
(`openai/gpt-5.6-sol`, $30/M output). It is explicit and documented in the `app.js` comment
block; switching to `luna`/`terra` is a one-line change in `MODEL_RESOLUTION`.

**Em-dash null-rendering was already done** (repoint follow-up) and left untouched:
`pctOrDash`/`penaltyOrDash` at `app.js:62–63` render `null` as an em-dash, never `0%`.

**Verify** (parsed from the regenerated `data.js` `models` array, resolving through
`MODEL_RESOLUTION`):

| key | resolves to | avg_cost | correct (was) |
|---|---|---|---|
| `deepseek` | `deepseek/deepseek-v4-pro` | $0.1588 | ✅ (was Flash $0.0681) |
| `claude` | `anthropic/claude-sonnet-5` | $4.7761 | ✅ (was Haiku $1.5369) |
| `gpt-5.6` | `openai/gpt-5.6-sol` | $3.9867 | ✅ (was Luna $0.0919) |
| `nano` | no match → `{}` | em-dash | ✅ (narration unmeasured in story corpus) |

**PASS.**

---

## 2. C1 — normalize `claude-fable-5` → `claude-sonnet-5`

**Finding.** `website.md` C1 + `docs/HANDOFF_2026-08-19.md`: the Claude CLI adapter silently
mapped `claude-fable-5 → claude-sonnet-5` until the fix, so **every historical
"claude-fable-5" result actually ran sonnet-5**. The site carried both names —
`evidence.html` archive said "Claude Fable 5", story pages said "Claude Sonnet 5".

**Fix (one source):**

| Location | Change |
|---|---|
| `scripts/_constants.py:16` | `MODEL_LABELS["anthropic/claude-fable-5"]` → `"Claude Sonnet 5"` (comment records the alias fact) |
| `scripts/build_data.py:941` | `_short_model_label` `"claude-fable-5"` → `"Claude Sonnet 5"` |
| `experiments/results/process_perturbation_resample_claude-fable-5.json:3,7,…` | `model` (top-level + 5 runs) → `anthropic/claude-sonnet-5` |
| `experiments/results/lab_grit_matrix.json` | 39 fable-5 `model`+`label` points → sonnet-5 |
| `firebase/public/evidence.html` | archive: all `Claude Fable 5` → `Claude Sonnet 5`, `claude-fable-5` → `claude-sonnet-5` |
| `firebase/public/framework.html:919,965` | calculator fallback + chart label `Claude Fable 5` → `Claude Sonnet 5` |
| `firebase/public/methodology.html:161` | strategy-taxonomy prose → `Claude Sonnet 5` |

**Verify.** `grep -rc "fable" firebase/public/data.js` → **0** (regenerated). `grep -rn
"Fable" firebase/public/*.html` → no matches. `build_data.py` now emits
`Computed: 6 perturbation models` (was 7 — the fable-5 findings merge into the one
sonnet-5 group, the correct outcome).

**PASS.**

---

## 3. C2 — DeepSeek pricing rebase + peak/off-peak

**Finding.** DeepSeek output was rebased to `$1.98/M` off-peak, `2×` at peak
(`efficiency.py:40–45`), but `story.html:123` still quoted the pre-rebase `$0.87` and
`11.5×`; `framework.html:830/868` quoted `$0.435/$0.0036/$0.87`; `framework.html:882`
inherited the stale `$0.14` per-session basis; peak/off-peak appeared nowhere.

**Fix (rates regenerated from `efficiency.PROVIDER_PRICING`: deepseek input 0.66 / cache_read
0.022 / output 1.98 off-peak, 2× peak; sonnet-5 output 10.00):**

| Location | Before → After |
|---|---|
| `story.html:123` | `11.5× ($10.00 vs $0.87)` → `~5.1× off-peak ($10.00 vs $1.98/M)`; adds `$3.96` peak + `01:00–04:00 & 06:00–10:00 UTC`, `~2.5×` peak gap |
| `framework.html:830` | DeepSeek row `$0.435/$0.0036/$0.87` → `$0.66/$0.022/$1.98` |
| `framework.html:834` | adds "DeepSeek rates are **off-peak**; peak is 2× (01:00–04:00 & 06:00–10:00 UTC)" |
| `framework.html:868` | DeepSeek card → `$0.66 / $0.022 / $1.98 (off-peak; 2× at peak)` |
| `framework.html:882` | `33× ($4.58 vs $0.14)` → `30× ($4.78 vs $0.16 per session)` (measured per-session, clearly labeled) |
| `framework.html:878,889,890` | `221 stories` → `156`; tier costs `~$0.14`/`~$4.58` → `~$0.16`/`~$4.78` |

The `30×` per-session gap is measured from the story corpus (`4.776119 / 0.158801 =
30.07`), distinct from the `~5.1×` per-token off-peak multiplier — the exact
per-session vs per-token conflation `website.md` C2 called out is now separated.

**Verify.** `grep -rn '$0.87' firebase/public/*.html` → no matches; `grep -rniE "11\.5x"`
→ no matches.

**PASS.**

---

## 4. C3/C4 — canonical corpus counts + mark historical figures

**Finding.** Static prose/meta still claimed the pre-shrink numbers: `1,097` sessions,
`221` stories, `227` experiments, `249` sessions, `224` game reports, `$288.69` cost — none
bound to the canonical registry (`canonical_stories` 225 / `canonical_findings` 64 /
`tombstoned_excluded` 77) or to the live story corpus (772 sessions / 156 stories / $219.51).

**Fix.**

*Canonical bindings (C3/C4 core):*

- `firebase/public/app.js:77–79` — three new `statMap` entries
  (`canonical_stories`/`canonical_findings`/`tombstoned_excluded`) reading
  `D.summary.*`.
- `firebase/public/evidence.html:95` — a "Canonical registry" receipt binding all three via
  `data-stat` (225 / 64 / 77). The values themselves are written by `build_data.py`
  `summary` block (`build_data.py:1311–1313`), straight from `corpus.story_count` /
  `corpus.finding_count` / `corpus.tombstoned_count`.

*Live story-corpus counts updated (already `data-stat`-bound; fallbacks + prose/meta synced
to the current generator output):*

| Token | → |
|---|---|
| `1,097` story sessions | `772` (`evidence/framework/index/story/methodology`) |
| `221` stories | `156` (141 unique + 15 reruns; `210 … plus 11 reruns` → `141 … plus 15 reruns`) |
| `$288.69` / `$288.6909` total cost | `$219.51` / `$219.5112` |

*Historical perturbation figures prefixed "historical"* (the pre-registry perturbation
corpus — 227 experiments / 249 sessions / 224 game reports — is frozen, not live):

- `framework.html:6,657,703,784` (`227 … perturbation experiments/worktrees`),
  `accelerator.html` (`249 … experiment sessions` ×5 + stat-card labels "Historical
  Experiment Sessions", `227 experiments`), `databricks.html` (`227 … controlled
  experiments` ×6), `methodology.html:6,46,52,60,89,274` (`249`/`227`), `story.html:6,81,112`,
  and the `evidence.html` archive (`227/249/224` — already under the "distinct, historical
  measurement" disclaimer, now explicit).

**Verify.** `grep` confirms no bare stale token remains outside historical framing:

```
1,097  -> none
$0.87  -> none
11.5x  -> none
227    -> none (all "historical")
224    -> none (all "historical")
221    -> none standalone (all -> 156)
249    -> 3 hits, all stat cards whose label reads "Historical…"
Fable  -> none (HTML) / 0 (data.js)
```

**PASS.**

---

## 5. pytest result

```
$ pytest tests/test_build_data.py tests/test_generate_manifest.py -q
............................                                             [100%]
28 passed in 0.19s
```

Additional safety run over the modules that reference the `claude-fable-5` model id (label
change must not disturb id-keyed logic):

```
$ pytest tests/test_build_data.py tests/test_generate_manifest.py tests/test_pricing.py tests/test_routing.py -q
....................................................                     [100%]
52 passed in 0.33s
```

No test was weakened. `test_pricing.py`/`test_routing.py` use `anthropic/claude-fable-5` as
an **id**, not a label, so the `_constants.py` label normalization is inert to them.

---

## 6. Build log (verbatim)

```
$ python scripts/build_data.py
Building data.js...
  Loaded inventory: 1078 experiment sessions
  Loaded canonical corpus: 64 finding + 225 story current records (77 tombstoned excluded); 64 perturbation entries
  Game reports on disk: 344
  Computed: 6 perturbation models          # was 7 — fable-5 findings merged into sonnet-5
  Story models: 7 (from stories.parquet)
Wrote /tmp/wf_website_repoint/firebase/public/data.js (174352 bytes)

$ python scripts/generate_manifest.py
Written /tmp/wf_website_repoint/experiments/data_manifest.json
  … registry: 635 entities (compacted from registry_index.jsonl)
```

`data.js` diff is content-only (label/id normalization + timestamps) — no corpus drift.

---

## 7. Engineer follow-ups (out of scope, not addressed)

1. **DeepSeek cache-read rate is stale but untouched.** Several pages state
   "cache-read at `$0.14/Mtok`" (`framework.html:664,845`, `glossary.html:105`,
   `accelerator.html:180,185`, `evidence.html:397,454`), while
   `efficiency.PROVIDER_PRICING["deepseek"]["cache_read"]` is `0.022`. C2 only flagged the
   *output* rebase (`$0.87 → $1.98`); this cache-rate claim is a separate stale number and
   should be regenerated from `PROVIDER_PRICING` in a follow-up.
2. **`lab_grit_matrix.json` was relabeled by hand.** It is a lab *output*; re-running
   `scripts/lab_grit_matrix.py` would now emit `label: "Claude Sonnet 5"` (via the changed
   `MODEL_LABELS`) but `model: "anthropic/claude-fable-5"` (it reads the legacy
   `_results_summary.json` id). The grit chart displays `label`, so the page stays correct;
   a full consistency fix belongs to the S1/S2 archive split.
3. **S1/S2 (split `evidence.html`, delete hard-coded inline arrays/fallbacks)** remains the
   larger structural follow-up — this repoint covered S3 + C1–C4 only, per
   `website_repoint.yaml`.
