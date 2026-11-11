"""Source completeness, status and identity counterfactuals; exposed development controls."""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_completeness as c
from app.generation import answer_facts, service
from app.generation.providers import Evidence, ExtractiveAnswerProvider, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResponse, SearchResult
from scripts import bilingual_lexical_admission_20261110 as replay
from scripts.gigachat_answer_smoke import configure

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/answer_completeness_source_v01.json"
SAVED = json.loads(FIXTURE.read_bytes())
SOURCE_IDS = {"Kondo_04": "E1", "Nambu_10": "E2", "Peng_01": "E1"}
ORIGINAL = {cid: Evidence(**next(e for e in d["trace"]["evidence"] if e["citation_id"] == SOURCE_IDS[cid]))
            for cid, d in SAVED.items()}
CANONICAL = {cid: c.view(e, c.family(SAVED[cid]["api"]["question"])).text for cid, e in ORIGINAL.items()}


def bundle(cid, text=None, question=None):
    data = SAVED[cid]
    source = ORIGINAL[cid] if text is None else replace(ORIGINAL[cid], text=text)
    return prepare(question or data["api"]["question"], [source], data["trace"]["retrieval"]["metadata"]["explicit_source_reference"],
                   answer_language="ru")


@pytest.mark.parametrize("cid,count", [("Kondo_04", 3), ("Nambu_10", 2), ("Peng_01", 10)])
def test_complete_actual_sources_recompute_all_fields_with_exact_raw_anchors(cid, count):
    result = bundle(cid)
    assert result.eligible, result.diagnostics
    record = answer_facts.selection_records(result.evidence)["F1"]
    assert len(record["facts"]) == count and record["arithmetic"] is None
    raw = ORIGINAL[cid].text
    for fact in record["facts"]:
        assert not fact["scientific_ownership_verified"]
        for anchor in [fact["support"], *[v["source"] for v in
                      (fact["sample"], fact["value"], fact["unit"], fact["method"], *fact["conditions"].values()) if v]]:
            assert raw[anchor["start"]:anchor["end"]] == anchor["text"]
    if cid == "Kondo_04":
        assert [f["sample"]["text"] for f in record["facts"]] == ["DME", "F3MEE", "F6DEE"]
        assert "неполным подавлением" in record["allowed_claim"] and "солевой" not in record["allowed_claim"]
    elif cid == "Nambu_10":
        assert record["facts"][0]["unit"]["text"] == "mA h g−1"
        assert record["facts"][1]["epistemic_status"] == "source_author_possibility"
        assert "experimentally_identified_film_composition" in record["facts"][1]["unknown_fields"]
        assert "может образовать" in record["allowed_claim"] and "на массу LiCoO2" in record["allowed_claim"]
    else:
        assert record["allowed_claim"].count("1 M LiPF6") == 4
        assert "1,2-Bis(1,1,2,2-tetrafluoroethoxy) ethane" in record["allowed_claim"]
        assert [f["conditions"]["ratio_basis"]["text"] for f in record["facts"][:4]] == [
            "by volume", "by weight", "by weight", "by weight"]


@pytest.mark.parametrize("cid,old,new", [
    ("Kondo_04", "F3MEE (18.7", "F3MEE (19.7"),
    ("Kondo_04", "in moderately solvating F3MEE", "in moderately solvating OTHER"),
    ("Kondo_04", "Li–solvent–graphite", "Li–salt–graphite"),
    ("Kondo_04", "μLi +", "μNa +"),
    ("Kondo_04", "LiFSI/solvent = 1/10", "LiFSI/solvent = 1/20"),
    ("Kondo_04", "incomplete inhibition", "complete inhibition"),
    ("Kondo_04", "forming Li-GIC LiC6", "forming Na-GIC NaC6"),
    ("Nambu_10", "can form", "does form"),
    ("Nambu_10", "can form", "cannot form"),
    ("Nambu_10", "50th cycle", "51th cycle"),
    ("Nambu_10", "FETFEE-based", "ETFEE-based"),
    ("Nambu_10", "EC–FETFEE system was as high", "EC–ETFEE system was as high"),
    ("Nambu_10", "mA h g−1 even", "mA h cm−2 even"),
    ("Peng_01", "LiPF6 dissolved in EC/EMC at", "LiBF4 dissolved in EC/EMC at"),
    ("Peng_01", "LiPF6 dissolved in EC/EMC/TFEE", "LiBF4 dissolved in EC/EMC/TFEE"),
    ("Peng_01", "by volume (marked as EE)", "by weight (marked as EE)"),
    ("Peng_01", "ratio by weight", "ratio by volume"),
    ("Peng_01", "EC/EMC/TFEE at", "EC/FEMC/TFEE at"),
    ("Peng_01", "1,2-Bis(1,1,2,2-tetrafluoroethoxy)", "1,2-Bis(2,2,2-trifluoroethoxy)"),
    ("Peng_01", "1 M LiPF6 dissolved", "0 M LiPF6 dissolved"),
    ("Peng_01", "3/6/1 ratio", "3/6/0 ratio"),
    ("Peng_01", "FET: 1 M", "EET: 1 M"),
    ("Peng_01", "methyl carbonate (FEMC)", "methyl carbonate (EMC)"),
])
def test_missing_or_conflicting_scientific_binding_refuses(cid, old, new):
    text = CANONICAL[cid]
    # Source grammar is case-sensitive; preserve actual capitalization in probes.
    if old.startswith("in moderately"):
        old, new = old[0].upper() + old[1:], new[0].upper() + new[1:]
    assert old in text
    assert not bundle(cid, text.replace(old, new)).eligible


@pytest.mark.parametrize("cid", SAVED)
@pytest.mark.parametrize("prefix", ["References\n", "Previously reported ", "Hypothetical: ", "Unmeasured: ", "Not observed: "])
def test_reference_prior_and_uncertain_scope_cannot_be_admitted(cid, prefix):
    text = CANONICAL[cid]
    pattern = {"Kondo_04": c.REACTION_FRAME, "Nambu_10": c.CAPACITY_RESULT, "Peng_01": c.COMPONENT_NAMES}[cid]
    match = pattern.search(text)
    assert match is not None
    assert not bundle(cid, text[:match.start()] + prefix + text[match.start():]).eligible


@pytest.mark.parametrize("cid", SAVED)
def test_complete_question_with_unknown_additional_requirement_refuses(cid):
    q = SAVED[cid]["api"]["question"]
    assert not bundle(cid, CANONICAL[cid], q + " Укажи также неизвестную температуру приготовления.").eligible


@pytest.mark.parametrize("cid", SAVED)
def test_repeated_or_cross_section_source_frames_refuse(cid):
    text = CANONICAL[cid]
    assert not bundle(cid, text + " " + text).eligible
    kind = c.family(SAVED[cid]["api"]["question"])
    pattern = {"solvent_reaction_comparison": c.PARTIAL_INTERCALATION,
               "capacity_film_status": c.POSSIBLE_FILM, "electrolyte_formulations": c.FORMULATIONS}[kind]
    match = pattern.search(text)
    assert match is not None
    assert not bundle(cid, text[:match.start()] + "2.9 Another section " + text[match.start():]).eligible


@pytest.mark.parametrize("cid", SAVED)
def test_splicing_across_parents_cannot_supply_a_complete_contract(cid):
    text = CANONICAL[cid]
    first_pattern = {"Kondo_04": c.REACTION_FRAME, "Nambu_10": c.CAPACITY_RESULT, "Peng_01": c.COMPONENT_NAMES}[cid]
    cut = first_pattern.search(text).end()
    originals = [replace(ORIGINAL[cid], text=text[:cut]),
                 replace(ORIGINAL[cid], text=text[cut:], chunk_id="other", citation_id="E99")]
    d = SAVED[cid]
    result = prepare(d["api"]["question"], originals, d["trace"]["retrieval"]["metadata"]["explicit_source_reference"],
                     answer_language="ru")
    assert not result.eligible


@pytest.mark.parametrize("cid", SAVED)
def test_one_complete_parent_remains_valid_even_with_another_incomplete_parent(cid):
    d = SAVED[cid]
    sources = [replace(ORIGINAL[cid], text="Incomplete unrelated paragraph."),
               replace(ORIGINAL[cid], text=CANONICAL[cid], chunk_id="other", citation_id="E99")]
    result = prepare(d["api"]["question"], sources, d["trace"]["retrieval"]["metadata"]["explicit_source_reference"],
                     answer_language="ru")
    assert result.eligible and result.evidence[0].citation_id == "E99"


@pytest.mark.parametrize("cid", ["Nambu_10", "Peng_01"])
def test_unreviewed_raw_drift_does_not_reuse_glyph_aliases(cid):
    assert not bundle(cid, ORIGINAL[cid].text + " ").eligible


@pytest.mark.parametrize("cid", SAVED)
def test_forged_record_or_rendering_does_not_recompute(cid):
    result = bundle(cid)
    payload = json.loads(result.evidence[0].text)
    payload["records"][0]["allowed_claim"] += " Придуманное подтверждение."
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0], text=json.dumps(payload))])


@pytest.mark.parametrize("cid", SAVED)
def test_unknown_constraints_fail_closed_in_actual_service_instead_of_free_answer(cid):
    d = SAVED[cid]
    api = {**d["api"], "question": d["api"]["question"] + " Укажи неизвестную температуру."}
    result, native = replay.run_service(service, api, d["trace"], configure())
    assert not result["generation_reached"] and native is None
    assert result["answer"]["status"] == "insufficient_evidence"


def test_changed_concentrations_and_aliases_bind_to_the_source_instead_of_fixed_paper_answers():
    text = CANONICAL["Peng_01"].replace("1 M LiPF6", "0.7 M LiPF6")
    q = SAVED["Peng_01"]["api"]["question"]
    for old, new in (("EE", "AA"), ("EET", "AAT"), ("FET", "BBT"), ("FFT", "BCT")):
        # Replace whole code tokens, including their labels and query selectors.
        import re
        text, q = re.sub(r"\b" + old + r"\b", new, text), re.sub(r"\b" + old + r"\b", new, q)
    result = bundle("Peng_01", text, q)
    assert result.eligible and result.records[0]["allowed_claim"].count("0.7 M LiPF6") == 4


def test_film_capacity_cycle_and_source_cathode_normalization_are_not_fixed_constants():
    text = CANONICAL["Nambu_10"].replace("120 mA h", "111 mA h").replace("50th cycle", "40th cycle")
    question = SAVED["Nambu_10"]["api"]["question"].replace("50-м", "40-м")
    result = bundle("Nambu_10", text, question)
    assert result.eligible and "111 mA h" in result.records[0]["allowed_claim"]


@pytest.mark.parametrize("cid", SAVED)
def test_unsupported_provider_cannot_fall_back_to_an_unbounded_answer(cid, monkeypatch):
    d = SAVED[cid]
    raw = d["trace"]["retrieval"]
    retrieval = SearchResponse(**{**raw, "results": [SearchResult(**r) for r in raw["results"]]})
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: deepcopy(retrieval))

    class NoFreeAnswer(ExtractiveAnswerProvider):
        def generate(self, *args, **kwargs):
            pytest.fail("Unsupported provider must stop before generation")

    result = service.answer_question(replay.NoDB(), configure(), **d["api"], provider=NoFreeAnswer(max_claims=5))
    assert result.status == "insufficient_evidence"
    assert result.metadata["evidence_adequacy"]["reason"] == "complete_answer_requires_fact_selection_provider"


@pytest.mark.parametrize("cid", SAVED)
@pytest.mark.parametrize("gate", ["concept", "relation"])
def test_complete_source_contract_does_not_override_required_concept_or_relation_gate(cid, gate, monkeypatch):
    original = service.assess_evidence_adequacy

    def missing(*args, **kwargs):
        value = original(*args, **kwargs)
        if gate == "concept":
            return replace(value, adequate=False, reason="missing_required_concepts",
                           required_concepts=replace(value.required_concepts, missing=["constructed_required_concept"]))
        return replace(value, adequate=False, reason="missing_relation_context",
                       relation_requirements={**value.relation_requirements, "missing": ["constructed_required_relation"]})

    monkeypatch.setattr(service, "assess_evidence_adequacy", missing)
    result, native = replay.run_service(service, SAVED[cid]["api"], SAVED[cid]["trace"], configure())
    assert not result["generation_reached"] and native is None
    assert result["trace"]["metadata"]["evidence_adequacy"]["reason"] == "complete_answer_required_fields_or_relations_unresolved"
