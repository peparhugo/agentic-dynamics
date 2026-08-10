/* Generated 2026-08-10 13:14:58 UTC by build_data.py */
/* DO NOT EDIT — regenerate with: python scripts/build_data.py */
window.FRAMEWORK_DATA = {
  "_meta": {
    "generated_at": "2026-08-10T13:14:58.775989+00:00",
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
        "avg_cost_per_joule": "C",
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
        "avg_cost_per_joule": "C",
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
        "avg_cost_per_joule": "C",
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
        "avg_cost_per_joule": "C",
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
        "avg_cost_per_joule": "C",
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
        "avg_cost_per_joule": "C",
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
        "avg_cost_per_joule": "C",
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
        "avg_cost_per_joule": "C",
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
  "reasoning": {
    "divergence": {
      "meta": {
        "experiment_id": "lab_reasoning_divergence",
        "total_pairs": 5443,
        "total_step_embeddings": 2215,
        "models_analyzed": 9,
        "data_source": "ChromaDB \u2014 per-step reasoning embeddings via bge-m3",
        "method": "Compares matching step positions (step N vs step N) across session pairs",
        "metric": "cosine distance between matching reasoning step embeddings"
      },
      "data": {
        "per_operator_pair": {
          "baseline \u00d7 baseline": {
            "operator_pair": "baseline \u00d7 baseline",
            "mean_distance": 0.1913,
            "std_dev": 0.0293,
            "count": 2838
          },
          "baseline \u00d7 remove_critical_constraint": {
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "mean_distance": 0.2124,
            "std_dev": 0.02,
            "count": 392
          },
          "baseline \u00d7 inject_alien_vocab": {
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "mean_distance": 0.202,
            "std_dev": 0.0236,
            "count": 388
          },
          "baseline \u00d7 shift_framing": {
            "operator_pair": "baseline \u00d7 shift_framing",
            "mean_distance": 0.2084,
            "std_dev": 0.0217,
            "count": 360
          },
          " \u00d7 baseline": {
            "operator_pair": " \u00d7 baseline",
            "mean_distance": 0.2355,
            "std_dev": 0.047,
            "count": 324
          },
          "baseline \u00d7 invert_constraint": {
            "operator_pair": "baseline \u00d7 invert_constraint",
            "mean_distance": 0.2097,
            "std_dev": 0.023,
            "count": 316
          },
          "baseline \u00d7 inject_phantom_success": {
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "mean_distance": 0.2004,
            "std_dev": 0.0229,
            "count": 234
          },
          "baseline \u00d7 inject_competing_goal": {
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "mean_distance": 0.2129,
            "std_dev": 0.0245,
            "count": 177
          },
          "inject_alien_vocab \u00d7 remove_critical_constraint": {
            "operator_pair": "inject_alien_vocab \u00d7 remove_critical_constraint",
            "mean_distance": 0.1782,
            "std_dev": 0.0332,
            "count": 27
          },
          "remove_critical_constraint \u00d7 shift_framing": {
            "operator_pair": "remove_critical_constraint \u00d7 shift_framing",
            "mean_distance": 0.1985,
            "std_dev": 0.0172,
            "count": 25
          },
          "inject_alien_vocab \u00d7 shift_framing": {
            "operator_pair": "inject_alien_vocab \u00d7 shift_framing",
            "mean_distance": 0.1819,
            "std_dev": 0.0277,
            "count": 25
          },
          "inject_alien_vocab \u00d7 invert_constraint": {
            "operator_pair": "inject_alien_vocab \u00d7 invert_constraint",
            "mean_distance": 0.1898,
            "std_dev": 0.0261,
            "count": 24
          },
          "invert_constraint \u00d7 remove_critical_constraint": {
            "operator_pair": "invert_constraint \u00d7 remove_critical_constraint",
            "mean_distance": 0.2068,
            "std_dev": 0.0195,
            "count": 22
          },
          " \u00d7 remove_critical_constraint": {
            "operator_pair": " \u00d7 remove_critical_constraint",
            "mean_distance": 0.2477,
            "std_dev": 0.0444,
            "count": 21
          },
          " \u00d7 inject_alien_vocab": {
            "operator_pair": " \u00d7 inject_alien_vocab",
            "mean_distance": 0.2446,
            "std_dev": 0.0463,
            "count": 20
          },
          "invert_constraint \u00d7 shift_framing": {
            "operator_pair": "invert_constraint \u00d7 shift_framing",
            "mean_distance": 0.1978,
            "std_dev": 0.0235,
            "count": 20
          },
          " \u00d7 shift_framing": {
            "operator_pair": " \u00d7 shift_framing",
            "mean_distance": 0.2433,
            "std_dev": 0.0431,
            "count": 20
          },
          "inject_phantom_success \u00d7 remove_critical_constraint": {
            "operator_pair": "inject_phantom_success \u00d7 remove_critical_constraint",
            "mean_distance": 0.1712,
            "std_dev": 0.0283,
            "count": 17
          },
          "inject_alien_vocab \u00d7 inject_phantom_success": {
            "operator_pair": "inject_alien_vocab \u00d7 inject_phantom_success",
            "mean_distance": 0.1643,
            "std_dev": 0.0291,
            "count": 17
          },
          " \u00d7 invert_constraint": {
            "operator_pair": " \u00d7 invert_constraint",
            "mean_distance": 0.2405,
            "std_dev": 0.0459,
            "count": 16
          },
          "inject_phantom_success \u00d7 shift_framing": {
            "operator_pair": "inject_phantom_success \u00d7 shift_framing",
            "mean_distance": 0.181,
            "std_dev": 0.0275,
            "count": 15
          },
          "inject_phantom_success \u00d7 invert_constraint": {
            "operator_pair": "inject_phantom_success \u00d7 invert_constraint",
            "mean_distance": 0.1911,
            "std_dev": 0.0269,
            "count": 14
          },
          "inject_alien_vocab \u00d7 inject_competing_goal": {
            "operator_pair": "inject_alien_vocab \u00d7 inject_competing_goal",
            "mean_distance": 0.1897,
            "std_dev": 0.0268,
            "count": 14
          },
          " \u00d7 inject_phantom_success": {
            "operator_pair": " \u00d7 inject_phantom_success",
            "mean_distance": 0.2442,
            "std_dev": 0.0513,
            "count": 13
          },
          "inject_competing_goal \u00d7 invert_constraint": {
            "operator_pair": "inject_competing_goal \u00d7 invert_constraint",
            "mean_distance": 0.1879,
            "std_dev": 0.0219,
            "count": 12
          },
          "inject_competing_goal \u00d7 remove_critical_constraint": {
            "operator_pair": "inject_competing_goal \u00d7 remove_critical_constraint",
            "mean_distance": 0.215,
            "std_dev": 0.0142,
            "count": 12
          },
          "inject_alien_vocab \u00d7 inject_alien_vocab": {
            "operator_pair": "inject_alien_vocab \u00d7 inject_alien_vocab",
            "mean_distance": 0.1607,
            "std_dev": 0.0334,
            "count": 11
          },
          "remove_critical_constraint \u00d7 remove_critical_constraint": {
            "operator_pair": "remove_critical_constraint \u00d7 remove_critical_constraint",
            "mean_distance": 0.1914,
            "std_dev": 0.0177,
            "count": 10
          },
          "shift_framing \u00d7 shift_framing": {
            "operator_pair": "shift_framing \u00d7 shift_framing",
            "mean_distance": 0.2009,
            "std_dev": 0.0212,
            "count": 10
          },
          "inject_competing_goal \u00d7 shift_framing": {
            "operator_pair": "inject_competing_goal \u00d7 shift_framing",
            "mean_distance": 0.2064,
            "std_dev": 0.013,
            "count": 10
          },
          " \u00d7 inject_competing_goal": {
            "operator_pair": " \u00d7 inject_competing_goal",
            "mean_distance": 0.2525,
            "std_dev": 0.0435,
            "count": 9
          },
          "inject_competing_goal \u00d7 inject_phantom_success": {
            "operator_pair": "inject_competing_goal \u00d7 inject_phantom_success",
            "mean_distance": 0.1929,
            "std_dev": 0.0146,
            "count": 8
          },
          "invert_constraint \u00d7 invert_constraint": {
            "operator_pair": "invert_constraint \u00d7 invert_constraint",
            "mean_distance": 0.1829,
            "std_dev": 0.0415,
            "count": 7
          },
          " \u00d7 ": {
            "operator_pair": " \u00d7 ",
            "mean_distance": 0.2431,
            "std_dev": 0.047,
            "count": 7
          },
          "inject_phantom_success \u00d7 inject_phantom_success": {
            "operator_pair": "inject_phantom_success \u00d7 inject_phantom_success",
            "mean_distance": 0.1451,
            "std_dev": 0.0123,
            "count": 3
          },
          "? \u00d7 ?": {
            "operator_pair": "? \u00d7 ?",
            "mean_distance": 0.2317,
            "std_dev": 0.0321,
            "count": 3
          },
          "inject_competing_goal \u00d7 inject_competing_goal": {
            "operator_pair": "inject_competing_goal \u00d7 inject_competing_goal",
            "mean_distance": 0.1431,
            "std_dev": 0.0649,
            "count": 2
          }
        },
        "per_class": {
          "": {
            "class": "",
            "mean_distance": 0.1999,
            "count": 1696
          },
          "?": {
            "class": "?",
            "mean_distance": 0.2317,
            "count": 3
          },
          "manifold": {
            "class": "manifold",
            "mean_distance": 0.181,
            "count": 46
          },
          "mixed": {
            "class": "mixed",
            "mean_distance": 0.203,
            "count": 3018
          },
          "semantic": {
            "class": "semantic",
            "mean_distance": 0.1912,
            "count": 680
          }
        },
        "per_model": {
          "anthropic/claude-fable-5": {
            "model_id": "anthropic/claude-fable-5",
            "label": "Claude Fable 5",
            "sessions_with_steps": 39,
            "baseline \u00d7 baseline": {
              "mean_distance": 0.212,
              "count": 91
            },
            "baseline \u00d7 inject_alien_vocab": {
              "mean_distance": 0.207,
              "count": 28
            },
            "baseline \u00d7 inject_competing_goal": {
              "mean_distance": 0.2239,
              "count": 28
            },
            "baseline \u00d7 inject_phantom_success": {
              "mean_distance": 0.2112,
              "count": 14
            },
            "baseline \u00d7 invert_constraint": {
              "mean_distance": 0.2116,
              "count": 28
            },
            "baseline \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2079,
              "count": 14
            },
            "inject_alien_vocab \u00d7 inject_alien_vocab": {
              "mean_distance": 0.1161,
              "count": 1
            },
            "inject_alien_vocab \u00d7 inject_competing_goal": {
              "mean_distance": 0.1975,
              "count": 4
            },
            "inject_alien_vocab \u00d7 inject_phantom_success": {
              "mean_distance": 0.1848,
              "count": 2
            },
            "inject_alien_vocab \u00d7 invert_constraint": {
              "mean_distance": 0.1978,
              "count": 4
            },
            "inject_alien_vocab \u00d7 remove_critical_constraint": {
              "mean_distance": 0.1189,
              "count": 2
            },
            "inject_competing_goal \u00d7 inject_competing_goal": {
              "mean_distance": 0.0782,
              "count": 1
            },
            "inject_competing_goal \u00d7 inject_phantom_success": {
              "mean_distance": 0.2088,
              "count": 2
            },
            "inject_competing_goal \u00d7 invert_constraint": {
              "mean_distance": 0.1623,
              "count": 4
            },
            "inject_competing_goal \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2387,
              "count": 2
            },
            "inject_phantom_success \u00d7 invert_constraint": {
              "mean_distance": 0.2126,
              "count": 2
            },
            "inject_phantom_success \u00d7 remove_critical_constraint": {
              "mean_distance": 0.1907,
              "count": 1
            },
            "invert_constraint \u00d7 invert_constraint": {
              "mean_distance": 0.0888,
              "count": 1
            },
            "invert_constraint \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2175,
              "count": 2
            }
          },
          "deepseek/deepseek-v4-pro": {
            "model_id": "deepseek/deepseek-v4-pro",
            "label": "DeepSeek v4 Pro",
            "sessions_with_steps": 101,
            " \u00d7 ": {
              "mean_distance": 0.2464,
              "count": 6
            },
            " \u00d7 baseline": {
              "mean_distance": 0.2349,
              "count": 288
            },
            " \u00d7 inject_alien_vocab": {
              "mean_distance": 0.2446,
              "count": 20
            },
            " \u00d7 inject_competing_goal": {
              "mean_distance": 0.2455,
              "count": 8
            },
            " \u00d7 inject_phantom_success": {
              "mean_distance": 0.2415,
              "count": 12
            },
            " \u00d7 invert_constraint": {
              "mean_distance": 0.2405,
              "count": 16
            },
            " \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2462,
              "count": 20
            },
            " \u00d7 shift_framing": {
              "mean_distance": 0.2433,
              "count": 20
            },
            "baseline \u00d7 baseline": {
              "mean_distance": 0.1892,
              "count": 2556
            },
            "baseline \u00d7 inject_alien_vocab": {
              "mean_distance": 0.2017,
              "count": 360
            },
            "baseline \u00d7 inject_competing_goal": {
              "mean_distance": 0.2096,
              "count": 144
            },
            "baseline \u00d7 inject_phantom_success": {
              "mean_distance": 0.1995,
              "count": 216
            },
            "baseline \u00d7 invert_constraint": {
              "mean_distance": 0.2095,
              "count": 288
            },
            "baseline \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2119,
              "count": 360
            },
            "baseline \u00d7 shift_framing": {
              "mean_distance": 0.2084,
              "count": 360
            },
            "inject_alien_vocab \u00d7 inject_alien_vocab": {
              "mean_distance": 0.1651,
              "count": 10
            },
            "inject_alien_vocab \u00d7 inject_competing_goal": {
              "mean_distance": 0.1865,
              "count": 10
            },
            "inject_alien_vocab \u00d7 inject_phantom_success": {
              "mean_distance": 0.1615,
              "count": 15
            },
            "inject_alien_vocab \u00d7 invert_constraint": {
              "mean_distance": 0.1882,
              "count": 20
            },
            "inject_alien_vocab \u00d7 remove_critical_constraint": {
              "mean_distance": 0.183,
              "count": 25
            },
            "inject_alien_vocab \u00d7 shift_framing": {
              "mean_distance": 0.1819,
              "count": 25
            },
            "inject_competing_goal \u00d7 inject_competing_goal": {
              "mean_distance": 0.208,
              "count": 1
            },
            "inject_competing_goal \u00d7 inject_phantom_success": {
              "mean_distance": 0.1875,
              "count": 6
            },
            "inject_competing_goal \u00d7 invert_constraint": {
              "mean_distance": 0.2007,
              "count": 8
            },
            "inject_competing_goal \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2102,
              "count": 10
            },
            "inject_competing_goal \u00d7 shift_framing": {
              "mean_distance": 0.2064,
              "count": 10
            },
            "inject_phantom_success \u00d7 inject_phantom_success": {
              "mean_distance": 0.1451,
              "count": 3
            },
            "inject_phantom_success \u00d7 invert_constraint": {
              "mean_distance": 0.1875,
              "count": 12
            },
            "inject_phantom_success \u00d7 remove_critical_constraint": {
              "mean_distance": 0.1671,
              "count": 15
            },
            "inject_phantom_success \u00d7 shift_framing": {
              "mean_distance": 0.181,
              "count": 15
            },
            "invert_constraint \u00d7 invert_constraint": {
              "mean_distance": 0.1986,
              "count": 6
            },
            "invert_constraint \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2058,
              "count": 20
            },
            "invert_constraint \u00d7 shift_framing": {
              "mean_distance": 0.1978,
              "count": 20
            },
            "remove_critical_constraint \u00d7 remove_critical_constraint": {
              "mean_distance": 0.1914,
              "count": 10
            },
            "remove_critical_constraint \u00d7 shift_framing": {
              "mean_distance": 0.1985,
              "count": 25
            },
            "shift_framing \u00d7 shift_framing": {
              "mean_distance": 0.2009,
              "count": 10
            }
          },
          "openai/gpt-5": {
            "model_id": "openai/gpt-5",
            "label": "GPT-5",
            "sessions_with_steps": 7,
            " \u00d7 baseline": {
              "mean_distance": 0.2908,
              "count": 5
            },
            " \u00d7 inject_competing_goal": {
              "mean_distance": 0.3088,
              "count": 1
            },
            "baseline \u00d7 baseline": {
              "mean_distance": 0.1976,
              "count": 10
            },
            "baseline \u00d7 inject_competing_goal": {
              "mean_distance": 0.2448,
              "count": 5
            }
          },
          "openai/gpt-5-mini": {
            "model_id": "openai/gpt-5-mini",
            "label": "GPT-5-mini",
            "sessions_with_steps": 13,
            " \u00d7 baseline": {
              "mean_distance": 0.2781,
              "count": 12
            },
            "baseline \u00d7 baseline": {
              "mean_distance": 0.2037,
              "count": 66
            }
          },
          "openai/gpt-5-nano": {
            "model_id": "openai/gpt-5-nano",
            "label": "GPT-5-nano",
            "sessions_with_steps": 7,
            " \u00d7 baseline": {
              "mean_distance": 0.2646,
              "count": 4
            },
            " \u00d7 inject_phantom_success": {
              "mean_distance": 0.2768,
              "count": 1
            },
            " \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2777,
              "count": 1
            },
            "baseline \u00d7 baseline": {
              "mean_distance": 0.2081,
              "count": 6
            },
            "baseline \u00d7 inject_phantom_success": {
              "mean_distance": 0.2127,
              "count": 4
            },
            "baseline \u00d7 remove_critical_constraint": {
              "mean_distance": 0.217,
              "count": 4
            },
            "inject_phantom_success \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2141,
              "count": 1
            }
          },
          "openai/gpt-5.5": {
            "model_id": "openai/gpt-5.5",
            "label": "GPT-5.5",
            "sessions_with_steps": 6,
            " \u00d7 baseline": {
              "mean_distance": 0.186,
              "count": 3
            },
            "baseline \u00d7 baseline": {
              "mean_distance": 0.1985,
              "count": 3
            }
          },
          "openai/gpt-5.6": {
            "model_id": "openai/gpt-5.6",
            "label": "GPT-5.6",
            "sessions_with_steps": 16,
            "baseline \u00d7 baseline": {
              "mean_distance": 0.2164,
              "count": 91
            },
            "baseline \u00d7 remove_critical_constraint": {
              "mean_distance": 0.2285,
              "count": 14
            }
          },
          "openai/gpt-5.6-fast": {
            "model_id": "openai/gpt-5.6-fast",
            "label": "GPT-5.6-fast",
            "sessions_with_steps": 9,
            " \u00d7 ": {
              "mean_distance": 0.2237,
              "count": 1
            },
            " \u00d7 baseline": {
              "mean_distance": 0.1867,
              "count": 12
            },
            "baseline \u00d7 baseline": {
              "mean_distance": 0.2164,
              "count": 15
            }
          },
          "unknown": {
            "model_id": "unknown",
            "label": "unknown",
            "sessions_with_steps": 6,
            "? \u00d7 ?": {
              "mean_distance": 0.2317,
              "count": 3
            }
          }
        },
        "pairs": [
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_3hlb2bus",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1809
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_3j2vrct4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1967
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_6xzauw79",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2492
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_9u9p6onc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2426
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_batch_batch_data_table_baseline claude_fable_5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2112
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_batch_batch_task_manager_baseline claude_fable",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 3,
            "mean_distance": 0.2465
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_e8bbu37m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1851
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_fhxfescx",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1802
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "invert_constraint \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2204
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "invert_constraint \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.0888
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2108
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2713
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1661
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.223
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2349
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_phantom_success \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2074
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1647
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2114
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2626
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 3,
            "mean_distance": 0.1625
          },
          {
            "session_a": "exp_1q13yzyh",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2003
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_3j2vrct4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1223
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_6xzauw79",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2566
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_9u9p6onc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2378
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_batch_batch_data_table_baseline claude_fable_5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2239
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_batch_batch_task_manager_baseline claude_fable",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 3,
            "mean_distance": 0.2275
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_e8bbu37m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1951
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_fhxfescx",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.217
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1965
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1724
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1891
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2532
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2153
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2182
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2215
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2013
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1865
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1876
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2253
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 3,
            "mean_distance": 0.2011
          },
          {
            "session_a": "exp_3hlb2bus",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2173
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_6xzauw79",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2393
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_9u9p6onc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2263
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_batch_batch_data_table_baseline claude_fable_5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2194
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_batch_batch_task_manager_baseline claude_fable",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2002
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_e8bbu37m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1556
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_fhxfescx",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2092
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1876
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1632
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.105
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.278
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2235
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2039
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2134
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2061
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1947
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1554
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2167
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.1905
          },
          {
            "session_a": "exp_3j2vrct4",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2222
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_9u9p6onc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.0177
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_batch_batch_data_table_baseline claude_fable_5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2175
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_batch_batch_task_manager_baseline claude_fable",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2116
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_e8bbu37m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2124
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_fhxfescx",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2609
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2453
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2404
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2229
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2367
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2483
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.09
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2206
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2277
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2287
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2371
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2404
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2611
          },
          {
            "session_a": "exp_6xzauw79",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2581
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_batch_batch_data_table_baseline claude_fable_5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2029
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_batch_batch_task_manager_baseline claude_fable",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2045
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_e8bbu37m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1999
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_fhxfescx",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2607
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2357
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2268
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2151
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.242
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2477
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.0838
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.212
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2257
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2218
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2252
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2359
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2527
          },
          {
            "session_a": "exp_9u9p6onc",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2528
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_batch_batch_task_manager_baseline claude_fable",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2044
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_e8bbu37m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2193
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_fhxfescx",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2242
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2022
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2035
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1978
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2623
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1966
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2118
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.193
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1991
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2076
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1888
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2631
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2142
          },
          {
            "session_a": "exp_batch_batch_data_table_baseline claude_fable_5",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2306
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_e8bbu37m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2182
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_fhxfescx",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2056
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1721
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 4,
            "mean_distance": 0.2308
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1824
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2566
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 4,
            "mean_distance": 0.2322
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2207
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.1794
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.188
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2304
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1481
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2306
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 3,
            "mean_distance": 0.201
          },
          {
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 4,
            "mean_distance": 0.2309
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_fhxfescx",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2198
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.222
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1885
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1826
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2628
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2008
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.1994
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2422
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2084
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1845
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2035
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2248
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 3,
            "mean_distance": 0.1866
          },
          {
            "session_a": "exp_e8bbu37m",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1875
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_gfjpa3ah",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2357
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1516
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1874
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2614
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.0782
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2575
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2145
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 inject_phantom_success",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.207
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1531
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.183
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2621
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2097
          },
          {
            "session_a": "exp_fhxfescx",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2319
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_icd406w9",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "invert_constraint \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2147
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1621
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.264
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2417
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2409
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.1329
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_phantom_success \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1907
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2256
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1268
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2483
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.1048
          },
          {
            "session_a": "exp_gfjpa3ah",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 remove_critical_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1815
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_jcrbm3rt",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1778
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2732
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 4,
            "mean_distance": 0.1513
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2012
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.213
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_phantom_success \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2178
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1544
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1693
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2608
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 3,
            "mean_distance": 0.1807
          },
          {
            "session_a": "exp_icd406w9",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 invert_constraint",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 4,
            "mean_distance": 0.2059
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_kt9lwfj8",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2451
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1992
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.206
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.1735
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.175
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1871
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1102
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2175
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.1529
          },
          {
            "session_a": "exp_jcrbm3rt",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2188
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_lk5zq3vn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.277
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2558
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.239
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_phantom_success",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2517
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.2938
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.246
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_swp_Claude_F_np",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2908
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_trdn7iwn",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_alien_vocab",
            "class_a": "",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2639
          },
          {
            "session_a": "exp_kt9lwfj8",
            "session_b": "exp_wo0bkk9m",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 baseline",
            "class_a": "",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.282
          },
          {
            "session_a": "exp_lk5zq3vn",
            "session_b": "exp_ovy9g9b5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "",
            "overlapping_steps": 2,
            "mean_distance": 0.2463
          },
          {
            "session_a": "exp_lk5zq3vn",
            "session_b": "exp_oylan6wf",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_alien_vocab \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "manifold",
            "overlapping_steps": 2,
            "mean_distance": 0.2107
          },
          {
            "session_a": "exp_lk5zq3vn",
            "session_b": "exp_q8yr7jw4",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "inject_competing_goal \u00d7 inject_phantom_success",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.2106
          },
          {
            "session_a": "exp_lk5zq3vn",
            "session_b": "exp_q9ckxin5",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 3,
            "mean_distance": 0.1621
          },
          {
            "session_a": "exp_lk5zq3vn",
            "session_b": "exp_qu6tc1zc",
            "model": "anthropic/claude-fable-5",
            "operator_pair": "baseline \u00d7 inject_competing_goal",
            "class_a": "semantic",
            "class_b": "semantic",
            "overlapping_steps": 2,
            "mean_distance": 0.1943
          }
        ]
      }
    },
    "cross_model": {
      "meta": {
        "experiment_id": "lab_cross_model_reasoning",
        "total_step_embeddings": 2215,
        "models_compared": 8,
        "model_pairs": 28,
        "data_source": "ChromaDB \u2014 per-step reasoning embeddings via bge-m3",
        "method": "Model-level centroid comparison + per-step-position distances"
      },
      "data": {
        "model_summary": {
          "anthropic/claude-fable-5": {
            "steps": 75,
            "sessions": 39
          },
          "deepseek/deepseek-v4-pro": {
            "steps": 1471,
            "sessions": 101
          },
          "openai/gpt-5": {
            "steps": 80,
            "sessions": 7
          },
          "openai/gpt-5-mini": {
            "steps": 174,
            "sessions": 13
          },
          "openai/gpt-5-nano": {
            "steps": 140,
            "sessions": 7
          },
          "openai/gpt-5.5": {
            "steps": 41,
            "sessions": 6
          },
          "openai/gpt-5.6": {
            "steps": 142,
            "sessions": 16
          },
          "openai/gpt-5.6-fast": {
            "steps": 71,
            "sessions": 9
          }
        },
        "centroid_comparison": [
          {
            "model_a": "anthropic/claude-fable-5",
            "model_b": "deepseek/deepseek-v4-pro",
            "centroid_distance": 0.0196,
            "steps_a": 75,
            "steps_b": 1471
          },
          {
            "model_a": "anthropic/claude-fable-5",
            "model_b": "openai/gpt-5",
            "centroid_distance": 0.0737,
            "steps_a": 75,
            "steps_b": 80
          },
          {
            "model_a": "anthropic/claude-fable-5",
            "model_b": "openai/gpt-5-mini",
            "centroid_distance": 0.0731,
            "steps_a": 75,
            "steps_b": 174
          },
          {
            "model_a": "anthropic/claude-fable-5",
            "model_b": "openai/gpt-5-nano",
            "centroid_distance": 0.0749,
            "steps_a": 75,
            "steps_b": 140
          },
          {
            "model_a": "anthropic/claude-fable-5",
            "model_b": "openai/gpt-5.5",
            "centroid_distance": 0.065,
            "steps_a": 75,
            "steps_b": 41
          },
          {
            "model_a": "anthropic/claude-fable-5",
            "model_b": "openai/gpt-5.6",
            "centroid_distance": 0.0596,
            "steps_a": 75,
            "steps_b": 142
          },
          {
            "model_a": "anthropic/claude-fable-5",
            "model_b": "openai/gpt-5.6-fast",
            "centroid_distance": 0.0609,
            "steps_a": 75,
            "steps_b": 71
          },
          {
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5",
            "centroid_distance": 0.0598,
            "steps_a": 1471,
            "steps_b": 80
          },
          {
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5-mini",
            "centroid_distance": 0.0598,
            "steps_a": 1471,
            "steps_b": 174
          },
          {
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5-nano",
            "centroid_distance": 0.063,
            "steps_a": 1471,
            "steps_b": 140
          },
          {
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5.5",
            "centroid_distance": 0.0585,
            "steps_a": 1471,
            "steps_b": 41
          },
          {
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5.6",
            "centroid_distance": 0.0513,
            "steps_a": 1471,
            "steps_b": 142
          },
          {
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5.6-fast",
            "centroid_distance": 0.0547,
            "steps_a": 1471,
            "steps_b": 71
          },
          {
            "model_a": "openai/gpt-5",
            "model_b": "openai/gpt-5-mini",
            "centroid_distance": 0.0139,
            "steps_a": 80,
            "steps_b": 174
          },
          {
            "model_a": "openai/gpt-5",
            "model_b": "openai/gpt-5-nano",
            "centroid_distance": 0.0099,
            "steps_a": 80,
            "steps_b": 140
          },
          {
            "model_a": "openai/gpt-5",
            "model_b": "openai/gpt-5.5",
            "centroid_distance": 0.0322,
            "steps_a": 80,
            "steps_b": 41
          },
          {
            "model_a": "openai/gpt-5",
            "model_b": "openai/gpt-5.6",
            "centroid_distance": 0.0275,
            "steps_a": 80,
            "steps_b": 142
          },
          {
            "model_a": "openai/gpt-5",
            "model_b": "openai/gpt-5.6-fast",
            "centroid_distance": 0.0243,
            "steps_a": 80,
            "steps_b": 71
          },
          {
            "model_a": "openai/gpt-5-mini",
            "model_b": "openai/gpt-5-nano",
            "centroid_distance": 0.0092,
            "steps_a": 174,
            "steps_b": 140
          },
          {
            "model_a": "openai/gpt-5-mini",
            "model_b": "openai/gpt-5.5",
            "centroid_distance": 0.0272,
            "steps_a": 174,
            "steps_b": 41
          },
          {
            "model_a": "openai/gpt-5-mini",
            "model_b": "openai/gpt-5.6",
            "centroid_distance": 0.0257,
            "steps_a": 174,
            "steps_b": 142
          },
          {
            "model_a": "openai/gpt-5-mini",
            "model_b": "openai/gpt-5.6-fast",
            "centroid_distance": 0.0225,
            "steps_a": 174,
            "steps_b": 71
          },
          {
            "model_a": "openai/gpt-5-nano",
            "model_b": "openai/gpt-5.5",
            "centroid_distance": 0.03,
            "steps_a": 140,
            "steps_b": 41
          },
          {
            "model_a": "openai/gpt-5-nano",
            "model_b": "openai/gpt-5.6",
            "centroid_distance": 0.0273,
            "steps_a": 140,
            "steps_b": 142
          },
          {
            "model_a": "openai/gpt-5-nano",
            "model_b": "openai/gpt-5.6-fast",
            "centroid_distance": 0.0234,
            "steps_a": 140,
            "steps_b": 71
          },
          {
            "model_a": "openai/gpt-5.5",
            "model_b": "openai/gpt-5.6",
            "centroid_distance": 0.015,
            "steps_a": 41,
            "steps_b": 142
          },
          {
            "model_a": "openai/gpt-5.5",
            "model_b": "openai/gpt-5.6-fast",
            "centroid_distance": 0.0104,
            "steps_a": 41,
            "steps_b": 71
          },
          {
            "model_a": "openai/gpt-5.6",
            "model_b": "openai/gpt-5.6-fast",
            "centroid_distance": 0.0062,
            "steps_a": 142,
            "steps_b": 71
          }
        ],
        "cross_model": {
          "anthropic/claude-fable-5 \u2194 deepseek/deepseek-v4-pro": {
            "label": "anthropic/claude-fable-5 \u2194 deepseek/deepseek-v4-pro",
            "centroid_distance": 0.0196,
            "position_count": 4,
            "total_steps_a": 75,
            "total_steps_b": 1471
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5": {
            "label": "anthropic/claude-fable-5 \u2194 openai/gpt-5",
            "centroid_distance": 0.0737,
            "position_count": 4,
            "total_steps_a": 75,
            "total_steps_b": 80
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5-mini": {
            "label": "anthropic/claude-fable-5 \u2194 openai/gpt-5-mini",
            "centroid_distance": 0.0731,
            "position_count": 4,
            "total_steps_a": 75,
            "total_steps_b": 174
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5-nano": {
            "label": "anthropic/claude-fable-5 \u2194 openai/gpt-5-nano",
            "centroid_distance": 0.0749,
            "position_count": 4,
            "total_steps_a": 75,
            "total_steps_b": 140
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.5": {
            "label": "anthropic/claude-fable-5 \u2194 openai/gpt-5.5",
            "centroid_distance": 0.065,
            "position_count": 4,
            "total_steps_a": 75,
            "total_steps_b": 41
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.6": {
            "label": "anthropic/claude-fable-5 \u2194 openai/gpt-5.6",
            "centroid_distance": 0.0596,
            "position_count": 4,
            "total_steps_a": 75,
            "total_steps_b": 142
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.6-fast": {
            "label": "anthropic/claude-fable-5 \u2194 openai/gpt-5.6-fast",
            "centroid_distance": 0.0609,
            "position_count": 4,
            "total_steps_a": 75,
            "total_steps_b": 71
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5": {
            "label": "deepseek/deepseek-v4-pro \u2194 openai/gpt-5",
            "centroid_distance": 0.0598,
            "position_count": 24,
            "total_steps_a": 1471,
            "total_steps_b": 80
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5-mini": {
            "label": "deepseek/deepseek-v4-pro \u2194 openai/gpt-5-mini",
            "centroid_distance": 0.0598,
            "position_count": 28,
            "total_steps_a": 1471,
            "total_steps_b": 174
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5-nano": {
            "label": "deepseek/deepseek-v4-pro \u2194 openai/gpt-5-nano",
            "centroid_distance": 0.063,
            "position_count": 29,
            "total_steps_a": 1471,
            "total_steps_b": 140
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.5": {
            "label": "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.5",
            "centroid_distance": 0.0585,
            "position_count": 14,
            "total_steps_a": 1471,
            "total_steps_b": 41
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.6": {
            "label": "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.6",
            "centroid_distance": 0.0513,
            "position_count": 17,
            "total_steps_a": 1471,
            "total_steps_b": 142
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.6-fast": {
            "label": "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.6-fast",
            "centroid_distance": 0.0547,
            "position_count": 13,
            "total_steps_a": 1471,
            "total_steps_b": 71
          },
          "openai/gpt-5 \u2194 openai/gpt-5-mini": {
            "label": "openai/gpt-5 \u2194 openai/gpt-5-mini",
            "centroid_distance": 0.0139,
            "position_count": 24,
            "total_steps_a": 80,
            "total_steps_b": 174
          },
          "openai/gpt-5 \u2194 openai/gpt-5-nano": {
            "label": "openai/gpt-5 \u2194 openai/gpt-5-nano",
            "centroid_distance": 0.0099,
            "position_count": 24,
            "total_steps_a": 80,
            "total_steps_b": 140
          },
          "openai/gpt-5 \u2194 openai/gpt-5.5": {
            "label": "openai/gpt-5 \u2194 openai/gpt-5.5",
            "centroid_distance": 0.0322,
            "position_count": 14,
            "total_steps_a": 80,
            "total_steps_b": 41
          },
          "openai/gpt-5 \u2194 openai/gpt-5.6": {
            "label": "openai/gpt-5 \u2194 openai/gpt-5.6",
            "centroid_distance": 0.0275,
            "position_count": 17,
            "total_steps_a": 80,
            "total_steps_b": 142
          },
          "openai/gpt-5 \u2194 openai/gpt-5.6-fast": {
            "label": "openai/gpt-5 \u2194 openai/gpt-5.6-fast",
            "centroid_distance": 0.0243,
            "position_count": 13,
            "total_steps_a": 80,
            "total_steps_b": 71
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5-nano": {
            "label": "openai/gpt-5-mini \u2194 openai/gpt-5-nano",
            "centroid_distance": 0.0092,
            "position_count": 28,
            "total_steps_a": 174,
            "total_steps_b": 140
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.5": {
            "label": "openai/gpt-5-mini \u2194 openai/gpt-5.5",
            "centroid_distance": 0.0272,
            "position_count": 14,
            "total_steps_a": 174,
            "total_steps_b": 41
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.6": {
            "label": "openai/gpt-5-mini \u2194 openai/gpt-5.6",
            "centroid_distance": 0.0257,
            "position_count": 17,
            "total_steps_a": 174,
            "total_steps_b": 142
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.6-fast": {
            "label": "openai/gpt-5-mini \u2194 openai/gpt-5.6-fast",
            "centroid_distance": 0.0225,
            "position_count": 13,
            "total_steps_a": 174,
            "total_steps_b": 71
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.5": {
            "label": "openai/gpt-5-nano \u2194 openai/gpt-5.5",
            "centroid_distance": 0.03,
            "position_count": 14,
            "total_steps_a": 140,
            "total_steps_b": 41
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.6": {
            "label": "openai/gpt-5-nano \u2194 openai/gpt-5.6",
            "centroid_distance": 0.0273,
            "position_count": 17,
            "total_steps_a": 140,
            "total_steps_b": 142
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.6-fast": {
            "label": "openai/gpt-5-nano \u2194 openai/gpt-5.6-fast",
            "centroid_distance": 0.0234,
            "position_count": 13,
            "total_steps_a": 140,
            "total_steps_b": 71
          },
          "openai/gpt-5.5 \u2194 openai/gpt-5.6": {
            "label": "openai/gpt-5.5 \u2194 openai/gpt-5.6",
            "centroid_distance": 0.015,
            "position_count": 14,
            "total_steps_a": 41,
            "total_steps_b": 142
          },
          "openai/gpt-5.5 \u2194 openai/gpt-5.6-fast": {
            "label": "openai/gpt-5.5 \u2194 openai/gpt-5.6-fast",
            "centroid_distance": 0.0104,
            "position_count": 13,
            "total_steps_a": 41,
            "total_steps_b": 71
          },
          "openai/gpt-5.6 \u2194 openai/gpt-5.6-fast": {
            "label": "openai/gpt-5.6 \u2194 openai/gpt-5.6-fast",
            "centroid_distance": 0.0062,
            "position_count": 13,
            "total_steps_a": 142,
            "total_steps_b": 71
          }
        },
        "per_step_position": {
          "0": {
            "mean_distance": 0.08,
            "std_dev": 0.0285,
            "model_pairs": 28
          },
          "1": {
            "mean_distance": 0.0805,
            "std_dev": 0.0219,
            "model_pairs": 28
          },
          "2": {
            "mean_distance": 0.0948,
            "std_dev": 0.0379,
            "model_pairs": 28
          },
          "3": {
            "mean_distance": 0.0992,
            "std_dev": 0.0298,
            "model_pairs": 28
          },
          "4": {
            "mean_distance": 0.0698,
            "std_dev": 0.0274,
            "model_pairs": 21
          },
          "5": {
            "mean_distance": 0.0776,
            "std_dev": 0.0233,
            "model_pairs": 21
          },
          "6": {
            "mean_distance": 0.0859,
            "std_dev": 0.0225,
            "model_pairs": 21
          },
          "7": {
            "mean_distance": 0.0956,
            "std_dev": 0.0262,
            "model_pairs": 21
          },
          "8": {
            "mean_distance": 0.0945,
            "std_dev": 0.0185,
            "model_pairs": 21
          },
          "9": {
            "mean_distance": 0.1067,
            "std_dev": 0.0295,
            "model_pairs": 21
          },
          "10": {
            "mean_distance": 0.1269,
            "std_dev": 0.0433,
            "model_pairs": 21
          },
          "11": {
            "mean_distance": 0.1449,
            "std_dev": 0.0414,
            "model_pairs": 21
          },
          "12": {
            "mean_distance": 0.1754,
            "std_dev": 0.0438,
            "model_pairs": 21
          },
          "13": {
            "mean_distance": 0.1651,
            "std_dev": 0.0599,
            "model_pairs": 15
          },
          "14": {
            "mean_distance": 0.1452,
            "std_dev": 0.0469,
            "model_pairs": 10
          },
          "15": {
            "mean_distance": 0.1564,
            "std_dev": 0.0512,
            "model_pairs": 10
          },
          "16": {
            "mean_distance": 0.1876,
            "std_dev": 0.0622,
            "model_pairs": 10
          },
          "17": {
            "mean_distance": 0.1927,
            "std_dev": 0.0552,
            "model_pairs": 6
          },
          "18": {
            "mean_distance": 0.1865,
            "std_dev": 0.0426,
            "model_pairs": 6
          },
          "19": {
            "mean_distance": 0.1839,
            "std_dev": 0.0439,
            "model_pairs": 6
          },
          "20": {
            "mean_distance": 0.156,
            "std_dev": 0.0287,
            "model_pairs": 6
          },
          "21": {
            "mean_distance": 0.1739,
            "std_dev": 0.0318,
            "model_pairs": 6
          },
          "22": {
            "mean_distance": 0.185,
            "std_dev": 0.0375,
            "model_pairs": 6
          },
          "23": {
            "mean_distance": 0.1903,
            "std_dev": 0.0329,
            "model_pairs": 6
          },
          "24": {
            "mean_distance": 0.175,
            "std_dev": 0.0414,
            "model_pairs": 3
          },
          "25": {
            "mean_distance": 0.2061,
            "std_dev": 0.035,
            "model_pairs": 3
          },
          "26": {
            "mean_distance": 0.2376,
            "std_dev": 0.0338,
            "model_pairs": 3
          },
          "27": {
            "mean_distance": 0.2189,
            "std_dev": 0.0257,
            "model_pairs": 3
          },
          "28": {
            "mean_distance": 0.2253,
            "std_dev": 0,
            "model_pairs": 1
          }
        },
        "position_details": {
          "anthropic/claude-fable-5 \u2194 deepseek/deepseek-v4-pro": {
            "0": {
              "distance": 0.0765,
              "n_a": 39,
              "n_b": 101
            },
            "1": {
              "distance": 0.069,
              "n_a": 22,
              "n_b": 100
            },
            "2": {
              "distance": 0.0961,
              "n_a": 10,
              "n_b": 99
            },
            "3": {
              "distance": 0.1116,
              "n_a": 4,
              "n_b": 98
            }
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5": {
            "0": {
              "distance": 0.1095,
              "n_a": 39,
              "n_b": 7
            },
            "1": {
              "distance": 0.0909,
              "n_a": 22,
              "n_b": 7
            },
            "2": {
              "distance": 0.1352,
              "n_a": 10,
              "n_b": 6
            },
            "3": {
              "distance": 0.1277,
              "n_a": 4,
              "n_b": 6
            }
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5-mini": {
            "0": {
              "distance": 0.0978,
              "n_a": 39,
              "n_b": 13
            },
            "1": {
              "distance": 0.0985,
              "n_a": 22,
              "n_b": 13
            },
            "2": {
              "distance": 0.1415,
              "n_a": 10,
              "n_b": 12
            },
            "3": {
              "distance": 0.1005,
              "n_a": 4,
              "n_b": 12
            }
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5-nano": {
            "0": {
              "distance": 0.1022,
              "n_a": 39,
              "n_b": 7
            },
            "1": {
              "distance": 0.0957,
              "n_a": 22,
              "n_b": 7
            },
            "2": {
              "distance": 0.1266,
              "n_a": 10,
              "n_b": 7
            },
            "3": {
              "distance": 0.1365,
              "n_a": 4,
              "n_b": 7
            }
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.5": {
            "0": {
              "distance": 0.0754,
              "n_a": 39,
              "n_b": 6
            },
            "1": {
              "distance": 0.1322,
              "n_a": 22,
              "n_b": 4
            },
            "2": {
              "distance": 0.1781,
              "n_a": 10,
              "n_b": 4
            },
            "3": {
              "distance": 0.156,
              "n_a": 4,
              "n_b": 4
            }
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.6": {
            "0": {
              "distance": 0.099,
              "n_a": 39,
              "n_b": 16
            },
            "1": {
              "distance": 0.0939,
              "n_a": 22,
              "n_b": 15
            },
            "2": {
              "distance": 0.1325,
              "n_a": 10,
              "n_b": 14
            },
            "3": {
              "distance": 0.1063,
              "n_a": 4,
              "n_b": 13
            }
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.6-fast": {
            "0": {
              "distance": 0.0857,
              "n_a": 39,
              "n_b": 9
            },
            "1": {
              "distance": 0.0997,
              "n_a": 22,
              "n_b": 8
            },
            "2": {
              "distance": 0.1433,
              "n_a": 10,
              "n_b": 8
            },
            "3": {
              "distance": 0.1031,
              "n_a": 4,
              "n_b": 8
            }
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5": {
            "0": {
              "distance": 0.0494,
              "n_a": 101,
              "n_b": 7
            },
            "1": {
              "distance": 0.0711,
              "n_a": 100,
              "n_b": 7
            },
            "2": {
              "distance": 0.117,
              "n_a": 99,
              "n_b": 6
            },
            "3": {
              "distance": 0.1237,
              "n_a": 98,
              "n_b": 6
            },
            "4": {
              "distance": 0.1233,
              "n_a": 97,
              "n_b": 6
            },
            "5": {
              "distance": 0.0997,
              "n_a": 96,
              "n_b": 6
            },
            "6": {
              "distance": 0.0919,
              "n_a": 94,
              "n_b": 5
            },
            "7": {
              "distance": 0.11,
              "n_a": 91,
              "n_b": 5
            },
            "8": {
              "distance": 0.1058,
              "n_a": 86,
              "n_b": 4
            },
            "9": {
              "distance": 0.0986,
              "n_a": 77,
              "n_b": 4
            },
            "10": {
              "distance": 0.1149,
              "n_a": 72,
              "n_b": 4
            },
            "11": {
              "distance": 0.1326,
              "n_a": 63,
              "n_b": 3
            },
            "12": {
              "distance": 0.1839,
              "n_a": 57,
              "n_b": 2
            },
            "13": {
              "distance": 0.1676,
              "n_a": 52,
              "n_b": 2
            },
            "14": {
              "distance": 0.1587,
              "n_a": 45,
              "n_b": 2
            },
            "15": {
              "distance": 0.1648,
              "n_a": 38,
              "n_b": 2
            },
            "16": {
              "distance": 0.1312,
              "n_a": 31,
              "n_b": 2
            },
            "17": {
              "distance": 0.2206,
              "n_a": 26,
              "n_b": 1
            },
            "18": {
              "distance": 0.216,
              "n_a": 24,
              "n_b": 1
            },
            "19": {
              "distance": 0.2076,
              "n_a": 18,
              "n_b": 1
            },
            "20": {
              "distance": 0.1817,
              "n_a": 14,
              "n_b": 1
            },
            "21": {
              "distance": 0.1687,
              "n_a": 12,
              "n_b": 1
            },
            "22": {
              "distance": 0.175,
              "n_a": 9,
              "n_b": 1
            },
            "23": {
              "distance": 0.1983,
              "n_a": 9,
              "n_b": 1
            }
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5-mini": {
            "0": {
              "distance": 0.0841,
              "n_a": 101,
              "n_b": 13
            },
            "1": {
              "distance": 0.086,
              "n_a": 100,
              "n_b": 13
            },
            "2": {
              "distance": 0.1168,
              "n_a": 99,
              "n_b": 12
            },
            "3": {
              "distance": 0.1315,
              "n_a": 98,
              "n_b": 12
            },
            "4": {
              "distance": 0.0903,
              "n_a": 97,
              "n_b": 12
            },
            "5": {
              "distance": 0.0942,
              "n_a": 96,
              "n_b": 12
            },
            "6": {
              "distance": 0.1094,
              "n_a": 94,
              "n_b": 12
            },
            "7": {
              "distance": 0.1249,
              "n_a": 91,
              "n_b": 12
            },
            "8": {
              "distance": 0.1085,
              "n_a": 86,
              "n_b": 10
            },
            "9": {
              "distance": 0.1011,
              "n_a": 77,
              "n_b": 10
            },
            "10": {
              "distance": 0.1068,
              "n_a": 72,
              "n_b": 9
            },
            "11": {
              "distance": 0.1081,
              "n_a": 63,
              "n_b": 9
            },
            "12": {
              "distance": 0.1192,
              "n_a": 57,
              "n_b": 8
            },
            "13": {
              "distance": 0.1055,
              "n_a": 52,
              "n_b": 7
            },
            "14": {
              "distance": 0.0961,
              "n_a": 45,
              "n_b": 6
            },
            "15": {
              "distance": 0.0804,
              "n_a": 38,
              "n_b": 5
            },
            "16": {
              "distance": 0.2058,
              "n_a": 31,
              "n_b": 1
            },
            "17": {
              "distance": 0.2033,
              "n_a": 26,
              "n_b": 1
            },
            "18": {
              "distance": 0.189,
              "n_a": 24,
              "n_b": 1
            },
            "19": {
              "distance": 0.172,
              "n_a": 18,
              "n_b": 1
            },
            "20": {
              "distance": 0.1849,
              "n_a": 14,
              "n_b": 1
            },
            "21": {
              "distance": 0.1839,
              "n_a": 12,
              "n_b": 1
            },
            "22": {
              "distance": 0.185,
              "n_a": 9,
              "n_b": 1
            },
            "23": {
              "distance": 0.1858,
              "n_a": 9,
              "n_b": 1
            },
            "24": {
              "distance": 0.1934,
              "n_a": 7,
              "n_b": 1
            },
            "25": {
              "distance": 0.22,
              "n_a": 5,
              "n_b": 1
            },
            "26": {
              "distance": 0.2219,
              "n_a": 5,
              "n_b": 1
            },
            "27": {
              "distance": 0.203,
              "n_a": 5,
              "n_b": 1
            }
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5-nano": {
            "0": {
              "distance": 0.0539,
              "n_a": 101,
              "n_b": 7
            },
            "1": {
              "distance": 0.0702,
              "n_a": 100,
              "n_b": 7
            },
            "2": {
              "distance": 0.1168,
              "n_a": 99,
              "n_b": 7
            },
            "3": {
              "distance": 0.1314,
              "n_a": 98,
              "n_b": 7
            },
            "4": {
              "distance": 0.124,
              "n_a": 97,
              "n_b": 6
            },
            "5": {
              "distance": 0.1095,
              "n_a": 96,
              "n_b": 6
            },
            "6": {
              "distance": 0.1059,
              "n_a": 94,
              "n_b": 6
            },
            "7": {
              "distance": 0.1147,
              "n_a": 91,
              "n_b": 6
            },
            "8": {
              "distance": 0.1079,
              "n_a": 86,
              "n_b": 6
            },
            "9": {
              "distance": 0.1079,
              "n_a": 77,
              "n_b": 6
            },
            "10": {
              "distance": 0.0857,
              "n_a": 72,
              "n_b": 6
            },
            "11": {
              "distance": 0.0917,
              "n_a": 63,
              "n_b": 6
            },
            "12": {
              "distance": 0.103,
              "n_a": 57,
              "n_b": 6
            },
            "13": {
              "distance": 0.1005,
              "n_a": 52,
              "n_b": 6
            },
            "14": {
              "distance": 0.0843,
              "n_a": 45,
              "n_b": 6
            },
            "15": {
              "distance": 0.0997,
              "n_a": 38,
              "n_b": 6
            },
            "16": {
              "distance": 0.1013,
              "n_a": 31,
              "n_b": 6
            },
            "17": {
              "distance": 0.0833,
              "n_a": 26,
              "n_b": 6
            },
            "18": {
              "distance": 0.1076,
              "n_a": 24,
              "n_b": 5
            },
            "19": {
              "distance": 0.1098,
              "n_a": 18,
              "n_b": 3
            },
            "20": {
              "distance": 0.1084,
              "n_a": 14,
              "n_b": 3
            },
            "21": {
              "distance": 0.1359,
              "n_a": 12,
              "n_b": 3
            },
            "22": {
              "distance": 0.1181,
              "n_a": 9,
              "n_b": 3
            },
            "23": {
              "distance": 0.1223,
              "n_a": 9,
              "n_b": 3
            },
            "24": {
              "distance": 0.1177,
              "n_a": 7,
              "n_b": 3
            },
            "25": {
              "distance": 0.158,
              "n_a": 5,
              "n_b": 2
            },
            "26": {
              "distance": 0.2064,
              "n_a": 5,
              "n_b": 1
            },
            "27": {
              "distance": 0.1985,
              "n_a": 5,
              "n_b": 1
            },
            "28": {
              "distance": 0.2253,
              "n_a": 5,
              "n_b": 1
            }
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.5": {
            "0": {
              "distance": 0.0872,
              "n_a": 101,
              "n_b": 6
            },
            "1": {
              "distance": 0.0969,
              "n_a": 100,
              "n_b": 4
            },
            "2": {
              "distance": 0.1384,
              "n_a": 99,
              "n_b": 4
            },
            "3": {
              "distance": 0.1402,
              "n_a": 98,
              "n_b": 4
            },
            "4": {
              "distance": 0.1103,
              "n_a": 97,
              "n_b": 4
            },
            "5": {
              "distance": 0.123,
              "n_a": 96,
              "n_b": 4
            },
            "6": {
              "distance": 0.134,
              "n_a": 94,
              "n_b": 3
            },
            "7": {
              "distance": 0.1165,
              "n_a": 91,
              "n_b": 3
            },
            "8": {
              "distance": 0.0977,
              "n_a": 86,
              "n_b": 3
            },
            "9": {
              "distance": 0.1532,
              "n_a": 77,
              "n_b": 2
            },
            "10": {
              "distance": 0.172,
              "n_a": 72,
              "n_b": 1
            },
            "11": {
              "distance": 0.1981,
              "n_a": 63,
              "n_b": 1
            },
            "12": {
              "distance": 0.1868,
              "n_a": 57,
              "n_b": 1
            },
            "13": {
              "distance": 0.1814,
              "n_a": 52,
              "n_b": 1
            }
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.6": {
            "0": {
              "distance": 0.1178,
              "n_a": 101,
              "n_b": 16
            },
            "1": {
              "distance": 0.0836,
              "n_a": 100,
              "n_b": 15
            },
            "2": {
              "distance": 0.0979,
              "n_a": 99,
              "n_b": 14
            },
            "3": {
              "distance": 0.1318,
              "n_a": 98,
              "n_b": 13
            },
            "4": {
              "distance": 0.1044,
              "n_a": 97,
              "n_b": 13
            },
            "5": {
              "distance": 0.0898,
              "n_a": 96,
              "n_b": 13
            },
            "6": {
              "distance": 0.08,
              "n_a": 94,
              "n_b": 13
            },
            "7": {
              "distance": 0.0999,
              "n_a": 91,
              "n_b": 13
            },
            "8": {
              "distance": 0.09,
              "n_a": 86,
              "n_b": 12
            },
            "9": {
              "distance": 0.0969,
              "n_a": 77,
              "n_b": 8
            },
            "10": {
              "distance": 0.104,
              "n_a": 72,
              "n_b": 5
            },
            "11": {
              "distance": 0.1232,
              "n_a": 63,
              "n_b": 2
            },
            "12": {
              "distance": 0.1702,
              "n_a": 57,
              "n_b": 1
            },
            "13": {
              "distance": 0.184,
              "n_a": 52,
              "n_b": 1
            },
            "14": {
              "distance": 0.1617,
              "n_a": 45,
              "n_b": 1
            },
            "15": {
              "distance": 0.1822,
              "n_a": 38,
              "n_b": 1
            },
            "16": {
              "distance": 0.1624,
              "n_a": 31,
              "n_b": 1
            }
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.6-fast": {
            "0": {
              "distance": 0.1015,
              "n_a": 101,
              "n_b": 9
            },
            "1": {
              "distance": 0.08,
              "n_a": 100,
              "n_b": 8
            },
            "2": {
              "distance": 0.1159,
              "n_a": 99,
              "n_b": 8
            },
            "3": {
              "distance": 0.1002,
              "n_a": 98,
              "n_b": 8
            },
            "4": {
              "distance": 0.0997,
              "n_a": 97,
              "n_b": 8
            },
            "5": {
              "distance": 0.1164,
              "n_a": 96,
              "n_b": 7
            },
            "6": {
              "distance": 0.1014,
              "n_a": 94,
              "n_b": 7
            },
            "7": {
              "distance": 0.1034,
              "n_a": 91,
              "n_b": 5
            },
            "8": {
              "distance": 0.1098,
              "n_a": 86,
              "n_b": 4
            },
            "9": {
              "distance": 0.1181,
              "n_a": 77,
              "n_b": 3
            },
            "10": {
              "distance": 0.1319,
              "n_a": 72,
              "n_b": 2
            },
            "11": {
              "distance": 0.1801,
              "n_a": 63,
              "n_b": 1
            },
            "12": {
              "distance": 0.2002,
              "n_a": 57,
              "n_b": 1
            }
          },
          "openai/gpt-5 \u2194 openai/gpt-5-mini": {
            "0": {
              "distance": 0.0823,
              "n_a": 7,
              "n_b": 13
            },
            "1": {
              "distance": 0.0808,
              "n_a": 7,
              "n_b": 13
            },
            "2": {
              "distance": 0.0445,
              "n_a": 6,
              "n_b": 12
            },
            "3": {
              "distance": 0.0466,
              "n_a": 6,
              "n_b": 12
            },
            "4": {
              "distance": 0.0585,
              "n_a": 6,
              "n_b": 12
            },
            "5": {
              "distance": 0.0558,
              "n_a": 6,
              "n_b": 12
            },
            "6": {
              "distance": 0.094,
              "n_a": 5,
              "n_b": 12
            },
            "7": {
              "distance": 0.0459,
              "n_a": 5,
              "n_b": 12
            },
            "8": {
              "distance": 0.0605,
              "n_a": 4,
              "n_b": 10
            },
            "9": {
              "distance": 0.067,
              "n_a": 4,
              "n_b": 10
            },
            "10": {
              "distance": 0.0522,
              "n_a": 4,
              "n_b": 9
            },
            "11": {
              "distance": 0.0897,
              "n_a": 3,
              "n_b": 9
            },
            "12": {
              "distance": 0.1166,
              "n_a": 2,
              "n_b": 8
            },
            "13": {
              "distance": 0.112,
              "n_a": 2,
              "n_b": 7
            },
            "14": {
              "distance": 0.1373,
              "n_a": 2,
              "n_b": 6
            },
            "15": {
              "distance": 0.1541,
              "n_a": 2,
              "n_b": 5
            },
            "16": {
              "distance": 0.2592,
              "n_a": 2,
              "n_b": 1
            },
            "17": {
              "distance": 0.2653,
              "n_a": 1,
              "n_b": 1
            },
            "18": {
              "distance": 0.2469,
              "n_a": 1,
              "n_b": 1
            },
            "19": {
              "distance": 0.2566,
              "n_a": 1,
              "n_b": 1
            },
            "20": {
              "distance": 0.1731,
              "n_a": 1,
              "n_b": 1
            },
            "21": {
              "distance": 0.2291,
              "n_a": 1,
              "n_b": 1
            },
            "22": {
              "distance": 0.2432,
              "n_a": 1,
              "n_b": 1
            },
            "23": {
              "distance": 0.2271,
              "n_a": 1,
              "n_b": 1
            }
          },
          "openai/gpt-5 \u2194 openai/gpt-5-nano": {
            "0": {
              "distance": 0.0349,
              "n_a": 7,
              "n_b": 7
            },
            "1": {
              "distance": 0.0475,
              "n_a": 7,
              "n_b": 7
            },
            "2": {
              "distance": 0.0486,
              "n_a": 6,
              "n_b": 7
            },
            "3": {
              "distance": 0.0965,
              "n_a": 6,
              "n_b": 7
            },
            "4": {
              "distance": 0.0523,
              "n_a": 6,
              "n_b": 6
            },
            "5": {
              "distance": 0.0643,
              "n_a": 6,
              "n_b": 6
            },
            "6": {
              "distance": 0.0806,
              "n_a": 5,
              "n_b": 6
            },
            "7": {
              "distance": 0.09,
              "n_a": 5,
              "n_b": 6
            },
            "8": {
              "distance": 0.0949,
              "n_a": 4,
              "n_b": 6
            },
            "9": {
              "distance": 0.1343,
              "n_a": 4,
              "n_b": 6
            },
            "10": {
              "distance": 0.1037,
              "n_a": 4,
              "n_b": 6
            },
            "11": {
              "distance": 0.1005,
              "n_a": 3,
              "n_b": 6
            },
            "12": {
              "distance": 0.1543,
              "n_a": 2,
              "n_b": 6
            },
            "13": {
              "distance": 0.1185,
              "n_a": 2,
              "n_b": 6
            },
            "14": {
              "distance": 0.1528,
              "n_a": 2,
              "n_b": 6
            },
            "15": {
              "distance": 0.1284,
              "n_a": 2,
              "n_b": 6
            },
            "16": {
              "distance": 0.0951,
              "n_a": 2,
              "n_b": 6
            },
            "17": {
              "distance": 0.1829,
              "n_a": 1,
              "n_b": 6
            },
            "18": {
              "distance": 0.1762,
              "n_a": 1,
              "n_b": 5
            },
            "19": {
              "distance": 0.1838,
              "n_a": 1,
              "n_b": 3
            },
            "20": {
              "distance": 0.1266,
              "n_a": 1,
              "n_b": 3
            },
            "21": {
              "distance": 0.1874,
              "n_a": 1,
              "n_b": 3
            },
            "22": {
              "distance": 0.1823,
              "n_a": 1,
              "n_b": 3
            },
            "23": {
              "distance": 0.1986,
              "n_a": 1,
              "n_b": 3
            }
          },
          "openai/gpt-5 \u2194 openai/gpt-5.5": {
            "0": {
              "distance": 0.0935,
              "n_a": 7,
              "n_b": 6
            },
            "1": {
              "distance": 0.1251,
              "n_a": 7,
              "n_b": 4
            },
            "2": {
              "distance": 0.1149,
              "n_a": 6,
              "n_b": 4
            },
            "3": {
              "distance": 0.0732,
              "n_a": 6,
              "n_b": 4
            },
            "4": {
              "distance": 0.0702,
              "n_a": 6,
              "n_b": 4
            },
            "5": {
              "distance": 0.0842,
              "n_a": 6,
              "n_b": 4
            },
            "6": {
              "distance": 0.1213,
              "n_a": 5,
              "n_b": 3
            },
            "7": {
              "distance": 0.0971,
              "n_a": 5,
              "n_b": 3
            },
            "8": {
              "distance": 0.1146,
              "n_a": 4,
              "n_b": 3
            },
            "9": {
              "distance": 0.1765,
              "n_a": 4,
              "n_b": 2
            },
            "10": {
              "distance": 0.2101,
              "n_a": 4,
              "n_b": 1
            },
            "11": {
              "distance": 0.2205,
              "n_a": 3,
              "n_b": 1
            },
            "12": {
              "distance": 0.2431,
              "n_a": 2,
              "n_b": 1
            },
            "13": {
              "distance": 0.2358,
              "n_a": 2,
              "n_b": 1
            }
          },
          "openai/gpt-5 \u2194 openai/gpt-5.6": {
            "0": {
              "distance": 0.1455,
              "n_a": 7,
              "n_b": 16
            },
            "1": {
              "distance": 0.0927,
              "n_a": 7,
              "n_b": 15
            },
            "2": {
              "distance": 0.0814,
              "n_a": 6,
              "n_b": 14
            },
            "3": {
              "distance": 0.0663,
              "n_a": 6,
              "n_b": 13
            },
            "4": {
              "distance": 0.0555,
              "n_a": 6,
              "n_b": 13
            },
            "5": {
              "distance": 0.0437,
              "n_a": 6,
              "n_b": 13
            },
            "6": {
              "distance": 0.0618,
              "n_a": 5,
              "n_b": 13
            },
            "7": {
              "distance": 0.0793,
              "n_a": 5,
              "n_b": 13
            },
            "8": {
              "distance": 0.1225,
              "n_a": 4,
              "n_b": 12
            },
            "9": {
              "distance": 0.1175,
              "n_a": 4,
              "n_b": 8
            },
            "10": {
              "distance": 0.1317,
              "n_a": 4,
              "n_b": 5
            },
            "11": {
              "distance": 0.125,
              "n_a": 3,
              "n_b": 2
            },
            "12": {
              "distance": 0.175,
              "n_a": 2,
              "n_b": 1
            },
            "13": {
              "distance": 0.2315,
              "n_a": 2,
              "n_b": 1
            },
            "14": {
              "distance": 0.2302,
              "n_a": 2,
              "n_b": 1
            },
            "15": {
              "distance": 0.24,
              "n_a": 2,
              "n_b": 1
            },
            "16": {
              "distance": 0.2072,
              "n_a": 2,
              "n_b": 1
            }
          },
          "openai/gpt-5 \u2194 openai/gpt-5.6-fast": {
            "0": {
              "distance": 0.1175,
              "n_a": 7,
              "n_b": 9
            },
            "1": {
              "distance": 0.0955,
              "n_a": 7,
              "n_b": 8
            },
            "2": {
              "distance": 0.0692,
              "n_a": 6,
              "n_b": 8
            },
            "3": {
              "distance": 0.0689,
              "n_a": 6,
              "n_b": 8
            },
            "4": {
              "distance": 0.0571,
              "n_a": 6,
              "n_b": 8
            },
            "5": {
              "distance": 0.0655,
              "n_a": 6,
              "n_b": 7
            },
            "6": {
              "distance": 0.0656,
              "n_a": 5,
              "n_b": 7
            },
            "7": {
              "distance": 0.0957,
              "n_a": 5,
              "n_b": 5
            },
            "8": {
              "distance": 0.1096,
              "n_a": 4,
              "n_b": 4
            },
            "9": {
              "distance": 0.1224,
              "n_a": 4,
              "n_b": 3
            },
            "10": {
              "distance": 0.1277,
              "n_a": 4,
              "n_b": 2
            },
            "11": {
              "distance": 0.1819,
              "n_a": 3,
              "n_b": 1
            },
            "12": {
              "distance": 0.1829,
              "n_a": 2,
              "n_b": 1
            }
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5-nano": {
            "0": {
              "distance": 0.0439,
              "n_a": 13,
              "n_b": 7
            },
            "1": {
              "distance": 0.0569,
              "n_a": 13,
              "n_b": 7
            },
            "2": {
              "distance": 0.0413,
              "n_a": 12,
              "n_b": 7
            },
            "3": {
              "distance": 0.0899,
              "n_a": 12,
              "n_b": 7
            },
            "4": {
              "distance": 0.0456,
              "n_a": 12,
              "n_b": 6
            },
            "5": {
              "distance": 0.0612,
              "n_a": 12,
              "n_b": 6
            },
            "6": {
              "distance": 0.0803,
              "n_a": 12,
              "n_b": 6
            },
            "7": {
              "distance": 0.1042,
              "n_a": 12,
              "n_b": 6
            },
            "8": {
              "distance": 0.0777,
              "n_a": 10,
              "n_b": 6
            },
            "9": {
              "distance": 0.1215,
              "n_a": 10,
              "n_b": 6
            },
            "10": {
              "distance": 0.0813,
              "n_a": 9,
              "n_b": 6
            },
            "11": {
              "distance": 0.0812,
              "n_a": 9,
              "n_b": 6
            },
            "12": {
              "distance": 0.0704,
              "n_a": 8,
              "n_b": 6
            },
            "13": {
              "distance": 0.0447,
              "n_a": 7,
              "n_b": 6
            },
            "14": {
              "distance": 0.0703,
              "n_a": 6,
              "n_b": 6
            },
            "15": {
              "distance": 0.0984,
              "n_a": 5,
              "n_b": 6
            },
            "16": {
              "distance": 0.2247,
              "n_a": 1,
              "n_b": 6
            },
            "17": {
              "distance": 0.2009,
              "n_a": 1,
              "n_b": 6
            },
            "18": {
              "distance": 0.1831,
              "n_a": 1,
              "n_b": 5
            },
            "19": {
              "distance": 0.1736,
              "n_a": 1,
              "n_b": 3
            },
            "20": {
              "distance": 0.1612,
              "n_a": 1,
              "n_b": 3
            },
            "21": {
              "distance": 0.1384,
              "n_a": 1,
              "n_b": 3
            },
            "22": {
              "distance": 0.2065,
              "n_a": 1,
              "n_b": 3
            },
            "23": {
              "distance": 0.2097,
              "n_a": 1,
              "n_b": 3
            },
            "24": {
              "distance": 0.214,
              "n_a": 1,
              "n_b": 3
            },
            "25": {
              "distance": 0.2403,
              "n_a": 1,
              "n_b": 2
            },
            "26": {
              "distance": 0.2845,
              "n_a": 1,
              "n_b": 1
            },
            "27": {
              "distance": 0.2552,
              "n_a": 1,
              "n_b": 1
            }
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.5": {
            "0": {
              "distance": 0.0657,
              "n_a": 13,
              "n_b": 6
            },
            "1": {
              "distance": 0.0772,
              "n_a": 13,
              "n_b": 4
            },
            "2": {
              "distance": 0.0882,
              "n_a": 12,
              "n_b": 4
            },
            "3": {
              "distance": 0.1009,
              "n_a": 12,
              "n_b": 4
            },
            "4": {
              "distance": 0.0655,
              "n_a": 12,
              "n_b": 4
            },
            "5": {
              "distance": 0.0884,
              "n_a": 12,
              "n_b": 4
            },
            "6": {
              "distance": 0.0498,
              "n_a": 12,
              "n_b": 3
            },
            "7": {
              "distance": 0.0871,
              "n_a": 12,
              "n_b": 3
            },
            "8": {
              "distance": 0.0951,
              "n_a": 10,
              "n_b": 3
            },
            "9": {
              "distance": 0.1516,
              "n_a": 10,
              "n_b": 2
            },
            "10": {
              "distance": 0.1826,
              "n_a": 9,
              "n_b": 1
            },
            "11": {
              "distance": 0.1975,
              "n_a": 9,
              "n_b": 1
            },
            "12": {
              "distance": 0.2279,
              "n_a": 8,
              "n_b": 1
            },
            "13": {
              "distance": 0.1398,
              "n_a": 7,
              "n_b": 1
            }
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.6": {
            "0": {
              "distance": 0.0779,
              "n_a": 13,
              "n_b": 16
            },
            "1": {
              "distance": 0.0586,
              "n_a": 13,
              "n_b": 15
            },
            "2": {
              "distance": 0.0686,
              "n_a": 12,
              "n_b": 14
            },
            "3": {
              "distance": 0.0627,
              "n_a": 12,
              "n_b": 13
            },
            "4": {
              "distance": 0.0381,
              "n_a": 12,
              "n_b": 13
            },
            "5": {
              "distance": 0.0442,
              "n_a": 12,
              "n_b": 13
            },
            "6": {
              "distance": 0.0838,
              "n_a": 12,
              "n_b": 13
            },
            "7": {
              "distance": 0.077,
              "n_a": 12,
              "n_b": 13
            },
            "8": {
              "distance": 0.1116,
              "n_a": 10,
              "n_b": 12
            },
            "9": {
              "distance": 0.1036,
              "n_a": 10,
              "n_b": 8
            },
            "10": {
              "distance": 0.1176,
              "n_a": 9,
              "n_b": 5
            },
            "11": {
              "distance": 0.1339,
              "n_a": 9,
              "n_b": 2
            },
            "12": {
              "distance": 0.1721,
              "n_a": 8,
              "n_b": 1
            },
            "13": {
              "distance": 0.1953,
              "n_a": 7,
              "n_b": 1
            },
            "14": {
              "distance": 0.1823,
              "n_a": 6,
              "n_b": 1
            },
            "15": {
              "distance": 0.2032,
              "n_a": 5,
              "n_b": 1
            },
            "16": {
              "distance": 0.2951,
              "n_a": 1,
              "n_b": 1
            }
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.6-fast": {
            "0": {
              "distance": 0.0703,
              "n_a": 13,
              "n_b": 9
            },
            "1": {
              "distance": 0.0608,
              "n_a": 13,
              "n_b": 8
            },
            "2": {
              "distance": 0.0432,
              "n_a": 12,
              "n_b": 8
            },
            "3": {
              "distance": 0.0673,
              "n_a": 12,
              "n_b": 8
            },
            "4": {
              "distance": 0.0492,
              "n_a": 12,
              "n_b": 8
            },
            "5": {
              "distance": 0.071,
              "n_a": 12,
              "n_b": 7
            },
            "6": {
              "distance": 0.0605,
              "n_a": 12,
              "n_b": 7
            },
            "7": {
              "distance": 0.094,
              "n_a": 12,
              "n_b": 5
            },
            "8": {
              "distance": 0.1112,
              "n_a": 10,
              "n_b": 4
            },
            "9": {
              "distance": 0.0998,
              "n_a": 10,
              "n_b": 3
            },
            "10": {
              "distance": 0.1219,
              "n_a": 9,
              "n_b": 2
            },
            "11": {
              "distance": 0.1637,
              "n_a": 9,
              "n_b": 1
            },
            "12": {
              "distance": 0.1806,
              "n_a": 8,
              "n_b": 1
            }
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.5": {
            "0": {
              "distance": 0.0636,
              "n_a": 7,
              "n_b": 6
            },
            "1": {
              "distance": 0.0905,
              "n_a": 7,
              "n_b": 4
            },
            "2": {
              "distance": 0.1173,
              "n_a": 7,
              "n_b": 4
            },
            "3": {
              "distance": 0.1209,
              "n_a": 7,
              "n_b": 4
            },
            "4": {
              "distance": 0.0774,
              "n_a": 6,
              "n_b": 4
            },
            "5": {
              "distance": 0.0882,
              "n_a": 6,
              "n_b": 4
            },
            "6": {
              "distance": 0.1166,
              "n_a": 6,
              "n_b": 3
            },
            "7": {
              "distance": 0.1656,
              "n_a": 6,
              "n_b": 3
            },
            "8": {
              "distance": 0.097,
              "n_a": 6,
              "n_b": 3
            },
            "9": {
              "distance": 0.0687,
              "n_a": 6,
              "n_b": 2
            },
            "10": {
              "distance": 0.1958,
              "n_a": 6,
              "n_b": 1
            },
            "11": {
              "distance": 0.1766,
              "n_a": 6,
              "n_b": 1
            },
            "12": {
              "distance": 0.2042,
              "n_a": 6,
              "n_b": 1
            },
            "13": {
              "distance": 0.1709,
              "n_a": 6,
              "n_b": 1
            }
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.6": {
            "0": {
              "distance": 0.1102,
              "n_a": 7,
              "n_b": 16
            },
            "1": {
              "distance": 0.079,
              "n_a": 7,
              "n_b": 15
            },
            "2": {
              "distance": 0.0772,
              "n_a": 7,
              "n_b": 14
            },
            "3": {
              "distance": 0.1121,
              "n_a": 7,
              "n_b": 13
            },
            "4": {
              "distance": 0.0525,
              "n_a": 6,
              "n_b": 13
            },
            "5": {
              "distance": 0.0548,
              "n_a": 6,
              "n_b": 13
            },
            "6": {
              "distance": 0.0819,
              "n_a": 6,
              "n_b": 13
            },
            "7": {
              "distance": 0.104,
              "n_a": 6,
              "n_b": 13
            },
            "8": {
              "distance": 0.0852,
              "n_a": 6,
              "n_b": 12
            },
            "9": {
              "distance": 0.0668,
              "n_a": 6,
              "n_b": 8
            },
            "10": {
              "distance": 0.0737,
              "n_a": 6,
              "n_b": 5
            },
            "11": {
              "distance": 0.0978,
              "n_a": 6,
              "n_b": 2
            },
            "12": {
              "distance": 0.1444,
              "n_a": 6,
              "n_b": 1
            },
            "13": {
              "distance": 0.2103,
              "n_a": 6,
              "n_b": 1
            },
            "14": {
              "distance": 0.1787,
              "n_a": 6,
              "n_b": 1
            },
            "15": {
              "distance": 0.2127,
              "n_a": 6,
              "n_b": 1
            },
            "16": {
              "distance": 0.1939,
              "n_a": 6,
              "n_b": 1
            }
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.6-fast": {
            "0": {
              "distance": 0.0875,
              "n_a": 7,
              "n_b": 9
            },
            "1": {
              "distance": 0.0711,
              "n_a": 7,
              "n_b": 8
            },
            "2": {
              "distance": 0.0626,
              "n_a": 7,
              "n_b": 8
            },
            "3": {
              "distance": 0.0928,
              "n_a": 7,
              "n_b": 8
            },
            "4": {
              "distance": 0.0594,
              "n_a": 6,
              "n_b": 8
            },
            "5": {
              "distance": 0.0765,
              "n_a": 6,
              "n_b": 7
            },
            "6": {
              "distance": 0.071,
              "n_a": 6,
              "n_b": 7
            },
            "7": {
              "distance": 0.1058,
              "n_a": 6,
              "n_b": 5
            },
            "8": {
              "distance": 0.0826,
              "n_a": 6,
              "n_b": 4
            },
            "9": {
              "distance": 0.0719,
              "n_a": 6,
              "n_b": 3
            },
            "10": {
              "distance": 0.1112,
              "n_a": 6,
              "n_b": 2
            },
            "11": {
              "distance": 0.1589,
              "n_a": 6,
              "n_b": 1
            },
            "12": {
              "distance": 0.1928,
              "n_a": 6,
              "n_b": 1
            }
          },
          "openai/gpt-5.5 \u2194 openai/gpt-5.6": {
            "0": {
              "distance": 0.052,
              "n_a": 6,
              "n_b": 16
            },
            "1": {
              "distance": 0.068,
              "n_a": 4,
              "n_b": 15
            },
            "2": {
              "distance": 0.0521,
              "n_a": 4,
              "n_b": 14
            },
            "3": {
              "distance": 0.0681,
              "n_a": 4,
              "n_b": 13
            },
            "4": {
              "distance": 0.0417,
              "n_a": 4,
              "n_b": 13
            },
            "5": {
              "distance": 0.0664,
              "n_a": 4,
              "n_b": 13
            },
            "6": {
              "distance": 0.0901,
              "n_a": 3,
              "n_b": 13
            },
            "7": {
              "distance": 0.0711,
              "n_a": 3,
              "n_b": 13
            },
            "8": {
              "distance": 0.062,
              "n_a": 3,
              "n_b": 12
            },
            "9": {
              "distance": 0.0923,
              "n_a": 2,
              "n_b": 8
            },
            "10": {
              "distance": 0.1874,
              "n_a": 1,
              "n_b": 5
            },
            "11": {
              "distance": 0.2037,
              "n_a": 1,
              "n_b": 2
            },
            "12": {
              "distance": 0.1957,
              "n_a": 1,
              "n_b": 1
            },
            "13": {
              "distance": 0.2787,
              "n_a": 1,
              "n_b": 1
            }
          },
          "openai/gpt-5.5 \u2194 openai/gpt-5.6-fast": {
            "0": {
              "distance": 0.0259,
              "n_a": 6,
              "n_b": 9
            },
            "1": {
              "distance": 0.0597,
              "n_a": 4,
              "n_b": 8
            },
            "2": {
              "distance": 0.0548,
              "n_a": 4,
              "n_b": 8
            },
            "3": {
              "distance": 0.0678,
              "n_a": 4,
              "n_b": 8
            },
            "4": {
              "distance": 0.062,
              "n_a": 4,
              "n_b": 8
            },
            "5": {
              "distance": 0.0929,
              "n_a": 4,
              "n_b": 7
            },
            "6": {
              "distance": 0.0738,
              "n_a": 3,
              "n_b": 7
            },
            "7": {
              "distance": 0.0841,
              "n_a": 3,
              "n_b": 5
            },
            "8": {
              "distance": 0.0862,
              "n_a": 3,
              "n_b": 4
            },
            "9": {
              "distance": 0.1028,
              "n_a": 2,
              "n_b": 3
            },
            "10": {
              "distance": 0.1751,
              "n_a": 1,
              "n_b": 2
            },
            "11": {
              "distance": 0.1255,
              "n_a": 1,
              "n_b": 1
            },
            "12": {
              "distance": 0.241,
              "n_a": 1,
              "n_b": 1
            }
          },
          "openai/gpt-5.6 \u2194 openai/gpt-5.6-fast": {
            "0": {
              "distance": 0.0285,
              "n_a": 16,
              "n_b": 9
            },
            "1": {
              "distance": 0.0241,
              "n_a": 15,
              "n_b": 8
            },
            "2": {
              "distance": 0.0355,
              "n_a": 14,
              "n_b": 8
            },
            "3": {
              "distance": 0.0426,
              "n_a": 13,
              "n_b": 8
            },
            "4": {
              "distance": 0.0294,
              "n_a": 13,
              "n_b": 8
            },
            "5": {
              "distance": 0.0402,
              "n_a": 13,
              "n_b": 7
            },
            "6": {
              "distance": 0.0492,
              "n_a": 13,
              "n_b": 7
            },
            "7": {
              "distance": 0.037,
              "n_a": 13,
              "n_b": 5
            },
            "8": {
              "distance": 0.0537,
              "n_a": 12,
              "n_b": 4
            },
            "9": {
              "distance": 0.0684,
              "n_a": 8,
              "n_b": 3
            },
            "10": {
              "distance": 0.0781,
              "n_a": 5,
              "n_b": 2
            },
            "11": {
              "distance": 0.1526,
              "n_a": 2,
              "n_b": 1
            },
            "12": {
              "distance": 0.2191,
              "n_a": 1,
              "n_b": 1
            }
          }
        }
      }
    },
    "step_clusters": {
      "meta": {
        "experiment_id": "lab_semantic_clusters",
        "total_step_embeddings": 2215,
        "pairwise_comparisons": 135505,
        "mean_distance": 0.228,
        "std_dev_distance": 0.0556,
        "method": "Step-level comparison: matching positions only (step N vs step N, different sessions)"
      },
      "data": {
        "closest_pairs": [
          {
            "step_a": "exp_1erxln69@12",
            "step_b": "exp_4f5g2wms@12",
            "session_a": "exp_1erxln69",
            "session_b": "exp_4f5g2wms",
            "step_index": 12,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_1gahysrh@0",
            "step_b": "exp_gbgylz6j@0",
            "session_a": "exp_1gahysrh",
            "session_b": "exp_gbgylz6j",
            "step_index": 0,
            "tool_a": "",
            "tool_b": "",
            "model_a": "openai/gpt-5.6-fast",
            "model_b": "openai/gpt-5.5",
            "distance": 0.0
          },
          {
            "step_a": "exp_1gahysrh@0",
            "step_b": "exp_kr8u4k9e@0",
            "session_a": "exp_1gahysrh",
            "session_b": "exp_kr8u4k9e",
            "step_index": 0,
            "tool_a": "",
            "tool_b": "",
            "model_a": "openai/gpt-5.6-fast",
            "model_b": "anthropic/claude-fable-5",
            "distance": 0.0
          },
          {
            "step_a": "exp_1gahysrh@0",
            "step_b": "exp_s3c_4qka@0",
            "session_a": "exp_1gahysrh",
            "session_b": "exp_s3c_4qka",
            "step_index": 0,
            "tool_a": "",
            "tool_b": "",
            "model_a": "openai/gpt-5.6-fast",
            "model_b": "openai/gpt-5.6",
            "distance": 0.0
          },
          {
            "step_a": "exp_34qst87v@7",
            "step_b": "exp_wkclt_vt@7",
            "session_a": "exp_34qst87v",
            "session_b": "exp_wkclt_vt",
            "step_index": 7,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_37z0nq68@8",
            "step_b": "exp_3zxicj_v@8",
            "session_a": "exp_37z0nq68",
            "session_b": "exp_3zxicj_v",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_37z0nq68@8",
            "step_b": "exp_fw57sbqz@8",
            "session_a": "exp_37z0nq68",
            "session_b": "exp_fw57sbqz",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_37z0nq68@8",
            "step_b": "exp_hn0qqsuf@8",
            "session_a": "exp_37z0nq68",
            "session_b": "exp_hn0qqsuf",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_37z0nq68@8",
            "step_b": "exp_kg2a1_b0@8",
            "session_a": "exp_37z0nq68",
            "session_b": "exp_kg2a1_b0",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_37z0nq68@8",
            "step_b": "exp_ot4ttmtr@8",
            "session_a": "exp_37z0nq68",
            "session_b": "exp_ot4ttmtr",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_37z0nq68@8",
            "step_b": "exp_vx4gb129@8",
            "session_a": "exp_37z0nq68",
            "session_b": "exp_vx4gb129",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_3zxicj_v@8",
            "step_b": "exp_fw57sbqz@8",
            "session_a": "exp_3zxicj_v",
            "session_b": "exp_fw57sbqz",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_3zxicj_v@8",
            "step_b": "exp_hn0qqsuf@8",
            "session_a": "exp_3zxicj_v",
            "session_b": "exp_hn0qqsuf",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_3zxicj_v@8",
            "step_b": "exp_kg2a1_b0@8",
            "session_a": "exp_3zxicj_v",
            "session_b": "exp_kg2a1_b0",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_3zxicj_v@8",
            "step_b": "exp_ot4ttmtr@8",
            "session_a": "exp_3zxicj_v",
            "session_b": "exp_ot4ttmtr",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_3zxicj_v@8",
            "step_b": "exp_vx4gb129@8",
            "session_a": "exp_3zxicj_v",
            "session_b": "exp_vx4gb129",
            "step_index": 8,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_4f5g2wms@13",
            "step_b": "exp_m3c9h6l0@13",
            "session_a": "exp_4f5g2wms",
            "session_b": "exp_m3c9h6l0",
            "step_index": 13,
            "tool_a": "todowrite",
            "tool_b": "todowrite",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": -0.0
          },
          {
            "step_a": "exp_6462vbw3@2",
            "step_b": "exp_batch_task_manager_natural@2",
            "session_a": "exp_6462vbw3",
            "session_b": "exp_batch_task_manager_natural",
            "step_index": 2,
            "tool_a": "todowrite",
            "tool_b": "todowrite",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_6462vbw3@2",
            "step_b": "exp_eyt9cssv@2",
            "session_a": "exp_6462vbw3",
            "session_b": "exp_eyt9cssv",
            "step_index": 2,
            "tool_a": "todowrite",
            "tool_b": "todowrite",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          },
          {
            "step_a": "exp_6462vbw3@2",
            "step_b": "exp_zwdvkm4q@2",
            "session_a": "exp_6462vbw3",
            "session_b": "exp_zwdvkm4q",
            "step_index": 2,
            "tool_a": "todowrite",
            "tool_b": "todowrite",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.0
          }
        ],
        "farthest_pairs": [
          {
            "step_a": "exp_batch_search_kv_store_natural@6",
            "step_b": "exp_owxe4fim@6",
            "session_a": "exp_batch_search_kv_store_natural",
            "session_b": "exp_owxe4fim",
            "step_index": 6,
            "tool_a": "write",
            "tool_b": "bash",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5-mini",
            "distance": 0.3794
          },
          {
            "step_a": "exp_erp5e4d9@10",
            "step_b": "exp_ze0y99pc@10",
            "session_a": "exp_erp5e4d9",
            "session_b": "exp_ze0y99pc",
            "step_index": 10,
            "tool_a": "bash",
            "tool_b": "write",
            "model_a": "openai/gpt-5-mini",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3778
          },
          {
            "step_a": "exp_batch_batch_task_manager_baseline claude_fable@2",
            "step_b": "exp_dalqefiq@2",
            "session_a": "exp_batch_batch_task_manager_baseline claude_fable",
            "session_b": "exp_dalqefiq",
            "step_index": 2,
            "tool_a": "bash",
            "tool_b": "",
            "model_a": "anthropic/claude-fable-5",
            "model_b": "openai/gpt-5",
            "distance": 0.3763
          },
          {
            "step_a": "exp_rt6ocba2@1",
            "step_b": "exp_selbvg5r@1",
            "session_a": "exp_rt6ocba2",
            "session_b": "exp_selbvg5r",
            "step_index": 1,
            "tool_a": "",
            "tool_b": "grep",
            "model_a": "openai/gpt-5",
            "model_b": "openai/gpt-5.5",
            "distance": 0.3745
          },
          {
            "step_a": "exp_dm1gxwnd@3",
            "step_b": "exp_zfgdwu49@3",
            "session_a": "exp_dm1gxwnd",
            "session_b": "exp_zfgdwu49",
            "step_index": 3,
            "tool_a": "bash",
            "tool_b": "bash",
            "model_a": "openai/gpt-5.6-fast",
            "model_b": "",
            "distance": 0.3704
          },
          {
            "step_a": "exp_dalqefiq@10",
            "step_b": "exp_p31ut41o@10",
            "session_a": "exp_dalqefiq",
            "session_b": "exp_p31ut41o",
            "step_index": 10,
            "tool_a": "apply_patch",
            "tool_b": "edit",
            "model_a": "openai/gpt-5",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3697
          },
          {
            "step_a": "exp_x8g28_k8@10",
            "step_b": "exp_ze0y99pc@10",
            "session_a": "exp_x8g28_k8",
            "session_b": "exp_ze0y99pc",
            "step_index": 10,
            "tool_a": "bash",
            "tool_b": "write",
            "model_a": "openai/gpt-5-mini",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3695
          },
          {
            "step_a": "exp_ba8s0njl@6",
            "step_b": "exp_batch_search_kv_store_natural@6",
            "session_a": "exp_ba8s0njl",
            "session_b": "exp_batch_search_kv_store_natural",
            "step_index": 6,
            "tool_a": "bash",
            "tool_b": "write",
            "model_a": "openai/gpt-5-mini",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.369
          },
          {
            "step_a": "exp_batch_batch_task_manager_baseline gpt_5_mini@9",
            "step_b": "exp_p31ut41o@9",
            "session_a": "exp_batch_batch_task_manager_baseline gpt_5_mini",
            "session_b": "exp_p31ut41o",
            "step_index": 9,
            "tool_a": "bash",
            "tool_b": "write",
            "model_a": "openai/gpt-5-mini",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3686
          },
          {
            "step_a": "exp_azk0fzz7@2",
            "step_b": "exp_pyo2sck7@2",
            "session_a": "exp_azk0fzz7",
            "session_b": "exp_pyo2sck7",
            "step_index": 2,
            "tool_a": "bash",
            "tool_b": "glob",
            "model_a": "openai/gpt-5",
            "model_b": "",
            "distance": 0.3663
          }
        ],
        "outliers": [
          {
            "step_a": "exp_1ruzb3rc@21",
            "step_b": "exp_bvv94cn2@21",
            "session_a": "exp_1ruzb3rc",
            "session_b": "exp_bvv94cn2",
            "step_index": 21,
            "tool_a": "bash",
            "tool_b": "",
            "model_a": "openai/gpt-5-nano",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3392
          },
          {
            "step_a": "exp_82jg7qi3@6",
            "step_b": "exp_z13l8zhz@6",
            "session_a": "exp_82jg7qi3",
            "session_b": "exp_z13l8zhz",
            "step_index": 6,
            "tool_a": "bash",
            "tool_b": "bash",
            "model_a": "openai/gpt-5.6",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3393
          },
          {
            "step_a": "exp__3wx7dg4@5",
            "step_b": "exp_sweep_gpt_5_mini_fp@5",
            "session_a": "exp__3wx7dg4",
            "session_b": "exp_sweep_gpt_5_mini_fp",
            "step_index": 5,
            "tool_a": "",
            "tool_b": "bash",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5-mini",
            "distance": 0.3393
          },
          {
            "step_a": "exp_nxb87bod@6",
            "step_b": "exp_rz0gn48h@6",
            "session_a": "exp_nxb87bod",
            "session_b": "exp_rz0gn48h",
            "step_index": 6,
            "tool_a": "bash",
            "tool_b": "write",
            "model_a": "openai/gpt-5.6-fast",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3393
          },
          {
            "step_a": "exp_05ngi4l9@32",
            "step_b": "exp_2yyxp_8_@32",
            "session_a": "exp_05ngi4l9",
            "session_b": "exp_2yyxp_8_",
            "step_index": 32,
            "tool_a": "edit",
            "tool_b": "",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3394
          },
          {
            "step_a": "exp_1erxln69@13",
            "step_b": "exp_x5tqss1y@13",
            "session_a": "exp_1erxln69",
            "session_b": "exp_x5tqss1y",
            "step_index": 13,
            "tool_a": "bash",
            "tool_b": "bash",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3394
          },
          {
            "step_a": "exp_dalqefiq@1",
            "step_b": "exp_sweep_gpt_5_6_fp@1",
            "session_a": "exp_dalqefiq",
            "session_b": "exp_sweep_gpt_5_6_fp",
            "step_index": 1,
            "tool_a": "",
            "tool_b": "todowrite",
            "model_a": "openai/gpt-5",
            "model_b": "openai/gpt-5.6",
            "distance": 0.3394
          },
          {
            "step_a": "exp_dbzmm0qd@4",
            "step_b": "exp_wo07wfxb@4",
            "session_a": "exp_dbzmm0qd",
            "session_b": "exp_wo07wfxb",
            "step_index": 4,
            "tool_a": "write",
            "tool_b": "write",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3396
          },
          {
            "step_a": "exp_mn5mnvtw@1",
            "step_b": "exp_sweep_gpt_5_6_fp@1",
            "session_a": "exp_mn5mnvtw",
            "session_b": "exp_sweep_gpt_5_6_fp",
            "step_index": 1,
            "tool_a": "read",
            "tool_b": "todowrite",
            "model_a": "deepseek/deepseek-v4-pro",
            "model_b": "openai/gpt-5.6",
            "distance": 0.3396
          },
          {
            "step_a": "exp_rt6ocba2@9",
            "step_b": "exp_rz0gn48h@9",
            "session_a": "exp_rt6ocba2",
            "session_b": "exp_rz0gn48h",
            "step_index": 9,
            "tool_a": "glob",
            "tool_b": "write",
            "model_a": "openai/gpt-5",
            "model_b": "deepseek/deepseek-v4-pro",
            "distance": 0.3396
          }
        ],
        "per_step_index": {
          "0": {
            "mean_distance": 0.2233,
            "std_dev": 0.0579,
            "count": 20706
          },
          "1": {
            "mean_distance": 0.2211,
            "std_dev": 0.0518,
            "count": 15931
          },
          "2": {
            "mean_distance": 0.2156,
            "std_dev": 0.0585,
            "count": 13203
          },
          "3": {
            "mean_distance": 0.2205,
            "std_dev": 0.0578,
            "count": 11935
          },
          "4": {
            "mean_distance": 0.2231,
            "std_dev": 0.0573,
            "count": 11026
          },
          "5": {
            "mean_distance": 0.2265,
            "std_dev": 0.0515,
            "count": 10440
          },
          "6": {
            "mean_distance": 0.2305,
            "std_dev": 0.0515,
            "count": 9870
          },
          "7": {
            "mean_distance": 0.2326,
            "std_dev": 0.0534,
            "count": 9180
          },
          "8": {
            "mean_distance": 0.2323,
            "std_dev": 0.0551,
            "count": 7750
          },
          "9": {
            "mean_distance": 0.2485,
            "std_dev": 0.05,
            "count": 5995
          },
          "10": {
            "mean_distance": 0.2369,
            "std_dev": 0.0541,
            "count": 4851
          },
          "11": {
            "mean_distance": 0.2418,
            "std_dev": 0.0509,
            "count": 3570
          },
          "12": {
            "mean_distance": 0.2406,
            "std_dev": 0.0594,
            "count": 2850
          },
          "13": {
            "mean_distance": 0.2453,
            "std_dev": 0.0525,
            "count": 2346
          },
          "14": {
            "mean_distance": 0.2507,
            "std_dev": 0.0506,
            "count": 1770
          },
          "15": {
            "mean_distance": 0.249,
            "std_dev": 0.0487,
            "count": 1326
          },
          "16": {
            "mean_distance": 0.2547,
            "std_dev": 0.0495,
            "count": 820
          },
          "17": {
            "mean_distance": 0.2489,
            "std_dev": 0.05,
            "count": 561
          },
          "18": {
            "mean_distance": 0.2473,
            "std_dev": 0.0484,
            "count": 465
          },
          "19": {
            "mean_distance": 0.2508,
            "std_dev": 0.0539,
            "count": 253
          },
          "20": {
            "mean_distance": 0.2656,
            "std_dev": 0.0407,
            "count": 171
          },
          "21": {
            "mean_distance": 0.2572,
            "std_dev": 0.0443,
            "count": 136
          },
          "22": {
            "mean_distance": 0.2622,
            "std_dev": 0.0271,
            "count": 91
          },
          "23": {
            "mean_distance": 0.2527,
            "std_dev": 0.0372,
            "count": 91
          },
          "24": {
            "mean_distance": 0.2564,
            "std_dev": 0.0307,
            "count": 55
          },
          "25": {
            "mean_distance": 0.2561,
            "std_dev": 0.0303,
            "count": 28
          },
          "26": {
            "mean_distance": 0.2785,
            "std_dev": 0.0368,
            "count": 21
          },
          "27": {
            "mean_distance": 0.2709,
            "std_dev": 0.0302,
            "count": 21
          },
          "28": {
            "mean_distance": 0.2795,
            "std_dev": 0.0222,
            "count": 15
          },
          "29": {
            "mean_distance": 0.2453,
            "std_dev": 0.0523,
            "count": 10
          },
          "30": {
            "mean_distance": 0.2657,
            "std_dev": 0.0416,
            "count": 6
          },
          "31": {
            "mean_distance": 0.2786,
            "std_dev": 0.0322,
            "count": 6
          },
          "32": {
            "mean_distance": 0.2935,
            "std_dev": 0.0389,
            "count": 3
          },
          "33": {
            "mean_distance": 0.2751,
            "std_dev": 0.01,
            "count": 3
          }
        },
        "cross_model": {
          "anthropic/claude-fable-5 \u2194 deepseek/deepseek-v4-pro": {
            "mean_distance": 0.2409,
            "count": 7521
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5": {
            "mean_distance": 0.2582,
            "count": 511
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5-mini": {
            "mean_distance": 0.2506,
            "count": 961
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5-nano": {
            "mean_distance": 0.2557,
            "count": 525
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.5": {
            "mean_distance": 0.2519,
            "count": 378
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.6": {
            "mean_distance": 0.254,
            "count": 1146
          },
          "anthropic/claude-fable-5 \u2194 openai/gpt-5.6-fast": {
            "mean_distance": 0.2485,
            "count": 639
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5": {
            "mean_distance": 0.2527,
            "count": 6359
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5-mini": {
            "mean_distance": 0.2558,
            "count": 13803
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5-nano": {
            "mean_distance": 0.2528,
            "count": 8688
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.5": {
            "mean_distance": 0.2464,
            "count": 3777
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.6": {
            "mean_distance": 0.2553,
            "count": 13047
          },
          "deepseek/deepseek-v4-pro \u2194 openai/gpt-5.6-fast": {
            "mean_distance": 0.2502,
            "count": 6685
          },
          "openai/gpt-5 \u2194 openai/gpt-5-mini": {
            "mean_distance": 0.227,
            "count": 794
          },
          "openai/gpt-5 \u2194 openai/gpt-5-nano": {
            "mean_distance": 0.2306,
            "count": 490
          },
          "openai/gpt-5 \u2194 openai/gpt-5.5": {
            "mean_distance": 0.2351,
            "count": 227
          },
          "openai/gpt-5 \u2194 openai/gpt-5.6": {
            "mean_distance": 0.2453,
            "count": 781
          },
          "openai/gpt-5 \u2194 openai/gpt-5.6-fast": {
            "mean_distance": 0.2364,
            "count": 406
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5-nano": {
            "mean_distance": 0.2295,
            "count": 1061
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.5": {
            "mean_distance": 0.2229,
            "count": 477
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.6": {
            "mean_distance": 0.235,
            "count": 1641
          },
          "openai/gpt-5-mini \u2194 openai/gpt-5.6-fast": {
            "mean_distance": 0.225,
            "count": 842
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.5": {
            "mean_distance": 0.2313,
            "count": 264
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.6": {
            "mean_distance": 0.2406,
            "count": 910
          },
          "openai/gpt-5-nano \u2194 openai/gpt-5.6-fast": {
            "mean_distance": 0.2307,
            "count": 459
          },
          "openai/gpt-5.5 \u2194 openai/gpt-5.6": {
            "mean_distance": 0.2147,
            "count": 507
          },
          "openai/gpt-5.5 \u2194 openai/gpt-5.6-fast": {
            "mean_distance": 0.2065,
            "count": 268
          },
          "openai/gpt-5.6 \u2194 openai/gpt-5.6-fast": {
            "mean_distance": 0.2114,
            "count": 916
          }
        },
        "by_tool_pair": {
          "bash \u00d7 write": {
            "mean_distance": 0.2375,
            "count": 14697
          },
          "write \u00d7 write": {
            "mean_distance": 0.2009,
            "count": 10410
          },
          "todowrite \u00d7 write": {
            "mean_distance": 0.2086,
            "count": 9502
          },
          "bash \u00d7 todowrite": {
            "mean_distance": 0.2253,
            "count": 8974
          },
          "bash \u00d7 bash": {
            "mean_distance": 0.2293,
            "count": 6583
          },
          "todowrite \u00d7 todowrite": {
            "mean_distance": 0.1747,
            "count": 4348
          },
          "read \u00d7 todowrite": {
            "mean_distance": 0.2226,
            "count": 2785
          },
          "apply_patch \u00d7 write": {
            "mean_distance": 0.26,
            "count": 2544
          },
          "bash \u00d7 read": {
            "mean_distance": 0.2339,
            "count": 2423
          },
          "read \u00d7 write": {
            "mean_distance": 0.2547,
            "count": 1704
          },
          "apply_patch \u00d7 bash": {
            "mean_distance": 0.2551,
            "count": 1635
          },
          "glob \u00d7 todowrite": {
            "mean_distance": 0.2372,
            "count": 1618
          },
          "bash \u00d7 glob": {
            "mean_distance": 0.2323,
            "count": 993
          },
          "apply_patch \u00d7 todowrite": {
            "mean_distance": 0.2526,
            "count": 988
          },
          "read \u00d7 read": {
            "mean_distance": 0.1583,
            "count": 920
          },
          "edit \u00d7 write": {
            "mean_distance": 0.2336,
            "count": 827
          },
          "bash \u00d7 edit": {
            "mean_distance": 0.256,
            "count": 706
          },
          "glob \u00d7 write": {
            "mean_distance": 0.2603,
            "count": 509
          },
          "glob \u00d7 read": {
            "mean_distance": 0.1951,
            "count": 460
          },
          "edit \u00d7 todowrite": {
            "mean_distance": 0.235,
            "count": 368
          },
          "glob \u00d7 glob": {
            "mean_distance": 0.2059,
            "count": 245
          },
          "apply_patch \u00d7 apply_patch": {
            "mean_distance": 0.2186,
            "count": 158
          },
          "apply_patch \u00d7 read": {
            "mean_distance": 0.2674,
            "count": 152
          },
          "edit \u00d7 read": {
            "mean_distance": 0.251,
            "count": 118
          },
          "apply_patch \u00d7 edit": {
            "mean_distance": 0.267,
            "count": 104
          },
          "grep \u00d7 todowrite": {
            "mean_distance": 0.2847,
            "count": 87
          },
          "grep \u00d7 read": {
            "mean_distance": 0.2825,
            "count": 84
          },
          "bash \u00d7 grep": {
            "mean_distance": 0.2654,
            "count": 73
          },
          "edit \u00d7 edit": {
            "mean_distance": 0.2487,
            "count": 35
          },
          "grep \u00d7 write": {
            "mean_distance": 0.2834,
            "count": 35
          },
          "edit \u00d7 glob": {
            "mean_distance": 0.2623,
            "count": 30
          },
          "apply_patch \u00d7 glob": {
            "mean_distance": 0.2733,
            "count": 18
          },
          "glob \u00d7 grep": {
            "mean_distance": 0.2684,
            "count": 10
          },
          "edit \u00d7 grep": {
            "mean_distance": 0.2973,
            "count": 6
          },
          "apply_patch \u00d7 grep": {
            "mean_distance": 0.2671,
            "count": 2
          },
          "grep \u00d7 grep": {
            "mean_distance": 0.1334,
            "count": 1
          }
        }
      }
    },
    "embedding_model": "bge-m3:latest",
    "embedding_dim": 1024,
    "indexed_steps": 2215,
    "sessions_indexed": 0
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
