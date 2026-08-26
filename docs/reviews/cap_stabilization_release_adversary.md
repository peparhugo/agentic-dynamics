---
status: accepted
---

# cap_stabilization_release — adversarial review (p6)

**Campaign:** `cap_stabilization_release` (`workflows/repository/cap_stabilization_release.yaml`)
· **Branch:** `feature/cap-stabilization-release` · **Model:** `deepseek/deepseek-v4-flash`
(operator's explicit choice, all phases) · **Attacker role:** adversarial release verifier,
attacking in the p6 order; a deviation that breaks a claimed green gate is a FAILED finding,
not a limitation.

## Attack 1 — The two verified defects are GONE

**Attack:** re-grep the exact pre-fix patterns: `Any` used but never imported in
`scripts/kb_produce_facts.py`; the duplicate `"arms"` dict key at `retro_session_routing.py`
(old :164/:171) silently overwriting the first entry. The re-run outputs must both be committed.

**Evidence:**
- `scripts/kb_produce_facts.py:52` — `from typing import Any` present; `Any` used at :731 and
  :818. `python3 -c "import scripts.kb_produce_facts"` → clean. Defect gone.
- `scripts/retro_session_routing.py:164` `"arm_names": list(ARMS)` and `:171` `"arms": stats` —
  the stats dict keeps the `arms` name (every consumer cites `arms.<arm>.cpvo.value`), the
  tuple moved to `arm_names`; nothing is overwritten. `grep -c '"arms"'` = 1, `grep -c '"arm_names"'` = 1.
- Both stored outputs committed (hard rule 4): old `1547f19fa`, new `3ffa50fe3` — the old is
  never deleted. Structural diff between the two committed files re-verified in this pass:
  `set(new) - set(old) == {"arm_names"}` — the ONLY added key. The arms stats differ solely via
  documented corpus growth (fork_cached n 246→349, escalate n 7→13; the ledgers are gitignored
  local-transient, so no live corpus reproduces the old snapshot — growth is documented in the p1
  log, not silent).

**Result: PASS.** No FAILED finding; no silent history rewrite.

## Attack 2 — ruff clean on the active surface (p2 command re-run)

**Attack:** re-run the p2 verification command and confirm 0 findings.

**Evidence:** `python3 -m ruff check .` → `All checks passed!` (0 errors, whole active surface
incl. `scripts/archive/` — the archive policy is **lint-clean, not excluded**, decided and
documented in `scripts/CONTEXT.md`; no per-file-ignores carve-out). `ruff check scripts/kb_produce_facts.py scripts/retro_session_routing.py` → clean.
Note: the p2-recheck commit `aa1cac2d6` restored the archive-policy note that merge `26eb0e32b`
had silently reverted out of `scripts/CONTEXT.md` mid-campaign — the decision is now documented on
the tip, satisfying hard rule 3 (documented, never implicit).

**Result: PASS.**

## Attack 3 — Full suite green on the branch (counts vs p3 log)

**Attack:** re-run the p3 gates and compare counts to the committed p3 log
(`experiments/results/workflows/cap_stabilization_release/p3_gate_evidence.json`).

**Evidence (re-run live in this pass):**
- **FULL suite** `pytest tests/ -q --timeout=600` → **2116 passed / 9 skipped / 0 failed**
  (372.92s, hang guard active). The 9 skips are documented reasons: 8× Chroma heartbeat-skips
  (`Chroma server unavailable (heartbeat failed) — live-server tests skip, never hang`) + 1×
  data-dependent skip (`No wasteful entries available`). Ollama/Neo4j/Sonar ran and passed.
- **Deterministic** `pytest tests/ -m "not external" -q --timeout=600` → **2010 passed / 115
  deselected / 0 failed** — matches the p3 log's `rerun_on_tip` block (the +3 vs the original
  2007 log are the p5 doc-lifecycle guards; not a regression).
- The p3 recheck (`0fa3f699b`) found + fixed **2 real failures** on the full suite — a
  test-isolation defect in the live-Neo4j `test_versioned_graph.py` (global `count(*)` colliding
  with real campaign ingestion: 29,675 SymbolVersion nodes, 469 SUPERSEDES edges). Fix: the count
  assertions are scoped to the test's own `repository_id`. Re-test: `test_versioned_graph.py`
  9 passed; full suite re-run green.
- `python3 scripts/build_data.py --dry-run` → OK. `python3 scripts/sync_data.py --check` → OK
  (parquet matches canonical source). Import gate (`import agentic_dynamics`) → OK.

**Result: PASS.** Counts match the p3 log; the two full-suite failures were found by the p3
recheck and are FIXED (not accepted limitations).

## Attack 4 — CI restructure + branch protection

**Attack:** confirm the workflow splits lint/test/repro/packaging into independent required jobs
(a lint failure can never hide test results again) and that the live branch protection matches
the review's requirements (or the spec doc is honest about not-applied).

**Evidence:**
- `.github/workflows/pytest.yml` jobs: `lint` (`ruff check .`), `test` (deterministic suite +
  `build_data --dry-run` + `sync_data --check` + import gate), `repro`, `packaging`. Before:
  one `test` job ran lint BEFORE tests (the P0 failure mode). YAML parses (4 jobs).
- **Live protection (applied, not merely spec'd):** `gh api …/branches/main/protection` →
  required checks `{lint, test, repro, packaging}`, `strict=true` (up-to-date branches),
  `enforce_admins=true`, `required_pull_request_reviews=1` (PR-only, dismiss stale). The durable
  record `docs/release/branch_protection_settings.md` matches the live state exactly.

**Result: PASS.**

## Attack 5 — DOCS: no stale language; README == index; surfaces regenerated + drift-free

**Attack:** re-grep the authoritative docs for the stale claims the review flagged; reconcile
README's spec figure against the generated index; confirm the generated surfaces are regenerated
and idempotent.

**Evidence:**
- Stale-language guard (`test_stale_cap_claims_absent_from_authoritative_docs`) passes against
  ARCHITECTURE.md / README.md / agent_config/mental-model.md (the 10 CAP modules all exist under
  `src/agentic_dynamics/control/`). `grep -rn "emerging" agent_config/` → 0. ARCHITECTURE.md's
  `## 4. Implemented vs proposed` "Reserved-but-empty" section is now the per-module
  **implementation-status map** (design commitment → implemented module → consumption state →
  gate → limitation; consumption cites cap_2a_rerun2/3, cap_2b, cap_escalation_measurement,
  cap_session_routing_*).
- README spec count guard (`test_readme_spec_counts_match_index`) passes: README row =
  `125 (11 experiments + 114 workflows)` = `experiments/specs/index.json` `n_specs` (125;
  artifact_kind split 11 experiments / 114 workflows). data.js `public_statistics` regenerated to
  match (113→114) and now carries `measured_spend_scope: story-corpus`.
- `python3 scripts/_gen_instructions.py` re-run twice → `git diff` unchanged between runs
  (drift-free); `.opencode/instructions/mental-model.md` + `.claude/rules/mental-model.md` carry
  the refreshed control-plane row.

**Result: PASS.**

## Attack 6 — Guard tests fail-on-old / pass-on-new (re-proven)

**Attack:** re-prove both directions of the p5 guards in this pass, not just cite the p5 log.

**Evidence (re-run in this pass):**
- FAIL-old: temporarily restoring the stale README row `124 (11 experiments + 113 workflows)` →
  `test_readme_spec_counts_match_index` FAILED (`AssertionError`); restoring the legacy
  `### Reserved-but-empty …` heading + `emerging control` row →
  `test_stale_cap_claims_absent_from_authoritative_docs` FAILED (`AssertionError`). Both reverted.
- PASS-new: `python3 -m pytest tests/test_doc_lifecycle.py` → **8 passed** (5 pre-existing + 3 new).

**Result: PASS.** The guards fail on the old text and pass on the new — both directions live.

## Attack 7 — Usual suite: secrets, uncommitted artifacts, hashes

**Attack:** scan the active surface for committed secrets, confirm no uncommitted artifacts,
confirm the manifest's data.js hash is real.

**Evidence:**
- Active-surface secret scan (`src/ scripts/ tests/ apps/ workflows/ .github/ agent_config/` +
  root files): zero matches for `ghp_*`, `AKIA*`, PEM private keys.
- `git status`: only `experiments/data_manifest.json` modified (this phase's manifest
  regeneration); no untracked source artifacts.
- `experiments/data_manifest.json` regenerated: `canonical_outputs.data.js.sha256` =
  `4432ee0c95a7…` **equals** the actual sha256 of `apps/website/data.js` (verified in this pass).
  `registry`: 12,152 entities compacted.

**Result: PASS.**

## Accepted limitations (no FAILED findings)

The only real failures found in this release's verification were the two live-Neo4j
`test_versioned_graph.py` isolation defects on the FIRST full-suite run — root-caused and FIXED in
the p3 recheck (`0fa3f699b`, scoped counts), then re-verified green here. They are findings with
fixes, not accepted limitations.

| # | Limitation | Reasoning | Residual risk |
|---|---|---|---|
| L1 | The fix-isolation diff of the retro re-run cannot be re-run against the same corpus today | The workflow-run ledgers are gitignored/local-transient; the old snapshot (253 obs) has no live corpus. The structural diff (only `arm_names` added) was verified in this pass against the two committed files, and p1 verified stats-byte-identical against a live corpus at p1 time | Low — no silent overwrite is possible (the fix removed the duplicate key); the growth delta is documented |
| L2 | `actuation_ingestion` has zero call sites; `--cap-shadow` decisions are recorded, never applied | By design (shadow mode; cap_2b adaptive is the single applied path). Not a regression — the fact plane is what the release stabilizes | None for this release's scope |
| L3 | Whole-repo spend is not published (workflow ledgers gitignored) | The spend figure is explicitly **story-corpus scoped** (label + note + `measured_spend_scope` in data.js) | Low — a reader ignoring the scope label could misread the figure; the label is now in the published dataset, not only prose |

## Re-stated release readiness

**READY.** All seven attacks PASS; zero FAILED findings; three accepted limitations, each with
reasoning and residual risk, none blocking. The two real failures surfaced by the full-suite run
were fixed, not waived. The branch carries the two fixes, a ruff-clean active surface with the
archive-policy decision documented on the tip, a green FULL suite (2116/9/0) and deterministic
suite (2010/0), a four-job independent CI with applied branch protection, canonical docs with
both-direction guards, and regenerated, drift-free instruction surfaces.
