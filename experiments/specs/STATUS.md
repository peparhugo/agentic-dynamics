# Spec status index

**Generated — do not edit by hand.** Regenerate with `python scripts/spec_status.py`;
`scripts/run_workflow.py` also refreshes it at the end of every run.

Generated at: `2026-08-20T22:42:27.486351+00:00`  ·  78 spec(s)
**Work remaining:** 18 runnable-now · 60 completed/retired

| name | kind | repeatable | status | version | supersedes | last_run | ok | model | cost | n_runs |
|---|---|---|---|---|---|---|---|---|---|---|
| `routing_kb_dispatch` | workflow | no | runnable | 0.1 | — | — | — | — | — | 0 |
| `self_recommending_experiment` | workflow | no | runnable | 0.1 | — | — | — | — | — | 0 |
| `agentic_dynamics_rebrand` | workflow | no | running | 0.1 | — | 2026-08-14 22:02 | fail | openai/gpt-5.6-sol | $7.7341 | 2 |
| `claude_background_sessions` | workflow | no | running | 0.1 | — | 2026-08-14 17:38 | fail | anthropic/claude-fable-5 | $15.4471 | 1 |
| `control_room_portal` | workflow | no | running | 0.2 | — | 2026-08-14 03:36 | fail | openai/gpt-5.6-sol | $0.0000 | 3 |
| `design_sessions` | workflow | no | running | 0.1 | — | 2026-08-14 06:58 | fail | openai/gpt-5.6-sol | $0.0000 | 1 |
| `auto_posthoc_wiring` | workflow | yes | active | 0.1 | — | 2026-08-17 16:17 | ok | deepseek/deepseek-v4-pro | $0.1471 | 1 |
| `explanation_tax` | experiment | yes | active | 0.2 | — | — | — | — | — | 0 |
| `labbook_refresh` | workflow | yes | active | 0.1 | — | 2026-08-17 18:14 | ok | deepseek/deepseek-v4-flash | $0.0275 | 1 |
| `posthoc_pipeline` | workflow | yes | active | 0.1 | — | — | — | — | — | 0 |
| `process_perturbation_resample` | experiment | yes | active | 0.1 | — | — | — | — | — | 0 |
| `queue_steer` | workflow | yes | active | 0.1 | — | 2026-08-15 19:32 | ok | deepseek/deepseek-v4-flash | $0.0330 | 1 |
| `rag_bare_vs_augmented` | experiment | yes | active | 0.1 | — | — | — | — | — | 0 |
| `registry_canonicalize` | workflow | yes | active | 0.1 | — | 2026-08-19 13:42 | ok | deepseek/deepseek-v4-pro | $0.1872 | 1 |
| `routing_kb_experiment_design` | experiment | yes | active | 0.1 | — | 2026-08-17 18:28 | ok | openai/gpt-5.6-sol | $3.0669 | 7 |
| `routing_kb_experiment_design_research` | experiment | yes | active | 0.1 | — | 2026-08-17 18:12 | ok | deepseek/deepseek-v4-pro | $0.2203 | 1 |
| `routing_regret_under_degradation` | experiment | yes | active | 0.2 | — | — | — | — | — | 0 |
| `context_abstraction_implement` | workflow | no | draft | 0.1 | — | 2026-08-20 00:56 | fail | anthropic/claude-opus-5 | $0.0000 | 2 |
| `canonical_state_design` | workflow | no | completed | 0.1 | — | 2026-08-18 15:48 | fail | openai/gpt-5.6-sol | $0.0798 | 5 |
| `canonical_state_finalize` | workflow | no | completed | 0.1 | — | 2026-08-18 20:38 | ok | anthropic/claude-fable-5 | $14.5891 | 1 |
| `canonical_state_implement` | workflow | no | completed | 0.1 | — | 2026-08-18 19:51 | ok | anthropic/claude-fable-5 | $51.4204 | 1 |
| `canonical_state_round2` | workflow | no | completed | 0.1 | — | 2026-08-18 17:55 | ok | anthropic/claude-fable-5 | $4.8433 | 2 |
| `claude_tools_to_skills` | workflow | no | completed | 0.1 | — | 2026-08-14 22:29 | ok | anthropic/claude-fable-5 | $8.3582 | 1 |
| `code_review` | workflow | no | completed | 0.1 | — | 2026-08-14 05:38 | ok | anthropic/claude-fable-5 | $2.4257 | 1 |
| `consolidation_release` | workflow | no | completed | 0.1 | — | 2026-08-20 13:10 | ok | deepseek/deepseek-v4-pro | $0.1756 | 1 |
| `consolidation_release_execute` | workflow | no | completed | 0.1 | — | 2026-08-20 17:28 | ok | deepseek/deepseek-v4-pro | $4.7695 | 1 |
| `consolidation_stage_0_architecture_spine` | workflow | no | completed | 0.1 | — | — | — | — | — | 0 |
| `consolidation_stage_1_package_move` | workflow | no | completed | 0.1 | — | — | — | — | — | 0 |
| `consolidation_stage_2_experiments_workflows_split` | workflow | no | completed | 0.1 | — | — | — | — | — | 0 |
| `consolidation_stage_3_cli_classification` | workflow | no | completed | 0.1 | — | — | — | — | — | 0 |
| `consolidation_stage_4_instruction_surfaces` | workflow | no | completed | 0.1 | — | — | — | — | — | 0 |
| `consolidation_stage_5_apps_realignment` | workflow | no | completed | 0.1 | — | — | — | — | — | 0 |
| `consolidation_stage_6_verification_release` | workflow | no | completed | 0.1 | — | — | — | — | — | 0 |
| `context_abstraction_plane` | workflow | no | completed | 0.1 | — | 2026-08-19 23:03 | ok | anthropic/claude-opus-5 | $10.3774 | 1 |
| `control_room_hardening` | workflow | no | completed | 0.1 | — | 2026-08-18 23:56 | ok | deepseek/deepseek-v4-pro | $0.1898 | 1 |
| `control_room_posthoc_visibility` | workflow | no | completed | 0.1 | — | 2026-08-17 15:37 | ok | deepseek/deepseek-v4-pro | $0.2049 | 1 |
| `control_room_ui_implement` | workflow | no | completed | 0.1 | — | 2026-08-19 14:48 | ok | deepseek/deepseek-v4-pro | $0.6086 | 1 |
| `control_room_ui_rebuild` | workflow | no | completed | 0.1 | — | 2026-08-19 16:03 | ok | anthropic/claude-opus-5 | $28.2125 | 1 |
| `control_room_ui_redesign` | workflow | no | completed | 0.1 | — | 2026-08-19 13:53 | ok | deepseek/deepseek-v4-pro | $0.1245 | 1 |
| `control_room_workflow_phase` | workflow | no | completed | 0.1 | — | 2026-08-17 15:44 | ok | deepseek/deepseek-v4-pro | $0.1682 | 1 |
| `deep_architecture_review` | workflow | no | completed | 0.1 | — | 2026-08-18 19:10 | ok | deepseek/deepseek-v4-pro | $0.1319 | 1 |
| `evidence_narrative` | workflow | no | completed | 0.1 | — | 2026-08-14 15:04 | ok | openai/gpt-5.6-sol | $0.0000 | 2 |
| `evidence_redesign` | workflow | no | completed | 0.1 | — | 2026-08-14 19:18 | ok | openai/gpt-5.6-sol | $5.9008 | 3 |
| `fix_review_findings` | workflow | no | completed | 0.1 | — | 2026-08-14 13:48 | ok | deepseek/deepseek-v4-pro | $0.1504 | 1 |
| `framework_facelift` | workflow | no | completed | 0.2 | — | 2026-08-14 15:18 | ok | openai/gpt-5.6-sol | $0.0000 | 1 |
| `kb_event_typing` | workflow | no | completed | 0.1 | — | 2026-08-19 00:38 | ok | deepseek/deepseek-v4-pro | $0.2661 | 1 |
| `kb_lineage_reconcile` | workflow | no | completed | 0.1 | — | 2026-08-19 00:31 | ok | deepseek/deepseek-v4-pro | $0.3715 | 1 |
| `kb_producer_factory` | workflow | no | completed | 0.1 | — | 2026-08-18 23:58 | ok | deepseek/deepseek-v4-pro | $0.4744 | 1 |
| `kb_record_fidelity` | workflow | no | completed | 0.1 | — | 2026-08-18 23:50 | ok | deepseek/deepseek-v4-pro | $0.1662 | 1 |
| `kb_write_path` | workflow | no | completed | 0.1 | — | 2026-08-18 23:48 | ok | deepseek/deepseek-v4-pro | $0.2425 | 1 |
| `measurement_bug_fixes` | workflow | no | completed | 0.1 | — | 2026-08-18 23:39 | ok | deepseek/deepseek-v4-pro | $0.1011 | 1 |
| `opencode_docs_refresh` | workflow | no | completed | 0.1 | — | 2026-08-14 21:33 | ok | anthropic/claude-fable-5 | $23.1829 | 1 |
| `perturbation_operators_fix` | workflow | no | completed | 0.1 | — | 2026-08-15 16:32 | ok | deepseek/deepseek-v4-pro | $0.1822 | 1 |
| `rag_knowledge_base` | workflow | no | completed | 0.1 | — | 2026-08-14 23:37 | ok | openai/gpt-5.6-sol | $5.4215 | 4 |
| `rag_knowledge_base_build` | workflow | no | completed | 0.1 | — | 2026-08-15 00:58 | ok | deepseek/deepseek-v4-pro | $0.7587 | 1 |
| `rag_knowledge_base_reconcile` | workflow | no | completed | 0.1 | — | 2026-08-15 19:31 | ok | deepseek/deepseek-v4-pro | $0.3449 | 1 |
| `rag_knowledge_base_wire` | workflow | no | completed | 0.1 | — | 2026-08-15 16:17 | ok | deepseek/deepseek-v4-pro | $0.3821 | 1 |
| `rag_knowledge_produce` | workflow | no | completed | 0.1 | — | 2026-08-15 20:16 | ok | deepseek/deepseek-v4-pro | $0.3555 | 1 |
| `rag_knowledge_produce_fix` | workflow | no | completed | 0.1 | — | 2026-08-15 21:11 | ok | deepseek/deepseek-v4-pro | $0.3693 | 1 |
| `rag_knowledge_sources` | workflow | no | completed | 0.1 | — | 2026-08-16 01:39 | ok | deepseek/deepseek-v4-pro | $0.7690 | 1 |
| `rag_scope_emit` | workflow | no | completed | 0.1 | — | 2026-08-17 15:28 | ok | deepseek/deepseek-v4-pro | $0.7587 | 1 |
| `rag_seam_split` | workflow | no | completed | 0.1 | — | 2026-08-18 23:44 | ok | deepseek/deepseek-v4-pro | $0.2958 | 1 |
| `refactor_master_plan` | workflow | no | completed | 0.1 | — | 2026-08-20 02:44 | ok | deepseek/deepseek-v4-pro | $0.5423 | 1 |
| `refactor_repair_release` | workflow | no | completed | 0.1 | — | 2026-08-20 22:10 | ok | deepseek/deepseek-v4-pro | $3.5232 | 1 |
| `remediation_data_integrity` | workflow | no | completed | 0.1 | — | 2026-08-15 20:31 | ok | deepseek/deepseek-v4-pro | $0.6293 | 1 |
| `repo_review_fable` | workflow | no | completed | 0.1 | — | 2026-08-18 23:24 | ok | deepseek/deepseek-v4-pro | $0.5659 | 2 |
| `routing_follow_up` | workflow | no | completed | 0.1 | — | 2026-08-14 22:26 | ok | deepseek/deepseek-v4-pro | $0.2511 | 1 |
| `routing_kb_more_itertools` | workflow | no | completed | 0.1 | — | 2026-08-17 18:38 | ok | deepseek/deepseek-v4-pro | $0.0337 | 1 |
| `routing_kb_wiring` | workflow | no | completed | 0.1 | — | 2026-08-17 19:52 | ok | deepseek/deepseek-v4-pro | $1.3789 | 1 |
| `site_golden_circle` | workflow | no | completed | 0.1 | — | 2026-08-14 07:36 | ok | openai/gpt-5.6-sol | $0.0000 | 1 |
| `spec_lifecycle` | workflow | no | completed | 0.1 | — | 2026-08-19 22:53 | ok | deepseek/deepseek-v4-pro | $0.4710 | 2 |
| `supervisor_control_room` | workflow | no | completed | 0.1 | — | 2026-08-14 16:09 | ok | openai/gpt-5.6-sol | $10.8221 | 2 |
| `task_vocabulary_unify` | workflow | no | completed | 0.1 | — | 2026-08-18 23:41 | ok | deepseek/deepseek-v4-pro | $0.1428 | 1 |
| `website_data_pipeline` | workflow | no | completed | 0.1 | — | 2026-08-17 20:08 | ok | deepseek/deepseek-v4-pro | $0.1364 | 1 |
| `website_registry_repoint` | workflow | no | completed | 0.1 | — | 2026-08-19 22:26 | ok | deepseek/deepseek-v4-pro | $0.3542 | 1 |
| `website_repoint` | workflow | no | completed | 0.1 | — | 2026-08-19 23:08 | ok | deepseek/deepseek-v4-pro | $0.3304 | 2 |
| `website_rewrite` | workflow | no | completed | 0.3 | — | 2026-08-17 21:00 | ok | openai/gpt-5.6-sol | $12.6287 | 3 |
| `workflow_step_routing` | workflow | no | completed | 0.2 | — | 2026-08-14 21:45 | ok | deepseek/deepseek-v4-pro | $0.0796 | 1 |

## Legend

**Status** — authored in the spec YAML's `status:` when the operator asserted one,
otherwise derived: `superseded` when the spec names a `superseded_by:`; for a
non-repeatable workflow, `completed` when a run succeeded, `running` when runs exist
but none succeeded, `runnable` when never run; else `active`.

| status | meaning |
|---|---|
| `runnable` | a non-repeatable workflow never run successfully — ready to run |
| `running` | a non-repeatable workflow that has been run but not yet completed |
| `active` | the current repeatable spec for its question — runnable now |
| `draft` | authored, not yet run to completion; not yet a claim about anything |
| `completed` | a non-repeatable workflow whose run succeeded (derived from the run ledgers) |
| `superseded` | a later spec took over its question (see that spec's `supersedes` column) |
| `tombstoned` | retired; kept for lineage, never to be run again |

**Columns**

| column | derivation |
|---|---|
| `name` / `version` | the spec YAML's `name:` / `version:` |
| `kind` | the spec YAML's `artifact_kind:` — `experiment` or `workflow` |
| `repeatable` | the spec YAML's `repeatable:` — `yes` (re-runnable) or `no` (one-shot) |
| `supersedes` | spec name(s) this spec replaces, from the YAML's `supersedes:` |
| `last_run` | latest run ledger's `ended_at` (UTC), over `experiments/results/workflows/<name>/*.json` |
| `ok` | that latest run's `ok` — every phase succeeded (`ok`) or at least one failed (`fail`) |
| `model` / `cost` | that latest run's `model` and `total_cost_usd` |
| `n_runs` | how many run ledgers exist for the spec in this checkout |

`—` means **no evidence**, not failure — the run-ledger directory
(`experiments/results/workflows/`) is untracked, so a fresh checkout shows an em-dash
for every run-derived column. The machine-readable form of this table, including
`results_pointer` (path to the latest run ledger), is `index.json` beside this file.
