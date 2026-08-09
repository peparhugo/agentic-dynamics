import pytest
from instrument.adapter import InstrumentedAdapter, InvokeTimeoutError
from instrument.trajectory import TrajectoryStep


class FakeResult:
    def __init__(self, text="test response", completion_tokens=42, estimated_cost_usd=0.001, prompt_tokens=100):
        self.text = text
        self.completion_tokens = completion_tokens
        self.estimated_cost_usd = estimated_cost_usd
        self.prompt_tokens = prompt_tokens


def fake_llm(prompt, model="", timeout=180):
    return FakeResult()


def test_invoke_returns_text_tokens_cost():
    adapter = InstrumentedAdapter(fake_llm, model="test-model")
    text, tokens, cost = adapter.invoke("test prompt", thought="test")
    assert text == "test response"
    assert tokens == 42
    assert cost == 0.001
    assert len(adapter._steps) == 1
    assert adapter._total_output_tokens == 42
    assert adapter._total_input_tokens == 100


def test_invoke_with_model_override():
    adapter = InstrumentedAdapter(fake_llm, model="default-model")
    text, tokens, cost = adapter.invoke("prompt", model="override-model", thought="test")
    assert text == "test response"


def test_get_trajectory():
    adapter = InstrumentedAdapter(fake_llm, model="traj-model")
    adapter.invoke("step 1", thought="think1")
    adapter.invoke("step 2", thought="think2")
    traj = adapter.get_trajectory(run_id="test-run")
    assert traj.run_id == "test-run"
    assert traj.model == "traj-model"
    assert traj.step_count() == 2


def test_invoke_with_dict_result():
    def fake_dict_llm(prompt, model="", timeout=180):
        return {"text": "dict response", "completion_tokens": 10, "estimated_cost_usd": 0.002, "prompt_tokens": 50}

    adapter = InstrumentedAdapter(fake_dict_llm, model="dict-model")
    text, tokens, cost = adapter.invoke("prompt", thought="dict")
    assert text == "dict response"
    assert tokens == 10
    assert cost == 0.002
