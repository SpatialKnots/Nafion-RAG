from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.retrieval.search import SearchResponse, exact_search, search_response_to_dict


@dataclass(frozen=True)
class EvaluationQuestion:
    id: str
    query: str
    expected_article_dois: list[str]
    expected_keywords: list[str]
    notes: str | None = None


def _string_list(value: object, field_name: str, question_id: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{question_id}.{field_name} must be a list of strings")
    return value


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
                    doi.lower() for doi in _string_list(item.get("expected_article_dois"), "expected_article_dois", question_id)
                ],
                expected_keywords=_string_list(item.get("expected_keywords"), "expected_keywords", question_id),
                notes=notes,
            )
        )
    return questions


def _evaluate_question(question: EvaluationQuestion, response: SearchResponse) -> dict[str, Any]:
    result_payload = cast(list[dict[str, object]], search_response_to_dict(response)["results"])
    result_dois = {str(result["doi"]).lower() for result in result_payload if result["doi"]}
    result_text = "\n".join(str(result["snippet"]) for result in result_payload).lower()
    missing_dois = [doi for doi in question.expected_article_dois if doi not in result_dois]
    missing_keywords = [keyword for keyword in question.expected_keywords if keyword.lower() not in result_text]
    passed = not missing_dois and not missing_keywords and bool(result_payload)
    return {
        "id": question.id,
        "query": question.query,
        "passed": passed,
        "expected_article_dois": question.expected_article_dois,
        "expected_keywords": question.expected_keywords,
        "missing_article_dois": missing_dois,
        "missing_keywords": missing_keywords,
        "result_count": len(result_payload),
        "results": result_payload,
    }


def run_retrieval_evaluation(
    session: Session,
    settings: Settings,
    questions_path: Path,
    *,
    collection: str,
    top_k: int,
) -> dict[str, Any]:
    questions = load_questions(questions_path)
    evaluated = [_evaluate_question(question, exact_search(session, question.query, collection, top_k)) for question in questions]
    failures = [item for item in evaluated if not item["passed"]]
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "questions_path": str(questions_path),
        "settings": {"collection": collection, "top_k": top_k, "retrieval_method": "exact_ilike", "default_top_k": settings.default_top_k},
        "summary": {
            "total": len(evaluated),
            "passed": len(evaluated) - len(failures),
            "failed": len(failures),
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
