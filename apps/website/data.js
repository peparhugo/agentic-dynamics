/* Generated 2026-08-21 21:50:38 UTC by build_data.py */
/* DO NOT EDIT — regenerate with: python scripts/build_data.py */
window.DYNAMICS_DATA = {
  "_meta": {
    "generated_at": "2026-08-21T21:50:36.833236+00:00",
    "provenance_note": "All values tagged [M]easured, [C]omputed, [H]euristic, or e[X]ternal. See methodology.html."
  },
  "summary": {
    "worktrees_total": 205,
    "sessions_total": 1067,
    "game_reports": 344,
    "total_cost": 309.1685,
    "architectures": 3,
    "variants": 7,
    "stories_total": 215,
    "stories_unique": 150,
    "stories_re_runs": 65,
    "story_sessions": 1067,
    "story_total_cost": 309.1685,
    "configs": 35,
    "registry_current_records": 215,
    "resolved_measurement_payloads": 215,
    "eligible_records": 215,
    "records_used": 215,
    "unresolved_waivered": 0,
    "canonical_findings": 64,
    "tombstoned_excluded": 87,
    "_provenance": {
      "worktrees_total": "M",
      "sessions_total": "M",
      "game_reports": "M",
      "total_cost": "M",
      "architectures": "M",
      "variants": "M",
      "stories_total": "C",
      "stories_unique": "C",
      "stories_re_runs": "C",
      "story_sessions": "C",
      "story_total_cost": "C",
      "configs": "M",
      "registry_current_records": "M",
      "resolved_measurement_payloads": "M",
      "eligible_records": "C",
      "records_used": "C",
      "unresolved_waivered": "M",
      "canonical_findings": "M",
      "tombstoned_excluded": "M"
    }
  },
  "resolution_report": {
    "expected_current": 521,
    "resolved": 521,
    "missing": 0,
    "unreadable": 0,
    "ambiguous": 0,
    "duplicate": 0,
    "waivers": []
  },
  "publication_contract": {
    "registry_identity": "688d7b949481fb8775976eec5eef9c8fe9fcd59b8b21f9a02cd61a3108b2dd05",
    "resolved_input_identity": "077f95acc9fdb7e40a132aa89c5c27c4d48eba4ba3582dc2028234723ecf7534",
    "data_integrity_policy_version": "data-integrity/v1",
    "normalization_version": "canonical-projection/v2",
    "waiver_digest": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "generator_source_tree_identity": "9a460623a3472a8225288e5d5c1e8dc2be0234cd8d215dc3e4539d344bf9f88f"
  },
  "public_statistics": {
    "story_sessions": 1067,
    "stories_total": 215,
    "story_total_cost": 309.1685,
    "db_sessions_total": 3370,
    "game_reports": 344,
    "model_variants": 7,
    "providers": 3,
    "experiment_configs": 35,
    "experiment_specs": 6,
    "workflow_specs": 75,
    "perturbation_operators": 10,
    "lab_books": 20,
    "lab_books_canonical": 8,
    "lab_books_quarantined": 12,
    "measured_spend_usd": 309.17,
    "_provenance": {
      "story_sessions": "M",
      "stories_total": "C",
      "story_total_cost": "C",
      "db_sessions_total": "M",
      "game_reports": "M",
      "model_variants": "M",
      "providers": "M",
      "experiment_configs": "M",
      "experiment_specs": "M",
      "workflow_specs": "M",
      "perturbation_operators": "M",
      "lab_books": "M",
      "lab_books_canonical": "M",
      "lab_books_quarantined": "M",
      "measured_spend_usd": "M"
    }
  },
  "models": [
    {
      "id": "deepseek/deepseek-v4-flash",
      "label": "DeepSeek v4 Flash",
      "provider": "deepseek",
      "cells": 31,
      "unique_cells": 21,
      "re_runs": 10,
      "sessions": 155,
      "total_cost": 2.308294,
      "avg_cost": 0.074461,
      "cost_cells": 31,
      "avg_captured_cost": 0.074461,
      "cost_captured_cells": 31,
      "total_cells": 31,
      "cost_coverage": 1.0,
      "avg_cache_hit": 0.964,
      "avg_tests": 52.4,
      "avg_test_code_ratio": 0.666,
      "avg_tok_per_session": 50036.0,
      "avg_duration_s": 1401.0,
      "avg_code_lines": 991.0,
      "final_tests_discovered": 1623,
      "test_executions_passed": 3290,
      "test_executions_run": 3292,
      "pass_rate": "100% (3290/3292)",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 0.014892,
      "avg_loc": 991.0,
      "avg_energy_j": 54395.2,
      "avg_energy_j_per_loc": 54.89,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 22,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 31,
      "reports_valid": 31,
      "reports_narrated": 0
    },
    {
      "id": "openai/gpt-5.6-luna",
      "label": "GPT-5.6 Luna",
      "provider": "openai",
      "cells": 34,
      "unique_cells": 23,
      "re_runs": 11,
      "sessions": 170,
      "total_cost": 3.180633,
      "avg_cost": 0.093548,
      "cost_cells": 34,
      "avg_captured_cost": 0.093548,
      "cost_captured_cells": 34,
      "total_cells": 34,
      "cost_coverage": 1.0,
      "avg_cache_hit": 0.937,
      "avg_tests": 14.3,
      "avg_test_code_ratio": 0.275,
      "avg_tok_per_session": 17957.0,
      "avg_duration_s": 658.0,
      "avg_code_lines": 697.0,
      "final_tests_discovered": 486,
      "test_executions_passed": 858,
      "test_executions_run": 858,
      "pass_rate": "100% (858/858)",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 0.01871,
      "avg_loc": 697.0,
      "avg_energy_j": 14130.0,
      "avg_energy_j_per_loc": 20.27,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 24,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 34,
      "reports_valid": 34,
      "reports_narrated": 0
    },
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "provider": "deepseek",
      "cells": 39,
      "unique_cells": 24,
      "re_runs": 15,
      "sessions": 187,
      "total_cost": 6.314403,
      "avg_cost": 0.161908,
      "cost_cells": 39,
      "avg_captured_cost": 0.161908,
      "cost_captured_cells": 39,
      "total_cells": 39,
      "cost_coverage": 1.0,
      "avg_cache_hit": 0.801,
      "avg_tests": 44.6,
      "avg_test_code_ratio": 0.798,
      "avg_tok_per_session": 38647.0,
      "avg_duration_s": 1766.0,
      "avg_code_lines": 879.0,
      "final_tests_discovered": 1739,
      "test_executions_passed": 3144,
      "test_executions_run": 3145,
      "pass_rate": "100% (3144/3145)",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 0.033767,
      "avg_loc": 879.0,
      "avg_energy_j": 39819.6,
      "avg_energy_j_per_loc": 45.3,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 37,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 39,
      "reports_valid": 39,
      "reports_narrated": 0
    },
    {
      "id": "openai/gpt-5.6-terra",
      "label": "openai/gpt-5.6-terra",
      "provider": "openai",
      "cells": 30,
      "unique_cells": 22,
      "re_runs": 8,
      "sessions": 150,
      "total_cost": 31.329782,
      "avg_cost": 1.044326,
      "cost_cells": 30,
      "avg_captured_cost": 1.044326,
      "cost_captured_cells": 30,
      "total_cells": 30,
      "cost_coverage": 1.0,
      "avg_cache_hit": 0.832,
      "avg_tests": 15.3,
      "avg_test_code_ratio": 0.337,
      "avg_tok_per_session": 31804.0,
      "avg_duration_s": 785.0,
      "avg_code_lines": 566.0,
      "final_tests_discovered": 458,
      "test_executions_passed": 1060,
      "test_executions_run": 1060,
      "pass_rate": "100% (1060/1060)",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 0.208865,
      "avg_loc": 566.0,
      "avg_energy_j": 18681.4,
      "avg_energy_j_per_loc": 33.01,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 20,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 30,
      "reports_valid": 30,
      "reports_narrated": 0
    },
    {
      "id": "anthropic/claude-haiku-4-5",
      "label": "anthropic/claude-haiku-4-5",
      "provider": "anthropic",
      "cells": 24,
      "unique_cells": 20,
      "re_runs": 4,
      "sessions": 120,
      "total_cost": 32.616808,
      "avg_cost": 1.63084,
      "cost_cells": 20,
      "avg_captured_cost": 1.63084,
      "cost_captured_cells": 20,
      "total_cells": 24,
      "cost_coverage": 0.8333,
      "avg_cache_hit": 0.824,
      "avg_tests": 127.9,
      "avg_test_code_ratio": 1.221,
      "avg_tok_per_session": 13581.0,
      "avg_duration_s": 862.0,
      "avg_code_lines": 1484.0,
      "final_tests_discovered": 3069,
      "test_executions_passed": 0,
      "test_executions_run": 0,
      "pass_rate": "unknown",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 0.326168,
      "avg_loc": 1484.0,
      "avg_energy_j": 15438.9,
      "avg_energy_j_per_loc": 10.4,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 2,
      "strategy_expl": 12,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 24,
      "reports_valid": 24,
      "reports_narrated": 0
    },
    {
      "id": "openai/gpt-5.6-sol",
      "label": "openai/gpt-5.6-sol",
      "provider": "openai",
      "cells": 30,
      "unique_cells": 19,
      "re_runs": 11,
      "sessions": 150,
      "total_cost": 114.52382,
      "avg_cost": 3.817461,
      "cost_cells": 30,
      "avg_captured_cost": 3.817461,
      "cost_captured_cells": 30,
      "total_cells": 30,
      "cost_coverage": 1.0,
      "avg_cache_hit": 0.85,
      "avg_tests": 23.6,
      "avg_test_code_ratio": 0.447,
      "avg_tok_per_session": 46636.0,
      "avg_duration_s": 1146.0,
      "avg_code_lines": 739.0,
      "final_tests_discovered": 708,
      "test_executions_passed": 1953,
      "test_executions_run": 1953,
      "pass_rate": "100% (1953/1953)",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 0.763492,
      "avg_loc": 739.0,
      "avg_energy_j": 27822.1,
      "avg_energy_j_per_loc": 37.65,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 23,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 30,
      "reports_valid": 30,
      "reports_narrated": 0
    },
    {
      "id": "anthropic/claude-sonnet-5",
      "label": "Claude Sonnet 5",
      "provider": "anthropic",
      "cells": 27,
      "unique_cells": 21,
      "re_runs": 6,
      "sessions": 135,
      "total_cost": 118.894751,
      "avg_cost": 5.169337,
      "cost_cells": 23,
      "avg_captured_cost": 5.169337,
      "cost_captured_cells": 23,
      "total_cells": 27,
      "cost_coverage": 0.8519,
      "avg_cache_hit": 0.84,
      "avg_tests": 117.1,
      "avg_test_code_ratio": 0.695,
      "avg_tok_per_session": 18404.0,
      "avg_duration_s": 1062.0,
      "avg_code_lines": 1761.0,
      "final_tests_discovered": 3163,
      "test_executions_passed": 455,
      "test_executions_run": 455,
      "pass_rate": "100% (455/455)",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 1.033867,
      "avg_loc": 1761.0,
      "avg_energy_j": 21095.0,
      "avg_energy_j_per_loc": 11.98,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 2,
      "strategy_expl": 14,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 27,
      "reports_valid": 27,
      "reports_narrated": 0
    }
  ],
  "perturbation_models": [
    {
      "id": "anthropic/claude-haiku-4-5",
      "label": "anthropic/claude-haiku-4-5",
      "provider": "anthropic",
      "reports": 7,
      "reports_valid": 7,
      "reports_narrated": 0,
      "n_reports": 7,
      "n_valid": 7,
      "n_narrated": 0,
      "avg_cost": 0.0442,
      "total_cost": 0.3097,
      "cost_ci95": [
        0.0,
        0.1327
      ],
      "pass_rate": null,
      "strategy_cons": 0,
      "strategy_expl": 6,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 1270,
      "avg_thinking_ratio": 0.0,
      "avg_escape": 0.66,
      "avg_arch_divergence": 0.833,
      "avg_composite_score": 0.8,
      "avg_energy_j": 749.5,
      "avg_energy_j_per_loc": 0.59,
      "correctness_per_dollar": 857142857.6041,
      "avg_quality_per_joule": 68.8659,
      "avg_constraints_met": 8.9,
      "avg_constraints_total": 9.0,
      "tokens_total": 22980,
      "tokens_input": 258,
      "tokens_output": 22722,
      "tokens_reasoning": 0,
      "avg_narration_penalty": null,
      "avg_struct_divergence": null,
      "avg_code_quality": null,
      "avg_comment_ratio": null,
      "narration_rate": null,
      "ast_files": null,
      "ast_functions": null,
      "ast_classes": null,
      "ast_type_hint_pct": null,
      "ast_docstring_pct": null,
      "cost_input": null,
      "cost_output": null,
      "cost_reasoning": null,
      "cost_cache": null,
      "tokens_cache_read": null,
      "tokens_cache_write": null,
      "_historical_fields": [
        "avg_narration_penalty",
        "avg_struct_divergence",
        "avg_code_quality",
        "avg_comment_ratio",
        "narration_rate",
        "ast_files",
        "ast_functions",
        "ast_classes",
        "ast_type_hint_pct",
        "ast_docstring_pct",
        "cost_input",
        "cost_output",
        "cost_reasoning",
        "cost_cache",
        "tokens_cache_read",
        "tokens_cache_write"
      ],
      "_provenance": {
        "reports": "M",
        "reports_valid": "M",
        "reports_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": null
      }
    },
    {
      "id": "deepseek/deepseek-v4-flash",
      "label": "DeepSeek v4 Flash",
      "provider": "deepseek",
      "reports": 7,
      "reports_valid": 7,
      "reports_narrated": 0,
      "n_reports": 7,
      "n_valid": 7,
      "n_narrated": 0,
      "avg_cost": 0.0096,
      "total_cost": 0.0672,
      "cost_ci95": [
        0.0083,
        0.0111
      ],
      "pass_rate": "98% (309/315) [tests]",
      "strategy_cons": 1,
      "strategy_expl": 4,
      "strategy_waste": 0,
      "strategy_efficient": 1,
      "avg_loc": 1143,
      "avg_thinking_ratio": 0.228,
      "avg_escape": 0.54,
      "avg_arch_divergence": 0.571,
      "avg_composite_score": 0.793,
      "avg_energy_j": 7992.3,
      "avg_energy_j_per_loc": 6.99,
      "correctness_per_dollar": 98.5565,
      "avg_quality_per_joule": 0.0001,
      "avg_constraints_met": 8.6,
      "avg_constraints_total": 9.0,
      "tokens_total": 230235,
      "tokens_input": 66381,
      "tokens_output": 109898,
      "tokens_reasoning": 53956,
      "avg_narration_penalty": null,
      "avg_struct_divergence": null,
      "avg_code_quality": null,
      "avg_comment_ratio": null,
      "narration_rate": null,
      "ast_files": null,
      "ast_functions": null,
      "ast_classes": null,
      "ast_type_hint_pct": null,
      "ast_docstring_pct": null,
      "cost_input": null,
      "cost_output": null,
      "cost_reasoning": null,
      "cost_cache": null,
      "tokens_cache_read": null,
      "tokens_cache_write": null,
      "_historical_fields": [
        "avg_narration_penalty",
        "avg_struct_divergence",
        "avg_code_quality",
        "avg_comment_ratio",
        "narration_rate",
        "ast_files",
        "ast_functions",
        "ast_classes",
        "ast_type_hint_pct",
        "ast_docstring_pct",
        "cost_input",
        "cost_output",
        "cost_reasoning",
        "cost_cache",
        "tokens_cache_read",
        "tokens_cache_write"
      ],
      "_provenance": {
        "reports": "M",
        "reports_valid": "M",
        "reports_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "openai/gpt-5.6-luna",
      "label": "GPT-5.6 Luna",
      "provider": "openai",
      "reports": 7,
      "reports_valid": 7,
      "reports_narrated": 0,
      "n_reports": 7,
      "n_valid": 7,
      "n_narrated": 0,
      "avg_cost": 0.0173,
      "total_cost": 0.1211,
      "cost_ci95": [
        0.0152,
        0.0196
      ],
      "pass_rate": "100% (53/53) [tests]",
      "strategy_cons": 0,
      "strategy_expl": 0,
      "strategy_waste": 0,
      "strategy_efficient": 6,
      "avg_loc": 334,
      "avg_thinking_ratio": 0.021,
      "avg_escape": 0.29,
      "avg_arch_divergence": 0.198,
      "avg_composite_score": 0.838,
      "avg_energy_j": 4060.4,
      "avg_energy_j_per_loc": 12.16,
      "correctness_per_dollar": 59.547,
      "avg_quality_per_joule": 0.0002,
      "avg_constraints_met": 8.9,
      "avg_constraints_total": 9.0,
      "tokens_total": 241190,
      "tokens_input": 187936,
      "tokens_output": 48507,
      "tokens_reasoning": 4747,
      "avg_narration_penalty": null,
      "avg_struct_divergence": null,
      "avg_code_quality": null,
      "avg_comment_ratio": null,
      "narration_rate": null,
      "ast_files": null,
      "ast_functions": null,
      "ast_classes": null,
      "ast_type_hint_pct": null,
      "ast_docstring_pct": null,
      "cost_input": null,
      "cost_output": null,
      "cost_reasoning": null,
      "cost_cache": null,
      "tokens_cache_read": null,
      "tokens_cache_write": null,
      "_historical_fields": [
        "avg_narration_penalty",
        "avg_struct_divergence",
        "avg_code_quality",
        "avg_comment_ratio",
        "narration_rate",
        "ast_files",
        "ast_functions",
        "ast_classes",
        "ast_type_hint_pct",
        "ast_docstring_pct",
        "cost_input",
        "cost_output",
        "cost_reasoning",
        "cost_cache",
        "tokens_cache_read",
        "tokens_cache_write"
      ],
      "_provenance": {
        "reports": "M",
        "reports_valid": "M",
        "reports_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "provider": "deepseek",
      "reports": 12,
      "reports_valid": 12,
      "reports_narrated": 0,
      "n_reports": 12,
      "n_valid": 12,
      "n_narrated": 0,
      "avg_cost": 0.0169,
      "total_cost": 0.2032,
      "cost_ci95": [
        0.0143,
        0.0195
      ],
      "pass_rate": "100% (270/271) [tests]",
      "strategy_cons": 0,
      "strategy_expl": 8,
      "strategy_waste": 0,
      "strategy_efficient": 2,
      "avg_loc": 636,
      "avg_thinking_ratio": 0.211,
      "avg_escape": 0.58,
      "avg_arch_divergence": 0.646,
      "avg_composite_score": 0.772,
      "avg_energy_j": 5015.1,
      "avg_energy_j_per_loc": 7.89,
      "correctness_per_dollar": 64.9708,
      "avg_quality_per_joule": 0.0002,
      "avg_constraints_met": 6.2,
      "avg_constraints_total": 7.8,
      "tokens_total": 270027,
      "tokens_input": 107878,
      "tokens_output": 102747,
      "tokens_reasoning": 59402,
      "avg_narration_penalty": null,
      "avg_struct_divergence": null,
      "avg_code_quality": null,
      "avg_comment_ratio": null,
      "narration_rate": null,
      "ast_files": null,
      "ast_functions": null,
      "ast_classes": null,
      "ast_type_hint_pct": null,
      "ast_docstring_pct": null,
      "cost_input": null,
      "cost_output": null,
      "cost_reasoning": null,
      "cost_cache": null,
      "tokens_cache_read": null,
      "tokens_cache_write": null,
      "_historical_fields": [
        "avg_narration_penalty",
        "avg_struct_divergence",
        "avg_code_quality",
        "avg_comment_ratio",
        "narration_rate",
        "ast_files",
        "ast_functions",
        "ast_classes",
        "ast_type_hint_pct",
        "ast_docstring_pct",
        "cost_input",
        "cost_output",
        "cost_reasoning",
        "cost_cache",
        "tokens_cache_read",
        "tokens_cache_write"
      ],
      "_provenance": {
        "reports": "M",
        "reports_valid": "M",
        "reports_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "anthropic/claude-sonnet-5",
      "label": "Claude Sonnet 5",
      "provider": "anthropic",
      "reports": 12,
      "reports_valid": 12,
      "reports_narrated": 0,
      "n_reports": 12,
      "n_valid": 12,
      "n_narrated": 0,
      "avg_cost": 0.3065,
      "total_cost": 3.6785,
      "cost_ci95": [
        0.1126,
        0.5311
      ],
      "pass_rate": null,
      "strategy_cons": 2,
      "strategy_expl": 2,
      "strategy_waste": 0,
      "strategy_efficient": 6,
      "avg_loc": 691,
      "avg_thinking_ratio": 0.0,
      "avg_escape": 0.46,
      "avg_arch_divergence": 0.389,
      "avg_composite_score": 0.757,
      "avg_energy_j": 1622.8,
      "avg_energy_j_per_loc": 2.35,
      "correctness_per_dollar": 416666668.1888,
      "avg_quality_per_joule": 32.5887,
      "avg_constraints_met": 6.7,
      "avg_constraints_total": 7.8,
      "tokens_total": 84843,
      "tokens_input": 266,
      "tokens_output": 84577,
      "tokens_reasoning": 0,
      "avg_narration_penalty": null,
      "avg_struct_divergence": null,
      "avg_code_quality": null,
      "avg_comment_ratio": null,
      "narration_rate": null,
      "ast_files": null,
      "ast_functions": null,
      "ast_classes": null,
      "ast_type_hint_pct": null,
      "ast_docstring_pct": null,
      "cost_input": null,
      "cost_output": null,
      "cost_reasoning": null,
      "cost_cache": null,
      "tokens_cache_read": null,
      "tokens_cache_write": null,
      "_historical_fields": [
        "avg_narration_penalty",
        "avg_struct_divergence",
        "avg_code_quality",
        "avg_comment_ratio",
        "narration_rate",
        "ast_files",
        "ast_functions",
        "ast_classes",
        "ast_type_hint_pct",
        "ast_docstring_pct",
        "cost_input",
        "cost_output",
        "cost_reasoning",
        "cost_cache",
        "tokens_cache_read",
        "tokens_cache_write"
      ],
      "_provenance": {
        "reports": "M",
        "reports_valid": "M",
        "reports_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": null
      }
    },
    {
      "id": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "provider": "openai",
      "reports": 19,
      "reports_valid": 19,
      "reports_narrated": 0,
      "n_reports": 19,
      "n_valid": 19,
      "n_narrated": 0,
      "avg_cost": 0.3522,
      "total_cost": 6.6916,
      "cost_ci95": [
        0.2841,
        0.415
      ],
      "pass_rate": "100% (137/137) [tests]",
      "strategy_cons": 1,
      "strategy_expl": 4,
      "strategy_waste": 0,
      "strategy_efficient": 11,
      "avg_loc": 474,
      "avg_thinking_ratio": 0.022,
      "avg_escape": 0.39,
      "avg_arch_divergence": 0.334,
      "avg_composite_score": 0.808,
      "avg_energy_j": 3820.4,
      "avg_energy_j_per_loc": 8.06,
      "correctness_per_dollar": 4.9624,
      "avg_quality_per_joule": 0.0003,
      "avg_constraints_met": 7.8,
      "avg_constraints_total": 8.2,
      "tokens_total": 572413,
      "tokens_input": 412819,
      "tokens_output": 147700,
      "tokens_reasoning": 11894,
      "avg_narration_penalty": null,
      "avg_struct_divergence": null,
      "avg_code_quality": null,
      "avg_comment_ratio": null,
      "narration_rate": null,
      "ast_files": null,
      "ast_functions": null,
      "ast_classes": null,
      "ast_type_hint_pct": null,
      "ast_docstring_pct": null,
      "cost_input": null,
      "cost_output": null,
      "cost_reasoning": null,
      "cost_cache": null,
      "tokens_cache_read": null,
      "tokens_cache_write": null,
      "_historical_fields": [
        "avg_narration_penalty",
        "avg_struct_divergence",
        "avg_code_quality",
        "avg_comment_ratio",
        "narration_rate",
        "ast_files",
        "ast_functions",
        "ast_classes",
        "ast_type_hint_pct",
        "ast_docstring_pct",
        "cost_input",
        "cost_output",
        "cost_reasoning",
        "cost_cache",
        "tokens_cache_read",
        "tokens_cache_write"
      ],
      "_provenance": {
        "reports": "M",
        "reports_valid": "M",
        "reports_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    }
  ],
  "charts": {
    "labels": [
      "DeepSeek v4 Flash",
      "GPT-5.6 Luna",
      "DeepSeek v4 Pro",
      "openai/gpt-5.6-terra",
      "anthropic/claude-haiku-4-5",
      "openai/gpt-5.6-sol",
      "Claude Sonnet 5"
    ],
    "costData": [
      0.074461,
      0.093548,
      0.161908,
      1.044326,
      1.63084,
      3.817461,
      5.169337
    ],
    "narrData": [
      null,
      null,
      null,
      null,
      null,
      null,
      null
    ],
    "locData": [
      991.0,
      697.0,
      879.0,
      566.0,
      1484.0,
      739.0,
      1761.0
    ],
    "costY": [
      0.074461,
      0.093548,
      0.161908,
      1.044326,
      1.63084,
      3.817461,
      5.169337
    ],
    "reports": [
      31,
      34,
      39,
      30,
      24,
      30,
      27
    ]
  },
  "calculator": {
    "model_costs": [
      {
        "n": "DeepSeek v4 Flash",
        "c": 0.074461,
        "p": 1.0
      },
      {
        "n": "GPT-5.6 Luna",
        "c": 0.093548,
        "p": 1.0
      },
      {
        "n": "DeepSeek v4 Pro",
        "c": 0.161908,
        "p": 1.0
      },
      {
        "n": "openai/gpt-5.6-terra",
        "c": 1.044326,
        "p": 1.0
      },
      {
        "n": "anthropic/claude-haiku-4-5",
        "c": 1.63084,
        "p": 0
      },
      {
        "n": "openai/gpt-5.6-sol",
        "c": 3.817461,
        "p": 1.0
      },
      {
        "n": "Claude Sonnet 5",
        "c": 5.169337,
        "p": 1.0
      }
    ],
    "escalation_tiers": [
      {
        "m": "DS\u2192Luna",
        "e": 1.3
      },
      {
        "m": "DS\u2192Pro",
        "e": 2.2
      },
      {
        "m": "DS\u2192openai/gpt-5.6-terra",
        "e": 14.0
      },
      {
        "m": "DS\u2192anthropic/claude-haiku-4-5",
        "e": 21.9
      },
      {
        "m": "DS\u2192openai/gpt-5.6-sol",
        "e": 51.3
      },
      {
        "m": "DS\u21925",
        "e": 69.4
      },
      {
        "m": "\u2192Human ($5/job)",
        "e": 67.1
      }
    ],
    "retry_rate_measured": 0.0,
    "woc_ratio": 1.0
  },
  "derived": {
    "cost_gap": "22\u00d7",
    "cost_gap_computation": "$1.63084 / $0.074461 = 21.9\u00d7",
    "overall_pass_rate": "100.0% (10760/10763) [tests]",
    "total_tests_passed": 10760,
    "total_tests_run": 10763,
    "total_cost_all_models": 309.1685,
    "total_cost_deepseek": 8.6227,
    "total_cost_claude": 151.5116,
    "total_narrated": 0,
    "total_valid_reports": 215,
    "total_reports_analyzed": 215,
    "_provenance": {
      "cost_gap": "C",
      "overall_pass_rate": "C",
      "total_tests_passed": "M",
      "total_tests_run": "M",
      "total_cost_all_models": "M",
      "total_cost_deepseek": "M",
      "total_cost_claude": "M",
      "total_narrated": "M",
      "total_valid_reports": "M",
      "total_reports_analyzed": "M"
    }
  },
  "operator_comparison": {
    "perturbed": {
      "perturbation_class": "process_perturbation",
      "models": {
        "DeepSeek v4 Pro": {
          "n": 2,
          "avg_cost": 0.0147,
          "cost_ci95": null,
          "avg_escape": 0.68,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.068,
          "avg_energy_j": 3582.8,
          "low_n": true
        },
        "Claude Sonnet 5": {
          "n": 2,
          "avg_cost": 0.0,
          "cost_ci95": null,
          "avg_escape": 0.32,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": 0.0,
          "low_n": true
        },
        "openai/gpt-5.6-terra": {
          "n": 2,
          "avg_cost": 0.2431,
          "cost_ci95": null,
          "avg_escape": 0.42,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.023,
          "avg_energy_j": 3910.1,
          "low_n": true
        },
        "DeepSeek v4 Flash": {
          "n": 2,
          "avg_cost": 0.0096,
          "cost_ci95": null,
          "avg_escape": 0.6,
          "escape_ci95": null,
          "avg_correctness": 0.99,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.292,
          "avg_energy_j": 8231.7,
          "low_n": true
        },
        "anthropic/claude-haiku-4-5": {
          "n": 2,
          "avg_cost": 0.0,
          "cost_ci95": null,
          "avg_escape": 0.79,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": 0.0,
          "low_n": true
        },
        "openai/gpt-5.6-sol": {
          "n": 2,
          "avg_cost": 0.515,
          "cost_ci95": null,
          "avg_escape": 0.44,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.016,
          "avg_energy_j": 4659.6,
          "low_n": true
        },
        "GPT-5.6 Luna": {
          "n": 2,
          "avg_cost": 0.0156,
          "cost_ci95": null,
          "avg_escape": 0.37,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.024,
          "avg_energy_j": 3555.4,
          "low_n": true
        }
      }
    },
    "baseline": {
      "perturbation_class": "baseline",
      "models": {
        "Claude Sonnet 5": {
          "n": 2,
          "avg_cost": 0.3131,
          "cost_ci95": null,
          "avg_escape": 0.0,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": 1624.1,
          "low_n": true
        },
        "DeepSeek v4 Pro": {
          "n": 2,
          "avg_cost": 0.0134,
          "cost_ci95": null,
          "avg_escape": 0.0,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.148,
          "avg_energy_j": 3558.1,
          "low_n": true
        },
        "openai/gpt-5.6-sol": {
          "n": 2,
          "avg_cost": 0.458,
          "cost_ci95": null,
          "avg_escape": 0.0,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.021,
          "avg_energy_j": 4111.1,
          "low_n": true
        },
        "GPT-5.6 Luna": {
          "n": 1,
          "avg_cost": 0.0168,
          "cost_ci95": null,
          "avg_escape": 0.0,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.019,
          "avg_energy_j": 4056.5,
          "low_n": true
        },
        "anthropic/claude-haiku-4-5": {
          "n": 1,
          "avg_cost": 0.0,
          "cost_ci95": null,
          "avg_escape": 0.0,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": 0.0,
          "low_n": true
        },
        "DeepSeek v4 Flash": {
          "n": 1,
          "avg_cost": 0.012,
          "cost_ci95": null,
          "avg_escape": 0.0,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.186,
          "avg_energy_j": 9024.4,
          "low_n": true
        },
        "openai/gpt-5.6-terra": {
          "n": 1,
          "avg_cost": 0.2095,
          "cost_ci95": null,
          "avg_escape": 0.0,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.017,
          "avg_energy_j": 3602.8,
          "low_n": true
        }
      }
    }
  },
  "perturbation_class_breakdown": {
    "process_perturbation": {
      "DeepSeek v4 Pro": {
        "n": 6,
        "low_n": false,
        "avg_cost": 0.0162,
        "cost_ci95": [
          0.0135,
          0.0186
        ],
        "avg_escape": 0.67,
        "escape_ci95": [
          0.521,
          0.8242
        ],
        "avg_correctness": 1.0,
        "correctness_ci95": [
          0.9911,
          1.0
        ],
        "avg_thinking_ratio": 0.254,
        "avg_loc": 512,
        "avg_tokens": 21811,
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-terra": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.1088,
        "cost_ci95": null,
        "avg_escape": 0.57,
        "escape_ci95": null,
        "avg_correctness": 0.7,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.026,
        "avg_loc": 192,
        "avg_tokens": 17103,
        "avg_narration_penalty": null
      },
      "DeepSeek v4 Flash": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0079,
        "cost_ci95": null,
        "avg_escape": 0.75,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.119,
        "avg_loc": 1194,
        "avg_tokens": 27850,
        "avg_narration_penalty": null
      },
      "anthropic/claude-haiku-4-5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0,
        "cost_ci95": null,
        "avg_escape": 0.74,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 1146,
        "avg_tokens": 0,
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-sol": {
        "n": 6,
        "low_n": false,
        "avg_cost": 0.3894,
        "cost_ci95": [
          0.3451,
          0.4258
        ],
        "avg_escape": 0.5,
        "escape_ci95": [
          0.3781,
          0.6143
        ],
        "avg_correctness": 1.0,
        "correctness_ci95": [
          1.0,
          1.0
        ],
        "avg_thinking_ratio": 0.029,
        "avg_loc": 464,
        "avg_tokens": 29168,
        "avg_narration_penalty": null
      },
      "Claude Sonnet 5": {
        "n": 6,
        "low_n": false,
        "avg_cost": 0.3063,
        "cost_ci95": [
          0.1161,
          0.4907
        ],
        "avg_escape": 0.63,
        "escape_ci95": [
          0.4418,
          0.8373
        ],
        "avg_correctness": 0.83,
        "correctness_ci95": [
          0.6333,
          1.0
        ],
        "avg_thinking_ratio": 0.0,
        "avg_loc": 460,
        "avg_tokens": 8283,
        "avg_narration_penalty": null
      },
      "GPT-5.6 Luna": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0196,
        "cost_ci95": null,
        "avg_escape": 0.37,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.016,
        "avg_loc": 343,
        "avg_tokens": 45713,
        "avg_narration_penalty": null
      }
    },
    "specification_corruption": {
      "Claude Sonnet 5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.6073,
        "cost_ci95": null,
        "avg_escape": 0.54,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 856,
        "avg_tokens": 10494,
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-sol": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.5505,
        "cost_ci95": null,
        "avg_escape": 0.46,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.012,
        "avg_loc": 682,
        "avg_tokens": 39448,
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-terra": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.1974,
        "cost_ci95": null,
        "avg_escape": 0.32,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.019,
        "avg_loc": 342,
        "avg_tokens": 31686,
        "avg_narration_penalty": null
      },
      "DeepSeek v4 Flash": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0096,
        "cost_ci95": null,
        "avg_escape": 0.6,
        "escape_ci95": null,
        "avg_correctness": 0.99,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.292,
        "avg_loc": 932,
        "avg_tokens": 32778,
        "avg_narration_penalty": null
      },
      "anthropic/claude-haiku-4-5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.1548,
        "cost_ci95": null,
        "avg_escape": 0.76,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 1416,
        "avg_tokens": 11490,
        "avg_narration_penalty": null
      },
      "DeepSeek v4 Pro": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0147,
        "cost_ci95": null,
        "avg_escape": 0.68,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.068,
        "avg_loc": 738,
        "avg_tokens": 20344,
        "avg_narration_penalty": null
      },
      "GPT-5.6 Luna": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0156,
        "cost_ci95": null,
        "avg_escape": 0.37,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.024,
        "avg_loc": 340,
        "avg_tokens": 28792,
        "avg_narration_penalty": null
      }
    },
    "objective_mutation": {
      "DeepSeek v4 Pro": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0247,
        "cost_ci95": null,
        "avg_escape": 0.77,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.287,
        "avg_loc": 1006,
        "avg_tokens": 30844,
        "avg_narration_penalty": null
      },
      "DeepSeek v4 Flash": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0101,
        "cost_ci95": null,
        "avg_escape": 0.56,
        "escape_ci95": null,
        "avg_correctness": 0.58,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.294,
        "avg_loc": 1120,
        "avg_tokens": 35268,
        "avg_narration_penalty": null
      },
      "GPT-5.6 Luna": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0169,
        "cost_ci95": null,
        "avg_escape": 0.26,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.024,
        "avg_loc": 330,
        "avg_tokens": 28330,
        "avg_narration_penalty": null
      },
      "Claude Sonnet 5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0,
        "cost_ci95": null,
        "avg_escape": 0.32,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 1156,
        "avg_tokens": 0,
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-sol": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.515,
        "cost_ci95": null,
        "avg_escape": 0.44,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.016,
        "avg_loc": 749,
        "avg_tokens": 33576,
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-terra": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.2431,
        "cost_ci95": null,
        "avg_escape": 0.42,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.023,
        "avg_loc": 405,
        "avg_tokens": 30637,
        "avg_narration_penalty": null
      },
      "anthropic/claude-haiku-4-5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0,
        "cost_ci95": null,
        "avg_escape": 0.79,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 1432,
        "avg_tokens": 0,
        "avg_narration_penalty": null
      }
    },
    "baseline": {
      "Claude Sonnet 5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.3131,
        "cost_ci95": null,
        "avg_escape": 0.0,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 753,
        "avg_tokens": 7078,
        "avg_narration_penalty": null
      },
      "DeepSeek v4 Pro": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0134,
        "cost_ci95": null,
        "avg_escape": 0.0,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.148,
        "avg_loc": 534,
        "avg_tokens": 18392,
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-sol": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.458,
        "cost_ci95": null,
        "avg_escape": 0.0,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.021,
        "avg_loc": 568,
        "avg_tokens": 31681,
        "avg_narration_penalty": null
      },
      "GPT-5.6 Luna": {
        "n": 1,
        "low_n": true,
        "avg_cost": 0.0168,
        "cost_ci95": null,
        "avg_escape": 0.0,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.019,
        "avg_loc": 314,
        "avg_tokens": 35520,
        "avg_narration_penalty": null
      },
      "anthropic/claude-haiku-4-5": {
        "n": 1,
        "low_n": true,
        "avg_cost": 0.0,
        "cost_ci95": null,
        "avg_escape": 0.0,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 902,
        "avg_tokens": 0,
        "avg_narration_penalty": null
      },
      "DeepSeek v4 Flash": {
        "n": 1,
        "low_n": true,
        "avg_cost": 0.012,
        "cost_ci95": null,
        "avg_escape": 0.0,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.186,
        "avg_loc": 1510,
        "avg_tokens": 38442,
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-terra": {
        "n": 1,
        "low_n": true,
        "avg_cost": 0.2095,
        "cost_ci95": null,
        "avg_escape": 0.0,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.017,
        "avg_loc": 343,
        "avg_tokens": 29140,
        "avg_narration_penalty": null
      }
    }
  },
  "energy_ranking": [
    {
      "id": "anthropic/claude-haiku-4-5",
      "label": "anthropic/claude-haiku-4-5",
      "avg_energy_j": 15438.9,
      "avg_energy_j_per_loc": 10.4,
      "avg_cost": 1.63084,
      "avg_loc": 1484.0
    },
    {
      "id": "anthropic/claude-sonnet-5",
      "label": "Claude Sonnet 5",
      "avg_energy_j": 21095.0,
      "avg_energy_j_per_loc": 11.98,
      "avg_cost": 5.169337,
      "avg_loc": 1761.0
    },
    {
      "id": "openai/gpt-5.6-luna",
      "label": "GPT-5.6 Luna",
      "avg_energy_j": 14130.0,
      "avg_energy_j_per_loc": 20.27,
      "avg_cost": 0.093548,
      "avg_loc": 697.0
    },
    {
      "id": "openai/gpt-5.6-terra",
      "label": "openai/gpt-5.6-terra",
      "avg_energy_j": 18681.4,
      "avg_energy_j_per_loc": 33.01,
      "avg_cost": 1.044326,
      "avg_loc": 566.0
    },
    {
      "id": "openai/gpt-5.6-sol",
      "label": "openai/gpt-5.6-sol",
      "avg_energy_j": 27822.1,
      "avg_energy_j_per_loc": 37.65,
      "avg_cost": 3.817461,
      "avg_loc": 739.0
    },
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "avg_energy_j": 39819.6,
      "avg_energy_j_per_loc": 45.3,
      "avg_cost": 0.161908,
      "avg_loc": 879.0
    },
    {
      "id": "deepseek/deepseek-v4-flash",
      "label": "DeepSeek v4 Flash",
      "avg_energy_j": 54395.2,
      "avg_energy_j_per_loc": 54.89,
      "avg_cost": 0.074461,
      "avg_loc": 991.0
    }
  ],
  "strategy_distribution": {
    "exploratory": 24,
    "efficient": 26,
    "?": 10,
    "conservative": 4
  },
  "routing": {
    "_meta": {
      "tasks_analyzed": 2,
      "total_valid_entries": 64
    },
    "per_task": [
      {
        "task": "process_perturbation_resample",
        "models_tested": 3,
        "best_correctness_model": "openai/gpt-5.6-sol",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "openai/gpt-5.6-sol",
        "routing": "default",
        "recommendation": "default deepseek/deepseek-v4-pro",
        "models": {
          "openai/gpt-5.6-sol": {
            "n": 5,
            "avg_correctness": 1.0,
            "avg_cost": 0.40127,
            "efficiency": 2.49
          },
          "anthropic/claude-sonnet-5": {
            "n": 5,
            "avg_correctness": 0.92,
            "avg_cost": 0.476491,
            "efficiency": 1.93
          },
          "deepseek/deepseek-v4-pro": {
            "n": 5,
            "avg_correctness": 1.0,
            "avg_cost": 0.01351,
            "efficiency": 74.02
          }
        }
      },
      {
        "task": "task_manager",
        "models_tested": 7,
        "best_correctness_model": "anthropic/claude-haiku-4-5",
        "best_efficiency_model": "deepseek/deepseek-v4-flash",
        "default_model": "deepseek/deepseek-v4-flash",
        "escalate_model": "anthropic/claude-haiku-4-5",
        "routing": "escalate",
        "recommendation": "escalate to anthropic/claude-haiku-4-5",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 7,
            "avg_correctness": 0.9974,
            "avg_cost": 0.01938,
            "efficiency": 51.47
          },
          "anthropic/claude-sonnet-5": {
            "n": 7,
            "avg_correctness": 0.9143,
            "avg_cost": 0.185146,
            "efficiency": 4.94
          },
          "openai/gpt-5.6-terra": {
            "n": 7,
            "avg_correctness": 0.9143,
            "avg_cost": 0.18689,
            "efficiency": 4.89
          },
          "deepseek/deepseek-v4-flash": {
            "n": 7,
            "avg_correctness": 0.8792,
            "avg_cost": 0.009603,
            "efficiency": 91.55
          },
          "anthropic/claude-haiku-4-5": {
            "n": 7,
            "avg_correctness": 1.0,
            "avg_cost": 0.044242,
            "efficiency": 22.6
          },
          "openai/gpt-5.6-sol": {
            "n": 7,
            "avg_correctness": 1.0,
            "avg_cost": 0.482432,
            "efficiency": 2.07
          },
          "openai/gpt-5.6-luna": {
            "n": 7,
            "avg_correctness": 1.0,
            "avg_cost": 0.017297,
            "efficiency": 57.81
          }
        }
      }
    ],
    "strategies": {
      "anthropic/claude-haiku-4-5_only": {
        "n": 7,
        "total_cost": 0.309695,
        "avg_cost": 0.044242,
        "avg_correctness": 1.0
      },
      "anthropic/claude-sonnet-5_only": {
        "n": 12,
        "total_cost": 3.678477,
        "avg_cost": 0.30654,
        "avg_correctness": 0.9167
      },
      "deepseek/deepseek-v4-flash_only": {
        "n": 7,
        "total_cost": 0.067223,
        "avg_cost": 0.009603,
        "avg_correctness": 0.8792
      },
      "deepseek/deepseek-v4-pro_only": {
        "n": 12,
        "total_cost": 0.203213,
        "avg_cost": 0.016934,
        "avg_correctness": 0.9985
      },
      "openai/gpt-5.6-luna_only": {
        "n": 7,
        "total_cost": 0.121081,
        "avg_cost": 0.017297,
        "avg_correctness": 1.0
      },
      "openai/gpt-5.6-sol_only": {
        "n": 12,
        "total_cost": 5.383373,
        "avg_cost": 0.448614,
        "avg_correctness": 1.0
      },
      "openai/gpt-5.6-terra_only": {
        "n": 7,
        "total_cost": 1.308232,
        "avg_cost": 0.18689,
        "avg_correctness": 0.9143
      },
      "grit_routed": {
        "n": 12,
        "total_cost": 0.377245,
        "avg_cost": 0.031437,
        "avg_correctness": 1.0,
        "routing_distribution": {
          "deepseek/deepseek-v4-pro": 5,
          "anthropic/claude-haiku-4-5": 7
        }
      }
    },
    "routing_distribution": {
      "default": 1,
      "escalate": 1
    }
  },
  "correctness_escape_quadrants": [],
  "sonar": {
    "models": {},
    "_historical": true,
    "_note": "[P] SonarQube per-cell aggregates retired with the legacy summary corpus \u2014 no canonical replacement in the registry."
  },
  "design_parameters": {
    "beta": {
      "value": 0.001,
      "provenance": "design",
      "note": "Context inflation rate \u2014 calibrate to your codebase"
    },
    "woc_healthy": {
      "value": 0.85,
      "provenance": "design"
    },
    "woc_critical": {
      "value": 0.7,
      "provenance": "design"
    },
    "strategy_thresholds": {
      "correctness_min": 0.7,
      "escape_min": 0.5,
      "novelty_min": 0.4,
      "efficient_cost_max": 0.003,
      "wasteful_correctness_max": 0.3,
      "provenance": "design"
    },
    "composite_weights": {
      "correctness": 0.35,
      "constraint": 0.3,
      "quality": 0.2,
      "novelty": 0.15,
      "provenance": "design"
    }
  },
  "external_sources": {
    "epm_baseline": {
      "value": "1.6%/yr",
      "provenance": "X",
      "source": "IEA World Energy Outlook 2024"
    },
    "epm_aggressive": {
      "value": "2.5%/yr",
      "provenance": "X",
      "source": "Aggressive scenario"
    },
    "energy_per_token_prompt": {
      "value": 0.08,
      "unit": "J",
      "provenance": "X",
      "source": "TokenPowerBench (Niu et al., AAAI 2026)"
    },
    "energy_per_token_output": {
      "value": 0.23,
      "unit": "J",
      "provenance": "X",
      "source": "TokenPowerBench (Niu et al., AAAI 2026)"
    },
    "energy_per_token_reasoning": {
      "value": 0.47,
      "unit": "J",
      "provenance": "X",
      "source": "TokenPowerBench (Niu et al., AAAI 2026)"
    },
    "energy_model_available": {
      "value": false,
      "provenance": "X",
      "note": "Claude/GPT architecture undisclosed \u2014 energy model disabled"
    },
    "deepseek_active_params": {
      "value": "49e9",
      "provenance": "X",
      "note": "MoE V4 Pro, publicly disclosed (49B active)"
    }
  },
  "stories": {
    "_provenance": "[M] token counts from session.jsonl; cost from opencode DB verified",
    "models": [
      {
        "model": "deepseek/deepseek-v4-flash",
        "cells": 31,
        "total_cost": 2.308294,
        "avg_cost": 0.074461,
        "avg_captured_cost": 0.074461,
        "cost_captured_cells": 31,
        "total_cells": 31,
        "cost_coverage": 1.0,
        "total_tokens": 7755588,
        "avg_cache_hit": 0.964,
        "avg_duration_s": 1401.0
      },
      {
        "model": "openai/gpt-5.6-luna",
        "cells": 34,
        "total_cost": 3.180633,
        "avg_cost": 0.093548,
        "avg_captured_cost": 0.093548,
        "cost_captured_cells": 34,
        "total_cells": 34,
        "cost_coverage": 1.0,
        "total_tokens": 3052682,
        "avg_cache_hit": 0.937,
        "avg_duration_s": 658.0
      },
      {
        "model": "deepseek/deepseek-v4-pro",
        "cells": 39,
        "total_cost": 6.314403,
        "avg_cost": 0.161908,
        "avg_captured_cost": 0.161908,
        "cost_captured_cells": 39,
        "total_cells": 39,
        "cost_coverage": 1.0,
        "total_tokens": 7536137,
        "avg_cache_hit": 0.801,
        "avg_duration_s": 1766.0
      },
      {
        "model": "openai/gpt-5.6-terra",
        "cells": 30,
        "total_cost": 31.329782,
        "avg_cost": 1.044326,
        "avg_captured_cost": 1.044326,
        "cost_captured_cells": 30,
        "total_cells": 30,
        "cost_coverage": 1.0,
        "total_tokens": 4770535,
        "avg_cache_hit": 0.832,
        "avg_duration_s": 785.0
      },
      {
        "model": "anthropic/claude-haiku-4-5",
        "cells": 24,
        "total_cost": 32.616808,
        "avg_cost": 1.63084,
        "avg_captured_cost": 1.63084,
        "cost_captured_cells": 20,
        "total_cells": 24,
        "cost_coverage": 0.8333,
        "total_tokens": 1629766,
        "avg_cache_hit": 0.824,
        "avg_duration_s": 862.0
      },
      {
        "model": "openai/gpt-5.6-sol",
        "cells": 30,
        "total_cost": 114.52382,
        "avg_cost": 3.817461,
        "avg_captured_cost": 3.817461,
        "cost_captured_cells": 30,
        "total_cells": 30,
        "cost_coverage": 1.0,
        "total_tokens": 6995342,
        "avg_cache_hit": 0.85,
        "avg_duration_s": 1146.0
      },
      {
        "model": "anthropic/claude-sonnet-5",
        "cells": 27,
        "total_cost": 118.894751,
        "avg_cost": 5.169337,
        "avg_captured_cost": 5.169337,
        "cost_captured_cells": 23,
        "total_cells": 27,
        "cost_coverage": 0.8519,
        "total_tokens": 2484557,
        "avg_cache_hit": 0.84,
        "avg_duration_s": 1062.0
      }
    ],
    "conditions": [
      {
        "condition": "clean",
        "cells": 135,
        "variants": 12,
        "total_cost": 208.287391,
        "avg_cost": 1.54287,
        "avg_captured_cost": 1.54287,
        "cost_captured_cells": 135,
        "total_cells": 135,
        "cost_coverage": 1.0,
        "success": 131,
        "fail": 4
      },
      {
        "condition": "early_degrade",
        "cells": 80,
        "variants": 12,
        "total_cost": 100.8811,
        "avg_cost": 1.401126,
        "avg_captured_cost": 1.401126,
        "cost_captured_cells": 72,
        "total_cells": 80,
        "cost_coverage": 0.9,
        "success": 69,
        "fail": 11
      }
    ],
    "stories": [
      {
        "story": "task_manager_api",
        "cells": 77,
        "total_cost": 87.323185,
        "avg_cost": 1.134067,
        "avg_captured_cost": 1.134067,
        "cost_captured_cells": 77,
        "total_cells": 77,
        "cost_coverage": 1.0,
        "sessions": 383,
        "avg_duration_s": 876.0,
        "avg_tokens_per_session": 23893.0
      },
      {
        "story": "notification_service",
        "cells": 73,
        "total_cost": 95.940785,
        "avg_cost": 1.453648,
        "avg_captured_cost": 1.453648,
        "cost_captured_cells": 66,
        "total_cells": 73,
        "cost_coverage": 0.9041,
        "sessions": 363,
        "avg_duration_s": 1143.0,
        "avg_tokens_per_session": 32065.0
      },
      {
        "story": "static_site_gen",
        "cells": 65,
        "total_cost": 125.904521,
        "avg_cost": 1.967258,
        "avg_captured_cost": 1.967258,
        "cost_captured_cells": 64,
        "total_cells": 65,
        "cost_coverage": 0.9846,
        "sessions": 321,
        "avg_duration_s": 1401.0,
        "avg_tokens_per_session": 40992.0
      }
    ],
    "tiers": [
      {
        "tier": "tier1_minimal",
        "quality": "bad",
        "cells": 43,
        "avg_cost": 1.549339,
        "avg_captured_cost": 1.549339,
        "cost_captured_cells": 41,
        "total_cells": 43,
        "cost_coverage": 0.9535,
        "avg_tokens_per_session": 32400.0,
        "avg_session_duration_s": 234.0
      },
      {
        "tier": "tier1_minimal",
        "quality": "good",
        "cells": 70,
        "avg_cost": 1.551765,
        "avg_captured_cost": 1.551765,
        "cost_captured_cells": 68,
        "total_cells": 70,
        "cost_coverage": 0.9714,
        "avg_tokens_per_session": 31413.0,
        "avg_session_duration_s": 238.0
      },
      {
        "tier": "tier2_small",
        "quality": "bad",
        "cells": 41,
        "avg_cost": 1.292634,
        "avg_captured_cost": 1.292634,
        "cost_captured_cells": 39,
        "total_cells": 41,
        "cost_coverage": 0.9512,
        "avg_tokens_per_session": 30951.0,
        "avg_session_duration_s": 220.0
      },
      {
        "tier": "tier2_small",
        "quality": "good",
        "cells": 61,
        "avg_cost": 1.520556,
        "avg_captured_cost": 1.520556,
        "cost_captured_cells": 59,
        "total_cells": 61,
        "cost_coverage": 0.9672,
        "avg_tokens_per_session": 32521.0,
        "avg_session_duration_s": 219.0
      }
    ],
    "sessions": {
      "total": 1067,
      "total_cost": 309.16849071000047,
      "total_tokens": 33518193,
      "total_cache_reads": 823919043,
      "cache_hit_rate": 0.977,
      "duration_s": 241966.7735237789,
      "successful": 1007,
      "failed": 60
    },
    "generated_at": "2026-08-21T21:50:36.931142+00:00"
  },
  "reviews": {
    "models": [
      {
        "model": "gpt-5.6-terra",
        "label": "gpt-5.6-terra",
        "stories": 20,
        "overall_coherence": 0.908,
        "architectural_fit": 0.749,
        "convention_adherence": 0.699,
        "better_pct": 75.0,
        "worse_pct": 14.0,
        "neutral_pct": 8.0,
        "top_issues": [
          {
            "theme": "other",
            "count": 38
          },
          {
            "theme": "security",
            "count": 17
          },
          {
            "theme": "incomplete refactor",
            "count": 16
          },
          {
            "theme": "test gaps",
            "count": 7
          },
          {
            "theme": "missing surface",
            "count": 6
          }
        ]
      },
      {
        "model": "gpt-5.6-sol",
        "label": "gpt-5.6-sol",
        "stories": 23,
        "overall_coherence": 0.899,
        "architectural_fit": 0.738,
        "convention_adherence": 0.665,
        "better_pct": 73.9,
        "worse_pct": 8.7,
        "neutral_pct": 13.9,
        "top_issues": [
          {
            "theme": "other",
            "count": 47
          },
          {
            "theme": "security",
            "count": 21
          },
          {
            "theme": "test gaps",
            "count": 15
          },
          {
            "theme": "incomplete refactor",
            "count": 12
          },
          {
            "theme": "missing surface",
            "count": 6
          }
        ]
      },
      {
        "model": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "stories": 22,
        "overall_coherence": 0.897,
        "architectural_fit": 0.749,
        "convention_adherence": 0.696,
        "better_pct": 74.2,
        "worse_pct": 6.7,
        "neutral_pct": 12.5,
        "top_issues": [
          {
            "theme": "other",
            "count": 32
          },
          {
            "theme": "security",
            "count": 18
          },
          {
            "theme": "incomplete refactor",
            "count": 18
          },
          {
            "theme": "test gaps",
            "count": 13
          },
          {
            "theme": "coupling",
            "count": 8
          }
        ]
      },
      {
        "model": "deepseek-v4-flash",
        "label": "DeepSeek v4 Flash",
        "stories": 21,
        "overall_coherence": 0.892,
        "architectural_fit": 0.754,
        "convention_adherence": 0.673,
        "better_pct": 65.7,
        "worse_pct": 7.6,
        "neutral_pct": 18.1,
        "top_issues": [
          {
            "theme": "other",
            "count": 39
          },
          {
            "theme": "incomplete refactor",
            "count": 15
          },
          {
            "theme": "test gaps",
            "count": 15
          },
          {
            "theme": "security",
            "count": 13
          },
          {
            "theme": "missing surface",
            "count": 7
          }
        ]
      },
      {
        "model": "claude-haiku-4-5",
        "label": "claude-haiku-4-5",
        "stories": 14,
        "overall_coherence": 0.881,
        "architectural_fit": 0.756,
        "convention_adherence": 0.769,
        "better_pct": 67.1,
        "worse_pct": 4.3,
        "neutral_pct": 25.7,
        "top_issues": [
          {
            "theme": "other",
            "count": 24
          },
          {
            "theme": "security",
            "count": 11
          },
          {
            "theme": "test gaps",
            "count": 9
          },
          {
            "theme": "schema drift",
            "count": 8
          },
          {
            "theme": "missing surface",
            "count": 7
          }
        ]
      },
      {
        "model": "deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "stories": 37,
        "overall_coherence": 0.876,
        "architectural_fit": 0.745,
        "convention_adherence": 0.705,
        "better_pct": 64.4,
        "worse_pct": 13.0,
        "neutral_pct": 18.1,
        "top_issues": [
          {
            "theme": "other",
            "count": 68
          },
          {
            "theme": "incomplete refactor",
            "count": 31
          },
          {
            "theme": "security",
            "count": 26
          },
          {
            "theme": "test gaps",
            "count": 18
          },
          {
            "theme": "coupling",
            "count": 9
          }
        ]
      },
      {
        "model": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "stories": 16,
        "overall_coherence": 0.824,
        "architectural_fit": 0.822,
        "convention_adherence": 0.763,
        "better_pct": 68.8,
        "worse_pct": 5.0,
        "neutral_pct": 21.2,
        "top_issues": [
          {
            "theme": "security",
            "count": 12
          },
          {
            "theme": "other",
            "count": 12
          },
          {
            "theme": "test gaps",
            "count": 12
          },
          {
            "theme": "missing surface",
            "count": 8
          },
          {
            "theme": "incomplete refactor",
            "count": 8
          }
        ]
      }
    ],
    "commit_reviews": 767,
    "story_reviews": 153,
    "reviewer": "deepseek/deepseek-v4-flash"
  },
  "analysis": {
    "models": [
      {
        "model": "deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "commits": 179,
        "lines_added": 121407,
        "lines_removed": 9090,
        "functions_added": 1410,
        "classes_added": 198,
        "imports_added": 1703,
        "sonar_available": 72,
        "sonar_bugs_delta": 6,
        "sonar_smells_delta": 114,
        "sonar_complexity_delta": 2152,
        "avg_convention": 0.712,
        "deep_cells": 37,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 37,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 37,
          "coverage": 0.0
        },
        "solution_correctness": 1.0,
        "solution_constraints": 1.0,
        "solution_quality": 0.045,
        "solution_novelty": 0.845,
        "solution_composite": 0.786,
        "basin_escape": 0.712,
        "strategies": {
          "exploratory": 37
        }
      },
      {
        "model": "deepseek-v4-flash",
        "label": "DeepSeek v4 Flash",
        "commits": 110,
        "lines_added": 79561,
        "lines_removed": 5859,
        "functions_added": 1363,
        "classes_added": 81,
        "imports_added": 1364,
        "sonar_available": 4,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 1,
        "sonar_complexity_delta": 51,
        "avg_convention": 0.686,
        "deep_cells": 22,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 22,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 22,
          "coverage": 0.0
        },
        "solution_correctness": 1.0,
        "solution_constraints": 1.0,
        "solution_quality": 0.037,
        "solution_novelty": 0.87,
        "solution_composite": 0.788,
        "basin_escape": 0.733,
        "strategies": {
          "exploratory": 22
        }
      },
      {
        "model": "gpt-5.6-sol",
        "label": "gpt-5.6-sol",
        "commits": 114,
        "lines_added": 64264,
        "lines_removed": 9317,
        "functions_added": 789,
        "classes_added": 76,
        "imports_added": 1017,
        "sonar_available": 0,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 0,
        "sonar_complexity_delta": 0,
        "avg_convention": 0.674,
        "deep_cells": 23,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 23,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 23,
          "coverage": 0.0
        },
        "solution_correctness": 1.0,
        "solution_constraints": 1.0,
        "solution_quality": 0.054,
        "solution_novelty": 0.917,
        "solution_composite": 0.798,
        "basin_escape": 0.783,
        "strategies": {
          "exploratory": 23
        }
      },
      {
        "model": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "commits": 80,
        "lines_added": 36187,
        "lines_removed": 2266,
        "functions_added": 1267,
        "classes_added": 86,
        "imports_added": 839,
        "sonar_available": 4,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 2,
        "sonar_complexity_delta": 43,
        "avg_convention": 0.732,
        "deep_cells": 16,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 16,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 16,
          "coverage": 0.0
        },
        "solution_correctness": 0.875,
        "solution_constraints": 0.958,
        "solution_quality": 0.052,
        "solution_novelty": 0.789,
        "solution_composite": 0.722,
        "basin_escape": 0.641,
        "strategies": {
          "exploratory": 14,
          "conservative": 2
        }
      },
      {
        "model": "claude-haiku-4-5",
        "label": "claude-haiku-4-5",
        "commits": 71,
        "lines_added": 33618,
        "lines_removed": 2496,
        "functions_added": 332,
        "classes_added": 188,
        "imports_added": 422,
        "sonar_available": 10,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 18,
        "sonar_complexity_delta": 133,
        "avg_convention": 0.754,
        "deep_cells": 14,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 14,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 14,
          "coverage": 0.0
        },
        "solution_correctness": 0.857,
        "solution_constraints": 0.976,
        "solution_quality": 0.037,
        "solution_novelty": 0.842,
        "solution_composite": 0.726,
        "basin_escape": 0.706,
        "strategies": {
          "exploratory": 12,
          "conservative": 2
        }
      },
      {
        "model": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "commits": 120,
        "lines_added": 19442,
        "lines_removed": 6657,
        "functions_added": 620,
        "classes_added": 67,
        "imports_added": 759,
        "sonar_available": 8,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 11,
        "sonar_complexity_delta": 87,
        "avg_convention": 0.693,
        "deep_cells": 24,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 24,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 24,
          "coverage": 0.0
        },
        "solution_correctness": 1.0,
        "solution_constraints": 0.986,
        "solution_quality": 0.087,
        "solution_novelty": 0.876,
        "solution_composite": 0.795,
        "basin_escape": 0.694,
        "strategies": {
          "exploratory": 24
        }
      },
      {
        "model": "gpt-5.6-terra",
        "label": "gpt-5.6-terra",
        "commits": 100,
        "lines_added": 17263,
        "lines_removed": 6550,
        "functions_added": 582,
        "classes_added": 69,
        "imports_added": 722,
        "sonar_available": 0,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 0,
        "sonar_complexity_delta": 0,
        "avg_convention": 0.695,
        "deep_cells": 20,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 20,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 20,
          "coverage": 0.0
        },
        "solution_correctness": 1.0,
        "solution_constraints": 0.983,
        "solution_quality": 0.088,
        "solution_novelty": 0.901,
        "solution_composite": 0.798,
        "basin_escape": 0.741,
        "strategies": {
          "exploratory": 20
        }
      }
    ],
    "stories_analyzed": 156,
    "commits_analyzed": 774,
    "sonar_commits_available": 98
  },
  "labs": {
    "cache_economics": {
      "experiment_id": "lab_cache_economics",
      "generated_at": "2026-08-21T23:18:16.219936",
      "summary": {
        "models": 7,
        "stories": 215
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 31,
          "avg_cost": 0.074,
          "avg_cache_hit": 0.964,
          "cache_reads": 224381696,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 7488299.0,
          "avg_tokens_per_cell": 250180.0
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 34,
          "avg_cost": 0.094,
          "avg_cache_hit": 0.937,
          "cache_reads": 44099872,
          "cache_writes": 2378880,
          "read_write_ratio": 18.5,
          "avg_context_per_cell": 1386840.0,
          "avg_tokens_per_cell": 89785.0
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 39,
          "avg_cost": 0.162,
          "avg_cache_hit": 0.801,
          "cache_reads": 146609152,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 3952443.0,
          "avg_tokens_per_cell": 193234.0
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 30,
          "avg_cost": 1.044,
          "avg_cache_hit": 0.832,
          "cache_reads": 23958016,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 957618.0,
          "avg_tokens_per_cell": 159018.0
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 24,
          "avg_cost": 1.631,
          "avg_cache_hit": 0.824,
          "cache_reads": 163588556,
          "cache_writes": 3922476,
          "read_write_ratio": 41.7,
          "avg_context_per_cell": 6884097.0,
          "avg_tokens_per_cell": 67907.0
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 30,
          "avg_cost": 3.817,
          "avg_cache_hit": 0.85,
          "cache_reads": 43466752,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 1682070.0,
          "avg_tokens_per_cell": 233178.0
        },
        {
          "model": "claude-sonnet-5",
          "cells": 27,
          "avg_cost": 5.169,
          "avg_cache_hit": 0.84,
          "cache_reads": 177814999,
          "cache_writes": 5250530,
          "read_write_ratio": 33.9,
          "avg_context_per_cell": 6677761.0,
          "avg_tokens_per_cell": 92021.0
        }
      ],
      "lab_contract": {
        "lab": "lab_cache_economics.py",
        "input_dataset_id": "canonical_registry/story",
        "registry_identity_sha256": "688d7b949481fb8775976eec5eef9c8fe9fcd59b8b21f9a02cd61a3108b2dd05",
        "resolved_input_sha256": "7d2ab0fe4c18695fe26767d6e848f7a2e3f3a397d16b1e183594f70b9136c716",
        "registry_version": "data-manifest/1.0+701rows",
        "metric_definition_version": "cache_economics/v1",
        "n_resolved_records": 215,
        "n_eligible_records": 215,
        "n_used_records": 215,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v4",
        "generated_at": "2026-08-21T21:18:16.220187+00:00"
      }
    },
    "condition_effects": {
      "experiment_id": "lab_condition_effects",
      "generated_at": "2026-08-21T23:18:16.596009",
      "summary": {
        "conditions": 2,
        "stories": 215,
        "reviews": 242,
        "joined_reviews": 155,
        "reviews_without_current_story": 87
      },
      "conditions": [
        {
          "condition": "clean",
          "cells": 135,
          "success_rate": 0.97,
          "cascade_rate": 0.015,
          "avg_cost": 1.5429,
          "total_cost": 208.2874,
          "reviews": 134,
          "worse_rate": 0.0
        },
        {
          "condition": "early_degrade",
          "cells": 80,
          "success_rate": 0.863,
          "cascade_rate": 0.025,
          "avg_cost": 1.261,
          "total_cost": 100.8811,
          "reviews": 21,
          "worse_rate": 0.0
        }
      ],
      "lab_contract": {
        "lab": "lab_condition_effects.py",
        "input_dataset_id": "canonical_registry/story+review",
        "registry_identity_sha256": "688d7b949481fb8775976eec5eef9c8fe9fcd59b8b21f9a02cd61a3108b2dd05",
        "resolved_input_sha256": "14648fd46fb445d31cd703e5734554043045b466936a968dd0bbc0a31df6b379",
        "registry_version": "data-manifest/1.0+701rows",
        "metric_definition_version": "condition_effects/v1",
        "n_resolved_records": 457,
        "n_eligible_records": 370,
        "n_used_records": 370,
        "n_excluded_records": 87,
        "n_unused_eligible_records": 0,
        "review_without_current_story": 87,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v4",
        "generated_at": "2026-08-21T21:18:16.596264+00:00"
      }
    },
    "grit": {
      "experiment_id": "lab_grit",
      "generated_at": "2026-08-21T23:18:17.132049",
      "metric_definition": "G(s) = P(test_executed_success | perturbation_strength = s)",
      "summary": {
        "cells": 144,
        "successes": 108,
        "grit_overall": 0.75,
        "strength_levels": [
          0.0,
          0.5
        ],
        "findings": 64,
        "stories": 215,
        "controlled_delta_grit": 0.0037,
        "excluded": 135,
        "exclusions": {
          "missing_required_field": 135
        }
      },
      "by_strength": [
        {
          "strength": 0.0,
          "n": 10,
          "successes": 7,
          "grit": 0.7,
          "ci95_lo": 0.3968,
          "ci95_hi": 0.8922,
          "insufficient_support": false,
          "sources": {
            "finding": 10,
            "story": 0
          }
        },
        {
          "strength": 0.5,
          "n": 134,
          "successes": 101,
          "grit": 0.7537,
          "ci95_lo": 0.6744,
          "ci95_hi": 0.8189,
          "insufficient_support": false,
          "sources": {
            "finding": 54,
            "story": 80
          }
        }
      ],
      "by_strength_finding_corpus": [
        {
          "strength": 0.0,
          "n": 10,
          "successes": 7,
          "grit": 0.7,
          "ci95_lo": 0.3968,
          "ci95_hi": 0.8922,
          "insufficient_support": false
        },
        {
          "strength": 0.5,
          "n": 54,
          "successes": 38,
          "grit": 0.7037,
          "ci95_lo": 0.5717,
          "ci95_hi": 0.8086,
          "insufficient_support": false
        }
      ],
      "by_model_perturbed": [
        {
          "model": "deepseek-v4-flash",
          "n": 15,
          "successes": 13,
          "grit": 0.8667,
          "ci95_lo": 0.6212,
          "ci95_hi": 0.9626,
          "insufficient_support": false
        },
        {
          "model": "deepseek-v4-pro",
          "n": 28,
          "successes": 24,
          "grit": 0.8571,
          "ci95_lo": 0.6851,
          "ci95_hi": 0.943,
          "insufficient_support": false
        },
        {
          "model": "gpt-5.6-luna",
          "n": 18,
          "successes": 14,
          "grit": 0.7778,
          "ci95_lo": 0.5478,
          "ci95_hi": 0.91,
          "insufficient_support": false
        },
        {
          "model": "claude-sonnet-5",
          "n": 22,
          "successes": 16,
          "grit": 0.7273,
          "ci95_lo": 0.5185,
          "ci95_hi": 0.8685,
          "insufficient_support": false
        },
        {
          "model": "gpt-5.6-sol",
          "n": 17,
          "successes": 12,
          "grit": 0.7059,
          "ci95_lo": 0.4687,
          "ci95_hi": 0.8672,
          "insufficient_support": false
        },
        {
          "model": "gpt-5.6-terra",
          "n": 16,
          "successes": 11,
          "grit": 0.6875,
          "ci95_lo": 0.444,
          "ci95_hi": 0.8584,
          "insufficient_support": false
        },
        {
          "model": "claude-haiku-4-5",
          "n": 18,
          "successes": 11,
          "grit": 0.6111,
          "ci95_lo": 0.3862,
          "ci95_hi": 0.797,
          "insufficient_support": false
        }
      ],
      "by_perturbation_class_perturbed": [
        {
          "perturbation_class": "objective_mutation",
          "n": 14,
          "successes": 11,
          "grit": 0.7857,
          "ci95_lo": 0.5241,
          "ci95_hi": 0.9243,
          "insufficient_support": false
        },
        {
          "perturbation_class": "process_perturbation",
          "n": 26,
          "successes": 15,
          "grit": 0.5769,
          "ci95_lo": 0.3895,
          "ci95_hi": 0.7446,
          "insufficient_support": false
        },
        {
          "perturbation_class": "specification_corruption",
          "n": 14,
          "successes": 12,
          "grit": 0.8571,
          "ci95_lo": 0.6006,
          "ci95_hi": 0.9599,
          "insufficient_support": false
        },
        {
          "perturbation_class": "story:early_degrade",
          "n": 80,
          "successes": 63,
          "grit": 0.7875,
          "ci95_lo": 0.6858,
          "ci95_hi": 0.8629,
          "insufficient_support": false
        }
      ],
      "by_operator_perturbed": [
        {
          "operator": "force_abandonment",
          "n": 3,
          "successes": 1,
          "grit": null,
          "ci95_lo": null,
          "ci95_hi": null,
          "insufficient_support": true
        },
        {
          "operator": "inject_alien_vocab",
          "n": 10,
          "successes": 5,
          "grit": 0.5,
          "ci95_lo": 0.2366,
          "ci95_hi": 0.7634,
          "insufficient_support": false
        },
        {
          "operator": "inject_competing_goal",
          "n": 7,
          "successes": 5,
          "grit": 0.7143,
          "ci95_lo": 0.3589,
          "ci95_hi": 0.9178,
          "insufficient_support": false
        },
        {
          "operator": "inject_phantom_success",
          "n": 7,
          "successes": 6,
          "grit": 0.8571,
          "ci95_lo": 0.4869,
          "ci95_hi": 0.9743,
          "insufficient_support": false
        },
        {
          "operator": "invert_constraint",
          "n": 7,
          "successes": 6,
          "grit": 0.8571,
          "ci95_lo": 0.4869,
          "ci95_hi": 0.9743,
          "insufficient_support": false
        },
        {
          "operator": "remove_critical_constraint",
          "n": 7,
          "successes": 6,
          "grit": 0.8571,
          "ci95_lo": 0.4869,
          "ci95_hi": 0.9743,
          "insufficient_support": false
        },
        {
          "operator": "reverse_causality",
          "n": 3,
          "successes": 3,
          "grit": null,
          "ci95_lo": null,
          "ci95_hi": null,
          "insufficient_support": true
        },
        {
          "operator": "shift_framing",
          "n": 10,
          "successes": 6,
          "grit": 0.6,
          "ci95_lo": 0.3127,
          "ci95_hi": 0.8318,
          "insufficient_support": false
        }
      ],
      "caveats": [
        "Only two perturbation strengths exist in the canonical corpus (0.0 and 0.5); G(s) is two points, not a dose-response curve.",
        "The s=0.0 level is baseline-only and comes entirely from the finding corpus, while s=0.5 mixes finding and story cells \u2014 read 'by_strength_finding_corpus' for the design-controlled comparison.",
        "A cell missing perturbation_strength or test_executed_success is excluded, never imputed; test_executed_success is the independent runner's verdict, never the agent's self-report.",
        "Rows with fewer than 5 cells report grit=null (insufficient_support) rather than an under-powered proportion.",
        "Observational corpus: no multiple-comparison correction across models, operators, or classes; differences are not claimed to be causal."
      ],
      "lab_contract": {
        "lab": "lab_grit.py",
        "input_dataset_id": "canonical_registry/finding+story",
        "registry_identity_sha256": "688d7b949481fb8775976eec5eef9c8fe9fcd59b8b21f9a02cd61a3108b2dd05",
        "resolved_input_sha256": "b1fcca3b2db24fec574383affacae45c6699065a11b660a1c86b702caeb6826a",
        "registry_version": "data-manifest/1.0+701rows",
        "metric_definition_version": "grit/v1",
        "n_resolved_records": 279,
        "n_eligible_records": 144,
        "n_used_records": 144,
        "n_excluded_records": 135,
        "n_unused_eligible_records": 0,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 135,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v4",
        "generated_at": "2026-08-21T21:18:17.132314+00:00"
      }
    },
    "quality_frontier": {
      "experiment_id": "lab_quality_frontier",
      "generated_at": "2026-08-21T23:18:17.543603",
      "summary": {
        "models": 7,
        "stories": 215,
        "analyses": 156,
        "lsp_available_cells": 0
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 22,
          "avg_cost": 0.068,
          "lsp_errors_per_cell": null,
          "lsp_cells": 0,
          "code_quality_score": 0.037,
          "cyclomatic_complexity": 475.455,
          "novelty_score": 0.87
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 24,
          "avg_cost": 0.092,
          "lsp_errors_per_cell": null,
          "lsp_cells": 0,
          "code_quality_score": 0.087,
          "cyclomatic_complexity": 262.583,
          "novelty_score": 0.876
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 37,
          "avg_cost": 0.159,
          "lsp_errors_per_cell": null,
          "lsp_cells": 0,
          "code_quality_score": 0.045,
          "cyclomatic_complexity": 309.378,
          "novelty_score": 0.845
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 20,
          "avg_cost": 1.015,
          "lsp_errors_per_cell": null,
          "lsp_cells": 0,
          "code_quality_score": 0.088,
          "cyclomatic_complexity": 233.8,
          "novelty_score": 0.901
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 14,
          "avg_cost": 1.537,
          "lsp_errors_per_cell": null,
          "lsp_cells": 0,
          "code_quality_score": 0.037,
          "cyclomatic_complexity": 381.571,
          "novelty_score": 0.842
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 23,
          "avg_cost": 3.987,
          "lsp_errors_per_cell": null,
          "lsp_cells": 0,
          "code_quality_score": 0.054,
          "cyclomatic_complexity": 297.348,
          "novelty_score": 0.917
        },
        {
          "model": "claude-sonnet-5",
          "cells": 16,
          "avg_cost": 4.776,
          "lsp_errors_per_cell": null,
          "lsp_cells": 0,
          "code_quality_score": 0.052,
          "cyclomatic_complexity": 375.375,
          "novelty_score": 0.789
        }
      ],
      "lab_contract": {
        "lab": "lab_quality_frontier.py",
        "input_dataset_id": "canonical_registry/story+analysis",
        "registry_identity_sha256": "688d7b949481fb8775976eec5eef9c8fe9fcd59b8b21f9a02cd61a3108b2dd05",
        "resolved_input_sha256": "58e642e6b38d847304d7f3dc8e649f53fd1126cb2222ed86c52393c0bd9c7c8f",
        "registry_version": "data-manifest/1.0+701rows",
        "metric_definition_version": "quality_frontier/v1",
        "n_resolved_records": 371,
        "n_eligible_records": 371,
        "n_used_records": 371,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v4",
        "generated_at": "2026-08-21T21:18:17.543873+00:00"
      }
    },
    "story_arc": {
      "experiment_id": "lab_story_arc",
      "generated_at": "2026-08-21T23:18:17.916347",
      "summary": {
        "snowball_factor": 2.26,
        "session1_cost": 0.1668,
        "session5_cost": 0.3773,
        "stories": 215
      },
      "sessions": [
        {
          "session_number": 1,
          "task_type": "greenfield",
          "n": 215,
          "avg_cost": 0.1668,
          "avg_tokens": 21663.0,
          "avg_tests": 4.5
        },
        {
          "session_number": 2,
          "task_type": "feature",
          "n": 215,
          "avg_cost": 0.232,
          "avg_tokens": 28432.0,
          "avg_tests": 8.6
        },
        {
          "session_number": 3,
          "task_type": "integration",
          "n": 215,
          "avg_cost": 0.3363,
          "avg_tokens": 34852.0,
          "avg_tests": 11.5
        },
        {
          "session_number": 4,
          "task_type": "refactor",
          "n": 211,
          "avg_cost": 0.339,
          "avg_tokens": 35257.0,
          "avg_tests": 11.0
        },
        {
          "session_number": 5,
          "task_type": "cross_cutting",
          "n": 211,
          "avg_cost": 0.3773,
          "avg_tokens": 40655.0,
          "avg_tests": 14.9
        }
      ],
      "by_condition": {
        "clean_s1": 0.1772,
        "clean_s2": 0.2418,
        "clean_s3": 0.3892,
        "clean_s4": 0.3522,
        "clean_s5": 0.4048,
        "early_degrade_s1": 0.1492,
        "early_degrade_s2": 0.2155,
        "early_degrade_s3": 0.2468,
        "early_degrade_s4": 0.3173,
        "early_degrade_s5": 0.3321
      },
      "by_model": {
        "claude-haiku-4-5": {
          "1": 0.1851,
          "2": 0.2663,
          "3": 0.2609,
          "4": 0.2557,
          "5": 0.3911
        },
        "claude-sonnet-5": {
          "1": 0.452,
          "2": 0.6493,
          "3": 1.075,
          "4": 0.9413,
          "5": 1.2859
        },
        "deepseek-v4-flash": {
          "1": 0.0061,
          "2": 0.0109,
          "3": 0.0187,
          "4": 0.0148,
          "5": 0.024
        },
        "deepseek-v4-pro": {
          "1": 0.0189,
          "2": 0.0245,
          "3": 0.0477,
          "4": 0.0311,
          "5": 0.0478
        },
        "gpt-5.6-luna": {
          "1": 0.0136,
          "2": 0.017,
          "3": 0.019,
          "4": 0.0213,
          "5": 0.0226
        },
        "gpt-5.6-sol": {
          "1": 0.4558,
          "2": 0.6406,
          "3": 0.9032,
          "4": 1.0115,
          "5": 0.8064
        },
        "gpt-5.6-terra": {
          "1": 0.1381,
          "2": 0.1625,
          "3": 0.2276,
          "4": 0.2454,
          "5": 0.2708
        }
      },
      "lab_contract": {
        "lab": "lab_story_arc.py",
        "input_dataset_id": "canonical_registry/story",
        "registry_identity_sha256": "688d7b949481fb8775976eec5eef9c8fe9fcd59b8b21f9a02cd61a3108b2dd05",
        "resolved_input_sha256": "7d2ab0fe4c18695fe26767d6e848f7a2e3f3a397d16b1e183594f70b9136c716",
        "registry_version": "data-manifest/1.0+701rows",
        "metric_definition_version": "story_arc/v1",
        "n_resolved_records": 215,
        "n_eligible_records": 215,
        "n_used_records": 215,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v4",
        "generated_at": "2026-08-21T21:18:17.916678+00:00"
      }
    },
    "verification_frontier": {
      "experiment_id": "lab_verification_frontier",
      "generated_at": "2026-08-21T23:18:18.648952",
      "summary": {
        "models": 7,
        "stories": 215,
        "cheapest": "deepseek-v4-flash",
        "most_verified": "claude-haiku-4-5",
        "pareto_frontier": [
          "deepseek-v4-flash",
          "claude-haiku-4-5"
        ]
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 31,
          "cost_cells": 31,
          "avg_cost": 0.074,
          "avg_tests": 57.0,
          "total_cost": 2.3083,
          "total_tests": 1767
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 34,
          "cost_cells": 34,
          "avg_cost": 0.094,
          "avg_tests": 14.294,
          "total_cost": 3.1806,
          "total_tests": 486
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 39,
          "cost_cells": 39,
          "avg_cost": 0.162,
          "avg_tests": 47.949,
          "total_cost": 6.3144,
          "total_tests": 1870
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 30,
          "cost_cells": 30,
          "avg_cost": 1.044,
          "avg_tests": 15.267,
          "total_cost": 31.3298,
          "total_tests": 458
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 24,
          "cost_cells": 20,
          "avg_cost": 1.631,
          "avg_tests": 127.875,
          "total_cost": 32.6168,
          "total_tests": 3069
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 30,
          "cost_cells": 30,
          "avg_cost": 3.817,
          "avg_tests": 24.4,
          "total_cost": 114.5238,
          "total_tests": 732
        },
        {
          "model": "claude-sonnet-5",
          "cells": 27,
          "cost_cells": 23,
          "avg_cost": 5.169,
          "avg_tests": 117.148,
          "total_cost": 118.8948,
          "total_tests": 3163
        }
      ],
      "lab_contract": {
        "lab": "lab_verification_frontier.py",
        "input_dataset_id": "canonical_registry/story",
        "registry_identity_sha256": "688d7b949481fb8775976eec5eef9c8fe9fcd59b8b21f9a02cd61a3108b2dd05",
        "resolved_input_sha256": "7d2ab0fe4c18695fe26767d6e848f7a2e3f3a397d16b1e183594f70b9136c716",
        "registry_version": "data-manifest/1.0+701rows",
        "metric_definition_version": "verification_frontier/v1",
        "n_resolved_records": 215,
        "n_eligible_records": 215,
        "n_used_records": 215,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v4",
        "generated_at": "2026-08-21T21:18:18.649199+00:00"
      }
    },
    "verification_value": {
      "experiment_id": "lab_verification_value",
      "generated_at": "2026-08-21T23:18:19.025019",
      "summary": {
        "correlation_tests_vs_worse_rate": -0.154,
        "cells": 106,
        "stories": 215,
        "reviews": 242
      },
      "rows": [
        {
          "model": "?",
          "tests": 0,
          "reviews": 432,
          "better_rate": 0.519,
          "worse_rate": 0.074
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 0,
          "reviews": 5,
          "better_rate": 0.2,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 136,
          "reviews": 5,
          "better_rate": 0.2,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 153,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 173,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 177,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 188,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 191,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 195,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 201,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 210,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 233,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.2
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 248,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 294,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 308,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.2
        },
        {
          "model": "claude-sonnet-5",
          "tests": 0,
          "reviews": 15,
          "better_rate": 0.2,
          "worse_rate": 0.133
        },
        {
          "model": "claude-sonnet-5",
          "tests": 70,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 76,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 152,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 164,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 165,
          "reviews": 10,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 193,
          "reviews": 10,
          "better_rate": 0.9,
          "worse_rate": 0.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 196,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
        },
        {
          "model": "claude-sonnet-5",
          "tests": 213,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 227,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 291,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
        },
        {
          "model": "claude-sonnet-5",
          "tests": 346,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 5,
          "reviews": 5,
          "better_rate": 0.2,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 7,
          "reviews": 25,
          "better_rate": 0.36,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 8,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 0.4
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 35,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 37,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 39,
          "reviews": 10,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 40,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 45,
          "reviews": 10,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 46,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 47,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 49,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 52,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 54,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 55,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 67,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 0,
          "reviews": 6,
          "better_rate": 0.333,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 2,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 3,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 4,
          "reviews": 20,
          "better_rate": 0.55,
          "worse_rate": 0.3
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 5,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 6,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 7,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 9,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.4
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 17,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 36,
          "reviews": 4,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 38,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 39,
          "reviews": 12,
          "better_rate": 0.667,
          "worse_rate": 0.083
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 43,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 44,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 46,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 47,
          "reviews": 10,
          "better_rate": 0.9,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 49,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 53,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 56,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 61,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.4
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 72,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 75,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 78,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 80,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 82,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 90,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 111,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 128,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 129,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 145,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 0,
          "reviews": 35,
          "better_rate": 0.571,
          "worse_rate": 0.114
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 7,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.2
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 8,
          "reviews": 10,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 9,
          "reviews": 20,
          "better_rate": 0.85,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 10,
          "reviews": 20,
          "better_rate": 0.85,
          "worse_rate": 0.1
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 11,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.2
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 13,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 14,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 16,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 25,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 62,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 0,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.2
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 1,
          "reviews": 10,
          "better_rate": 0.6,
          "worse_rate": 0.1
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 2,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 3,
          "reviews": 10,
          "better_rate": 0.5,
          "worse_rate": 0.2
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 4,
          "reviews": 10,
          "better_rate": 0.5,
          "worse_rate": 0.5
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 5,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 13,
          "reviews": 10,
          "better_rate": 0.9,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 14,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 15,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 17,
          "reviews": 20,
          "better_rate": 0.8,
          "worse_rate": 0.05
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 20,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 21,
          "reviews": 15,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 22,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 24,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 0,
          "reviews": 30,
          "better_rate": 0.533,
          "worse_rate": 0.233
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 9,
          "reviews": 5,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 10,
          "reviews": 10,
          "better_rate": 1.0,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 11,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 12,
          "reviews": 10,
          "better_rate": 0.9,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 15,
          "reviews": 10,
          "better_rate": 0.9,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 16,
          "reviews": 15,
          "better_rate": 0.733,
          "worse_rate": 0.2
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 17,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 18,
          "reviews": 10,
          "better_rate": 0.7,
          "worse_rate": 0.3
        }
      ],
      "lab_contract": {
        "lab": "lab_verification_value.py",
        "input_dataset_id": "canonical_registry/story+review",
        "registry_identity_sha256": "688d7b949481fb8775976eec5eef9c8fe9fcd59b8b21f9a02cd61a3108b2dd05",
        "resolved_input_sha256": "14648fd46fb445d31cd703e5734554043045b466936a968dd0bbc0a31df6b379",
        "registry_version": "data-manifest/1.0+701rows",
        "metric_definition_version": "verification_value/v1",
        "n_resolved_records": 457,
        "n_eligible_records": 457,
        "n_used_records": 457,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v4",
        "generated_at": "2026-08-21T21:18:19.025292+00:00"
      }
    }
  }
};
