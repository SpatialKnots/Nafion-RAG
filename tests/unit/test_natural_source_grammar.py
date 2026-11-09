"""Exposed real role windows and constructed controls; not independent scientific gold."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts, fact_recipes
from app.generation.fact_types import FactPatternError, verify_anchor
from app.generation.gigachat import GigaChatAnswerProvider
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.reference_quotes import prepare as quotations

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "output/natural_source_grammar_20261109/controls_v01.json").read_bytes())


def constructed(case):
    original = DATA["natural"][1]["source"]
    return Evidence(**{**original, "text": case["text"]})


@pytest.mark.parametrize("case", DATA["natural"], ids=lambda c: c["id"])
def test_unchanged_real_windows_have_declared_role_behavior(case):
    source = Evidence(**case["source"])
    params = {"grade": "Nafion-117", "product": "b1", "comparator": "NCD"}
    if not case["expected_complete"]:
        with pytest.raises(FactPatternError):
            fact_recipes.RECIPES[case["recipe"]](source, params)
        return
    rendering = fact_recipes.RECIPES[case["recipe"]](source, {})
    fact, = rendering.facts
    assert fact.property == "coulombic_efficiency" and fact.epistemic_status == "source_reported_approximate"
    assert fact.value.text == "98" and fact.conditions["cycles"].text == "200"
    assert fact.conditions["current"].text == "1" and fact.conditions["capacity"].text == "1"
    assert fact.conditions["current_unit"].text == "mA cm−2"
    assert fact.conditions["capacity_unit"].text == "mAh cm−2"
    verify_anchor(fact.support, source)
    for value in (fact.sample, fact.value, fact.unit, *fact.conditions.values()):
        assert value is not None
        verify_anchor(value.source, source)
    assert not fact.scientific_ownership_verified


@pytest.mark.parametrize("case", DATA["constructed"], ids=lambda c: c["id"])
def test_constructed_variants_do_not_transfer_conditions_or_status(case):
    if not case["expected_complete"]:
        with pytest.raises(FactPatternError):
            fact_recipes.coulombic(constructed(case), {})
        return
    rendered = fact_recipes.coulombic(constructed(case), {})
    fact, = rendered.facts
    assert "около" in rendered.text and "кулоновская" in rendered.text
    assert fact.epistemic_status == "source_reported_approximate"
    assert "measurement_temperature" in fact.unknown_fields
    if case["id"] == "varied_values":
        assert [fact.value.numeric_value, fact.conditions["cycles"].numeric_value,
                fact.conditions["current"].numeric_value, fact.conditions["capacity"].numeric_value] == ["87", "37", "2", "3"]


def packet():
    """Explicit component assembly of real raw parents, NOT production admission."""
    abstract = next(c["source"] for c in DATA["natural"] if c["id"].startswith("natural_legacy"))
    conclusion = DATA["natural"][1]["source"]
    sources = [Evidence(**{**abstract, "citation_id": "E1"}), Evidence(**{**conclusion, "citation_id": "E2"})]
    records = [answer_facts._record(recipe, source, {}, f"F{index}") for index, (recipe, source) in enumerate(
        [("composition", sources[0]), ("capacity", sources[0]), ("coulombic", sources[1])], 1)]
    selected = [replace(source, source_type=answer_facts.SOURCE_TYPE, text=json.dumps({
        "version": answer_facts.VERSION, "family": "composition_cycling", "language": "ru", "params": {},
        "raw_source": source.text, "records": [r for r in records if r["citation_id"] == source.citation_id]}, ensure_ascii=False))
        for source in sources]
    return sources, selected


def test_exact_real_component_packet_preserves_F_ids_and_native_source_quotes():
    sources, selected = packet()
    records = answer_facts.selection_records(selected)
    assert list(records) == ["F1", "F2", "F3"]
    assert "source_grammar" not in records["F1"] and "source_grammar" not in records["F2"]
    assert records["F3"]["source_grammar"] == {"version": "natural_coulombic_source_v0.1"}
    client = GigaChatAnswerProvider(credentials="offline", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                   timeout_seconds=120, max_tokens=1200)
    calls = []

    def post(url, raw, authorization, *, oauth=False):
        if oauth:
            return b'{"access_token":"offline"}'
        body = json.loads(raw)
        prompt = json.loads(body["messages"][-1]["content"].split("Source-bound records:\n", 1)[1])
        assert prompt == answer_facts.prompt_records(selected)
        calls.append(prompt)
        for record in prompt:
            parent = next(s for s in sources if s.citation_id == record["citation_id"])
            assert all(f["source_quote"] in parent.text for f in record["source_bound_facts"])
        content = {"answerable": True, "claims": [{"text": k, "citation_ids": [r["citation_id"]]} for k, r in records.items()]}
        return json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
                          "content": json.dumps(content)}}]}).encode()

    client._post = post
    generated = client.generate("Состав электролита и результаты циклирования", selected)
    assert len(calls) == 1
    resolved = answer_facts.resolve_selections(generated.claims, selected)
    assert resolved[-1].text == records["F3"]["allowed_claim"]
    for raw, derived in zip(sources, selected, strict=True):
        answer_facts.verify_raw_binding(derived.text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
                                       citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end)


@pytest.mark.parametrize("mode", ["value", "operation", "unknowns", "grammar", "summary", "partial", "citation"])
def test_new_record_cannot_bypass_recomputation_or_id_completeness(mode):
    _, selected = packet()
    records = answer_facts.selection_records(selected)
    if mode in {"partial", "citation"}:
        chosen = [GeneratedClaim(k, [r["citation_id"]]) for k, r in records.items()]
        if mode == "partial":
            chosen.pop()
        else:
            chosen[-1] = replace(chosen[-1], citation_ids=["E1"])
        with pytest.raises(GenerationOutputError):
            answer_facts.resolve_selections(chosen, selected)
        return
    payload = json.loads(selected[-1].text)
    record = payload["records"][0]
    if mode == "value":
        record["facts"][0]["value"]["text"] = "99"
    elif mode == "operation":
        record["facts"][0]["operation"] = "cleaning"
    elif mode == "unknowns":
        record["facts"][0]["unknown_fields"] = []
    elif mode == "grammar":
        record["source_grammar"]["version"] = "invented"
    else:
        record["allowed_claim"] += " доказано"
    selected[-1] = replace(selected[-1], text=json.dumps(payload))
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records(selected)


def test_natural_conclusion_alone_does_not_bypass_production_quotation_admission():
    source = Evidence(**DATA["natural"][1]["source"])
    question = json.loads((ROOT / "output/natural_source_grammar_20261109/freeze_v02/service/Q01_current.json").read_bytes())[
        "trace"]["retrieval"]["query"]
    quote = quotations(question, [source], {"resolved": True, "article_id": source.article_id})
    assert quote is not None and not quote.eligible
    bundle = answer_facts.prepare(question, [source], quote, None, answer_language="ru")
    assert not bundle.eligible


@pytest.mark.parametrize("variant", ["different_new_values", "legacy_and_new"])
def test_multiple_coulombic_passages_in_one_parent_remain_ambiguous(variant):
    source = Evidence(**DATA["natural"][1]["source"])
    extra = (DATA["original_CE_excerpt"].replace("98%", "87%") if variant == "different_new_values"
             else next(c["raw_span"]["text"] for c in DATA["natural"] if c["id"].startswith("natural_legacy")))
    with pytest.raises(FactPatternError):
        fact_recipes.coulombic(replace(source, text=source.text + "\n" + extra), {})
