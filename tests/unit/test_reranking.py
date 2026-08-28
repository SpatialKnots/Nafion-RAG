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
