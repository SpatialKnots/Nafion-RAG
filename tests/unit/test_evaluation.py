from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.evaluation.retrieval import (
    EvaluationQuestion,
    _evaluate_question,
    compare_retrieval_methods,
    compare_retrieval_reports,
    load_questions,
    run_retrieval_evaluation,
    write_evaluation_report,
)
from app.retrieval.search import SearchResponse, SearchResult


def test_load_questions_rejects_malformed_entries(tmp_path) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text("- id: q01\n  expected_article_dois: []\n  expected_keywords: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="q01.query"):
        load_questions(path)


def test_load_questions_accepts_expected_fields(tmp_path) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text(
        "- id: q01\n"
        "  query: Li-Nafion conductivity\n"
        "  expected_article_dois:\n"
        "    - 10.1000/Example\n"
        "  expected_keywords:\n"
        "    - conductivity\n",
        encoding="utf-8",
    )

    questions = load_questions(path)

    assert questions[0].id == "q01"
    assert questions[0].expected_article_dois == ["10.1000/example"]
    assert questions[0].expected_article_titles == []
    assert questions[0].expected_article_checksums == []
    assert questions[0].expected_keywords == ["conductivity"]


def test_load_questions_accepts_title_and_checksum_targets(tmp_path) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text(
        "- id: q01\n"
        "  query: Moore Martin\n"
        "  expected_article_titles:\n"
        "    - Chemical and Morphological Properties\n"
        "  expected_article_checksums:\n"
        "    - ABCDEF\n"
        "  expected_keywords:\n"
        "    - ionomers\n",
        encoding="utf-8",
    )

    questions = load_questions(path)

    assert questions[0].expected_article_dois == []
    assert questions[0].expected_article_titles == ["chemical and morphological properties"]
    assert questions[0].expected_article_checksums == ["abcdef"]


def test_load_questions_requires_at_least_one_article_target(tmp_path) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text(
        "- id: q01\n  query: Nafion\n  expected_keywords:\n    - Nafion\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_article_dois"):
        load_questions(path)


def test_retrieval_evaluation_reports_failures_and_top_result(monkeypatch, tmp_path) -> None:
    questions_path = tmp_path / "questions.yaml"
    questions_path.write_text(
        "- id: q01\n"
        "  query: Li-Nafion conductivity\n"
        "  expected_article_dois:\n"
        "    - 10.1000/example\n"
        "  expected_keywords:\n"
        "    - conductivity\n"
        "    - NMP\n",
        encoding="utf-8",
    )

    def fake_search_chunks(
        session: object,
        query: str,
        collection_name: str,
        top_k: int,
        *,
        method: str = "exact",
        filters: object | None = None,
        group_by: str = "none",
        chunks_per_article: int | None = None,
        settings: object | None = None,
    ) -> SearchResponse:
        assert method == "exact"
        assert filters is not None
        assert group_by == "none"
        assert chunks_per_article is None
        assert settings is not None
        return SearchResponse(
            query=query,
            results=[
                SearchResult(
                    article_id=str(uuid.uuid4()),
                    chunk_id=str(uuid.uuid4()),
                    title="Li-Nafion paper",
                    doi="10.1000/example",
                    page_start=2,
                    page_end=3,
                    source_type="method",
                    snippet="Li-Nafion conductivity was measured.",
                    score=12.0,
                    retrieval_method="exact_ilike",
                )
            ],
        )

    monkeypatch.setattr("app.evaluation.retrieval.search_chunks", fake_search_chunks)
    monkeypatch.setattr("app.evaluation.retrieval._article_checksums_for_results", lambda session, result_payload: {})

    report = run_retrieval_evaluation(
        object(),  # type: ignore[arg-type]
        SimpleNamespace(default_top_k=10),  # type: ignore[arg-type]
        questions_path,
        collection="literature",
        top_k=5,
        method="exact",
    )

    assert report["settings"]["method"] == "exact"
    assert report["settings"]["retrieval_method"] == "exact_ilike"
    assert report["settings"]["filter_mode"] == "unfiltered"
    assert report["settings"]["filters"] == {}
    assert report["settings"]["group_by"] == "none"
    assert report["settings"]["chunks_per_article"] is None
    assert report["settings"]["retrieval_metadata"] == {}
    assert report["summary"] == {
        "total": 1,
        "passed": 0,
        "top_1_passed": 0,
        "failed": 1,
        "recall_at_k": 1.0,
        "mean_rank": 1.0,
        "empty_result_queries": 0,
    }
    question = report["questions"][0]
    assert question["top_1_passed"] is False
    assert question["rank_of_expected"] == 1
    assert question["recall_at_k"] == 1.0
    assert question["missing_article_dois"] == []
    assert question["missing_article_titles"] == []
    assert question["missing_article_checksums"] == []
    assert question["missing_keywords"] == ["NMP"]
    assert question["result_count"] == 1
    assert question["top_result"]["doi"] == "10.1000/example"
    assert question["top_result"]["retrieval_method"] == "exact_ilike"


def test_retrieval_evaluation_rejects_unknown_method(tmp_path) -> None:
    questions_path = tmp_path / "questions.yaml"
    questions_path.write_text(
        "- id: q01\n  query: Nafion\n  expected_article_dois:\n    - 10.1000/example\n  expected_keywords:\n    - Nafion\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported retrieval method"):
        run_retrieval_evaluation(
            object(),  # type: ignore[arg-type]
            SimpleNamespace(default_top_k=10),  # type: ignore[arg-type]
            questions_path,
            collection="literature",
            top_k=5,
            method="weighted",
        )


def test_retrieval_evaluation_records_semantic_metadata(monkeypatch, tmp_path) -> None:
    questions_path = tmp_path / "questions.yaml"
    questions_path.write_text(
        "- id: q01\n  query: proton transport\n  expected_article_dois:\n    - 10.1000/example\n  expected_keywords:\n    - proton\n",
        encoding="utf-8",
    )

    def fake_search_chunks(*args: object, **kwargs: object) -> SearchResponse:
        assert kwargs["method"] == "semantic"
        return SearchResponse(
            query="proton transport",
            results=[
                SearchResult(
                    article_id=str(uuid.uuid4()),
                    chunk_id=str(uuid.uuid4()),
                    title="Expected",
                    doi="10.1000/example",
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="proton transport evidence",
                    score=0.8,
                    retrieval_method="semantic_cosine",
                )
            ],
            metadata={"embedding_model": "test/model", "manifest_sha256": "abc"},
        )

    monkeypatch.setattr("app.evaluation.retrieval.search_chunks", fake_search_chunks)
    monkeypatch.setattr("app.evaluation.retrieval._article_checksums_for_results", lambda session, result_payload: {})
    report = run_retrieval_evaluation(
        object(),  # type: ignore[arg-type]
        SimpleNamespace(default_top_k=10),  # type: ignore[arg-type]
        questions_path,
        collection="literature",
        top_k=10,
        method="semantic",
    )

    assert report["settings"]["retrieval_method"] == "semantic_cosine"
    assert report["settings"]["retrieval_metadata"]["embedding_model"] == "test/model"
    assert report["summary"]["top_1_passed"] == 1


def test_retrieval_evaluation_records_hybrid_component_diagnostics(monkeypatch, tmp_path) -> None:
    questions_path = tmp_path / "questions.yaml"
    questions_path.write_text(
        "- id: q01\n  query: proton transport\n  expected_article_dois:\n    - 10.1000/example\n  expected_keywords:\n    - proton\n",
        encoding="utf-8",
    )

    def fake_search_chunks(*args: object, **kwargs: object) -> SearchResponse:
        assert kwargs["method"] == "hybrid"
        return SearchResponse(
            query="proton transport",
            results=[
                SearchResult(
                    article_id=str(uuid.uuid4()),
                    chunk_id=str(uuid.uuid4()),
                    title="Expected",
                    doi="10.1000/example",
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="proton transport evidence",
                    score=0.03,
                    retrieval_method="hybrid_rrf",
                    method_scores={"exact_ilike": 10.0, "semantic_cosine": 0.8},
                    method_ranks={"exact_ilike": 2, "semantic_cosine": 1},
                )
            ],
            metadata={"fusion": "reciprocal_rank_fusion", "rrf_k": 60},
        )

    monkeypatch.setattr("app.evaluation.retrieval.search_chunks", fake_search_chunks)
    monkeypatch.setattr("app.evaluation.retrieval._article_checksums_for_results", lambda session, result_payload: {})
    report = run_retrieval_evaluation(
        object(),  # type: ignore[arg-type]
        SimpleNamespace(default_top_k=10),  # type: ignore[arg-type]
        questions_path,
        collection="literature",
        top_k=10,
        method="hybrid",
    )

    assert report["settings"]["retrieval_method"] == "hybrid_rrf"
    assert report["settings"]["retrieval_metadata"]["rrf_k"] == 60
    assert report["questions"][0]["top_result"]["method_ranks"] == {"exact_ilike": 2, "semantic_cosine": 1}


def test_retrieval_evaluation_supports_title_and_checksum_targets(tmp_path) -> None:
    article_id = str(uuid.uuid4())
    question = load_questions_from_text(
        tmp_path,
        "- id: q01\n"
        "  query: Moore Martin\n"
        "  expected_article_titles:\n"
        "    - Moore и Martin - 1988 - Chemical and morphological properties\n"
        "  expected_article_checksums:\n"
        "    - ABC123\n"
        "  expected_keywords:\n"
        "    - solution-cast\n",
    )[0]
    response = SearchResponse(
        query="Moore Martin",
        results=[
            SearchResult(
                article_id=article_id,
                chunk_id=str(uuid.uuid4()),
                title="Moore и Martin - 1988 - Chemical and morphological properties",
                doi=None,
                page_start=1,
                page_end=1,
                source_type="body",
                snippet="Chemical and morphological properties of solution-cast ionomers.",
                score=10.0,
                retrieval_method="exact_ilike",
            )
        ],
    )

    payload = _evaluate_question(question, response, {article_id: "abc123"})

    assert payload["passed"] is True
    assert payload["top_1_passed"] is True
    assert payload["rank_of_expected"] == 1
    assert payload["recall_at_k"] == 1.0
    assert payload["missing_article_dois"] == []
    assert payload["missing_article_titles"] == []
    assert payload["missing_article_checksums"] == []


def test_retrieval_evaluation_reports_missing_targets_separately(tmp_path) -> None:
    question = load_questions_from_text(
        tmp_path,
        "- id: q01\n"
        "  query: DOI-less paper\n"
        "  expected_article_dois:\n"
        "    - 10.1000/missing\n"
        "  expected_article_titles:\n"
        "    - Missing title\n"
        "  expected_article_checksums:\n"
        "    - missing-checksum\n"
        "  expected_keywords:\n"
        "    - absent\n",
    )[0]
    response = SearchResponse(query="DOI-less paper", results=[])

    payload = _evaluate_question(question, response, {})

    assert payload["passed"] is False
    assert payload["top_1_passed"] is False
    assert payload["rank_of_expected"] is None
    assert payload["recall_at_k"] == 0.0
    assert payload["missing_article_dois"] == ["10.1000/missing"]
    assert payload["missing_article_titles"] == ["missing title"]
    assert payload["missing_article_checksums"] == ["missing-checksum"]
    assert payload["missing_keywords"] == ["absent"]


def test_retrieval_evaluation_reports_expected_article_rank(tmp_path) -> None:
    expected_article_id = str(uuid.uuid4())
    question = load_questions_from_text(
        tmp_path,
        "- id: q01\n  query: ranked paper\n  expected_article_dois:\n    - 10.1000/expected\n  expected_keywords:\n    - ranked\n",
    )[0]
    response = SearchResponse(
        query="ranked paper",
        results=[
            SearchResult(
                article_id=str(uuid.uuid4()),
                chunk_id=str(uuid.uuid4()),
                title="Wrong paper",
                doi="10.1000/wrong",
                page_start=1,
                page_end=1,
                source_type="body",
                snippet="ranked query text",
                score=20.0,
                retrieval_method="exact_ilike",
            ),
            SearchResult(
                article_id=expected_article_id,
                chunk_id=str(uuid.uuid4()),
                title="Expected paper",
                doi="10.1000/expected",
                page_start=2,
                page_end=2,
                source_type="body",
                snippet="ranked expected text",
                score=10.0,
                retrieval_method="exact_ilike",
            ),
        ],
    )

    payload = _evaluate_question(question, response, {})

    assert payload["passed"] is True
    assert payload["top_1_passed"] is False
    assert payload["rank_of_expected"] == 2
    assert payload["recall_at_k"] == 1.0


def load_questions_from_text(tmp_path: Path, text: str) -> list[EvaluationQuestion]:
    path = tmp_path / "questions.yaml"
    path.write_text(text, encoding="utf-8")
    return load_questions(path)


def test_write_evaluation_report_uses_exports_directory(tmp_path) -> None:
    output_path = write_evaluation_report({"summary": {"total": 0}}, Path(tmp_path))

    assert output_path.parent == tmp_path / "exports"
    assert output_path.name.startswith("retrieval_eval_")
    assert output_path.read_text(encoding="utf-8")


def test_compare_retrieval_reports_reports_deltas_regressions_and_improvements() -> None:
    exact = {
        "settings": {"method": "exact", "retrieval_method": "exact_ilike", "collection": "literature", "top_k": 10},
        "summary": {"top_1_passed": 1, "recall_at_k": 1.0, "mean_rank": 2.0},
        "questions": [
            {"id": "regressed", "query": "q1", "passed": True, "top_1_passed": True, "rank_of_expected": 1},
            {"id": "improved", "query": "q2", "passed": True, "top_1_passed": False, "rank_of_expected": 3},
        ],
    }
    semantic = {
        "settings": {
            "method": "semantic",
            "retrieval_method": "semantic_cosine",
            "collection": "literature",
            "top_k": 10,
        },
        "summary": {"top_1_passed": 1, "recall_at_k": 0.5, "mean_rank": 1.0},
        "questions": [
            {"id": "regressed", "query": "q1", "passed": False, "top_1_passed": False, "rank_of_expected": None},
            {"id": "improved", "query": "q2", "passed": True, "top_1_passed": True, "rank_of_expected": 1},
        ],
    }

    comparison = compare_retrieval_reports(exact, semantic)

    assert comparison["regressions"] == ["regressed"]
    assert comparison["improvements"] == ["improved"]
    assert comparison["top_1_regressions"] == ["regressed"]
    assert comparison["top_1_improvements"] == ["improved"]
    assert comparison["summary"]["recall_at_k_delta"] == -0.5
    assert comparison["summary"]["mean_rank_delta"] == -1.0


def test_compare_retrieval_reports_rejects_different_top_k() -> None:
    exact = {
        "settings": {"method": "exact", "retrieval_method": "exact_ilike", "collection": "literature", "top_k": 10},
        "summary": {},
        "questions": [],
    }
    semantic = {
        "settings": {
            "method": "semantic",
            "retrieval_method": "semantic_cosine",
            "collection": "literature",
            "top_k": 5,
        },
        "summary": {},
        "questions": [],
    }

    with pytest.raises(ValueError, match="top_k"):
        compare_retrieval_reports(exact, semantic)


def test_compare_retrieval_methods_builds_three_way_deltas() -> None:
    exact = _method_report("exact", "exact_ilike", passed=2, top_1=1, mean_rank=2.0, rank=2)
    semantic = _method_report("semantic", "semantic_cosine", passed=1, top_1=1, mean_rank=1.0, rank=1)
    hybrid = _method_report("hybrid", "hybrid_rrf", passed=2, top_1=2, mean_rank=1.0, rank=1)

    comparison = compare_retrieval_methods(exact, semantic, hybrid)

    assert comparison["methods"]["hybrid_rrf"]["top_1_passed"] == 2
    assert comparison["deltas"]["hybrid_vs_exact"]["top_1_passed"] == 1.0
    assert comparison["deltas"]["hybrid_vs_semantic"]["passed"] == 1.0
    assert comparison["questions"][0]["hybrid_rank"] == 1


def test_compare_retrieval_methods_rejects_wrong_hybrid_report() -> None:
    exact = _method_report("exact", "exact_ilike", passed=1, top_1=1, mean_rank=1.0, rank=1)
    semantic = _method_report("semantic", "semantic_cosine", passed=1, top_1=1, mean_rank=1.0, rank=1)

    with pytest.raises(ValueError, match="hybrid report"):
        compare_retrieval_methods(exact, semantic, semantic)


def _method_report(method: str, concrete: str, *, passed: int, top_1: int, mean_rank: float, rank: int) -> dict:
    return {
        "settings": {"method": method, "retrieval_method": concrete, "collection": "literature", "top_k": 10},
        "summary": {
            "total": 2,
            "passed": passed,
            "top_1_passed": top_1,
            "failed": 2 - passed,
            "recall_at_k": 1.0,
            "mean_rank": mean_rank,
            "empty_result_queries": 0,
        },
        "questions": [
            {
                "id": "q01",
                "query": "query",
                "passed": passed > 0,
                "top_1_passed": top_1 > 0,
                "rank_of_expected": rank,
            }
        ],
    }
