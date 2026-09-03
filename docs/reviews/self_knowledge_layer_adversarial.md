---
status: accepted
kind: adversarial_review
spec: self_knowledge_layer
phase: s7_adversarial
author_model: deepseek/deepseek-v4-pro
author_under_review: deepseek/deepseek-v4-flash
generated_at: 2026-09-03T23:47:33Z
---

# self_knowledge_layer s7 — INDEPENDENT adversarial review: loop 2 is real, correctly layered

**Release verdict: merge-ready to main.** Reviewer `deepseek/deepseek-v4-pro` (a DIFFERENT model
and session from the `deepseek-v4-flash` author). This review FALSIFIES, not certifies. Every
claim below was re-derived against the wave code at `/tmp/wt_selfk` (HEAD `9af93b313`) — a
hermetic probe exercising the real modules (injected tmp artifact dirs + fake knowledge stream),
plus the live s8 gate suite — none asserted. The six record families the wave builds (session
spine, decision records, wave verdicts, belief protocol, scoreboard, reflections) all held under
independent probe; the actor layering held under a workload-scope probe and the supervisor rail is
separate; no producer is opt-in. Four findings are recorded: two FIXED on-branch (F-1, F-4), two
RECORD-level accepted limitations (F-2, F-3) that are the belief engine's follow-up, not a falsified
claim.

---

## 1. Attack results, in mandate order

| # | Claim | Independent probe (hermetic, real modules) | Result |
|---|---|---|---|
| 1 | session open retrieves the last close; close writes a retrievable record | `session_ingestion.close_session` → `open_session` against a tmp dir + fake stream: close status `closed`, open status `opened` with the exact `slug`/`waves_run`/`merged`/`self_notes`; empty dir → `bootstrap`. Round-trip exact. | **PASS** |
| 2 | a promote invocation emits a decision record | `record_decision` with the promote-shaped dict (`actor: verified_command`, `category: promote`, `run_id`+`candidate_sha` bound): status `recorded`; `scan_decision_records(category="promote")` returns it; identical re-record → `no-op`. Call site wired in `scripts/promote.py` step 6 (after push, `_emit_best_effort`, injectable) + `publish_release.py`. | **PASS** |
| 3 | a completed run emits its wave verdict (synthetic completion) | `wave_verdict_ingestion.build_wave_verdict_record` from a synthetic ledger + control row + review: verdict `merge-ready`, `merge_state promotable`, `findings_count 3`, `residuals [RECORD…]`, `actor run`, `scope workload:…/job:…`. A `failed` run still emits (`verdict not`) — a failure is a verdict, not silence. | **PASS** |
| 4 | two confirms → ONE record n=2; disconfirm lowers the posterior | `version_from_record` chained twice: `entity_id` identical across all versions, `n_confirmations 0→2`, `supersedes` links the chain, posterior `0.5→0.75`; a disconfirm lowers `0.75→0.6`. | **PASS** |
| 5 | scoreboard rows measured from s3 records | `build_scoreboard` over two `wave-verdict/v1` artifacts: `waves_completed 2`, `waves_merged 1`, `merge_rate 0.5`, `findings_per_reviewed_wave 1.5`, `cost/wave mean 1.5 median 1.5`, per-model `['deepseek/deepseek-v4-flash']`; empty set → `waves_completed 0`, `merge_rate None` (not a fabricated zero). | **PASS** |
| 6 | reflection series accumulates session-keyed entries | two `append_reflection` (sess_A, sess_B) → `read_reflection_series` count 2 in session order; re-close B → still 2 entries, `sess_A` untouched, `sess_B` count 1 (never overwrites another session's). | **PASS** |
| 7 | actor layering: a cell/workload scope cannot resolve the AIO's private records; supervisor rail separate | `scope_excluded(record.repository_id, requested_scope)` is `True` for `self-wt_cell`, `org:agentic-dynamics/workload:other`, `self-wt_wave4` (the records carry `repository_id="agentic-dynamics"`); `grep` finds zero references to any new record family in `scripts/supervise.py` / `control/supervisor.py`. | **PASS** |
| 8 | no producer is opt-in (the k1 lesson) | wave-verdict + belief-update emissions are gated ONLY on the run ledger state (`_WAVE_VERDICT_LEDGER_STATES` = `{succeeded, failed}`), not a flag; session close / decision record / reflection append are default-on. The one opt-in path (`rag_augment`) is loop 1's pre-existing RAG, not a loop-2 producer. | **PASS** |

All eight mandate probes PASS. The wave is not falsified at the claim level; the four findings below
are gate/hygiene defects (fixed) and two belief-engine operational gaps (recorded).

---

## 2. Re-verification evidence (reproducible)

```bash
# (a) the full s8 gate, after the on-branch fixes
cd /tmp/wt_selfk && python3 -m pytest tests/test_session_spine.py tests/test_decision_records.py \
  tests/test_wave_verdicts.py tests/test_belief_protocol.py tests/test_scoreboard.py \
  tests/test_reflections.py tests/test_workflow_runner.py tests/test_knowledge_ingestion.py \
  tests/test_cli_resolution.py tests/test_script_classification.py tests/test_doc_lifecycle.py \
  tests/test_agent_config_render.py tests/test_control_status.py -q -p no:cacheprovider
# -> 568 passed in 45.03s   (BEFORE the fixes the same gate was RED: test_doc_lifecycle 2 failed)

# (b) hermetic probes 1-8 (the real ingestion modules, tmp dirs + fake stream)
# -> see §1; probe 4 chain: entity_id stable, n=2 after two confirms, posterior 0.5->0.75->0.6
# -> probe 7: scope_excluded(...) True for every cell/workload scope, False only for the empty scope
```

The `'inert belief engine'` concern was probed directly: with an EMPTY durable KB (the production
reality — see F-2), `apply_wave_verdict` returns `consulted=0 updated=0`; with the s4c seeds
persisted and a NEW run id, it returns `consulted=5 bearing=2 updated=2` with correct `supersedes`
links — the update protocol is real, it is simply never fed (F-2).

---

## 3. Findings

| # | Attack | Disposition | Reasoning + evidence |
|---|---|---|---|
| F-1 | **s8 gate is RED as shipped** — `test_doc_lifecycle.py` fails twice because `docs/designs/proposed/self_knowledge_layer.md` carries no frontmatter `status: proposed` (it has only a body `**Status:** proposed`). The wave declares `test_doc_lifecycle.py` in its s8 gate, so the gate fails. | **FIXED** on-branch | Verified: `python3 -m pytest tests/test_doc_lifecycle.py -q` → 2 failed (`test_every_document_has_status_field`, `test_kind_tree_statuses`), both naming only `self_knowledge_layer.md`. Every OTHER `docs/designs/proposed/*.md` starts with `---`. Pre-existing (the design doc was authored at `9d5511e10`, an ancestor of the merge-base `30f6b39fe`), but it is the wave's own gate that lists the test. Fix: added `---\nstatus: proposed\n---` frontmatter; the full gate is now green. |
| F-2 | **the belief engine's trigger is inert in production — the s4c seeds are never persisted.** `belief_seeds.derive_seed_records()` has no producer/command (grep: `SEEDS`/`derive_seed_records` referenced only in the module + `__init__.py`), while `belief_update.belief_index()` reads only the durable KB artifacts. The s4b trigger (`_belief_update_payloads` in `run_workflow.py`) therefore consults an empty index and updates nothing. | **RECORD** (accepted limitation) | Probe: empty artifact dir → `apply_wave_verdict` `consulted=0 updated=0`; seeds persisted → `consulted=5 updated=2`. The s4c phase fence explicitly deferred persistence ("persisting it is a later phase's concern"), and the preregistered s4 criteria (seeds exist + retrievable by domain; two confirms → one n=2 record; disconfirm lowers) are met at the type+protocol level. Follow-up: a persistence step (`kb_produce`-style belief source or a seed bootstrap) must write `derive_seed_records()` to the durable KB before the trigger updates anything. |
| F-3 | **the wired trigger's default polarity mis-polarizes the pessimist seed.** `_belief_update_payloads` calls `apply_wave_verdict` WITHOUT a `signal_fn`, so the default `verdict_signal` treats every green verdict as a `confirm`. Seed 3 ("findings were opt-in and never produced") is a pessimist hypothesis whose green outcome must DISCONFIRM — yet a green `kb_finding_layer` verdict would CONFIRM it (n_conf 0→1, posterior 0.333→0.5, the wrong direction). The `signal_fn` inversion hook exists (module docstring names it) but is never passed at the call site. | **RECORD** (accepted limitation) | Probe: seeded KB + green `kb_finding_layer` verdict → the "findings were opt-in…" seed received `signal=confirm`. The update OPERATION itself is polarity-explicit (`update_belief(signal=…)`), so the direct seam is correct; the DEFAULT polarity at the trigger is naive. Fix path: encode polarity on the belief record (a `polarity: positive|negative` field, `negative` on seed 3) and invert in `apply_wave_verdict`'s default, or pass a `signal_fn` at `_belief_update_payloads`. This only manifests once F-2 is addressed (the engine is inert until the seeds land), so it is a follow-up, not a live wrong-update today. |
| F-4 | **scoreboard empty/absent render prints literal `None`.** `_render_human` left the mean/median rows un-guarded, so an empty scoreboard rendered `cost/wave (mean None, median None)` — contradicting the "measured-or-absent, never fabricated" doctrine and the `merge_rate`/findings rows' `n/a` guard. | **FIXED** on-branch | Verified: `build_scoreboard(empty_dir)` + `_render_human` printed `mean None, median None`. Fix: added a `_fmt` helper (`None` → `n/a`) and applied it to every measured row in `_render_human`; re-probe now prints `mean n/a, median n/a`. Cosmetic only — the underlying document was already correct (`None`, never `0.0`). |

F-1 and F-4 are fixed on the branch. F-2 and F-3 are RECORD-level accepted limitations: neither
falsifies a mandate claim, and both are the belief engine's already-deferred follow-up (F-2 is
explicitly out of the s4c fence; F-3 is a polarity-judgment boundary the author documented but left
unwired, and it cannot misfire while the index is empty).

---

## 4. Re-stated verdict

| Mandate | Result |
|---|---|
| session spine (open retrieves last close / close writes retrievable) | **PASS** — exact round-trip + bootstrap, re-verified |
| decision records at the moment of decision (promote/publish emit) | **PASS** — retrieve-by-category, bound run_id/candidate_sha, rerun-safe, call sites wired |
| wave-verdict narratives at run completion (default-on, failures emit too) | **PASS** — synthetic completion derives verdict/cost/phases/merge_state/residuals; failed run emits `not` |
| belief protocol (update in place, never duplicated; disconfirm lowers) | **PASS (type+protocol) / F-2+F-3 follow-up** — n=2 on two confirms, posterior moves correctly; the production trigger is inert until seeds persist (F-2) and needs polarity inversion (F-3) |
| scoreboard rows measured from s3 records | **PASS** — recomputed, deduped, measured-or-absent; empty set yields no fabricated zeros |
| reflection series accumulates session-keyed entries | **PASS** — one entry per session, series grows, nothing overwrites |
| actor layering (cell cannot resolve AIO records; supervisor separate) | **PASS** — `scope_excluded` holds for every cell/workload scope; supervisor rail has zero references to the new families |
| no producer opt-in (k1 lesson) | **PASS** — all six producers default-on; only the pre-existing RAG path is opt-in |
| s8 test gate | **PASS after F-1** — 568 passed (was red on `test_doc_lifecycle` before the fix) |

**Loop 2 is real + correctly layered.** Five of six record families (session spine, decisions, wave
verdicts, scoreboard, reflections) are fully operational and verified end-to-end; the sixth (the
belief engine) is structurally real — the update protocol and posterior rule are correct under
probe — with two recorded operational gaps (unpersisted seeds F-2, naive default polarity F-3) that
are explicitly deferred follow-ups rather than falsified claims. The actor/scope layering holds and
every producer is default-on. Merge-ready to main; F-2/F-3 should be carried by the controller as
the belief engine's next phase, not as a blocker on this wave.

---

## 5. LOG

```
s7_adversarial: PASS (merge-ready)
findings: F-1 FIXED (s8 gate red — design doc lacked status:proposed frontmatter; 2 test_doc_lifecycle failures)
          F-2 RECORD (s4c seeds never persisted -> belief trigger consults empty index, updates nothing;
                      persistence explicitly deferred by the s4c fence)
          F-3 RECORD (wired trigger default polarity mis-polarizes pessimist seed 3; signal_fn hook unwired)
          F-4 FIXED (scoreboard empty render printed "None"; added _fmt n/a guard)
verification: probes 1-8 all PASS (hermetic, real modules): close->open exact, decision retrieve-by-category,
              wave verdict merge-ready + failed->not, n=2 one entity + disconfirm lowers 0.75->0.6,
              scoreboard 2 records -> merge_rate 0.5 / empty -> no fabricated zeros, reflection 2 sessions -> 2 entries,
              scope_excluded True for every cell/workload scope, supervisor rail clean, all producers default-on;
              s8 gate 568 passed in 45.03s (post F-1/F-4 fixes)
```
