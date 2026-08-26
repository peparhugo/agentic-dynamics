---
status: accepted
---

# cap_stabilization_release — known-safe list (p6 adversarial: attempted non-falsifying attacks)

**Campaign:** `cap_stabilization_release` (`workflows/repository/cap_stabilization_release.yaml`).
This document records the **non-falsifying** attacks attempted during the adversarial pass and why
each is safe. A falsifying attack would have been a FAILED finding in
`docs/reviews/cap_stabilization_release_adversary.md`; none of these falsified the release
readiness.

| # | attempted attack | evidence | why safe |
|---|---|---|---|
| K1 | Find `Any` used-but-unimported again in `scripts/kb_produce_facts.py` | `from typing import Any` at :52; `dict[str, Any]` at :731/:818; `import scripts.kb_produce_facts` clean | The import was added (p1) and the module still imports |
| K2 | Find a duplicate `"arms"` dict key still silently overwriting in `scripts/retro_session_routing.py` | `grep -c '"arms"'` = 1 and `grep -c '"arm_names"'` = 1; the stats dict keeps `arms`, the tuple moved to `arm_names` | No key is overwritten; the re-run output is structurally diff-only-`arm_names` vs the old committed output |
| K3 | Re-run `ruff check .` and find a finding | `All checks passed!` (0 errors), incl. `scripts/archive/` (lint-clean policy, not excluded) | Active surface is lint-clean |
| K4 | Re-run the deterministic suite and find a failure | `2010 passed / 115 deselected / 0 failed`; failure set empty | Suite is green on the branch tip |
| K5 | Parse `pytest.yml` and find lint still gating tests in one job | Jobs = `lint` / `test` / `repro` / `packaging`; lint has its own job; `test` owns tests + integrity gates | A lint failure can no longer hide test results |
| K6 | Read the live branch protection and find a mismatch with `docs/release/branch_protection_settings.md` | `gh api …/protection` → contexts `{lint,test,repro,packaging}`, `strict=true`, `enforce_admins=true`, PR reviews `1` — matches the doc | Protection is applied and the record is truthful |
| K7 | Find README's spec figure ≠ `experiments/specs/index.json` | `test_readme_spec_counts_match_index` passes; README row `125 (11 + 114)` == index `n_specs` 125 | The count reconciles against the authoritative index |
| K8 | Find stale CAP/control language in the authoritative docs | `test_stale_cap_claims_absent_from_authoritative_docs` passes; `grep -rn "emerging" agent_config/` = 0 | The old "reserved-but-empty"/"emerging control" claims are gone from ARCHITECTURE/README/mental-model |
| K9 | Regenerate the instruction surfaces and find drift | `python3 scripts/_gen_instructions.py` twice → `git diff` identical between runs | Regeneration is idempotent (AGENTS.md/.opencode/.claude derive from agent_config) |
| K10 | Find a stale README ↔ data.js `public_statistics` figure | `test_readme_figures_match_public_statistics` passes (7 rows reconstructed from the published block, incl. the relabeled `Story-corpus measured spend` row) | The headline figures mirror the generated dataset |
| K11 | Find a committed secret in the active surface | Active-surface scan (`src/ scripts/ tests/ apps/ workflows/ .github/ agent_config/` + root) → 0 matches for `ghp_*`, `AKIA*`, PEM private keys | No secrets committed |
| K12 | Find a hash mismatch between `experiments/data_manifest.json` and the tree | `canonical_outputs.data.js.sha256` == actual sha256 of `apps/website/data.js` (verified in p6) | The manifest's canonical-output hash is real, not remembered |
| K13 | Find uncommitted artifacts left behind by the release work | `git status` clean except the manifest regeneration committed with this phase; no untracked source files | The release commits everything it generates |
| K14 | Find the p1 null-not-zero guard tests regressed | `tests/test_ratio_null_not_zero.py` passes with `tests/test_strategy.py` (strategy.py `exploration_premium`/`thermal_efficiency` verified `None`, not `0.0`) | The sweep's guard survived the subsequent phases |
| K15 | Re-run `retro_session_routing.py` and find the fix changed stats | Structural diff old→new is exactly `arm_names`; the arms stats differ only via documented corpus growth (gitignored ledgers), asserted in the p1 log | No fix-induced stat change; growth is recorded, not silent |
| K16 | Re-run the FULL suite (with the hang guard) and find a failure that is NOT already fixed | `pytest tests/ -q --timeout=600` → 2116 passed / 9 skipped (documented reasons) / 0 failed; the 2 live-Neo4j `test_versioned_graph.py` failures found by the p3 recheck were fixed (counts scoped to the test's own `repository_id`) and are green here | The suite's only real failures were found and fixed, not waived |
| K17 | Find the archive-policy decision UNDOCUMENTED on the tip | `scripts/CONTEXT.md` carries the `archive lint policy` bullet (restored by `aa1cac2d6`; merge `26eb0e32b` had reverted it out) and `ruff check scripts/archive/` passes | Hard rule 3's decision + reasoning are committed, never implicit |
| K18 | Regenerate the instruction surfaces and find drift | `python3 scripts/_gen_instructions.py` twice → `git status` unchanged between runs (0 modified) | The generated surfaces (AGENTS.md/.opencode/.claude) are idempotent and match agent_config |
