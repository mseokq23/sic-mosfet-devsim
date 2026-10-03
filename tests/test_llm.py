import json
import sys
import types
import pytest
from sicsim import llm

PAYLOAD = dict(round=1, seed=0, batch_size=2, model_summary={},
               candidates=[dict(candidate_id=f"C{i:04d}", predictive_uncertainty=0.1 * (i + 1), distance_to_train=0.2) for i in range(4)])


def _fake_anthropic(captured, text):
    class Messages:
        def create(self, **kw):
            captured.update(kw)
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)],
                                         usage=types.SimpleNamespace(input_tokens=123, output_tokens=45), stop_reason="end_turn")

    class Client:
        def __init__(self, api_key=None):
            captured["api_key"] = api_key
            self.messages = Messages()
    return types.SimpleNamespace(Anthropic=Client, __version__="fake")


def test_live_uses_named_secret_and_structured_output(monkeypatch):
    cap = {}
    text = json.dumps(dict(selected_ids=["C0003", "C0002"], reason_codes=["HIGH_UNCERTAINTY"], short_rationale="ok"))
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic(cap, text))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MSEOKQ_CLAUDE", "test-key")
    ids, rec = llm.select(PAYLOAD, [], {"dry_run": False, "model": "claude-sonnet-5-5"})
    assert ids == ["C0003", "C0002"] and rec["mode"] == "live" and rec["api_key_env"] == "MSEOKQ_CLAUDE"
    assert cap["api_key"] == "test-key" and cap["model"] == "claude-sonnet-5-5"
    assert cap["output_config"]["format"]["type"] == "json_schema"
    assert "test-key" not in json.dumps(rec)


def test_live_without_key_fails_loudly(monkeypatch):
    for n in llm.API_KEY_ENVS:
        monkeypatch.delenv(n, raising=False)
    with pytest.raises(llm.LLMUnavailable):
        llm.select(PAYLOAD, [], {"dry_run": False})


def test_invalid_live_response_is_rejected_and_logged(monkeypatch):
    cap = {}
    bad = json.dumps(dict(selected_ids=["X999", "C0001"], reason_codes=["DIVERSITY"], short_rationale="bad"))
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic(cap, bad))
    monkeypatch.setenv("MSEOKQ_CLAUDE", "k")
    ids, rec = llm.select(PAYLOAD, [], {"dry_run": False})
    assert ids is None and rec["validator_status"] == "rejected" and rec["reject_reason"].startswith("OUT_OF_LIST")


def test_dry_run_is_labelled():
    ids, rec = llm.select(PAYLOAD, [], {"dry_run": True})
    assert rec["mode"] == "dry-run" and rec["model_id"] == "dry-run" and len(ids) == 2
