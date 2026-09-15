"""Unit B regression: every maintained direct worker call selects build EXPLICITLY.

The project default (``opencode.json``'s ``default_agent``) is the AIO coordinator; a call
that rides the default silently becomes a coordinator. These tests capture the ACTUAL
subprocess argv / SDK request with execution mocked — no model calls, no opencode process.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.fast


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(
        f"script_under_test_{name}", ROOT / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _agent_value(args: list[str]) -> str:
    assert "--agent" in args, f"no explicit --agent in {args!r}"
    return args[args.index("--agent") + 1]


def test_project_default_is_the_aio_coordinator():
    """The default this pinning must beat is configured — the premise of every test below."""
    config = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert config.get("default_agent") == "aio-control"


def test_mutation_generation_captures_the_argv_with_build_pinned(monkeypatch):
    from agentic_dynamics.measurement import mutation

    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = list(args)
        return SimpleNamespace(stdout="mutated text\n", returncode=0, stderr="")

    monkeypatch.setattr(mutation.subprocess, "run", fake_run)
    out = mutation._call_opencode("prompt", model="deepseek/deepseek-v4-flash", timeout=5)
    assert _agent_value(seen["args"]) == "build"
    assert out == "mutated text"


def test_review_call_captures_the_argv_with_build_pinned(monkeypatch):
    from agentic_dynamics.reporting import review

    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = list(args)
        return SimpleNamespace(stdout="", returncode=0, stderr="")

    monkeypatch.setattr(review.subprocess, "run", fake_run)
    review._call_agent("review this", "deepseek/deepseek-v4-flash", timeout=5)
    assert _agent_value(seen["args"]) == "build"


def test_story_timeout_continuation_pins_build():
    from agentic_dynamics.runtime.story.orchestration import _continuation_cmd

    args = _continuation_cmd(
        "/bin/opencode", "ses_abc", Path("/tmp/wt"), "deepseek/deepseek-v4-flash"
    )
    assert _agent_value(args) == "build"
    assert args[args.index("--session") + 1] == "ses_abc"
    assert "--fork" in args
    assert args[args.index("--dir") + 1] == "/tmp/wt"


@pytest.mark.parametrize("script", ["sweep_parallel", "remaining_batch", "batch_run"])
def test_sweep_and_batch_entry_points_pin_build(script):
    """The Python sweep/batch drivers build their own argv — captured directly, no run."""
    module = _load_script(script)
    if script == "batch_run":
        args = module._opencode_cmd("title", "/tmp/wd", "prompt")
    else:
        args = module._opencode_cmd("deepseek/deepseek-v4-flash", "title", "/tmp/wd", "prompt")
    assert _agent_value(args) == "build"
    assert args[args.index("--dir") + 1] == "/tmp/wd"


def test_sdk_bridge_request_selects_build():
    """The bridge's actual prompt request (built through its own function) carries the pin;
    a specialized profile rides through when a caller selects one."""
    node = os.environ.get("NODE_BIN") or shutil.which("node")
    if not node:
        pytest.skip("node is not available in this environment")
    bridge = ROOT / "scripts" / "sdk_bridge.mjs"
    code = (
        "import(process.env.BRIDGE_PATH).then((m) => {"
        "  const base = m.buildPromptParams({sessionID: 'ses_t', providerID: 'deepseek',"
        "    modelID: 'deepseek-v4-flash', prompt: 'hi', schema: {type: 'object'}});"
        "  const specialized = m.buildPromptParams({sessionID: 'ses_t', providerID: 'deepseek',"
        "    modelID: 'deepseek-v4-flash', prompt: 'hi', agent: 'instrument-dev'});"
        "  console.log(JSON.stringify({base, specialized}));"
        "}).catch((e) => { console.error(e); process.exit(1); })"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", code],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "BRIDGE_PATH": str(bridge)},
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["base"]["agent"] == "build"
    assert payload["base"]["format"]["type"] == "json_schema"
    assert payload["base"]["parts"][0]["text"] == "hi"
    assert payload["specialized"]["agent"] == "instrument-dev"


def test_sweep_shell_caller_pins_build():
    text = (ROOT / "scripts" / "sweep_parallel.sh").read_text(encoding="utf-8")
    block = text[text.index("opencode run"):].split("\n\n", 1)[0]
    assert "--agent build" in block
