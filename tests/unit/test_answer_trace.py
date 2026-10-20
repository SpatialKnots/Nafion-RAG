"""Native final-answer bridge counterexamples; network calls are synthetic."""
import json
from dataclasses import asdict

import pytest

from app.evaluation import answer_trace as trace
from app.generation.providers import Evidence, GenerationOutputError


def evidence():
    return [Evidence(citation_id="E1", article_id="synthetic-article", chunk_id="synthetic-chunk", title="Synthetic paper", doi=None,
        page_start=1, page_end=1, source_type="body", text="Conductivity 1 S/cm.\nExact stored text.", score=1,
        retrieval_method="synthetic", method_scores={}, method_ranks={})]


def native(content=None, status="completed"):
    return {"status": status, "model": "synthetic", "usage": {"output_tokens": 10}, "output": [
        {"type": "message", "role": "assistant", "status": "completed", "content": [
            {"type": "output_text", "text": json.dumps(content or {"answerable": True,
                "claims": [{"text": "Reported conductivity.", "citation_ids": ["E1"]}]})}]}]}


def prepare():
    provider = trace.TraceResponsesProvider(model="synthetic", api_key="synthetic-key")
    with pytest.raises(trace.PreparationComplete):
        provider.generate("Synthetic question", evidence())
    return provider.prepared_request


def test_dry_preparation_is_not_model_refusal_and_preserves_existing_prompt_formatter():
    payload = json.loads(prepare())
    assert payload["input"][0]["content"] == trace.SCIENTIFIC_ANSWER_SYSTEM_PROMPT
    assert "Conductivity 1 S/cm. Exact stored text." in payload["input"][1]["content"]
    assert "\nExact stored text." in asdict(evidence()[0])["text"]
    assert payload["store"] is False and payload["truncation"] == "disabled"
    assert "synthetic-key" not in json.dumps(payload)
    assert not {"tools", "temperature", "seed", "Authorization"} & payload.keys()


def test_changed_request_never_calls_network_or_creates_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "send_openai_request", lambda *a: pytest.fail("Changed request must not be sent"))
    provider = trace.TraceResponsesProvider(model="synthetic", api_key="synthetic-key", output=tmp_path / "run",
                                            expected_request=b"changed")
    with pytest.raises(ValueError, match="differs from frozen"):
        provider.generate("Synthetic question", evidence())
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("kind", ["valid", "incomplete", "refusal", "invalid_json", "no_claims", "timeout"])
def test_raw_native_artifacts_and_failures_are_preserved(tmp_path, monkeypatch, kind):
    response = native()
    if kind == "incomplete":
        response["status"] = "incomplete"
    if kind == "refusal":
        response["output"][0]["content"] = [{"type": "refusal", "refusal": "Synthetic refusal"}]
    if kind == "invalid_json":
        response["output"][0]["content"][0]["text"] = "invalid"
    if kind == "no_claims":
        response = native({"answerable": True, "claims": []})

    def send(*args):
        if kind == "timeout":
            raise TimeoutError("Synthetic timeout")
        return json.dumps(response).encode(), "synthetic-request-id"

    monkeypatch.setattr(trace, "send_openai_request", send)
    run = tmp_path / "run"
    provider = trace.TraceResponsesProvider(model="synthetic", api_key="synthetic-key", output=run, expected_request=prepare())
    if kind == "valid":
        result = provider.generate("Synthetic question", evidence())
        assert result.claims[0].citation_ids == ["E1"] and provider.result["status"] == "provider_valid"
    else:
        with pytest.raises((TimeoutError, ValueError, GenerationOutputError)):
            provider.generate("Synthetic question", evidence())
        assert provider.result["status"] == "failed" and not (run / "reply.json").exists()
    assert (run / "response.json").exists() == (kind != "timeout")
    assert json.loads((run / "provider_result.json").read_bytes())["status"] == provider.result["status"]
    assert all(b"synthetic-key" not in path.read_bytes() for path in run.iterdir())
