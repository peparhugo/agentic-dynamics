/* Generated 2026-09-02 22:29:22 UTC by build_data.py */
/* DO NOT EDIT — regenerate with: python scripts/build_data.py */
window.DYNAMICS_DATA = {
  "_meta": {
    "generated_at": "2026-09-02T22:29:19.152566+00:00",
    "provenance_note": "All values tagged [M]easured, [C]omputed, [H]euristic, or e[X]ternal. See methodology.html."
  },
  "summary": {
    "worktrees_total": 1837,
    "sessions_total": 1027,
    "game_reports": 348,
    "total_cost": 309.1685,
    "architectures": 3,
    "variants": 7,
    "stories_total": 207,
    "stories_unique": 142,
    "stories_re_runs": 65,
    "story_sessions": 1027,
    "story_total_cost": 309.1685,
    "configs": 0,
    "registry_current_records": 207,
    "resolved_measurement_payloads": 207,
    "eligible_records": 207,
    "records_used": 207,
    "unresolved_waivered": 0,
    "canonical_findings": 64,
    "contaminated_tombstones": 77,
    "no_measurement_tombstones": 0,
    "tombstones_total": 95,
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
      "contaminated_tombstones": "M",
      "no_measurement_tombstones": "M",
      "tombstones_total": "M"
    }
  },
  "resolution_report": {
    "expected_current": 513,
    "resolved": 513,
    "missing": 0,
    "unreadable": 0,
    "ambiguous": 0,
    "duplicate": 0,
    "waivers": []
  },
  "publication_contract": {
    "registry_identity": "dfff942e34e5143e94ef238550994330059bbf4010e1c64555b5f72d59e75406",
    "resolved_input_identity": "ceb34869d5699a53c4b929cf03006ac9222e65f4e181722142e91e2fea2e0901",
    "data_integrity_policy_version": "data-integrity/v1",
    "normalization_version": "canonical-projection/v2",
    "waiver_digest": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "generator_source_tree_identity": "b82f48cd50e79b3c20045627db7d0ea2a8d82d2d3af9fc61318b1343aa1f8c1c"
  },
  "public_statistics": {
    "story_sessions": 1027,
    "stories_total": 207,
    "story_total_cost": 309.1685,
    "db_sessions_total": 6333,
    "game_reports": 348,
    "model_variants": 7,
    "providers": 3,
    "experiment_configs": 0,
    "experiment_specs": 11,
    "workflow_specs": 172,
    "perturbation_operators": 10,
    "lab_books": 21,
    "lab_books_canonical": 8,
    "lab_books_quarantined": 12,
    "measured_spend_usd": 309.17,
    "measured_spend_scope": "story-corpus",
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
      "measured_spend_usd": "M",
      "measured_spend_scope": "P"
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
      "cost_captured_records": 31,
      "total_records": 31,
      "total_captured_cost": 2.308294,
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
      "strategy_cons": 1,
      "strategy_expl": 30,
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
      "cost_captured_records": 34,
      "total_records": 34,
      "total_captured_cost": 3.180633,
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
      "strategy_expl": 34,
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
      "cost_captured_records": 39,
      "total_records": 39,
      "total_captured_cost": 6.314403,
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
      "strategy_expl": 39,
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
      "cost_captured_records": 30,
      "total_records": 30,
      "total_captured_cost": 31.329782,
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
      "strategy_expl": 30,
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
      "cells": 20,
      "unique_cells": 16,
      "re_runs": 4,
      "sessions": 100,
      "total_cost": 32.616808,
      "avg_cost": 1.63084,
      "cost_cells": 20,
      "avg_captured_cost": 1.63084,
      "cost_captured_records": 20,
      "total_records": 20,
      "total_captured_cost": 32.616808,
      "cost_coverage": 1.0,
      "avg_cache_hit": 0.989,
      "avg_tests": 153.4,
      "avg_test_code_ratio": 1.465,
      "avg_tok_per_session": 16298.0,
      "avg_duration_s": 1032.0,
      "avg_code_lines": 1584.0,
      "final_tests_discovered": 3069,
      "test_executions_passed": 0,
      "test_executions_run": 0,
      "pass_rate": "unknown",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 0.326168,
      "avg_loc": 1584.0,
      "avg_energy_j": 18526.7,
      "avg_energy_j_per_loc": 11.7,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 3,
      "strategy_expl": 17,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 20,
      "reports_valid": 20,
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
      "cost_captured_records": 30,
      "total_records": 30,
      "total_captured_cost": 114.52382,
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
      "strategy_expl": 30,
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
      "cells": 23,
      "unique_cells": 17,
      "re_runs": 6,
      "sessions": 115,
      "total_cost": 118.894751,
      "avg_cost": 5.169337,
      "cost_cells": 23,
      "avg_captured_cost": 5.169337,
      "cost_captured_records": 23,
      "total_records": 23,
      "total_captured_cost": 118.894751,
      "cost_coverage": 1.0,
      "avg_cache_hit": 0.986,
      "avg_tests": 137.5,
      "avg_test_code_ratio": 0.815,
      "avg_tok_per_session": 21605.0,
      "avg_duration_s": 1245.0,
      "avg_code_lines": 1954.0,
      "final_tests_discovered": 3163,
      "test_executions_passed": 455,
      "test_executions_run": 455,
      "pass_rate": "100% (455/455)",
      "pass_rate_scope": "weighted over repeated session-level test executions (each session re-runs the suite; the count is summed across sessions)",
      "avg_cost_per_session": 1.033867,
      "avg_loc": 1954.0,
      "avg_energy_j": 24763.6,
      "avg_energy_j_per_loc": 12.67,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 3,
      "strategy_expl": 20,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 23,
      "reports_valid": 23,
      "reports_narrated": 0
    }
  ],
  "perturbation_models": [
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
      "avg_captured_cost": 0.009603,
      "total_captured_cost": 0.067223,
      "cost_captured_records": 7,
      "total_records": 7,
      "cost_coverage": 1.0,
      "cost_ci95": [
        0.0083,
        0.0111
      ],
      "pass_rate": "98% (309/315) [tests]",
      "strategy_cons": 1,
      "strategy_expl": 4,
      "strategy_waste": 0,
      "strategy_efficient": 1,
      "strategy_unknown": 1,
      "avg_loc": 1143,
      "avg_correctness": 0.88,
      "avg_thinking_ratio": 0.228,
      "avg_escape": 0.63,
      "avg_arch_divergence": 0.667,
      "avg_composite_score": 0.793,
      "avg_energy_j": 7992.3,
      "avg_energy_j_per_loc": 6.99,
      "correctness_per_dollar": 98.5565,
      "avg_quality_per_joule": 0.0001,
      "avg_constraints_met": 8.6,
      "avg_constraints_total": 9.0,
      "correctness_coverage": {
        "value": 0.88,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "thinking_ratio_coverage": {
        "value": 0.228,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "escape_coverage": {
        "value": 0.63,
        "n_available": 6,
        "n_total": 7,
        "coverage": 0.8571
      },
      "architecture_divergence_coverage": {
        "value": 0.667,
        "n_available": 6,
        "n_total": 7,
        "coverage": 0.8571
      },
      "composite_score_coverage": {
        "value": 0.793,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "energy_j_coverage": {
        "value": 7992.3,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "quality_per_joule_coverage": {
        "value": 0.0001,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
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
        "avg_captured_cost": "C",
        "total_captured_cost": "C",
        "cost_captured_records": "M",
        "total_records": "M",
        "cost_coverage": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_correctness": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "correctness_coverage": "C",
        "thinking_ratio_coverage": "C",
        "escape_coverage": "C",
        "architecture_divergence_coverage": "C",
        "composite_score_coverage": "C",
        "energy_j_coverage": "C",
        "quality_per_joule_coverage": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "strategy_unknown": "C",
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
      "avg_captured_cost": 0.017297,
      "total_captured_cost": 0.121081,
      "cost_captured_records": 7,
      "total_records": 7,
      "cost_coverage": 1.0,
      "cost_ci95": [
        0.0152,
        0.0196
      ],
      "pass_rate": "100% (53/53) [tests]",
      "strategy_cons": 0,
      "strategy_expl": 0,
      "strategy_waste": 0,
      "strategy_efficient": 6,
      "strategy_unknown": 1,
      "avg_loc": 334,
      "avg_correctness": 1.0,
      "avg_thinking_ratio": 0.021,
      "avg_escape": 0.34,
      "avg_arch_divergence": 0.231,
      "avg_composite_score": 0.838,
      "avg_energy_j": 4060.4,
      "avg_energy_j_per_loc": 12.16,
      "correctness_per_dollar": 59.547,
      "avg_quality_per_joule": 0.0002,
      "avg_constraints_met": 8.9,
      "avg_constraints_total": 9.0,
      "correctness_coverage": {
        "value": 1.0,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "thinking_ratio_coverage": {
        "value": 0.021,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "escape_coverage": {
        "value": 0.34,
        "n_available": 6,
        "n_total": 7,
        "coverage": 0.8571
      },
      "architecture_divergence_coverage": {
        "value": 0.231,
        "n_available": 6,
        "n_total": 7,
        "coverage": 0.8571
      },
      "composite_score_coverage": {
        "value": 0.838,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "energy_j_coverage": {
        "value": 4060.4,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "quality_per_joule_coverage": {
        "value": 0.0002,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
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
        "avg_captured_cost": "C",
        "total_captured_cost": "C",
        "cost_captured_records": "M",
        "total_records": "M",
        "cost_coverage": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_correctness": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "correctness_coverage": "C",
        "thinking_ratio_coverage": "C",
        "escape_coverage": "C",
        "architecture_divergence_coverage": "C",
        "composite_score_coverage": "C",
        "energy_j_coverage": "C",
        "quality_per_joule_coverage": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "strategy_unknown": "C",
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
      "avg_captured_cost": 0.016934,
      "total_captured_cost": 0.203213,
      "cost_captured_records": 12,
      "total_records": 12,
      "cost_coverage": 1.0,
      "cost_ci95": [
        0.0143,
        0.0195
      ],
      "pass_rate": "100% (270/271) [tests]",
      "strategy_cons": 0,
      "strategy_expl": 8,
      "strategy_waste": 0,
      "strategy_efficient": 2,
      "strategy_unknown": 2,
      "avg_loc": 636,
      "avg_correctness": 1.0,
      "avg_thinking_ratio": 0.211,
      "avg_escape": 0.69,
      "avg_arch_divergence": 0.775,
      "avg_composite_score": 0.772,
      "avg_energy_j": 5015.1,
      "avg_energy_j_per_loc": 7.89,
      "correctness_per_dollar": 64.9708,
      "avg_quality_per_joule": 0.0002,
      "avg_constraints_met": 6.2,
      "avg_constraints_total": 7.8,
      "correctness_coverage": {
        "value": 1.0,
        "n_available": 12,
        "n_total": 12,
        "coverage": 1.0
      },
      "thinking_ratio_coverage": {
        "value": 0.211,
        "n_available": 12,
        "n_total": 12,
        "coverage": 1.0
      },
      "escape_coverage": {
        "value": 0.69,
        "n_available": 10,
        "n_total": 12,
        "coverage": 0.8333
      },
      "architecture_divergence_coverage": {
        "value": 0.775,
        "n_available": 10,
        "n_total": 12,
        "coverage": 0.8333
      },
      "composite_score_coverage": {
        "value": 0.772,
        "n_available": 12,
        "n_total": 12,
        "coverage": 1.0
      },
      "energy_j_coverage": {
        "value": 5015.1,
        "n_available": 12,
        "n_total": 12,
        "coverage": 1.0
      },
      "quality_per_joule_coverage": {
        "value": 0.0002,
        "n_available": 12,
        "n_total": 12,
        "coverage": 1.0
      },
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
        "avg_captured_cost": "C",
        "total_captured_cost": "C",
        "cost_captured_records": "M",
        "total_records": "M",
        "cost_coverage": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_correctness": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "correctness_coverage": "C",
        "thinking_ratio_coverage": "C",
        "escape_coverage": "C",
        "architecture_divergence_coverage": "C",
        "composite_score_coverage": "C",
        "energy_j_coverage": "C",
        "quality_per_joule_coverage": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "strategy_unknown": "C",
        "pass_rate": "M"
      }
    },
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
      "avg_cost": 0.3097,
      "total_cost": 0.3097,
      "avg_captured_cost": 0.309695,
      "total_captured_cost": 0.309695,
      "cost_captured_records": 1,
      "total_records": 7,
      "cost_coverage": 0.1429,
      "cost_ci95": null,
      "pass_rate": null,
      "strategy_cons": 0,
      "strategy_expl": 6,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "strategy_unknown": 1,
      "avg_loc": 1270,
      "avg_correctness": 1.0,
      "avg_thinking_ratio": 0.0,
      "avg_escape": 0.77,
      "avg_arch_divergence": 0.972,
      "avg_composite_score": 0.8,
      "avg_energy_j": 5246.7,
      "avg_energy_j_per_loc": 4.13,
      "correctness_per_dollar": 3.229,
      "avg_quality_per_joule": 0.0001,
      "avg_constraints_met": 8.9,
      "avg_constraints_total": 9.0,
      "correctness_coverage": {
        "value": 1.0,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "thinking_ratio_coverage": {
        "value": 0.0,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "escape_coverage": {
        "value": 0.77,
        "n_available": 6,
        "n_total": 7,
        "coverage": 0.8571
      },
      "architecture_divergence_coverage": {
        "value": 0.972,
        "n_available": 6,
        "n_total": 7,
        "coverage": 0.8571
      },
      "composite_score_coverage": {
        "value": 0.8,
        "n_available": 7,
        "n_total": 7,
        "coverage": 1.0
      },
      "energy_j_coverage": {
        "value": 5246.7,
        "n_available": 1,
        "n_total": 7,
        "coverage": 0.1429
      },
      "quality_per_joule_coverage": {
        "value": 0.0001,
        "n_available": 1,
        "n_total": 7,
        "coverage": 0.1429
      },
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
        "avg_captured_cost": "C",
        "total_captured_cost": "C",
        "cost_captured_records": "M",
        "total_records": "M",
        "cost_coverage": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_correctness": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "correctness_coverage": "C",
        "thinking_ratio_coverage": "C",
        "escape_coverage": "C",
        "architecture_divergence_coverage": "C",
        "composite_score_coverage": "C",
        "energy_j_coverage": "C",
        "quality_per_joule_coverage": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "strategy_unknown": "C",
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
      "avg_captured_cost": 0.35219,
      "total_captured_cost": 6.691605,
      "cost_captured_records": 19,
      "total_records": 19,
      "cost_coverage": 1.0,
      "cost_ci95": [
        0.2841,
        0.415
      ],
      "pass_rate": "100% (137/137) [tests]",
      "strategy_cons": 1,
      "strategy_expl": 4,
      "strategy_waste": 0,
      "strategy_efficient": 11,
      "strategy_unknown": 3,
      "avg_loc": 474,
      "avg_correctness": 0.97,
      "avg_thinking_ratio": 0.022,
      "avg_escape": 0.46,
      "avg_arch_divergence": 0.397,
      "avg_composite_score": 0.808,
      "avg_energy_j": 3820.4,
      "avg_energy_j_per_loc": 8.06,
      "correctness_per_dollar": 4.9624,
      "avg_quality_per_joule": 0.0003,
      "avg_constraints_met": 7.8,
      "avg_constraints_total": 8.2,
      "correctness_coverage": {
        "value": 0.97,
        "n_available": 19,
        "n_total": 19,
        "coverage": 1.0
      },
      "thinking_ratio_coverage": {
        "value": 0.022,
        "n_available": 19,
        "n_total": 19,
        "coverage": 1.0
      },
      "escape_coverage": {
        "value": 0.46,
        "n_available": 16,
        "n_total": 19,
        "coverage": 0.8421
      },
      "architecture_divergence_coverage": {
        "value": 0.397,
        "n_available": 16,
        "n_total": 19,
        "coverage": 0.8421
      },
      "composite_score_coverage": {
        "value": 0.808,
        "n_available": 19,
        "n_total": 19,
        "coverage": 1.0
      },
      "energy_j_coverage": {
        "value": 3820.4,
        "n_available": 19,
        "n_total": 19,
        "coverage": 1.0
      },
      "quality_per_joule_coverage": {
        "value": 0.0003,
        "n_available": 19,
        "n_total": 19,
        "coverage": 1.0
      },
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
        "avg_captured_cost": "C",
        "total_captured_cost": "C",
        "cost_captured_records": "M",
        "total_records": "M",
        "cost_coverage": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_correctness": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "correctness_coverage": "C",
        "thinking_ratio_coverage": "C",
        "escape_coverage": "C",
        "architecture_divergence_coverage": "C",
        "composite_score_coverage": "C",
        "energy_j_coverage": "C",
        "quality_per_joule_coverage": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "strategy_unknown": "C",
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
      "avg_cost": 0.5255,
      "total_cost": 3.6785,
      "avg_captured_cost": 0.525497,
      "total_captured_cost": 3.678477,
      "cost_captured_records": 7,
      "total_records": 12,
      "cost_coverage": 0.5833,
      "cost_ci95": [
        0.2899,
        0.7756
      ],
      "pass_rate": null,
      "strategy_cons": 2,
      "strategy_expl": 2,
      "strategy_waste": 0,
      "strategy_efficient": 6,
      "strategy_unknown": 2,
      "avg_loc": 691,
      "avg_correctness": 0.92,
      "avg_thinking_ratio": 0.0,
      "avg_escape": 0.55,
      "avg_arch_divergence": 0.467,
      "avg_composite_score": 0.757,
      "avg_energy_j": 2782.0,
      "avg_energy_j_per_loc": 4.03,
      "correctness_per_dollar": 2.6094,
      "avg_quality_per_joule": 0.0004,
      "avg_constraints_met": 6.7,
      "avg_constraints_total": 7.8,
      "correctness_coverage": {
        "value": 0.92,
        "n_available": 12,
        "n_total": 12,
        "coverage": 1.0
      },
      "thinking_ratio_coverage": {
        "value": 0.0,
        "n_available": 12,
        "n_total": 12,
        "coverage": 1.0
      },
      "escape_coverage": {
        "value": 0.55,
        "n_available": 10,
        "n_total": 12,
        "coverage": 0.8333
      },
      "architecture_divergence_coverage": {
        "value": 0.467,
        "n_available": 10,
        "n_total": 12,
        "coverage": 0.8333
      },
      "composite_score_coverage": {
        "value": 0.757,
        "n_available": 12,
        "n_total": 12,
        "coverage": 1.0
      },
      "energy_j_coverage": {
        "value": 2782.0,
        "n_available": 7,
        "n_total": 12,
        "coverage": 0.5833
      },
      "quality_per_joule_coverage": {
        "value": 0.0004,
        "n_available": 7,
        "n_total": 12,
        "coverage": 0.5833
      },
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
        "avg_captured_cost": "C",
        "total_captured_cost": "C",
        "cost_captured_records": "M",
        "total_records": "M",
        "cost_coverage": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_correctness": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_arch_divergence": "C",
        "avg_composite_score": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "correctness_coverage": "C",
        "thinking_ratio_coverage": "C",
        "escape_coverage": "C",
        "architecture_divergence_coverage": "C",
        "composite_score_coverage": "C",
        "energy_j_coverage": "C",
        "quality_per_joule_coverage": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "strategy_unknown": "C",
        "pass_rate": null
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
      1584.0,
      739.0,
      1954.0
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
      20,
      30,
      23
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
    "total_valid_reports": 207,
    "total_reports_analyzed": 207,
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
          "avg_captured_cost": 0.014741,
          "total_captured_cost": 0.029483,
          "cost_captured_records": 2,
          "total_records": 2,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.068,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": 0.68,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "architecture_divergence_coverage": {
            "value": 0.75,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "composite_score_coverage": {
            "value": 0.762,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 3582.8,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "low_n": true
        },
        "Claude Sonnet 5": {
          "n": 2,
          "avg_cost": null,
          "cost_ci95": null,
          "avg_escape": 0.32,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": null,
          "avg_captured_cost": null,
          "total_captured_cost": 0,
          "cost_captured_records": 0,
          "total_records": 2,
          "cost_coverage": 0.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": 0.32,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "architecture_divergence_coverage": {
            "value": 0.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "composite_score_coverage": {
            "value": 0.783,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
          "quality_per_joule_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
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
          "avg_captured_cost": 0.243143,
          "total_captured_cost": 0.486286,
          "cost_captured_records": 2,
          "total_records": 2,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.023,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": 0.42,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "architecture_divergence_coverage": {
            "value": 0.3,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "composite_score_coverage": {
            "value": 0.845,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 3910.1,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
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
          "avg_captured_cost": 0.009605,
          "total_captured_cost": 0.01921,
          "cost_captured_records": 2,
          "total_records": 2,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 0.99,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.292,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": 0.6,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "architecture_divergence_coverage": {
            "value": 0.5,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "composite_score_coverage": {
            "value": 0.79,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 8231.7,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0001,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "low_n": true
        },
        "anthropic/claude-haiku-4-5": {
          "n": 2,
          "avg_cost": null,
          "cost_ci95": null,
          "avg_escape": 0.79,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": null,
          "avg_captured_cost": null,
          "total_captured_cost": 0,
          "cost_captured_records": 0,
          "total_records": 2,
          "cost_coverage": 0.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": 0.79,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "architecture_divergence_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "composite_score_coverage": {
            "value": 0.813,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
          "quality_per_joule_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
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
          "avg_captured_cost": 0.51495,
          "total_captured_cost": 1.0299,
          "cost_captured_records": 2,
          "total_records": 2,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.016,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": 0.44,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "architecture_divergence_coverage": {
            "value": 0.45,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "composite_score_coverage": {
            "value": 0.823,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 4659.6,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
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
          "avg_captured_cost": 0.015643,
          "total_captured_cost": 0.031287,
          "cost_captured_records": 2,
          "total_records": 2,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.024,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": 0.37,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "architecture_divergence_coverage": {
            "value": 0.3,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "composite_score_coverage": {
            "value": 0.835,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 3555.4,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "low_n": true
        }
      }
    },
    "baseline": {
      "perturbation_class": "baseline",
      "models": {
        "Claude Sonnet 5": {
          "n": 2,
          "avg_cost": 0.6261,
          "cost_ci95": null,
          "avg_escape": null,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": 3248.2,
          "avg_captured_cost": 0.626113,
          "total_captured_cost": 0.626113,
          "cost_captured_records": 1,
          "total_records": 2,
          "cost_coverage": 0.5,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
          "architecture_divergence_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
          "composite_score_coverage": {
            "value": 0.714,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 3248.2,
            "n_available": 1,
            "n_total": 2,
            "coverage": 0.5
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 1,
            "n_total": 2,
            "coverage": 0.5
          },
          "low_n": true
        },
        "DeepSeek v4 Pro": {
          "n": 2,
          "avg_cost": 0.0134,
          "cost_ci95": null,
          "avg_escape": null,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.148,
          "avg_energy_j": 3558.1,
          "avg_captured_cost": 0.01339,
          "total_captured_cost": 0.02678,
          "cost_captured_records": 2,
          "total_records": 2,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.148,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
          "architecture_divergence_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
          "composite_score_coverage": {
            "value": 0.747,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 3558.1,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "low_n": true
        },
        "openai/gpt-5.6-sol": {
          "n": 2,
          "avg_cost": 0.458,
          "cost_ci95": null,
          "avg_escape": null,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.021,
          "avg_energy_j": 4111.1,
          "avg_captured_cost": 0.457954,
          "total_captured_cost": 0.915907,
          "cost_captured_records": 2,
          "total_records": 2,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.021,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
          "architecture_divergence_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 2,
            "coverage": 0.0
          },
          "composite_score_coverage": {
            "value": 0.763,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 4111.1,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 2,
            "n_total": 2,
            "coverage": 1.0
          },
          "low_n": true
        },
        "GPT-5.6 Luna": {
          "n": 1,
          "avg_cost": 0.0168,
          "cost_ci95": null,
          "avg_escape": null,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.019,
          "avg_energy_j": 4056.5,
          "avg_captured_cost": 0.016778,
          "total_captured_cost": 0.016778,
          "cost_captured_records": 1,
          "total_records": 1,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.019,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "architecture_divergence_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "composite_score_coverage": {
            "value": 0.789,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 4056.5,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "low_n": true
        },
        "anthropic/claude-haiku-4-5": {
          "n": 1,
          "avg_cost": null,
          "cost_ci95": null,
          "avg_escape": null,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": null,
          "avg_captured_cost": null,
          "total_captured_cost": 0,
          "cost_captured_records": 0,
          "total_records": 1,
          "cost_coverage": 0.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.0,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "architecture_divergence_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "composite_score_coverage": {
            "value": 0.747,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "quality_per_joule_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "low_n": true
        },
        "DeepSeek v4 Flash": {
          "n": 1,
          "avg_cost": 0.012,
          "cost_ci95": null,
          "avg_escape": null,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.186,
          "avg_energy_j": 9024.4,
          "avg_captured_cost": 0.01195,
          "total_captured_cost": 0.01195,
          "cost_captured_records": 1,
          "total_records": 1,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.186,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "architecture_divergence_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "composite_score_coverage": {
            "value": 0.738,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 9024.4,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0001,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "low_n": true
        },
        "openai/gpt-5.6-terra": {
          "n": 1,
          "avg_cost": 0.2095,
          "cost_ci95": null,
          "avg_escape": null,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.017,
          "avg_energy_j": 3602.8,
          "avg_captured_cost": 0.209516,
          "total_captured_cost": 0.209516,
          "cost_captured_records": 1,
          "total_records": 1,
          "cost_coverage": 1.0,
          "correctness_coverage": {
            "value": 1.0,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "thinking_ratio_coverage": {
            "value": 0.017,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "escape_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "architecture_divergence_coverage": {
            "value": null,
            "n_available": 0,
            "n_total": 1,
            "coverage": 0.0
          },
          "composite_score_coverage": {
            "value": 0.783,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "energy_j_coverage": {
            "value": 3602.8,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
          "quality_per_joule_coverage": {
            "value": 0.0002,
            "n_available": 1,
            "n_total": 1,
            "coverage": 1.0
          },
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
        "avg_captured_cost": 0.016247,
        "total_captured_cost": 0.097485,
        "cost_captured_records": 6,
        "total_records": 6,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.254,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.67,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.108776,
        "total_captured_cost": 0.217552,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 0.7,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.026,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.57,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.007888,
        "total_captured_cost": 0.015776,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.119,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.75,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "avg_narration_penalty": null
      },
      "anthropic/claude-haiku-4-5": {
        "n": 2,
        "low_n": true,
        "avg_cost": null,
        "cost_ci95": null,
        "avg_escape": 0.74,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 1146,
        "avg_tokens": 0,
        "avg_captured_cost": null,
        "total_captured_cost": 0,
        "cost_captured_records": 0,
        "total_records": 2,
        "cost_coverage": 0.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.74,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.389425,
        "total_captured_cost": 2.33655,
        "cost_captured_records": 6,
        "total_records": 6,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.029,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.5,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
        "avg_narration_penalty": null
      },
      "Claude Sonnet 5": {
        "n": 6,
        "low_n": false,
        "avg_cost": 0.3675,
        "cost_ci95": [
          0.1777,
          0.5574
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
        "avg_captured_cost": 0.367538,
        "total_captured_cost": 1.837691,
        "cost_captured_records": 5,
        "total_records": 6,
        "cost_coverage": 0.8333,
        "correctness_coverage": {
          "value": 0.83,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.0,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.63,
          "n_available": 6,
          "n_total": 6,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.019588,
        "total_captured_cost": 0.039175,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.016,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.37,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "avg_narration_penalty": null
      }
    },
    "specification_corruption": {
      "Claude Sonnet 5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 1.2147,
        "cost_ci95": null,
        "avg_escape": 0.54,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 856,
        "avg_tokens": 10494,
        "avg_captured_cost": 1.214673,
        "total_captured_cost": 1.214673,
        "cost_captured_records": 1,
        "total_records": 2,
        "cost_coverage": 0.5,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.54,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.550508,
        "total_captured_cost": 1.101016,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.012,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.46,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.197439,
        "total_captured_cost": 0.394879,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.019,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.32,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.009605,
        "total_captured_cost": 0.01921,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 0.99,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.292,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.6,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "avg_narration_penalty": null
      },
      "anthropic/claude-haiku-4-5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.3097,
        "cost_ci95": null,
        "avg_escape": 0.76,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 1416,
        "avg_tokens": 11490,
        "avg_captured_cost": 0.309695,
        "total_captured_cost": 0.309695,
        "cost_captured_records": 1,
        "total_records": 2,
        "cost_coverage": 0.5,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.76,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.014741,
        "total_captured_cost": 0.029483,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.068,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.68,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.015643,
        "total_captured_cost": 0.031287,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.024,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.37,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.024733,
        "total_captured_cost": 0.049466,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.287,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.77,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.010144,
        "total_captured_cost": 0.020287,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 0.58,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.294,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.56,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.01692,
        "total_captured_cost": 0.033841,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.024,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.26,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "avg_narration_penalty": null
      },
      "Claude Sonnet 5": {
        "n": 2,
        "low_n": true,
        "avg_cost": null,
        "cost_ci95": null,
        "avg_escape": 0.32,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 1156,
        "avg_tokens": 0,
        "avg_captured_cost": null,
        "total_captured_cost": 0,
        "cost_captured_records": 0,
        "total_records": 2,
        "cost_coverage": 0.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.32,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.51495,
        "total_captured_cost": 1.0299,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.016,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.44,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
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
        "avg_captured_cost": 0.243143,
        "total_captured_cost": 0.486286,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.023,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.42,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "avg_narration_penalty": null
      },
      "anthropic/claude-haiku-4-5": {
        "n": 2,
        "low_n": true,
        "avg_cost": null,
        "cost_ci95": null,
        "avg_escape": 0.79,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 1432,
        "avg_tokens": 0,
        "avg_captured_cost": null,
        "total_captured_cost": 0,
        "cost_captured_records": 0,
        "total_records": 2,
        "cost_coverage": 0.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": 0.79,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "avg_narration_penalty": null
      }
    },
    "baseline": {
      "Claude Sonnet 5": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.6261,
        "cost_ci95": null,
        "avg_escape": null,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 753,
        "avg_tokens": 7078,
        "avg_captured_cost": 0.626113,
        "total_captured_cost": 0.626113,
        "cost_captured_records": 1,
        "total_records": 2,
        "cost_coverage": 0.5,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": null,
          "n_available": 0,
          "n_total": 2,
          "coverage": 0.0
        },
        "avg_narration_penalty": null
      },
      "DeepSeek v4 Pro": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.0134,
        "cost_ci95": null,
        "avg_escape": null,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.148,
        "avg_loc": 534,
        "avg_tokens": 18392,
        "avg_captured_cost": 0.01339,
        "total_captured_cost": 0.02678,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.148,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": null,
          "n_available": 0,
          "n_total": 2,
          "coverage": 0.0
        },
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-sol": {
        "n": 2,
        "low_n": true,
        "avg_cost": 0.458,
        "cost_ci95": null,
        "avg_escape": null,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.021,
        "avg_loc": 568,
        "avg_tokens": 31681,
        "avg_captured_cost": 0.457954,
        "total_captured_cost": 0.915907,
        "cost_captured_records": 2,
        "total_records": 2,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.021,
          "n_available": 2,
          "n_total": 2,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": null,
          "n_available": 0,
          "n_total": 2,
          "coverage": 0.0
        },
        "avg_narration_penalty": null
      },
      "GPT-5.6 Luna": {
        "n": 1,
        "low_n": true,
        "avg_cost": 0.0168,
        "cost_ci95": null,
        "avg_escape": null,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.019,
        "avg_loc": 314,
        "avg_tokens": 35520,
        "avg_captured_cost": 0.016778,
        "total_captured_cost": 0.016778,
        "cost_captured_records": 1,
        "total_records": 1,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 1,
          "n_total": 1,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.019,
          "n_available": 1,
          "n_total": 1,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": null,
          "n_available": 0,
          "n_total": 1,
          "coverage": 0.0
        },
        "avg_narration_penalty": null
      },
      "anthropic/claude-haiku-4-5": {
        "n": 1,
        "low_n": true,
        "avg_cost": null,
        "cost_ci95": null,
        "avg_escape": null,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 902,
        "avg_tokens": 0,
        "avg_captured_cost": null,
        "total_captured_cost": 0,
        "cost_captured_records": 0,
        "total_records": 1,
        "cost_coverage": 0.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 1,
          "n_total": 1,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.0,
          "n_available": 1,
          "n_total": 1,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": null,
          "n_available": 0,
          "n_total": 1,
          "coverage": 0.0
        },
        "avg_narration_penalty": null
      },
      "DeepSeek v4 Flash": {
        "n": 1,
        "low_n": true,
        "avg_cost": 0.012,
        "cost_ci95": null,
        "avg_escape": null,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.186,
        "avg_loc": 1510,
        "avg_tokens": 38442,
        "avg_captured_cost": 0.01195,
        "total_captured_cost": 0.01195,
        "cost_captured_records": 1,
        "total_records": 1,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 1,
          "n_total": 1,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.186,
          "n_available": 1,
          "n_total": 1,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": null,
          "n_available": 0,
          "n_total": 1,
          "coverage": 0.0
        },
        "avg_narration_penalty": null
      },
      "openai/gpt-5.6-terra": {
        "n": 1,
        "low_n": true,
        "avg_cost": 0.2095,
        "cost_ci95": null,
        "avg_escape": null,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.017,
        "avg_loc": 343,
        "avg_tokens": 29140,
        "avg_captured_cost": 0.209516,
        "total_captured_cost": 0.209516,
        "cost_captured_records": 1,
        "total_records": 1,
        "cost_coverage": 1.0,
        "correctness_coverage": {
          "value": 1.0,
          "n_available": 1,
          "n_total": 1,
          "coverage": 1.0
        },
        "thinking_ratio_coverage": {
          "value": 0.017,
          "n_available": 1,
          "n_total": 1,
          "coverage": 1.0
        },
        "escape_coverage": {
          "value": null,
          "n_available": 0,
          "n_total": 1,
          "coverage": 0.0
        },
        "avg_narration_penalty": null
      }
    }
  },
  "energy_ranking": [
    {
      "id": "anthropic/claude-haiku-4-5",
      "label": "anthropic/claude-haiku-4-5",
      "avg_energy_j": 18526.7,
      "avg_energy_j_per_loc": 11.7,
      "avg_cost": 1.63084,
      "avg_loc": 1584.0
    },
    {
      "id": "anthropic/claude-sonnet-5",
      "label": "Claude Sonnet 5",
      "avg_energy_j": 24763.6,
      "avg_energy_j_per_loc": 12.67,
      "avg_cost": 5.169337,
      "avg_loc": 1954.0
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
    "unknown": 10,
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
            "n_outcome": 5,
            "n_cost": 5,
            "avg_correctness": 1.0,
            "avg_cost": 0.40127,
            "efficiency": 2.49
          },
          "anthropic/claude-sonnet-5": {
            "n": 5,
            "n_outcome": 5,
            "n_cost": 5,
            "avg_correctness": 0.92,
            "avg_cost": 0.476491,
            "efficiency": 1.93
          },
          "deepseek/deepseek-v4-pro": {
            "n": 5,
            "n_outcome": 5,
            "n_cost": 5,
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
            "n_outcome": 7,
            "n_cost": 7,
            "avg_correctness": 0.9974,
            "avg_cost": 0.01938,
            "efficiency": 51.47
          },
          "anthropic/claude-sonnet-5": {
            "n": 7,
            "n_outcome": 7,
            "n_cost": 2,
            "avg_correctness": 0.9143,
            "avg_cost": 0.648012,
            "efficiency": 1.41
          },
          "openai/gpt-5.6-terra": {
            "n": 7,
            "n_outcome": 7,
            "n_cost": 7,
            "avg_correctness": 0.9143,
            "avg_cost": 0.18689,
            "efficiency": 4.89
          },
          "deepseek/deepseek-v4-flash": {
            "n": 7,
            "n_outcome": 7,
            "n_cost": 7,
            "avg_correctness": 0.8792,
            "avg_cost": 0.009603,
            "efficiency": 91.55
          },
          "anthropic/claude-haiku-4-5": {
            "n": 7,
            "n_outcome": 7,
            "n_cost": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.309695,
            "efficiency": 3.23
          },
          "openai/gpt-5.6-sol": {
            "n": 7,
            "n_outcome": 7,
            "n_cost": 7,
            "avg_correctness": 1.0,
            "avg_cost": 0.482432,
            "efficiency": 2.07
          },
          "openai/gpt-5.6-luna": {
            "n": 7,
            "n_outcome": 7,
            "n_cost": 7,
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
        "n_cost": 1,
        "n_outcome": 7,
        "total_cost": 0.309695,
        "avg_cost": 0.309695,
        "avg_correctness": 1.0
      },
      "anthropic/claude-sonnet-5_only": {
        "n": 12,
        "n_cost": 7,
        "n_outcome": 12,
        "total_cost": 3.678477,
        "avg_cost": 0.525497,
        "avg_correctness": 0.9167
      },
      "deepseek/deepseek-v4-flash_only": {
        "n": 7,
        "n_cost": 7,
        "n_outcome": 7,
        "total_cost": 0.067223,
        "avg_cost": 0.009603,
        "avg_correctness": 0.8792
      },
      "deepseek/deepseek-v4-pro_only": {
        "n": 12,
        "n_cost": 12,
        "n_outcome": 12,
        "total_cost": 0.203213,
        "avg_cost": 0.016934,
        "avg_correctness": 0.9985
      },
      "openai/gpt-5.6-luna_only": {
        "n": 7,
        "n_cost": 7,
        "n_outcome": 7,
        "total_cost": 0.121081,
        "avg_cost": 0.017297,
        "avg_correctness": 1.0
      },
      "openai/gpt-5.6-sol_only": {
        "n": 12,
        "n_cost": 12,
        "n_outcome": 12,
        "total_cost": 5.383373,
        "avg_cost": 0.448614,
        "avg_correctness": 1.0
      },
      "openai/gpt-5.6-terra_only": {
        "n": 7,
        "n_cost": 7,
        "n_outcome": 7,
        "total_cost": 1.308232,
        "avg_cost": 0.18689,
        "avg_correctness": 0.9143
      },
      "grit_routed": {
        "n": 12,
        "n_cost": 6,
        "n_outcome": 12,
        "total_cost": 0.377245,
        "avg_cost": 0.062874,
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
        "cost_captured_records": 31,
        "total_records": 31,
        "total_captured_cost": 2.308294,
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
        "cost_captured_records": 34,
        "total_records": 34,
        "total_captured_cost": 3.180633,
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
        "cost_captured_records": 39,
        "total_records": 39,
        "total_captured_cost": 6.314403,
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
        "cost_captured_records": 30,
        "total_records": 30,
        "total_captured_cost": 31.329782,
        "cost_coverage": 1.0,
        "total_tokens": 4770535,
        "avg_cache_hit": 0.832,
        "avg_duration_s": 785.0
      },
      {
        "model": "anthropic/claude-haiku-4-5",
        "cells": 20,
        "total_cost": 32.616808,
        "avg_cost": 1.63084,
        "avg_captured_cost": 1.63084,
        "cost_captured_records": 20,
        "total_records": 20,
        "total_captured_cost": 32.616808,
        "cost_coverage": 1.0,
        "total_tokens": 1629766,
        "avg_cache_hit": 0.989,
        "avg_duration_s": 1032.0
      },
      {
        "model": "openai/gpt-5.6-sol",
        "cells": 30,
        "total_cost": 114.52382,
        "avg_cost": 3.817461,
        "avg_captured_cost": 3.817461,
        "cost_captured_records": 30,
        "total_records": 30,
        "total_captured_cost": 114.52382,
        "cost_coverage": 1.0,
        "total_tokens": 6995342,
        "avg_cache_hit": 0.85,
        "avg_duration_s": 1146.0
      },
      {
        "model": "anthropic/claude-sonnet-5",
        "cells": 23,
        "total_cost": 118.894751,
        "avg_cost": 5.169337,
        "avg_captured_cost": 5.169337,
        "cost_captured_records": 23,
        "total_records": 23,
        "total_captured_cost": 118.894751,
        "cost_coverage": 1.0,
        "total_tokens": 2484557,
        "avg_cache_hit": 0.986,
        "avg_duration_s": 1245.0
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
        "cost_captured_records": 135,
        "total_records": 135,
        "total_captured_cost": 208.287391,
        "cost_coverage": 1.0,
        "success": 131,
        "fail": 4
      },
      {
        "condition": "early_degrade",
        "cells": 72,
        "variants": 12,
        "total_cost": 100.8811,
        "avg_cost": 1.401126,
        "avg_captured_cost": 1.401126,
        "cost_captured_records": 72,
        "total_records": 72,
        "total_captured_cost": 100.8811,
        "cost_coverage": 1.0,
        "success": 69,
        "fail": 3
      }
    ],
    "stories": [
      {
        "story": "task_manager_api",
        "cells": 77,
        "total_cost": 87.323185,
        "avg_cost": 1.134067,
        "avg_captured_cost": 1.134067,
        "cost_captured_records": 77,
        "total_records": 77,
        "total_captured_cost": 87.323185,
        "cost_coverage": 1.0,
        "sessions": 383,
        "avg_duration_s": 876.0,
        "avg_tokens_per_session": 23893.0
      },
      {
        "story": "notification_service",
        "cells": 66,
        "total_cost": 95.940785,
        "avg_cost": 1.453648,
        "avg_captured_cost": 1.453648,
        "cost_captured_records": 66,
        "total_records": 66,
        "total_captured_cost": 95.940785,
        "cost_coverage": 1.0,
        "sessions": 328,
        "avg_duration_s": 1263.0,
        "avg_tokens_per_session": 35466.0
      },
      {
        "story": "static_site_gen",
        "cells": 64,
        "total_cost": 125.904521,
        "avg_cost": 1.967258,
        "avg_captured_cost": 1.967258,
        "cost_captured_records": 64,
        "total_records": 64,
        "total_captured_cost": 125.904521,
        "cost_coverage": 1.0,
        "sessions": 316,
        "avg_duration_s": 1423.0,
        "avg_tokens_per_session": 41632.0
      }
    ],
    "tiers": [
      {
        "tier": "tier1_minimal",
        "quality": "bad",
        "cells": 41,
        "avg_cost": 1.549339,
        "avg_captured_cost": 1.549339,
        "cost_captured_records": 41,
        "total_records": 41,
        "total_captured_cost": 63.522913,
        "cost_coverage": 1.0,
        "avg_tokens_per_session": 33980.0,
        "avg_session_duration_s": 245.0
      },
      {
        "tier": "tier1_minimal",
        "quality": "good",
        "cells": 68,
        "avg_cost": 1.551765,
        "avg_captured_cost": 1.551765,
        "cost_captured_records": 68,
        "total_records": 68,
        "total_captured_cost": 105.520049,
        "cost_coverage": 1.0,
        "avg_tokens_per_session": 32337.0,
        "avg_session_duration_s": 245.0
      },
      {
        "tier": "tier2_small",
        "quality": "bad",
        "cells": 39,
        "avg_cost": 1.292634,
        "avg_captured_cost": 1.292634,
        "cost_captured_records": 39,
        "total_records": 39,
        "total_captured_cost": 50.412727,
        "cost_coverage": 1.0,
        "avg_tokens_per_session": 32538.0,
        "avg_session_duration_s": 231.0
      },
      {
        "tier": "tier2_small",
        "quality": "good",
        "cells": 59,
        "avg_cost": 1.520556,
        "avg_captured_cost": 1.520556,
        "cost_captured_records": 59,
        "total_records": 59,
        "total_captured_cost": 89.712802,
        "cost_coverage": 1.0,
        "avg_tokens_per_session": 33624.0,
        "avg_session_duration_s": 227.0
      }
    ],
    "sessions": {
      "total": 1027,
      "total_cost": 309.16849071000047,
      "total_tokens": 33518193,
      "total_cache_reads": 823919043,
      "cache_hit_rate": 0.977,
      "duration_s": 241893.54902822094,
      "successful": 1007,
      "failed": 20
    },
    "generated_at": "2026-09-02T22:29:19.308251+00:00"
  },
  "reviews": {
    "models": [
      {
        "model": "deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "stories": 37,
        "overall_coherence": 0.0,
        "architectural_fit": null,
        "convention_adherence": 0.712,
        "better_pct": 0.0,
        "worse_pct": 100.0,
        "neutral_pct": 0.0,
        "top_issues": [
          {
            "theme": "other",
            "count": 670
          },
          {
            "theme": "test gaps",
            "count": 284
          },
          {
            "theme": "incomplete refactor",
            "count": 8
          }
        ]
      },
      {
        "model": "gpt-5.6-terra",
        "label": "gpt-5.6-terra",
        "stories": 20,
        "overall_coherence": 0.0,
        "architectural_fit": null,
        "convention_adherence": 0.695,
        "better_pct": 0.0,
        "worse_pct": 100.0,
        "neutral_pct": 0.0,
        "top_issues": [
          {
            "theme": "other",
            "count": 229
          },
          {
            "theme": "test gaps",
            "count": 79
          }
        ]
      },
      {
        "model": "deepseek-v4-flash",
        "label": "DeepSeek v4 Flash",
        "stories": 21,
        "overall_coherence": 0.0,
        "architectural_fit": null,
        "convention_adherence": 0.682,
        "better_pct": 0.0,
        "worse_pct": 100.0,
        "neutral_pct": 0.0,
        "top_issues": [
          {
            "theme": "other",
            "count": 437
          },
          {
            "theme": "test gaps",
            "count": 244
          }
        ]
      },
      {
        "model": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "stories": 24,
        "overall_coherence": 0.0,
        "architectural_fit": null,
        "convention_adherence": 0.693,
        "better_pct": 0.0,
        "worse_pct": 100.0,
        "neutral_pct": 0.0,
        "top_issues": [
          {
            "theme": "other",
            "count": 271
          },
          {
            "theme": "test gaps",
            "count": 68
          }
        ]
      },
      {
        "model": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "stories": 16,
        "overall_coherence": 0.0,
        "architectural_fit": null,
        "convention_adherence": 0.732,
        "better_pct": 0.0,
        "worse_pct": 100.0,
        "neutral_pct": 0.0,
        "top_issues": [
          {
            "theme": "other",
            "count": 196
          },
          {
            "theme": "test gaps",
            "count": 143
          },
          {
            "theme": "incomplete refactor",
            "count": 6
          },
          {
            "theme": "security",
            "count": 2
          }
        ]
      },
      {
        "model": "gpt-5.6-sol",
        "label": "gpt-5.6-sol",
        "stories": 23,
        "overall_coherence": 0.0,
        "architectural_fit": null,
        "convention_adherence": 0.673,
        "better_pct": 0.0,
        "worse_pct": 100.0,
        "neutral_pct": 0.0,
        "top_issues": [
          {
            "theme": "other",
            "count": 302
          },
          {
            "theme": "test gaps",
            "count": 164
          }
        ]
      },
      {
        "model": "claude-haiku-4-5",
        "label": "claude-haiku-4-5",
        "stories": 14,
        "overall_coherence": 0.0,
        "architectural_fit": null,
        "convention_adherence": 0.751,
        "better_pct": 0.0,
        "worse_pct": 100.0,
        "neutral_pct": 0.0,
        "top_issues": [
          {
            "theme": "other",
            "count": 91
          },
          {
            "theme": "test gaps",
            "count": 36
          },
          {
            "theme": "incomplete refactor",
            "count": 1
          }
        ]
      }
    ],
    "commit_reviews": 764,
    "story_reviews": 155,
    "reviewer": "deepseek/deepseek-v4-flash"
  },
  "analysis": {
    "models": [
      {
        "model": "deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "commits": 189,
        "lines_added": 125134,
        "lines_removed": 9526,
        "functions_added": 3286,
        "classes_added": 269,
        "imports_added": 9274,
        "sonar_available": 189,
        "sonar_bugs_delta": 12,
        "sonar_smells_delta": 321,
        "sonar_complexity_delta": 4731,
        "avg_convention": 0.717,
        "deep_cells": 39,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 39,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 39,
          "coverage": 0.0
        },
        "solution_correctness": {
          "value": 1.0,
          "n_available": 39,
          "n_total": 39,
          "coverage": 1.0
        },
        "solution_constraints": {
          "value": 1.0,
          "n_available": 39,
          "n_total": 39,
          "coverage": 1.0
        },
        "solution_quality": {
          "value": 0.044,
          "n_available": 39,
          "n_total": 39,
          "coverage": 1.0
        },
        "solution_novelty": {
          "value": 0.845,
          "n_available": 39,
          "n_total": 39,
          "coverage": 1.0
        },
        "solution_composite": {
          "value": 0.786,
          "n_available": 39,
          "n_total": 39,
          "coverage": 1.0
        },
        "basin_escape": {
          "value": 0.713,
          "n_available": 39,
          "n_total": 39,
          "coverage": 1.0
        },
        "strategies": {
          "exploratory": 39
        }
      },
      {
        "model": "deepseek-v4-flash",
        "label": "DeepSeek v4 Flash",
        "commits": 152,
        "lines_added": 112407,
        "lines_removed": 8761,
        "functions_added": 3554,
        "classes_added": 167,
        "imports_added": 9850,
        "sonar_available": 152,
        "sonar_bugs_delta": 27,
        "sonar_smells_delta": 207,
        "sonar_complexity_delta": 4927,
        "avg_convention": 0.687,
        "deep_cells": 31,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 31,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 31,
          "coverage": 0.0
        },
        "solution_correctness": {
          "value": 0.968,
          "n_available": 31,
          "n_total": 31,
          "coverage": 1.0
        },
        "solution_constraints": {
          "value": 0.989,
          "n_available": 31,
          "n_total": 31,
          "coverage": 1.0
        },
        "solution_quality": {
          "value": 0.038,
          "n_available": 31,
          "n_total": 31,
          "coverage": 1.0
        },
        "solution_novelty": {
          "value": 0.88,
          "n_available": 31,
          "n_total": 31,
          "coverage": 1.0
        },
        "solution_composite": {
          "value": 0.775,
          "n_available": 31,
          "n_total": 31,
          "coverage": 1.0
        },
        "basin_escape": {
          "value": 0.743,
          "n_available": 31,
          "n_total": 31,
          "coverage": 1.0
        },
        "strategies": {
          "exploratory": 30,
          "conservative": 1
        }
      },
      {
        "model": "gpt-5.6-sol",
        "label": "gpt-5.6-sol",
        "commits": 149,
        "lines_added": 77716,
        "lines_removed": 12012,
        "functions_added": 2196,
        "classes_added": 150,
        "imports_added": 6877,
        "sonar_available": 149,
        "sonar_bugs_delta": 3,
        "sonar_smells_delta": 97,
        "sonar_complexity_delta": 3648,
        "avg_convention": 0.68,
        "deep_cells": 30,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 30,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 30,
          "coverage": 0.0
        },
        "solution_correctness": {
          "value": 1.0,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "solution_constraints": {
          "value": 1.0,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "solution_quality": {
          "value": 0.054,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "solution_novelty": {
          "value": 0.916,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "solution_composite": {
          "value": 0.798,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "basin_escape": {
          "value": 0.786,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "strategies": {
          "exploratory": 30
        }
      },
      {
        "model": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "commits": 115,
        "lines_added": 62819,
        "lines_removed": 4128,
        "functions_added": 2591,
        "classes_added": 116,
        "imports_added": 4731,
        "sonar_available": 115,
        "sonar_bugs_delta": 11,
        "sonar_smells_delta": 124,
        "sonar_complexity_delta": 2214,
        "avg_convention": 0.717,
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
        "solution_correctness": {
          "value": 0.87,
          "n_available": 23,
          "n_total": 23,
          "coverage": 1.0
        },
        "solution_constraints": {
          "value": 0.971,
          "n_available": 23,
          "n_total": 23,
          "coverage": 1.0
        },
        "solution_quality": {
          "value": 0.048,
          "n_available": 23,
          "n_total": 23,
          "coverage": 1.0
        },
        "solution_novelty": {
          "value": 0.81,
          "n_available": 23,
          "n_total": 23,
          "coverage": 1.0
        },
        "solution_composite": {
          "value": 0.727,
          "n_available": 23,
          "n_total": 23,
          "coverage": 1.0
        },
        "basin_escape": {
          "value": 0.664,
          "n_available": 23,
          "n_total": 23,
          "coverage": 1.0
        },
        "strategies": {
          "exploratory": 20,
          "conservative": 3
        }
      },
      {
        "model": "claude-haiku-4-5",
        "label": "claude-haiku-4-5",
        "commits": 99,
        "lines_added": 62391,
        "lines_removed": 4321,
        "functions_added": 1690,
        "classes_added": 206,
        "imports_added": 2896,
        "sonar_available": 99,
        "sonar_bugs_delta": 3,
        "sonar_smells_delta": 200,
        "sonar_complexity_delta": 1797,
        "avg_convention": 0.707,
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
        "solution_correctness": {
          "value": 0.85,
          "n_available": 20,
          "n_total": 20,
          "coverage": 1.0
        },
        "solution_constraints": {
          "value": 0.983,
          "n_available": 20,
          "n_total": 20,
          "coverage": 1.0
        },
        "solution_quality": {
          "value": 0.036,
          "n_available": 20,
          "n_total": 20,
          "coverage": 1.0
        },
        "solution_novelty": {
          "value": 0.86,
          "n_available": 20,
          "n_total": 20,
          "coverage": 1.0
        },
        "solution_composite": {
          "value": 0.729,
          "n_available": 20,
          "n_total": 20,
          "coverage": 1.0
        },
        "basin_escape": {
          "value": 0.733,
          "n_available": 20,
          "n_total": 20,
          "coverage": 1.0
        },
        "strategies": {
          "exploratory": 17,
          "conservative": 3
        }
      },
      {
        "model": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "commits": 170,
        "lines_added": 27729,
        "lines_removed": 9605,
        "functions_added": 1730,
        "classes_added": 115,
        "imports_added": 4817,
        "sonar_available": 170,
        "sonar_bugs_delta": 15,
        "sonar_smells_delta": 180,
        "sonar_complexity_delta": 3559,
        "avg_convention": 0.694,
        "deep_cells": 34,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 34,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 34,
          "coverage": 0.0
        },
        "solution_correctness": {
          "value": 1.0,
          "n_available": 34,
          "n_total": 34,
          "coverage": 1.0
        },
        "solution_constraints": {
          "value": 0.99,
          "n_available": 34,
          "n_total": 34,
          "coverage": 1.0
        },
        "solution_quality": {
          "value": 0.087,
          "n_available": 34,
          "n_total": 34,
          "coverage": 1.0
        },
        "solution_novelty": {
          "value": 0.88,
          "n_available": 34,
          "n_total": 34,
          "coverage": 1.0
        },
        "solution_composite": {
          "value": 0.796,
          "n_available": 34,
          "n_total": 34,
          "coverage": 1.0
        },
        "basin_escape": {
          "value": 0.7,
          "n_available": 34,
          "n_total": 34,
          "coverage": 1.0
        },
        "strategies": {
          "exploratory": 34
        }
      },
      {
        "model": "gpt-5.6-terra",
        "label": "gpt-5.6-terra",
        "commits": 150,
        "lines_added": 26281,
        "lines_removed": 9714,
        "functions_added": 1718,
        "classes_added": 115,
        "imports_added": 5110,
        "sonar_available": 150,
        "sonar_bugs_delta": 13,
        "sonar_smells_delta": 109,
        "sonar_complexity_delta": 2840,
        "avg_convention": 0.689,
        "deep_cells": 30,
        "lsp_available": 0,
        "lsp_errors_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 30,
          "coverage": 0.0
        },
        "lsp_warnings_per_cell": {
          "value": null,
          "n_available": 0,
          "n_total": 30,
          "coverage": 0.0
        },
        "solution_correctness": {
          "value": 1.0,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "solution_constraints": {
          "value": 0.989,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "solution_quality": {
          "value": 0.086,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "solution_novelty": {
          "value": 0.91,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "solution_composite": {
          "value": 0.8,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "basin_escape": {
          "value": 0.752,
          "n_available": 30,
          "n_total": 30,
          "coverage": 1.0
        },
        "strategies": {
          "exploratory": 30
        }
      }
    ],
    "stories_analyzed": 207,
    "commits_analyzed": 1024,
    "sonar_commits_available": 1024
  },
  "labs": {
    "cache_economics": {
      "experiment_id": "lab_cache_economics",
      "generated_at": "2026-08-31T19:55:51.556650",
      "summary": {
        "models": 7,
        "stories": 207
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 31,
          "avg_cost": 0.074461,
          "avg_captured_cost": 0.074461,
          "total_captured_cost": 2.308294,
          "cost_captured_records": 31,
          "total_records": 31,
          "cost_coverage": 1.0,
          "avg_cache_hit": 0.964,
          "cache_hit_coverage": {
            "value": 0.964,
            "n_available": 31,
            "n_total": 31,
            "coverage": 1.0
          },
          "cache_reads": 224381696,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 7488299.0,
          "context_coverage": {
            "value": 7488299.0,
            "n_available": 31,
            "n_total": 31,
            "coverage": 1.0
          },
          "avg_tokens_per_cell": 250180.0,
          "tokens_coverage": {
            "value": 250180.0,
            "n_available": 31,
            "n_total": 31,
            "coverage": 1.0
          }
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 34,
          "avg_cost": 0.093548,
          "avg_captured_cost": 0.093548,
          "total_captured_cost": 3.180633,
          "cost_captured_records": 34,
          "total_records": 34,
          "cost_coverage": 1.0,
          "avg_cache_hit": 0.937,
          "cache_hit_coverage": {
            "value": 0.937,
            "n_available": 34,
            "n_total": 34,
            "coverage": 1.0
          },
          "cache_reads": 44099872,
          "cache_writes": 2378880,
          "read_write_ratio": 18.5,
          "avg_context_per_cell": 1386840.0,
          "context_coverage": {
            "value": 1386840.0,
            "n_available": 34,
            "n_total": 34,
            "coverage": 1.0
          },
          "avg_tokens_per_cell": 89785.0,
          "tokens_coverage": {
            "value": 89785.0,
            "n_available": 34,
            "n_total": 34,
            "coverage": 1.0
          }
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 39,
          "avg_cost": 0.161908,
          "avg_captured_cost": 0.161908,
          "total_captured_cost": 6.314403,
          "cost_captured_records": 39,
          "total_records": 39,
          "cost_coverage": 1.0,
          "avg_cache_hit": 0.801,
          "cache_hit_coverage": {
            "value": 0.801,
            "n_available": 39,
            "n_total": 39,
            "coverage": 1.0
          },
          "cache_reads": 146609152,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 3952443.0,
          "context_coverage": {
            "value": 3952443.0,
            "n_available": 39,
            "n_total": 39,
            "coverage": 1.0
          },
          "avg_tokens_per_cell": 193234.0,
          "tokens_coverage": {
            "value": 193234.0,
            "n_available": 39,
            "n_total": 39,
            "coverage": 1.0
          }
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 30,
          "avg_cost": 1.044326,
          "avg_captured_cost": 1.044326,
          "total_captured_cost": 31.329782,
          "cost_captured_records": 30,
          "total_records": 30,
          "cost_coverage": 1.0,
          "avg_cache_hit": 0.832,
          "cache_hit_coverage": {
            "value": 0.832,
            "n_available": 30,
            "n_total": 30,
            "coverage": 1.0
          },
          "cache_reads": 23958016,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 957618.0,
          "context_coverage": {
            "value": 957618.0,
            "n_available": 30,
            "n_total": 30,
            "coverage": 1.0
          },
          "avg_tokens_per_cell": 159018.0,
          "tokens_coverage": {
            "value": 159018.0,
            "n_available": 30,
            "n_total": 30,
            "coverage": 1.0
          }
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 20,
          "avg_cost": 1.63084,
          "avg_captured_cost": 1.63084,
          "total_captured_cost": 32.616808,
          "cost_captured_records": 20,
          "total_records": 20,
          "cost_coverage": 1.0,
          "avg_cache_hit": 0.989,
          "cache_hit_coverage": {
            "value": 0.989,
            "n_available": 20,
            "n_total": 20,
            "coverage": 1.0
          },
          "cache_reads": 163588556,
          "cache_writes": 3922476,
          "read_write_ratio": 41.7,
          "avg_context_per_cell": 8260916.0,
          "context_coverage": {
            "value": 8260916.0,
            "n_available": 20,
            "n_total": 20,
            "coverage": 1.0
          },
          "avg_tokens_per_cell": 81488.0,
          "tokens_coverage": {
            "value": 81488.0,
            "n_available": 20,
            "n_total": 20,
            "coverage": 1.0
          }
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 30,
          "avg_cost": 3.817461,
          "avg_captured_cost": 3.817461,
          "total_captured_cost": 114.52382,
          "cost_captured_records": 30,
          "total_records": 30,
          "cost_coverage": 1.0,
          "avg_cache_hit": 0.85,
          "cache_hit_coverage": {
            "value": 0.85,
            "n_available": 30,
            "n_total": 30,
            "coverage": 1.0
          },
          "cache_reads": 43466752,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 1682070.0,
          "context_coverage": {
            "value": 1682070.0,
            "n_available": 30,
            "n_total": 30,
            "coverage": 1.0
          },
          "avg_tokens_per_cell": 233178.0,
          "tokens_coverage": {
            "value": 233178.0,
            "n_available": 30,
            "n_total": 30,
            "coverage": 1.0
          }
        },
        {
          "model": "claude-sonnet-5",
          "cells": 23,
          "avg_cost": 5.169337,
          "avg_captured_cost": 5.169337,
          "total_captured_cost": 118.894751,
          "cost_captured_records": 23,
          "total_records": 23,
          "cost_coverage": 1.0,
          "avg_cache_hit": 0.986,
          "cache_hit_coverage": {
            "value": 0.986,
            "n_available": 23,
            "n_total": 23,
            "coverage": 1.0
          },
          "cache_reads": 177814999,
          "cache_writes": 5250530,
          "read_write_ratio": 33.9,
          "avg_context_per_cell": 7839111.0,
          "context_coverage": {
            "value": 7839111.0,
            "n_available": 23,
            "n_total": 23,
            "coverage": 1.0
          },
          "avg_tokens_per_cell": 108024.0,
          "tokens_coverage": {
            "value": 108024.0,
            "n_available": 23,
            "n_total": 23,
            "coverage": 1.0
          }
        }
      ],
      "lab_contract": {
        "lab": "lab_cache_economics.py",
        "input_dataset_id": "canonical_registry/story",
        "registry_identity_sha256": "dfff942e34e5143e94ef238550994330059bbf4010e1c64555b5f72d59e75406",
        "resolved_input_sha256": "38a1f5dbe586890f453f846aa185f75e150bed7de0d3de007b8c66e3811b1be6",
        "registry_version": "data-manifest/1.0+14911rows",
        "metric_definition_version": "cache_economics/v2",
        "metric_source_sha256": "c3c4ea9e7f5875b281d24905d28cdaacd4e9cb3be779327c77e856f486f47d5a",
        "n_resolved_records": 207,
        "n_eligible_records": 207,
        "n_used_records": 207,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "used_record_refs_sha256": "7d0b943104c02063bd3726e99b4e4a5777ec6ddfca03bd089a49ed1932127254",
        "excluded_record_refs_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "used_unique_records": 207,
        "used_contributions": 207,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v6",
        "generated_at": "2026-08-31T19:55:51.557221+00:00"
      }
    },
    "condition_effects": {
      "experiment_id": "lab_condition_effects",
      "generated_at": "2026-08-31T19:55:52.219038",
      "summary": {
        "conditions": 2,
        "stories": 207,
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
          "avg_cost": 1.54287,
          "total_cost": 208.287391,
          "avg_captured_cost": 1.54287,
          "total_captured_cost": 208.287391,
          "cost_captured_records": 135,
          "total_records": 135,
          "cost_coverage": 1.0,
          "reviews": 134,
          "worse_rate": 0.0
        },
        {
          "condition": "early_degrade",
          "cells": 72,
          "success_rate": 0.958,
          "cascade_rate": 0.028,
          "avg_cost": 1.401126,
          "total_cost": 100.8811,
          "avg_captured_cost": 1.401126,
          "total_captured_cost": 100.8811,
          "cost_captured_records": 72,
          "total_records": 72,
          "cost_coverage": 1.0,
          "reviews": 21,
          "worse_rate": 0.0
        }
      ],
      "lab_contract": {
        "lab": "lab_condition_effects.py",
        "input_dataset_id": "canonical_registry/story+review",
        "registry_identity_sha256": "dfff942e34e5143e94ef238550994330059bbf4010e1c64555b5f72d59e75406",
        "resolved_input_sha256": "8c90d86e0573b3f1e71982d544672cf90ef94cb1097452b3c857baf343d008a6",
        "registry_version": "data-manifest/1.0+14911rows",
        "metric_definition_version": "condition_effects/v2",
        "metric_source_sha256": "c7023d1bd40fa57e38cc738cca8a9a71780532be3f60898f74954fb6c80f7b32",
        "n_resolved_records": 449,
        "n_eligible_records": 362,
        "n_used_records": 362,
        "n_excluded_records": 87,
        "n_unused_eligible_records": 0,
        "used_record_refs_sha256": "47d98b8cd543f705e025bdfcf24a773b60499081a608bec700ac783a3a7002b3",
        "excluded_record_refs_sha256": "b9f23e41d491fb219bd9ef35f71b785a6adba1b092bb77d337183067b8b13a86",
        "used_unique_records": 362,
        "used_contributions": 362,
        "review_without_current_story": 87,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v6",
        "generated_at": "2026-08-31T19:55:52.219801+00:00"
      }
    },
    "grit": {
      "experiment_id": "lab_grit",
      "generated_at": "2026-08-31T19:55:52.984566",
      "metric_definition": "G(s) = P(test_executed_success | perturbation_strength = s)",
      "summary": {
        "cells": 136,
        "successes": 108,
        "grit_overall": 0.7941,
        "strength_levels": [
          0.0,
          0.5
        ],
        "findings": 64,
        "stories": 207,
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
          "n": 126,
          "successes": 101,
          "grit": 0.8016,
          "ci95_lo": 0.7235,
          "ci95_hi": 0.8618,
          "insufficient_support": false,
          "sources": {
            "finding": 54,
            "story": 72
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
          "model": "claude-sonnet-5",
          "n": 18,
          "successes": 16,
          "grit": 0.8889,
          "ci95_lo": 0.672,
          "ci95_hi": 0.969,
          "insufficient_support": false
        },
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
          "model": "claude-haiku-4-5",
          "n": 14,
          "successes": 11,
          "grit": 0.7857,
          "ci95_lo": 0.5241,
          "ci95_hi": 0.9243,
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
          "n": 72,
          "successes": 63,
          "grit": 0.875,
          "ci95_lo": 0.7792,
          "ci95_hi": 0.9328,
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
        "registry_identity_sha256": "dfff942e34e5143e94ef238550994330059bbf4010e1c64555b5f72d59e75406",
        "resolved_input_sha256": "66cb2de70d47e50269d54829a673734d7b7acc5768004a2e112623d5c811837d",
        "registry_version": "data-manifest/1.0+14911rows",
        "metric_definition_version": "grit/v2",
        "metric_source_sha256": "efffc47f8bc8e92356489e96cc82a9b08bd6b07eb5196e5c0250b8baf04b1e91",
        "n_resolved_records": 271,
        "n_eligible_records": 136,
        "n_used_records": 136,
        "n_excluded_records": 135,
        "n_unused_eligible_records": 0,
        "used_record_refs_sha256": "e5754e8893e767ad81ed56ced90e2b7841c5ab3e0e3b9993c01406279bf53e19",
        "excluded_record_refs_sha256": "406e4dcfb0de6257038bf88643c3577caf680c24ba5dd5009f64e7bc119b4edf",
        "used_unique_records": 136,
        "used_contributions": 136,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 135,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v6",
        "generated_at": "2026-08-31T19:55:52.985209+00:00"
      }
    },
    "story_arc": {
      "experiment_id": "lab_story_arc",
      "generated_at": "2026-08-31T19:55:54.303819",
      "summary": {
        "snowball_factor": 2.32,
        "session1_cost": 0.173207,
        "session5_cost": 0.402034,
        "stories": 207
      },
      "sessions": [
        {
          "session_number": 1,
          "task_type": "greenfield",
          "n": 207,
          "avg_cost": 0.173207,
          "avg_captured_cost": 0.173207,
          "total_captured_cost": 35.853902,
          "cost_captured_records": 207,
          "total_records": 207,
          "cost_coverage": 1.0,
          "avg_tokens": 22501.0,
          "avg_tests": 4.7
        },
        {
          "session_number": 2,
          "task_type": "feature",
          "n": 207,
          "avg_cost": 0.242173,
          "avg_captured_cost": 0.242173,
          "total_captured_cost": 49.88772,
          "cost_captured_records": 206,
          "total_records": 207,
          "cost_coverage": 0.9952,
          "avg_tokens": 29531.0,
          "avg_tests": 8.9
        },
        {
          "session_number": 3,
          "task_type": "integration",
          "n": 207,
          "avg_cost": 0.35613,
          "avg_captured_cost": 0.35613,
          "total_captured_cost": 72.294344,
          "cost_captured_records": 203,
          "total_records": 207,
          "cost_coverage": 0.9807,
          "avg_tokens": 36199.0,
          "avg_tests": 12.0
        },
        {
          "session_number": 4,
          "task_type": "refactor",
          "n": 203,
          "avg_cost": 0.359446,
          "avg_captured_cost": 0.359446,
          "total_captured_cost": 71.529731,
          "cost_captured_records": 199,
          "total_records": 203,
          "cost_coverage": 0.9803,
          "avg_tokens": 36646.0,
          "avg_tests": 11.5
        },
        {
          "session_number": 5,
          "task_type": "cross_cutting",
          "n": 203,
          "avg_cost": 0.402034,
          "avg_captured_cost": 0.402034,
          "total_captured_cost": 79.602794,
          "cost_captured_records": 198,
          "total_records": 203,
          "cost_coverage": 0.9754,
          "avg_tokens": 42257.0,
          "avg_tests": 15.5
        }
      ],
      "by_condition": {
        "clean_s1": 0.1772,
        "clean_s2": 0.2436,
        "clean_s3": 0.3981,
        "clean_s4": 0.3605,
        "clean_s5": 0.4176,
        "early_degrade_s1": 0.1658,
        "early_degrade_s2": 0.2395,
        "early_degrade_s3": 0.2781,
        "early_degrade_s4": 0.3575,
        "early_degrade_s5": 0.3742
      },
      "by_model": {
        "claude-haiku-4-5": {
          "1": 0.2221,
          "2": 0.3196,
          "3": 0.3478,
          "4": 0.3609,
          "5": 0.5521
        },
        "claude-sonnet-5": {
          "1": 0.5306,
          "2": 0.7969,
          "3": 1.3193,
          "4": 1.1553,
          "5": 1.6533
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
          "3": 0.049,
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
        "registry_identity_sha256": "dfff942e34e5143e94ef238550994330059bbf4010e1c64555b5f72d59e75406",
        "resolved_input_sha256": "38a1f5dbe586890f453f846aa185f75e150bed7de0d3de007b8c66e3811b1be6",
        "registry_version": "data-manifest/1.0+14911rows",
        "metric_definition_version": "story_arc/v2",
        "metric_source_sha256": "1e10f13a3df8657c2e75ca2045a1bb8835fb3880b6c475f5d2da6747b40a7c95",
        "n_resolved_records": 207,
        "n_eligible_records": 207,
        "n_used_records": 207,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "used_record_refs_sha256": "7d0b943104c02063bd3726e99b4e4a5777ec6ddfca03bd089a49ed1932127254",
        "excluded_record_refs_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "used_unique_records": 207,
        "used_contributions": 207,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v6",
        "generated_at": "2026-08-31T19:55:54.304487+00:00"
      }
    },
    "verification_frontier": {
      "experiment_id": "lab_verification_frontier",
      "generated_at": "2026-08-31T19:55:55.717947",
      "summary": {
        "models": 7,
        "stories": 207,
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
          "avg_cost": 0.074461,
          "avg_captured_cost": 0.074461,
          "total_captured_cost": 2.308294,
          "cost_captured_records": 31,
          "total_records": 31,
          "cost_coverage": 1.0,
          "avg_tests": 57.0,
          "total_cost": 2.308294,
          "total_tests": 1767
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 34,
          "cost_cells": 34,
          "avg_cost": 0.093548,
          "avg_captured_cost": 0.093548,
          "total_captured_cost": 3.180633,
          "cost_captured_records": 34,
          "total_records": 34,
          "cost_coverage": 1.0,
          "avg_tests": 14.294,
          "total_cost": 3.180633,
          "total_tests": 486
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 39,
          "cost_cells": 39,
          "avg_cost": 0.161908,
          "avg_captured_cost": 0.161908,
          "total_captured_cost": 6.314403,
          "cost_captured_records": 39,
          "total_records": 39,
          "cost_coverage": 1.0,
          "avg_tests": 47.949,
          "total_cost": 6.314403,
          "total_tests": 1870
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 30,
          "cost_cells": 30,
          "avg_cost": 1.044326,
          "avg_captured_cost": 1.044326,
          "total_captured_cost": 31.329782,
          "cost_captured_records": 30,
          "total_records": 30,
          "cost_coverage": 1.0,
          "avg_tests": 15.267,
          "total_cost": 31.329782,
          "total_tests": 458
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 20,
          "cost_cells": 20,
          "avg_cost": 1.63084,
          "avg_captured_cost": 1.63084,
          "total_captured_cost": 32.616808,
          "cost_captured_records": 20,
          "total_records": 20,
          "cost_coverage": 1.0,
          "avg_tests": 153.45,
          "total_cost": 32.616808,
          "total_tests": 3069
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 30,
          "cost_cells": 30,
          "avg_cost": 3.817461,
          "avg_captured_cost": 3.817461,
          "total_captured_cost": 114.52382,
          "cost_captured_records": 30,
          "total_records": 30,
          "cost_coverage": 1.0,
          "avg_tests": 24.4,
          "total_cost": 114.52382,
          "total_tests": 732
        },
        {
          "model": "claude-sonnet-5",
          "cells": 23,
          "cost_cells": 23,
          "avg_cost": 5.169337,
          "avg_captured_cost": 5.169337,
          "total_captured_cost": 118.894751,
          "cost_captured_records": 23,
          "total_records": 23,
          "cost_coverage": 1.0,
          "avg_tests": 137.522,
          "total_cost": 118.894751,
          "total_tests": 3163
        }
      ],
      "lab_contract": {
        "lab": "lab_verification_frontier.py",
        "input_dataset_id": "canonical_registry/story",
        "registry_identity_sha256": "dfff942e34e5143e94ef238550994330059bbf4010e1c64555b5f72d59e75406",
        "resolved_input_sha256": "38a1f5dbe586890f453f846aa185f75e150bed7de0d3de007b8c66e3811b1be6",
        "registry_version": "data-manifest/1.0+14911rows",
        "metric_definition_version": "verification_frontier/v2",
        "metric_source_sha256": "3c9ec2ce0be32ac9c6ae3e3ba3e3cdb4e2930a11d87dbb07c0933472b356457c",
        "n_resolved_records": 207,
        "n_eligible_records": 207,
        "n_used_records": 207,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "used_record_refs_sha256": "7d0b943104c02063bd3726e99b4e4a5777ec6ddfca03bd089a49ed1932127254",
        "excluded_record_refs_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "used_unique_records": 207,
        "used_contributions": 207,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v6",
        "generated_at": "2026-08-31T19:55:55.718539+00:00"
      }
    },
    "verification_value": {
      "experiment_id": "lab_verification_value",
      "generated_at": "2026-08-31T19:55:56.369591",
      "summary": {
        "correlation_tests_vs_worse_rate": null,
        "cells": 105,
        "stories": 207,
        "reviews": 242,
        "review_without_current_story": 87,
        "story_without_review": 52
      },
      "rows": [
        {
          "model": "claude-haiku-4-5",
          "tests": 0,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 136,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 153,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 173,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 177,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 188,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 191,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 195,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 201,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 210,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 233,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 248,
          "reviews": 6,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 294,
          "reviews": 3,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-haiku-4-5",
          "tests": 308,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 0,
          "reviews": 15,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 70,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 76,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 152,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 164,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 165,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 193,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 196,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 213,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 227,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 291,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "claude-sonnet-5",
          "tests": 346,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 5,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 7,
          "reviews": 25,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 8,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 35,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 37,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 39,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 40,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 45,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 46,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 47,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 49,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 52,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 54,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 55,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-flash",
          "tests": 67,
          "reviews": 2,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 0,
          "reviews": 7,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 2,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 3,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 4,
          "reviews": 20,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 5,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 6,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 7,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 9,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 17,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 36,
          "reviews": 4,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 38,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 39,
          "reviews": 12,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 43,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 44,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 46,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 47,
          "reviews": 11,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 49,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 53,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 56,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 61,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 72,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 75,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 78,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 80,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 82,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 90,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 111,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 128,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 129,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 145,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 0,
          "reviews": 35,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 7,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 8,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 9,
          "reviews": 20,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 10,
          "reviews": 20,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 11,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 13,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 14,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 16,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 25,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 62,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 0,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 1,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 2,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 3,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 4,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 5,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 13,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 14,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 15,
          "reviews": 4,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 17,
          "reviews": 20,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 20,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 21,
          "reviews": 15,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 22,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-sol",
          "tests": 24,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 0,
          "reviews": 30,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 9,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 10,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 11,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 12,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 15,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 16,
          "reviews": 15,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 17,
          "reviews": 5,
          "better_rate": 0.0,
          "worse_rate": 1.0
        },
        {
          "model": "gpt-5.6-terra",
          "tests": 18,
          "reviews": 10,
          "better_rate": 0.0,
          "worse_rate": 1.0
        }
      ],
      "lab_contract": {
        "lab": "lab_verification_value.py",
        "input_dataset_id": "canonical_registry/story+review",
        "registry_identity_sha256": "dfff942e34e5143e94ef238550994330059bbf4010e1c64555b5f72d59e75406",
        "resolved_input_sha256": "8c90d86e0573b3f1e71982d544672cf90ef94cb1097452b3c857baf343d008a6",
        "registry_version": "data-manifest/1.0+14911rows",
        "metric_definition_version": "verification_value/v2",
        "metric_source_sha256": "f8331d35688c569a39b7247378995514661aa372eef25b879a4536ce544e339a",
        "n_resolved_records": 449,
        "n_eligible_records": 310,
        "n_used_records": 310,
        "n_excluded_records": 139,
        "n_unused_eligible_records": 0,
        "used_record_refs_sha256": "d97d3c41fa0c6b75296d300bb5e33079444ca39a59795f6893b2860af9f2d357",
        "excluded_record_refs_sha256": "4fef61c240f7496476b8dced22dfb15d28a32cd0c93ec44b798410a71ad70ec4",
        "used_unique_records": 310,
        "used_contributions": 310,
        "review_without_current_story": 87,
        "story_without_review": 52,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": null,
        "contract_version": "lab-contract/v6",
        "generated_at": "2026-08-31T19:55:56.370362+00:00"
      }
    }
  },
  "verdicts": {
    "sources": {
      "cap_2b": "experiments/results/cap_2b/cap_2b_score_20260826T160018Z.json",
      "escalation": "experiments/results/cap_escalation_measurement/cap_escalation_measurement_score_20260826T125726Z.json",
      "calibration": "experiments/results/cap_2a_rerun2/cap_2a_rerun2_score_20260826T015846Z.json"
    },
    "cap_2b": {
      "decision": "NON_INFERIOR",
      "cpvo_ratio": 0.785746,
      "cpvo_ratio_ci_95": [
        0.6842,
        0.9105
      ],
      "margin_cpvo_ratio_le": 1.1,
      "success_gap_static_minus_adaptive": -0.333333,
      "margin_success_gap_le": 0.05,
      "authorization": "design review only, not control activation",
      "per_arm": {
        "static": {
          "n": 9,
          "total_cost_usd": 0.080062,
          "accepted_outcomes": 6,
          "cpvo_usd": 0.013344,
          "cpvo_ci_95": [
            0.011744,
            0.01477
          ],
          "verified_success_rate": 0.666667,
          "verified_success_wilson_95": [
            0.3542,
            0.8794
          ]
        },
        "adaptive": {
          "n": 9,
          "total_cost_usd": 0.094364,
          "accepted_outcomes": 9,
          "cpvo_usd": 0.010485,
          "cpvo_ci_95": [
            0.009522,
            0.011569
          ],
          "verified_success_rate": 1.0,
          "verified_success_wilson_95": [
            0.7008,
            1.0
          ]
        }
      },
      "defect_bearing": {
        "static": {
          "n_defect_bearing": 3,
          "total_cost_usd": 0.026837,
          "accepted_outcomes": 0,
          "cpvo_usd": null,
          "verified_success_rate": 0.0,
          "note": "defect-bearing = critical stimulus cells (the pilot's n per pre-registration section 3). static arm: 0 accepted (defect present); adaptive arm: rework applied -> accepted."
        },
        "adaptive": {
          "n_defect_bearing": 3,
          "total_cost_usd": 0.040609,
          "accepted_outcomes": 3,
          "cpvo_usd": 0.013536,
          "verified_success_rate": 1.0,
          "note": "defect-bearing = critical stimulus cells (the pilot's n per pre-registration section 3). static arm: 0 accepted (defect present); adaptive arm: rework applied -> accepted."
        }
      },
      "n_total": 18,
      "n_defect_bearing": 6
    },
    "escalation": {
      "baseline_cost_usd": 0.008949,
      "baseline_source": "experiments/results/cap_2a_rerun3/cap2a_r3_critical_baseline_phase_ledger.json (total_measured_cost_usd)",
      "base_downstream_defect_cost_usd": 0.004021,
      "per_model": [
        {
          "model": "openai/gpt-5.6-sol",
          "fix_cost_usd": 0.102619,
          "E_x": 11.4671,
          "E_x_formula": "0.102619 / 0.008949",
          "defect_fixed": true,
          "tests_passing": true
        },
        {
          "model": "anthropic/claude-sonnet-5",
          "fix_cost_usd": 0.111982,
          "E_x": 12.5134,
          "E_x_formula": "0.111982 / 0.008949",
          "defect_fixed": true,
          "tests_passing": true
        }
      ],
      "note": "n=1 per escalation model; descriptive, no CI"
    },
    "calibration": {
      "initial": "0/3",
      "rerun_hit_rate": 0.6667,
      "rerun_n": 3,
      "rerun_wilson_95": [
        0.2077,
        0.9385
      ],
      "note": "2/3 = 0.667, Wilson [0.2077, 0.9385], n=3; descriptive, not statistical clearance"
    }
  }
};
