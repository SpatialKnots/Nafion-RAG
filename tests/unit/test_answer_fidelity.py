"""Constructed, varied source quantities; no actual provider calls or scientific score."""

import hashlib
import json
from dataclasses import replace

import pytest

from app.generation.answer_fidelity import instruction, prepare, validate
from app.generation.gigachat import GigaChatAnswerProvider
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError

Q2 = ("How does conductivity of a single-phase Li2O layer differ from bulk Li2O at room temperature, "
      "and what experimental conditions were used?")
Q4 = "How do mixing temperature, heating and cooling affect Li-Nafion EC/SL uptake and structure?"
COMPARE = ("The single-component Li2O SEI (~10-8 S/cm) and that of sintered bulk Li2O pellets "
           "reported in literature (~10-11 S/cm) at room temperature.")
GAS = "Li foils were reacted in O2 gas at fixed temperature ranging from 30 °C to 210 °C for 2 hours, forming Li2O."
MEDIUM = "EIS in symmetric cells used electrolyte (0.8 M LiPF6 in EC/DEC, v/v = 2/3, synthetic control)."
CYCLES = ("The higher the mixing temperature, the greater the solvent uptake. Only in the heating cycle; "
          "during the cooling cycle the decrease was barely noticeable.")
HOLD = ("A long-term (45 days) isothermal treatment was carried out at 35 ◦C. "
        "This procedure did not influence the obtained W values.")
ALTERNATIVES = "This suggests either equilibrium state or that syneresis requires a very long time."
HYPOTHESIS = "The hysteresis supports the hypothesis of an irreversible rearrangement at elevated temperatures."
INTENSITY = "Plasticiser somewhat reduces the intensity of crystal reflection; heating causes a slight decrease in intensity."
CRYSTALS = "The crystalline regions, which remain nearly unchanged over 35–75 ◦C."
HALOS = ("The halo observed in the “dry” membrane sharply decreases. A new, intense halo increases up to 55 ◦C "
         "and does not change at 75 ◦C.")


def source(text, cid="E1", article="synthetic"):
    return Evidence(cid, article, "chunk-" + cid, "Constructed", None, 1, 2, "body", text, 0,
                    "constructed", {}, {})


def sources(kind):
    if kind == "Q2":
        return [source("\n".join([COMPARE, GAS, MEDIUM]))]
    return [source("\n".join(["Li-Nafion EC/SL.", CYCLES, HOLD, ALTERNATIVES, HYPOTHESIS])),
            source("\n".join([INTENSITY, CRYSTALS, HALOS]), "E2")]


def claims(kind):
    if kind == "Q2":
        return [GeneratedClaim("При комнатной температуре проводимость слоя Li₂O около 10⁻⁸ S/cm, "
                               "а объёмного Li₂O около 10⁻¹¹ S/cm по литературным данным.", ["E1"]),
                GeneratedClaim("Синтез: литиевую фольгу обрабатывали в O₂ от 30 до 210 °C в течение 2 часов.", ["E1"]),
                GeneratedClaim("EIS в симметричных Li‖Li ячейках: 0.8 M LiPF₆ в EC/DEC 2:3 по объёму.", ["E1"])]
    return [GeneratedClaim("При нагревании поглощение увеличивается, при охлаждении достигнутое поглощение сохраняется.", ["E1"]),
            GeneratedClaim("После 45 суток при 35 °C поглощение не изменилось.", ["E1"]),
            GeneratedClaim("Возможны либо близость к равновесию, либо очень медленный синерезис.", ["E1"]),
            GeneratedClaim("Гистерезис поддерживает гипотезу необратимой перестройки.", ["E1"]),
            GeneratedClaim("Интенсивность кристаллического рефлекса незначительно снижается.", ["E2"]),
            GeneratedClaim("Кристаллические области практически неизменны.", ["E2"]),
            GeneratedClaim("Старое гало сухой мембраны уменьшается; появляется новое аморфное гало.", ["E2"])]


@pytest.mark.parametrize("kind,q", [("Q2", Q2), ("Q4", Q4)])
def test_constructed_complete_answers_preserve_exact_source_anchors(kind, q):
    evidence = sources(kind)
    contract = prepare(q, evidence)
    assert contract.eligible, contract.missing_source_roles
    validate(claims(kind), contract)
    assert "EVERY role" in instruction(contract)
    for requirement in contract.requirements:
        for anchor in requirement.anchors:
            original = next(e.text for e in evidence if e.citation_id == anchor["citation_id"])
            assert original[anchor["start"]:anchor["end"]] == anchor["text"]
            assert hashlib.sha256(original.encode()).hexdigest() == anchor["raw_chunk_sha256"]


@pytest.mark.parametrize("kind,index", [("Q2", i) for i in range(3)] + [("Q4", i) for i in range(7)])
def test_missing_role_or_wrong_citation_cannot_pass(kind, index):
    selected = claims(kind)
    contract = prepare(Q2 if kind == "Q2" else Q4, sources(kind))
    with pytest.raises(GenerationOutputError):
        validate(selected[:index] + selected[index+1:], contract)
    selected[index] = replace(selected[index], citation_ids=["unrelated"])
    with pytest.raises(GenerationOutputError):
        validate(selected, contract)


@pytest.mark.parametrize("index,before,after", [
    (0, "10⁻⁸", "10⁻¹¹"), (0, "10⁻¹¹", "10⁻⁸"), (1, "210", "250"), (1, "30 до", "130 до"),
    (1, "2 часов", "1 часа"),
    (2, "0.8 M", "1.0 M"), (2, "0.8 M", "0.8 m"), (2, "2:3", "1:1"), (2, "по объёму", "по массе"),
    (1, "обрабатывали", "не обрабатывали"), (2, "EIS", "не использовали EIS"),
])
def test_wrong_quantities_basis_and_negated_operations_fail(index, before, after):
    selected = claims("Q2")
    selected[index] = replace(selected[index], text=selected[index].text.replace(before, after))
    with pytest.raises(GenerationOutputError):
        validate(selected, prepare(Q2, sources("Q2")))


@pytest.mark.parametrize("extra", ["Необратимость доказана.", "Гипотеза необратимости доказана.",
    "Наблюдается значительное уменьшение интенсивности кристаллических рефлексов."])
def test_adding_overstatement_to_complete_answer_is_rejected(extra):
    with pytest.raises(GenerationOutputError):
        validate(claims("Q4") + [GeneratedClaim(extra, ["E2"])], prepare(Q4, sources("Q4")))


@pytest.mark.parametrize("index,before,after", [
    (0, "сохраняется", "не сохраняется"), (1, "45 суток", "60 суток"),
    (3, "поддерживает", "не поддерживает"), (5, "практически неизменны", "не остаются практически неизменными"),
    (6, "появляется", "не появляется"), (2, "синерезис.", "синерезис исключены."),
])
def test_negation_or_changed_hold_is_not_role_coverage(index, before, after):
    selected = claims("Q4")
    selected[index] = replace(selected[index], text=selected[index].text.replace(before, after))
    with pytest.raises(GenerationOutputError):
        validate(selected, prepare(Q4, sources("Q4")))


def test_no_cross_work_join_or_ambiguous_work():
    evidence = sources("Q4")
    evidence[1] = replace(evidence[1], article_id="other")
    assert not prepare(Q4, evidence).eligible
    evidence = sources("Q2")
    assert not prepare(Q2, evidence + [replace(evidence[0], article_id="other", citation_id="E9")]).eligible


@pytest.mark.parametrize("missing", [COMPARE, GAS, MEDIUM])
def test_missing_source_does_not_invent_conditions(missing):
    evidence = [source("\n".join([s for s in [COMPARE, GAS, MEDIUM] if s != missing]))]
    contract = prepare(Q2, evidence)
    assert not contract.eligible
    assert contract.missing_source_roles


def test_unscoped_behavior_and_ru_question_forms():
    assert prepare("What is Nafion?", sources("Q2")) is None
    validate([GeneratedClaim("ordinary", ["E1"])], None)
    assert instruction(None) == ""
    assert prepare("Проводимость однофазного слоя Li₂O и объёмного Li₂O при комнатной температуре: какие условия?",
                   sources("Q2")).eligible


def test_english_complete_comparison_and_conditions():
    selected = [GeneratedClaim("At room temperature the layer has 10-8 S/cm and bulk Li2O has 10-11 S/cm from literature.", ["E1"]),
                GeneratedClaim("Synthesis: Li foil was treated in O2 from 30 to 210 °C for 2 hours.", ["E1"]),
                GeneratedClaim("EIS in symmetric Li cells: 0.8 M LiPF6 in EC/DEC 2:3 by volume.", ["E1"])]
    validate(selected, prepare(Q2, sources("Q2")))


@pytest.mark.parametrize("prefix", ["No ", "It is not true that ", "Hypothetical: ", "We proposed that "])
def test_nonaffirmative_source_prefix_cannot_supply_synthesis(prefix):
    evidence = sources("Q2")
    evidence[0] = replace(evidence[0], text=evidence[0].text.replace(GAS, prefix + GAS))
    assert not prepare(Q2, evidence).eligible


def test_structure_does_not_borrow_material_from_question():
    evidence = sources("Q4")
    evidence[0] = replace(evidence[0], text=evidence[0].text.replace("Li-Nafion EC/SL.", "Other material."))
    assert not prepare(Q4, evidence).eligible


def test_swapped_layer_and_bulk_values_fail():
    selected = claims("Q2")
    text = selected[0].text.replace("10⁻⁸", "PLACEHOLDER").replace("10⁻¹¹", "10⁻⁸").replace("PLACEHOLDER", "10⁻¹¹")
    selected[0] = replace(selected[0], text=text)
    with pytest.raises(GenerationOutputError):
        validate(selected, prepare(Q2, sources("Q2")))


def test_lowercase_source_m_is_not_molarity():
    evidence = sources("Q2")
    evidence[0] = replace(evidence[0], text=evidence[0].text.replace("0.8 M", "0.8 m"))
    assert not prepare(Q2, evidence).eligible


def test_preserved_crystals_are_not_negated_by_not_significantly_influence():
    evidence = sources("Q4")
    evidence[1] = replace(evidence[1], text=evidence[1].text.replace(CRYSTALS,
        "It does not significantly influence the " + CRYSTALS.removeprefix("The ")))
    contract = prepare(Q4, evidence)
    assert contract.eligible, contract.missing_source_roles
    validate(claims("Q4"), contract)


def test_english_structure_answer_keeps_qualifiers():
    texts = ["On heating uptake increases; on cooling uptake is retained.",
             "After 45 days at 35 °C uptake is unchanged.", "Either near equilibrium or very slow syneresis.",
             "Hysteresis supports the hypothesis of irreversible rearrangement.",
             "Crystalline intensity somewhat decreases.", "Crystalline regions remain nearly unchanged.",
             "The old dry-membrane halo decreases and a new amorphous halo appears."]
    validate([GeneratedClaim(t, ["E1" if i < 4 else "E2"]) for i, t in enumerate(texts)], prepare(Q4, sources("Q4")))


@pytest.mark.parametrize("mode", ["complete", "incomplete", "abstention", "missing_source"])
def test_actual_provider_enforces_contract_and_preserves_abstention(mode):
    evidence = sources("Q2")
    if mode == "missing_source":
        evidence = [replace(evidence[0], text=evidence[0].text.replace(GAS, ""))]
    selected = claims("Q2") if mode == "complete" else claims("Q2")[:1] if mode == "incomplete" else []
    calls, bodies = [], []
    client = GigaChatAnswerProvider(credentials="offline", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                   timeout_seconds=120, max_tokens=1200)

    def post(url, body, authorization, *, oauth=False):
        calls.append("fake_oauth" if oauth else "fake_model")
        if oauth:
            return b'{"access_token":"offline"}'
        bodies.append(json.loads(body))
        return json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(
            {"answerable": mode != "abstention", "claims": [{"text": c.text, "citation_ids": c.citation_ids}
                                                            for c in selected]})}}]}).encode()

    client._post = post
    if mode in {"incomplete", "missing_source"}:
        with pytest.raises(GenerationOutputError):
            client.generate(Q2, evidence)
    else:
        result = client.generate(Q2, evidence)
        assert result.answerable == (mode == "complete")
    if mode == "missing_source":
        assert calls == []
    else:
        assert calls == ["fake_oauth", "fake_model"]
        assert "EVERY role" in bodies[0]["messages"][1]["content"]
        assert "gas_synthesis" in bodies[0]["messages"][1]["content"]
