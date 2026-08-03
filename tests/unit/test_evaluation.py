from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.evaluation.retrieval import load_questions, run_retrieval_evaluation, write_evaluation_report
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
    assert questions[0].expected_keywords == ["conductivity"]


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

    def fake_exact_search(session: object, query: str, collection_name: str, top_k: int) -> SearchResponse:
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

    monkeypatch.setattr("app.evaluation.retrieval.exact_search", fake_exact_search)

    report = run_retrieval_evaluation(
        object(),  # type: ignore[arg-type]
        SimpleNamespace(default_top_k=10),  # type: ignore[arg-type]
        questions_path,
        collection="literature",
        top_k=5,
    )

    assert report["summary"] == {"total": 1, "passed": 0, "failed": 1, "empty_result_queries": 0}
    question = report["questions"][0]
    assert question["missing_article_dois"] == []
    assert question["missing_keywords"] == ["NMP"]
    assert question["result_count"] == 1
    assert question["top_result"]["doi"] == "10.1000/example"
    assert question["top_result"]["retrieval_method"] == "exact_ilike"


def test_write_evaluation_report_uses_exports_directory(tmp_path) -> None:
    output_path = write_evaluation_report({"summary": {"total": 0}}, Path(tmp_path))

    assert output_path.parent == tmp_path / "exports"
    assert output_path.name.startswith("retrieval_eval_")
    assert output_path.read_text(encoding="utf-8")
