"""Constructed source bindings/renderings; no real model or scientific accuracy."""

import json
import re
from dataclasses import asdict, replace

import pytest

from app.generation.answer_facts import prepare, resolve_selections, selection_records, verify_raw_binding
from app.generation.answer_fidelity import prepare as fidelity
from app.generation.fact_types import SourceView
from app.generation.gigachat import GigaChatAnswerProvider
from app.generation.presentation import capture_sources
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.reference_quotes import prepare as quotations
from app.retrieval.search import SearchResponse, SearchResult
from app.ui import _claim_source_fragment

COMPOSITION = ("Каков состав разработанного Smith и Jones (2021) электролита с фторированным эфиром и карбонатами "
               "и какие результаты циклирования были получены с ним в ячейках Li‖FePO₄ и Li‖Ag?")
DISPERSION = ("Каким способом Smith и соавторы (2021) получили не содержащую этанола водную дисперсию "
              "Nafion-120 (образец c2) и какова была протонная проводимость мембраны, изготовленной из этой "
              "дисперсии, в сравнении с мембраной из коммерческой дисперсии XYZ?")
OXIDE = "Проводимость однофазного слоя Li₂O и объёмного Li₂O при комнатной температуре: какие условия?"
STRUCTURE = "Li-Nafion EC/SL: как температура смешения при нагревании и охлаждении влияет на структуру?"
HEAD = "Smith and Jones 2021\n"
ABSTRACT = (HEAD + "ABSTRACT: A fluorinated ether and carbonate electrolyte has 0.6 M LiBF4 in ABC/dimethyl\n"
            "carbonate/DEF (2:3:4 by volume). We added 0.1 M lithium difluoro(oxalato)borate as a film-\n"
            "forming additive, so that a new bifunctional electrolyte of 0.7 M has been obtained. "
            "The electrolyte enables Li||FePO4 batteries to maintain nearly 71% capacity after 43 cycles "
            "when charged to 3.2 V under the current density of 3 mA g−1. Meanwhile, Li||Ag half-cells maintain "
            "about 83% coulombic efficiency after being charged/discharged 29 times under 4 mA cm−2 "
            "current density and 2 mAh cm−2 lithium deposition amount per cycle.\nKEYWORDS: synthetic.\n")
METHOD = (HEAD + "Dissolution procedures\nNafion-120 membrane, to obtain a dispersion, was put in an autoclave containing a "
          "40/60 mixture of water and ethanol, and heated at 423 K for two hours. A clear homogeneous dispersion "
          "was obtained (a3 sample). Ethanol-free Nafion dispersion was prepared from the a3 sample by "
          "semi-batch continuous azeotropic distillation at constant volume. A clear dispersion without ethanol "
          "was obtained (c2 sample).\nNafion recast film\nRecast membrane without using organic solvents (as DMF) "
          "was obtained from the c2 dispersion on a glass plate, evaporating the water at 433 K.\nCharacterisation\n")
TABLE = (HEAD + "Tab. 8.\nEIS analysis.\nSample\nConductivity\n—————\nS · cm−1\nWater content\n—————\nwt.-%\n"
         "XYZ\n0.013\n12\nSample c2a)\n0.072\n21\na) Synthetic footnote.\nFig. 9.\n")
OXIDE_SOURCE = ("single-component Li2O SEI (~10-8 S/cm) and that of sintered bulk Li2O pellets reported in "
                "literature (~10-11 S/cm) at room temperature.\nLi foils were reacted in O2 gas at fixed temperature "
                "ranging from 30 °C to 210 °C for 2 hours, forming Li2O. Symmetric Li-Li cells used "
                "electrolyte (0.8 M LiPF6 in EC/DEC, v/v = 2/3, synthetic control). EIS measurements were conducted.")
CYCLE_SOURCE = ("Li-Nafion EC/SL. The higher the mixing temperature, the greater the solvent uptake. "
                "Only in the heating cycle; during the cooling cycle the decrease was barely noticeable. "
                "A long-term (45 days) isothermal treatment was carried out at 35 ◦C. "
                "This procedure did not influence the obtained W values. This suggests either equilibrium state "
                "or that syneresis requires a very long time. The hysteresis supports the hypothesis of an "
                "irreversible rearrangement at elevated temperatures.")
STRUCTURE_SOURCE = ("Li-Nafion EC/SL. Plasticiser somewhat reduces the intensity of crystal reflection; heating "
                    "causes a slight decrease in intensity. The crystalline regions, which remain nearly unchanged "
                    "over 35–75 ◦C. The halo observed in the “dry” membrane sharply decreases. A new, intense halo "
                    "increases up to 55 ◦C and does not change at 75 ◦C.")


def evidence(text, cid="E1", article="work"):
    return Evidence(cid, article, "chunk-" + cid, "Constructed", None, 1, 2, "main_text", text, 0, "constructed", {}, {})


def inputs(kind):
    if kind == "composition":
        return COMPOSITION, [replace(evidence(ABSTRACT), page_end=1)]
    if kind == "dispersion":
        return DISPERSION, [replace(evidence(METHOD), page_end=1), replace(evidence(TABLE, "E2"), page_end=1)]
    if kind == "oxide":
        return OXIDE, [evidence(OXIDE_SOURCE)]
    return STRUCTURE, [evidence(CYCLE_SOURCE), evidence(STRUCTURE_SOURCE, "E2")]


def bundle(kind):
    q, sources = inputs(kind)
    quote = quotations(q, sources, {"resolved": True, "article_id": "work"})
    return prepare(q, sources, quote, fidelity(q, sources), answer_language="ru")


@pytest.mark.parametrize("kind,count", [("composition", 3), ("dispersion", 3), ("oxide", 3), ("structure", 4)])
def test_complete_bundles_recompute_values_conditions_and_russian_text(kind, count):
    result = bundle(kind)
    assert result.eligible, (result.reason, result.diagnostics)
    records = selection_records(result.evidence)
    assert len(records) == count
    chosen = [GeneratedClaim(key, [r["citation_id"]]) for key, r in reversed(list(records.items()))]
    rendered = resolve_selections(chosen, result.evidence)
    assert [c.text for c in rendered] == [r["allowed_claim"] for r in records.values()]
    assert all(re.search(r"[а-я]", c.text) for c in rendered)
    for raw in result.display:
        derived = next(e for e in result.evidence if e.citation_id == raw.citation_id)
        verify_raw_binding(derived.text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
                           citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end)


def test_composition_values_and_cycle_quantities_cannot_be_confused():
    result = bundle("composition")
    assert result.eligible, result.diagnostics
    r = result.records
    assert r[0]["arithmetic"]["result"] == "0.7"
    assert r[1]["facts"][0]["property"] == "capacity_retention"
    assert r[1]["facts"][0]["value"]["text"] == "71"
    assert r[1]["facts"][0]["conditions"]["cycles"]["text"] == "43"
    assert r[2]["facts"][0]["property"] == "coulombic_efficiency"
    assert "83%" in r[2]["allowed_claim"] and "29" in r[2]["allowed_claim"]


def test_dispersion_keeps_steps_and_arithmetic_comparability_unknowns():
    result = bundle("dispersion")
    assert result.eligible, result.diagnostics
    assert "423 K" in result.records[0]["allowed_claim"] and "433 K" in result.records[1]["allowed_claim"]
    assert result.records[2]["arithmetic"]["exact_fraction"] == "72/13"
    assert result.records[2]["arithmetic"]["display_value"] == "5.5"
    assert result.records[0]["facts"][0]["unknown_fields"] == ["water_ethanol_ratio_basis"]
    assert "ionomer_equivalent_weight" in result.records[2]["facts"][0]["unknown_fields"]
    assert result.records[0]["facts"][0]["value"]["text"] == "a3"
    assert result.records[0]["facts"][1]["value"]["text"] == "c2"
    assert result.records[0]["facts"][0]["conditions"]["duration"]["numeric_value"] == "2"


def test_ambiguous_table_unit_stays_literal():
    q, src = inputs("dispersion")
    src[1] = replace(src[1], text=src[1].text.replace("S · cm−1", "S N cm–1"))
    result = prepare(q, src, quotations(q, src, {"resolved": True, "article_id": "work"}), None, answer_language="ru")
    assert result.eligible, result.diagnostics
    assert result.records[2]["facts"][0]["unit"]["text"] == "S N cm–1"
    assert "неоднознач" in result.records[2]["allowed_claim"].lower()
    assert "S/cm" not in result.records[2]["allowed_claim"]


def test_normalization_always_maps_back_to_raw_ligatures_and_line_breaks():
    source = evidence("ﬁlm-\nforming\u00a0at 25 °C")
    view = SourceView(source)
    assert view.text == "filmforming at 25 °C"
    match = view.one(r"(?P<label>filmforming)")
    assert view.value(match, "label").source.text == "ﬁlm-\nforming"


@pytest.mark.parametrize("bad", ["F0", "F4", "f1", "F01", "Ｆ1", "F١", " F1", "F1 ", "F1\n", "F1 extra"])
def test_invalid_ids_are_never_normalized_or_repaired(bad):
    result = bundle("composition")
    chosen = [GeneratedClaim(r["selection_id"], [r["citation_id"]]) for r in result.records]
    chosen[0] = replace(chosen[0], text=bad)
    with pytest.raises(GenerationOutputError):
        resolve_selections(chosen, result.evidence)


@pytest.mark.parametrize("mode", ["partial", "duplicate", "wrong_citation", "copied_summary", "multiple_citations"])
def test_incomplete_or_free_selections_fail_atomically(mode):
    result = bundle("composition")
    chosen = [GeneratedClaim(r["selection_id"], [r["citation_id"]]) for r in result.records]
    if mode == "partial":
        chosen.pop()
    elif mode == "duplicate":
        chosen[1] = chosen[0]
    elif mode == "wrong_citation":
        chosen[0] = replace(chosen[0], citation_ids=["E9"])
    elif mode == "copied_summary":
        chosen[0] = replace(chosen[0], text=result.records[0]["allowed_claim"])
    else:
        chosen[0] = replace(chosen[0], citation_ids=["E1", "E2"])
    with pytest.raises(GenerationOutputError):
        resolve_selections(chosen, result.evidence)


@pytest.mark.parametrize("change", ["value", "unit", "sample", "operation", "conditions", "status", "rendering", "source",
                                    "recipe", "missing"])
def test_server_fact_payload_tampering_is_rejected(change):
    result = bundle("composition")
    item = result.evidence[0]
    payload = json.loads(item.text)
    record = payload["records"][0]
    fact = record["facts"][0]
    if change in {"value", "unit", "sample"}:
        fact[change]["text"] = "incorrect"
    elif change == "operation":
        fact["operation"] = "measurement_instead_of_preparation"
    elif change == "conditions":
        fact["conditions"]["ratio_basis"]["text"] = "mass"
    elif change == "status":
        fact["epistemic_status"] = "scientifically_confirmed"
    elif change == "rendering":
        record["allowed_claim"] += " Invented assertion."
    elif change == "source":
        payload["raw_source"] = payload["raw_source"].replace("0.6", "0.9")
    elif change == "recipe":
        record["recipe"] = "coulombic"
    else:
        payload["records"].pop()
    modified = [replace(item, text=json.dumps(payload, ensure_ascii=False))]
    with pytest.raises(GenerationOutputError):
        selection_records(modified)


def test_missing_fact_field_keeps_existing_path_with_diagnostic():
    q, src = inputs("composition")
    src[0] = replace(src[0], text=src[0].text.replace("0.7 M", "0.8 M"))
    result = prepare(q, src, quotations(q, src, {"resolved": True, "article_id": "work"}), None, answer_language="ru")
    assert not result.eligible
    assert any(d["reason"] == "reported_total_inconsistent_with_components" for d in result.diagnostics)
    assert result.evidence == []


def test_english_and_unscoped_requests_keep_existing_presentation():
    q, src = inputs("composition")
    result = prepare(q, src, quotations(q, src, {"resolved": True, "article_id": "work"}), None, answer_language="en")
    assert not result.eligible and result.reason == "russian_fact_renderer_not_requested"
    assert prepare("ordinary question", src, None, None) is None


def test_hypotheses_and_unknown_sample_fields_are_not_promoted():
    result = bundle("structure")
    assert result.eligible, result.diagnostics
    statuses = {f["epistemic_status"] for r in result.records for f in r["facts"]}
    assert "hypothesis" in statuses and "alternative_interpretations" in statuses
    assert all(not f["scientific_ownership_verified"] for r in result.records for f in r["facts"])
    assert "необратимость не доказана" in result.records[1]["allowed_claim"]


def test_provider_selects_ids_instead_of_writing_scientific_text():
    result = bundle("composition")
    client = GigaChatAnswerProvider(credentials="offline", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                   timeout_seconds=120, max_tokens=1200)
    bodies = []

    def post(url, body, authorization, *, oauth=False):
        if oauth:
            return b'{"access_token":"offline"}'
        bodies.append(json.loads(body))
        return json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps({
            "answerable": True, "claims": [{"text": key, "citation_ids": [r["citation_id"]]}
                                            for key, r in selection_records(result.evidence).items()]})}}]}).encode()

    client._post = post
    generated = client.generate(COMPOSITION, result.evidence)
    assert [c.text for c in generated.claims] == ["F1", "F2", "F3"]
    assert bodies[0]["response_format"]["schema"]["$defs"]["_Claim"]["properties"]["text"]["enum"] == ["F1", "F2", "F3"]


def test_ui_keeps_russian_summary_and_exact_quotes_out_of_transport_json():
    result = bundle("composition")
    original, derived = result.display[0], result.evidence[0]
    row = SearchResult(original.article_id, original.chunk_id, original.title, original.doi, original.page_start,
                       original.page_end, original.source_type, "snippet", 0, "constructed", full_text=original.text,
                       text_layer="original")
    captured = capture_sources(SearchResponse(COMPOSITION, [row]), [derived])
    citation = asdict(original) | {"pdf_page_url": "/articles/work/pdf?layer=original#page=1"}
    rendered = _claim_source_fragment(citation, captured[original.citation_id])
    assert "Русская сводка" in rendered and "Точные исходные цитаты" in rendered
    assert "ABSTRACT:" in rendered and "0.6" in rendered
    assert "source_fact_selection_v0.2" not in rendered


@pytest.mark.parametrize("kind,before,after", [
    ("composition", "0.6 M", "0.6 m"), ("composition", "by volume", "by mass"),
    ("composition", "71% capacity after 43", "71% capacity after unknown"),
    ("dispersion", "from the a3 sample", "from the a4 sample"),
    ("dispersion", "c2 dispersion on a glass", "c3 dispersion on a glass"),
    ("oxide", "0.8 M", "0.8 m"), ("oxide", "Symmetric Li-Li", "Asymmetric Li-Cu"),
    ("structure", "supports the hypothesis", "proves"),
    ("structure", "somewhat reduces", "greatly reduces"),
])
def test_changed_conditions_or_owner_do_not_produce_a_structured_answer(kind, before, after):
    q, sources = inputs(kind)
    sources = [replace(e, text=e.text.replace(before, after)) for e in sources]
    quote = quotations(q, sources, {"resolved": True, "article_id": "work"})
    contract = fidelity(q, sources)
    result = prepare(q, sources, quote, contract, answer_language="ru")
    assert result is not None and not result.eligible


@pytest.mark.parametrize("change", ["mixed", "wrong_article", "family_type", "unknown_selector", "bad_json", "role_order"])
def test_malformed_or_cross_source_contract_fails_before_transport(change):
    result = bundle("dispersion")
    items = list(result.evidence)
    p = json.loads(items[0].text)
    if change == "mixed":
        items[1] = replace(items[1], source_type="main_text")
    elif change == "wrong_article":
        items[1] = replace(items[1], article_id="other")
    elif change == "family_type":
        p["family"] = []
    elif change == "unknown_selector":
        p["params"]["invented"] = "condition"
    elif change == "role_order":
        p["records"][0]["selection_id"] = "F8"
    items[0] = replace(items[0], text="not JSON" if change == "bad_json" else json.dumps(p))
    with pytest.raises(GenerationOutputError):
        selection_records(items)


def test_source_hash_and_conditions_map_back_to_original_parent():
    result = bundle("dispersion")
    raw = result.display[0]
    d = result.evidence[0]
    with pytest.raises(ValueError):
        verify_raw_binding(d.text, raw.text.replace("423 K", "424 K"), article_id=raw.article_id,
                           chunk_id=raw.chunk_id, citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end)


def test_source_contract_never_joins_operations_from_other_work():
    q, sources = inputs("dispersion")
    sources[1] = replace(sources[1], article_id="other")
    quote = quotations(q, sources, {"resolved": True, "article_id": "work"})
    result = prepare(q, sources, quote, None, answer_language="ru")
    assert not result.eligible and result.reason == "reference_precondition_not_eligible"


def test_explicit_power_notation_has_numeric_value_without_changing_unit_or_surface():
    result = bundle("oxide")
    values = result.records[0]["facts"]
    assert values[0]["value"]["text"] == "10-8"
    assert values[0]["value"]["numeric_value"] == "1E-8"
    assert values[1]["value"]["numeric_value"] == "1E-11"
    assert values[0]["unit"]["text"] == "S/cm"
    assert values[0]["unit"]["source"]["start"] != values[1]["unit"]["source"]["start"]
    assert "10⁻⁸ S/cm" in result.records[0]["allowed_claim"]


@pytest.mark.parametrize("bad", ["1e-0.6 M", "1,0.6 M", "-0.6 M", "1.0.6 M"])
def test_partial_numeric_tokens_do_not_become_concentrations(bad):
    q, sources = inputs("composition")
    sources[0] = replace(sources[0], text=sources[0].text.replace("0.6 M", bad))
    result = prepare(q, sources, quotations(q, sources, {"resolved": True, "article_id": "work"}), None, answer_language="ru")
    assert not result.eligible
