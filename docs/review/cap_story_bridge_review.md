---
status: accepted
---

# CAP Story Bridge — Sonnet-5 Adversarial Review (a3_review_story_bridge)

**Reviewer:** claude-sonnet-5, `feature/cap-sonnet-adversary` phase `a3_review_story_bridge`
**Target:** `feature/cap-story_bridge` (spec names it `feature/cap-story-bridge`; same
underscore/dash cosmetic mismatch as the other three branches — confirmed not missing).
**Target commits:** `50b6eb0b5` (s1_token_split_instrumentation), `194605bab`
(s2_story_facts_reducer), `d68752aee` (s3_document), on top of shared base `6cdefa102`.
**Method:** re-derived the reducer/producer diff surface directly (`git diff` scoped to
`control/reducers/`, isolating exactly what changed); read `story_facts.py` side-by-side against
the pre-existing `attempt_facts.py` it claims to mirror; ran all 78 relevant hermetic tests in
the branch's own worktree (`/tmp/wt_story_bridge`, checked out at `d68752aee`); ran an
**independent, non-destructive live idempotency experiment** against a temp copy of the real
registry (never touched the on-disk `registry_index.jsonl`) to verify convergence-to-zero on a
second run, rather than trusting the doc's or the fixture tests' narrower claim.

## Verdict: **PASS — no findings, clean sweep**

This is the strongest of the three branches reviewed so far. Every one of the task's five named
attack vectors was checked against raw evidence and none of them falsified the work. Notably,
this branch's own reducer avoids — apparently by design, not luck — the exact idempotency defect
I found in the `pattern_minting` branch's `pattern/v1` reducer, and I verified the difference at
the code level and confirmed it live.

## Findings

None. No mandatory fixes, no informational notes rising to the level of a finding.

## Known-safe list (attacked, did not falsify)

| # | Attack attempted | Result |
|---|---|---|
| 1 | **"Zero diffs to existing reducers" — some pre-existing reducer file was modified, not just the new `story_facts.py`** | **Not falsified.** `git diff 6cdefa102 d68752aee -- src/agentic_dynamics/control/reducers/` touches exactly two files: `__init__.py` (5 lines — import + registry-dict entries for the new reducer, purely additive, no existing line changed) and the new `story_facts.py`. `attempt_facts.py`, `job_facts.py`, `workflow_facts.py`, `spec_status.py`, `policy_facts.py`, `pattern.py`, `checkpoint.py`, `_common.py` are all byte-identical to the base commit — confirmed by the empty diff, not by trusting the doc's own table (which makes the identical claim in §6). |
| 2 | **`FACT_PREDICATES` was modified in a way that smuggles a new, unregistered predicate name, or drops an existing producer** | **Not falsified, and precisely scoped.** `control/facts.py`'s 16-line diff touches exactly 8 existing `PredicateSpec` entries, each adding `"story_facts/v1"` to an already-existing `produced_by` tuple that already had `"attempt_facts/v1"` — no predicate spec's other fields (subject_type, scope_type, abstraction_level, value_type) changed, and no NEW predicate key was added. Independently confirmed the 8 touched keys (`phase_status`, `phase_test_verified`, `attempt_cost_usd`, `attempt_tokens_out`, `attempt_tokens_in`, `attempt_model`, `phase_commit`, `attempt_confidence`) are the exact, complete set of `story_facts.py`'s own `_PRODUCES` tuple — a Python set-equality check confirms it, not a visual scan. |
| 3 | **Token-split instrumentation is not actually additive — an absent split changes existing behavior or serialized shape** | **Not falsified.** Read the full instrumentation diff (`opencode.py`, `story/models.py`, `story/orchestration.py`, `story/persistence.py`) line by line: the new `AgenticResult.usage_reported: bool = False` field defaults to the pre-instrumentation behavior; `SessionResult.tokens: dict|None = None` is optional and `to_dict()` only adds the `"tokens"` key when it is not `None` (an old-format on-disk cell round-trips with zero shape change); `session_token_split()` returns `None` unless `usage_reported` was actually set by a real backend usage event. `load_story_result` defensively defaults a missing/non-dict `tokens` key back to `None`. All four hermetic tests in `test_story.py`'s new coverage (measured-zero vs absent, serialization round-trip) pass. |
| 4 | **`story_facts/v1` does not actually follow `attempt_facts/v1`'s identity + null-not-zero discipline — it diverges in a way that could silently corrupt or duplicate facts** | **Not falsified.** Read both reducers' `_epistemic`/`_EPISTEMIC_BY_PREDICATE` tables side by side: structurally identical (the same two exceptions — `attempt_confidence`→advisory, `phase_test_verified`→verified — everything else `observed`). Both `_fact()` constructors follow the identical pattern (`compute_fact_entity_id` from repo+scope+subject+predicate, `recompute_inputs_digest` from evidence_ids+reducer_version, `fact_id=""` deferred to persistence). Null-not-zero is enforced identically: `attempt_tokens_in`/`out` only emit `if tokens_in is not None` (so a measured `0` emits, an absent key does not — confirmed by `test_measured_zero_split_is_a_real_split_absent_is_not`), and `phase_test_verified` only emits `if is_terminal and isinstance(cell.get("test_executed_success"), bool)` (`None` stays absent, confirmed by `test_phase_test_verified_is_absent_when_cell_verdict_is_none`). |
| 5 | **Hermetic + idempotent tests don't exist, are rubber stamps, or don't actually pass** | **Not falsified.** `tests/test_story_facts_reducer.py` — 14 real tests, all passing (`python3 -m pytest` locally: 78/78 across the full relevant test surface including `test_story.py`, `test_kb_produce_facts_extension.py`, and the repo's dependency/data-flow/classification guards). Specifically exercised: `test_rederivation_is_byte_identical_and_time_invariant` (varies the injected clock, holds identity/knowledge_id fixed — proves the clock is only a fallback, never the value); `test_two_distinct_cells_never_collide_on_attempt_entity_id` (both condition-difference and started_at-difference cases); `test_every_emitted_fact_passes_verify_chain`; `test_producer_story_facts_v1_supersedes_the_projection_slot` (proves the new reducer occupies the SAME logical slot as the old p3 projection and correctly supersedes it rather than coexisting as a conflicted second producer). |
| 6 | **Predicate vocabulary strays outside `FACT_PREDICATES`** | **Not falsified.** `test_story_facts_reducer_is_registered` asserts, for every predicate in `STORY_FACTS_V1.produces`, both that it exists in `FACT_PREDICATES` and that `"story_facts/v1"` is named in its `produced_by` — the literal, load-bearing assertion for this attack vector, not an inferred property. |
| 7 | **The doc's idempotency claim is the same kind of trap I found in the `pattern_minting` branch — true only at mint time, false on any later commit, because the fact's value embeds an ambient current-HEAD revision** | **Not falsified — actively checked, given the sibling branch's real defect.** Traced `_fact()`'s `source_revision=str(session.get("commit_hash") or REVISION_FALLBACK)`: this reducer uses an EVIDENCE-CARRIED value (the session's own recorded `commit_hash`), never the caller-injected `inp.source_revision`/ambient current-HEAD default that broke `pattern/v1`. Separately, `fact_payload()` (`control/fact_ingestion.py`) never includes `source_revision`/`revision` in the hashed content at all — unlike `pattern`'s `PatternPayload`, none of `story_facts/v1`'s eight predicate values (plain scalars: status strings, cost floats, token ints, a bool) embed a revision/timestamp field, so `fact_fingerprint()` is structurally insensitive to revision drift for this reducer. **Verified live, not just by code reading:** ran a safe, non-destructive experiment — copied the real `registry_index.jsonl` to a temp file (never touched the repo's actual file), derived `story_facts/v1` for 5 real story cells against that copy (100 facts, all correctly classified `supersede` against the pre-existing p3-projection records — the documented, intended one-time transition), appended those 100 records' registration lines to the temp copy (simulating what the real `kb-registry-v1` consumer would write), then re-derived the SAME 5 cells again against the now-updated temp registry: **0** records — true convergence, reproduced exactly, with no `--revision` pinning needed (unlike the workaround `pattern/v1` required). |

## Notes for the record

- The full-corpus `python3 scripts/kb_produce_facts.py --reducer story_facts/v1 --dry-run` (no
  cell-count limit) is slow — I started it, it was still computing after ~4 minutes (killed as a
  diagnostic, not a finding against the branch), consistent with `derive_fact_records`'s
  `registry_head()` doing a linear scan of the ~12,000-line `registry_index.jsonl` once per
  candidate fact, and the full story corpus (227 cells × ~5 sessions × up to 8 predicates)
  producing on the order of several thousand candidates. This is a pre-existing property of the
  shared `fact_ingestion.derive_fact_records` machinery (not something this branch's `story_facts.py`
  introduced), and the workflow spec's own VERIFY bar is hermetic fixture tests, not a full-corpus
  timed run — so this is recorded here as an operational observation, not a finding. My smaller,
  isolated, safe 5-cell experiment (above) obtained the same correctness answer in under 7 seconds.
- The doc's §6 evidence table pre-emptively documents the same pre-existing environmental test
  failures/hangs (`test_ollama_analyzer`/`test_opencode_analyzer` hanging on live-LLM subprocesses)
  that I independently ran into and had to kill on the `cap_e2_cascade_run` branch's review — good
  corroborating evidence that this is a known, repo-wide, pre-existing condition and not something
  either branch introduced.
