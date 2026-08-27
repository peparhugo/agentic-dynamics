---
status: accepted
---

# cap_runner_hardening — known-safe attacks

**Role:** adversarial verifier (p5). **Source revision:** `d2d9d9c1c` (p4 integration).

This companion file records the non-falsifying attacks that were attempted against the three
runner hardenings — what was tried, the evidence, and why each attempt did not falsify them.
The two attacks that DID falsify the hardening (watchdog junk-heartbeat bypass, deploy-gate
script indirection) are fixed and documented in the companion `cap_runner_hardening_adversary.md`.

## Attempted attacks and why they did not falsify

### K1. Watchdog — "a slow but genuinely working agent is killed" — not supported
- **Tried:** a fake agent writing a real `step_start` event every 300 ms (well under the 1.8 s
  test threshold) for the whole phase.
- **Evidence:** `test_watchdog_never_kills_a_compliant_agent` — the phase completes `ok`, the
  kill seam is never invoked (`killed == []`), `stall_evidence is None`. The stall clock counts
  step activity, not wall time.
- **Why safe:** the watchdog fires only on a step *gap* past the threshold (default 20 min,
  above any legitimately observed gap of ~10 min); continuous steps — even slow ones — keep the
  phase alive indefinitely.

### K2. Watchdog — "the phase legitimately runs long, so it misfires" — not supported
- **Tried:** reasoning that a multi-hour compliant phase (continuous steps) would trip the
  watchdog because it is long.
- **Evidence:** the stall clock is the last-step age, never the phase wall clock; a 3-hour phase
  with continuous steps never stalls. Measured overhead of the poll itself: ~1.3 ms/poll on a
  1.3 MB transcript (the p5 regression evidence in the adversary doc).
- **Why safe:** only a step *gap* — not duration — trips the watchdog.

### K3. Deploy gate — "a benign command that mentions firebase is a false positive" — not supported
- **Tried:** bash tool inputs that mention firebase but are not a production deploy (e.g.
  `python scripts/build_data.py`, `firebase --help`, reading a firebase config).
- **Evidence:** `test_deploy_gate_not_triggered_by_clean_phases_or_test_phases` — clean
  commands pass; the gate matches only the deploy patterns in bash tool inputs (never skill
  content, prose, or file contents). The output tier matches only firebase's deploy banner, not
  the word "firebase".
- **Why safe:** the gate's vocabulary is the deploy command + the deploy banner, both
  production-specific.

### K4. Deploy gate — "the gate blocks a legitimate deploy phase" — not supported
- **Tried:** a phase that IS meant to deploy.
- **Evidence:** `test_deploy_gate_passes_a_deploy_allowed_phase` — the same revamp2 command in
  a phase marked `deploy_allowed: true` passes; the marker is the phase's own opt-in.
- **Why safe:** the gate is not a blanket block; it confines deploys to explicitly marked phases.

### K5. Deploy gate — "a different working directory escapes the scan" — not supported
- **Tried:** `firebase deploy --only hosting` with `"workdir": "/somewhere/else"`.
- **Evidence:** `test_deploy_gate_evasion_attempts_that_are_caught` — the command string is what
  is matched; the workdir is irrelevant, the phase fails `DEPLOY_GATE`.
- **Why safe:** the gate scans the command the agent issued, wherever it ran it.

### K6. Commit enforcement — "a legitimately-matching commit is rejected" — not supported
- **Tried:** the runner's own commit shape `[workflow] <phase> — <goal>` (including the goal
  prefix truncated at 40 chars) and commits with a `(done, extra)` suffix.
- **Evidence:** `test_commit_prefix_passes_a_matching_commit` and
  `test_commit_prefix_trailing_content_after_a_valid_prefix_matches` — both pass; the end-to-end
  revamp2 replay accepts the phase's own `[workflow] p1_implement_inventory — Deliver the
  site's IMPLEMENTED visual system:` commit.
- **Why safe:** the enforcement is byte-identical to the resume machinery's pattern, so anything
  the resume would treat as the phase's commit is accepted.

### K7. Commit enforcement — "the adapter's own Initial commit is rejected" — not supported
- **Tried:** a fresh worktree where the adapter's `_init_git_workdir` creates its `Initial`
  commit (runner identity) during the phase.
- **Evidence:** `test_commit_prefix_exempts_the_adapters_initial_commit` (the p4 integration
  fix) — the init commit is exempted narrowly (subject `Initial` + `RUNNER_INIT_AUTHOR_EMAIL`),
  while a plain-message commit under the same forged identity is still rejected.
- **Why safe:** the exemption is scoped to the runner's own execution-layer artifact, never to
  manual agent commits.

### K8. Regression — "the hardening changes compliant campaign behavior" — not supported
- **Tried:** running the full hardening test surface and the spec corpus after all fixes.
- **Evidence:** 204 tests green on the hardening surface; full `tests/` = 2135 passed with only
  the 7 known pre-existing failures (unrelated data/publication drift on the base commit); all
  129 spec YAMLs load and validate unchanged; the p4 live CLI smoke (real flash model) completed
  both phases `ok` with all three gates `null`.
- **Why safe:** the three gates are fail-on-violation, silent-when-clean; compliant phases carry
  no new evidence fields and no new failure paths.

### K9. Usual suite — "the change leaks secrets / hashes / credentials" — not supported
- **Tried:** grepping the changed surface for `password=`, `api_key=`, `secret=`, hardcoded
  tokens and checking the committed diff for added hashes.
- **Evidence:** no matches; the diff adds only pattern regexes, clock/scan logic, tests, and
  docs — nothing secret and nothing credential-shaped.
- **Why safe:** no new configuration, no new I/O beyond the transcript read (already present),
  and no new environment access.

## Verdict

Seven attack families and two hygiene checks attempted; **none** falsified the hardened runner
beyond the two already-fixed findings (watchdog junk-heartbeat, deploy-gate script indirection —
see the adversary doc). The known-safe list is the honest boundary of what was tried and why it
held.
