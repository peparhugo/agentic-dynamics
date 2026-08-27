---
status: accepted
---

# cap_runner_hardening — adversarial verification

**Role:** adversarial verifier (p5). **Source revision:** `d2d9d9c1c` (p4 integration). The p5
phase fixes two real findings (F1, F3) on the current branch tip; this document covers the
attacks against the hardened runner (p1 watchdog, p2 deploy gate, p3 commit-prefix).

## Findings table

| # | Attack (order) | Result | Disposition |
|---|---|---|---|
| F1 | (1) watchdog bypass — a stalled agent writes junk heartbeats to the session file | **FALSIFIED** | **FIXED**: the stall clock now advances only on MEANINGFUL step events (`_MEANINGFUL_EVENT_TYPES`), not on any write; re-test passes |
| F2 | (1) watchdog — forged `{"type":"step_start"}` heartbeats | accepted limitation | cannot distinguish a forged-but-valid event from a real one at the transcript level (the model's own output channel); measured disease was total silence |
| F3 | (2) deploy gate — `./deploy.sh` / alias / variable that reaches `firebase deploy` without the literal command | **FALSIFIED** | **FIXED**: added the OUTPUT tier — firebase's production-deploy banner in the tool output catches indirection; re-test passes |
| F4 | (2) deploy gate — indirection that surfaces neither the literal command nor the banner in this phase | accepted limitation | shell state across phases is not deterministically resolvable; blast radius bounded (deploy_allowed marker + phase fail + operator stop) |
| F5 | (2) deploy gate — command evasion (different cwd, `&&`/`;` chaining, `npx firebase-tools`, `firebase --help && firebase deploy`, mirror-host flag) | **PASS** | no finding — every form still exposes the firebase command and is caught |
| F6 | (3) commit — wrong phase name, hyphen/double-em-dash/missing-space instead of the literal em-dash | **PASS** | no finding — the validator enforces the phase's OWN name + the exact `—` pattern the resume machinery matches |
| F7 | (3) commit — trailing content after a valid prefix | known-safe | by design: the same `startswith` leniency the resume machinery has; not a bypass of the contract |
| F8 | (4) regression — compliant campaigns + the spec corpus + watchdog overhead | **PASS** | 204-test hardening surface green, 129 specs load with 0 errors, ~1.3 ms/poll overhead |
| F9 | (5) usual suite — secrets / hashes / credentials | **PASS** | no credentials, no secrets, no new hashes on the changed surface |

## F1. Watchdog bypass via junk heartbeats — FIXED

- **Attack:** a stalled agent that writes a non-JSON heartbeat line (`echo "heartbeat" >>
  .instrument/session.jsonl`) or a junk JSON dict (`{"foo":"bar"}`) every ~150 ms while doing
  nothing else. The p1 watchdog polled the transcript's **mtime**, so any write reset the stall
  clock — the agent would never be SIGTERM'd.
- **Evidence:** `test_watchdog_sees_through_a_junk_heartbeat` reproduces exactly that: a fake
  agent writes one real `step_start`, then alternates `heartbeat keep-alive` and `{"foo":"bar"}`
  lines until killed. Before the fix the phase would complete (watchdog fooled); the run shows
  the phase **failed `STALLED`** with `stall_evidence.transcript_tail == "heartbeat keep-alive"`
  and `killed == ["SIGTERM"]`.
- **Fix:** `PhaseWatchdog` now maintains a stall **clock** (`_last_activity`) advanced only by a
  line that parses as a session event whose `type` is in `_MEANINGFUL_EVENT_TYPES`
  (`step_start`/`step_finish`/`message`/`text`/`reasoning`/`tool_use`/`tool`/`file`/`add`/
  `snapshot` — the vocabulary the adapters emit). `_poll_transcript` reads only the bytes
  appended since the last poll (cheap incremental tail, offset reset on truncation), so the
  "cheap mtime poll" overhead is preserved while junk writes no longer count.
- **Re-test:** the full watchdog family passes (stalled → SIGTERM+STALLED; slow-but-stepping →
  never killed; env override; zero disables; agent-only) plus the new heartbeat test.

## F2. Watchdog bypass via forged valid events — accepted limitation

- **Attack:** an agent that writes real-looking `{"type":"step_start"}` / `{"type":"step_finish"}`
  lines every ~200 ms. These are indistinguishable from genuine model-turn boundaries at the
  transcript level.
- **Evidence:** `test_watchdog_cannot_distinguish_a_forged_valid_step` pins the boundary — the
  phase completes normally (the watchdog stays alive).
- **Reasoning:** the transcript is the model's own output channel; the runner cannot tell an
  event the adapter forwarded from the model's stream from one the agent appended itself.
  **Residual risk:** an agent deliberately emitting model-shaped events is outside the measured
  disease (the measured stalls were *total* silence, 45-65 min with no output at all), and the
  phase timeout still bounds the phase. Documented, not fixed.

## F3. Deploy gate indirection via script/alias/variable — FIXED (output tier)

- **Attack:** run the deploy from a script file (`./deploy.sh`) or via an alias/variable defined
  earlier, so THIS phase's bash input contains no `firebase deploy` literal. The p2 gate matched
  only the tool input.
- **Evidence:** `test_deploy_gate_catches_a_deploy_script_by_its_output` — a bash tool_use with
  input `./deploy.sh` and the real revamp2-style output (`=== Deploying to 'ai-finops-rulebook'
  ... ✔ Deploy complete! Hosting URL: https://ai-finops-rulebook.web.app`) → phase **failed
  `DEPLOY_GATE`** with `command == "./deploy.sh"` and pattern `firebase deploy output (Deploy
  complete!)`.
- **Fix:** added `DEPLOY_OUTPUT_PATTERNS` — firebase's production-deploy banner signatures
  (`Deploy complete!`, `hosting[ai-finops-rulebook|agentic-dynamics]`, `Hosting URL:
  https://…web.app`) — scanned from the bash tool's captured output when the command tier did
  not match. A real firebase deploy prints this banner however it was invoked, so the common
  indirection (script, alias, variable) is caught.
- **Re-test:** `test_deploy_gate_evasion_attempts_that_are_caught` (5 command forms) +
  `test_deploy_gate_catches_a_deploy_script_by_its_output` all green.

## F4. Deploy gate indirection that never surfaces — accepted limitation

- **Attack:** an alias/variable defined in an **earlier** phase, or a wrapper that suppresses
  firebase's output, so neither the literal command NOR the banner appears in this phase's
  transcript (`$DEPLOY --only hosting --project agentic-dynamics` with output `ok`).
- **Evidence:** `test_deploy_gate_variable_indirection_without_a_banner_is_a_limitation` pins
  the boundary — `_scan_transcript_for_deploys` returns `[]`.
- **Reasoning:** resolving shell state across phases (aliases, exported variables, sourced
  wrappers) is not deterministically possible from a transcript scan. **Residual risk is
  bounded:** the measured disease was an agent *plainly* running `firebase deploy`; a phase that
  deploys is still caught in the direct/script/alias-with-banner cases, the failed phase stops
  the campaign for the operator, and only `deploy_allowed` phases (a human-authored marker) may
  deploy at all. Documented, not fixed.

## F5. Deploy gate command evasion — PASS (no finding)

- **Attack:** `firebase deploy` from a different working directory; `firebase --help > /dev/null
  && firebase deploy`; `npx firebase-tools deploy`; `true; firebase deploy`; explicit
  `--project agentic-dynamics`. Each still contains the firebase production-deploy token.
- **Evidence:** `test_deploy_gate_evasion_attempts_that_are_caught` asserts every form fails a
  non-deploy phase with `DEPLOY_GATE` and the exact command in the evidence. The `npx
  firebase-tools` form matches because `\bfirebase\b` has a word boundary before `-tools`.
  The workdir is irrelevant — the command string is what is matched.

## F6. Commit-enforcement message evasion — PASS (no finding)

- **Attack:** commit a DIFFERENT phase's name (`[workflow] p3_dom_verification — g` during the
  `scope` phase), a hyphen (`scope - g`), a double em-dash (`scope —— g`), or a missing space
  (`scope —g`).
- **Evidence:** `test_commit_prefix_evasion_attempts_that_are_caught` asserts all are rejected —
  the validator requires group(1) == the phase's OWN name, the literal `—`, and the 40-char goal
  prefix, byte-identical to `_completed_phases`. `[workflow] scope — g` alone passes.

## F7. Commit-enforcement trailing content — known-safe (by design)

- **Attack:** `git commit -m "[workflow] scope — g; rm -rf /"` — trailing content after a valid
  prefix.
- **Evidence:** `test_commit_prefix_trailing_content_after_a_valid_prefix_matches` — it matches.
- **Why safe:** the enforcement's contract is *exactly* the resume machinery's pattern
  (`_completed_phases` uses `startswith(goal_prefix)` on group(2)); a commit that resumes as this
  phase's commit IS this phase's commit by definition. Making the enforcement stricter than the
  pattern it guards would reject commits the resume machinery accepts (a false positive), which
  is worse. Documented.

## F8. Regression — PASS

- The hardening changes nothing for compliant campaigns: `tests/test_workflow_runner.py` +
  `test_streaming.py` + `test_step_routing.py` + `test_context_plane_seam.py` +
  `test_test_runner_wiring.py` + `test_experiment_spec.py` + `test_compile_experiment.py` +
  `test_dependency_direction.py` + adapter suites = **204 passed** (`--timeout=600`); the full
  `tests/` run = **2135 passed**, 9 skipped, only the 7 known pre-existing failures
  (data/publication/doc-lifecycle drift, present on the base commit).
- Spec corpus: **129 workflow/definition YAMLs load with 0 validation errors** (p2's
  `deploy_allowed` type gate included).
- Watchdog overhead: measured ~**1.3 ms per poll** on a 1.3 MB session transcript (a 3-hour
  phase), with each poll reading only the appended bytes — negligible.

## F9. Usual suite — PASS

- Grep of the changed surface (`workflow_runner.py`, `test_workflow_runner.py`) for
  `password=`, `api_key=`, `secret=`, hardcoded tokens → no matches. No new hashes, no
  credentials, nothing committed.

## Verdict

**PASS** — two of the six attack families falsified the hardening (F1 watchdog heartbeat, F3
deploy-gate indirection); both are **fixed** with regression tests and re-tests green. Two
documented, accepted limitations remain (F2 forged-valid events, F4 cross-phase indirection
without a banner), each with explicit residual-risk reasoning. The remaining attacks (F5-F9)
did not falsify.
