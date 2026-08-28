from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.retrieval.cross_lingual import GLOSSARY, build_query_bundle, detect_query_language, glossary_terms_for_concepts
from app.retrieval.search import (
    SearchResponse,
    SearchResult,
    hybrid_cross_lingual_search,
    hybrid_cross_lingual_v2_search,
    normalize_retrieval_method,
)


def test_detect_query_language_identifies_english_russian_and_mixed() -> None:
    assert detect_query_language("How does Nafion swell?")[0] == "en"
    assert detect_query_language("Как набухает мембрана Nafion?")[0] == "mixed"
    assert detect_query_language("термодинамика взаимодействия с водой")[0] == "ru"


def test_cross_lingual_glossary_is_loaded_from_versioned_data_file() -> None:
    assert len(GLOSSARY) >= 10
    assert glossary_terms_for_concepts(["transport"])["transport"]["en"][0] == "ionic conductivity"


def test_query_bundle_adds_russian_glossary_variant_for_english_query() -> None:
    bundle = build_query_bundle("How do lithium ions affect thermodynamic and relaxation properties of Nafion membranes?")

    assert bundle.language == "en"
    assert "lithium_form" in bundle.matched_concepts
    assert "morphology_dynamics" in bundle.matched_concepts
    assert any(variant.language == "ru" and "ионы лития" in variant.text for variant in bundle.variants)
    assert any(variant.language == "ru" and "релаксационные свойства" in variant.text for variant in bundle.variants)


def test_query_bundle_adds_same_language_and_cross_language_glossary_variants() -> None:
    bundle = build_query_bundle("ионная проводимость Li-Nafion EC SL")

    assert "transport" in bundle.matched_concepts
    assert "ec_sl_solvents" in bundle.matched_concepts
    assert any(variant.language == "ru" and "ионная проводимость" in variant.text for variant in bundle.variants)
    assert any(variant.language == "en" and "ionic conductivity" in variant.text for variant in bundle.variants)
    assert any(variant.language == "en" and "ethylene carbonate" in variant.text for variant in bundle.variants)


def test_query_bundle_maps_english_water_interaction_to_russian_terms() -> None:
    bundle = build_query_bundle("What are the thermodynamic interactions of PFSA Nafion with water?")

    assert "thermodynamic_interaction" in bundle.matched_concepts
    assert "water_interaction" in bundle.matched_concepts
    assert any(variant.language == "ru" and "вода" in variant.text for variant in bundle.variants)


def test_query_bundle_maps_russian_casting_annealing_to_english_terms() -> None:
    bundle = build_query_bundle("Где исследовано влияние растворителя кастинга и температуры отжига на recast Nafion membranes?")

    assert "casting_annealing" in bundle.matched_concepts
    assert any(variant.language == "en" and "casting solvent" in variant.text for variant in bundle.variants)
    assert any(variant.language == "en" and "annealing temperature" in variant.text for variant in bundle.variants)


def test_query_bundle_does_not_match_ec_inside_recast() -> None:
    bundle = build_query_bundle("recast Nafion membranes")

    assert "ec_sl_solvents" not in bundle.matched_concepts


def test_query_bundle_maps_recast_solvent_list_to_dai_variant() -> None:
    bundle = build_query_bundle("Где сравниваются DMF, DMSO, NMP, EtOH и DMAc для recast Nafion?")

    assert "recast_solvent_list" in bundle.matched_concepts
    assert "ec_sl_solvents" not in bundle.matched_concepts
    assert any(
        variant.language == "en" and "dmf dmso nmp etoh dmac recast nafion" in variant.text
        for variant in bundle.variants
    )


def test_query_bundle_distinguishes_solvent_casting_from_casting_solvent() -> None:
    bundle = build_query_bundle("Как solvent casting влияет на морфологию и свойства мембран Nafion?")

    assert "solution_casting_morphology" in bundle.matched_concepts
    assert "casting_annealing" not in bundle.matched_concepts
    assert any(variant.language == "en" and "solution casting morphology properties" in variant.text for variant in bundle.variants)


def test_query_bundle_maps_istomina_temperature_property_terms() -> None:
    bundle = build_query_bundle("Как температура смешения влияет на физико-химические свойства Li-Nafion?")

    assert "mixing_temperature" in bundle.matched_concepts
    assert "physicochemical_properties" in bundle.matched_concepts
    assert any(variant.language == "en" and "mixing temperature" in variant.text for variant in bundle.variants)
    assert any(variant.language == "en" and "physicochemical properties" in variant.text for variant in bundle.variants)


def test_normalize_retrieval_method_accepts_hybrid_cross_lingual() -> None:
    assert normalize_retrieval_method(" Hybrid_Cross_Lingual ") == "hybrid_cross_lingual"


def test_normalize_retrieval_method_accepts_hybrid_cross_lingual_v2() -> None:
    assert normalize_retrieval_method(" Hybrid_Cross_Lingual_V2 ") == "hybrid_cross_lingual_v2"


def test_hybrid_cross_lingual_search_merges_original_and_glossary_results(monkeypatch) -> None:
    english_result = _result(uuid.UUID(int=1), "Sanginov 2021", "10.1016/j.electacta.2021.137914", "hybrid_rrf")
    russian_result = _result(uuid.UUID(int=2), "Диссертация Чернюк С.Д.", None, "exact_ilike")

    monkeypatch.setattr(
        "app.retrieval.search.hybrid_search",
        lambda *args, **kwargs: SearchResponse(query=args[1], results=[english_result], metadata={"retrieval_method": "hybrid_rrf"}),
    )
    monkeypatch.setattr(
        "app.retrieval.search.exact_search",
        lambda *args, **kwargs: SearchResponse(query=args[1], results=[russian_result]),
    )

    response = hybrid_cross_lingual_search(
        object(),  # type: ignore[arg-type]
        "How do lithium ions affect thermodynamic and relaxation properties of Nafion membranes?",
        top_k=5,
        settings=SimpleNamespace(search_max_top_k=100, hybrid_rrf_k=60),
    )

    assert {result.title for result in response.results} == {"Sanginov 2021", "Диссертация Чернюк С.Д."}
    assert all(result.retrieval_method == "hybrid_cross_lingual_rrf" for result in response.results)
    assert response.metadata["retrieval_method"] == "hybrid_cross_lingual_rrf"
    cross_lingual = response.metadata["cross_lingual"]  # type: ignore[index]
    assert cross_lingual["query_language"] == "en"  # type: ignore[index]
    assert len(cross_lingual["variants"]) >= 2  # type: ignore[index]
    assert any(hit["result_count"] == 1 for hit in cross_lingual["variant_hits"][1:])  # type: ignore[index]


def test_hybrid_cross_lingual_v2_adds_normalized_lexical_channel(monkeypatch) -> None:
    original_result = _result(uuid.UUID(int=1), "Russian same-language paper", None, "hybrid_rrf")
    normalized_result = _result(uuid.UUID(int=2), "Sanginov 2021", "10.1016/j.electacta.2021.137914", "exact_ilike")
    exact_queries: list[str] = []

    monkeypatch.setattr(
        "app.retrieval.search.hybrid_search",
        lambda *args, **kwargs: SearchResponse(query=args[1], results=[original_result], metadata={"retrieval_method": "hybrid_rrf"}),
    )

    def fake_exact(*args, **kwargs):
        exact_queries.append(args[1])
        if "ионн" in args[1] and "проводимост" in args[1]:
            return SearchResponse(query=args[1], results=[normalized_result])
        return SearchResponse(query=args[1], results=[])

    monkeypatch.setattr("app.retrieval.search.exact_search", fake_exact)

    response = hybrid_cross_lingual_v2_search(
        object(),  # type: ignore[arg-type]
        "Как EC и SL влияют на ионную проводимость Li-Nafion?",
        top_k=5,
        settings=SimpleNamespace(search_max_top_k=100, hybrid_rrf_k=60),
    )

    assert any("ионн" in query and "проводимост" in query for query in exact_queries)
    assert {result.title for result in response.results} == {"Russian same-language paper", "Sanginov 2021"}
    assert all(result.retrieval_method == "hybrid_cross_lingual_v2_rrf" for result in response.results)
    cross_lingual = response.metadata["cross_lingual"]  # type: ignore[index]
    assert cross_lingual["version"] == "v2"  # type: ignore[index]
    query_metadata = cross_lingual["query"]  # type: ignore[index]
    assert query_metadata["original"] == "Как EC и SL влияют на ионную проводимость Li-Nafion?"  # type: ignore[index]
    assert "EC" in query_metadata["protected_tokens"]  # type: ignore[index]
    channels = cross_lingual["channels"]  # type: ignore[index]
    assert channels["lexical_normalized"]["result_count"] == 1  # type: ignore[index]


def test_hybrid_cross_lingual_v2_can_add_multilingual_semantic_channel(monkeypatch) -> None:
    original_result = _result(uuid.UUID(int=1), "Original channel", None, "hybrid_rrf")
    semantic_result = _result(uuid.UUID(int=2), "Multilingual semantic channel", None, "semantic_multilingual_cosine")

    monkeypatch.setattr(
        "app.retrieval.search.hybrid_search",
        lambda *args, **kwargs: SearchResponse(query=args[1], results=[original_result], metadata={"retrieval_method": "hybrid_rrf"}),
    )
    monkeypatch.setattr("app.retrieval.search.exact_search", lambda *args, **kwargs: SearchResponse(query=args[1], results=[]))
    monkeypatch.setattr(
        "app.retrieval.search.semantic_multilingual_search",
        lambda *args, **kwargs: SearchResponse(
            query=args[1],
            results=[semantic_result],
            metadata={"embedding_model": "test/multilingual", "semantic_role": "multilingual"},
        ),
    )

    response = hybrid_cross_lingual_v2_search(
        object(),  # type: ignore[arg-type]
        "How does lithium substitution affect Nafion?",
        top_k=5,
        settings=SimpleNamespace(
            search_max_top_k=100,
            hybrid_rrf_k=60,
            cross_lingual_multilingual_embeddings_enabled=True,
        ),
    )

    assert {result.title for result in response.results} == {"Original channel", "Multilingual semantic channel"}
    channels = response.metadata["cross_lingual"]["channels"]  # type: ignore[index]
    assert channels["semantic_multilingual"]["enabled"] is True  # type: ignore[index]
    assert channels["semantic_multilingual"]["result_count"] == 1  # type: ignore[index]
    assert channels["semantic_multilingual"]["model"] == "test/multilingual"  # type: ignore[index]


def _result(chunk_id: uuid.UUID, title: str, doi: str | None, method: str) -> SearchResult:
    return SearchResult(
        article_id=str(uuid.UUID(int=100 + chunk_id.int)),
        chunk_id=str(chunk_id),
        title=title,
        doi=doi,
        page_start=1,
        page_end=1,
        source_type="method",
        snippet=f"{title} evidence",
        full_text=f"{title} full evidence",
        score=1.0,
        retrieval_method=method,
    )
