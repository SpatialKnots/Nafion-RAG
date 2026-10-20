from __future__ import annotations

import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.evaluation.retrieval import ExtendedEvaluationQuestion, _evaluate_extended_question
from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.evidence_selection import select_answer_evidence
from app.generation.providers import (
    SCIENTIFIC_ANSWER_SYSTEM_PROMPT,
    Evidence,
    ExtractiveAnswerProvider,
    GeneratedClaim,
    GenerationOutputError,
    GenerationUnavailableError,
    OpenAIAnswerProvider,
    ProviderResult,
)
from app.generation.service import (
    answer_question,
    answer_response_to_dict,
    build_answer_provider,
    normalize_answer_language,
    normalize_answer_style,
)
from app.retrieval.search import SearchResponse, SearchResult


def test_answer_gate_blocks_provider_when_required_material_is_absent(monkeypatch) -> None:
    result = replace(_search_result(), snippet="Nafion acid anhydrous composite fuel cells.")
    monkeypatch.setattr("app.generation.service.search_chunks", lambda *a, **kw: SearchResponse(query="PBI", results=[result]))

    class ForbiddenProvider:
        def generate(self, *args, **kwargs):
            pytest.fail("Provider must not run with missing required concepts")

    response = answer_question(
        object(),
        _settings(),
        "PBI phosphoric acid Nafion composite anhydrous fuel cells",  # type: ignore[arg-type]
        provider=ForbiddenProvider(),  # type: ignore[arg-type]
    )
    assert response.status == "insufficient_evidence"
    assert response.claims == []
    diagnostics = response.metadata["evidence_adequacy"]
    assert diagnostics["reason"] == "missing_required_concepts"
    assert diagnostics["required_concepts"]["missing"] == ["polybenzimidazole", "phosphoric_acid"]

    evaluation = _evaluate_extended_question(
        ExtendedEvaluationQuestion("pbi_control", response.query, [], [], answerable=False),
        SearchResponse(query=response.query, results=[result]),
        {},
        elapsed_ms=0,
        top_k=10,
    )
    assert evaluation["unanswerable_passed"] is True
    assert evaluation["evidence_adequacy"]["required_concepts"] == diagnostics["required_concepts"]


def test_answer_question_returns_source_linked_extractive_claims(monkeypatch) -> None:
    search_result = _search_result()
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="How was conductivity measured?",
            results=[search_result],
            metadata={"fusion": "reciprocal_rank_fusion"},
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "How was conductivity measured?",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )
    payload = answer_response_to_dict(response)

    assert response.status == "answered"
    assert response.answer == "Conductivity was measured by impedance spectroscopy. [E1]"
    assert payload["citations"][0]["chunk_id"] == search_result.chunk_id  # type: ignore[index]
    assert payload["citations"][0]["page_start"] == 2  # type: ignore[index]
    assert payload["citations"][0]["pdf_page_url"] == f"/articles/{search_result.article_id}/pdf?layer=original#page=2"  # type: ignore[index]
    assert payload["citations"][0]["context_url"].endswith("?before=1&after=1")  # type: ignore[index]
    assert payload["citations"][0]["method_ranks"] == {"exact_ilike": 1, "semantic_cosine": 2}  # type: ignore[index]


def test_answer_question_uses_full_text_as_generation_evidence(monkeypatch) -> None:
    search_result = _search_result()
    search_result = SearchResult(
        article_id=search_result.article_id,
        chunk_id=search_result.chunk_id,
        title=search_result.title,
        doi=search_result.doi,
        page_start=search_result.page_start,
        page_end=search_result.page_end,
        source_type="table",
        snippet="Truncated table row with DMF.",
        full_text="Full table text: DMF row separates temperature range and conductivity at 25 C.",
        score=search_result.score,
        retrieval_method=search_result.retrieval_method,
    )
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="Nafion conductivity in DMF",
            results=[search_result],
            metadata={"fusion": "reciprocal_rank_fusion"},
        ),
    )

    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="The full table separates these values.", citation_ids=["E1"])],
            provider="test",
            model="test-model",
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Nafion conductivity in DMF",
        provider=provider,
    )

    assert provider.evidence_texts == ["Full table text: DMF row separates temperature range and conductivity at 25 C."]
    assert response.citations[0].text == "Truncated table row with DMF."


def test_answer_question_uses_display_snippets_for_extractive_provider(monkeypatch) -> None:
    search_result = _search_result()
    search_result = SearchResult(
        article_id=search_result.article_id,
        chunk_id=search_result.chunk_id,
        title=search_result.title,
        doi=search_result.doi,
        page_start=search_result.page_start,
        page_end=search_result.page_end,
        source_type="body",
        snippet="Small-angle X-ray scattering found ionic clusters in hydrated Nafion.",
        full_text=(
            "Small-angle X-ray scattering found ionic clusters in hydrated Nafion. "
            + "Long OCR body text unrelated to the displayed answer. " * 50
        ),
        score=search_result.score,
        retrieval_method=search_result.retrieval_method,
    )
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="small-angle X-ray scattering Nafion",
            results=[search_result],
            metadata={"fusion": "reciprocal_rank_fusion"},
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "small-angle X-ray scattering Nafion",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "answered"
    assert response.answer == "Small-angle X-ray scattering found ionic clusters in hydrated Nafion. [E1]"
    assert "Long OCR body text" not in response.answer


def test_answer_question_displays_marker_centered_citation_excerpt(monkeypatch) -> None:
    search_result = _search_result()
    search_result = SearchResult(
        article_id=search_result.article_id,
        chunk_id=search_result.chunk_id,
        title=search_result.title,
        doi=search_result.doi,
        page_start=search_result.page_start,
        page_end=search_result.page_end,
        source_type="table",
        snippet="Opening background that does not contain the table.",
        full_text=(
            "Opening background that does not contain the requested values. "
            "Table 4.6 reports Li-Nafion conductivity in plasticized membranes with DMF, DMSO, and NMP."
        ),
        score=search_result.score,
        retrieval_method=search_result.retrieval_method,
    )
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="Li-Nafion conductivity in plasticizers", results=[search_result]),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="The table reports conductivity.", citation_ids=["E1"])],
            provider="test",
            model=None,
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Li-Nafion conductivity in plasticizers",
        provider=provider,
    )

    assert provider.evidence_texts[0].startswith("Opening background")
    assert "Table 4.6 reports Li-Nafion conductivity" in response.citations[0].text


def test_answer_question_passes_mini_review_style_to_provider(monkeypatch) -> None:
    search_result = _search_result()
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="Nafion conductivity", results=[search_result]),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="Evidence paper reports conductivity.", citation_ids=["E1"])],
            provider="test",
            model="test-model",
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Nafion conductivity",
        answer_style="mini_review",
        provider=provider,
    )

    assert provider.answer_style == "mini_review"
    assert response.metadata["answer_style"] == "mini_review"


def test_answer_question_merges_mini_review_claims_by_article(monkeypatch) -> None:
    first_article_id = str(uuid.UUID(int=41))
    second_article_id = str(uuid.UUID(int=42))
    results = [
        SearchResult(
            article_id=first_article_id,
            chunk_id=str(uuid.UUID(int=43)),
            title="Nafion casting paper",
            doi="10.1000/casting",
            page_start=2,
            page_end=2,
            source_type="body",
            snippet="Nafion conductivity was measured after solution casting.",
            full_text="Nafion conductivity was measured after solution casting.",
            score=0.03,
            retrieval_method="hybrid_rrf",
        ),
        SearchResult(
            article_id=first_article_id,
            chunk_id=str(uuid.UUID(int=44)),
            title="Nafion casting paper",
            doi="10.1000/casting",
            page_start=4,
            page_end=4,
            source_type="body",
            snippet="Nafion morphology changed with solvent composition.",
            full_text="Nafion morphology changed with solvent composition.",
            score=0.02,
            retrieval_method="hybrid_rrf",
        ),
        SearchResult(
            article_id=second_article_id,
            chunk_id=str(uuid.UUID(int=45)),
            title="Second Nafion paper",
            doi="10.1000/second",
            page_start=1,
            page_end=1,
            source_type="body",
            snippet="A separate Nafion study reports conductivity trends.",
            full_text="A separate Nafion study reports conductivity trends.",
            score=0.01,
            retrieval_method="hybrid_rrf",
        ),
    ]
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="Nafion conductivity morphology", results=results),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[
                GeneratedClaim(text="The casting paper reports conductivity.", citation_ids=["E1"]),
                GeneratedClaim(text="The casting paper also reports morphology.", citation_ids=["E2"]),
                GeneratedClaim(text="The second paper reports a separate trend.", citation_ids=["E3"]),
            ],
            provider="openai",
            model="test-model",
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Nafion conductivity morphology",
        answer_style="mini_review",
        provider=provider,
    )

    assert response.claims == [
        GeneratedClaim(
            text="The casting paper reports conductivity. The casting paper also reports morphology.",
            citation_ids=["E1", "E2"],
        ),
        GeneratedClaim(text="The second paper reports a separate trend.", citation_ids=["E3"]),
    ]
    assert response.answer == (
        "The casting paper reports conductivity. The casting paper also reports morphology. [E1] [E2]\n\n"
        "The second paper reports a separate trend. [E3]"
    )


def test_answer_question_passes_answer_language_to_provider(monkeypatch) -> None:
    search_result = _search_result()
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="Nafion conductivity", results=[search_result]),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="Данные подтверждают проводимость.", citation_ids=["E1"])],
            provider="test",
            model="test-model",
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Nafion conductivity",
        answer_language="ru",
        provider=provider,
    )

    assert provider.answer_language == "ru"
    assert response.metadata["answer_language"] == "ru"


def test_normalize_answer_style_rejects_unknown_style() -> None:
    with pytest.raises(ValueError, match="answer_style"):
        normalize_answer_style("narrative")


def test_normalize_answer_language_rejects_unknown_language() -> None:
    with pytest.raises(ValueError, match="answer_language"):
        normalize_answer_language("de")


def test_evidence_adequacy_reports_concept_coverage() -> None:
    adequacy = assess_evidence_adequacy(
        "How does Li-Nafion swelling depend on water?",
        [_evidence("Литированный Nafion показывает набухание; вода здесь не обсуждается как сорбция.")],
        concept_terms={
            "swelling": {"en": ["swelling"], "ru": ["набухание"]},
            "water_interaction": {"en": ["water"], "ru": ["вода"]},
        },
    )

    coverage = adequacy.concept_coverage
    assert coverage["matched"] == ["swelling", "water_interaction"]
    assert coverage["missing"] == []


def test_evidence_adequacy_accepts_inflected_russian_plasticizer_conductivity_query() -> None:
    adequacy = assess_evidence_adequacy(
        "В каких пластификаторах наибольшую проводимость дают Li-Nafion",
        [
            _evidence(
                "The best transport properties of Li-Nafion provided EC/SL mixtures enriched "
                "with ethylene carbonate. Conductivity was shown for the binary plasticiser."
            )
        ],
    )

    assert adequacy.adequate is True
    assert "пластификаторах" in adequacy.matched_terms
    assert "наибольшую" in adequacy.matched_terms


def test_evidence_adequacy_accepts_cross_lingual_concept_coverage() -> None:
    adequacy = assess_evidence_adequacy(
        "Nafion зависимость морфологии от природы растворителя при получении плёнок",
        [
            _evidence(
                "Morphology and properties of Nafion membranes prepared by solution casting "
                "depend on solvent processing conditions."
            )
        ],
        concept_terms={
            "solution_casting_morphology": {
                "en": ["nafion membranes prepared by solution casting", "solution casting"],
                "ru": ["природа растворителя морфология плёнок"],
            }
        },
    )

    assert adequacy.adequate is True
    assert adequacy.reason == "sufficient_concept_coverage"
    assert adequacy.concept_coverage["matched"] == ["solution_casting_morphology"]


def test_answer_question_refuses_when_retrieval_returns_no_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="unknown", results=[]),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "unknown",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "insufficient_evidence"
    assert response.answer is None
    assert response.citations == []


def test_answer_question_refuses_when_evidence_lacks_distinctive_terms(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="zirconium cerium extraterrestrial regolith perchlorate electrolyte",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="Unrelated paper",
                    doi=None,
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="Nafion conductivity in polymer membranes.",
                    score=1.0,
                    retrieval_method="exact_ilike",
                )
            ],
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "zirconium cerium extraterrestrial regolith perchlorate electrolyte",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "insufficient_evidence"
    assert response.claims == []
    assert response.metadata["evidence_adequacy"]["adequate"] is False  # type: ignore[index]


def test_answer_question_refuses_when_short_scientific_term_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="Nafion conductivity in DMF",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="Water-cast Nafion paper",
                    doi=None,
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="Recast Nafion-117 thin film from water solution shows thermogravimetric decomposition.",
                    score=1.0,
                    retrieval_method="hybrid_rrf",
                )
            ],
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Nafion conductivity in DMF",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "insufficient_evidence"
    assert response.claims == []
    assert response.metadata["evidence_adequacy"]["distinctive_terms"] == ["nafion", "conductivity", "dmf"]  # type: ignore[index]
    assert response.metadata["evidence_adequacy"]["matched_terms"] == ["nafion"]  # type: ignore[index]


def test_answer_question_suggests_domain_typo_correction(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="What protocol of Nafion litation",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="Li-Nafion protocol paper",
                    doi=None,
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="Nafion membranes were converted to the lithium form before conductivity measurements.",
                    full_text="Nafion membranes were converted to the lithium form before conductivity measurements.",
                    score=1.0,
                    retrieval_method="hybrid_rrf",
                )
            ],
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "What protocol of Nafion litation",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assistance = response.metadata["query_assistance"]  # type: ignore[index]
    assert response.status == "insufficient_evidence"
    assert assistance["corrected_query"] == "What protocol of Nafion lithiation"  # type: ignore[index]
    assert assistance["corrections"][0]["original"] == "litation"  # type: ignore[index]
    assert assistance["corrections"][0]["suggestion"] == "lithiation"  # type: ignore[index]


def test_answer_question_suggests_hyphenated_domain_typo_correction(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="Li-Nafeon membrane litation pratocole",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="Li-Nafion protocol paper",
                    doi=None,
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="Li-Nafion lithiation protocol evidence.",
                    full_text="Li-Nafion lithiation protocol evidence.",
                    score=1.0,
                    retrieval_method="hybrid_rrf",
                )
            ],
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Li-Nafeon membrane litation pratocole",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assistance = response.metadata["query_assistance"]  # type: ignore[index]
    assert assistance["corrected_query"] == "Li-Nafion membrane lithiation protocol"  # type: ignore[index]
    assert {item["original"]: item["suggestion"] for item in assistance["corrections"]} == {  # type: ignore[index]
        "nafeon": "Nafion",
        "litation": "lithiation",
        "pratocole": "protocol",
    }


def test_answer_question_allows_domain_synonyms_for_lithiation_protocol(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="Li-Nafion membrane lithiation protocol",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="Sanginov 2021",
                    doi="10.1016/j.electacta.2021.137914",
                    page_start=3,
                    page_end=3,
                    source_type="method",
                    snippet="Experimental section reports Li-Nafion membranes swelled with EC/SL mixtures.",
                    full_text="2. Experimental. A commercial Nafion membrane was prepared as Li-Nafion and swelled with EC/SL mixtures.",
                    score=1.0,
                    retrieval_method="hybrid_rrf",
                )
            ],
        ),
    )
    provider = StaticProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="The evidence describes Li-Nafion preparation in the experimental section.", citation_ids=["E1"])],
            provider="test",
            model=None,
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Li-Nafion membrane lithiation protocol",
        provider=provider,
    )

    assert response.status == "answered"
    assert response.metadata["evidence_adequacy"]["matched_terms"] == ["li-nafion", "lithiation", "protocol"]  # type: ignore[index]


def test_answer_question_prioritizes_article_with_full_distinctive_term_coverage(monkeypatch) -> None:
    ma_article = str(uuid.UUID(int=1))
    dai_article = str(uuid.UUID(int=2))
    sanginov_article = str(uuid.UUID(int=3))
    retrieval_results = [
        SearchResult(
            article_id=ma_article,
            chunk_id=str(uuid.UUID(int=11)),
            title="Ma 2009 Nafion membranes prepared by solution casting",
            doi=None,
            page_start=1,
            page_end=1,
            source_type="method",
            snippet="Nafion membranes were prepared by solution casting.",
            full_text="Nafion membranes were prepared by solution casting.",
            score=0.04,
            retrieval_method="hybrid_rrf",
        ),
        SearchResult(
            article_id=dai_article,
            chunk_id=str(uuid.UUID(int=12)),
            title="Dai 2017 recast Nafion membranes",
            doi=None,
            page_start=8,
            page_end=8,
            source_type="table",
            snippet="Recast Nafion membranes prepared from DMF solvent showed selectivity.",
            full_text="Recast Nafion membranes prepared from DMF solvent showed selectivity.",
            score=0.03,
            retrieval_method="hybrid_rrf",
        ),
        SearchResult(
            article_id=sanginov_article,
            chunk_id=str(uuid.UUID(int=13)),
            title="Sanginov 2021",
            doi="10.1016/j.electacta.2021.137914",
            page_start=3,
            page_end=3,
            source_type="method",
            snippet="Experimental section reports Li-Nafion membranes swelled with EC/SL mixtures.",
            full_text="2. Experimental. A commercial Nafion membrane was prepared as Li-Nafion and swelled with EC/SL mixtures.",
            score=0.02,
            retrieval_method="hybrid_rrf",
        ),
        SearchResult(
            article_id=sanginov_article,
            chunk_id=str(uuid.UUID(int=14)),
            title="Sanginov 2021",
            doi="10.1016/j.electacta.2021.137914",
            page_start=3,
            page_end=3,
            source_type="table",
            snippet="Li-Nafion conductivity table.",
            full_text="Li-Nafion membranes were converted to the lithium form before conductivity measurements.",
            score=0.01,
            retrieval_method="hybrid_rrf",
        ),
    ]
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="Li-Nafion membrane lithiation protocol",
            results=retrieval_results,
            metadata={"fusion": "reciprocal_rank_fusion"},
        ),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="Sanginov evidence describes Li-Nafion preparation.", citation_ids=["E1"])],
            provider="test",
            model=None,
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Li-Nafion membrane lithiation protocol",
        provider=provider,
    )

    selection = response.metadata["answer_evidence_selection"]  # type: ignore[index]
    assert response.status == "answered"
    assert provider.evidence_texts[0].startswith("2. Experimental.")
    assert response.citations[0].title == "Sanginov 2021"
    assert selection["reordered"] is True  # type: ignore[index]
    assert selection["article_term_coverage"][2]["matched_terms"] == ["li-nafion", "lithiation", "protocol"]  # type: ignore[index]


def test_answer_question_prioritizes_specific_plasticizer_conductivity_evidence(monkeypatch) -> None:
    article_id = str(uuid.UUID(int=1))
    background = SearchResult(
        article_id=article_id,
        chunk_id=str(uuid.UUID(int=11)),
        title="Диссертация Чернюк С.Д.",
        doi=None,
        page_start=28,
        page_end=29,
        source_type="method",
        snippet="Li-Nafion применяют в ЛИА; растворы солей лития в карбонатах имеют биполярный перенос заряда.",
        full_text="Li-Nafion применяют в ЛИА; растворы солей лития в карбонатах имеют биполярный перенос заряда.",
        score=0.04,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    table = SearchResult(
        article_id=article_id,
        chunk_id=str(uuid.UUID(int=12)),
        title="Диссертация Чернюк С.Д.",
        doi=None,
        page_start=107,
        page_end=109,
        source_type="table",
        snippet="Таблица 4.6 — Ионная проводимость мембраны Li-Nafion при 25 °C.",
        full_text=(
            "Таблица 4.6 — Ионная проводимость мембраны Li-Nafion при 25 °C, "
            "пластифицированных растворителями различной природы. DMF, DMSO, NMP, "
            "NMF and DMAA show highest ionic conductivities."
        ),
        score=0.03,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="В каких пластификаторах наибольшую проводимость дают Li-Nafion",
            results=[background, table],
            metadata={
                "cross_lingual": {
                    "variants": [
                        {"text": "ionic conductivity binary plasticiser li-nafion"},
                    ],
                    "matched_concepts": ["lithium_form", "transport", "plasticizers"],
                }
            },
        ),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="The table gives the solvent conductivity comparison.", citation_ids=["E1"])],
            provider="test",
            model=None,
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "В каких пластификаторах наибольшую проводимость дают Li-Nafion",
        method="hybrid_cross_lingual",
        provider=provider,
    )

    selection = response.metadata["answer_evidence_selection"]  # type: ignore[index]
    assert response.status == "answered"
    assert provider.evidence_texts[0].startswith("Таблица 4.6")
    assert response.citations[0].chunk_id == table.chunk_id
    assert selection["conductivity_plasticizer_intent"] is True  # type: ignore[index]
    assert selection["conductivity_plasticizer_result_count"] == 1  # type: ignore[index]
    assert selection["filtered_to_conductivity_plasticizer_evidence"] is True  # type: ignore[index]
    assert [citation.chunk_id for citation in response.citations] == [table.chunk_id]


def test_answer_question_uses_cross_lingual_variant_terms_for_evidence_selection(monkeypatch) -> None:
    dissertation = SearchResult(
        article_id=str(uuid.UUID(int=10)),
        chunk_id=str(uuid.UUID(int=11)),
        title="Диссертация Чернюк С.Д.",
        doi=None,
        page_start=48,
        page_end=48,
        source_type="method",
        snippet="Рассмотрено влияние ионов лития на термодинамические и релаксационные свойства мембран Nafion.",
        full_text="Рассмотрено влияние ионов лития на термодинамические и релаксационные свойства мембран Nafion.",
        score=0.01,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    english_paper = SearchResult(
        article_id=str(uuid.UUID(int=12)),
        chunk_id=str(uuid.UUID(int=13)),
        title="English Nafion paper",
        doi="10.1000/english",
        page_start=1,
        page_end=1,
        source_type="body",
        snippet="Nafion membranes contain ions and thermodynamic relaxation evidence.",
        full_text="Nafion membranes contain ions and thermodynamic relaxation evidence.",
        score=0.02,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="How do lithium ions affect thermodynamic and relaxation properties of Nafion membranes?",
            results=[english_paper, dissertation],
            metadata={
                "cross_lingual": {
                    "variants": [
                        {
                            "text": "How do lithium ions affect thermodynamic and relaxation properties of Nafion membranes?",
                            "language": "en",
                            "source": "original",
                        },
                        {
                            "text": "ионы лития термодинамические релаксационные свойства",
                            "language": "ru",
                            "source": "glossary",
                        },
                    ]
                }
            },
        ),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="The dissertation has the cross-lingual evidence.", citation_ids=["E1"])],
            provider="test",
            model=None,
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "How do lithium ions affect thermodynamic and relaxation properties of Nafion membranes?",
        provider=provider,
    )

    assert response.status == "answered"
    assert provider.evidence_texts[0].startswith("Рассмотрено влияние")
    assert response.citations[0].title == "Диссертация Чернюк С.Д."


def test_answer_question_deduplicates_near_duplicate_article_evidence(monkeypatch) -> None:
    article_id = str(uuid.UUID(int=30))
    first = SearchResult(
        article_id=article_id,
        chunk_id=str(uuid.UUID(int=31)),
        title="Moore and Martin 1988",
        doi=None,
        page_start=3,
        page_end=4,
        source_type="body",
        snippet="Small-angle X-ray scattering found a peak assigned to ionic clusters in hydrated Nafion.",
        full_text=(
            "Wide- and Small-Angle X-ray Studies used small-angle X-ray scattering for Nafion. "
            "A large scattering peak was attributed to ionic clusters in hydrated Nafion."
        ),
        score=0.02,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    duplicate = SearchResult(
        article_id=article_id,
        chunk_id=str(uuid.UUID(int=32)),
        title="Moore and Martin 1988",
        doi=None,
        page_start=3,
        page_end=3,
        source_type="body",
        snippet="Small-angle X-ray scattering found a peak assigned to ionic clusters in hydrated Nafion.",
        full_text=(
            "Wide- and Small-Angle X-ray Studies used small-angle X-ray scattering for Nafion. "
            "A large scattering peak was attributed to ionic clusters in hydrated Nafion."
        ),
        score=0.019,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    other = SearchResult(
        article_id=str(uuid.UUID(int=33)),
        chunk_id=str(uuid.UUID(int=34)),
        title="Welch 2012",
        doi=None,
        page_start=1,
        page_end=2,
        source_type="body",
        snippet="Small angle scattering studies reported Nafion dispersion morphology in solvent systems.",
        full_text="Small angle scattering studies reported Nafion dispersion morphology in solvent systems.",
        score=0.018,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="small-angle X-ray scattering Nafion",
            results=[first, duplicate, other],
            metadata={"fusion": "reciprocal_rank_fusion"},
        ),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[
                GeneratedClaim(text="SAXS evidence supports ionic cluster discussion.", citation_ids=["E1"]),
                GeneratedClaim(text="Additional scattering evidence is available.", citation_ids=["E2"]),
            ],
            provider="openai",
            model="test-model",
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "small-angle X-ray scattering Nafion",
        provider=provider,
    )

    assert response.status == "answered"
    assert len(provider.evidence_texts) == 2
    assert [citation.chunk_id for citation in response.citations] == [first.chunk_id, other.chunk_id]
    deduplication = response.metadata["answer_evidence_deduplication"]  # type: ignore[index]
    assert deduplication["input_count"] == 3  # type: ignore[index]
    assert deduplication["kept_count"] == 2  # type: ignore[index]
    assert deduplication["dropped_count"] == 1  # type: ignore[index]


def test_answer_question_prioritizes_swelling_comparison_table_for_generation() -> None:
    generic = SearchResult(
        article_id=str(uuid.UUID(int=20)),
        chunk_id=str(uuid.UUID(int=21)),
        title="Sanginov 2021",
        doi=None,
        page_start=3,
        page_end=4,
        source_type="method",
        snippet="Li-Nafion membranes were swelled with EC/SL mixtures.",
        full_text="Li-Nafion membranes were swelled with EC/SL mixtures.",
        score=0.02,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    table = SearchResult(
        article_id=str(uuid.UUID(int=22)),
        chunk_id=str(uuid.UUID(int=23)),
        title="Диссертация Чернюк С.Д.",
        doi=None,
        page_start=96,
        page_end=97,
        source_type="body",
        snippet="Таблица 4.5 — Равновесная степень набухания H-Nafion and Li-Nafion.",
        full_text=(
            "Таблица 4.5 — Равновесная степень набухания H-Nafion and Li-Nafion. "
            "Растворитель H-Nafion Li-Nafion αH αLi диметилсульфоксид 0.89 1.12 "
            "N,N-диметилформамид 0.72 1.15 метанол 1.14 1.18 "
            "N-метил-2-пирролидон 0.64 1.37"
        ),
        score=0.01,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    selection = select_answer_evidence(
        "In what solvents Li-Nafion has more swelling degree than H-Nafion?",
        [generic, table],
        additional_queries=["степень набухания αH αLi H-Nafion Li-Nafion"],
    )

    assert selection.results[0].title == "Диссертация Чернюк С.Д."
    assert selection.results[0].full_text.startswith("Таблица 4.5")
    assert selection.metadata["numeric_comparison_intent"] is True
    assert selection.metadata["numeric_table_result_count"] == 1


def test_answer_question_adds_derived_swelling_comparison_evidence(monkeypatch) -> None:
    table = SearchResult(
        article_id=str(uuid.UUID(int=24)),
        chunk_id=str(uuid.UUID(int=25)),
        title="Диссертация Чернюк С.Д.",
        doi=None,
        page_start=96,
        page_end=97,
        source_type="body",
        snippet="Таблица 4.5 — Равновесная степень набухания H-Nafion and Li-Nafion.",
        full_text=(
            "Таблица 4.5 — Равновесная степень набухания H-Nafion and Li-Nafion. "
            "Растворитель H-Nafion Li-Nafion αH ΔH αLi ΔH ацетонитрил 0.14 -0.45 0.12 -0.92 "
            "ацетон 0.38 -2.10 0.27 -1.67 вода 0.38 -0.24 0.35 -0.16 "
            "изопропанол 0.83 -1.62 0.49 -1.81 диметилсульфоксид 0.89 -3.8 1.12 -4.60 "
            "N,N-диметилформамид 0.72 -4.24 1.15 -4.36 метанол 1.14 -0.99 1.18 -1.29 "
            "этанол 1.44 -1.73 1.33 -1.57 N-метил-2-пирролидон 0.64 -5.86 1.37 -6.44"
        ),
        score=0.01,
        retrieval_method="hybrid_cross_lingual_rrf",
    )
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="In what solvents Li-Nafion has more swelling degree than H-Nafion?",
            results=[table],
            metadata={"cross_lingual": {"matched_concepts": ["swelling_degree_comparison"], "variants": []}},
        ),
    )
    provider = CapturingProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="Derived table comparison is available.", citation_ids=["E1"])],
            provider="test",
            model=None,
        )
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Какие растворители дают Li-Nafion большую степень набухания, чем H-Nafion?",
        provider=provider,
    )

    assert provider.evidence_texts[0].startswith("Deterministic row comparison extracted from Table 4.5")
    assert "methanol: alphaLi=1.18 > alphaH=1.14" in provider.evidence_texts[0]
    assert response.citations[0].source_type == "table_derived"
    assert response.metadata["derived_evidence"]["matching_row_count"] == 4  # type: ignore[index]


def test_answer_question_refuses_when_only_solvent_matches(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="Nafion conductivity in DMF",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="DMF morphology paper",
                    doi=None,
                    page_start=1,
                    page_end=1,
                    source_type="table",
                    snippet="Aggregation radii were measured for membranes prepared from DMAc, DMF, and NMF solvents.",
                    score=1.0,
                    retrieval_method="hybrid_rrf",
                )
            ],
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Nafion conductivity in DMF",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "insufficient_evidence"
    assert response.metadata["evidence_adequacy"]["distinctive_terms"] == ["nafion", "conductivity", "dmf"]  # type: ignore[index]
    assert response.metadata["evidence_adequacy"]["matched_terms"] == ["dmf"]  # type: ignore[index]


def test_answer_question_rejects_unknown_generated_citation(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="conductivity measured", results=[_search_result()]),
    )
    provider = StaticProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="Unsupported claim", citation_ids=["E99"])],
            provider="test",
            model="test-model",
        )
    )

    with pytest.raises(GenerationOutputError, match="unknown citations"):
        answer_question(object(), _settings(), "conductivity measured", provider=provider)  # type: ignore[arg-type]


def test_answer_question_rejects_answerable_output_without_claims(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="conductivity measured", results=[_search_result()]),
    )
    provider = StaticProvider(ProviderResult(answerable=True, claims=[], provider="test", model=None))

    with pytest.raises(GenerationOutputError, match="at least one claim"):
        answer_question(object(), _settings(), "conductivity measured", provider=provider)  # type: ignore[arg-type]


def test_build_answer_provider_rejects_unknown_provider() -> None:
    settings = _settings()
    settings.rag_provider = "unknown"

    with pytest.raises(ValueError, match="Supported provider: openai"):
        build_answer_provider(settings)  # type: ignore[arg-type]


def test_openai_provider_requires_api_key() -> None:
    with pytest.raises(GenerationUnavailableError, match="RAG_OPENAI_API_KEY"):
        OpenAIAnswerProvider(
            base_url="https://api.openai.com/v1",
            api_key="",
            model="gpt-4.1-mini",
            timeout_seconds=10,
            max_tokens=100,
        )


def test_openai_provider_parses_structured_claims() -> None:
    provider = OpenAIAnswerProvider(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model="gpt-4.1-mini",
        timeout_seconds=10,
        max_tokens=100,
    )

    result = provider._parse_response(  # noqa: SLF001 - direct parser unit test
        {"choices": [{"message": {"content": '{"answerable":true,"claims":[{"text":"Supported","citation_ids":["E1"]}]}'}}]}
    )

    assert result.answerable is True
    assert result.claims == [GeneratedClaim(text="Supported", citation_ids=["E1"])]
    assert result.provider == "openai"
    assert result.model == "gpt-4.1-mini"


def test_provider_system_prompt_preserves_table_semantics() -> None:
    assert "Do not write citation IDs in claim text" in SCIENTIFIC_ANSWER_SYSTEM_PROMPT
    assert "preserve row and column meaning" in SCIENTIFIC_ANSWER_SYSTEM_PROMPT
    assert "enumerate all supported matching rows" in SCIENTIFIC_ANSWER_SYSTEM_PROMPT
    assert "Compare numeric table cells arithmetically" in SCIENTIFIC_ANSWER_SYSTEM_PROMPT
    assert "Do not merge a temperature range" in SCIENTIFIC_ANSWER_SYSTEM_PROMPT
    assert "at-25-C conductivity columns" in SCIENTIFIC_ANSWER_SYSTEM_PROMPT
    assert "same cited row" in SCIENTIFIC_ANSWER_SYSTEM_PROMPT
    assert "no more than one claim per article/work" in SCIENTIFIC_ANSWER_SYSTEM_PROMPT


def test_extractive_provider_collapses_pdf_line_breaks_in_answer_text() -> None:
    provider = ExtractiveAnswerProvider(max_claims=1)
    result = provider.generate(
        "How large enthalpy of H-Nafion and Li-Nafion swelling in water?",
        [
            _evidence(
                "СLi+,мембр =\n1000\nЭВ ∙൬\n1\nρмембр + αLi\nρр−ль൰\n,\n(4.15)\n"
                "Таким образом,\nконцентрация носителей заряда\nвыше."
            )
        ],
    )

    assert result.answerable is True
    assert result.claims == [
        GeneratedClaim(
            text="СLi+,мембр = 1000 ЭВ ∙൬ 1 ρмембр + αLi ρр−ль൰ , (4.15) Таким образом, концентрация носителей заряда выше.",
            citation_ids=["E1"],
        )
    ]


def test_llm_provider_prompts_collapse_pdf_line_breaks_in_evidence() -> None:
    evidence = [_evidence("Подставляя для Li-Nafion\nв ДМФА\nЭВ = 1100 г/моль")]
    openai_provider = OpenAIAnswerProvider(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model="gpt-4.1-mini",
        timeout_seconds=10,
        max_tokens=100,
    )

    expected = "Подставляя для Li-Nafion в ДМФА ЭВ = 1100 г/моль"

    assert expected in openai_provider._user_prompt("question", evidence)  # noqa: SLF001 - prompt normalization test


def test_build_answer_provider_accepts_openai() -> None:
    settings = _settings()
    settings.rag_provider = "openai"
    settings.rag_openai_api_key = "test-key"

    provider = build_answer_provider(settings)  # type: ignore[arg-type]

    assert isinstance(provider, OpenAIAnswerProvider)


class StaticProvider:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result

    def generate(
        self,
        question: str,
        evidence: list[object],
        *,
        answer_style: str = "claims",
        answer_language: str = "auto",
    ) -> ProviderResult:
        return self.result


class CapturingProvider:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result
        self.evidence_texts: list[str] = []
        self.answer_style = "claims"
        self.answer_language = "auto"

    def generate(
        self,
        question: str,
        evidence: list[object],
        *,
        answer_style: str = "claims",
        answer_language: str = "auto",
    ) -> ProviderResult:
        self.evidence_texts = [item.text for item in evidence]  # type: ignore[attr-defined]
        self.answer_style = answer_style
        self.answer_language = answer_language
        return self.result


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        default_collection="literature",
        rag_top_k=5,
        rag_retrieval_method="hybrid",
        rag_provider="openai",
        rag_max_claims=5,
        rag_openai_base_url="https://api.openai.com/v1",
        rag_openai_api_key="",
        rag_openai_model="gpt-4.1-mini",
        rag_openai_max_tokens=1200,
        rag_model="",
        rag_timeout_seconds=120,
    )


def _search_result() -> SearchResult:
    return SearchResult(
        article_id=str(uuid.UUID(int=1)),
        chunk_id=str(uuid.UUID(int=2)),
        title="Evidence paper",
        doi="10.1000/evidence",
        page_start=2,
        page_end=3,
        source_type="method",
        snippet="Conductivity was measured by impedance spectroscopy.",
        score=0.03,
        retrieval_method="hybrid_rrf",
        method_scores={"exact_ilike": 100.0, "semantic_cosine": 0.8},
        method_ranks={"exact_ilike": 1, "semantic_cosine": 2},
    )


def _evidence(text: str) -> Evidence:
    return Evidence(
        citation_id="E1",
        article_id=str(uuid.UUID(int=1)),
        chunk_id=str(uuid.UUID(int=2)),
        title="Диссертация Чернюк С.Д.",
        doi=None,
        page_start=116,
        page_end=116,
        source_type="body",
        text=text,
        score=0.03,
        retrieval_method="hybrid_cross_lingual_rrf",
        method_scores={},
        method_ranks={},
    )


def test_trace_observer_runs_before_provider_and_receives_isolated_copies(monkeypatch):
    events = []
    original = SearchResponse(query="How was conductivity measured?", results=[_search_result()])
    monkeypatch.setattr("app.generation.service.search_chunks", lambda *a, **kw: original)

    def observer(retrieval, evidence, metadata):
        events.append("trace")
        assert evidence[0].text == "Conductivity was measured by impedance spectroscopy."
        retrieval.results.clear()
        evidence.clear()
        metadata.clear()

    class ObservedProvider:
        def generate(self, question, evidence, **kwargs):
            assert events == ["trace"] and len(evidence) == 1
            events.append("provider")
            return ProviderResult(True, [GeneratedClaim("Reported method.", ["E1"])], "synthetic", "synthetic")

    response = answer_question(object(), _settings(), "How was conductivity measured?",
                               provider=ObservedProvider(), trace_observer=observer)
    assert response.status == "answered" and events == ["trace", "provider"]
    assert len(original.results) == 1 and "evidence_adequacy" in response.metadata


def test_trace_observer_captures_gate_rejection_without_model_call(monkeypatch):
    from app.evaluation.answer_trace import TraceCollector

    monkeypatch.setattr("app.generation.service.search_chunks", lambda *a, **kw: SearchResponse(query="missing", results=[]))

    class ForbiddenProvider:
        def generate(self, *args, **kwargs):
            pytest.fail("Gate rejection must not call model")

    collector = TraceCollector()
    response = answer_question(object(), _settings(), "Missing conductivity evidence",
                               provider=ForbiddenProvider(), trace_observer=collector)
    assert response.status == "insufficient_evidence" and collector.trace["evidence"] == []
    assert collector.trace["metadata"]["evidence_adequacy"]["reason"] == "no_evidence"


def test_live_trace_mismatch_stops_before_provider(monkeypatch):
    from app.evaluation.answer_trace import TraceCollector

    monkeypatch.setattr("app.generation.service.search_chunks",
                        lambda *a, **kw: SearchResponse(query="changed", results=[_search_result()]))
    with pytest.raises(ValueError, match="differs from frozen"):
        answer_question(object(), _settings(), "How was conductivity measured?",
                        trace_observer=TraceCollector(expected=b"different frozen trace"))


def test_native_trace_unknown_citations_fail_existing_service_validation(tmp_path, monkeypatch):
    import json

    from app.evaluation import answer_trace as trace

    monkeypatch.setattr("app.generation.service.search_chunks",
                        lambda *a, **kw: SearchResponse(query="conductivity", results=[_search_result()]))
    prepared = trace.TraceResponsesProvider(model="synthetic", api_key="synthetic-key")
    with pytest.raises(trace.PreparationComplete):
        answer_question(object(), _settings(), "How was conductivity measured?", provider=prepared)
    payload = {"status": "completed", "output": [{"type": "message", "role": "assistant", "status": "completed", "content": [{
        "type": "output_text", "text": json.dumps({"answerable": True,
            "claims": [{"text": "Invented citation.", "citation_ids": ["E999"]}]})}]}]}
    monkeypatch.setattr(trace, "send_openai_request", lambda *a: (json.dumps(payload).encode(), "synthetic-request-id"))
    run = tmp_path / "native"
    provider = trace.TraceResponsesProvider(model="synthetic", api_key="synthetic-key", output=run,
                                            expected_request=prepared.prepared_request)
    with pytest.raises(GenerationOutputError, match="unknown citations"):
        answer_question(object(), _settings(), "How was conductivity measured?", provider=provider)
    assert (run / "response.json").is_file() and provider.result["status"] == "provider_valid"
