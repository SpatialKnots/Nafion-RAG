from __future__ import annotations

import uuid

from app.retrieval.reranking import rerank_cross_lingual_results
from app.retrieval.search import SearchResult


def test_rerank_prefers_protected_token_and_query_coverage() -> None:
    weak = _result(
        uuid.UUID(int=1),
        "General Nafion paper",
        "Nafion membranes show conductivity in water.",
        ranks={"lexical_original": 1},
    )
    strong = _result(
        uuid.UUID(int=2),
        "Sanginov 2021",
        "Li-Nafion membranes with EC and SL show ionic conductivity.",
        ranks={"glossary_en_1": 8},
    )

    reranked = rerank_cross_lingual_results(
        [weak, strong],
        original_query="Как EC и SL влияют на ионную проводимость Li-Nafion?",
        query_language="ru",
        query_variants=[
            ("original", "Как EC и SL влияют на ионную проводимость Li-Nafion?"),
            ("glossary", "ionic conductivity ethylene carbonate sulfolane li-nafion"),
        ],
    )

    assert [result.title for result in reranked.results] == ["Sanginov 2021", "General Nafion paper"]
    assert reranked.metadata["reranked"] is True
    assert reranked.metadata["top_features"][0]["protected_matches"] >= 3  # type: ignore[index]


def test_rerank_uses_saturated_article_support() -> None:
    article_id = str(uuid.UUID(int=100))
    first = _result(
        uuid.UUID(int=1),
        "Dai 2017",
        "Casting solvent affects recast Nafion membranes.",
        article_id=article_id,
        ranks={"lexical_original": 5},
    )
    second = _result(
        uuid.UUID(int=2),
        "Dai 2017",
        "Annealing temperature changes vanadium permeability.",
        article_id=article_id,
        ranks={"semantic_multilingual": 7},
    )
    isolated = _result(
        uuid.UUID(int=3),
        "Unrelated paper",
        "Casting appears in a short reference list.",
        ranks={"lexical_original": 1},
    )

    reranked = rerank_cross_lingual_results(
        [isolated, first, second],
        original_query="Где исследовано влияние растворителя кастинга и температуры отжига на recast Nafion membranes?",
        query_language="ru",
        query_variants=[("original", "растворителя кастинга температуры отжига recast Nafion membranes")],
    )

    assert reranked.results[0].title == "Dai 2017"
    assert reranked.metadata["top_features"][0]["article_score"] > reranked.metadata["top_features"][2]["article_score"]  # type: ignore[index]


def test_rerank_prefers_title_phrase_match_over_loose_terms() -> None:
    loose = _result(
        uuid.UUID(int=1),
        "General EC SL notes",
        "Nafion membranes mention ethylene carbonate and sulfolane in a reference list.",
        ranks={"glossary_en_1": 1},
    )
    title_match = _result(
        uuid.UUID(int=2),
        "Influence of Mixing Temperature on the Physicochemical Properties",
        "Li-Nafion membrane plasticised with ethylene carbonate and sulfolane.",
        ranks={"glossary_en_1": 8},
    )

    reranked = rerank_cross_lingual_results(
        [loose, title_match],
        original_query="Какая работа изучает mixing temperature and physicochemical properties Li-Nafion?",
        query_language="mixed",
        query_variants=[("glossary", "mixing temperature physicochemical properties swelling degree")],
    )

    assert reranked.results[0].title == "Influence of Mixing Temperature on the Physicochemical Properties"
    assert reranked.metadata["top_features"][0]["title_phrase_matches"] >= 1  # type: ignore[index]


def test_rerank_maps_russian_highest_plasticizer_conductivity_terms() -> None:
    generic = _result(
        uuid.UUID(int=1),
        "Lithium salt background",
        "Lithium salts in carbonates have bipolar charge transport.",
        ranks={"glossary_ru_1": 1},
    )
    conductivity = _result(
        uuid.UUID(int=2),
        "Istomina 2021",
        (
            "Li-Nafion membrane plasticised with EC/SL binary plasticiser. "
            "The best transport properties of Li-Nafion provided EC/SL mixtures enriched "
            "with ethylene carbonate, and conductivity rapidly decreases with sulfolane."
        ),
        ranks={"glossary_en_2": 8},
    )

    reranked = rerank_cross_lingual_results(
        [generic, conductivity],
        original_query="В каких пластификаторах наибольшую проводимость дают Li-Nafion",
        query_language="ru",
        query_variants=[
            ("original", "В каких пластификаторах наибольшую проводимость дают Li-Nafion"),
            ("glossary", "ionic conductivity binary plasticiser li-nafion"),
        ],
    )

    assert reranked.results[0].title == "Istomina 2021"
    assert reranked.metadata["top_features"][0]["term_matches"] >= 4  # type: ignore[index]


def test_rerank_prefers_swelling_comparison_numeric_table() -> None:
    generic = _result(
        uuid.UUID(int=1),
        "General swelling discussion",
        "Li-Nafion and H-Nafion swelling degree is discussed in organic solvents.",
        ranks={"glossary_ru_1": 1},
    )
    table = _result(
        uuid.UUID(int=2),
        "Диссертация Чернюк С.Д.",
        (
            "Таблица 4.5 — Равновесная степень набухания и энтальпия набухания "
            "H-Nafion and Li-Nafion. Растворитель H-Nafion Li-Nafion αH αLi "
            "диметилсульфоксид 0.89 1.12 N,N-диметилформамид 0.72 1.15 "
            "N-метил-2-пирролидон 0.64 1.37"
        ),
        ranks={"glossary_ru_1": 5},
    )

    reranked = rerank_cross_lingual_results(
        [generic, table],
        original_query="In what solvents Li-Nafion has more swelling degree than H-Nafion?",
        query_language="en",
        query_variants=[("glossary", "степень набухания αH αLi H-Nafion Li-Nafion")],
    )

    assert reranked.results[0].title == "Диссертация Чернюк С.Д."
    assert reranked.metadata["top_features"][0]["numeric_table_bonus"] == 2  # type: ignore[index]


def _result(
    chunk_id: uuid.UUID,
    title: str,
    text: str,
    *,
    article_id: str | None = None,
    ranks: dict[str, int] | None = None,
) -> SearchResult:
    return SearchResult(
        article_id=article_id or str(uuid.UUID(int=chunk_id.int + 100)),
        chunk_id=str(chunk_id),
        title=title,
        doi=None,
        page_start=1,
        page_end=1,
        source_type="body",
        snippet=text,
        full_text=text,
        score=1.0,
        retrieval_method="hybrid_cross_lingual_rrf",
        method_ranks=ranks or {},
    )
