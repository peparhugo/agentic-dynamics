"""Tests for the Claude CLI → opencode event adapter."""

import json

from agentic_dynamics.adapters import claude_adapter as module_under_test
from agentic_dynamics.adapters.claude_adapter import (
    ClaudeStreamAdapter,
    _claude_model_arg,
    _resolve_claude_bin,
    _resolve_claude_model,
    adapt_usage,
    run_claude_agentic,
)

FAKE_CLAUDE = """#!/usr/bin/env python3
lines = [
    '{"type":"system","subtype":"init","session_id":"s1"}',
    '{"type":"assistant","message":{"content":[{"type":"text","text":"Hello"}]}}',
    '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1","name":"Bash","input":{"command":"ls"}}]}}',
    '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"ok","is_error":false}]}}',
    '{"type":"result","subtype":"success","is_error":false,"total_cost_usd":0.01,'
    '"usage":{"input_tokens":10,"output_tokens":5,'
    '"cache_read_input_tokens":2,"cache_creation_input_tokens":3}}',
]
for l in lines:
    print(l)
"""


def test_adapt_usage_maps_fields():
    usage = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 20,
        "cache_creation_input_tokens": 30,
    }
    out = adapt_usage(usage, 0.42)
    assert out["tokens"]["input"] == 100
    assert out["tokens"]["output"] == 50
    assert out["tokens"]["reasoning"] == 0
    assert out["tokens"]["total"] == 150
    assert out["tokens"]["cache"] == {"read": 20, "write": 30}
    assert out["cost"] == 0.42


def test_adapt_usage_handles_missing_fields():
    out = adapt_usage(None, 0.0)
    assert out["tokens"]["input"] == 0
    assert out["tokens"]["output"] == 0
    assert out["cost"] == 0.0


def test_resolve_claude_bin_uses_path_lookup():
    assert _resolve_claude_bin(find_executable=lambda name: "/usr/local/bin/claude") == (
        "/usr/local/bin/claude"
    )


def test_resolve_claude_bin_honors_explicit_override():
    assert _resolve_claude_bin(configured="/custom/claude") == "/custom/claude"


def test_resolve_claude_bin_falls_back_to_command_name_when_path_is_missing():
    assert _resolve_claude_bin(find_executable=lambda name: None) == "claude"


def test_adapter_full_sequence():
    adapter = ClaudeStreamAdapter()
    events = []

    events += adapter.feed({"type": "system", "subtype": "init"})
    assert events[0]["type"] == "step_start"

    text_events = adapter.feed(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hi"}]}}
    )
    assert text_events == [{"type": "text", "part": {"type": "text", "text": "Hi"}}]

    # tool_use is buffered, not emitted
    pending = adapter.feed(
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"cmd": "ls"}}]
            },
        }
    )
    assert pending == []

    # tool_result flushes a single completed tool_use
    done = adapter.feed(
        {
            "type": "user",
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok", "is_error": False}]
            },
        }
    )
    assert len(done) == 1
    assert done[0]["type"] == "tool_use"
    assert done[0]["part"]["tool"] == "Bash"
    assert done[0]["part"]["state"]["status"] == "completed"

    # result emits step_finish with adapted tokens
    result = adapter.feed(
        {
            "type": "result",
            "subtype": "success",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
    )
    assert result[0]["type"] == "step_finish"
    assert result[0]["part"]["tokens"]["input"] == 10
    assert result[0]["part"]["cost"] == 0.01


def test_adapter_reasoning_emitted_as_reasoning():
    adapter = ClaudeStreamAdapter()
    events = adapter.feed(
        {
            "type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": "planning..."}]},
        }
    )
    assert events == [{"type": "reasoning", "part": {"type": "reasoning", "text": "planning..."}}]


def test_model_resolution_passes_real_ids_through():
    assert _resolve_claude_model("anthropic/claude-sonnet-4-5") == "claude-sonnet-4-5"
    assert _resolve_claude_model("anthropic/claude-opus-4-5") == "claude-opus-4-5"
    assert _resolve_claude_model("anthropic/sonnet") == "sonnet"
    assert _resolve_claude_model("anthropic/opus") == "opus"
    assert _resolve_claude_model("anthropic/haiku") == "haiku"
    assert _resolve_claude_model("anthropic/fable") == "fable"


def test_model_resolution_passes_claude5_ids_through():
    assert _resolve_claude_model("anthropic/claude-sonnet-5") == "claude-sonnet-5"
    assert _resolve_claude_model("anthropic/claude-fable-5") == "claude-fable-5"


def test_model_resolution_unknown_passthrough():
    assert _resolve_claude_model("anthropic/claude-future-model") == "claude-future-model"


def test_model_resolution_empty():
    assert _resolve_claude_model("") == ""
    assert _resolve_claude_model("anthropic") == ""
    assert _claude_model_arg("") == []
    assert _claude_model_arg("anthropic") == []


def test_claude_model_arg_builds_flag():
    assert _claude_model_arg("anthropic/claude-sonnet-4-5") == ["--model", "claude-sonnet-4-5"]
    assert _claude_model_arg("anthropic/claude-fable-5") == ["--model", "claude-fable-5"]


def test_run_claude_agentic_honors_transcript_path(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude"
    script.write_text(FAKE_CLAUDE)
    script.chmod(0o755)
    monkeypatch.setattr(module_under_test, "CLAUDE_BIN", str(script))

    custom = tmp_path / "nested" / "session_2.jsonl"
    result = run_claude_agentic(
        "do stuff", model="anthropic/claude-sonnet-4-5",
        init_git=False, timeout=30, transcript_path=str(custom),
    )
    assert custom.exists()
    first = json.loads(custom.read_text().splitlines()[0])
    assert first["type"] == "step_start"
    assert result.raw_transcript


def test_run_claude_agentic_end_to_end(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude"
    script.write_text(FAKE_CLAUDE)
    script.chmod(0o755)
    monkeypatch.setattr(module_under_test, "CLAUDE_BIN", str(script))

    result = run_claude_agentic(
        "do stuff", model="anthropic/claude-sonnet-4-5", init_git=False, timeout=30
    )

    assert result.total_tool_calls == 1
    assert result.tool_calls[0]["tool"] == "Bash"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.cache_read_tokens == 2
    assert result.cache_write_tokens == 3
    assert result.estimated_cost_usd == 0.01
    assert "Hello" in result.final_response

    transcript = result.raw_transcript.splitlines()
    assert json.loads(transcript[0])["type"] == "step_start"
    assert json.loads(transcript[-1])["type"] == "step_finish"
