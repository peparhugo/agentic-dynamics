---
status: accepted
---

# cap_runner_hardening2 — known-safe list

**Role:** adversarial verifier (p5). Attempted attacks that did **not** falsify the hardening,
with the evidence and why each is safe. The finding table (including the one FIX) lives in
`docs/reviews/cap_runner_hardening2_adversary.md`.

## Known-safe table

| # | Attempted attack | Evidence | Why safe |
|---|---|---|---|
| K1 | (1) orphan — a parent writes a NON-meaningful heartbeat (`compaction`) after the subagent terminates | probe + `test_heartbeat_compaction_after_spawn_does_not_rescue_the_parent`: `flagged == 1` | the sweep's parent-silence arm reads ONLY `MEANINGFUL_STEP_TYPES`; a junk heartbeat is not progress |
| K2 | (1) orphan — a live parent still stepping with a running subagent is flagged | probe + `test_live_parent_still_stepping_with_running_subagent_is_never_flagged` + `test_parent_step_after_spawn_rescues…`: `flagged == 0` | BOTH arms must hold: a parent with any meaningful step after the spawn is never an orphan |
| K3 | (1) orphan — a subagent whose parent is outside the observed set | `test_dangling_parent_is_skipped`: `flagged == 0` | parent silence cannot be verified → skipped (never a fabricated verdict) |
| K4 | (1) orphan — the terra 43.4-min orphan is no longer detected | `test_terra_orphan_is_replayed_and_detected` (spawn 21:11:02Z, completion 21:12:31Z, idle 41.83 min): detected | the replay fixture + pure timestamp rule reproduce the post-mortem detection |
| K5 | (2) relabel — tree-hash spoofing via an EMPTY commit | probe: `git commit --allow-empty` → tree unchanged (`f22dbe99…` == discarded) → the gate still matches and fires RELABEL | the gate compares TREE hashes, not commit hashes; an empty commit changes neither |
| K6 | (2) relabel — an approval committed DURING the phase (post-hoc) | `test_approval_committed_during_the_phase_is_not_an_approval`: `present_at_pre_head == False` → RELABEL | the escape requires the approval to be committed before the phase (present at pre-head) |
| K7 | (2) relabel — approval with a wrong tree / wrong phase / placeholder operator / missing date | `test_approval_authorizes_only_when_all_contract_fields_hold`: each refused with the named failed check | the gate validates all four contract fields independently |
| K8 | (2) relabel — a discarded tree of a DIFFERENT spec/branch | probe: the same tree recorded under another spec is not a match for this spec | the ledger is keyed `(spec, branch, tree_hash)` — cross-scope trees never fire |
| K9 | (2) relabel — an operator restoring a discarded tree WITHOUT the approval artifact | `test_relabel_without_approval_fails_with_identical_tree_proof`: RELABEL fires | the escape is unreachable without the committed approval — failing is the designed behavior, not a false positive |
| K10 | (2) relabel — the runnér's own `_git_commit` of genuine work trips the gate | `test_runner_own_git_commit_of_genuine_work_never_fires`: no gate | the gate is a separate post-phase check; a never-discarded tree never matches |
| K11 | (3) checkpoint — an approval committed on the SAME commit as the checkpoint (descendant not strict) | probe + `test_resume_refuses_approval_committed_at_checkpoint`: `failed == ['authored_after_checkpoint']` | the approval must be ABSENT at the checkpoint commit (authored after it) |
| K12 | (3) checkpoint — an approval for the WRONG phase/spec (artifact naming) | probe: `approvals/<spec>/implement_approval.md` for phase `design` → `failed == ['no_artifact']` | the contract looks only at the canonical `approvals/<spec>/<phase>_approval.md` path — a misplaced approval is not found |
| K13 | (3) checkpoint — a resume re-runs the checkpoint phase instead of honoring it | probe + `test_resume_refuses_without_approval`: `agent_calls == 0`, `phases == []` | the checkpoint's `[workflow] <phase>` commit makes the resume machinery SKIP it; the contract check then refuses before any phase runs |
| K14 | (3) checkpoint — a phase AFTER a checkpoint runs before the awaiting state is recorded (the revamp3 violation exactly) | probe: a 3-phase spec with p2 `checkpoint: true` → `phases == ['design']`, status `awaiting`, p3 NEVER ran | the stop is deterministic: the checkpoint flip happens after the phase commits and all gates, and `break` exits the loop before the next phase |
| K15 | (3) checkpoint — a placeholder signature ("operator", `<required: …>`, "your name", single initial) | `test_approval_contract_validates_signature_identity_and_dates` + the revamp3 template probe: each refused | `_operator_is_placeholder` refuses generic words, angle-bracketed templates, and sub-two-char values |
| K16 | (3) checkpoint — the real revamp3 unsigned template authorizes a resume | `test_revamp3_unsigned_template_is_refused` + `test_revamp3_template_signature_fields_are_placeholders` | the template committed with the work fails `authored_after_checkpoint`; its `SIGNED-BY-OPERATOR: <required: …>` / `DATE: <required: …>` fields are placeholders |
| K17 | (3) checkpoint — a checkpoint phase that FAILS is recorded as awaiting | `test_checkpoint_phase_that_fails_is_not_awaiting`: status `failed`, `awaiting == False` | the designed stop fires only on successful completion |
| K18 | (4) regression — non-checkpoint campaigns / non-agent phases are affected | `test_non_checkpoint_campaigns_are_unaffected` (control_room_portal runs all 4 phases ok, no awaiting) + the deploy/commit gates' `kind != "test"` guards | all three mechanisms are opt-in and agent-phase-only |
