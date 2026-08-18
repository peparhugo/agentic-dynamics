# Hand-off — Agentic Dynamics (ai-finops-framework)

**Date:** 2026-08-17
**Repo:** `peparhugo/agentic-dynamics` (remote origin), local `/home/drseuss/ai-finops-framework`

## TL;DR

This repo is the measurement instrument for **Agentic Dynamics** — the empirical study of how AI
agents behave under change, *measured as business outcomes*. This session instrumented the missing
ledger fields, re-ran the contaminated cells, corrected the single-task corpus, and produced three
model-authored website rewrites. **Two things are unresolved and must be handled before anything
new ships: (1) the story corpus shrank 221→156 (a data-integrity regression), and (2) the website
rewrite is NOT clearly better than the already-live site.**

## The live site (do not regress past this)

`https://ai-finops-rulebook.web.app` (canonical) + `agentic-dynamics.web.app` (mirror). The live
site is **mature and good**: a Why→What→How→evidence→"durable-value gap" narrative with concrete
provenance-tagged findings. It shows **1,097 story sessions / 221 stories / $288.69**.

## What landed this session (done + merged)

- **Operator fix** — strength-0 no-op, `inject_alien_vocab` cross-domain, `reverse_causality` dedup,
  `derive_seed` (deterministic, `seed_variant` deviates / repetition re-measures).
- **Ledger instrumentation** — `confidence`, `perturbation_strength`, `test_executed_success`
  (independent), `answer`/`explanation` token split now measured (was the "load-bearing gap").
- **Flash-authored perturbation** — `compile_prompt_perturbation` (session path of the starting point).
- **queue_steer** — `src/instrument/queue_reinterleave.py` + `POST /api/queue/reinterleave`.
- **Control Room observability** — three-stage pipeline view (execute/analyze/review) + live workflow
  phase badge; `FINOPS_HOST=0.0.0.0 FINOPS_PORT=8001` (ChromaDB owns 8000).
- **auto_posthoc_wiring** — `worker.py`/`analysis_worker.py` auto-trigger analyze→review per worktree.
- **Spec family** — `posthoc_pipeline`, `labbook_refresh`, `self_recommending_experiment`,
  `routing_regret_under_degradation`, `explanation_tax` (rewritten: output decomposition, not "tax"),
  `process_perturbation_resample`, `control_room_*`, `website_rewrite`.
- **Docs** — `docs/agentic_dynamics_vision.md` (positioning), `docs/website_rewrite_compare.md`,
  `code_reviews/2026-08-15_self-healing-remediation-finding.md`, `docs/agentic_dynamics_arxiv_draft.md`.

## New measured averages (the defensible silver lining)

| Metric | Value |
|---|---|
| Cost spread at equal correctness | $0.014 vs $0.44/run (30×) — DeepSeek vs premium, both 100% |
| Recovery under real degradation | 100% success, $1.56/story (vs $1.27 clean) |
| Cost compounding (snowball) | 4.6× session 1→5 under real degradation |
| Confidence (measured) | 0.96 mean |
| Token decomposition | reasoning 4.1× code+prose; narration 1.7% of code |
| Verification correlation | −0.077 |
| Hardest story | `static_site_gen` correctness 0.39 |

## ⚠️ OPEN ISSUE #1 — story corpus shrank (most urgent)

**Symptom:** live site says **221 stories / 1,097 sessions / $288.69**; current `data.js` and
`experiments/results/stories/*.json` say **156 stories / 772 sessions / $219.51**. ~65 story result
files (and their sessions/cost) went missing somewhere in the remediation re-run + `sync_data`
regenerations.

**Likely cause (unverified):** the remediation `rerun_contaminated` re-ran the `early_degrade` cells
only, and some combination of overwrite/cleanup + the 13 dropped Claude stubs reduced the on-disk
corpus. **Action:** check `git log` for the old `experiments/results/stories/*.json` (the 221-file
set is committed in history — e.g. the "restore 227-run corpus" era) and determine whether the ~65
missing files are recoverable, then decide restore-vs-accept.

## ⚠️ OPEN ISSUE #2 — single-task summary shrank

`analyze_worktrees.py` regenerated `_results_summary.json` from the *present* worktrees, shrinking it
**227 → 144 entries (49 valid)** and leaving escape `NaN` for most (baseline-less). The old 227-entry
summary is committed in git. Same restore-vs-accept decision needed.

## ⚠️ OPEN ISSUE #3 — website rewrite (three models)

- Three independent rewrites on branches `feature/website-rewrite-{deepseek,fable5,openai}` (each a
  full `firebase/public/` rewrite in place).
- Assembled a "best-of" on `feature/website-rewrite-bestof` (Fable 5 base + DeepSeek evidence/methodology
  + OpenAI evidence-boundary/legend).
- **Verdict: NOT confident it beats the live site.** The models gutted it (DeepSeek −3050, OpenAI −4103
  lines), and it sits on the *smaller* corpus. Comparison + cherry-pick table in
  `docs/website_rewrite_compare.md`. Keep the live site up until #1/#2 are resolved.

## Environment / ops notes

- Redis: framework queue on **6380 db 1** (`story_jobs`/`analysis_jobs`/`review_jobs`). Never 6379.
- Control Room: `FINOPS_HOST=0.0.0.0 FINOPS_PORT=8001 python3 admin/server.py` (Tailscale reachable).
- `claude` CLI was intermittently missing → 13 Claude cells un-runnable; resample later ran claude-fable-5
  fine. Check `which claude` if Claude cells stub.
- `pytest` venv: `/tmp/pytest_venv` is `--without-pip --system-site-packages` + a no-op `bin/pip`
  (ensurepip unavailable on this host). Recreate that way if it breaks.
- Worktree/run pattern: `git worktree add -b feature/<x> /tmp/pipeline/feature_<x>` then
  `python3 scripts/run_workflow.py --spec experiments/specs/<x>.yaml --goal "..." --model <m> --workdir <wt>`.

---

## Session prompt (paste into a new session)

> You are continuing work on the **ai-finops-framework** repo (the measurement instrument for
> **Agentic Dynamics** — how AI agents behave under change, measured as business outcomes). Read
> `docs/HANDOFF.md` first, then `docs/agentic_dynamics_vision.md` for positioning, and
> `docs/website_rewrite_compare.md` for the three-model rewrite review.
>
> **Before doing anything new, resolve the data-integrity regression:** the story corpus shrank from
> **221 stories / 1,097 sessions / $288.69** (live site + git history) to **156 / 772 / $219.51**
> (current `data.js` + `experiments/results/stories/`). Use `git log -- experiments/results/stories/`
> to find where ~65 story result files disappeared, determine whether they're recoverable from history,
> and either restore them or document a deliberate accept decision. The same restore-vs-accept question
> applies to the single-task `_results_summary.json` (shrank 227→144).
>
> The live site (`ai-finops-rulebook.web.app`) is mature and good and should NOT be regressed; the
> three-model website rewrite (`feature/website-rewrite-*`) is NOT clearly better and should not be
> deployed until the corpus question is settled. Do not touch `firebase/public/` on `main` until the
> corpus is restored. Report the corpus-shrinkage root cause first, then propose the next step.
