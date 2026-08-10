/* Generated 2026-08-10 00:11:38 UTC by build_data.py */
/* DO NOT EDIT — regenerate with: python scripts/build_data.py */
window.FRAMEWORK_DATA = {
  "_meta": {
    "generated_at": "2026-08-10T00:11:38.812581+00:00",
    "source_inventory": "/home/drseuss/ai-finops-framework/experiments/inventory.json",
    "source_summary": "/home/drseuss/ai-finops-framework/experiments/results/_results_summary.json",
    "source_db": "/home/drseuss/.local/share/opencode/opencode.db",
    "provenance_note": "All values tagged [M]easured, [C]omputed, [H]euristic, or e[X]ternal. See methodology.html."
  },
  "summary": {
    "worktrees_total": 251,
    "sessions_total": 249,
    "game_reports": 224,
    "total_cost": 64.9827,
    "architectures": 3,
    "variants": 8,
    "configs": 34,
    "_provenance": {
      "worktrees_total": "M",
      "sessions_total": "M",
      "game_reports": "M",
      "total_cost": "M",
      "architectures": "M",
      "variants": "M",
      "configs": "M"
    }
  },
  "models": [
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "provider": "deepseek",
      "sessions": 133,
      "n_reports": 119,
      "n_valid": 109,
      "n_narrated": 10,
      "reports": 119,
      "reports_valid": 109,
      "reports_narrated": 10,
      "avg_cost": 0.0158,
      "total_cost": 2.0427,
      "cost_ci95": [
        0.0147,
        0.017
      ],
      "pass_rate": "84% (976/1163)",
      "strategy_cons": 78,
      "strategy_expl": 29,
      "strategy_waste": 2,
      "strategy_efficient": 0,
      "avg_loc": 706,
      "avg_thinking_ratio": 0.087,
      "avg_escape": NaN,
      "avg_narration_penalty": 0.0,
      "avg_arch_divergence": NaN,
      "avg_struct_divergence": NaN,
      "avg_composite_score": 0.615,
      "avg_code_quality": 0.246,
      "avg_comment_ratio": 0.02,
      "avg_energy_j": 4091.8,
      "avg_energy_j_per_loc": 5.8,
      "avg_cost_per_joule": 28.6092,
      "avg_quality_per_joule": 0.0002,
      "narration_rate": 8,
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
        "avg_cost_per_joule": "C",
        "avg_quality_per_joule": "C",
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
      "pass_rate": "89% (8/9)",
      "strategy_cons": 4,
      "strategy_expl": 2,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 199,
      "avg_thinking_ratio": 0.19,
      "avg_escape": NaN,
      "avg_narration_penalty": 0.3,
      "avg_arch_divergence": NaN,
      "avg_struct_divergence": NaN,
      "avg_composite_score": 0.688,
      "avg_code_quality": 0.487,
      "avg_comment_ratio": 0.072,
      "avg_energy_j": 4689.4,
      "avg_energy_j_per_loc": 23.56,
      "avg_cost_per_joule": 3.6094,
      "avg_quality_per_joule": 0.0002,
      "narration_rate": 14,
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
        "avg_cost_per_joule": "C",
        "avg_quality_per_joule": "C",
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
      "sessions": 16,
      "n_reports": 13,
      "n_valid": 12,
      "n_narrated": 1,
      "reports": 13,
      "reports_valid": 12,
      "reports_narrated": 1,
      "avg_cost": 0.0258,
      "total_cost": 0.4077,
      "cost_ci95": [
        0.0206,
        0.0333
      ],
      "pass_rate": "94% (30/32)",
      "strategy_cons": 11,
      "strategy_expl": 1,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 264,
      "avg_thinking_ratio": 0.066,
      "avg_escape": NaN,
      "avg_narration_penalty": 0.18,
      "avg_arch_divergence": NaN,
      "avg_struct_divergence": NaN,
      "avg_composite_score": 0.694,
      "avg_code_quality": 0.407,
      "avg_comment_ratio": 0.063,
      "avg_energy_j": 3838.6,
      "avg_energy_j_per_loc": 14.54,
      "avg_cost_per_joule": 4.5089,
      "avg_quality_per_joule": 0.0002,
      "narration_rate": 8,
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
        "avg_cost_per_joule": "C",
        "avg_quality_per_joule": "C",
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
      "pass_rate": "70% (16/23)",
      "strategy_cons": 3,
      "strategy_expl": 8,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 403,
      "avg_thinking_ratio": 0.083,
      "avg_escape": NaN,
      "avg_narration_penalty": 0.03,
      "avg_arch_divergence": NaN,
      "avg_struct_divergence": NaN,
      "avg_composite_score": 0.639,
      "avg_code_quality": 0.273,
      "avg_comment_ratio": 0.063,
      "avg_energy_j": 4816.7,
      "avg_energy_j_per_loc": 11.95,
      "avg_cost_per_joule": 4.1783,
      "avg_quality_per_joule": 0.0002,
      "narration_rate": 15,
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
        "avg_cost_per_joule": "C",
        "avg_quality_per_joule": "C",
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
      "pass_rate": "100% (27/27)",
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
      "avg_cost_per_joule": 7.7529,
      "avg_quality_per_joule": 0.0004,
      "narration_rate": 50,
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
        "avg_cost_per_joule": "C",
        "avg_quality_per_joule": "C",
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
      "sessions": 18,
      "n_reports": 16,
      "n_valid": 15,
      "n_narrated": 1,
      "reports": 16,
      "reports_valid": 15,
      "reports_narrated": 1,
      "avg_cost": 0.4474,
      "total_cost": 7.817,
      "cost_ci95": [
        0.3763,
        0.5175
      ],
      "pass_rate": "100% (166/166)",
      "strategy_cons": 14,
      "strategy_expl": 1,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 367,
      "avg_thinking_ratio": 0.064,
      "avg_escape": NaN,
      "avg_narration_penalty": 0.02,
      "avg_arch_divergence": NaN,
      "avg_struct_divergence": NaN,
      "avg_composite_score": 0.726,
      "avg_code_quality": 0.37,
      "avg_comment_ratio": 0.009,
      "avg_energy_j": 2286.5,
      "avg_energy_j_per_loc": 6.23,
      "avg_cost_per_joule": 5.0078,
      "avg_quality_per_joule": 0.0004,
      "narration_rate": 6,
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
        "avg_cost_per_joule": "C",
        "avg_quality_per_joule": "C",
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
      "pass_rate": "100% (73/73)",
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
      "avg_cost_per_joule": 6.1925,
      "avg_quality_per_joule": 0.0005,
      "narration_rate": 33,
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
        "avg_cost_per_joule": "C",
        "avg_quality_per_joule": "C",
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
      "sessions": 47,
      "n_reports": 44,
      "n_valid": 39,
      "n_narrated": 5,
      "reports": 44,
      "reports_valid": 39,
      "reports_narrated": 5,
      "avg_cost": 1.0847,
      "total_cost": 47.5417,
      "cost_ci95": [
        0.9058,
        1.2585
      ],
      "pass_rate": "99% (276/279)",
      "strategy_cons": 27,
      "strategy_expl": 12,
      "strategy_waste": 0,
      "strategy_efficient": 0,
      "avg_loc": 568,
      "avg_thinking_ratio": 0.0,
      "avg_escape": NaN,
      "avg_narration_penalty": 0.08,
      "avg_arch_divergence": NaN,
      "avg_struct_divergence": NaN,
      "avg_composite_score": 0.636,
      "avg_code_quality": 0.278,
      "avg_comment_ratio": 0.033,
      "avg_energy_j": 2857.6,
      "avg_energy_j_per_loc": 5.03,
      "avg_cost_per_joule": 3.891,
      "avg_quality_per_joule": 0.0006,
      "narration_rate": 11,
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
        "avg_cost_per_joule": "C",
        "avg_quality_per_joule": "C",
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
      "DeepSeek v4 Pro",
      "GPT-5-nano",
      "GPT-5-mini",
      "GPT-5",
      "GPT-5.5",
      "GPT-5.6",
      "GPT-5.6-fast",
      "Claude Fable 5"
    ],
    "costData": [
      0.0158,
      0.0057,
      0.0258,
      0.159,
      0.282,
      0.4474,
      0.6625,
      1.0847
    ],
    "narrData": [
      8,
      14,
      8,
      15,
      50,
      6,
      33,
      11
    ],
    "locData": [
      706,
      199,
      264,
      403,
      262,
      367,
      343,
      568
    ],
    "costY": [
      0.0158,
      0.0057,
      0.0258,
      0.159,
      0.282,
      0.4474,
      0.6625,
      1.0847
    ],
    "reports": [
      119,
      7,
      13,
      13,
      6,
      16,
      9,
      44
    ]
  },
  "calculator": {
    "model_costs": [
      {
        "n": "DeepSeek v4 Pro",
        "c": 0.0158,
        "p": 0.84
      },
      {
        "n": "GPT-5-nano",
        "c": 0.0057,
        "p": 0.89
      },
      {
        "n": "GPT-5-mini",
        "c": 0.0258,
        "p": 0.94
      },
      {
        "n": "GPT-5",
        "c": 0.159,
        "p": 0.7
      },
      {
        "n": "GPT-5.5",
        "c": 0.282,
        "p": 1.0
      },
      {
        "n": "GPT-5.6",
        "c": 0.4474,
        "p": 1.0
      },
      {
        "n": "GPT-5.6-fast",
        "c": 0.6625,
        "p": 1.0
      },
      {
        "n": "Claude Fable 5",
        "c": 1.0847,
        "p": 0.99
      }
    ],
    "escalation_tiers": [
      {
        "m": "DS\u2192GPT-5-nano",
        "e": 0.4
      },
      {
        "m": "DS\u2192GPT-5-mini",
        "e": 1.6
      },
      {
        "m": "DS\u2192GPT-5",
        "e": 10.1
      },
      {
        "m": "DS\u2192GPT-5.5",
        "e": 17.8
      },
      {
        "m": "DS\u2192GPT-5.6",
        "e": 28.3
      },
      {
        "m": "DS\u2192GPT-5.6-fast",
        "e": 41.9
      },
      {
        "m": "DS\u21925",
        "e": 68.7
      },
      {
        "m": "\u2192Human ($5/job)",
        "e": 316.5
      }
    ],
    "retry_rate_measured": 0.115,
    "woc_ratio": 0.9
  },
  "derived": {
    "cost_gap": "69\u00d7",
    "cost_gap_computation": "$1.0847 / $0.0158 = 68.7\u00d7",
    "overall_pass_rate": "88.7% (1572/1772)",
    "total_tests_passed": 1572,
    "total_tests_run": 1772,
    "total_cost_all_models": 64.9827,
    "total_cost_deepseek": 2.0427,
    "total_cost_claude": 47.5417,
    "total_narrated": 26,
    "total_valid_reports": 201,
    "total_reports_analyzed": 227,
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
          "avg_escape": NaN,
          "escape_ci95": [
            NaN,
            NaN
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
          "avg_escape": NaN,
          "escape_ci95": [
            NaN,
            NaN
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
          "avg_escape": NaN,
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
          "avg_escape": NaN,
          "escape_ci95": [
            NaN,
            NaN
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
          "avg_escape": NaN,
          "escape_ci95": [
            NaN,
            NaN
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
          "avg_escape": NaN,
          "escape_ci95": [
            NaN,
            NaN
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
        "avg_escape": NaN,
        "escape_ci95": [
          NaN,
          NaN
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
        "avg_escape": NaN,
        "escape_ci95": [
          NaN,
          NaN
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
        "avg_escape": NaN,
        "escape_ci95": [
          NaN,
          NaN
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
        "avg_escape": NaN,
        "escape_ci95": [
          0.4464,
          NaN
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
        "avg_escape": NaN,
        "escape_ci95": [
          NaN,
          NaN
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
        "avg_escape": NaN,
        "escape_ci95": [
          NaN,
          NaN
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
      "id": "openai/gpt-5.6-fast",
      "label": "GPT-5.6-fast",
      "avg_energy_j": 1598.7,
      "avg_energy_j_per_loc": 4.66,
      "avg_cost": 0.6625,
      "avg_loc": 343
    },
    {
      "id": "anthropic/claude-fable-5",
      "label": "Claude Fable 5",
      "avg_energy_j": 2857.6,
      "avg_energy_j_per_loc": 5.03,
      "avg_cost": 1.0847,
      "avg_loc": 568
    },
    {
      "id": "deepseek/deepseek-v4-pro",
      "label": "DeepSeek v4 Pro",
      "avg_energy_j": 4091.8,
      "avg_energy_j_per_loc": 5.8,
      "avg_cost": 0.0158,
      "avg_loc": 706
    },
    {
      "id": "openai/gpt-5.6",
      "label": "GPT-5.6",
      "avg_energy_j": 2286.5,
      "avg_energy_j_per_loc": 6.23,
      "avg_cost": 0.4474,
      "avg_loc": 367
    },
    {
      "id": "openai/gpt-5.5",
      "label": "GPT-5.5",
      "avg_energy_j": 2553.6,
      "avg_energy_j_per_loc": 9.75,
      "avg_cost": 0.282,
      "avg_loc": 262
    },
    {
      "id": "openai/gpt-5",
      "label": "GPT-5",
      "avg_energy_j": 4816.7,
      "avg_energy_j_per_loc": 11.95,
      "avg_cost": 0.159,
      "avg_loc": 403
    },
    {
      "id": "openai/gpt-5-mini",
      "label": "GPT-5-mini",
      "avg_energy_j": 3838.6,
      "avg_energy_j_per_loc": 14.54,
      "avg_cost": 0.0258,
      "avg_loc": 264
    },
    {
      "id": "openai/gpt-5-nano",
      "label": "GPT-5-nano",
      "avg_energy_j": 4689.4,
      "avg_energy_j_per_loc": 23.56,
      "avg_cost": 0.0057,
      "avg_loc": 199
    }
  ],
  "strategy_distribution": {
    "exploratory": 59,
    "?": 24,
    "conservative": 141,
    "wasteful": 3
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
    "claude_active_params": {
      "value": "500B",
      "provenance": "X",
      "note": "Conservative estimate"
    },
    "deepseek_active_params": {
      "value": "37B",
      "provenance": "X",
      "note": "MoE, ~3% active at inference"
    }
  }
};
