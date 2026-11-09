"""Constructed ID contracts: no scientific measurements or external calls."""

import hashlib
import json
from dataclasses import replace

import pytest

from app.generation.gigachat import GigaChatAnswerProvider
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.reference_quotes import SOURCE_TYPE, VERSION, resolve_selections, selection_choices, selection_records


def contract():
    result = []
    for i, (role, raw) in enumerate((("method", "Method: ﬁlm-\nforming at 25 °C; ΔH −12.3."),
                                      ("table", "Sample α\n0.123\n17%\na) source footnote.")), 1):
        record = {"selection_id": f"S{i}", "role": role, "citation_id": f"E{i}", "article_id": "article",
                  "chunk_id": f"chunk{i}", "raw_chunk_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                  "raw_span": {"start": 0, "end": len(raw), "text": raw},
                  "allowed_claim": f"Цитата источника ({role}):\n«{raw}»", "scientific_ownership_verified": False}
        result.append(Evidence(citation_id=f"E{i}", article_id="article", chunk_id=f"chunk{i}", title="Synthetic",
                               doi=None, page_start=i, page_end=i, source_type=SOURCE_TYPE,
                               text=json.dumps({"version": VERSION, "records": [record]}, ensure_ascii=False), score=0.0,
                               retrieval_method="constructed", method_scores={}, method_ranks={}))
    return result


def fake_client(evidence, claims, *, answerable=True):
    client = GigaChatAnswerProvider(credentials="offline-placeholder", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                   timeout_seconds=120, max_tokens=1200)
    calls, bodies = [], []

    def post(url, body, authorization, *, oauth=False):
        calls.append("simulated_oauth" if oauth else "simulated_model")
        if oauth:
            return b'{"access_token":"offline-placeholder"}'
        bodies.append(json.loads(body))
        return json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(
            {"answerable": answerable, "claims": claims}, ensure_ascii=False)}}]}).encode()

    client._post = post
    return client, calls, bodies


def test_ids_resolve_to_server_text_in_canonical_order_without_normalization():
    evidence = contract()
    before = [e.text for e in evidence]
    assert selection_choices(evidence) == {"E1": ["S1"], "E2": ["S2"]}
    selected = resolve_selections([GeneratedClaim("S2", ["E2"]), GeneratedClaim("S1", ["E1"])], evidence)
    records = selection_records(evidence)
    assert [c.text for c in selected] == [r["allowed_claim"] for r in records.values()]
    assert "ﬁlm-\nforming" in selected[0].text and "25 °C" in selected[0].text and "−12.3" in selected[0].text
    assert [e.text for e in evidence] == before


@pytest.mark.parametrize("bad", ["S0", "S3", "s1", "S01", "S١", "Ｓ1", "S1 ", " S1", "S1\n", "S1 extra", "\uababSTRACT"])
def test_unknown_or_noncanonical_ids_are_not_repaired(bad):
    with pytest.raises(GenerationOutputError):
        resolve_selections([GeneratedClaim(bad, ["E1"]), GeneratedClaim("S2", ["E2"])], contract())


@pytest.mark.parametrize("claims", [[], [GeneratedClaim("S1", ["E1"])],
                                    [GeneratedClaim("S1", ["E1"]), GeneratedClaim("S1", ["E1"])],
                                    [GeneratedClaim("S1", ["E2"]), GeneratedClaim("S2", ["E1"])],
                                    [GeneratedClaim("S1", ["E1", "E2"]), GeneratedClaim("S2", ["E2"])]])
def test_partial_duplicate_or_wrong_citation_selection_fails_atomically(claims):
    with pytest.raises(GenerationOutputError):
        resolve_selections(claims, contract())


def test_full_source_text_is_not_an_id():
    evidence = contract()
    record = next(iter(selection_records(evidence).values()))
    with pytest.raises(GenerationOutputError):
        resolve_selections([GeneratedClaim(record["allowed_claim"], ["E1"]), GeneratedClaim("S2", ["E2"])], evidence)


@pytest.mark.parametrize("change", ["version", "missing_id", "duplicate", "gap", "binding", "claim", "span"])
def test_invalid_contract_is_rejected_before_oauth(change):
    evidence = contract()
    payload = json.loads(evidence[0].text)
    record = payload["records"][0]
    if change == "version":
        payload["version"] = "old"
    elif change == "missing_id":
        record.pop("selection_id")
    elif change == "duplicate":
        record["selection_id"] = "S2"
    elif change == "gap":
        record["selection_id"] = "S9"
    elif change == "binding":
        record["citation_id"] = "other"
    elif change == "claim":
        record["allowed_claim"] = "Invented 999."
    else:
        record["raw_span"]["end"] += 1
    evidence[0] = replace(evidence[0], text=json.dumps(payload))
    client, calls, _ = fake_client(evidence, [])
    with pytest.raises(GenerationOutputError):
        client.generate("Constructed question", evidence)
    assert calls == []


def test_mixed_contract_cannot_enable_unrestricted_text():
    evidence = contract()
    evidence[1] = replace(evidence[1], source_type="body", text="Unrestricted source")
    with pytest.raises(GenerationOutputError, match="mix"):
        selection_records(evidence)


def test_actual_provider_schema_uses_ids_but_keeps_source_text_in_input():
    evidence = contract()
    client, calls, bodies = fake_client(evidence, [{"text": "S1", "citation_ids": ["E1"]}, {"text": "S2", "citation_ids": ["E2"]}])
    result = client.generate("Constructed question", evidence)
    assert [c.text for c in result.claims] == ["S1", "S2"]
    assert calls == ["simulated_oauth", "simulated_model"]
    native = bodies[0]
    assert native["response_format"]["schema"]["$defs"]["_Claim"]["properties"]["text"]["enum"] == ["S1", "S2"]
    assert "ﬁlm-\\nforming" in native["messages"][1]["content"]
    assert "Do not copy" in native["messages"][1]["content"]


@pytest.mark.parametrize("bad", [" S1", "S1 ", "S1\n", "Ｓ1", "S١"])
def test_provider_does_not_strip_or_normalize_bad_selection_ids(bad):
    client, _, _ = fake_client(contract(), [{"text": bad, "citation_ids": ["E1"]}])
    with pytest.raises(GenerationOutputError):
        client.generate("Constructed question", contract())


def test_provider_abstention_remains_allowed():
    client, _, _ = fake_client(contract(), [], answerable=False)
    result = client.generate("Constructed question", contract())
    assert not result.answerable and result.claims == []


def test_nonreference_claims_preserve_existing_behavior():
    claims = [GeneratedClaim("ordinary claim", ["E1"])]
    assert resolve_selections(claims, [replace(contract()[0], source_type="body", text="Raw")]) is claims
