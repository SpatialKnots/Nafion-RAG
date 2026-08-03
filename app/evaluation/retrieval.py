from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article
from app.retrieval.search import SearchResponse, normalize_retrieval_method, search_chunks, search_response_to_dict


@dataclass(frozen=True)
class EvaluationQuestion:
    id: str
    query: str
    expected_article_dois: list[str]
    expected_article_titles: list[str]
    expected_article_checksums: list[str]
    expected_keywords: list[str]
    notes: str | None = None


def _normalize_title(value: str) -> str:
    return " ".join(value.lower().split())


def _string_list(value: object, field_name: str, question_id: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{question_id}.{field_name} must be a list of strings")
    return value


def _optional_string_list(value: object, field_name: str, question_id: str) -> list[str]:
    if value is None:
        return []
    return _string_list(value, field_name, question_id)


def load_questions(path: Path) -> list[EvaluationQuestion]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("evaluation questions file must contain a list")
    questions: list[EvaluationQuestion] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"question at index {index} must be a mapping")
        question_id = item.get("id")
        query = item.get("query")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"question at index {index} has invalid id")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{question_id}.query must be a non-empty string")
        notes = item.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise ValueError(f"{question_id}.notes must be a string when provided")
        questions.append(
            EvaluationQuestion(
                id=question_id,
                query=query,
                expected_article_dois=[
                    doi.lower() for doi in _optional_string_list(item.get("expected_article_dois"), "expected_article_dois", question_id)
                ],
                expected_article_titles=[
                    _normalize_title(title)
                    for title in _optional_string_list(item.get("expected_article_titles"), "expected_article_titles", question_id)
                ],
                expected_article_checksums=[
                    checksum.lower()
                    for checksum in _optional_string_list(item.get("expected_article_checksums"), "expected_article_checksums", question_id)
                ],
                expected_keywords=_string_list(item.get("expected_keywords"), "expected_keywords", question_id),
                notes=notes,
            )
        )
        if not (
            questions[-1].expected_article_dois
            or questions[-1].expected_article_titles
            or questions[-1].expected_article_checksums
        ):
            raise ValueError(
                f"{question_id} must define at least one of expected_article_dois, "
                "expected_article_titles, or expected_article_checksums"
            )
    return questions


def _article_checksums_for_results(session: Session, result_payload: list[dict[str, object]]) -> dict[str, str]:
    article_ids = [UUID(str(result["article_id"])) for result in result_payload if result.get("article_id")]
    if not article_ids:
        return {}
    rows = session.execute(select(Article.id, Article.checksum_sha256).where(Article.id.in_(article_ids))).all()
    return {str(article_id): checksum.lower() for article_id, checksum in rows}


def _result_matches_expected_article(
    result: dict[str, object],
    question: EvaluationQuestion,
    article_checksums: dict[str, str],
) -> bool:
    doi = result.get("doi")
    title = result.get("title")
    checksum = article_checksums.get(str(result["article_id"]))
    return (
        (bool(doi) and str(doi).lower() in question.expected_article_dois)
        or (bool(title) and _normalize_title(str(title)) in question.expected_article_titles)
        or (bool(checksum) and checksum in question.expected_article_checksums)
    )


def _rank_of_expected_article(
    result_payload: list[dict[str, object]],
    question: EvaluationQuestion,
    article_checksums: dict[str, str],
) -> int | None:
    for index, result in enumerate(result_payload, start=1):
        if _result_matches_expected_article(result, question, article_checksums):
            return index
    return None


def _evaluate_question(question: EvaluationQuestion, response: SearchResponse, article_checksums: dict[str, str]) -> dict[str, Any]:
    result_payload = cast(list[dict[str, object]], search_response_to_dict(response)["results"])
    result_dois = {str(result["doi"]).lower() for result in result_payload if result["doi"]}
    result_titles = {_normalize_title(str(result["title"])) for result in result_payload if result["title"]}
    result_checksums = {
        checksum for result in result_payload if (checksum := article_checksums.get(str(result["article_id"])))
    }
    result_text = "\n".join(str(result["snippet"]) for result in result_payload).lower()
    missing_dois = [doi for doi in question.expected_article_dois if doi not in result_dois]
    missing_titles = [title for title in question.expected_article_titles if title not in result_titles]
    missing_checksums = [checksum for checksum in question.expected_article_checksums if checksum not in result_checksums]
    missing_keywords = [keyword for keyword in question.expected_keywords if keyword.lower() not in result_text]
    passed = not missing_dois and not missing_titles and not missing_checksums and not missing_keywords and bool(result_payload)
    rank_of_expected = _rank_of_expected_article(result_payload, question, article_checksums)
    top_1_passed = rank_of_expected == 1 and not missing_keywords
    top_result = result_payload[0] if result_payload else None
    return {
        "id": question.id,
        "query": question.query,
        "passed": passed,
        "top_1_passed": top_1_passed,
        "rank_of_expected": rank_of_expected,
        "recall_at_k": 1.0 if rank_of_expected is not None else 0.0,
        "expected_article_dois": question.expected_article_dois,
        "expected_article_titles": question.expected_article_titles,
        "expected_article_checksums": question.expected_article_checksums,
        "expected_keywords": question.expected_keywords,
        "missing_article_dois": missing_dois,
        "missing_article_titles": missing_titles,
        "missing_article_checksums": missing_checksums,
        "missing_keywords": missing_keywords,
        "result_count": len(result_payload),
        "top_result": top_result,
        "results": result_payload,
    }


def run_retrieval_evaluation(
    session: Session,
    settings: Settings,
    questions_path: Path,
    *,
    collection: str,
    top_k: int,
    method: str = "exact",
) -> dict[str, Any]:
    normalized_method = normalize_retrieval_method(method)
    questions = load_questions(questions_path)
    evaluated = []
    for question in questions:
        response = search_chunks(session, question.query, collection, top_k, method=normalized_method)
        result_payload = cast(list[dict[str, object]], search_response_to_dict(response)["results"])
        evaluated.append(_evaluate_question(question, response, _article_checksums_for_results(session, result_payload)))
    failures = [item for item in evaluated if not item["passed"]]
    ranks = [item["rank_of_expected"] for item in evaluated if isinstance(item["rank_of_expected"], int)]
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "questions_path": str(questions_path),
        "settings": {
            "collection": collection,
            "top_k": top_k,
            "method": normalized_method,
            "retrieval_method": "exact_ilike",
            "default_top_k": settings.default_top_k,
        },
        "summary": {
            "total": len(evaluated),
            "passed": len(evaluated) - len(failures),
            "top_1_passed": sum(1 for item in evaluated if item["top_1_passed"]),
            "failed": len(failures),
            "recall_at_k": (sum(float(item["recall_at_k"]) for item in evaluated) / len(evaluated)) if evaluated else 0.0,
            "mean_rank": (sum(ranks) / len(ranks)) if ranks else None,
            "empty_result_queries": sum(1 for item in evaluated if item["result_count"] == 0),
        },
        "questions": evaluated,
        "failures": failures,
    }


def write_evaluation_report(report: dict[str, Any], data_root: Path) -> Path:
    export_dir = data_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = export_dir / f"retrieval_eval_{timestamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
