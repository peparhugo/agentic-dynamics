/* Generated 2026-08-15 20:15:40 UTC by build_data.py */
/* DO NOT EDIT — regenerate with: python scripts/build_data.py */
window.DYNAMICS_DATA = {
  "_meta": {
    "generated_at": "2026-08-15T20:15:40.629639+00:00",
    "provenance_note": "All values tagged [M]easured, [C]omputed, [H]euristic, or e[X]ternal. See methodology.html."
  },
  "summary": {
    "worktrees_total": 205,
    "sessions_total": 787,
    "game_reports": 273,
    "total_cost": 218.1939,
    "architectures": 3,
    "variants": 7,
    "stories_total": 159,
    "stories_unique": 151,
    "stories_re_runs": 8,
    "story_sessions": 787,
    "story_total_cost": 218.1939,
    "configs": 35,
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
      "configs": "M"
    }
  },
  "models": [
    {
      "id": "deepseek/deepseek-v4-flash",
      "label": "DeepSeek v4 Flash",
      "provider": "deepseek",
      "cells": 22,
      "unique_cells": 21,
      "re_runs": 1,
      "sessions": 110,
      "total_cost": 1.499069,
      "avg_cost": 0.06814,
      "cost_cells": 22,
      "avg_cache_hit": 0.965,
      "avg_tests": 36.4,
      "avg_test_code_ratio": 0.658,
      "avg_tok_per_session": 46515.0,
      "avg_duration_s": 1290.0,
      "avg_code_lines": 2197.0,
      "tests_total": 800,
      "tests_passed": 2304,
      "tests_run": 2306,
      "pass_rate": "100% (2304/2306)",
      "avg_cost_per_session": 0.013628,
      "avg_loc": 2197.0,
      "avg_energy_j": 52422.3,
      "avg_energy_j_per_loc": 23.86,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 22,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 22,
      "reports_valid": 22,
      "reports_narrated": 0
    },
    {
      "id": "openai/gpt-5.6-luna",
      "label": "GPT-5.6 Luna",
      "provider": "openai",
      "cells": 23,
      "unique_cells": 20,
      "re_runs": 3,
      "sessions": 115,
      "total_cost": 2.100259,
      "avg_cost": 0.091316,
      "cost_cells": 23,
      "avg_cache_hit": 0.971,
      "avg_tests": 7.7,
      "avg_test_code_ratio": 0.277,
      "avg_tok_per_session": 7697.0,
      "avg_duration_s": 540.0,
      "avg_code_lines": 763.0,
      "tests_total": 178,
      "tests_passed": 553,
      "tests_run": 553,
      "pass_rate": "100% (553/553)",
      "avg_cost_per_session": 0.018263,
      "avg_loc": 763.0,
      "avg_energy_j": 9920.1,
      "avg_energy_j_per_loc": 13.0,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 22,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 23,
      "reports_valid": 23,
      "reports_narrated": 0
    },
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "provider": "deepseek",
      "cells": 31,
      "unique_cells": 28,
      "re_runs": 3,
      "sessions": 147,
      "total_cost": 4.66263,
      "avg_cost": 0.150407,
      "cost_cells": 31,
      "avg_cache_hit": 0.762,
      "avg_tests": 47.8,
      "avg_test_code_ratio": 0.916,
      "avg_tok_per_session": 35393.0,
      "avg_duration_s": 1698.0,
      "avg_code_lines": 1410.0,
      "tests_total": 1481,
      "tests_passed": 2705,
      "tests_run": 2706,
      "pass_rate": "100% (2705/2706)",
      "avg_cost_per_session": 0.031718,
      "avg_loc": 1410.0,
      "avg_energy_j": 35290.0,
      "avg_energy_j_per_loc": 25.03,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 21,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 31,
      "reports_valid": 31,
      "reports_narrated": 0
    },
    {
      "id": "openai/gpt-5.6-terra",
      "label": "openai/gpt-5.6-terra",
      "provider": "openai",
      "cells": 20,
      "unique_cells": 20,
      "re_runs": 0,
      "sessions": 100,
      "total_cost": 20.303648,
      "avg_cost": 1.015182,
      "cost_cells": 20,
      "avg_cache_hit": 0.821,
      "avg_tests": 9.8,
      "avg_test_code_ratio": 0.361,
      "avg_tok_per_session": 32400.0,
      "avg_duration_s": 731.0,
      "avg_code_lines": 693.0,
      "tests_total": 195,
      "tests_passed": 770,
      "tests_run": 770,
      "pass_rate": "100% (770/770)",
      "avg_cost_per_session": 0.203036,
      "avg_loc": 693.0,
      "avg_energy_j": 18629.5,
      "avg_energy_j_per_loc": 26.88,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 20,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 20,
      "reports_valid": 20,
      "reports_narrated": 0
    },
    {
      "id": "anthropic/claude-haiku-4-5",
      "label": "anthropic/claude-haiku-4-5",
      "provider": "anthropic",
      "cells": 20,
      "unique_cells": 20,
      "re_runs": 0,
      "sessions": 100,
      "total_cost": 21.516785,
      "avg_cost": 1.536913,
      "cost_cells": 14,
      "avg_cache_hit": 0.692,
      "avg_tests": 135.4,
      "avg_test_code_ratio": 1.273,
      "avg_tok_per_session": 10965.0,
      "avg_duration_s": 705.0,
      "avg_code_lines": 1682.0,
      "tests_total": 2707,
      "tests_passed": 0,
      "tests_run": 0,
      "pass_rate": "unknown",
      "avg_cost_per_session": 0.307383,
      "avg_loc": 1682.0,
      "avg_energy_j": 12474.3,
      "avg_energy_j_per_loc": 7.42,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 8,
      "strategy_expl": 10,
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
      "cells": 23,
      "unique_cells": 23,
      "re_runs": 0,
      "sessions": 115,
      "total_cost": 91.693651,
      "avg_cost": 3.98668,
      "cost_cells": 23,
      "avg_cache_hit": 0.849,
      "avg_tests": 12.0,
      "avg_test_code_ratio": 0.402,
      "avg_tok_per_session": 48229.0,
      "avg_duration_s": 1233.0,
      "avg_code_lines": 1255.0,
      "tests_total": 275,
      "tests_passed": 1289,
      "tests_run": 1289,
      "pass_rate": "100% (1289/1289)",
      "avg_cost_per_session": 0.797336,
      "avg_loc": 1255.0,
      "avg_energy_j": 28959.4,
      "avg_energy_j_per_loc": 23.08,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 23,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 23,
      "reports_valid": 23,
      "reports_narrated": 0
    },
    {
      "id": "anthropic/claude-sonnet-5",
      "label": "Claude Sonnet 5",
      "provider": "anthropic",
      "cells": 20,
      "unique_cells": 19,
      "re_runs": 1,
      "sessions": 100,
      "total_cost": 76.417905,
      "avg_cost": 4.776119,
      "cost_cells": 16,
      "avg_cache_hit": 0.789,
      "avg_tests": 122.6,
      "avg_test_code_ratio": 0.727,
      "avg_tok_per_session": 16178.0,
      "avg_duration_s": 958.0,
      "avg_code_lines": 2177.0,
      "tests_total": 2451,
      "tests_passed": 455,
      "tests_run": 455,
      "pass_rate": "100% (455/455)",
      "avg_cost_per_session": 0.955224,
      "avg_loc": 2177.0,
      "avg_energy_j": 18548.1,
      "avg_energy_j_per_loc": 8.52,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 6,
      "strategy_expl": 13,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 20,
      "reports_valid": 20,
      "reports_narrated": 0
    }
  ],
  "perturbation_models": [
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "provider": "deepseek",
      "sessions": 201,
      "n_reports": 119,
      "n_valid": 109,
      "n_narrated": 10,
      "reports": 119,
      "reports_valid": 109,
      "reports_narrated": 10,
      "avg_cost": 0.0158,
      "total_cost": 5.7444,
      "cost_ci95": [
        0.0147,
        0.017
      ],
      "pass_rate": "84% (976/1163) [tests]",
      "strategy_cons": 78,
      "strategy_expl": 29,
      "strategy_waste": 2,
      "strategy_efficient": 0,
      "avg_loc": 706,
      "avg_thinking_ratio": 0.087,
      "avg_escape": null,
      "avg_narration_penalty": 0.0,
      "avg_arch_divergence": null,
      "avg_struct_divergence": null,
      "avg_composite_score": 0.615,
      "avg_code_quality": 0.246,
      "avg_comment_ratio": 0.02,
      "avg_energy_j": 4091.8,
      "avg_energy_j_per_loc": 5.8,
      "correctness_per_dollar": 28.6092,
      "avg_quality_per_joule": 0.0002,
      "narration_rate": 8,
      "ast_files": 22.7,
      "ast_functions": 74,
      "ast_classes": 13,
      "ast_type_hint_pct": 10,
      "ast_docstring_pct": 2,
      "avg_constraints_met": 3.3,
      "avg_constraints_total": 6.8,
      "cost_input": 0.1294,
      "cost_output": 0.4233,
      "cost_reasoning": 0.0234,
      "cost_cache": 1.1452,
      "tokens_total": 2462590,
      "tokens_input": 1186808,
      "tokens_output": 1035636,
      "tokens_reasoning": 240146,
      "tokens_cache_read": 26248192,
      "tokens_cache_write": 0,
      "_provenance": {
        "sessions": "M",
        "n_reports": "M",
        "n_valid": "M",
        "n_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_cache_read": "M",
        "tokens_cache_write": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_narration_penalty": "C",
        "avg_arch_divergence": "C",
        "avg_struct_divergence": "C",
        "avg_composite_score": "C",
        "avg_code_quality": "C",
        "avg_comment_ratio": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "ast_files": "C",
        "ast_functions": "C",
        "ast_classes": "C",
        "ast_type_hint_pct": "C",
        "ast_docstring_pct": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "narration_rate": "C",
        "cost_input": "C",
        "cost_output": "C",
        "cost_reasoning": "C",
        "cost_cache": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "provider": "openai",
      "sessions": 7,
      "n_reports": 7,
      "n_valid": 6,
      "n_narrated": 1,
      "reports": 7,
      "reports_valid": 6,
      "reports_narrated": 1,
      "avg_cost": 0.0057,
      "total_cost": 0.0345,
      "cost_ci95": [
        0.0044,
        0.0072
      ],
      "pass_rate": "89% (8/9) [tests]",
      "strategy_cons": 4,
      "strategy_expl": 2,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 199,
      "avg_thinking_ratio": 0.19,
      "avg_escape": null,
      "avg_narration_penalty": 0.3,
      "avg_arch_divergence": null,
      "avg_struct_divergence": null,
      "avg_composite_score": 0.688,
      "avg_code_quality": 0.487,
      "avg_comment_ratio": 0.072,
      "avg_energy_j": 4689.4,
      "avg_energy_j_per_loc": 23.56,
      "correctness_per_dollar": 3.6094,
      "avg_quality_per_joule": 0.0002,
      "narration_rate": 14,
      "ast_files": 3.3,
      "ast_functions": 21,
      "ast_classes": 2,
      "ast_type_hint_pct": 27,
      "ast_docstring_pct": 0,
      "avg_constraints_met": 0.0,
      "avg_constraints_total": 7.0,
      "cost_input": 0.0029,
      "cost_output": 0.0074,
      "cost_reasoning": 0.0074,
      "cost_cache": 0.0162,
      "tokens_total": 152892,
      "tokens_input": 93961,
      "tokens_output": 29491,
      "tokens_reasoning": 29440,
      "tokens_cache_read": 1142656,
      "tokens_cache_write": 0,
      "_provenance": {
        "sessions": "M",
        "n_reports": "M",
        "n_valid": "M",
        "n_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_cache_read": "M",
        "tokens_cache_write": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_narration_penalty": "C",
        "avg_arch_divergence": "C",
        "avg_struct_divergence": "C",
        "avg_composite_score": "C",
        "avg_code_quality": "C",
        "avg_comment_ratio": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "ast_files": "C",
        "ast_functions": "C",
        "ast_classes": "C",
        "ast_type_hint_pct": "C",
        "ast_docstring_pct": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "narration_rate": "C",
        "cost_input": "C",
        "cost_output": "C",
        "cost_reasoning": "C",
        "cost_cache": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "provider": "openai",
      "sessions": 13,
      "n_reports": 13,
      "n_valid": 12,
      "n_narrated": 1,
      "reports": 13,
      "reports_valid": 12,
      "reports_narrated": 1,
      "avg_cost": 0.0258,
      "total_cost": 0.3115,
      "cost_ci95": [
        0.0206,
        0.0333
      ],
      "pass_rate": "94% (30/32) [tests]",
      "strategy_cons": 11,
      "strategy_expl": 1,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 264,
      "avg_thinking_ratio": 0.066,
      "avg_escape": null,
      "avg_narration_penalty": 0.18,
      "avg_arch_divergence": null,
      "avg_struct_divergence": null,
      "avg_composite_score": 0.694,
      "avg_code_quality": 0.407,
      "avg_comment_ratio": 0.063,
      "avg_energy_j": 3838.6,
      "avg_energy_j_per_loc": 14.54,
      "correctness_per_dollar": 4.5089,
      "avg_quality_per_joule": 0.0002,
      "narration_rate": 8,
      "ast_files": 5.1,
      "ast_functions": 25,
      "ast_classes": 3,
      "ast_type_hint_pct": 9,
      "ast_docstring_pct": 1,
      "avg_constraints_met": 2.0,
      "avg_constraints_total": 7.0,
      "cost_input": 0.0341,
      "cost_output": 0.0751,
      "cost_reasoning": 0.0244,
      "cost_cache": 0.1759,
      "tokens_total": 339450,
      "tokens_input": 249447,
      "tokens_output": 67475,
      "tokens_reasoning": 22528,
      "tokens_cache_read": 2678784,
      "tokens_cache_write": 0,
      "_provenance": {
        "sessions": "M",
        "n_reports": "M",
        "n_valid": "M",
        "n_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_cache_read": "M",
        "tokens_cache_write": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_narration_penalty": "C",
        "avg_arch_divergence": "C",
        "avg_struct_divergence": "C",
        "avg_composite_score": "C",
        "avg_code_quality": "C",
        "avg_comment_ratio": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "ast_files": "C",
        "ast_functions": "C",
        "ast_classes": "C",
        "ast_type_hint_pct": "C",
        "ast_docstring_pct": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "narration_rate": "C",
        "cost_input": "C",
        "cost_output": "C",
        "cost_reasoning": "C",
        "cost_cache": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "openai/gpt-5",
      "label": "GPT-5",
      "provider": "openai",
      "sessions": 13,
      "n_reports": 13,
      "n_valid": 11,
      "n_narrated": 2,
      "reports": 13,
      "reports_valid": 11,
      "reports_narrated": 2,
      "avg_cost": 0.159,
      "total_cost": 1.7921,
      "cost_ci95": [
        0.1303,
        0.1846
      ],
      "pass_rate": "70% (16/23) [tests]",
      "strategy_cons": 3,
      "strategy_expl": 8,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 403,
      "avg_thinking_ratio": 0.083,
      "avg_escape": null,
      "avg_narration_penalty": 0.03,
      "avg_arch_divergence": null,
      "avg_struct_divergence": null,
      "avg_composite_score": 0.639,
      "avg_code_quality": 0.273,
      "avg_comment_ratio": 0.063,
      "avg_energy_j": 4816.7,
      "avg_energy_j_per_loc": 11.95,
      "correctness_per_dollar": 4.1783,
      "avg_quality_per_joule": 0.0002,
      "narration_rate": 15,
      "ast_files": 8.6,
      "ast_functions": 13,
      "ast_classes": 2,
      "ast_type_hint_pct": 18,
      "ast_docstring_pct": 1,
      "avg_constraints_met": 2.8,
      "avg_constraints_total": 7.0,
      "cost_input": 0.1903,
      "cost_output": 0.4842,
      "cost_reasoning": 0.1877,
      "cost_cache": 0.8867,
      "tokens_total": 358967,
      "tokens_input": 246343,
      "tokens_output": 81904,
      "tokens_reasoning": 30720,
      "tokens_cache_read": 2517888,
      "tokens_cache_write": 0,
      "_provenance": {
        "sessions": "M",
        "n_reports": "M",
        "n_valid": "M",
        "n_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_cache_read": "M",
        "tokens_cache_write": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_narration_penalty": "C",
        "avg_arch_divergence": "C",
        "avg_struct_divergence": "C",
        "avg_composite_score": "C",
        "avg_code_quality": "C",
        "avg_comment_ratio": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "ast_files": "C",
        "ast_functions": "C",
        "ast_classes": "C",
        "ast_type_hint_pct": "C",
        "ast_docstring_pct": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "narration_rate": "C",
        "cost_input": "C",
        "cost_output": "C",
        "cost_reasoning": "C",
        "cost_cache": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "openai/gpt-5.5",
      "label": "GPT-5.5",
      "provider": "openai",
      "sessions": 6,
      "n_reports": 6,
      "n_valid": 3,
      "n_narrated": 3,
      "reports": 6,
      "reports_valid": 3,
      "reports_narrated": 3,
      "avg_cost": 0.282,
      "total_cost": 0.9688,
      "cost_ci95": null,
      "pass_rate": "100% (27/27) [tests]",
      "strategy_cons": 1,
      "strategy_expl": 2,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 262,
      "avg_thinking_ratio": 0.021,
      "avg_escape": 0.64,
      "avg_narration_penalty": 0.0,
      "avg_arch_divergence": 0.683,
      "avg_struct_divergence": 0.287,
      "avg_composite_score": 0.852,
      "avg_code_quality": 0.383,
      "avg_comment_ratio": 0.01,
      "avg_energy_j": 2553.6,
      "avg_energy_j_per_loc": 9.75,
      "correctness_per_dollar": 7.7529,
      "avg_quality_per_joule": 0.0004,
      "narration_rate": 50,
      "ast_files": 3.0,
      "ast_functions": 33,
      "ast_classes": 1,
      "ast_type_hint_pct": 37,
      "ast_docstring_pct": 0,
      "avg_constraints_met": 6.7,
      "avg_constraints_total": 7.0,
      "cost_input": 0.1298,
      "cost_output": 0.3085,
      "cost_reasoning": 0.0256,
      "cost_cache": 0.3821,
      "tokens_total": 63015,
      "tokens_input": 47475,
      "tokens_output": 14338,
      "tokens_reasoning": 1202,
      "tokens_cache_read": 284672,
      "tokens_cache_write": 0,
      "_provenance": {
        "sessions": "M",
        "n_reports": "M",
        "n_valid": "M",
        "n_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_cache_read": "M",
        "tokens_cache_write": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_narration_penalty": "C",
        "avg_arch_divergence": "C",
        "avg_struct_divergence": "C",
        "avg_composite_score": "C",
        "avg_code_quality": "C",
        "avg_comment_ratio": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "ast_files": "C",
        "ast_functions": "C",
        "ast_classes": "C",
        "ast_type_hint_pct": "C",
        "ast_docstring_pct": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "narration_rate": "C",
        "cost_input": "C",
        "cost_output": "C",
        "cost_reasoning": "C",
        "cost_cache": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "provider": "openai",
      "sessions": 16,
      "n_reports": 16,
      "n_valid": 15,
      "n_narrated": 1,
      "reports": 16,
      "reports_valid": 15,
      "reports_narrated": 1,
      "avg_cost": 0.4474,
      "total_cost": 6.7513,
      "cost_ci95": [
        0.3763,
        0.5175
      ],
      "pass_rate": "100% (166/166) [tests]",
      "strategy_cons": 14,
      "strategy_expl": 1,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 367,
      "avg_thinking_ratio": 0.064,
      "avg_escape": null,
      "avg_narration_penalty": 0.02,
      "avg_arch_divergence": null,
      "avg_struct_divergence": null,
      "avg_composite_score": 0.726,
      "avg_code_quality": 0.37,
      "avg_comment_ratio": 0.009,
      "avg_energy_j": 2286.5,
      "avg_energy_j_per_loc": 6.23,
      "correctness_per_dollar": 5.0078,
      "avg_quality_per_joule": 0.0004,
      "narration_rate": 6,
      "ast_files": 4.9,
      "ast_functions": 37,
      "ast_classes": 2,
      "ast_type_hint_pct": 5,
      "ast_docstring_pct": 0,
      "avg_constraints_met": 4.7,
      "avg_constraints_total": 6.4,
      "cost_input": 0.0013,
      "cost_output": 2.7502,
      "cost_reasoning": 0.1924,
      "cost_cache": 3.7669,
      "tokens_total": 139957,
      "tokens_input": 516,
      "tokens_output": 130337,
      "tokens_reasoning": 9104,
      "tokens_cache_read": 1870459,
      "tokens_cache_write": 254361,
      "_provenance": {
        "sessions": "M",
        "n_reports": "M",
        "n_valid": "M",
        "n_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_cache_read": "M",
        "tokens_cache_write": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_narration_penalty": "C",
        "avg_arch_divergence": "C",
        "avg_struct_divergence": "C",
        "avg_composite_score": "C",
        "avg_code_quality": "C",
        "avg_comment_ratio": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "ast_files": "C",
        "ast_functions": "C",
        "ast_classes": "C",
        "ast_type_hint_pct": "C",
        "ast_docstring_pct": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "narration_rate": "C",
        "cost_input": "C",
        "cost_output": "C",
        "cost_reasoning": "C",
        "cost_cache": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "openai/gpt-5.6-fast",
      "label": "GPT-5.6-fast",
      "provider": "openai",
      "sessions": 9,
      "n_reports": 9,
      "n_valid": 6,
      "n_narrated": 3,
      "reports": 9,
      "reports_valid": 6,
      "reports_narrated": 3,
      "avg_cost": 0.6625,
      "total_cost": 4.3781,
      "cost_ci95": [
        0.6082,
        0.7169
      ],
      "pass_rate": "100% (73/73) [tests]",
      "strategy_cons": 2,
      "strategy_expl": 4,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 343,
      "avg_thinking_ratio": 0.071,
      "avg_escape": 0.58,
      "avg_narration_penalty": 0.0,
      "avg_arch_divergence": 0.565,
      "avg_struct_divergence": 0.29,
      "avg_composite_score": 0.76,
      "avg_code_quality": 0.299,
      "avg_comment_ratio": 0.008,
      "avg_energy_j": 1598.7,
      "avg_energy_j_per_loc": 4.66,
      "correctness_per_dollar": 6.1925,
      "avg_quality_per_joule": 0.0005,
      "narration_rate": 33,
      "ast_files": 3.3,
      "ast_functions": 34,
      "ast_classes": 0,
      "ast_type_hint_pct": 28,
      "ast_docstring_pct": 0,
      "avg_constraints_met": 5.0,
      "avg_constraints_total": 7.0,
      "cost_input": 0.0011,
      "cost_output": 1.4601,
      "cost_reasoning": 0.1126,
      "cost_cache": 2.4013,
      "tokens_total": 38930,
      "tokens_input": 210,
      "tokens_output": 35930,
      "tokens_reasoning": 2790,
      "tokens_cache_read": 619431,
      "tokens_cache_write": 82432,
      "_provenance": {
        "sessions": "M",
        "n_reports": "M",
        "n_valid": "M",
        "n_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_cache_read": "M",
        "tokens_cache_write": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_narration_penalty": "C",
        "avg_arch_divergence": "C",
        "avg_struct_divergence": "C",
        "avg_composite_score": "C",
        "avg_code_quality": "C",
        "avg_comment_ratio": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "ast_files": "C",
        "ast_functions": "C",
        "ast_classes": "C",
        "ast_type_hint_pct": "C",
        "ast_docstring_pct": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "narration_rate": "C",
        "cost_input": "C",
        "cost_output": "C",
        "cost_reasoning": "C",
        "cost_cache": "C",
        "strategy_cons": "C",
        "strategy_expl": "C",
        "strategy_waste": "C",
        "strategy_efficient": "C",
        "pass_rate": "M"
      }
    },
    {
      "id": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "provider": "anthropic",
      "sessions": 44,
      "n_reports": 44,
      "n_valid": 39,
      "n_narrated": 5,
      "reports": 44,
      "reports_valid": 39,
      "reports_narrated": 5,
      "avg_cost": 1.0847,
      "total_cost": 43.4191,
      "cost_ci95": [
        0.9058,
        1.2585
      ],
      "pass_rate": "99% (276/279) [tests]",
      "strategy_cons": 27,
      "strategy_expl": 12,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 568,
      "avg_thinking_ratio": 0.0,
      "avg_escape": null,
      "avg_narration_penalty": 0.08,
      "avg_arch_divergence": null,
      "avg_struct_divergence": null,
      "avg_composite_score": 0.636,
      "avg_code_quality": 0.278,
      "avg_comment_ratio": 0.033,
      "avg_energy_j": 2857.6,
      "avg_energy_j_per_loc": 5.03,
      "correctness_per_dollar": 3.891,
      "avg_quality_per_joule": 0.0006,
      "narration_rate": 11,
      "ast_files": 10.5,
      "ast_functions": 30,
      "ast_classes": 6,
      "ast_type_hint_pct": 18,
      "ast_docstring_pct": 6,
      "avg_constraints_met": 2.6,
      "avg_constraints_total": 6.6,
      "cost_input": 0.0078,
      "cost_output": 24.214,
      "cost_reasoning": 0.0,
      "cost_cache": 18.0817,
      "tokens_total": 485063,
      "tokens_input": 784,
      "tokens_output": 484279,
      "tokens_reasoning": 0,
      "tokens_cache_read": 6289478,
      "tokens_cache_write": 943380,
      "_provenance": {
        "sessions": "M",
        "n_reports": "M",
        "n_valid": "M",
        "n_narrated": "M",
        "total_cost": "M",
        "tokens_input": "M",
        "tokens_output": "M",
        "tokens_reasoning": "M",
        "tokens_cache_read": "M",
        "tokens_cache_write": "M",
        "tokens_total": "M",
        "avg_cost": "C",
        "cost_ci95": "C",
        "avg_loc": "C",
        "avg_thinking_ratio": "C",
        "avg_escape": "C",
        "avg_narration_penalty": "C",
        "avg_arch_divergence": "C",
        "avg_struct_divergence": "C",
        "avg_composite_score": "C",
        "avg_code_quality": "C",
        "avg_comment_ratio": "C",
        "avg_energy_j": "C",
        "avg_energy_j_per_loc": "C",
        "avg_quality_per_joule": "C",
        "correctness_per_dollar": "C",
        "ast_files": "C",
        "ast_functions": "C",
        "ast_classes": "C",
        "ast_type_hint_pct": "C",
        "ast_docstring_pct": "C",
        "avg_constraints_met": "C",
        "avg_constraints_total": "C",
        "narration_rate": "C",
        "cost_input": "C",
        "cost_output": "C",
        "cost_reasoning": "C",
        "cost_cache": "C",
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
      0.06814,
      0.091316,
      0.150407,
      1.015182,
      1.536913,
      3.98668,
      4.776119
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
      2197.0,
      763.0,
      1410.0,
      693.0,
      1682.0,
      1255.0,
      2177.0
    ],
    "costY": [
      0.06814,
      0.091316,
      0.150407,
      1.015182,
      1.536913,
      3.98668,
      4.776119
    ],
    "reports": [
      22,
      23,
      31,
      20,
      20,
      23,
      20
    ]
  },
  "calculator": {
    "model_costs": [
      {
        "n": "DeepSeek v4 Flash",
        "c": 0.06814,
        "p": 1.0
      },
      {
        "n": "GPT-5.6 Luna",
        "c": 0.091316,
        "p": 1.0
      },
      {
        "n": "DeepSeek v4 Pro",
        "c": 0.150407,
        "p": 1.0
      },
      {
        "n": "openai/gpt-5.6-terra",
        "c": 1.015182,
        "p": 1.0
      },
      {
        "n": "anthropic/claude-haiku-4-5",
        "c": 1.536913,
        "p": 0
      },
      {
        "n": "openai/gpt-5.6-sol",
        "c": 3.98668,
        "p": 1.0
      },
      {
        "n": "Claude Sonnet 5",
        "c": 4.776119,
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
        "e": 14.9
      },
      {
        "m": "DS\u2192anthropic/claude-haiku-4-5",
        "e": 22.6
      },
      {
        "m": "DS\u2192openai/gpt-5.6-sol",
        "e": 58.5
      },
      {
        "m": "DS\u21925",
        "e": 70.1
      },
      {
        "m": "\u2192Human ($5/job)",
        "e": 73.4
      }
    ],
    "retry_rate_measured": 0.0,
    "woc_ratio": 1.0
  },
  "derived": {
    "cost_gap": "23\u00d7",
    "cost_gap_computation": "$1.536913 / $0.06814 = 22.6\u00d7",
    "overall_pass_rate": "100.0% (8076/8079) [tests]",
    "total_tests_passed": 8076,
    "total_tests_run": 8079,
    "total_cost_all_models": 218.1939,
    "total_cost_deepseek": 6.1617,
    "total_cost_claude": 97.9347,
    "total_narrated": 0,
    "total_valid_reports": 159,
    "total_reports_analyzed": 159,
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
      "perturbation_class": "semantic",
      "models": {
        "DeepSeek v4 Pro": {
          "n": 12,
          "avg_cost": 0.0167,
          "cost_ci95": [
            0.0136,
            0.0197
          ],
          "avg_escape": 0.7595,
          "escape_ci95": [
            0.7302,
            0.8062
          ],
          "avg_correctness": 0.7667,
          "correctness_ci95": [
            0.6167,
            0.8667
          ],
          "avg_thinking_ratio": 0.0981,
          "avg_energy_j": 4355.4208,
          "low_n": false
        },
        "GPT-5.6": {
          "n": 6,
          "avg_cost": 0.3424,
          "cost_ci95": [
            0.2968,
            0.393
          ],
          "avg_escape": 0.4097,
          "escape_ci95": [
            0.2944,
            0.5432
          ],
          "avg_correctness": 1.0,
          "correctness_ci95": [
            1.0,
            1.0
          ],
          "avg_thinking_ratio": 0.0603,
          "avg_energy_j": 1628.735,
          "low_n": false
        },
        "Claude Fable 5": {
          "n": 3,
          "avg_cost": 1.2892,
          "cost_ci95": [
            0.9862,
            1.8753
          ],
          "avg_escape": 0.6214,
          "escape_ci95": [
            0.5937,
            0.6432
          ],
          "avg_correctness": 0.8667,
          "correctness_ci95": [
            0.8,
            1.0
          ],
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": 3553.32,
          "low_n": true
        },
        "GPT-5-nano": {
          "n": 5,
          "avg_cost": 0.0061,
          "cost_ci95": [
            0.0046,
            0.0079
          ],
          "avg_escape": 0.5408,
          "escape_ci95": [
            0.419,
            0.6641
          ],
          "avg_correctness": 0.77,
          "correctness_ci95": [
            0.7,
            0.88
          ],
          "avg_thinking_ratio": 0.1984,
          "avg_energy_j": 5010.78,
          "low_n": false
        },
        "GPT-5.6-fast": {
          "n": 6,
          "avg_cost": 0.6625,
          "cost_ci95": [
            0.6082,
            0.7169
          ],
          "avg_escape": 0.5846,
          "escape_ci95": [
            0.4395,
            0.707
          ],
          "avg_correctness": 1.0,
          "correctness_ci95": [
            1.0,
            1.0
          ],
          "avg_thinking_ratio": 0.0706,
          "avg_energy_j": 1598.6667,
          "low_n": false
        },
        "GPT-5-mini": {
          "n": 6,
          "avg_cost": 0.0207,
          "cost_ci95": [
            0.0169,
            0.0253
          ],
          "avg_escape": 0.3912,
          "escape_ci95": [
            0.3152,
            0.4779
          ],
          "avg_correctness": 0.95,
          "correctness_ci95": [
            0.85,
            1.0
          ],
          "avg_thinking_ratio": 0.0651,
          "avg_energy_j": 3131.795,
          "low_n": false
        },
        "GPT-5": {
          "n": 1,
          "avg_cost": 0.1685,
          "cost_ci95": null,
          "avg_escape": 0.7032,
          "escape_ci95": null,
          "avg_correctness": 1.0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.0833,
          "avg_energy_j": 4568.33,
          "low_n": true
        },
        "GPT-5.5": {
          "n": 3,
          "avg_cost": 0.282,
          "cost_ci95": [
            0.2251,
            0.3159
          ],
          "avg_escape": 0.6383,
          "escape_ci95": [
            0.468,
            0.7321
          ],
          "avg_correctness": 1.0,
          "correctness_ci95": [
            1.0,
            1.0
          ],
          "avg_thinking_ratio": 0.0205,
          "avg_energy_j": 2553.56,
          "low_n": true
        }
      }
    },
    "unknown": {
      "perturbation_class": "unknown",
      "models": {
        "GPT-5": {
          "n": 2,
          "avg_cost": 0.0216,
          "cost_ci95": [
            0.01,
            0.0332
          ],
          "avg_escape": 0,
          "escape_ci95": null,
          "avg_correctness": 0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0,
          "avg_energy_j": 0,
          "low_n": true
        },
        "GPT-5.6-fast": {
          "n": 3,
          "avg_cost": 0.1343,
          "cost_ci95": [
            0.0809,
            0.1683
          ],
          "avg_escape": 0,
          "escape_ci95": null,
          "avg_correctness": 0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0,
          "avg_energy_j": 0,
          "low_n": true
        },
        "GPT-5-nano": {
          "n": 1,
          "avg_cost": 0.0005,
          "cost_ci95": null,
          "avg_escape": 0,
          "escape_ci95": null,
          "avg_correctness": 0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0,
          "avg_energy_j": 0,
          "low_n": true
        },
        "DeepSeek v4 Pro": {
          "n": 9,
          "avg_cost": 0.0071,
          "cost_ci95": [
            0.0049,
            0.0095
          ],
          "avg_escape": 0,
          "escape_ci95": null,
          "avg_correctness": 0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0,
          "avg_energy_j": 0,
          "low_n": false
        },
        "GPT-5.5": {
          "n": 3,
          "avg_cost": 0.041,
          "cost_ci95": [
            0.0325,
            0.053
          ],
          "avg_escape": 0,
          "escape_ci95": null,
          "avg_correctness": 0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0,
          "avg_energy_j": 0,
          "low_n": true
        },
        "GPT-5-mini": {
          "n": 1,
          "avg_cost": 0.0021,
          "cost_ci95": null,
          "avg_escape": 0,
          "escape_ci95": null,
          "avg_correctness": 0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0,
          "avg_energy_j": 0,
          "low_n": true
        },
        "Claude Fable 5": {
          "n": 4,
          "avg_cost": 0.2238,
          "cost_ci95": [
            0.1688,
            0.2688
          ],
          "avg_escape": 0,
          "escape_ci95": null,
          "avg_correctness": 0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0,
          "avg_energy_j": 0,
          "low_n": true
        },
        "GPT-5.6": {
          "n": 1,
          "avg_cost": 0.0405,
          "cost_ci95": null,
          "avg_escape": 0,
          "escape_ci95": null,
          "avg_correctness": 0,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0,
          "avg_energy_j": 0,
          "low_n": true
        }
      }
    },
    "baseline": {
      "perturbation_class": "semantic",
      "models": {
        "DeepSeek v4 Pro": {
          "n": 68,
          "avg_cost": 0.015,
          "cost_ci95": [
            0.0134,
            0.0165
          ],
          "avg_escape": null,
          "escape_ci95": [
            null,
            null
          ],
          "avg_correctness": 0.8988,
          "correctness_ci95": [
            0.8486,
            0.9405
          ],
          "avg_thinking_ratio": 0.0786,
          "avg_energy_j": 3843.4185,
          "low_n": false
        },
        "Claude Fable 5": {
          "n": 24,
          "avg_cost": 0.9288,
          "cost_ci95": [
            0.6883,
            1.1929
          ],
          "avg_escape": null,
          "escape_ci95": [
            null,
            null
          ],
          "avg_correctness": 0.924,
          "correctness_ci95": [
            0.8344,
            0.9833
          ],
          "avg_thinking_ratio": 0.0,
          "avg_energy_j": 2335.8121,
          "low_n": false
        },
        "GPT-5-nano": {
          "n": 1,
          "avg_cost": 0.0037,
          "cost_ci95": null,
          "avg_escape": null,
          "escape_ci95": null,
          "avg_correctness": 0.7,
          "correctness_ci95": null,
          "avg_thinking_ratio": 0.1482,
          "avg_energy_j": 3082.71,
          "low_n": true
        },
        "GPT-5.6": {
          "n": 9,
          "avg_cost": 0.5174,
          "cost_ci95": [
            0.4159,
            0.6236
          ],
          "avg_escape": null,
          "escape_ci95": [
            null,
            null
          ],
          "avg_correctness": 1.0,
          "correctness_ci95": [
            1.0,
            1.0
          ],
          "avg_thinking_ratio": 0.0669,
          "avg_energy_j": 2725.0289,
          "low_n": false
        },
        "GPT-5-mini": {
          "n": 6,
          "avg_cost": 0.0309,
          "cost_ci95": [
            0.0219,
            0.0435
          ],
          "avg_escape": null,
          "escape_ci95": [
            null,
            null
          ],
          "avg_correctness": 0.8667,
          "correctness_ci95": [
            0.7667,
            0.9583
          ],
          "avg_thinking_ratio": 0.066,
          "avg_energy_j": 4545.4,
          "low_n": false
        },
        "GPT-5": {
          "n": 3,
          "avg_cost": 0.1966,
          "cost_ci95": [
            0.1773,
            0.2201
          ],
          "avg_escape": null,
          "escape_ci95": [
            null,
            null
          ],
          "avg_correctness": 0.8333,
          "correctness_ci95": [
            0.7,
            1.0
          ],
          "avg_thinking_ratio": 0.1019,
          "avg_energy_j": 6593.97,
          "low_n": true
        }
      }
    }
  },
  "perturbation_class_breakdown": {
    "semantic": {
      "DeepSeek v4 Pro": {
        "n": 97,
        "low_n": false,
        "avg_cost": 0.0157,
        "cost_ci95": [
          0.0144,
          0.017
        ],
        "avg_escape": null,
        "escape_ci95": [
          null,
          null
        ],
        "avg_correctness": 0.91,
        "correctness_ci95": [
          0.8791,
          0.9426
        ],
        "avg_thinking_ratio": 0.085,
        "avg_loc": 703,
        "avg_tokens": 22558,
        "avg_narration_penalty": 0.0
      },
      "GPT-5.6": {
        "n": 15,
        "low_n": false,
        "avg_cost": 0.4474,
        "cost_ci95": [
          0.3763,
          0.5175
        ],
        "avg_escape": null,
        "escape_ci95": [
          null,
          null
        ],
        "avg_correctness": 1.0,
        "correctness_ci95": [
          1.0,
          1.0
        ],
        "avg_thinking_ratio": 0.064,
        "avg_loc": 367,
        "avg_tokens": 9330,
        "avg_narration_penalty": 0.02
      },
      "Claude Fable 5": {
        "n": 36,
        "low_n": false,
        "avg_cost": 1.0677,
        "cost_ci95": [
          0.8761,
          1.2718
        ],
        "avg_escape": null,
        "escape_ci95": [
          null,
          null
        ],
        "avg_correctness": 0.95,
        "correctness_ci95": [
          0.9132,
          0.9826
        ],
        "avg_thinking_ratio": 0.0,
        "avg_loc": 545,
        "avg_tokens": 12185,
        "avg_narration_penalty": 0.09
      },
      "GPT-5-nano": {
        "n": 6,
        "low_n": false,
        "avg_cost": 0.0057,
        "cost_ci95": [
          0.0044,
          0.0072
        ],
        "avg_escape": null,
        "escape_ci95": [
          0.4464,
          null
        ],
        "avg_correctness": 0.76,
        "correctness_ci95": [
          0.7,
          0.8583
        ],
        "avg_thinking_ratio": 0.19,
        "avg_loc": 199,
        "avg_tokens": 25482,
        "avg_narration_penalty": 0.3
      },
      "GPT-5.6-fast": {
        "n": 6,
        "low_n": false,
        "avg_cost": 0.6625,
        "cost_ci95": [
          0.6082,
          0.7169
        ],
        "avg_escape": 0.58,
        "escape_ci95": [
          0.4395,
          0.707
        ],
        "avg_correctness": 1.0,
        "correctness_ci95": [
          1.0,
          1.0
        ],
        "avg_thinking_ratio": 0.071,
        "avg_loc": 343,
        "avg_tokens": 6488,
        "avg_narration_penalty": 0.0
      },
      "GPT-5-mini": {
        "n": 12,
        "low_n": false,
        "avg_cost": 0.0258,
        "cost_ci95": [
          0.0206,
          0.0333
        ],
        "avg_escape": null,
        "escape_ci95": [
          null,
          null
        ],
        "avg_correctness": 0.91,
        "correctness_ci95": [
          0.8333,
          0.975
        ],
        "avg_thinking_ratio": 0.066,
        "avg_loc": 264,
        "avg_tokens": 28288,
        "avg_narration_penalty": 0.18
      },
      "GPT-5": {
        "n": 10,
        "low_n": false,
        "avg_cost": 0.158,
        "cost_ci95": [
          0.1241,
          0.1865
        ],
        "avg_escape": null,
        "escape_ci95": [
          null,
          null
        ],
        "avg_correctness": 0.95,
        "correctness_ci95": [
          0.87,
          1.0
        ],
        "avg_thinking_ratio": 0.083,
        "avg_loc": 396,
        "avg_tokens": 33055,
        "avg_narration_penalty": 0.03
      },
      "GPT-5.5": {
        "n": 3,
        "low_n": true,
        "avg_cost": 0.282,
        "cost_ci95": null,
        "avg_escape": 0.64,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.021,
        "avg_loc": 262,
        "avg_tokens": 21005,
        "avg_narration_penalty": 0.0
      }
    },
    "manifold": {
      "DeepSeek v4 Pro": {
        "n": 12,
        "low_n": false,
        "avg_cost": 0.0167,
        "cost_ci95": [
          0.0136,
          0.0197
        ],
        "avg_escape": 0.76,
        "escape_ci95": [
          0.7302,
          0.8062
        ],
        "avg_correctness": 0.77,
        "correctness_ci95": [
          0.6167,
          0.8667
        ],
        "avg_thinking_ratio": 0.098,
        "avg_loc": 729,
        "avg_tokens": 22870,
        "avg_narration_penalty": 0.0
      },
      "Claude Fable 5": {
        "n": 3,
        "low_n": true,
        "avg_cost": 1.2892,
        "cost_ci95": null,
        "avg_escape": 0.62,
        "escape_ci95": null,
        "avg_correctness": 0.87,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.0,
        "avg_loc": 841,
        "avg_tokens": 15464,
        "avg_narration_penalty": 0.0
      },
      "GPT-5": {
        "n": 1,
        "low_n": true,
        "avg_cost": 0.1685,
        "cost_ci95": null,
        "avg_escape": 0.7,
        "escape_ci95": null,
        "avg_correctness": 1.0,
        "correctness_ci95": null,
        "avg_thinking_ratio": 0.083,
        "avg_loc": 473,
        "avg_tokens": 28417,
        "avg_narration_penalty": 0.0
      }
    }
  },
  "energy_ranking": [
    {
      "id": "anthropic/claude-haiku-4-5",
      "label": "anthropic/claude-haiku-4-5",
      "avg_energy_j": 12474.3,
      "avg_energy_j_per_loc": 7.42,
      "avg_cost": 1.536913,
      "avg_loc": 1682.0
    },
    {
      "id": "anthropic/claude-sonnet-5",
      "label": "Claude Sonnet 5",
      "avg_energy_j": 18548.1,
      "avg_energy_j_per_loc": 8.52,
      "avg_cost": 4.776119,
      "avg_loc": 2177.0
    },
    {
      "id": "openai/gpt-5.6-luna",
      "label": "GPT-5.6 Luna",
      "avg_energy_j": 9920.1,
      "avg_energy_j_per_loc": 13.0,
      "avg_cost": 0.091316,
      "avg_loc": 763.0
    },
    {
      "id": "openai/gpt-5.6-sol",
      "label": "openai/gpt-5.6-sol",
      "avg_energy_j": 28959.4,
      "avg_energy_j_per_loc": 23.08,
      "avg_cost": 3.98668,
      "avg_loc": 1255.0
    },
    {
      "id": "deepseek/deepseek-v4-flash",
      "label": "DeepSeek v4 Flash",
      "avg_energy_j": 52422.3,
      "avg_energy_j_per_loc": 23.86,
      "avg_cost": 0.06814,
      "avg_loc": 2197.0
    },
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "avg_energy_j": 35290.0,
      "avg_energy_j_per_loc": 25.03,
      "avg_cost": 0.150407,
      "avg_loc": 1410.0
    },
    {
      "id": "openai/gpt-5.6-terra",
      "label": "openai/gpt-5.6-terra",
      "avg_energy_j": 18629.5,
      "avg_energy_j_per_loc": 26.88,
      "avg_cost": 1.015182,
      "avg_loc": 693.0
    }
  ],
  "strategy_distribution": {
    "exploratory": 59,
    "?": 24,
    "conservative": 141,
    "wasteful": 3
  },
  "routing": {
    "_meta": {
      "tasks_analyzed": 17,
      "total_valid_entries": 201
    },
    "per_task": [
      {
        "task": "baseline",
        "models_tested": 4,
        "best_correctness_model": "deepseek/deepseek-v4-pro",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "",
        "routing": "default",
        "recommendation": "default deepseek/deepseek-v4-pro",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 3,
            "avg_correctness": 1.0,
            "avg_cost": 0.015557,
            "efficiency": 64.28
          },
          "openai/gpt-5.6": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.386228,
            "efficiency": 2.59
          },
          "openai/gpt-5-mini": {
            "n": 2,
            "avg_correctness": 0.875,
            "avg_cost": 0.043339,
            "efficiency": 20.19
          },
          "anthropic/claude-fable-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.162945,
            "efficiency": 6.14
          }
        }
      },
      {
        "task": "collaborative_editor",
        "models_tested": 3,
        "best_correctness_model": "anthropic/claude-fable-5",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "anthropic/claude-fable-5",
        "routing": "default",
        "recommendation": "default deepseek/deepseek-v4-pro",
        "models": {
          "anthropic/claude-fable-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 2.489478,
            "efficiency": 0.4
          },
          "openai/gpt-5.6": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.700061,
            "efficiency": 1.43
          },
          "deepseek/deepseek-v4-pro": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.022099,
            "efficiency": 45.25
          }
        }
      },
      {
        "task": "data_table",
        "models_tested": 3,
        "best_correctness_model": "anthropic/claude-fable-5",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "openai/gpt-5.6",
        "escalate_model": "anthropic/claude-fable-5",
        "routing": "default",
        "recommendation": "default openai/gpt-5.6",
        "models": {
          "anthropic/claude-fable-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 2.053133,
            "efficiency": 0.49
          },
          "openai/gpt-5.6": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.729557,
            "efficiency": 1.37
          },
          "deepseek/deepseek-v4-pro": {
            "n": 1,
            "avg_correctness": 0.6,
            "avg_cost": 0.019413,
            "efficiency": 30.91
          }
        }
      },
      {
        "task": "inject_alien_vocab",
        "models_tested": 3,
        "best_correctness_model": "openai/gpt-5",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "openai/gpt-5",
        "routing": "escalate",
        "recommendation": "escalate to openai/gpt-5",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 7,
            "avg_correctness": 0.7429,
            "avg_cost": 0.017329,
            "efficiency": 42.87
          },
          "anthropic/claude-fable-5": {
            "n": 2,
            "avg_correctness": 0.9,
            "avg_cost": 1.430752,
            "efficiency": 0.63
          },
          "openai/gpt-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.168483,
            "efficiency": 5.94
          }
        }
      },
      {
        "task": "inject_competing_goal",
        "models_tested": 3,
        "best_correctness_model": "openai/gpt-5",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "openai/gpt-5",
        "routing": "escalate",
        "recommendation": "escalate to openai/gpt-5",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 3,
            "avg_correctness": 0.8667,
            "avg_cost": 0.015738,
            "efficiency": 55.07
          },
          "openai/gpt-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.159429,
            "efficiency": 6.27
          },
          "anthropic/claude-fable-5": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 1.482016,
            "efficiency": 0.67
          }
        }
      },
      {
        "task": "inject_phantom_success",
        "models_tested": 4,
        "best_correctness_model": "openai/gpt-5",
        "best_efficiency_model": "openai/gpt-5-nano",
        "default_model": "openai/gpt-5-nano",
        "escalate_model": "openai/gpt-5",
        "routing": "escalate",
        "recommendation": "escalate to openai/gpt-5",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 5,
            "avg_correctness": 0.92,
            "avg_cost": 0.020589,
            "efficiency": 44.68
          },
          "openai/gpt-5-nano": {
            "n": 1,
            "avg_correctness": 0.7,
            "avg_cost": 0.004173,
            "efficiency": 167.74
          },
          "openai/gpt-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.147749,
            "efficiency": 6.77
          },
          "anthropic/claude-fable-5": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 1.720768,
            "efficiency": 0.58
          }
        }
      },
      {
        "task": "inject_phantom_success_s0.5",
        "models_tested": 8,
        "best_correctness_model": "openai/gpt-5.6",
        "best_efficiency_model": "openai/gpt-5-nano",
        "default_model": "openai/gpt-5-nano",
        "escalate_model": "openai/gpt-5.6",
        "routing": "escalate",
        "recommendation": "escalate to openai/gpt-5.6",
        "models": {
          "openai/gpt-5.6": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.309446,
            "efficiency": 3.23
          },
          "anthropic/claude-fable-5": {
            "n": 2,
            "avg_correctness": 0.85,
            "avg_cost": 0.949532,
            "efficiency": 0.9
          },
          "openai/gpt-5-mini": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.017839,
            "efficiency": 56.06
          },
          "openai/gpt-5.5": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.270472,
            "efficiency": 3.7
          },
          "openai/gpt-5-nano": {
            "n": 1,
            "avg_correctness": 0.7,
            "avg_cost": 0.004373,
            "efficiency": 160.06
          },
          "openai/gpt-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.063435,
            "efficiency": 15.76
          },
          "deepseek/deepseek-v4-pro": {
            "n": 4,
            "avg_correctness": 1.0,
            "avg_cost": 0.01328,
            "efficiency": 75.3
          },
          "openai/gpt-5.6-fast": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.658125,
            "efficiency": 1.52
          }
        }
      },
      {
        "task": "invert_constraint",
        "models_tested": 3,
        "best_correctness_model": "anthropic/claude-fable-5",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "anthropic/claude-fable-5",
        "routing": "escalate",
        "recommendation": "escalate to anthropic/claude-fable-5",
        "models": {
          "anthropic/claude-fable-5": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 1.046811,
            "efficiency": 0.96
          },
          "deepseek/deepseek-v4-pro": {
            "n": 5,
            "avg_correctness": 0.76,
            "avg_cost": 0.018165,
            "efficiency": 41.84
          },
          "openai/gpt-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.184944,
            "efficiency": 5.41
          }
        }
      },
      {
        "task": "perturbed",
        "models_tested": 4,
        "best_correctness_model": "openai/gpt-5.6",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "openai/gpt-5.6",
        "routing": "escalate",
        "recommendation": "escalate to openai/gpt-5.6",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 3,
            "avg_correctness": 0.9297,
            "avg_cost": 0.016884,
            "efficiency": 55.06
          },
          "openai/gpt-5.6": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.408636,
            "efficiency": 2.45
          },
          "openai/gpt-5-mini": {
            "n": 2,
            "avg_correctness": 0.875,
            "avg_cost": 0.030346,
            "efficiency": 28.83
          },
          "anthropic/claude-fable-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.360892,
            "efficiency": 2.77
          }
        }
      },
      {
        "task": "remove_critical_constraint",
        "models_tested": 5,
        "best_correctness_model": "openai/gpt-5",
        "best_efficiency_model": "openai/gpt-5-nano",
        "default_model": "openai/gpt-5-nano",
        "escalate_model": "openai/gpt-5",
        "routing": "escalate",
        "recommendation": "escalate to openai/gpt-5",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 5,
            "avg_correctness": 0.88,
            "avg_cost": 0.019426,
            "efficiency": 45.3
          },
          "openai/gpt-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.206743,
            "efficiency": 4.84
          },
          "anthropic/claude-fable-5": {
            "n": 2,
            "avg_correctness": 0.9,
            "avg_cost": 1.091805,
            "efficiency": 0.82
          },
          "openai/gpt-5.6": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.374009,
            "efficiency": 2.67
          },
          "openai/gpt-5-nano": {
            "n": 1,
            "avg_correctness": 0.75,
            "avg_cost": 0.006376,
            "efficiency": 117.63
          }
        }
      },
      {
        "task": "remove_critical_constraint_s0.5",
        "models_tested": 7,
        "best_correctness_model": "openai/gpt-5.6",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "openai/gpt-5.6",
        "routing": "default",
        "recommendation": "default deepseek/deepseek-v4-pro",
        "models": {
          "openai/gpt-5.6": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.397594,
            "efficiency": 2.52
          },
          "openai/gpt-5.6-fast": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.685522,
            "efficiency": 1.46
          },
          "deepseek/deepseek-v4-pro": {
            "n": 4,
            "avg_correctness": 1.0,
            "avg_cost": 0.014286,
            "efficiency": 70.0
          },
          "openai/gpt-5.5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.304967,
            "efficiency": 3.28
          },
          "openai/gpt-5": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.114151,
            "efficiency": 8.76
          },
          "openai/gpt-5-mini": {
            "n": 2,
            "avg_correctness": 1.0,
            "avg_cost": 0.024369,
            "efficiency": 41.04
          },
          "anthropic/claude-fable-5": {
            "n": 2,
            "avg_correctness": 0.85,
            "avg_cost": 1.336673,
            "efficiency": 0.64
          }
        }
      },
      {
        "task": "shift_framing",
        "models_tested": 2,
        "best_correctness_model": "deepseek/deepseek-v4-pro",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "",
        "routing": "default",
        "recommendation": "default deepseek/deepseek-v4-pro",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 5,
            "avg_correctness": 0.8,
            "avg_cost": 0.015839,
            "efficiency": 50.51
          },
          "anthropic/claude-fable-5": {
            "n": 1,
            "avg_correctness": 0.8,
            "avg_cost": 1.006182,
            "efficiency": 0.8
          }
        }
      },
      {
        "task": "standardized_build",
        "models_tested": 4,
        "best_correctness_model": "deepseek/deepseek-v4-pro",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "",
        "routing": "default",
        "recommendation": "default deepseek/deepseek-v4-pro",
        "models": {
          "openai/gpt-5-mini": {
            "n": 1,
            "avg_correctness": 0.7,
            "avg_cost": 0.023859,
            "efficiency": 29.34
          },
          "deepseek/deepseek-v4-pro": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.020049,
            "efficiency": 49.88
          },
          "openai/gpt-5.6": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.266403,
            "efficiency": 3.75
          },
          "anthropic/claude-fable-5": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 1.110397,
            "efficiency": 0.9
          }
        }
      },
      {
        "task": "standardized_retry",
        "models_tested": 3,
        "best_correctness_model": "openai/gpt-5.6-fast",
        "best_efficiency_model": "openai/gpt-5-nano",
        "default_model": "openai/gpt-5-nano",
        "escalate_model": "openai/gpt-5.6-fast",
        "routing": "escalate",
        "recommendation": "escalate to openai/gpt-5.6-fast",
        "models": {
          "openai/gpt-5-nano": {
            "n": 1,
            "avg_correctness": 0.7,
            "avg_cost": 0.009503,
            "efficiency": 73.66
          },
          "openai/gpt-5.6-fast": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.661033,
            "efficiency": 1.51
          },
          "deepseek/deepseek-v4-pro": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.013816,
            "efficiency": 72.38
          }
        }
      },
      {
        "task": "std_final",
        "models_tested": 4,
        "best_correctness_model": "openai/gpt-5-nano",
        "best_efficiency_model": "openai/gpt-5-nano",
        "default_model": "openai/gpt-5-nano",
        "escalate_model": "",
        "routing": "default",
        "recommendation": "default openai/gpt-5-nano",
        "models": {
          "openai/gpt-5-nano": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.005871,
            "efficiency": 170.32
          },
          "openai/gpt-5.6-fast": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.626804,
            "efficiency": 1.6
          },
          "deepseek/deepseek-v4-pro": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.01493,
            "efficiency": 66.98
          },
          "openai/gpt-5-mini": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.015874,
            "efficiency": 63.0
          }
        }
      },
      {
        "task": "task_manager",
        "models_tested": 4,
        "best_correctness_model": "openai/gpt-5.6",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "openai/gpt-5.6",
        "routing": "default",
        "recommendation": "default deepseek/deepseek-v4-pro",
        "models": {
          "deepseek/deepseek-v4-pro": {
            "n": 5,
            "avg_correctness": 0.9828,
            "avg_cost": 0.019124,
            "efficiency": 51.39
          },
          "anthropic/claude-fable-5": {
            "n": 1,
            "avg_correctness": 0.7,
            "avg_cost": 2.022152,
            "efficiency": 0.35
          },
          "openai/gpt-5.6": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.498459,
            "efficiency": 2.01
          },
          "openai/gpt-5-mini": {
            "n": 1,
            "avg_correctness": 1.0,
            "avg_cost": 0.019817,
            "efficiency": 50.46
          }
        }
      },
      {
        "task": "url_shortener",
        "models_tested": 2,
        "best_correctness_model": "anthropic/claude-fable-5",
        "best_efficiency_model": "deepseek/deepseek-v4-pro",
        "default_model": "deepseek/deepseek-v4-pro",
        "escalate_model": "anthropic/claude-fable-5",
        "routing": "escalate",
        "recommendation": "escalate to anthropic/claude-fable-5",
        "models": {
          "anthropic/claude-fable-5": {
            "n": 8,
            "avg_correctness": 0.9844,
            "avg_cost": 0.513726,
            "efficiency": 1.92
          },
          "deepseek/deepseek-v4-pro": {
            "n": 21,
            "avg_correctness": 0.896,
            "avg_cost": 0.008336,
            "efficiency": 107.48
          }
        }
      }
    ],
    "strategies": {
      "anthropic/claude-fable-5_only": {
        "n": 39,
        "total_cost": 42.303518,
        "avg_cost": 1.084706,
        "avg_correctness": 0.9455
      },
      "deepseek/deepseek-v4-pro_only": {
        "n": 109,
        "total_cost": 1.721342,
        "avg_cost": 0.015792,
        "avg_correctness": 0.8965
      },
      "openai/gpt-5_only": {
        "n": 11,
        "total_cost": 1.748905,
        "avg_cost": 0.158991,
        "avg_correctness": 0.9545
      },
      "openai/gpt-5-mini_only": {
        "n": 12,
        "total_cost": 0.309337,
        "avg_cost": 0.025778,
        "avg_correctness": 0.9083
      },
      "openai/gpt-5-nano_only": {
        "n": 6,
        "total_cost": 0.033984,
        "avg_cost": 0.005664,
        "avg_correctness": 0.7583
      },
      "openai/gpt-5.5_only": {
        "n": 3,
        "total_cost": 0.845911,
        "avg_cost": 0.28197,
        "avg_correctness": 1.0
      },
      "openai/gpt-5.6_only": {
        "n": 15,
        "total_cost": 6.710796,
        "avg_cost": 0.447386,
        "avg_correctness": 1.0
      },
      "openai/gpt-5.6-fast_only": {
        "n": 6,
        "total_cost": 3.975131,
        "avg_cost": 0.662522,
        "avg_correctness": 1.0
      },
      "grit_routed": {
        "n": 41,
        "total_cost": 10.768792,
        "avg_cost": 0.262653,
        "avg_correctness": 0.9705,
        "routing_distribution": {
          "deepseek/deepseek-v4-pro": 19,
          "openai/gpt-5.6": 6,
          "openai/gpt-5": 4,
          "anthropic/claude-fable-5": 10,
          "openai/gpt-5.6-fast": 1,
          "openai/gpt-5-nano": 1
        }
      }
    },
    "routing_distribution": {
      "default": 8,
      "escalate": 9
    }
  },
  "grit_matrix": [
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.75,
      "correctness": 0.8,
      "cost": 0.0335,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 809,
      "thinking_ratio": 0.07,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.76,
      "correctness": 1.0,
      "cost": 0.3443,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r2",
      "loc": 407,
      "thinking_ratio": 0.03,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0241,
      "perturbation_class": "semantic",
      "task": "exp_0s36_d3n",
      "loc": 1008,
      "thinking_ratio": 0.11,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.75,
      "correctness": 1.0,
      "cost": 0.034,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 960,
      "thinking_ratio": 0.51,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.25,
      "correctness": 1.0,
      "cost": 0.3341,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r1",
      "loc": 407,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.76,
      "cost": 0.0214,
      "perturbation_class": "semantic",
      "task": "exp_1erxln69",
      "loc": 1266,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.63,
      "correctness": 1.0,
      "cost": 0.9285,
      "perturbation_class": "semantic",
      "task": "invert_constraint_s0.5",
      "loc": 485,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "color": "rgba(239,68,68,0.75)",
      "escape": 0.43,
      "correctness": 1.0,
      "cost": 0.0059,
      "perturbation_class": "semantic",
      "task": "std_final",
      "loc": 216,
      "thinking_ratio": 0.22,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 2.2412,
      "perturbation_class": "semantic",
      "task": "exp_1spl4mgd",
      "loc": 1327,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.751,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 436,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.4696,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 159,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 1.0,
      "correctness": 0.0,
      "cost": 0.004,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 0,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "color": "rgba(239,68,68,0.75)",
      "escape": 0.74,
      "correctness": 0.7,
      "cost": 0.0095,
      "perturbation_class": "semantic",
      "task": "standardized_retry",
      "loc": 246,
      "thinking_ratio": 0.19,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.76,
      "correctness": 1.0,
      "cost": 0.0279,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 1275,
      "thinking_ratio": 0.12,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.94,
      "cost": 0.0087,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 211,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0104,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 207,
      "thinking_ratio": 0.09,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0217,
      "perturbation_class": "semantic",
      "task": "exp_37z0nq68",
      "loc": 796,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 1.2564,
      "perturbation_class": "semantic",
      "task": "exp_3hlb2bus",
      "loc": 581,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.8723,
      "perturbation_class": "semantic",
      "task": "exp_3j2vrct4",
      "loc": 463,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.89,
      "cost": 0.0163,
      "perturbation_class": "semantic",
      "task": "exp_3zxicj_v",
      "loc": 840,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0237,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 1446,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6-fast",
      "label": "GPT-5.6-fast",
      "color": "rgba(59,130,246,0.60)",
      "escape": 0.74,
      "correctness": 1.0,
      "cost": 0.6163,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r1",
      "loc": 305,
      "thinking_ratio": 0.04,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.37,
      "correctness": 1.0,
      "cost": 0.0169,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r3",
      "loc": 1052,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.74,
      "correctness": 0.8,
      "cost": 0.016,
      "perturbation_class": "manifold",
      "task": "shift_framing_s0.5",
      "loc": 861,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.017,
      "perturbation_class": "semantic",
      "task": "exp_6462vbw3",
      "loc": 748,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "color": "rgba(239,68,68,0.75)",
      "escape": null,
      "correctness": 0.7,
      "cost": 0.0037,
      "perturbation_class": "semantic",
      "task": "exp_6ij8p3sl",
      "loc": 182,
      "thinking_ratio": 0.15,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "color": "rgba(239,68,68,0.75)",
      "escape": 0.68,
      "correctness": 0.7,
      "cost": 0.0042,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 144,
      "thinking_ratio": 0.11,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6-fast",
      "label": "GPT-5.6-fast",
      "color": "rgba(59,130,246,0.60)",
      "escape": 0.75,
      "correctness": 1.0,
      "cost": 0.6268,
      "perturbation_class": "semantic",
      "task": "std_final",
      "loc": 292,
      "thinking_ratio": 0.09,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.37,
      "correctness": 1.0,
      "cost": 0.9876,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r1",
      "loc": 562,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.3907,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 126,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.63,
      "correctness": 0.8,
      "cost": 1.0062,
      "perturbation_class": "manifold",
      "task": "shift_framing_s0.5",
      "loc": 678,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.4,
      "correctness": 1.0,
      "cost": 0.0146,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r2",
      "loc": 202,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.73,
      "correctness": 0.8,
      "cost": 0.0236,
      "perturbation_class": "semantic",
      "task": "invert_constraint_s0.5",
      "loc": 632,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.77,
      "correctness": 0.8,
      "cost": 0.02,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 1048,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.27,
      "correctness": 1.0,
      "cost": 0.4508,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r1",
      "loc": 453,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0059,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 92,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.74,
      "correctness": 0.8,
      "cost": 0.0151,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 713,
      "thinking_ratio": 0.25,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.72,
      "correctness": 1.0,
      "cost": 0.2067,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 525,
      "thinking_ratio": 0.16,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0214,
      "perturbation_class": "semantic",
      "task": "exp_9o_y1a_8",
      "loc": 1030,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.65,
      "correctness": 0.8,
      "cost": 0.8493,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 654,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.4122,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 133,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.75,
      "correctness": 0.8,
      "cost": 0.0237,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 841,
      "thinking_ratio": 0.12,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.7,
      "correctness": 1.0,
      "cost": 0.0058,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 364,
      "thinking_ratio": 0.05,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0104,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 385,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.5",
      "label": "GPT-5.5",
      "color": "rgba(251,191,36,0.60)",
      "escape": 0.47,
      "correctness": 1.0,
      "cost": 0.305,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r1",
      "loc": 251,
      "thinking_ratio": 0.01,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6-fast",
      "label": "GPT-5.6-fast",
      "color": "rgba(59,130,246,0.60)",
      "escape": 0.45,
      "correctness": 1.0,
      "cost": 0.661,
      "perturbation_class": "semantic",
      "task": "standardized_retry",
      "loc": 322,
      "thinking_ratio": 0.09,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0337,
      "perturbation_class": "semantic",
      "task": "exp__ygf4hz3",
      "loc": 910,
      "thinking_ratio": 0.31,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.5",
      "label": "GPT-5.5",
      "color": "rgba(251,191,36,0.60)",
      "escape": 0.73,
      "correctness": 1.0,
      "cost": 0.2251,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r2",
      "loc": 247,
      "thinking_ratio": 0.02,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.79,
      "cost": 0.0142,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 706,
      "thinking_ratio": 0.13,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.0217,
      "perturbation_class": "semantic",
      "task": "exp_aqqqi9v5",
      "loc": 1220,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.2,
      "cost": 0.0185,
      "perturbation_class": "semantic",
      "task": "exp_arc_7as6",
      "loc": 4,
      "thinking_ratio": 0.75,
      "strategy": "wasteful",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.73,
      "correctness": 0.8,
      "cost": 0.0177,
      "perturbation_class": "semantic",
      "task": "inject_competing_goal_s0.5",
      "loc": 763,
      "thinking_ratio": 0.15,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.72,
      "correctness": 1.0,
      "cost": 0.1521,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r1",
      "loc": 330,
      "thinking_ratio": 0.05,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 0.7,
      "cost": 1.3795,
      "perturbation_class": "semantic",
      "task": "exp_b48bnosz",
      "loc": 729,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0047,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 95,
      "thinking_ratio": 0.02,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.24,
      "correctness": 1.0,
      "cost": 0.0309,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r2",
      "loc": 306,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.98,
      "cost": 0.018,
      "perturbation_class": "semantic",
      "task": "autocomplete_search",
      "loc": 1186,
      "thinking_ratio": 0.16,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 2.4895,
      "perturbation_class": "semantic",
      "task": "collaborative_editor",
      "loc": 1074,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.7001,
      "perturbation_class": "semantic",
      "task": "collaborative_editor",
      "loc": 40,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 2.0531,
      "perturbation_class": "semantic",
      "task": "data_table",
      "loc": 313,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.7978,
      "perturbation_class": "semantic",
      "task": "data_table",
      "loc": 52,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 0.7,
      "cost": 2.0222,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 1093,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.4985,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 602,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0198,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 386,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0221,
      "perturbation_class": "semantic",
      "task": "collaborative_editor",
      "loc": 1227,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.6613,
      "perturbation_class": "semantic",
      "task": "data_table",
      "loc": 29,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.6,
      "cost": 0.0194,
      "perturbation_class": "semantic",
      "task": "data_table",
      "loc": 839,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.92,
      "cost": 0.0215,
      "perturbation_class": "semantic",
      "task": "factorial_compound",
      "loc": 1537,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0303,
      "perturbation_class": "semantic",
      "task": "fastapi_maintenance",
      "loc": 3021,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.0203,
      "perturbation_class": "semantic",
      "task": "form_wizard",
      "loc": 405,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0175,
      "perturbation_class": "semantic",
      "task": "mint_financial",
      "loc": 1530,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.6,
      "cost": 0.0089,
      "perturbation_class": "semantic",
      "task": "notification_system",
      "loc": 120,
      "thinking_ratio": 0.18,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0177,
      "perturbation_class": "semantic",
      "task": "search_kv_store",
      "loc": 1239,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.98,
      "cost": 0.013,
      "perturbation_class": "semantic",
      "task": "social_graph",
      "loc": 1333,
      "thinking_ratio": 0.11,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.93,
      "cost": 0.01,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 533,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.94,
      "cost": 0.0095,
      "perturbation_class": "semantic",
      "task": "twitter_timeline",
      "loc": 439,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0116,
      "perturbation_class": "semantic",
      "task": "web_crawler",
      "loc": 320,
      "thinking_ratio": 0.21,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.7,
      "correctness": 1.0,
      "cost": 0.1477,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 475,
      "thinking_ratio": 0.1,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.68,
      "correctness": 1.0,
      "cost": 0.1849,
      "perturbation_class": "semantic",
      "task": "invert_constraint_s0.5",
      "loc": 476,
      "thinking_ratio": 0.06,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.75,
      "correctness": 1.0,
      "cost": 0.0243,
      "perturbation_class": "semantic",
      "task": "invert_constraint_s0.5",
      "loc": 1115,
      "thinking_ratio": 0.09,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.0098,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 146,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.33,
      "correctness": 1.0,
      "cost": 0.0133,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r3",
      "loc": 702,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.0126,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 227,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.7,
      "correctness": 1.0,
      "cost": 0.1594,
      "perturbation_class": "semantic",
      "task": "inject_competing_goal_s0.5",
      "loc": 469,
      "thinking_ratio": 0.05,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.7,
      "correctness": 0.8,
      "cost": 0.0133,
      "perturbation_class": "manifold",
      "task": "shift_framing_s0.5",
      "loc": 439,
      "thinking_ratio": 0.11,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.35,
      "correctness": 1.0,
      "cost": 0.2848,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r2",
      "loc": 310,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6-fast",
      "label": "GPT-5.6-fast",
      "color": "rgba(59,130,246,0.60)",
      "escape": 0.74,
      "correctness": 1.0,
      "cost": 0.7548,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r2",
      "loc": 441,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.68,
      "correctness": 0.8,
      "cost": 0.0136,
      "perturbation_class": "semantic",
      "task": "invert_constraint_s0.5",
      "loc": 353,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.75,
      "correctness": 1.0,
      "cost": 0.0146,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 799,
      "thinking_ratio": 0.07,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.9975,
      "perturbation_class": "semantic",
      "task": "exp_e8bbu37m",
      "loc": 459,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.72,
      "correctness": 1.0,
      "cost": 0.0134,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 615,
      "thinking_ratio": 0.04,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.9377,
      "perturbation_class": "semantic",
      "task": "exp_ednngz36",
      "loc": 456,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.38,
      "correctness": 1.0,
      "cost": 0.0211,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r1",
      "loc": 233,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0044,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 62,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.97,
      "cost": 0.0191,
      "perturbation_class": "semantic",
      "task": "exp_er1n2rx3",
      "loc": 945,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.56,
      "correctness": 0.7,
      "cost": 0.0239,
      "perturbation_class": "semantic",
      "task": "standardized_build",
      "loc": 200,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0156,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 838,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0167,
      "perturbation_class": "semantic",
      "task": "exp_f1cezegh",
      "loc": 1178,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.62,
      "correctness": 1.0,
      "cost": 1.3579,
      "perturbation_class": "semantic",
      "task": "inject_competing_goal_s0.5",
      "loc": 1015,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.011,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 551,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.4637,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 638,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.77,
      "correctness": 1.0,
      "cost": 0.035,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 947,
      "thinking_ratio": 0.25,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.67,
      "correctness": 1.0,
      "cost": 1.3343,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 907,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.5,
      "correctness": 1.0,
      "cost": 0.02,
      "perturbation_class": "semantic",
      "task": "standardized_build",
      "loc": 558,
      "thinking_ratio": 0.11,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.75,
      "correctness": 1.0,
      "cost": 0.025,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 1133,
      "thinking_ratio": 0.09,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.73,
      "correctness": 0.8,
      "cost": 0.0127,
      "perturbation_class": "semantic",
      "task": "inject_competing_goal_s0.5",
      "loc": 662,
      "thinking_ratio": 0.09,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.78,
      "cost": 0.021,
      "perturbation_class": "semantic",
      "task": "exp_hcnattl6",
      "loc": 1070,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.4972,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 161,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0159,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 726,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.65,
      "correctness": 1.0,
      "cost": 1.1651,
      "perturbation_class": "semantic",
      "task": "invert_constraint_s0.5",
      "loc": 747,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.37,
      "correctness": 1.0,
      "cost": 0.0149,
      "perturbation_class": "semantic",
      "task": "std_final",
      "loc": 415,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0053,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 63,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.72,
      "correctness": 0.8,
      "cost": 0.0119,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 650,
      "thinking_ratio": 0.09,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.73,
      "correctness": 0.8,
      "cost": 0.0159,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 700,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.28,
      "correctness": 1.0,
      "cost": 0.0091,
      "perturbation_class": "semantic",
      "task": "standardized_test",
      "loc": 369,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.9687,
      "perturbation_class": "semantic",
      "task": "exp_jcrbm3rt",
      "loc": 432,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.96,
      "cost": 0.0109,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 444,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0081,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 281,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.46,
      "correctness": 1.0,
      "cost": 0.2664,
      "perturbation_class": "semantic",
      "task": "standardized_build",
      "loc": 268,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.82,
      "correctness": 0.2,
      "cost": 0.0105,
      "perturbation_class": "semantic",
      "task": "invert_constraint_s0.5",
      "loc": 32,
      "thinking_ratio": 0.46,
      "strategy": "wasteful",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.8868,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 387,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "color": "rgba(239,68,68,0.75)",
      "escape": 0.48,
      "correctness": 0.7,
      "cost": 0.0044,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r2",
      "loc": 165,
      "thinking_ratio": 0.17,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.66,
      "correctness": 1.0,
      "cost": 1.6062,
      "perturbation_class": "semantic",
      "task": "inject_competing_goal_s0.5",
      "loc": 904,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.73,
      "correctness": 1.0,
      "cost": 0.0634,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r1",
      "loc": 203,
      "thinking_ratio": 0.06,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0169,
      "perturbation_class": "semantic",
      "task": "exp_m3c9h6l0",
      "loc": 891,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0056,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 111,
      "thinking_ratio": 0.02,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0145,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 697,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0148,
      "perturbation_class": "semantic",
      "task": "exp_mmp26p5c",
      "loc": 756,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0081,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 221,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.72,
      "correctness": 0.8,
      "cost": 0.0133,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 560,
      "thinking_ratio": 0.06,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0206,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 694,
      "thinking_ratio": 0.32,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.71,
      "correctness": 1.0,
      "cost": 0.0762,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r1",
      "loc": 241,
      "thinking_ratio": 0.04,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.0126,
      "perturbation_class": "semantic",
      "task": "exp_nlme9vjk",
      "loc": 472,
      "thinking_ratio": 0.12,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.37,
      "correctness": 1.0,
      "cost": 0.0115,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r2",
      "loc": 504,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6-fast",
      "label": "GPT-5.6-fast",
      "color": "rgba(59,130,246,0.60)",
      "escape": 0.29,
      "correctness": 1.0,
      "cost": 0.7495,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r2",
      "loc": 407,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.63,
      "cost": 0.0104,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 386,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.44,
      "correctness": 1.0,
      "cost": 1.1104,
      "perturbation_class": "semantic",
      "task": "standardized_build",
      "loc": 600,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.35,
      "correctness": 1.0,
      "cost": 0.0179,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r1",
      "loc": 245,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.64,
      "correctness": 1.0,
      "cost": 1.8753,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 1212,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.72,
      "correctness": 0.8,
      "cost": 0.0141,
      "perturbation_class": "manifold",
      "task": "shift_framing_s0.5",
      "loc": 475,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0229,
      "perturbation_class": "semantic",
      "task": "exp_plz1xajw",
      "loc": 607,
      "thinking_ratio": 0.25,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": null,
      "correctness": 0.7,
      "cost": 0.1773,
      "perturbation_class": "semantic",
      "task": "exp_pqcfk5nr",
      "loc": 327,
      "thinking_ratio": 0.13,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.61,
      "correctness": 1.0,
      "cost": 1.5805,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 912,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.43,
      "correctness": 0.7,
      "cost": 0.9114,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r2",
      "loc": 440,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.67,
      "correctness": 1.0,
      "cost": 1.861,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 1005,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.6456,
      "perturbation_class": "semantic",
      "task": "exp_q9ckxin5",
      "loc": 267,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.74,
      "correctness": 1.0,
      "cost": 0.0168,
      "perturbation_class": "semantic",
      "task": "inject_competing_goal_s0.5",
      "loc": 948,
      "thinking_ratio": 0.06,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0197,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 925,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0097,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 391,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.9408,
      "perturbation_class": "semantic",
      "task": "exp_qu6tc1zc",
      "loc": 562,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.31,
      "correctness": 1.0,
      "cost": 0.0154,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r1",
      "loc": 770,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.29,
      "correctness": 1.0,
      "cost": 0.0159,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r2",
      "loc": 782,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.1924,
      "perturbation_class": "semantic",
      "task": "exp_rt6ocba2",
      "loc": 397,
      "thinking_ratio": 0.09,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.73,
      "correctness": 1.0,
      "cost": 0.0188,
      "perturbation_class": "semantic",
      "task": "invert_constraint_s0.5",
      "loc": 758,
      "thinking_ratio": 0.15,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0203,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 1139,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0167,
      "perturbation_class": "semantic",
      "task": "exp_s73ost4b",
      "loc": 899,
      "thinking_ratio": 0.02,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.5",
      "label": "GPT-5.5",
      "color": "rgba(251,191,36,0.60)",
      "escape": 0.71,
      "correctness": 1.0,
      "cost": 0.3159,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r1",
      "loc": 288,
      "thinking_ratio": 0.03,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.42,
      "correctness": 1.0,
      "cost": 0.0159,
      "perturbation_class": "semantic",
      "task": "std_final",
      "loc": 221,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.3088,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 427,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.3937,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 477,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.4235,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 618,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0271,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 227,
      "thinking_ratio": 0.1,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0323,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 281,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": null,
      "correctness": 0.75,
      "cost": 0.0595,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 342,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": null,
      "correctness": 0.75,
      "cost": 0.0284,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 342,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.1629,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 48,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.3609,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 230,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.38,
      "cost": 0.0064,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 227,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0158,
      "perturbation_class": "semantic",
      "task": "exp_tqnuch_d",
      "loc": 903,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.59,
      "correctness": 0.8,
      "cost": 0.9862,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 633,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.0213,
      "perturbation_class": "semantic",
      "task": "exp_u9zvdibz",
      "loc": 1127,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.43,
      "correctness": 1.0,
      "cost": 0.0106,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r1",
      "loc": 372,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.4089,
      "perturbation_class": "semantic",
      "task": "exp_uc2lmxka",
      "loc": 455,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.005,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 141,
      "thinking_ratio": 0.01,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.37,
      "correctness": 1.0,
      "cost": 0.374,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 323,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "color": "rgba(239,68,68,0.75)",
      "escape": 0.38,
      "correctness": 0.75,
      "cost": 0.0064,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5",
      "loc": 240,
      "thinking_ratio": 0.31,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.4021,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 130,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.72,
      "correctness": 0.8,
      "cost": 0.0081,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5",
      "loc": 244,
      "thinking_ratio": 0.06,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.75,
      "correctness": 0.8,
      "cost": 0.019,
      "perturbation_class": "manifold",
      "task": "shift_framing_s0.5",
      "loc": 982,
      "thinking_ratio": 0.07,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5.6-fast",
      "label": "GPT-5.6-fast",
      "color": "rgba(59,130,246,0.60)",
      "escape": 0.55,
      "correctness": 1.0,
      "cost": 0.5667,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r1",
      "loc": 291,
      "thinking_ratio": 0.04,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 0.88,
      "cost": 0.3002,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 117,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0103,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 527,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.35,
      "correctness": 1.0,
      "cost": 0.0156,
      "perturbation_class": "semantic",
      "task": "inject_phantom_success_s0.5_r2",
      "loc": 962,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.98,
      "cost": 0.0219,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 1295,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.7,
      "correctness": 1.0,
      "cost": 0.1685,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 473,
      "thinking_ratio": 0.08,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.98,
      "cost": 0.0157,
      "perturbation_class": "semantic",
      "task": "exp_wkclt_vt",
      "loc": 853,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.74,
      "correctness": 0.8,
      "cost": 0.0168,
      "perturbation_class": "manifold",
      "task": "shift_framing_s0.5",
      "loc": 921,
      "thinking_ratio": 0.1,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0145,
      "perturbation_class": "semantic",
      "task": "exp_wo07wfxb",
      "loc": 750,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.6322,
      "perturbation_class": "semantic",
      "task": "exp_wo0bkk9m",
      "loc": 298,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.0185,
      "perturbation_class": "semantic",
      "task": "exp_x5tqss1y",
      "loc": 883,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": null,
      "correctness": 0.7,
      "cost": 0.018,
      "perturbation_class": "semantic",
      "task": "exp_x8g28_k8",
      "loc": 187,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0142,
      "perturbation_class": "semantic",
      "task": "exp_xszdrm2e",
      "loc": 809,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.6,
      "correctness": 0.7,
      "cost": 1.4486,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r1",
      "loc": 768,
      "thinking_ratio": 0.0,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.38,
      "correctness": 1.0,
      "cost": 1.2247,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r2",
      "loc": 634,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0073,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 169,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 0.32,
      "cost": 0.01,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 375,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.73,
      "correctness": 0.8,
      "cost": 0.02,
      "perturbation_class": "manifold",
      "task": "inject_alien_vocab_s0.5",
      "loc": 742,
      "thinking_ratio": 0.06,
      "strategy": "exploratory",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": null,
      "correctness": 1.0,
      "cost": 0.0165,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 885,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.32,
      "correctness": 1.0,
      "cost": 0.0138,
      "perturbation_class": "semantic",
      "task": "standardized_retry",
      "loc": 314,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": null,
      "correctness": 0.8,
      "cost": 0.2201,
      "perturbation_class": "semantic",
      "task": "exp_zpgio1qs",
      "loc": 514,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "wasteful"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.42,
      "correctness": 1.0,
      "cost": 0.011,
      "perturbation_class": "semantic",
      "task": "remove_critical_constraint_s0.5_r1",
      "loc": 484,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "wasteful"
    }
  ],
  "sonar": {},
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
        "cells": 22,
        "total_cost": 1.499069,
        "avg_cost": 0.06814,
        "total_tokens": 5116663,
        "avg_cache_hit": 0.965,
        "avg_duration_s": 1290.0
      },
      {
        "model": "openai/gpt-5.6-luna",
        "cells": 23,
        "total_cost": 2.100259,
        "avg_cost": 0.091316,
        "total_tokens": 885142,
        "avg_cache_hit": 0.971,
        "avg_duration_s": 540.0
      },
      {
        "model": "deepseek/deepseek-v4-pro",
        "cells": 31,
        "total_cost": 4.66263,
        "avg_cost": 0.150407,
        "total_tokens": 5485954,
        "avg_cache_hit": 0.762,
        "avg_duration_s": 1698.0
      },
      {
        "model": "openai/gpt-5.6-terra",
        "cells": 20,
        "total_cost": 20.303648,
        "avg_cost": 1.015182,
        "total_tokens": 3239989,
        "avg_cache_hit": 0.821,
        "avg_duration_s": 731.0
      },
      {
        "model": "anthropic/claude-haiku-4-5",
        "cells": 20,
        "total_cost": 21.516785,
        "avg_cost": 1.075839,
        "total_tokens": 1096509,
        "avg_cache_hit": 0.692,
        "avg_duration_s": 705.0
      },
      {
        "model": "anthropic/claude-sonnet-5",
        "cells": 20,
        "total_cost": 76.417905,
        "avg_cost": 3.820895,
        "total_tokens": 1617762,
        "avg_cache_hit": 0.789,
        "avg_duration_s": 958.0
      },
      {
        "model": "openai/gpt-5.6-sol",
        "cells": 23,
        "total_cost": 91.693651,
        "avg_cost": 3.98668,
        "total_tokens": 5546328,
        "avg_cache_hit": 0.849,
        "avg_duration_s": 1233.0
      }
    ],
    "conditions": [
      {
        "condition": "bad_seed",
        "cells": 44,
        "variants": 6,
        "total_cost": 59.719593,
        "avg_cost": 1.357263,
        "success": 39,
        "fail": 5
      },
      {
        "condition": "clean",
        "cells": 90,
        "variants": 12,
        "total_cost": 119.36938,
        "avg_cost": 1.326326,
        "success": 81,
        "fail": 9
      },
      {
        "condition": "early_degrade",
        "cells": 25,
        "variants": 12,
        "total_cost": 39.104974,
        "avg_cost": 1.564199,
        "success": 25,
        "fail": 0
      }
    ],
    "stories": [
      {
        "story": "task_manager_api",
        "cells": 59,
        "total_cost": 62.785346,
        "avg_cost": 1.064158,
        "sessions": 293,
        "avg_duration_s": 897.0,
        "avg_tokens_per_session": 22220.0
      },
      {
        "story": "notification_service",
        "cells": 49,
        "total_cost": 75.452126,
        "avg_cost": 1.539839,
        "sessions": 243,
        "avg_duration_s": 1220.0,
        "avg_tokens_per_session": 32293.0
      },
      {
        "story": "static_site_gen",
        "cells": 51,
        "total_cost": 79.956474,
        "avg_cost": 1.567774,
        "sessions": 251,
        "avg_duration_s": 1118.0,
        "avg_tokens_per_session": 33419.0
      }
    ],
    "tiers": [
      {
        "tier": "tier1_minimal",
        "quality": "bad",
        "cells": 30,
        "avg_cost": 1.306853,
        "avg_tokens_per_session": 30530.0,
        "avg_session_duration_s": 231.0
      },
      {
        "tier": "tier1_minimal",
        "quality": "good",
        "cells": 54,
        "avg_cost": 1.512277,
        "avg_tokens_per_session": 29014.0,
        "avg_session_duration_s": 237.0
      },
      {
        "tier": "tier2_small",
        "quality": "bad",
        "cells": 27,
        "avg_cost": 1.035831,
        "avg_tokens_per_session": 26909.0,
        "avg_session_duration_s": 209.0
      },
      {
        "tier": "tier2_small",
        "quality": "good",
        "cells": 48,
        "avg_cost": 1.444958,
        "avg_tokens_per_session": 28926.0,
        "avg_session_duration_s": 194.0
      }
    ],
    "sessions": {
      "total": 787,
      "total_cost": 218.19394637999997,
      "total_tokens": 22683067,
      "total_cache_reads": 552989323,
      "cache_hit_rate": 0.977,
      "duration_s": 169706.8773381479,
      "successful": 723,
      "failed": 64
    },
    "generated_at": "2026-08-15T20:15:40.668857+00:00"
  },
  "reviews": {
    "models": [
      {
        "model": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "stories": 2,
        "overall_coherence": 0.925,
        "architectural_fit": 0.814,
        "convention_adherence": 0.681,
        "better_pct": 80.0,
        "worse_pct": 0.0,
        "neutral_pct": 20.0,
        "top_issues": [
          {
            "theme": "security",
            "count": 2
          },
          {
            "theme": "other",
            "count": 1
          },
          {
            "theme": "missing surface",
            "count": 1
          },
          {
            "theme": "incomplete refactor",
            "count": 1
          },
          {
            "theme": "schema drift",
            "count": 1
          }
        ]
      },
      {
        "model": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "stories": 22,
        "overall_coherence": 0.897,
        "architectural_fit": 0.745,
        "convention_adherence": 0.693,
        "better_pct": 72.7,
        "worse_pct": 7.3,
        "neutral_pct": 13.6,
        "top_issues": [
          {
            "theme": "other",
            "count": 32
          },
          {
            "theme": "incomplete refactor",
            "count": 18
          },
          {
            "theme": "security",
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
        "model": "deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "stories": 21,
        "overall_coherence": 0.883,
        "architectural_fit": 0.748,
        "convention_adherence": 0.726,
        "better_pct": 60.8,
        "worse_pct": 13.4,
        "neutral_pct": 20.6,
        "top_issues": [
          {
            "theme": "other",
            "count": 30
          },
          {
            "theme": "incomplete refactor",
            "count": 20
          },
          {
            "theme": "security",
            "count": 18
          },
          {
            "theme": "test gaps",
            "count": 12
          },
          {
            "theme": "schema drift",
            "count": 9
          }
        ]
      },
      {
        "model": "?",
        "label": "?",
        "stories": 27,
        "overall_coherence": 0.877,
        "architectural_fit": 0.763,
        "convention_adherence": 0.715,
        "better_pct": 69.7,
        "worse_pct": 9.8,
        "neutral_pct": 18.2,
        "top_issues": [
          {
            "theme": "other",
            "count": 45
          },
          {
            "theme": "security",
            "count": 25
          },
          {
            "theme": "test gaps",
            "count": 25
          },
          {
            "theme": "incomplete refactor",
            "count": 13
          },
          {
            "theme": "missing surface",
            "count": 9
          }
        ]
      }
    ],
    "commit_reviews": 349,
    "story_reviews": 72,
    "reviewer": "deepseek/deepseek-v4-flash"
  },
  "analysis": {
    "models": [
      {
        "model": "?",
        "label": "?",
        "commits": 384,
        "lines_added": 145141,
        "lines_removed": 17723,
        "functions_added": 2954,
        "classes_added": 359,
        "imports_added": 2641,
        "sonar_available": 0,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 0,
        "sonar_complexity_delta": 0,
        "avg_convention": 0.729,
        "deep_cells": 77,
        "lsp_available": 0,
        "lsp_errors_per_cell": 0.0,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 0.831,
        "solution_constraints": 0.926,
        "solution_quality": 0.1,
        "solution_novelty": 0.757,
        "solution_composite": 0.702,
        "basin_escape": 0.63,
        "strategies": {
          "exploratory": 64,
          "conservative": 13
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
        "sonar_available": 0,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 0,
        "sonar_complexity_delta": 0,
        "avg_convention": 0.686,
        "deep_cells": 22,
        "lsp_available": 0,
        "lsp_errors_per_cell": 0.0,
        "lsp_warnings_per_cell": 0.0,
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
        "lsp_errors_per_cell": 0.0,
        "lsp_warnings_per_cell": 0.0,
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
        "model": "deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "commits": 99,
        "lines_added": 57302,
        "lines_removed": 3752,
        "functions_added": 650,
        "classes_added": 155,
        "imports_added": 710,
        "sonar_available": 0,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 0,
        "sonar_complexity_delta": 0,
        "avg_convention": 0.747,
        "deep_cells": 21,
        "lsp_available": 0,
        "lsp_errors_per_cell": 0.0,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 1.0,
        "solution_constraints": 1.0,
        "solution_quality": 0.048,
        "solution_novelty": 0.797,
        "solution_composite": 0.779,
        "basin_escape": 0.659,
        "strategies": {
          "exploratory": 21
        }
      },
      {
        "model": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "commits": 95,
        "lines_added": 34841,
        "lines_removed": 2164,
        "functions_added": 1164,
        "classes_added": 83,
        "imports_added": 803,
        "sonar_available": 0,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 0,
        "sonar_complexity_delta": 0,
        "avg_convention": 0.737,
        "deep_cells": 19,
        "lsp_available": 0,
        "lsp_errors_per_cell": 0.0,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 0.684,
        "solution_constraints": 0.895,
        "solution_quality": 0.114,
        "solution_novelty": 0.619,
        "solution_composite": 0.623,
        "basin_escape": 0.505,
        "strategies": {
          "conservative": 6,
          "exploratory": 13
        }
      },
      {
        "model": "claude-haiku-4-5",
        "label": "claude-haiku-4-5",
        "commits": 90,
        "lines_added": 30229,
        "lines_removed": 2094,
        "functions_added": 281,
        "classes_added": 160,
        "imports_added": 377,
        "sonar_available": 0,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 0,
        "sonar_complexity_delta": 0,
        "avg_convention": 0.763,
        "deep_cells": 18,
        "lsp_available": 0,
        "lsp_errors_per_cell": 0.0,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 0.556,
        "solution_constraints": 0.852,
        "solution_quality": 0.143,
        "solution_novelty": 0.561,
        "solution_composite": 0.563,
        "basin_escape": 0.476,
        "strategies": {
          "exploratory": 10,
          "conservative": 8
        }
      },
      {
        "model": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "commits": 110,
        "lines_added": 18041,
        "lines_removed": 6258,
        "functions_added": 543,
        "classes_added": 60,
        "imports_added": 711,
        "sonar_available": 0,
        "sonar_bugs_delta": 0,
        "sonar_smells_delta": 0,
        "sonar_complexity_delta": 0,
        "avg_convention": 0.691,
        "deep_cells": 22,
        "lsp_available": 0,
        "lsp_errors_per_cell": 0.0,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 1.0,
        "solution_constraints": 0.985,
        "solution_quality": 0.086,
        "solution_novelty": 0.879,
        "solution_composite": 0.794,
        "basin_escape": 0.694,
        "strategies": {
          "exploratory": 22
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
        "lsp_errors_per_cell": 0.0,
        "lsp_warnings_per_cell": 0.0,
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
    "stories_analyzed": 222,
    "commits_analyzed": 1102,
    "sonar_commits_available": 0
  },
  "labs": {
    "verification_frontier": {
      "experiment_id": "lab_verification_frontier",
      "generated_at": "2026-08-15T22:14:29.429029",
      "summary": {
        "models": 7,
        "cheapest": "deepseek-v4-flash",
        "most_verified": "claude-haiku-4-5",
        "pareto_frontier": [
          "deepseek-v4-flash",
          "deepseek-v4-pro",
          "claude-haiku-4-5"
        ]
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 22,
          "cost_cells": 22,
          "avg_cost": 0.068,
          "avg_tests": 36.364,
          "total_cost": 1.4991,
          "total_tests": 800
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 23,
          "cost_cells": 23,
          "avg_cost": 0.091,
          "avg_tests": 7.739,
          "total_cost": 2.1003,
          "total_tests": 178
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 31,
          "cost_cells": 31,
          "avg_cost": 0.15,
          "avg_tests": 47.774,
          "total_cost": 4.6626,
          "total_tests": 1481
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 20,
          "cost_cells": 20,
          "avg_cost": 1.015,
          "avg_tests": 9.75,
          "total_cost": 20.3036,
          "total_tests": 195
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 20,
          "cost_cells": 14,
          "avg_cost": 1.537,
          "avg_tests": 135.35,
          "total_cost": 21.5168,
          "total_tests": 2707
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 23,
          "cost_cells": 23,
          "avg_cost": 3.987,
          "avg_tests": 11.957,
          "total_cost": 91.6937,
          "total_tests": 275
        },
        {
          "model": "claude-sonnet-5",
          "cells": 20,
          "cost_cells": 16,
          "avg_cost": 4.776,
          "avg_tests": 122.55,
          "total_cost": 76.4179,
          "total_tests": 2451
        }
      ]
    },
    "story_arc": {
      "experiment_id": "lab_story_arc",
      "generated_at": "2026-08-15T22:14:18.112053",
      "summary": {
        "snowball_factor": 2.38,
        "session1_cost": 0.1557,
        "session5_cost": 0.3706
      },
      "sessions": [
        {
          "session_number": 1,
          "task_type": "greenfield",
          "n": 159,
          "avg_cost": 0.1557,
          "avg_tokens": 19980.0,
          "avg_tests": 4.6
        },
        {
          "session_number": 2,
          "task_type": "feature",
          "n": 159,
          "avg_cost": 0.2126,
          "avg_tokens": 25786.0,
          "avg_tests": 8.7
        },
        {
          "session_number": 3,
          "task_type": "integration",
          "n": 159,
          "avg_cost": 0.3433,
          "avg_tokens": 32558.0,
          "avg_tests": 11.4
        },
        {
          "session_number": 4,
          "task_type": "refactor",
          "n": 155,
          "avg_cost": 0.3072,
          "avg_tokens": 32313.0,
          "avg_tests": 11.5
        },
        {
          "session_number": 5,
          "task_type": "cross_cutting",
          "n": 155,
          "avg_cost": 0.3706,
          "avg_tokens": 38607.0,
          "avg_tests": 15.3
        }
      ],
      "by_condition": {
        "bad_seed_s1": 0.1928,
        "bad_seed_s2": 0.2459,
        "bad_seed_s3": 0.3771,
        "bad_seed_s4": 0.2936,
        "bad_seed_s5": 0.372,
        "clean_s1": 0.1398,
        "clean_s2": 0.2011,
        "clean_s3": 0.3269,
        "clean_s4": 0.2753,
        "clean_s5": 0.3587,
        "early_degrade_s1": 0.1562,
        "early_degrade_s2": 0.2028,
        "early_degrade_s3": 0.3505,
        "early_degrade_s4": 0.4437,
        "early_degrade_s5": 0.411
      },
      "by_model": {
        "claude-haiku-4-5": {
          "1": 0.1364,
          "2": 0.1799,
          "3": 0.2324,
          "4": 0.1694,
          "5": 0.3577
        },
        "claude-sonnet-5": {
          "1": 0.3688,
          "2": 0.5352,
          "3": 1.068,
          "4": 0.6568,
          "5": 1.1921
        },
        "deepseek-v4-flash": {
          "1": 0.0058,
          "2": 0.0099,
          "3": 0.0154,
          "4": 0.014,
          "5": 0.0231
        },
        "deepseek-v4-pro": {
          "1": 0.0177,
          "2": 0.0227,
          "3": 0.0401,
          "4": 0.0292,
          "5": 0.0511
        },
        "gpt-5.6-luna": {
          "1": 0.0129,
          "2": 0.0168,
          "3": 0.0185,
          "4": 0.0211,
          "5": 0.022
        },
        "gpt-5.6-sol": {
          "1": 0.4785,
          "2": 0.6551,
          "3": 0.9675,
          "4": 1.0774,
          "5": 0.8082
        },
        "gpt-5.6-terra": {
          "1": 0.1337,
          "2": 0.1564,
          "3": 0.2156,
          "4": 0.2367,
          "5": 0.2728
        }
      }
    },
    "condition_effects": {
      "experiment_id": "lab_condition_effects",
      "generated_at": "2026-08-15T22:09:58.344415",
      "summary": {
        "conditions": 3
      },
      "conditions": [
        {
          "condition": "bad_seed",
          "cells": 40,
          "success_rate": 0.875,
          "cascade_rate": 0.025,
          "avg_cost": 1.4815,
          "total_cost": 59.2605
        },
        {
          "condition": "clean",
          "cells": 94,
          "success_rate": 0.904,
          "cascade_rate": 0.0,
          "avg_cost": 1.2748,
          "total_cost": 119.8285
        },
        {
          "condition": "early_degrade",
          "cells": 25,
          "success_rate": 1.0,
          "cascade_rate": 0.08,
          "avg_cost": 1.5642,
          "total_cost": 39.105
        }
      ]
    },
    "verification_value": {
      "experiment_id": "lab_verification_value",
      "generated_at": "2026-08-15T22:14:29.488567",
      "summary": {
        "correlation_tests_vs_worse_rate": -0.077,
        "cells": 30
      },
      "rows": [
        {
          "model": "?",
          "tests": 0,
          "reviews": 132,
          "better_rate": 0.697,
          "worse_rate": 0.098
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
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.6
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
          "reviews": 7,
          "better_rate": 0.714,
          "worse_rate": 0.0
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
          "tests": 46,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.2
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 47,
          "reviews": 10,
          "better_rate": 0.7,
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
          "tests": 82,
          "reviews": 5,
          "better_rate": 0.6,
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
        }
      ]
    },
    "cache_economics": {
      "experiment_id": "lab_cache_economics",
      "generated_at": "2026-08-15T22:09:58.250797",
      "summary": {
        "models": 7
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 22,
          "avg_cost": 0.068,
          "avg_cache_hit": 0.965,
          "cache_reads": 150797952,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 7087028.0,
          "avg_tokens_per_cell": 232576.0
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 23,
          "avg_cost": 0.091,
          "avg_cache_hit": 0.971,
          "cache_reads": 29738784,
          "cache_writes": 2378880,
          "read_write_ratio": 12.5,
          "avg_context_per_cell": 1331475.0,
          "avg_tokens_per_cell": 38484.0
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 31,
          "avg_cost": 0.15,
          "avg_cache_hit": 0.762,
          "cache_reads": 105461376,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 3578946.0,
          "avg_tokens_per_cell": 176966.0
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 20,
          "avg_cost": 1.015,
          "avg_cache_hit": 0.821,
          "cache_reads": 14951424,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 909571.0,
          "avg_tokens_per_cell": 161999.0
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 20,
          "avg_cost": 1.537,
          "avg_cache_hit": 0.692,
          "cache_reads": 102433886,
          "cache_writes": 2753242,
          "read_write_ratio": 37.2,
          "avg_context_per_cell": 5176520.0,
          "avg_tokens_per_cell": 54825.0
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 23,
          "avg_cost": 3.987,
          "avg_cache_hit": 0.849,
          "cache_reads": 34351104,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 1734671.0,
          "avg_tokens_per_cell": 241145.0
        },
        {
          "model": "claude-sonnet-5",
          "cells": 20,
          "avg_cost": 4.776,
          "avg_cache_hit": 0.789,
          "cache_reads": 115254797,
          "cache_writes": 3460787,
          "read_write_ratio": 33.3,
          "avg_context_per_cell": 5843628.0,
          "avg_tokens_per_cell": 80888.0
        }
      ]
    },
    "quality_frontier": {
      "experiment_id": "lab_quality_frontier",
      "generated_at": "2026-08-15T22:14:18.060885",
      "summary": {
        "models": 7
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 22,
          "avg_cost": 0.068,
          "lsp_errors_per_cell": 0.0,
          "code_quality_score": 0.037,
          "cyclomatic_complexity": 475.455,
          "novelty_score": 0.87
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 22,
          "avg_cost": 0.091,
          "lsp_errors_per_cell": 0.0,
          "code_quality_score": 0.086,
          "cyclomatic_complexity": 266.091,
          "novelty_score": 0.879
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 21,
          "avg_cost": 0.128,
          "lsp_errors_per_cell": 0.0,
          "code_quality_score": 0.048,
          "cyclomatic_complexity": 262.143,
          "novelty_score": 0.797
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 20,
          "avg_cost": 1.015,
          "lsp_errors_per_cell": 0.0,
          "code_quality_score": 0.088,
          "cyclomatic_complexity": 233.8,
          "novelty_score": 0.901
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 12,
          "avg_cost": 1.5,
          "lsp_errors_per_cell": 0.0,
          "code_quality_score": 0.143,
          "cyclomatic_complexity": 275.0,
          "novelty_score": 0.561
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 23,
          "avg_cost": 3.987,
          "lsp_errors_per_cell": 0.0,
          "code_quality_score": 0.054,
          "cyclomatic_complexity": 297.348,
          "novelty_score": 0.917
        },
        {
          "model": "claude-sonnet-5",
          "cells": 15,
          "avg_cost": 4.807,
          "lsp_errors_per_cell": 0.0,
          "code_quality_score": 0.114,
          "cyclomatic_complexity": 314.789,
          "novelty_score": 0.619
        }
      ]
    }
  }
};
