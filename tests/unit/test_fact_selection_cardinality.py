"""Observed duplicate-ID regressions and multi-ID/abstention schema boundaries."""

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

from app.generation import answer_facts
from app.generation.gigachat import GigaChatAnswerProvider, _Answer
from app.generation.providers import GenerationOutputError
from app.generation.quantitative_facts import prepare
from tests.unit.test_answer_facts import bundle as multi_bundle
from tests.unit.test_quantitative_facts import RANGE_Q, REF, source

DUPLICATES = json.loads((Path(__file__).resolve().parents[1] / "fixtures/duplicate_fact_selections_v01.json").read_bytes())["cases"]


def capture(evidence, response):
    provider = GigaChatAnswerProvider(credentials="synthetic", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                      timeout_seconds=1, max_tokens=1200)
    calls, requests = [], []

    def post(url, body, authorization, *, oauth=False):
        calls.append("oauth" if oauth else "model")
        if oauth:
            return b'{"access_token":"synthetic"}'
        requests.append(json.loads(body))
        return json.dumps(response).encode()

    provider._post = post
    result, error = None, None
    try:
        result = provider.generate(RANGE_Q, evidence, answer_language="ru")
    except GenerationOutputError as exc:
        error = exc
    assert calls == ["oauth", "model"] and len(requests) == 1
    return requests[0]["response_format"]["schema"], result, error


def envelope(claims, answerable=True):
    return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
            "content": json.dumps({"answerable": answerable, "claims": claims})}}]}


@pytest.mark.parametrize("saved", DUPLICATES, ids=lambda r: r["id"])
def test_all_seven_actual_duplicate_outputs_fail_native_schema_and_unchanged_local_validator(saved):
    original = deepcopy(saved["response"])
    content = json.loads(original["choices"][0]["message"]["content"])
    citation, = content["claims"][0]["citation_ids"]
    bounded = prepare(RANGE_Q, [source(citation_id=citation)], REF)
    schema, result, error = capture(bounded.evidence, original)
    assert result is None and error is not None
    assert schema["properties"]["claims"]["maxItems"] == 1
    assert schema["properties"]["claims"]["uniqueItems"] is True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(content, schema)
    assert original == saved["response"]


@pytest.mark.parametrize("kind", ["single", "multiple"])
@pytest.mark.parametrize("abstain", [False, True])
def test_valid_complete_selections_and_empty_abstention_survive_for_single_and_multiple_ids(kind, abstain):
    bounded = prepare(RANGE_Q, [source()], REF) if kind == "single" else multi_bundle("composition")
    records = answer_facts.selection_records(bounded.evidence)
    claims = [] if abstain else [{"text": key, "citation_ids": [record["citation_id"]]} for key, record in records.items()]
    schema, result, error = capture(bounded.evidence, envelope(claims, not abstain))
    jsonschema.validate({"answerable": not abstain, "claims": claims}, schema)
    assert error is None and result.answerable is not abstain
    assert schema["properties"]["claims"]["maxItems"] == len(records)
    citation_schema = schema["$defs"]["_Claim"]["properties"]["citation_ids"]
    assert citation_schema["minItems"] == citation_schema["maxItems"] == 1
    assert "maxItems" not in _Answer.model_json_schema()["properties"]["claims"]


def test_partial_multi_id_selection_still_fails_local_complete_set_validation():
    bounded = multi_bundle("composition")
    key, record = next(iter(answer_facts.selection_records(bounded.evidence).items()))
    schema, result, error = capture(bounded.evidence, envelope([{"text": key, "citation_ids": [record["citation_id"]]}]))
    assert schema["properties"]["claims"]["maxItems"] > 1
    assert result is None and error is not None


@pytest.mark.parametrize("claims", [[{"text": "F1", "citation_ids": ["E999"]}],
                                   [{"text": "invented prose", "citation_ids": ["E1"]}],
                                   [{"text": "F1", "citation_ids": ["E1", "E1"]}]])
def test_wrong_citation_prose_and_multi_citation_remain_rejected(claims):
    bounded = prepare(RANGE_Q, [source()], REF)
    schema, result, error = capture(bounded.evidence, envelope(claims))
    assert result is None and error is not None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"answerable": True, "claims": claims}, schema)


def test_free_text_path_keeps_its_existing_schema():
    claims = [{"text": "Constructed statement.", "citation_ids": ["E1"]}]
    schema, result, error = capture([source("Constructed statement.")], envelope(claims))
    assert error is None and result.answerable
    assert "maxItems" not in schema["properties"]["claims"]
    assert "uniqueItems" not in schema["properties"]["claims"]
