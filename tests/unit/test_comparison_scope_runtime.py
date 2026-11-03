"""Paired-table arithmetic and refusal of an unsupported conductivity optimum."""

import json
from decimal import Decimal

import pytest
from test_lithiation_overview import evidence, provider, search, settings

from app.generation import service
from app.generation.comparison_scope import conductivity_superlative
from app.generation.lithiation_overview import allowed_claims, validate_claims
from app.generation.providers import GeneratedClaim, GenerationOutputError

QUESTION = "Покажи как меняется степень набухания мембраны Нафион пре переходе от протонированной к литированной форме"
ROWS = [
    ("ацетонитрил", ".14", ".12"), ("ацетон", ".38", ".27"), ("вода", ".38", ".35"),
    ("изопропанол", ".83", ".49"), ("диметилсульфоксид", ".89", "1.12"),
    ("n,n-диметилформамид", ".72", "1.15"), ("метанол", "1.14", "1.18"),
    ("этанол", "1.44", "1.33"), ("n-метил-2-пирролидон", ".64", "1.37"),
]


def table(rows=ROWS):
    return "Таблица 4.5. Равновесная степень набухания H-Nafion Li-Nafion αH ΔH αLi ΔH\n" + "\n".join(
        f"{name} {Decimal(h):.2f} -0.1 {Decimal(li):.2f} -0.2" for name, h, li in rows)


def test_all_nine_rows_keep_orientation_and_decimal_deltas():
    selected, _, metadata = service._bounded_swelling_transition([evidence(table())], "ru", QUESTION)
    assert metadata["eligible"]
    record, = metadata["records"]
    assert len(record["rows"]) == 9
    assert [row["delta_alpha"] for row in record["rows"]] == ["-0.02", "-0.11", "-0.03", "-0.34", "0.23", "0.43", "0.04", "-0.11", "0.73"]
    text = allowed_claims(selected)["E1"][0]
    assert "выше в 4/9" in text and "ниже в 5/9" in text
    assert "25" not in text and "Арифметическое" in text
    assert text.index("выше в 4/9") < text.index("ацетонитрил")
    assert "N,N-диметилформамид" in text and "N-метил-2-пирролидон" in text
    validate_claims([GeneratedClaim(text, ["E1"])], allowed_claims(selected))
    with pytest.raises(GenerationOutputError):
        validate_claims([GeneratedClaim("Для большинства Li-Nafion выше.", ["E1"])], allowed_claims(selected))


@pytest.mark.parametrize("source", [table(ROWS[:5]), "αH αLi acetonitrile .14 -0.1 .12 -0.2", "Nafion swelling data."])
def test_partial_or_unknown_table_never_admitted_as_nine_row_comparison(source):
    assert not service._bounded_swelling_transition([evidence(source)], "ru", QUESTION)[2]["eligible"]


@pytest.mark.parametrize("suffix", [" при 25°C", " в воде", " с PBI", " при 60 градусах"])
def test_specific_conditions_cannot_be_answered_by_unqualified_table(suffix):
    assert not service._bounded_swelling_transition([evidence(table())], "ru", QUESTION + suffix)[2]["eligible"]


def test_equal_rows_and_changed_signs_are_computed_not_hardcoded():
    changed = [(name, h, h) for name, h, li in ROWS]
    text = service._bounded_swelling_transition([evidence(table(changed))], "ru", QUESTION)[2]["records"][0]["allowed_claim"]
    assert "выше в 0/9" in text and "ниже в 0/9" in text and "равны в 9/9" in text
    assert "значения совпадают" in text and "зависит от растворителя" not in text


@pytest.mark.parametrize("delta,conclusion", [("0.10", "выше или совпадают"), ("-0.10", "ниже или совпадают")])
def test_direction_conclusion_follows_all_row_signs(delta, conclusion):
    changed = [(name, h, str(Decimal(h) + Decimal(delta))) for name, h, li in ROWS]
    text = service._bounded_swelling_transition([evidence(table(changed))], "ru", QUESTION)[2]["records"][0]["allowed_claim"]
    assert conclusion in text and "общего увеличения" not in text


def test_other_material_table_cannot_supply_nafion_form_comparison():
    source = table().replace("H-Nafion Li-Nafion", "PBI Li-PBI")
    assert not service._bounded_swelling_transition([evidence(source)], "ru", QUESTION)[2]["eligible"]


@pytest.mark.parametrize("source", [table().replace("αH ΔH αLi ΔH", "αLi ΔH αH ΔH"),
                                  table().replace("степень набухания", "теплопроводность")])
def test_reversed_column_order_or_different_quantity_not_silently_interpreted(source):
    assert not service._bounded_swelling_transition([evidence(source)], "ru", QUESTION)[2]["eligible"]


@pytest.mark.parametrize("question", [
    "Какая смесь растворителей даёт наилучшую ионную проводимость для Li-Nafion",
    "What solvent mixture gives the highest conductivity for Li-Nafion?",
    "Какая смесь даёт максимальную проводимость Li-Nafion среди исследованных?",
])
def test_superlative_requires_source_supported_comparable_universe(question):
    result = conductivity_superlative(question)
    assert result is not None and not result["eligible"] and not result["winner_established"]


def test_noncomparative_conductivity_question_unchanged():
    assert conductivity_superlative("Как измеряли проводимость Li-Nafion?") is None


def test_unknown_global_optimum_blocks_provider_before_build(monkeypatch):
    question = "Какая смесь растворителей даёт наилучшую ионную проводимость для Li-Nafion"
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: search("Li-Nafion mixture highest conductivity EC/SL."))
    monkeypatch.setattr(service, "build_answer_provider", lambda *a: pytest.fail("No model for unsupported optimum"))
    result = service.answer_question(object(), settings(), question)
    assert result.status == "insufficient_evidence"
    assert result.metadata["conductivity_best_scope"]["required"] == [
        "comparison_universe", "same_material_form", "composition_at_optimum", "temperature_basis"]


def test_complete_table_reaches_strict_actual_gigachat_parser_without_network(monkeypatch):
    calls = []
    active = provider()

    def post(url, body, authorization, *, oauth=False):
        calls.append(url)
        if oauth:
            return b'{"access_token":"synthetic"}'
        native = json.loads(body)
        text = native["response_format"]["schema"]["$defs"]["_Claim"]["properties"]["text"]["enum"][0]
        content = json.dumps({"answerable": True, "claims": [{"text": text, "citation_ids": ["E1"]}]}, ensure_ascii=False)
        return json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": content}}]},
                          ensure_ascii=False).encode()

    monkeypatch.setattr(active, "_post", post)
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: search(table()))
    result = service.answer_question(object(), settings(), QUESTION, provider=active)
    assert result.status == "answered" and "выше в 4/9" in result.answer and len(calls) == 2
