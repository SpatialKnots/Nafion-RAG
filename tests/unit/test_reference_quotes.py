"""Constructed quotations and values; not measured scientific evidence."""

import json
from dataclasses import replace

import pytest

from app.generation.lithiation_overview import allowed_claims, validate_claims
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.reference_quotes import prepare, validate_complete, verify_raw_binding

COMPOSITION_QUERY = ("Каков состав разработанного Smith и Jones (2021) электролита с фторированным эфиром и карбонатами "
                     "и какие результаты циклирования были получены с ним в ячейках Li‖FePO₄ и Li‖Ag?")
PREPARATION_QUERY = ("Каким способом Smith и соавторы (2021) получили не содержащую этанола водную дисперсию "
                     "Nafion-120 (образец c2) и какова была протонная проводимость мембраны, изготовленной из этой "
                     "дисперсии, в сравнении с мембраной из коммерческой дисперсии XYZ?")
ABSTRACT = ("Smith and Jones 2021\nABSTRACT: A fluorinated ether and carbonate electrolyte contains 0.7 M salt at 2:3:4 by volume. "
            "Li||FePO4 batteries retain 71% after 43 cycles at 3 mA g−1 and 3.2 V. "
            "Li||Ag cells retain 83% after 29 times at 4 mA cm−2.\nKEYWORDS: synthetic control.\n")
METHOD = ("Smith and Jones 2021\nDissolution procedures\nNafion-120 in water and ethanol was heated at 423 K for two hours. "
          "Ethanol-free Nafion dispersion (c2 sample) was prepared by azeotropic distillation.\nNafion recast film\n")
TABLE = ("Smith and Jones 2021\nTab. 8.\nSynthetic EIS analysis.\nSample\nConductivity\nS · cm−1\nWater content\nwt.-%\n"
         "XYZ\n0.013\n12\nSample c2a)\n0.072\n21\na) Synthetic sample footnote.\nFig. 9.\n")
META = {"resolved": True, "article_id": "work"}


def evidence(text, citation="E1", article="work"):
    return Evidence(citation_id=citation, article_id=article, chunk_id="chunk-" + citation, title="Synthetic source",
                    doi=None, page_start=1, page_end=1, source_type="body", text=text, score=1.0,
                    retrieval_method="constructed", method_scores={}, method_ranks={})


def packet():
    return prepare(PREPARATION_QUERY, [evidence(METHOD), evidence(TABLE, "E2")], META)


def test_composition_contract_exact_raw_span_and_allowed_claim():
    result = prepare(COMPOSITION_QUERY, [evidence(ABSTRACT)], META)
    assert result.eligible and len(result.records) == 1
    record = result.records[0]
    span = record["raw_span"]
    assert ABSTRACT[span["start"]:span["end"]] == span["text"]
    assert "71%" in record["allowed_claim"] and "43 cycles" in record["allowed_claim"]
    assert result.display[0].text == ABSTRACT
    assert not record["scientific_ownership_verified"]
    verify_raw_binding(result.evidence[0].text, ABSTRACT, article_id="work", chunk_id="chunk-E1", citation_id="E1")


def test_complete_method_table_contract_keeps_units_conditions_and_footnote():
    result = packet()
    assert result.eligible and len(result.records) == 2
    text = "\n".join(r["allowed_claim"] for r in result.records)
    assert "423 K" in text and "two hours" in text and "0.072" in text and "21" in text
    assert "S · cm−1" in text and "a) Synthetic sample footnote." in text
    assert {r["role"] for r in result.records} == {"method", "table"}


@pytest.mark.parametrize("query", [COMPOSITION_QUERY + " при 35 °C", PREPARATION_QUERY + " после 50 циклов",
                                   COMPOSITION_QUERY.replace("были получены", "не были получены")])
def test_extra_constraints_block_instead_of_being_dropped(query):
    result = prepare(query, [evidence(ABSTRACT), evidence(METHOD, "E2"), evidence(TABLE, "E3")], META)
    assert not result.eligible and result.reason == "unsupported_explicit_reference_constraint"


@pytest.mark.parametrize("abstract", [ABSTRACT.replace("Li||Ag", "Li||Cu"), ABSTRACT.replace("KEYWORDS:", "BROKEN:"),
                                       ABSTRACT.replace("71%", "unknown"), ABSTRACT.replace("0.7 M", "unspecified"),
                                       ABSTRACT.replace("by volume", "unknown basis"),
                                       ABSTRACT.replace("fluorinated", "ordinary"),
                                       ABSTRACT.replace("retain 71%", "will retain 71%")])
def test_missing_cell_condition_boundary_or_future_does_not_admit(abstract):
    assert not prepare(COMPOSITION_QUERY, [evidence(abstract)], META).eligible


@pytest.mark.parametrize("method,table", [
    (METHOD.replace("c2 sample", "d2 sample"), TABLE),
    (METHOD.replace("Nafion-120", "Nafion-117"), TABLE),
    (METHOD.replace("was prepared", "was not prepared"), TABLE),
    (METHOD.replace("was prepared", "will be prepared"), TABLE),
    (METHOD.replace("azeotropic distillation", "unknown method"), TABLE),
    (METHOD, TABLE.replace("S · cm−1", "unreported units")),
    (METHOD, TABLE.replace("XYZ\n0.013", "OTHER\n0.013")),
    (METHOD, TABLE.replace("a) Synthetic sample footnote.\n", "")),
    (METHOD, TABLE.replace("Water content", "Unknown column")),
    (METHOD, TABLE.replace("Fig. 9.", "broken ending")),
])
def test_incomplete_or_misattributed_preparation_table_blocks(method, table):
    assert not prepare(PREPARATION_QUERY, [evidence(method), evidence(table, "E2")], META).eligible


def test_source_roles_never_join_across_articles_or_unresolved_reference():
    assert not prepare(PREPARATION_QUERY, [evidence(METHOD), evidence(TABLE, "E2", "other")], META).eligible
    assert not prepare(COMPOSITION_QUERY, [evidence(ABSTRACT)], {"resolved": False}).eligible


@pytest.mark.parametrize("raw", [ABSTRACT.replace("Smith and Jones", "Smith and Brown"),
                                  ABSTRACT.replace("2021", "2020"), ABSTRACT.replace("Smith and Jones 2021\n", "")])
def test_named_coauthors_year_and_front_matter_required(raw):
    result = prepare(COMPOSITION_QUERY, [evidence(raw)], META)
    assert not result.eligible and result.reason == "explicit_authors_not_bound_to_source_front_matter"


def test_later_bibliography_does_not_supply_author_identity():
    result = prepare(COMPOSITION_QUERY, [replace(evidence(ABSTRACT), page_start=8, page_end=8)], META)
    assert not result.eligible


@pytest.mark.parametrize("query,raws", [
    ("What composition of the fluorinated ether electrolyte and cycling results were obtained in Li‖FePO₄ and Li‖Ag cells "
     "in Smith and Jones (2021)?", [ABSTRACT]),
    ("How was ethanol free Nafion-120 water dispersion sample c2 prepared in Smith (2021), and what proton conductivity "
     "comparison with the commercial dispersion XYZ was obtained?", [METHOD, TABLE]),
])
def test_supported_english_question_forms(query, raws):
    result = prepare(query, [evidence(raw, f"E{i}") for i, raw in enumerate(raws, 1)], META)
    assert result.eligible


def test_different_abstracts_are_ambiguous_but_identical_overlaps_are_not():
    assert not prepare(COMPOSITION_QUERY, [evidence(ABSTRACT), evidence(ABSTRACT.replace("71%", "72%"), "E2")], META).eligible
    assert prepare(COMPOSITION_QUERY, [evidence(ABSTRACT), evidence(ABSTRACT, "E2")], META).eligible


def test_same_parent_can_hold_both_roles_without_duplicate_citations():
    result = prepare(PREPARATION_QUERY, [evidence(METHOD + TABLE)], META)
    assert result.eligible and len(result.evidence) == 1
    assert len(allowed_claims(result.evidence)["E1"]) == 2


def test_partial_selection_paraphrase_or_wrong_citation_fails():
    result = packet()
    claims = [GeneratedClaim(r["allowed_claim"], [r["citation_id"]]) for r in result.records]
    validate_claims(claims, allowed_claims(result.evidence))
    validate_complete(claims, result)
    with pytest.raises(GenerationOutputError, match="every required"):
        validate_complete(claims[:1], result)
    for altered in (replace(claims[0], text="Conductivity is 999."), replace(claims[0], citation_ids=["unknown"])):
        with pytest.raises(GenerationOutputError, match="exact"):
            validate_claims([altered], allowed_claims(result.evidence))


@pytest.mark.parametrize("change", ["text", "claim", "hash", "citation", "parent"])
def test_tampered_raw_contract_fails(change):
    result = packet()
    payload = json.loads(result.evidence[0].text)
    record = payload["records"][0]
    if change == "text":
        record["raw_span"]["text"] += " unsupported"
    elif change == "claim":
        record["allowed_claim"] = "Unsupported claim"
    elif change == "hash":
        record["raw_chunk_sha256"] = "0" * 64
    elif change == "citation":
        record["citation_id"] = "other"
    else:
        record["chunk_id"] = "other"
    with pytest.raises(ValueError, match="differs"):
        verify_raw_binding(json.dumps(payload), METHOD, article_id="work", chunk_id="chunk-E1", citation_id="E1")
