"""Run a reasoning topology experiment from a config file.

Usage:
    python scripts/run.py experiments/configs/baseline.yaml
    python scripts/run.py experiments/configs/comparative.yaml --model deepseek
"""

import argparse
import json
import os
import sys
import time
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument import (
    ExperimentConfig, run_experiment, build_operators, perturb_prompt,
    persist_to_lab_book,
)
from instrument.adapter import InstrumentedAdapter


def make_deepseek_invoke(key: str):
    """Build an invoke function for DeepSeek API."""
    def invoke(prompt, *, model="deepseek-v4-pro", timeout=60):
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.7},
            timeout=timeout + 15,
        )
        d = resp.json()
        tok = d.get("usage", {}).get("completion_tokens", 0) or 0
        reasoning_tok = d.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens", 0) or 0
        prompt_tok = d.get("usage", {}).get("prompt_tokens", 0) or 0
        total_tok = d.get("usage", {}).get("total_tokens", 0) or 0
        text = d["choices"][0]["message"]["content"] if d.get("choices") else ""
        # DeepSeek pricing: $0.27/M input, $1.10/M output, $0.14/M reasoning
        cost = (prompt_tok * 0.27 + tok * 1.10 + reasoning_tok * 0.14) / 1_000_000
        return type("Result", (), {
            "text": text, "completion_tokens": tok, "total_tokens": total_tok,
            "prompt_tokens": prompt_tok, "reasoning_tokens": reasoning_tok,
            "estimated_cost_usd": cost, "ok": resp.status_code == 200
        })
    return invoke


def make_codex_invoke():
    """Build an invoke function for Codex CLI."""
    import subprocess
    def invoke(prompt, *, model="gpt-5-mini", timeout=60):
        proc = subprocess.run(
            ["codex", "exec", "-m", model, prompt],
            capture_output=True, text=True, timeout=timeout + 15,
            cwd=os.getcwd(),
        )
        text = proc.stdout.strip()
        tok = len(text.split()) * 1.3  # rough token estimate
        return type("Result", (), {"text": text, "completion_tokens": int(tok), "total_tokens": int(tok), "estimated_cost_usd": 0, "ok": proc.returncode == 0})
    return invoke


INVOKE_BUILDERS = {
    "deepseek": lambda: make_deepseek_invoke(os.environ.get("DEEPSEEK_API_KEY", "")),
    "codex": make_codex_invoke,
}


def load_config(path: str) -> dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Run a reasoning topology experiment")
    parser.add_argument("config", help="Path to YAML experiment config")
    parser.add_argument("--model", help="Override model adapter")
    parser.add_argument("--model-id", help="Override model ID")
    parser.add_argument("--limit", type=int, help="Limit operators to first N")
    args = parser.parse_args()

    cfg = load_config(args.config)

    model_override = args.model or cfg["model"]
    model_id = args.model_id or cfg["model_id"]

    builder = INVOKE_BUILDERS.get(model_override)
    if not builder:
        print(f"Unknown model: {model_override}. Available: {list(INVOKE_BUILDERS)}")
        sys.exit(1)

    invoke_fn = builder()

    operators = cfg["operators"]
    if args.limit:
        operators = operators[:args.limit]

    config = ExperimentConfig(
        name=cfg["name"],
        task=cfg["task"].strip(),
        constraints=cfg.get("constraints", []),
        operators=operators,
        strengths=cfg["strengths"],
        model=cfg["model"],
        model_id=model_id,
        rng_seed=cfg.get("rng_seed", 42),
        repetitions=cfg.get("repetitions", 1),
        output_dir=Path("experiments/results"),
    )

    def llm_fn(prompt):
        result = invoke_fn(prompt, model=model_id, timeout=60)
        # Return the rich result object directly — experiment.py handles both tuples and objects
        return result

    print(f"Experiment: {config.name}")
    print(f"Model: {model_override}/{model_id}")
    print(f"Operators: {len(operators)}, Strengths: {config.strengths}")
    print(f"Task: {config.task[:80]}...")
    print()

    result = run_experiment(config, llm_fn, on_progress=print)

    print(result.summary())

    path = persist_to_lab_book(result)
    print(f"\nLab book: {path}")

    results_json = Path("experiments/results") / f"{config.name}_{model_override}.json"
    import json
    results_json.write_text(json.dumps(result.to_dict(), indent=2, default=str))
    print(f"Results: {results_json}")


if __name__ == "__main__":
    main()
