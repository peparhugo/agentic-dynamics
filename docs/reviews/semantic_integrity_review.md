---
status: accepted
---
# Semantic-Integrity Review — external critique (2026-08-20)

**Provenance [X]:** operator-provided external review of main at `35ef34310` (the merged
refactor-repair release), received 2026-08-20. Retained as the citable input for the
semantic-integrity release. Every load-bearing claim was re-verified against the tree before
authoring the release spec (verification marks in square brackets).

## Verdict

The repair release was addressed seriously and substantially. The repository is now **a
coherent modular monorepo with strong architectural boundaries, but with two remaining trust
problems: the scientific derivation path and the active context supplied to its own agents.**
The top-level architecture is good enough to build on — no further broad restructuring. But
the repair release is not fully complete: source-level gaps remain that the repository's own
verification report does not cover.

## What was successfully fixed

- The eight-plane package architecture is credible; ARCHITECTURE.md is the authority.
- The Control Room uses `PROJECT_ROOT`; the CLI does true longest-prefix resolution with a
  tested command matrix; checkout-only packaging is explicit.
- Artifact identity (`artifact_kind`, `intent`, `repeatable`, `side_effects`) gives the
  compiler a real semantic basis; the status index separates experiment/repeatable-workflow/
  one-shot-workflow.
- Runtime routing and telemetry were dependency-inverted through runtime-owned protocols;
  Control Room and story runtime split into subpackages.
- The agent-surface generator has two renderers with target-specific frontmatter,
  argument reindexing, and schema-oriented tests.
- Recorded verification: 1,286 deterministic tests, 203 architecture/guard tests, 78/78
  specs compiling, Docker build / CLI help / reproduce dry-run passing. (Not independently
  re-executed by the reviewer; we re-ran the suite ourselves.)

## P0 — The active lab pipeline bypasses the canonical data-integrity boundary

The largest remaining issue. `build_data.py` constructs its principal measurement corpus
from current registry rows (correct), but the **lab-book path does not use that boundary**:

- `_results_summary.json` (144 entries, retired) is still committed and still read by
  `lab_basin_topology.py`, `lab_sonar_quality.py`, `lab_claude_audit.py`,
  `lab_correctness_premium.py`, `lab_flail_triggers.py`, `lab_grit_matrix.py`;
  `lab_condition_effects.py` reads raw story JSONL. These are not abandoned historical
  scripts — `reproduce.sh` invokes them and `scripts/CONTEXT.md` presents the lab suite as
  maintained. [verified: 10 labs read `_results_summary.json`; `build_data.py:355` loads
  `lab_grit_matrix.json`, `_load_labs()` at :914 loads all lab JSONs with zero provenance
  checks]
- The website builder loads lab JSONs directly (Grit matrix, general lab outputs) without
  checking source dataset, registry version, tombstone application, manifest match, or
  publication eligibility. Result: a **split publication path** — main metrics canonical,
  lab metrics legacy — so the website can mix canonical and noncanonical findings.
- `tests/test_data_integrity.py` does not guard active lab inputs or publication
  provenance; it would stay green while a lab loaded the retired summary and published.
- **Grit has two meanings**: the README defines
  G(s) = P(test_executed_success | perturbation_strength = s), but `lab_grit_matrix.py`
  classifies correctness×escape quadrants and calls one `high_grit` [verified both].

**Required correction:** classify every lab as
`lab_status: canonical | historical | quarantined` + `publication_eligible: true|false`.
A publication-eligible lab must carry `input_dataset_id`, `input_manifest_sha256`,
`registry_version`, `metric_definition_version`, `data_integrity_policy`,
`requires_external_service`. Enforce: a publication lab may consume only a canonical
exported table or the registry resolver — not `_results_summary.json`, arbitrary result
globs, or unfiltered raw story files; `build_data.py` rejects lab JSON whose embedded
manifest hash does not match the current manifest. Resolve the Grit collision (rename the
quadrant lab or implement the formal metric). Until then, lab-driven website findings are
not canonical.

## P1 — The active agent instructions still describe the old repository

Root instructions were refreshed, but **`agent_config/agents/` and `agent_config/skills/`
were not brought through the same semantic update.** These files are executable context —
generated into `.opencode/`/`.claude/` and directly guiding the systems that modify the
repository. Examples: `instrument-dev` agent still says "AI FinOps Dynamics", flat
`perturb.py`/`opencode.py`/`story.py`, older design-doc locations, pre-plane inventories;
`instrument` skill has old module locations, imports from the deleted package, the old
SEMANTIC/MANIFOLD taxonomy, old `experiments/specs` guidance; `control-room` skill
references `admin/server.py`, `instrument.supervisor`, `instrument.telemetry`; `run-workflow`
skill points at old spec paths and `instrument.story`. [verified: the three skills carry
stale references; `tests/test_stale_path_guard.py` does NOT scan `agent_config/`]
The renderer tests prove format — not that the prose refers to real files, valid imports,
current concepts, or existing commands. The repository now **reliably generates stale
context**.

**Required correction:** extend the guard to the complete `agent_config/**` tree — for
active agent/skill documents validate that referenced paths exist, import examples resolve,
CLI commands map to registered commands, named scripts exist, retired package imports are
absent, retired taxonomy terms are absent (except historical explanations), and hard-coded
module/line counts are removed or generated. Rewrite the specialist agents around the eight
planes. (This is also a CAP prerequisite: a system cannot supply canonical context while its
own committed agent context is stale.)

## P1 — The reproduction container is built, but the full pipeline is not exercised

CI builds the image and dry-runs reproduce.sh but never runs the image's default
reproduction command. Unresolved source issues: `reproduce.sh` unconditionally includes the
Neo4j basin lab [verified: `scripts/reproduce.sh:56-57`]; the Docker image installs the base
package only (no Neo4j optional deps, no Neo4j service); the image does not COPY
`conventions/` (commit analysis loads scoring conventions from there and silently falls
back) [verified: Dockerfile copies zero `conventions/`/`apps/` files]; `--rm` + results mount
means `apps/website/data.js` output is not persisted.

**Required correction:** split `reproduce core` (deterministic, no external services,
canonical registry only) from `reproduce --with-neo4j` / `reproduce --with-sonar`; CI runs
the actual container core command against a small checked-in fixture, not merely the build +
dry-run.

## P1/P2 — The agent configuration is target-specific but not yet semantically neutral

Separate renderers were correct, but the canonical source is still predominantly
OpenCode-shaped; the Claude renderer strips fields, and the tests compare prose, not
effective model/tool/permission behavior. Omission can change actual agent capabilities.

**Required correction:** a neutral intent schema (`role`, `capabilities`:
read_repository/execute_tests/edit_code:confirm/spawn_subagents, `model_class`), with each
renderer mapping intent to its platform and refusing generation when an important
capability cannot be represented. (Sequence this AFTER the lab contract and context
guards — it re-touches the new renderers.)

## P2 — Workflow lifecycle confuses historical failure with current execution

`derive_status` marks a non-repeatable workflow with attempts but no success as `running`
without requiring an active lease, heartbeat, or live worker; old workflows still report
`running` [verified: 6 `running` entries in STATUS.md]. Use `draft | runnable | running
(requires active lease/heartbeat) | failed | blocked | completed | superseded | tombstoned`;
a historical failed run never stays `running` indefinitely.

## P2 — The Control Room composition root is used as a service locator

Routes import `server` inside handlers and read `_server._DUCK` / `_server._DEMO_MODE`
[verified: all 5 route modules import server]. Preserved test-monkeypatch compatibility but
leaves a circular conceptual dependency. Introduce an explicit application context —
`ControlRoomServices` dataclass (telemetry/registry/supervisor/design_sessions) passed into
route registration. A local improvement, not a repository-wide refactor.

## P3 — Hygiene

`ARCHITECTURE.md` describes CAP files as empty placeholders although the files are
intentionally absent; README counts and deployment paths drift; `.scannerwork/` +
`.sonar_lock` remain tracked without `.scannerwork` being ignored; CI dependency/action
versions mostly unpinned. Cleanup items, not blockers.

## Overall diagnosis

No longer a sprawling mess — **clear architectural planes + strong guard coverage +
several stale semantic surfaces + an inconsistent scientific derivation path.** The
remaining problem is not where the code lives; it is **which information is authoritative.**
Before a controller can consume canonical facts, every upstream measurement and every
active agent instruction must have provable canonical lineage. Core website metrics largely
have it; lab outputs do not consistently; root architecture instructions largely reflect
the new system; specialist agent context does not.

## Recommended next release — a semantic-integrity release (not another refactor)

1. Quarantine legacy labs; remove noncanonical labs from default reproduction and website
   publication immediately.
2. Create the canonical lab contract (registry-backed input, manifest identity,
   metric-version identity, publication eligibility).
3. Rebuild derived outputs — every active lab + website dataset from current canonical
   records only.
4. Resolve the Grit collision (rename the quadrant analysis or implement the formal Grit).
5. Rewrite active agent context around the eight-plane architecture.
6. Add semantic context guards (paths, imports, commands, concepts, generated target
   capabilities).
7. Execute the reproduction image in CI (deterministic core pipeline, not only dry-run +
   build).
8. Finish lifecycle backfill (stale running → failed/completed/superseded).

After those items the repository is sufficiently stable to begin the first Context
Abstraction Plane increments without recreating the sprawl or allowing noncanonical
measurements to become "canonical facts."
