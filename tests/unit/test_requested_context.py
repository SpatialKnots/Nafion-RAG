"""Constructed retrieval controls; no measured scientific accuracy claims."""

from dataclasses import replace
from uuid import UUID

import pytest

from app.retrieval.requested_context import body_facets, requested_facets, retain_requested_context
from app.retrieval.search import SearchResult

TABLE_QUERY = "Li-Nafion equilibrium swelling degree and enthalpy of swelling at 25 C?"
CYCLE_QUERY = "Li-Nafion EC/SL mixing temperature: heating and cooling uptake and structural changes?"
TABLE = "Table. Li-Nafion equilibrium swelling (%) and enthalpy of swelling, J/g.\nSample\n−12.3\n27"
CYCLE = "Li-Nafion EC/SL mixing temperature and solvent uptake upon heating and cooling. Values retained at equilibrium."
STRUCTURE = "Li-Nafion EC/SL plasticiser: diffraction, amorphous and crystalline regions, glass transition, Tg and halo."


def row(number, text, *, article=1):
    return SearchResult(article_id=str(UUID(int=article)), chunk_id=str(UUID(int=number)), title="Synthetic control",
                        doi=None, page_start=number, page_end=number, source_type="body", text_layer="original",
                        snippet=text, full_text=text, score=1 / number, retrieval_method="constructed")


@pytest.mark.parametrize("query,expected", [
    (TABLE_QUERY, ("equilibrium_swelling_enthalpy_table",)),
    ("Li-Nafion: равновесная степень набухания и энтальпия набухания?", ("equilibrium_swelling_enthalpy_table",)),
    (CYCLE_QUERY, ("mixing_uptake_cycles", "plasticised_structure")),
    ("Как температура смешения EC/SL влияет на Li-Nafion при нагревании, охлаждении и на структуру?",
     ("mixing_uptake_cycles", "plasticised_structure")),
    ("H-Nafion equilibrium swelling and enthalpy?", ()),
    ("Li-Nafion enthalpy?", ()),
    ("Li-Nafion heating and cooling?", ()),
])
def test_bounded_query_families(query, expected):
    assert requested_facets(query) == expected


def test_table_kept_before_cut_without_mutation():
    distractors = [row(i, "Li-Nafion discussion.") for i in range(1, 12)]
    table = row(20, TABLE)
    original = [*distractors, table]
    result, metadata = retain_requested_context(TABLE_QUERY, original, limit=5)
    assert result[0] is table
    assert result[1:] == distractors
    assert original == [*distractors, table]
    assert metadata["missing_facets"] == []
    assert metadata["scientific_ownership_verified"] is False
    assert table.full_text == TABLE
    assert table.page_start == 20 and table.score == 1 / 20


@pytest.mark.parametrize("text", [
    "Table. Li-Nafion equilibrium swelling (%) and cohesion energy, εcoh, kJ/mol.",
    TABLE.replace("Li-Nafion", "H-Nafion"),
    TABLE.replace("Li-Nafion", "PBI"),
    TABLE.replace("J/g", "kJ/mol"),
    TABLE.replace("equilibrium swelling (%)", "solvent dielectric permittivity"),
    "Li-Nafion equilibrium swelling and enthalpy of swelling.",
])
def test_wrong_quantity_or_material_does_not_reserve_table(text):
    result, metadata = retain_requested_context(TABLE_QUERY, [row(1, text)], limit=5)
    assert metadata is None and len(result) == 1


def test_title_alone_does_not_supply_facets():
    control = replace(row(1, "Unrelated results."), title=TABLE)
    _, metadata = retain_requested_context(TABLE_QUERY, [control], limit=5)
    assert metadata is None


def test_both_cycle_and_structure_kept_from_one_work():
    unrelated = [row(1, "Li-Nafion EC/SL conductivity.")]
    cycle, structure = row(2, CYCLE), row(3, STRUCTURE)
    result, metadata = retain_requested_context(CYCLE_QUERY, [*unrelated, structure, cycle], limit=2)
    assert result[:2] == [cycle, structure]
    assert metadata["missing_facets"] == []


def test_cross_article_facets_never_declared_complete():
    cycle, structure = row(2, CYCLE), row(3, STRUCTURE, article=2)
    _, metadata = retain_requested_context(CYCLE_QUERY, [cycle, structure], limit=5)
    assert metadata["missing_facets"] == ["plasticised_structure"]
    assert metadata["reserved_chunk_ids"] == [cycle.chunk_id]


def test_low_top_k_preserves_explicit_incompleteness():
    result, metadata = retain_requested_context(CYCLE_QUERY, [row(1, CYCLE), row(2, STRUCTURE)], limit=1)
    assert len(result[:1]) == 1
    assert metadata["missing_facets"] == ["plasticised_structure"]


def test_abstract_cycle_mention_without_measured_context_does_not_qualify():
    abstract = "Li-Nafion EC/SL mixing temperature: solvent uptake shows hysteresis between heating and cooling modes."
    assert "mixing_uptake_cycles" not in body_facets(abstract, requested_facets(CYCLE_QUERY))


def test_observed_null_stays_source_context_not_an_absent_experiment():
    text = CYCLE + " Isothermal treatment did not change the obtained uptake."
    assert "mixing_uptake_cycles" in body_facets(text, requested_facets(CYCLE_QUERY))


def test_inactive_question_exact_order_and_metadata_preserved():
    original = [row(1, TABLE), row(2, CYCLE)]
    result, metadata = retain_requested_context("Nafion conductivity?", original, limit=1)
    assert result == original and result[0] is original[0] and metadata is None


def test_invalid_limit_fails():
    with pytest.raises(ValueError, match="positive"):
        retain_requested_context(TABLE_QUERY, [], limit=0)
