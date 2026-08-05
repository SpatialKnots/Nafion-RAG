from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.evaluation.benchmark import run_search_benchmark, write_benchmark_report
from app.evaluation.retrieval import (
    EvaluationQuestion,
    ExtendedEvaluationQuestion,
    _evaluate_extended_question,
    _evaluate_question,
    check_extended_evaluation_thresholds,
    compare_retrieval_methods,
    compare_retrieval_reports,
    load_evaluation_thresholds,
    load_extended_questions,
    load_questions,
    run_extended_retrieval_evaluation,
    run_retrieval_evaluation,
    write_evaluation_report,
    write_extended_evaluation_report,
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


def test_load_extended_questions_accepts_new_schema(tmp_path) -> None:
    path = tmp_path / "questions_extended.yaml"
    path.write_text(
        "- id: q01\n"
        "  query: Nafion solvent morphology\n"
        "  language: en\n"
        "  answerable: true\n"
        "  expected:\n"
        "    articles:\n"
        "      - doi: 10.1000/Example\n"
        "        relevance: 3\n"
        "    chunks:\n"
        "      - article_doi: 10.1000/Example\n"
        "        text_contains:\n"
        "          - morphology\n"
        "        relevance: 2\n",
        encoding="utf-8",
    )

    questions = load_extended_questions(path)

    assert questions[0].expected_articles[0].doi == "10.1000/example"
    assert questions[0].expected_articles[0].relevance == 3
    assert questions[0].expected_chunks[0].text_contains == ["morphology"]


def test_load_extended_questions_adapts_legacy_schema(tmp_path) -> None:
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

    questions = load_extended_questions(path)

    assert questions[0].expected_articles[0].doi == "10.1000/example"
    assert questions[0].expected_chunks[0].text_contains == ["conductivity"]


def test_load_extended_questions_accepts_unanswerable_without_expected(tmp_path) -> None:
    path = tmp_path / "questions_extended.yaml"
    path.write_text(
        "- id: q_absent\n"
        "  query: absent topic\n"
        "  answerable: false\n"
        "  expected:\n"
        "    articles: []\n"
        "    chunks: []\n",
        encoding="utf-8",
    )

    questions = load_extended_questions(path)

    assert questions[0].answerable is False
    assert questions[0].expected_articles == []
    assert questions[0].expected_chunks == []


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


def test_search_benchmark_serializes_latency_report(monkeypatch, tmp_path) -> None:
    questions_path = tmp_path / "questions.yaml"
    questions_path.write_text(
        "- id: q01\n"
        "  query: Li-Nafion conductivity\n"
        "  expected_article_dois:\n"
        "    - 10.1000/example\n"
        "  expected_keywords:\n"
        "    - conductivity\n",
        encoding="utf-8",
    )
    collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
    state = SimpleNamespace(
        status="ready",
        desired_revision=1,
        active_revision=1,
        active_generation_id="generation-1",
        active_manifest_sha256="abc",
    )
    session = SequenceScalarSession([collection, 1, 2, state])

    def fake_search_chunks(*args: object, **kwargs: object) -> SearchResponse:
        return SearchResponse(
            query="Li-Nafion conductivity",
            results=[
                SearchResult(
                    article_id=str(uuid.uuid4()),
                    chunk_id=str(uuid.uuid4()),
                    title="Li-Nafion paper",
                    doi="10.1000/example",
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="conductivity evidence",
                    score=1.0,
                    retrieval_method="exact_ilike",
                )
            ],
        )

    monkeypatch.setattr("app.evaluation.benchmark.search_chunks", fake_search_chunks)

    report = run_search_benchmark(
        session,  # type: ignore[arg-type]
        SimpleNamespace(
            embedding_model="test/model",
            vector_index_cache_enabled=True,
            vector_index_use_mmap=False,
        ),  # type: ignore[arg-type]
        questions_path,
        collection="literature",
        methods=["exact"],
        warmup=0,
        runs=2,
        top_k=5,
    )
    output_path = write_benchmark_report(report, tmp_path)

    assert output_path.name.startswith("backend_benchmark_")
    assert report["corpus"]["article_count"] == 1
    assert report["corpus"]["chunk_count"] == 2
    assert report["methods"]["exact"]["total_measured_searches"] == 2
    assert report["methods"]["exact"]["latency_ms"]["p50"] is not None


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


def test_extended_evaluation_reports_precision_mrr_ndcg_and_trace(tmp_path) -> None:
    expected_article_id = str(uuid.uuid4())
    question = load_extended_questions_from_text(
        tmp_path,
        "- id: q01\n"
        "  query: solvent morphology\n"
        "  expected:\n"
        "    articles:\n"
        "      - doi: 10.1000/expected\n"
        "        relevance: 3\n"
        "    chunks:\n"
        "      - article_doi: 10.1000/expected\n"
        "        text_contains:\n"
        "          - morphology\n"
        "        relevance: 2\n",
    )[0]
    response = SearchResponse(
        query="solvent morphology",
        results=[
            SearchResult(
                article_id=str(uuid.uuid4()),
                chunk_id=str(uuid.uuid4()),
                title="Wrong paper",
                doi="10.1000/wrong",
                page_start=1,
                page_end=1,
                source_type="body",
                snippet="solvent text",
                score=5.0,
                retrieval_method="exact_ilike",
            ),
            SearchResult(
                article_id=expected_article_id,
                chunk_id=str(uuid.uuid4()),
                title="Expected",
                doi="10.1000/expected",
                page_start=2,
                page_end=2,
                source_type="body",
                snippet="Nafion solvent morphology evidence",
                score=4.0,
                retrieval_method="exact_ilike",
            ),
        ],
    )

    payload = _evaluate_extended_question(question, response, {}, elapsed_ms=12.5, top_k=2)

    assert payload["passed"] is True
    assert payload["rank_of_first_relevant"] == 2
    assert payload["article_recall_at_k"] == 1.0
    assert payload["chunk_recall_at_k"] == 1.0
    assert payload["article_precision_at_k"] == 0.5
    assert payload["mrr"] == 0.5
    assert payload["ndcg_at_k"] < 1.0
    assert payload["evidence_trace_complete"] is True


def test_extended_evaluation_reports_unanswerable_separately(tmp_path) -> None:
    question = load_extended_questions_from_text(
        tmp_path,
        "- id: q_absent\n"
        "  query: absent topic\n"
        "  answerable: false\n"
        "  expected:\n"
        "    articles: []\n"
        "    chunks: []\n",
    )[0]
    response = SearchResponse(
        query="zirconium cerium extraterrestrial regolith perchlorate electrolyte",
        results=[
            SearchResult(
                article_id=str(uuid.uuid4()),
                chunk_id=str(uuid.uuid4()),
                title="Unrelated",
                doi=None,
                page_start=1,
                page_end=1,
                source_type="body",
                snippet="Nafion conductivity in polymer membranes.",
                score=1.0,
                retrieval_method="exact_ilike",
            )
        ],
    )

    payload = _evaluate_extended_question(question, response, {}, elapsed_ms=1.0, top_k=10)

    assert payload["passed"] is True
    assert payload["answerable"] is False
    assert payload["unanswerable_passed"] is True
    assert payload["evidence_adequacy"]["adequate"] is False
    assert payload["article_precision_at_k"] is None


def test_run_extended_retrieval_evaluation_summarizes_metrics(monkeypatch, tmp_path) -> None:
    questions_path = tmp_path / "questions_extended.yaml"
    questions_path.write_text(
        "- id: q01\n"
        "  query: Li-Nafion conductivity\n"
        "  expected:\n"
        "    articles:\n"
        "      - doi: 10.1000/example\n"
        "        relevance: 2\n"
        "    chunks:\n"
        "      - article_doi: 10.1000/example\n"
        "        text_contains:\n"
        "          - conductivity\n"
        "- id: q_absent\n"
        "  query: absent topic\n"
        "  answerable: false\n"
        "  expected:\n"
        "    articles: []\n"
        "    chunks: []\n",
        encoding="utf-8",
    )

    def fake_search_chunks(*args: object, **kwargs: object) -> SearchResponse:
        query = str(args[1])
        if query == "absent topic":
            return SearchResponse(query=query, results=[])
        return SearchResponse(
            query=query,
            results=[
                SearchResult(
                    article_id=str(uuid.uuid4()),
                    chunk_id=str(uuid.uuid4()),
                    title="Li-Nafion paper",
                    doi="10.1000/example",
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="conductivity evidence",
                    score=1.0,
                    retrieval_method="exact_ilike",
                )
            ],
        )

    monkeypatch.setattr("app.evaluation.retrieval.search_chunks", fake_search_chunks)
    monkeypatch.setattr("app.evaluation.retrieval._article_checksums_for_results", lambda session, result_payload: {})
    monkeypatch.setattr("app.evaluation.retrieval._git_commit", lambda: "abc")
    monkeypatch.setattr("app.evaluation.retrieval._corpus_manifest_sha256", lambda: "def")

    report = run_extended_retrieval_evaluation(
        object(),  # type: ignore[arg-type]
        SimpleNamespace(default_top_k=10),  # type: ignore[arg-type]
        questions_path,
        collection="literature",
        top_k=10,
        method="exact",
    )

    assert report["schema"] == "retrieval_eval_extended_v1"
    assert report["summary"]["total"] == 2
    assert report["summary"]["answerable"] == 1
    assert report["summary"]["unanswerable_passed"] == 1
    assert report["summary"]["unanswerable_pass_rate"] == 1.0
    assert report["summary"]["false_answerable"] == 0
    assert report["summary"]["article_recall_at_k"] == 1.0
    assert report["summary"]["mrr"] == 1.0
    assert report["provenance"]["git_commit"] == "abc"


def test_extended_thresholds_report_failures(tmp_path) -> None:
    path = tmp_path / "thresholds.yaml"
    path.write_text("exact:\n  min_mrr: 0.75\n  max_empty_result_queries: 0\n", encoding="utf-8")
    thresholds = load_evaluation_thresholds(path, "exact")
    report = {"summary": {"mrr": 0.5, "empty_result_queries": 1}}

    failures = check_extended_evaluation_thresholds(report, thresholds)

    assert failures == [
        {"threshold": "min_mrr", "metric": "mrr", "expected": 0.75, "actual": 0.5},
        {"threshold": "max_empty_result_queries", "metric": "empty_result_queries", "expected": 0.0, "actual": 1},
    ]


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


def load_extended_questions_from_text(tmp_path: Path, text: str) -> list[ExtendedEvaluationQuestion]:
    path = tmp_path / "questions_extended.yaml"
    path.write_text(text, encoding="utf-8")
    return load_extended_questions(path)


def test_write_evaluation_report_uses_exports_directory(tmp_path) -> None:
    output_path = write_evaluation_report({"summary": {"total": 0}}, Path(tmp_path))

    assert output_path.parent == tmp_path / "exports"
    assert output_path.name.startswith("retrieval_eval_")
    assert output_path.read_text(encoding="utf-8")


def test_write_extended_evaluation_report_uses_method_suffix(tmp_path) -> None:
    output_path = write_extended_evaluation_report({"settings": {"method": "hybrid"}, "summary": {}}, Path(tmp_path))

    assert output_path.parent == tmp_path / "exports"
    assert output_path.name.startswith("retrieval_eval_extended_hybrid_")
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


class SequenceScalarSession:
    def __init__(self, scalar_values: list[object]) -> None:
        self.scalar_values = scalar_values

    def scalar(self, statement: object) -> object:
        if not self.scalar_values:
            raise AssertionError(f"unexpected scalar query: {statement}")
        return self.scalar_values.pop(0)


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
