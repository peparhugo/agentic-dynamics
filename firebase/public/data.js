/* Generated 2026-08-14 13:11:00 UTC by build_data.py */
/* DO NOT EDIT — regenerate with: python scripts/build_data.py */
window.DYNAMICS_DATA = {
  "_meta": {
    "generated_at": "2026-08-14T13:11:00.721433+00:00",
    "provenance_note": "All values tagged [M]easured, [C]omputed, [H]euristic, or e[X]ternal. See methodology.html."
  },
  "summary": {
    "worktrees_total": 205,
    "sessions_total": 1097,
    "game_reports": 224,
    "total_cost": 288.6909,
    "architectures": 3,
    "variants": 7,
    "stories_total": 221,
    "stories_unique": 210,
    "stories_re_runs": 11,
    "story_sessions": 1097,
    "story_total_cost": 288.6909,
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
      "cells": 30,
      "unique_cells": 30,
      "re_runs": 0,
      "sessions": 150,
      "total_cost": 2.044974,
      "avg_cost": 0.068166,
      "cost_cells": 30,
      "avg_cache_hit": 0.964,
      "avg_tests": 33.5,
      "avg_test_code_ratio": 0.658,
      "avg_tok_per_session": 46576.0,
      "avg_duration_s": 1386.0,
      "avg_code_lines": 2294.0,
      "tests_total": 1006,
      "tests_passed": 3112,
      "tests_run": 3114,
      "pass_rate": "100% (3112/3114)",
      "avg_cost_per_session": 0.013633,
      "avg_loc": 2294.0,
      "avg_energy_j": 52973.5,
      "avg_energy_j_per_loc": 23.09,
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
      "id": "openai/gpt-5.6-luna",
      "label": "GPT-5.6 Luna",
      "provider": "openai",
      "cells": 34,
      "unique_cells": 30,
      "re_runs": 4,
      "sessions": 170,
      "total_cost": 3.085027,
      "avg_cost": 0.090736,
      "cost_cells": 34,
      "avg_cache_hit": 0.975,
      "avg_tests": 7.3,
      "avg_test_code_ratio": 0.275,
      "avg_tok_per_session": 6324.0,
      "avg_duration_s": 528.0,
      "avg_code_lines": 714.0,
      "tests_total": 249,
      "tests_passed": 861,
      "tests_run": 861,
      "pass_rate": "100% (861/861)",
      "avg_cost_per_session": 0.018147,
      "avg_loc": 714.0,
      "avg_energy_j": 9295.3,
      "avg_energy_j_per_loc": 13.02,
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
      "cells": 35,
      "unique_cells": 30,
      "re_runs": 5,
      "sessions": 167,
      "total_cost": 4.822804,
      "avg_cost": 0.137794,
      "cost_cells": 35,
      "avg_cache_hit": 0.778,
      "avg_tests": 34.4,
      "avg_test_code_ratio": 1.087,
      "avg_tok_per_session": 34702.0,
      "avg_duration_s": 1675.0,
      "avg_code_lines": 1384.0,
      "tests_total": 1204,
      "tests_passed": 3489,
      "tests_run": 3499,
      "pass_rate": "100% (3489/3499)",
      "avg_cost_per_session": 0.028879,
      "avg_loc": 1384.0,
      "avg_energy_j": 33592.0,
      "avg_energy_j_per_loc": 24.27,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 0,
      "strategy_expl": 35,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "reports": 35,
      "reports_valid": 35,
      "reports_narrated": 0
    },
    {
      "id": "openai/gpt-5.6-terra",
      "label": "openai/gpt-5.6-terra",
      "provider": "openai",
      "cells": 30,
      "unique_cells": 30,
      "re_runs": 0,
      "sessions": 150,
      "total_cost": 30.640397,
      "avg_cost": 1.021347,
      "cost_cells": 30,
      "avg_cache_hit": 0.819,
      "avg_tests": 8.8,
      "avg_test_code_ratio": 0.331,
      "avg_tok_per_session": 33004.0,
      "avg_duration_s": 775.0,
      "avg_code_lines": 708.0,
      "tests_total": 265,
      "tests_passed": 1033,
      "tests_run": 1033,
      "pass_rate": "100% (1033/1033)",
      "avg_cost_per_session": 0.204269,
      "avg_loc": 708.0,
      "avg_energy_j": 19012.1,
      "avg_energy_j_per_loc": 26.85,
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
      "cells": 31,
      "unique_cells": 30,
      "re_runs": 1,
      "sessions": 155,
      "total_cost": 30.216397,
      "avg_cost": 1.590337,
      "cost_cells": 19,
      "avg_cache_hit": 0.606,
      "avg_tests": 117.4,
      "avg_test_code_ratio": 1.022,
      "avg_tok_per_session": 10082.0,
      "avg_duration_s": 632.0,
      "avg_code_lines": 1862.0,
      "tests_total": 3638,
      "tests_passed": 0,
      "tests_run": 0,
      "pass_rate": "unknown",
      "avg_cost_per_session": 0.318067,
      "avg_loc": 1862.0,
      "avg_energy_j": 11472.9,
      "avg_energy_j_per_loc": 6.16,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 12,
      "strategy_expl": 17,
      "strategy_waste": 2,
      "strategy_efficient": 0,
      "reports": 31,
      "reports_valid": 31,
      "reports_narrated": 0
    },
    {
      "id": "openai/gpt-5.6-sol",
      "label": "openai/gpt-5.6-sol",
      "provider": "openai",
      "cells": 30,
      "unique_cells": 30,
      "re_runs": 0,
      "sessions": 150,
      "total_cost": 112.46246,
      "avg_cost": 3.748749,
      "cost_cells": 30,
      "avg_cache_hit": 0.843,
      "avg_tests": 12.9,
      "avg_test_code_ratio": 0.423,
      "avg_tok_per_session": 46888.0,
      "avg_duration_s": 1203.0,
      "avg_code_lines": 1166.0,
      "tests_total": 387,
      "tests_passed": 1776,
      "tests_run": 1776,
      "pass_rate": "100% (1776/1776)",
      "avg_cost_per_session": 0.74975,
      "avg_loc": 1166.0,
      "avg_energy_j": 27904.9,
      "avg_energy_j_per_loc": 23.93,
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
      "cells": 31,
      "unique_cells": 30,
      "re_runs": 1,
      "sessions": 155,
      "total_cost": 105.418795,
      "avg_cost": 4.583426,
      "cost_cells": 23,
      "avg_cache_hit": 0.731,
      "avg_tests": 122.1,
      "avg_test_code_ratio": 0.647,
      "avg_tok_per_session": 14312.0,
      "avg_duration_s": 844.0,
      "avg_code_lines": 2129.0,
      "tests_total": 3786,
      "tests_passed": 455,
      "tests_run": 455,
      "pass_rate": "100% (455/455)",
      "avg_cost_per_session": 0.916685,
      "avg_loc": 2129.0,
      "avg_energy_j": 16416.3,
      "avg_energy_j_per_loc": 7.71,
      "narration_rate": null,
      "avg_narration_penalty": null,
      "strategy_cons": 8,
      "strategy_expl": 18,
      "strategy_waste": 5,
      "strategy_efficient": 0,
      "reports": 31,
      "reports_valid": 31,
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
      0.068166,
      0.090736,
      0.137794,
      1.021347,
      1.590337,
      3.748749,
      4.583426
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
      2294.0,
      714.0,
      1384.0,
      708.0,
      1862.0,
      1166.0,
      2129.0
    ],
    "costY": [
      0.068166,
      0.090736,
      0.137794,
      1.021347,
      1.590337,
      3.748749,
      4.583426
    ],
    "reports": [
      30,
      34,
      35,
      30,
      31,
      30,
      31
    ]
  },
  "calculator": {
    "model_costs": [
      {
        "n": "DeepSeek v4 Flash",
        "c": 0.068166,
        "p": 1.0
      },
      {
        "n": "GPT-5.6 Luna",
        "c": 0.090736,
        "p": 1.0
      },
      {
        "n": "DeepSeek v4 Pro",
        "c": 0.137794,
        "p": 1.0
      },
      {
        "n": "openai/gpt-5.6-terra",
        "c": 1.021347,
        "p": 1.0
      },
      {
        "n": "anthropic/claude-haiku-4-5",
        "c": 1.590337,
        "p": 0
      },
      {
        "n": "openai/gpt-5.6-sol",
        "c": 3.748749,
        "p": 1.0
      },
      {
        "n": "Claude Sonnet 5",
        "c": 4.583426,
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
        "e": 2.0
      },
      {
        "m": "DS\u2192openai/gpt-5.6-terra",
        "e": 15.0
      },
      {
        "m": "DS\u2192anthropic/claude-haiku-4-5",
        "e": 23.3
      },
      {
        "m": "DS\u2192openai/gpt-5.6-sol",
        "e": 55.0
      },
      {
        "m": "DS\u21925",
        "e": 67.2
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
    "cost_gap_computation": "$1.590337 / $0.068166 = 23.3\u00d7",
    "overall_pass_rate": "99.9% (10726/10738) [tests]",
    "total_tests_passed": 10726,
    "total_tests_run": 10738,
    "total_cost_all_models": 288.6909,
    "total_cost_deepseek": 6.8678,
    "total_cost_claude": 135.6352,
    "total_narrated": 0,
    "total_valid_reports": 221,
    "total_reports_analyzed": 221,
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
      "avg_energy_j": 11472.9,
      "avg_energy_j_per_loc": 6.16,
      "avg_cost": 1.590337,
      "avg_loc": 1862.0
    },
    {
      "id": "anthropic/claude-sonnet-5",
      "label": "Claude Sonnet 5",
      "avg_energy_j": 16416.3,
      "avg_energy_j_per_loc": 7.71,
      "avg_cost": 4.583426,
      "avg_loc": 2129.0
    },
    {
      "id": "openai/gpt-5.6-luna",
      "label": "GPT-5.6 Luna",
      "avg_energy_j": 9295.3,
      "avg_energy_j_per_loc": 13.02,
      "avg_cost": 0.090736,
      "avg_loc": 714.0
    },
    {
      "id": "deepseek/deepseek-v4-flash",
      "label": "DeepSeek v4 Flash",
      "avg_energy_j": 52973.5,
      "avg_energy_j_per_loc": 23.09,
      "avg_cost": 0.068166,
      "avg_loc": 2294.0
    },
    {
      "id": "openai/gpt-5.6-sol",
      "label": "openai/gpt-5.6-sol",
      "avg_energy_j": 27904.9,
      "avg_energy_j_per_loc": 23.93,
      "avg_cost": 3.748749,
      "avg_loc": 1166.0
    },
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "avg_energy_j": 33592.0,
      "avg_energy_j_per_loc": 24.27,
      "avg_cost": 0.137794,
      "avg_loc": 1384.0
    },
    {
      "id": "openai/gpt-5.6-terra",
      "label": "openai/gpt-5.6-terra",
      "avg_energy_j": 19012.1,
      "avg_energy_j_per_loc": 26.85,
      "avg_cost": 1.021347,
      "avg_loc": 708.0
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.0241,
      "perturbation_class": "semantic",
      "task": "exp_0s36_d3n",
      "loc": 1008,
      "thinking_ratio": 0.11,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0214,
      "perturbation_class": "semantic",
      "task": "exp_1erxln69",
      "loc": 1266,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "color": "rgba(239,68,68,0.75)",
      "escape": 0.43,
      "correctness": 0.7,
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 2.2412,
      "perturbation_class": "semantic",
      "task": "exp_1spl4mgd",
      "loc": 1327,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.751,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 436,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.4696,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 159,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0087,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 211,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0104,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 207,
      "thinking_ratio": 0.09,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0217,
      "perturbation_class": "semantic",
      "task": "exp_37z0nq68",
      "loc": 796,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 1.2564,
      "perturbation_class": "semantic",
      "task": "exp_3hlb2bus",
      "loc": 581,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.8723,
      "perturbation_class": "semantic",
      "task": "exp_3j2vrct4",
      "loc": 463,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0163,
      "perturbation_class": "semantic",
      "task": "exp_3zxicj_v",
      "loc": 840,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0237,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 1446,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.017,
      "perturbation_class": "semantic",
      "task": "exp_6462vbw3",
      "loc": 748,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "color": "rgba(239,68,68,0.75)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.0037,
      "perturbation_class": "semantic",
      "task": "exp_6ij8p3sl",
      "loc": 182,
      "thinking_ratio": 0.15,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.3907,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 126,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0059,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 92,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "correctness": 0.8,
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0214,
      "perturbation_class": "semantic",
      "task": "exp_9o_y1a_8",
      "loc": 1030,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.4122,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 133,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0104,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 385,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0337,
      "perturbation_class": "semantic",
      "task": "exp__ygf4hz3",
      "loc": 910,
      "thinking_ratio": 0.31,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0142,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 706,
      "thinking_ratio": 0.13,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.0217,
      "perturbation_class": "semantic",
      "task": "exp_aqqqi9v5",
      "loc": 1220,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.2,
      "cost": 0.0185,
      "perturbation_class": "semantic",
      "task": "exp_arc_7as6",
      "loc": 4,
      "thinking_ratio": 0.75,
      "strategy": "wasteful",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 1.3795,
      "perturbation_class": "semantic",
      "task": "exp_b48bnosz",
      "loc": 729,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0047,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 95,
      "thinking_ratio": 0.02,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.24,
      "correctness": 0.7,
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.018,
      "perturbation_class": "semantic",
      "task": "autocomplete_search",
      "loc": 1186,
      "thinking_ratio": 0.16,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 2.4895,
      "perturbation_class": "semantic",
      "task": "collaborative_editor",
      "loc": 1074,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.7001,
      "perturbation_class": "semantic",
      "task": "collaborative_editor",
      "loc": 40,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 2.0531,
      "perturbation_class": "semantic",
      "task": "data_table",
      "loc": 313,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.7978,
      "perturbation_class": "semantic",
      "task": "data_table",
      "loc": 52,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 2.0222,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 1093,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.4985,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 602,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0198,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 386,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0221,
      "perturbation_class": "semantic",
      "task": "collaborative_editor",
      "loc": 1227,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 0.6,
      "cost": 0.6613,
      "perturbation_class": "semantic",
      "task": "data_table",
      "loc": 29,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.6,
      "cost": 0.0194,
      "perturbation_class": "semantic",
      "task": "data_table",
      "loc": 839,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0215,
      "perturbation_class": "semantic",
      "task": "factorial_compound",
      "loc": 1537,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0303,
      "perturbation_class": "semantic",
      "task": "fastapi_maintenance",
      "loc": 3021,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.0203,
      "perturbation_class": "semantic",
      "task": "form_wizard",
      "loc": 405,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0175,
      "perturbation_class": "semantic",
      "task": "mint_financial",
      "loc": 1530,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.6,
      "cost": 0.0089,
      "perturbation_class": "semantic",
      "task": "notification_system",
      "loc": 120,
      "thinking_ratio": 0.18,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0177,
      "perturbation_class": "semantic",
      "task": "search_kv_store",
      "loc": 1239,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.013,
      "perturbation_class": "semantic",
      "task": "social_graph",
      "loc": 1333,
      "thinking_ratio": 0.11,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.01,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 533,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0095,
      "perturbation_class": "semantic",
      "task": "twitter_timeline",
      "loc": 439,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0116,
      "perturbation_class": "semantic",
      "task": "web_crawler",
      "loc": 320,
      "thinking_ratio": 0.21,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.7,
      "correctness": 0.8,
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
      "correctness": 0.8,
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
      "correctness": 0.8,
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
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.0098,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 146,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.0126,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 227,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.9975,
      "perturbation_class": "semantic",
      "task": "exp_e8bbu37m",
      "loc": 459,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.9377,
      "perturbation_class": "semantic",
      "task": "exp_ednngz36",
      "loc": 456,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.38,
      "correctness": 0.7,
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
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.0044,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 62,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0191,
      "perturbation_class": "semantic",
      "task": "exp_er1n2rx3",
      "loc": 945,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0156,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 838,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0167,
      "perturbation_class": "semantic",
      "task": "exp_f1cezegh",
      "loc": 1178,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.011,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 551,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.4637,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 638,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.67,
      "correctness": 0.8,
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.021,
      "perturbation_class": "semantic",
      "task": "exp_hcnattl6",
      "loc": 1070,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.4972,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 161,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0159,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 726,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0053,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 63,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.9687,
      "perturbation_class": "semantic",
      "task": "exp_jcrbm3rt",
      "loc": 432,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0109,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 444,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0081,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 281,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.8868,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 387,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "correctness": 0.8,
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0169,
      "perturbation_class": "semantic",
      "task": "exp_m3c9h6l0",
      "loc": 891,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0056,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 111,
      "thinking_ratio": 0.02,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0145,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 697,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0148,
      "perturbation_class": "semantic",
      "task": "exp_mmp26p5c",
      "loc": 756,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0081,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 221,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0206,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 694,
      "thinking_ratio": 0.32,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.0126,
      "perturbation_class": "semantic",
      "task": "exp_nlme9vjk",
      "loc": 472,
      "thinking_ratio": 0.12,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0104,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 386,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.44,
      "correctness": 0.7,
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0229,
      "perturbation_class": "semantic",
      "task": "exp_plz1xajw",
      "loc": 607,
      "thinking_ratio": 0.25,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.1773,
      "perturbation_class": "semantic",
      "task": "exp_pqcfk5nr",
      "loc": 327,
      "thinking_ratio": 0.13,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.61,
      "correctness": 0.8,
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
      "quadrant": "explorative"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.6456,
      "perturbation_class": "semantic",
      "task": "exp_q9ckxin5",
      "loc": 267,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0197,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 925,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0097,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 391,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.9408,
      "perturbation_class": "semantic",
      "task": "exp_qu6tc1zc",
      "loc": 562,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.1924,
      "perturbation_class": "semantic",
      "task": "exp_rt6ocba2",
      "loc": 397,
      "thinking_ratio": 0.09,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0203,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 1139,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0167,
      "perturbation_class": "semantic",
      "task": "exp_s73ost4b",
      "loc": 899,
      "thinking_ratio": 0.02,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
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
      "quadrant": "explorative"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.3088,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 427,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.3937,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 477,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.4235,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 618,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.0271,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 227,
      "thinking_ratio": 0.1,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0323,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 281,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.0595,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 342,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.0284,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 342,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.1629,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 48,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.3609,
      "perturbation_class": "semantic",
      "task": "perturbed",
      "loc": 230,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0064,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 227,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0158,
      "perturbation_class": "semantic",
      "task": "exp_tqnuch_d",
      "loc": 903,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0213,
      "perturbation_class": "semantic",
      "task": "exp_u9zvdibz",
      "loc": 1127,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.4089,
      "perturbation_class": "semantic",
      "task": "exp_uc2lmxka",
      "loc": 455,
      "thinking_ratio": 0.05,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.005,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 141,
      "thinking_ratio": 0.01,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "color": "rgba(59,130,246,0.75)",
      "escape": 0.37,
      "correctness": 0.7,
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
      "correctness": 0.7,
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
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.4021,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 130,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.3002,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 117,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0103,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 527,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0219,
      "perturbation_class": "semantic",
      "task": "task_manager",
      "loc": 1295,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.7,
      "correctness": 0.8,
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0157,
      "perturbation_class": "semantic",
      "task": "exp_wkclt_vt",
      "loc": 853,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0145,
      "perturbation_class": "semantic",
      "task": "exp_wo07wfxb",
      "loc": 750,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "color": "rgba(6,182,212,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.6322,
      "perturbation_class": "semantic",
      "task": "exp_wo0bkk9m",
      "loc": 298,
      "thinking_ratio": 0.0,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.0185,
      "perturbation_class": "semantic",
      "task": "exp_x5tqss1y",
      "loc": 883,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "color": "rgba(239,68,68,0.60)",
      "escape": 0.0,
      "correctness": 0.7,
      "cost": 0.018,
      "perturbation_class": "semantic",
      "task": "exp_x8g28_k8",
      "loc": 187,
      "thinking_ratio": 0.06,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0142,
      "perturbation_class": "semantic",
      "task": "exp_xszdrm2e",
      "loc": 809,
      "thinking_ratio": 0.03,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0073,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 169,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
    },
    {
      "model": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "color": "rgba(52,211,153,0.75)",
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.01,
      "perturbation_class": "semantic",
      "task": "url_shortener",
      "loc": 375,
      "thinking_ratio": 0.04,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "escape": 0.0,
      "correctness": 1.0,
      "cost": 0.0165,
      "perturbation_class": "semantic",
      "task": "baseline",
      "loc": 885,
      "thinking_ratio": 0.07,
      "strategy": "conservative",
      "quadrant": "high_grit"
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
      "quadrant": "explorative"
    },
    {
      "model": "openai/gpt-5",
      "label": "GPT-5",
      "color": "rgba(251,191,36,0.75)",
      "escape": 0.0,
      "correctness": 0.8,
      "cost": 0.2201,
      "perturbation_class": "semantic",
      "task": "exp_zpgio1qs",
      "loc": 514,
      "thinking_ratio": 0.08,
      "strategy": "conservative",
      "quadrant": "conservative_fail"
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
      "quadrant": "explorative"
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
        "cells": 30,
        "total_cost": 2.044974,
        "avg_cost": 0.068166,
        "total_tokens": 6986407,
        "avg_cache_hit": 0.964,
        "avg_duration_s": 1386.0
      },
      {
        "model": "openai/gpt-5.6-luna",
        "cells": 34,
        "total_cost": 3.085027,
        "avg_cost": 0.090736,
        "total_tokens": 1075066,
        "avg_cache_hit": 0.975,
        "avg_duration_s": 528.0
      },
      {
        "model": "deepseek/deepseek-v4-pro",
        "cells": 35,
        "total_cost": 4.822804,
        "avg_cost": 0.137794,
        "total_tokens": 6072866,
        "avg_cache_hit": 0.778,
        "avg_duration_s": 1675.0
      },
      {
        "model": "anthropic/claude-haiku-4-5",
        "cells": 31,
        "total_cost": 30.216397,
        "avg_cost": 0.974722,
        "total_tokens": 1562780,
        "avg_cache_hit": 0.606,
        "avg_duration_s": 632.0
      },
      {
        "model": "openai/gpt-5.6-terra",
        "cells": 30,
        "total_cost": 30.640397,
        "avg_cost": 1.021347,
        "total_tokens": 4950585,
        "avg_cache_hit": 0.819,
        "avg_duration_s": 775.0
      },
      {
        "model": "anthropic/claude-sonnet-5",
        "cells": 31,
        "total_cost": 105.418795,
        "avg_cost": 3.400606,
        "total_tokens": 2218404,
        "avg_cache_hit": 0.731,
        "avg_duration_s": 844.0
      },
      {
        "model": "openai/gpt-5.6-sol",
        "cells": 30,
        "total_cost": 112.46246,
        "avg_cost": 3.748749,
        "total_tokens": 7033139,
        "avg_cache_hit": 0.843,
        "avg_duration_s": 1203.0
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
        "cells": 89,
        "variants": 12,
        "total_cost": 119.322572,
        "avg_cost": 1.340703,
        "success": 80,
        "fail": 9
      },
      {
        "condition": "early_degrade",
        "cells": 88,
        "variants": 12,
        "total_cost": 109.648689,
        "avg_cost": 1.246008,
        "success": 75,
        "fail": 13
      }
    ],
    "stories": [
      {
        "story": "task_manager_api",
        "cells": 78,
        "total_cost": 87.807082,
        "avg_cost": 1.125732,
        "sessions": 388,
        "avg_duration_s": 867.0,
        "avg_tokens_per_session": 22031.0
      },
      {
        "story": "static_site_gen",
        "cells": 70,
        "total_cost": 95.841249,
        "avg_cost": 1.369161,
        "sessions": 346,
        "avg_duration_s": 1007.0,
        "avg_tokens_per_session": 30255.0
      },
      {
        "story": "notification_service",
        "cells": 73,
        "total_cost": 105.042523,
        "avg_cost": 1.438939,
        "sessions": 363,
        "avg_duration_s": 1166.0,
        "avg_tokens_per_session": 29364.0
      }
    ],
    "tiers": [
      {
        "tier": "tier1_minimal",
        "quality": "bad",
        "cells": 44,
        "avg_cost": 1.319078,
        "avg_tokens_per_session": 27258.0,
        "avg_session_duration_s": 212.0
      },
      {
        "tier": "tier1_minimal",
        "quality": "good",
        "cells": 69,
        "avg_cost": 1.466812,
        "avg_tokens_per_session": 27010.0,
        "avg_session_duration_s": 219.0
      },
      {
        "tier": "tier2_small",
        "quality": "bad",
        "cells": 43,
        "avg_cost": 1.058701,
        "avg_tokens_per_session": 26729.0,
        "avg_session_duration_s": 200.0
      },
      {
        "tier": "tier2_small",
        "quality": "good",
        "cells": 65,
        "avg_cost": 1.291035,
        "avg_tokens_per_session": 27192.0,
        "avg_session_duration_s": 189.0
      }
    ],
    "sessions": {
      "total": 1097,
      "total_cost": 288.69085364000034,
      "total_tokens": 29899247,
      "total_cache_reads": 715852100,
      "cache_hit_rate": 0.977,
      "duration_s": 223261.00070005076,
      "successful": 976,
      "failed": 121
    },
    "generated_at": "2026-08-14T13:11:00.757309+00:00"
  },
  "reviews": {
    "models": [
      {
        "model": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "stories": 3,
        "overall_coherence": 0.927,
        "architectural_fit": 0.823,
        "convention_adherence": 0.716,
        "better_pct": 80.0,
        "worse_pct": 0.0,
        "neutral_pct": 20.0,
        "top_issues": [
          {
            "theme": "test gaps",
            "count": 4
          },
          {
            "theme": "security",
            "count": 3
          },
          {
            "theme": "incomplete refactor",
            "count": 2
          },
          {
            "theme": "other",
            "count": 1
          },
          {
            "theme": "missing surface",
            "count": 1
          }
        ]
      },
      {
        "model": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "stories": 34,
        "overall_coherence": 0.888,
        "architectural_fit": 0.753,
        "convention_adherence": 0.701,
        "better_pct": 74.1,
        "worse_pct": 8.8,
        "neutral_pct": 11.8,
        "top_issues": [
          {
            "theme": "other",
            "count": 59
          },
          {
            "theme": "security",
            "count": 29
          },
          {
            "theme": "incomplete refactor",
            "count": 24
          },
          {
            "theme": "test gaps",
            "count": 23
          },
          {
            "theme": "coupling",
            "count": 11
          }
        ]
      },
      {
        "model": "deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "stories": 35,
        "overall_coherence": 0.881,
        "architectural_fit": 0.75,
        "convention_adherence": 0.72,
        "better_pct": 61.6,
        "worse_pct": 11.6,
        "neutral_pct": 23.2,
        "top_issues": [
          {
            "theme": "other",
            "count": 48
          },
          {
            "theme": "security",
            "count": 31
          },
          {
            "theme": "incomplete refactor",
            "count": 26
          },
          {
            "theme": "test gaps",
            "count": 24
          },
          {
            "theme": "schema drift",
            "count": 11
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
        "model": "deepseek-v4-flash",
        "label": "DeepSeek v4 Flash",
        "commits": 150,
        "lines_added": 111951,
        "lines_removed": 8474,
        "functions_added": 1872,
        "classes_added": 110,
        "imports_added": 1870,
        "sonar_available": 150,
        "sonar_bugs_delta": 27,
        "sonar_smells_delta": 201,
        "sonar_complexity_delta": 4881,
        "avg_convention": 0.673,
        "deep_cells": 30,
        "lsp_available": 30,
        "lsp_errors_per_cell": 13.5,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 1.0,
        "solution_constraints": 1.0,
        "solution_quality": 0.035,
        "solution_novelty": 0.877,
        "solution_composite": 0.789,
        "basin_escape": 0.738,
        "strategies": {
          "exploratory": 30
        }
      },
      {
        "model": "deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "commits": 166,
        "lines_added": 97420,
        "lines_removed": 7199,
        "functions_added": 1238,
        "classes_added": 247,
        "imports_added": 1179,
        "sonar_available": 166,
        "sonar_bugs_delta": 6,
        "sonar_smells_delta": 78,
        "sonar_complexity_delta": 4111,
        "avg_convention": 0.713,
        "deep_cells": 35,
        "lsp_available": 35,
        "lsp_errors_per_cell": 11.3,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 1.0,
        "solution_constraints": 0.99,
        "solution_quality": 0.048,
        "solution_novelty": 0.815,
        "solution_composite": 0.779,
        "basin_escape": 0.678,
        "strategies": {
          "exploratory": 35
        }
      },
      {
        "model": "gpt-5.6-sol",
        "label": "gpt-5.6-sol",
        "commits": 150,
        "lines_added": 76959,
        "lines_removed": 11671,
        "functions_added": 1085,
        "classes_added": 108,
        "imports_added": 1251,
        "sonar_available": 150,
        "sonar_bugs_delta": 4,
        "sonar_smells_delta": 90,
        "sonar_complexity_delta": 3603,
        "avg_convention": 0.657,
        "deep_cells": 30,
        "lsp_available": 30,
        "lsp_errors_per_cell": 9.2,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 1.0,
        "solution_constraints": 1.0,
        "solution_quality": 0.056,
        "solution_novelty": 0.912,
        "solution_composite": 0.798,
        "basin_escape": 0.776,
        "strategies": {
          "exploratory": 30
        }
      },
      {
        "model": "claude-haiku-4-5",
        "label": "claude-haiku-4-5",
        "commits": 157,
        "lines_added": 54775,
        "lines_removed": 3809,
        "functions_added": 521,
        "classes_added": 254,
        "imports_added": 701,
        "sonar_available": 147,
        "sonar_bugs_delta": 2,
        "sonar_smells_delta": 176,
        "sonar_complexity_delta": 1795,
        "avg_convention": 0.745,
        "deep_cells": 31,
        "lsp_available": 31,
        "lsp_errors_per_cell": 9.0,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 0.548,
        "solution_constraints": 0.839,
        "solution_quality": 0.167,
        "solution_novelty": 0.521,
        "solution_composite": 0.555,
        "basin_escape": 0.444,
        "strategies": {
          "exploratory": 17,
          "conservative": 12,
          "wasteful": 2
        }
      },
      {
        "model": "claude-sonnet-5",
        "label": "Claude Sonnet 5",
        "commits": 155,
        "lines_added": 51447,
        "lines_removed": 2996,
        "functions_added": 1876,
        "classes_added": 122,
        "imports_added": 1211,
        "sonar_available": 152,
        "sonar_bugs_delta": 5,
        "sonar_smells_delta": 159,
        "sonar_complexity_delta": 2245,
        "avg_convention": 0.718,
        "deep_cells": 31,
        "lsp_available": 31,
        "lsp_errors_per_cell": 9.4,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 0.581,
        "solution_constraints": 0.882,
        "solution_quality": 0.125,
        "solution_novelty": 0.59,
        "solution_composite": 0.581,
        "basin_escape": 0.484,
        "strategies": {
          "conservative": 8,
          "wasteful": 5,
          "exploratory": 18
        }
      },
      {
        "model": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "commits": 170,
        "lines_added": 27509,
        "lines_removed": 9481,
        "functions_added": 843,
        "classes_added": 102,
        "imports_added": 1033,
        "sonar_available": 170,
        "sonar_bugs_delta": 2,
        "sonar_smells_delta": 89,
        "sonar_complexity_delta": 4750,
        "avg_convention": 0.679,
        "deep_cells": 34,
        "lsp_available": 34,
        "lsp_errors_per_cell": 5.1,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 1.0,
        "solution_constraints": 0.971,
        "solution_quality": 0.086,
        "solution_novelty": 0.88,
        "solution_composite": 0.79,
        "basin_escape": 0.704,
        "strategies": {
          "exploratory": 34
        }
      },
      {
        "model": "gpt-5.6-terra",
        "label": "gpt-5.6-terra",
        "commits": 150,
        "lines_added": 25843,
        "lines_removed": 9946,
        "functions_added": 825,
        "classes_added": 97,
        "imports_added": 1079,
        "sonar_available": 150,
        "sonar_bugs_delta": 5,
        "sonar_smells_delta": 75,
        "sonar_complexity_delta": 2724,
        "avg_convention": 0.67,
        "deep_cells": 30,
        "lsp_available": 30,
        "lsp_errors_per_cell": 13.7,
        "lsp_warnings_per_cell": 0.0,
        "solution_correctness": 1.0,
        "solution_constraints": 0.967,
        "solution_quality": 0.088,
        "solution_novelty": 0.905,
        "solution_composite": 0.793,
        "basin_escape": 0.743,
        "strategies": {
          "exploratory": 30
        }
      }
    ],
    "stories_analyzed": 221,
    "commits_analyzed": 1098,
    "sonar_commits_available": 1085
  },
  "labs": {
    "verification_frontier": {
      "experiment_id": "lab_verification_frontier",
      "generated_at": "2026-08-13T21:21:51.439198",
      "summary": {
        "models": 7,
        "cheapest": "deepseek-v4-flash",
        "most_verified": "claude-sonnet-5",
        "pareto_frontier": [
          "deepseek-v4-flash",
          "deepseek-v4-pro",
          "claude-haiku-4-5",
          "claude-sonnet-5"
        ]
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 30,
          "cost_cells": 30,
          "avg_cost": 0.068,
          "avg_tests": 33.533,
          "total_cost": 2.045,
          "total_tests": 1006
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 34,
          "cost_cells": 34,
          "avg_cost": 0.091,
          "avg_tests": 7.324,
          "total_cost": 3.085,
          "total_tests": 249
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 35,
          "cost_cells": 35,
          "avg_cost": 0.138,
          "avg_tests": 34.4,
          "total_cost": 4.8228,
          "total_tests": 1204
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 30,
          "cost_cells": 30,
          "avg_cost": 1.021,
          "avg_tests": 8.833,
          "total_cost": 30.6404,
          "total_tests": 265
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 31,
          "cost_cells": 19,
          "avg_cost": 1.59,
          "avg_tests": 117.355,
          "total_cost": 30.2164,
          "total_tests": 3638
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 30,
          "cost_cells": 30,
          "avg_cost": 3.749,
          "avg_tests": 12.9,
          "total_cost": 112.4625,
          "total_tests": 387
        },
        {
          "model": "claude-sonnet-5",
          "cells": 31,
          "cost_cells": 23,
          "avg_cost": 4.583,
          "avg_tests": 122.129,
          "total_cost": 105.4188,
          "total_tests": 3786
        }
      ]
    },
    "story_arc": {
      "experiment_id": "lab_story_arc",
      "generated_at": "2026-08-13T21:12:55.849893",
      "summary": {
        "snowball_factor": 2.13,
        "session1_cost": 0.1594,
        "session5_cost": 0.3391
      },
      "sessions": [
        {
          "session_number": 1,
          "task_type": "greenfield",
          "n": 221,
          "avg_cost": 0.1594,
          "avg_tokens": 19307.0,
          "avg_tests": 4.4
        },
        {
          "session_number": 2,
          "task_type": "feature",
          "n": 221,
          "avg_cost": 0.2101,
          "avg_tokens": 24312.0,
          "avg_tests": 8.4
        },
        {
          "session_number": 3,
          "task_type": "integration",
          "n": 221,
          "avg_cost": 0.3194,
          "avg_tokens": 30588.0,
          "avg_tests": 10.6
        },
        {
          "session_number": 4,
          "task_type": "refactor",
          "n": 217,
          "avg_cost": 0.2896,
          "avg_tokens": 30235.0,
          "avg_tests": 10.9
        },
        {
          "session_number": 5,
          "task_type": "cross_cutting",
          "n": 217,
          "avg_cost": 0.3391,
          "avg_tokens": 35490.0,
          "avg_tests": 14.8
        }
      ],
      "by_condition": {
        "bad_seed_s1": 0.1928,
        "bad_seed_s2": 0.2459,
        "bad_seed_s3": 0.3771,
        "bad_seed_s4": 0.2936,
        "bad_seed_s5": 0.372,
        "clean_s1": 0.1374,
        "clean_s2": 0.1975,
        "clean_s3": 0.3206,
        "clean_s4": 0.2699,
        "clean_s5": 0.3519,
        "early_degrade_s1": 0.1686,
        "early_degrade_s2": 0.2075,
        "early_degrade_s3": 0.2909,
        "early_degrade_s4": 0.3091,
        "early_degrade_s5": 0.3097
      },
      "by_model": {
        "claude-haiku-4-5": {
          "1": 0.1312,
          "2": 0.1695,
          "3": 0.2035,
          "4": 0.1705,
          "5": 0.3001
        },
        "claude-sonnet-5": {
          "1": 0.3773,
          "2": 0.4972,
          "3": 0.9467,
          "4": 0.6161,
          "5": 0.9633
        },
        "deepseek-v4-flash": {
          "1": 0.006,
          "2": 0.0097,
          "3": 0.016,
          "4": 0.0147,
          "5": 0.0218
        },
        "deepseek-v4-pro": {
          "1": 0.0179,
          "2": 0.0228,
          "3": 0.0311,
          "4": 0.028,
          "5": 0.0464
        },
        "gpt-5.6-luna": {
          "1": 0.013,
          "2": 0.0164,
          "3": 0.0195,
          "4": 0.02,
          "5": 0.0218
        },
        "gpt-5.6-sol": {
          "1": 0.4671,
          "2": 0.6464,
          "3": 0.8765,
          "4": 0.9728,
          "5": 0.7859
        },
        "gpt-5.6-terra": {
          "1": 0.1404,
          "2": 0.1574,
          "3": 0.2136,
          "4": 0.2431,
          "5": 0.267
        }
      }
    },
    "condition_effects": {
      "experiment_id": "lab_condition_effects",
      "generated_at": "2026-08-13T21:12:55.899760",
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
          "cells": 96,
          "success_rate": 0.906,
          "cascade_rate": 0.0,
          "avg_cost": 1.2514,
          "total_cost": 120.1318
        },
        {
          "condition": "early_degrade",
          "cells": 85,
          "success_rate": 0.847,
          "cascade_rate": 0.035,
          "avg_cost": 1.2859,
          "total_cost": 109.2986
        }
      ]
    },
    "verification_value": {
      "experiment_id": "lab_verification_value",
      "generated_at": "2026-08-13T21:12:55.967813",
      "summary": {
        "correlation_tests_vs_worse_rate": -0.226,
        "cells": 38
      },
      "rows": [
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
          "tests": 165,
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
          "tests": 1,
          "reviews": 5,
          "better_rate": 0.4,
          "worse_rate": 0.2
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
          "reviews": 12,
          "better_rate": 0.417,
          "worse_rate": 0.083
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 4,
          "reviews": 10,
          "better_rate": 0.2,
          "worse_rate": 0.5
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
          "tests": 32,
          "reviews": 5,
          "better_rate": 0.4,
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
          "reviews": 10,
          "better_rate": 0.6,
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
          "tests": 40,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
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
          "tests": 45,
          "reviews": 10,
          "better_rate": 0.5,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 46,
          "reviews": 10,
          "better_rate": 0.8,
          "worse_rate": 0.1
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 47,
          "reviews": 15,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 49,
          "reviews": 10,
          "better_rate": 0.9,
          "worse_rate": 0.0
        },
        {
          "model": "deepseek-v4-pro",
          "tests": 50,
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
          "reviews": 10,
          "better_rate": 0.6,
          "worse_rate": 0.2
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
          "reviews": 50,
          "better_rate": 0.6,
          "worse_rate": 0.14
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 6,
          "reviews": 5,
          "better_rate": 0.6,
          "worse_rate": 0.4
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 7,
          "reviews": 10,
          "better_rate": 0.7,
          "worse_rate": 0.1
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 8,
          "reviews": 15,
          "better_rate": 0.8,
          "worse_rate": 0.0
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 9,
          "reviews": 25,
          "better_rate": 0.8,
          "worse_rate": 0.04
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 10,
          "reviews": 25,
          "better_rate": 0.88,
          "worse_rate": 0.08
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 11,
          "reviews": 10,
          "better_rate": 0.7,
          "worse_rate": 0.1
        },
        {
          "model": "gpt-5.6-luna",
          "tests": 13,
          "reviews": 10,
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
          "tests": 15,
          "reviews": 5,
          "better_rate": 1.0,
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
          "tests": 17,
          "reviews": 5,
          "better_rate": 0.8,
          "worse_rate": 0.2
        }
      ]
    },
    "cache_economics": {
      "experiment_id": "lab_cache_economics",
      "generated_at": "2026-08-13T21:21:51.489397",
      "summary": {
        "models": 7
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 30,
          "avg_cost": 0.068,
          "avg_cache_hit": 0.964,
          "cache_reads": 202925952,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 6997079.0,
          "avg_tokens_per_cell": 232880.0
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 34,
          "avg_cost": 0.091,
          "avg_cache_hit": 0.975,
          "cache_reads": 43900353,
          "cache_writes": 3703149,
          "read_write_ratio": 11.9,
          "avg_context_per_cell": 1322806.0,
          "avg_tokens_per_cell": 31620.0
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 35,
          "avg_cost": 0.138,
          "avg_cache_hit": 0.778,
          "cache_reads": 105729792,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 3194362.0,
          "avg_tokens_per_cell": 173510.0
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 30,
          "avg_cost": 1.021,
          "avg_cache_hit": 0.819,
          "cache_reads": 22476288,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 914229.0,
          "avg_tokens_per_cell": 165020.0
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 31,
          "avg_cost": 1.59,
          "avg_cache_hit": 0.606,
          "cache_reads": 144011879,
          "cache_writes": 3862280,
          "read_write_ratio": 37.3,
          "avg_context_per_cell": 4695957.0,
          "avg_tokens_per_cell": 50412.0
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 30,
          "avg_cost": 3.749,
          "avg_cache_hit": 0.843,
          "cache_reads": 41913344,
          "cache_writes": 0,
          "read_write_ratio": null,
          "avg_context_per_cell": 1631549.0,
          "avg_tokens_per_cell": 234438.0
        },
        {
          "model": "claude-sonnet-5",
          "cells": 31,
          "avg_cost": 4.583,
          "avg_cache_hit": 0.731,
          "cache_reads": 154894492,
          "cache_writes": 4809267,
          "read_write_ratio": 32.2,
          "avg_context_per_cell": 5068158.0,
          "avg_tokens_per_cell": 71561.0
        }
      ]
    },
    "quality_frontier": {
      "experiment_id": "lab_quality_frontier",
      "generated_at": "2026-08-13T21:21:51.567150",
      "summary": {
        "models": 7
      },
      "models": [
        {
          "model": "deepseek-v4-flash",
          "cells": 30,
          "avg_cost": 0.068,
          "lsp_errors_per_cell": 13.467,
          "code_quality_score": 0.035,
          "cyclomatic_complexity": 481.4,
          "novelty_score": 0.877
        },
        {
          "model": "gpt-5.6-luna",
          "cells": 34,
          "avg_cost": 0.091,
          "lsp_errors_per_cell": 5.118,
          "code_quality_score": 0.086,
          "cyclomatic_complexity": 262.647,
          "novelty_score": 0.88
        },
        {
          "model": "deepseek-v4-pro",
          "cells": 35,
          "avg_cost": 0.138,
          "lsp_errors_per_cell": 11.343,
          "code_quality_score": 0.048,
          "cyclomatic_complexity": 261.514,
          "novelty_score": 0.815
        },
        {
          "model": "gpt-5.6-terra",
          "cells": 30,
          "avg_cost": 1.021,
          "lsp_errors_per_cell": 13.7,
          "code_quality_score": 0.088,
          "cyclomatic_complexity": 232.133,
          "novelty_score": 0.905
        },
        {
          "model": "claude-haiku-4-5",
          "cells": 19,
          "avg_cost": 1.59,
          "lsp_errors_per_cell": 9.0,
          "code_quality_score": 0.167,
          "cyclomatic_complexity": 282.484,
          "novelty_score": 0.521
        },
        {
          "model": "gpt-5.6-sol",
          "cells": 30,
          "avg_cost": 3.749,
          "lsp_errors_per_cell": 9.233,
          "code_quality_score": 0.056,
          "cyclomatic_complexity": 298.067,
          "novelty_score": 0.912
        },
        {
          "model": "claude-sonnet-5",
          "cells": 23,
          "avg_cost": 4.583,
          "lsp_errors_per_cell": 9.419,
          "code_quality_score": 0.125,
          "cyclomatic_complexity": 289.194,
          "novelty_score": 0.59
        }
      ]
    }
  }
};
