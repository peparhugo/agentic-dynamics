"""Tests for backend dispatch."""

from agentic_dynamics.adapters.backends import get_backend_for_model, resolve_backend


def test_anthropic_routes_to_claude_cli():
    assert get_backend_for_model("anthropic/claude-sonnet-4-5") == "claude_cli"
    assert get_backend_for_model("anthropic/claude-opus-4-5") == "claude_cli"


def test_other_providers_route_to_opencode():
    assert get_backend_for_model("deepseek/deepseek-v4-pro") == "opencode"
    assert get_backend_for_model("openai/gpt-5.6-luna") == "opencode"


def test_env_override_forces_backend(monkeypatch):
    monkeypatch.setenv("DYNAMIC_CODE_BACKEND", "claude_cli")
    assert get_backend_for_model("deepseek/deepseek-v4-pro") == "claude_cli"
    monkeypatch.setenv("DYNAMIC_CODE_BACKEND", "opencode")
    assert get_backend_for_model("anthropic/claude-sonnet-4-5") == "opencode"


def test_resolve_backend_explicit_wins():
    assert resolve_backend("anthropic/claude-sonnet-4-5", "opencode") == "opencode"
    assert resolve_backend("deepseek/deepseek-v4-pro", "claude_cli") == "claude_cli"


def test_resolve_backend_auto_falls_through():
    assert resolve_backend("anthropic/claude-sonnet-4-5", "auto") == "claude_cli"
    assert resolve_backend("deepseek/deepseek-v4-pro", None) == "opencode"
