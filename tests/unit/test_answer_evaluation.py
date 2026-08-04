from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

from app.evaluation.answers import _evaluate_answer, run_answer_evaluation, write_answer_evaluation_report
from app.evaluation.retrieval import EvaluationQuestion
from app.generation.providers import Evidence, GeneratedClaim
from app.generation.service import AnswerResponse


def test_evaluate_answer_checks_targets_keywords_and_citation_coverage() -> None:
    article_id = str(uuid.UUID(int=1))
    response = _answer_response(article_id)
    question = EvaluationQuestion(
        id="q01",
        query="conductivity",
        expected_article_dois=["10.1000/evidence"],
        expected_article_titles=[],
        expected_article_checksums=["checksum"],
        expected_keywords=["conductivity"],
    )

    result = _evaluate_answer(question, response, {article_id: "checksum"})

    assert result["passed"] is True
    assert result["citation_coverage"] == 1.0
    assert result["exact_extractive_claims"] == 1


def test_evaluate_answer_reports_missing_keyword() -> None:
    response = _answer_response(str(uuid.UUID(int=1)))
    question = EvaluationQuestion(
        id="q01",
        query="conductivity",
        expected_article_dois=["10.1000/evidence"],
        expected_article_titles=[],
        expected_article_checksums=[],
        expected_keywords=["absent"],
    )

    result = _evaluate_answer(question, response, {})

    assert result["passed"] is False
    assert result["missing_keywords"] == ["absent"]


def test_run_answer_evaluation_summarizes_answers(monkeypatch, tmp_path) -> None:
    questions_path = tmp_path / "questions.yaml"
    questions_path.write_text(
        "- id: q01\n  query: conductivity\n  expected_article_dois:\n    - 10.1000/evidence\n  expected_keywords:\n    - conductivity\n",
        encoding="utf-8",
    )
    response = _answer_response(str(uuid.UUID(int=1)))
    monkeypatch.setattr("app.evaluation.answers.answer_question", lambda *args, **kwargs: response)
    monkeypatch.setattr("app.evaluation.answers._citation_checksums", lambda *args, **kwargs: {})
    settings = SimpleNamespace(rag_provider="extractive", rag_model="")

    report = run_answer_evaluation(
        object(),  # type: ignore[arg-type]
        settings,  # type: ignore[arg-type]
        questions_path,
        collection="literature",
        top_k=5,
        method="hybrid",
    )

    assert report["summary"]["passed"] == 1
    assert report["summary"]["answered"] == 1
    assert report["summary"]["citation_coverage"] == 1.0


def test_write_answer_evaluation_report_uses_exports_directory(tmp_path) -> None:
    path = write_answer_evaluation_report({"summary": {}}, Path(tmp_path))

    assert path.parent == tmp_path / "exports"
    assert path.name.startswith("answer_eval_")


def _answer_response(article_id: str) -> AnswerResponse:
    text = "Conductivity was measured by impedance spectroscopy."
    return AnswerResponse(
        query="conductivity",
        status="answered",
        answer=f"{text} [E1]",
        claims=[GeneratedClaim(text=text, citation_ids=["E1"])],
        citations=[
            Evidence(
                citation_id="E1",
                article_id=article_id,
                chunk_id=str(uuid.UUID(int=2)),
                title="Evidence paper",
                doi="10.1000/evidence",
                page_start=1,
                page_end=2,
                source_type="method",
                text=text,
                score=0.03,
                retrieval_method="hybrid_rrf",
                method_scores={"exact_ilike": 10.0, "semantic_cosine": 0.8},
                method_ranks={"exact_ilike": 1, "semantic_cosine": 2},
            )
        ],
        retrieval_method="hybrid",
        generation_provider="extractive",
        generation_model=None,
        metadata={},
    )
