from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.retrieval.cross_lingual import GLOSSARY, build_query_bundle, detect_query_language, glossary_terms_for_concepts
from app.retrieval.search import (
    SearchResponse,
    SearchResult,
    hybrid_cross_lingual_search,
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


def test_query_bundle_maps_inflected_russian_plasticizer_conductivity_query() -> None:
    bundle = build_query_bundle("В каких пластификаторах наибольшую проводимость дают Li-Nafion")

    assert "transport" in bundle.matched_concepts
    assert "plasticizers" in bundle.matched_concepts
    assert "lithium_form" in bundle.matched_concepts
    assert any(variant.language == "en" and "ionic conductivity" in variant.text for variant in bundle.variants)
    assert any(variant.language == "en" and "binary plasticiser" in variant.text for variant in bundle.variants)


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


def test_query_bundle_maps_english_solvent_nature_film_morphology_to_russian_terms() -> None:
    bundle = build_query_bundle("Nafion dependence of morphology on the nature of the solvent in obtaining films")

    assert "solution_casting_morphology" in bundle.matched_concepts
    assert any(variant.language == "ru" and "природа растворителя" in variant.text for variant in bundle.variants)
    assert any(variant.language == "en" and "dependence morphology solvent" in variant.text for variant in bundle.variants)


def test_query_bundle_maps_russian_solvent_nature_film_morphology_to_english_terms() -> None:
    bundle = build_query_bundle("Зависимость морфологии Nafion от природы растворителя при получении пленок")

    assert "solution_casting_morphology" in bundle.matched_concepts
    assert any(variant.language == "en" and "solvent nature film morphology" in variant.text for variant in bundle.variants)
    assert any(variant.language == "ru" and "зависимость морфологии растворителя" in variant.text for variant in bundle.variants)


def test_query_bundle_maps_istomina_temperature_property_terms() -> None:
    bundle = build_query_bundle("Как температура смешения влияет на физико-химические свойства Li-Nafion?")

    assert "mixing_temperature" in bundle.matched_concepts
    assert "physicochemical_properties" in bundle.matched_concepts
    assert any(variant.language == "en" and "mixing temperature" in variant.text for variant in bundle.variants)
    assert any(variant.language == "en" and "physicochemical properties" in variant.text for variant in bundle.variants)


def test_query_bundle_maps_swelling_degree_comparison_to_alpha_columns() -> None:
    bundle = build_query_bundle("In what solvents Li-Nafion has more swelling degree than H-Nafion?")

    assert "swelling_degree_comparison" in bundle.matched_concepts
    assert any(variant.language == "ru" and "αH αLi H-Nafion Li-Nafion" in variant.text for variant in bundle.variants)


def test_normalize_retrieval_method_accepts_hybrid_cross_lingual() -> None:
    assert normalize_retrieval_method(" Hybrid_Cross_Lingual ") == "hybrid_cross_lingual"


def test_normalize_retrieval_method_rejects_hybrid_cross_lingual_v2() -> None:
    try:
        normalize_retrieval_method(" Hybrid_Cross_Lingual_V2 ")
    except ValueError as exc:
        assert "Unsupported retrieval method" in str(exc)
    else:
        raise AssertionError("hybrid_cross_lingual_v2 should not be a public retrieval method")


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


def test_hybrid_cross_lingual_search_uses_article_diverse_feature_window(monkeypatch) -> None:
    dissertation_results = [
        _result(uuid.UUID(int=index), "Диссертация Чернюк С.Д.", None, "exact_ilike")
        for index in range(1, 12)
    ]
    dai = SearchResult(
        article_id=str(uuid.UUID(int=500)),
        chunk_id=str(uuid.UUID(int=500)),
        title="Dai 2017",
        doi="10.1016/j.memsci.2016.09.014",
        page_start=1,
        page_end=1,
        source_type="body",
        snippet="Effect of casting solvent and annealing temperature on recast Nafion membranes.",
        full_text="Effect of casting solvent and annealing temperature on recast Nafion membranes.",
        score=1.0,
        retrieval_method="exact_ilike",
    )

    monkeypatch.setattr(
        "app.retrieval.search.hybrid_search",
        lambda *args, **kwargs: SearchResponse(query=args[1], results=dissertation_results),
    )

    def fake_exact(*args, **kwargs) -> SearchResponse:
        query = args[1]
        if "casting solvent" in query:
            return SearchResponse(query=query, results=[dai])
        return SearchResponse(query=query, results=dissertation_results)

    monkeypatch.setattr("app.retrieval.search.exact_search", fake_exact)

    response = hybrid_cross_lingual_search(
        object(),  # type: ignore[arg-type]
        "Где исследовано влияние растворителя кастинга и температуры отжига на recast Nafion membranes?",
        top_k=5,
        settings=SimpleNamespace(search_max_top_k=100, hybrid_rrf_k=60),
    )

    assert response.results[0].title == "Dai 2017"
    assert response.metadata["reranking"]["feature_window_selection"] == "article_diverse"  # type: ignore[index]


def test_hybrid_cross_lingual_search_keeps_cross_language_candidate_visible(monkeypatch) -> None:
    english_results = [
        SearchResult(
            article_id=str(uuid.UUID(int=700 + index)),
            chunk_id=str(uuid.UUID(int=700 + index)),
            title=f"English article {index}",
            doi=None,
            page_start=1,
            page_end=1,
            source_type="body",
            snippet="Nafion solution casting morphology and solvent nature evidence.",
            full_text="Nafion solution casting morphology and solvent nature evidence.",
            score=1.0,
            retrieval_method="hybrid_rrf",
        )
        for index in range(5)
    ]
    russian_result = SearchResult(
        article_id=str(uuid.UUID(int=800)),
        chunk_id=str(uuid.UUID(int=800)),
        title="Диссертация Чернюк С.Д.",
        doi=None,
        page_start=42,
        page_end=43,
        source_type="body",
        snippet="Природа растворителя влияет на морфологию мембран Nafion.",
        full_text="Природа растворителя влияет на морфологию мембран Nafion.",
        score=1.0,
        retrieval_method="exact_ilike",
    )

    monkeypatch.setattr(
        "app.retrieval.search.hybrid_search",
        lambda *args, **kwargs: SearchResponse(query=args[1], results=english_results),
    )

    def fake_exact(*args, **kwargs) -> SearchResponse:
        query = args[1]
        if "природа растворителя" in query:
            return SearchResponse(query=query, results=[russian_result])
        return SearchResponse(query=query, results=[])

    monkeypatch.setattr("app.retrieval.search.exact_search", fake_exact)

    response = hybrid_cross_lingual_search(
        object(),  # type: ignore[arg-type]
        "Nafion dependence of morphology on the nature of the solvent in obtaining films",
        top_k=5,
        settings=SimpleNamespace(search_max_top_k=100, hybrid_rrf_k=60),
    )

    assert any(result.title == "Диссертация Чернюк С.Д." for result in response.results)
    assert response.metadata["language_diversity"]["applied"] is True  # type: ignore[index]


def test_hybrid_cross_lingual_search_uses_wide_window_for_water_thermodynamics(monkeypatch) -> None:
    seen_top_k: list[int] = []
    dissertation_results = [
        _result(uuid.UUID(int=index), "Диссертация Чернюк С.Д.", None, "exact_ilike")
        for index in range(1, 12)
    ]
    chernyuk_2023 = SearchResult(
        article_id=str(uuid.UUID(int=600)),
        chunk_id=str(uuid.UUID(int=600)),
        title="Чернюк 2023",
        doi="10.31857/s2308112023700463",
        page_start=7,
        page_end=8,
        source_type="main_text",
        snippet="Термодинамика взаимодействия Nafion с водой и сорбция воды.",
        full_text="Термодинамика взаимодействия Nafion с водой и сорбция воды.",
        score=1.0,
        retrieval_method="exact_ilike",
    )

    def fake_hybrid(*args, **kwargs) -> SearchResponse:
        seen_top_k.append(args[3])
        return SearchResponse(query=args[1], results=dissertation_results)

    def fake_exact(*args, **kwargs) -> SearchResponse:
        seen_top_k.append(args[3])
        query = args[1]
        if "термодинамика взаимодействия" in query:
            return SearchResponse(query=query, results=[*dissertation_results, chernyuk_2023])
        return SearchResponse(query=query, results=dissertation_results)

    monkeypatch.setattr("app.retrieval.search.hybrid_search", fake_hybrid)
    monkeypatch.setattr("app.retrieval.search.exact_search", fake_exact)

    response = hybrid_cross_lingual_search(
        object(),  # type: ignore[arg-type]
        "Which Russian paper discusses Nafion-water sorption thermodynamics?",
        top_k=5,
        settings=SimpleNamespace(search_max_top_k=100, hybrid_rrf_k=60),
    )

    assert max(seen_top_k) == 25
    assert any(result.title == "Чернюк 2023" for result in response.results)
    assert response.metadata["reranking"]["window_size"] == 25  # type: ignore[index]


def test_hybrid_cross_lingual_search_keeps_lithium_water_alcohol_window_narrow(monkeypatch) -> None:
    seen_top_k: list[int] = []
    result = _result(uuid.UUID(int=1), "Чернюк 2024", None, "exact_ilike")

    def fake_search(*args, **kwargs) -> SearchResponse:
        seen_top_k.append(args[3])
        return SearchResponse(query=args[1], results=[result])

    monkeypatch.setattr("app.retrieval.search.hybrid_search", fake_search)
    monkeypatch.setattr("app.retrieval.search.exact_search", fake_search)

    response = hybrid_cross_lingual_search(
        object(),  # type: ignore[arg-type]
        "What is the enthalpy of interaction of lithiated Nafion with aqueous alcohol solutions?",
        top_k=5,
        settings=SimpleNamespace(search_max_top_k=100, hybrid_rrf_k=60),
    )

    assert max(seen_top_k) == 10
    assert response.metadata["reranking"]["window_size"] == 5  # type: ignore[index]


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
