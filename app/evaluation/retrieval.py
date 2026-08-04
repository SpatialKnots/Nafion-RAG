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
from app.retrieval.search import (
    SearchFilters,
    SearchResponse,
    concrete_retrieval_method,
    normalize_retrieval_method,
    search_chunks,
    search_response_to_dict,
)


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
        if not (questions[-1].expected_article_dois or questions[-1].expected_article_titles or questions[-1].expected_article_checksums):
            raise ValueError(
                f"{question_id} must define at least one of expected_article_dois, expected_article_titles, or expected_article_checksums"
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


def _result_payloads_from_response(response: SearchResponse) -> list[dict[str, object]]:
    payload = search_response_to_dict(response)
    if "results" in payload:
        return cast(list[dict[str, object]], payload["results"])
    grouped_results: list[dict[str, object]] = []
    groups = payload.get("groups", [])
    if not isinstance(groups, list):
        return grouped_results
    for group in groups:
        if isinstance(group, dict) and isinstance(group.get("results"), list):
            grouped_results.extend(cast(list[dict[str, object]], group["results"]))
    return grouped_results


def _evaluate_question(question: EvaluationQuestion, response: SearchResponse, article_checksums: dict[str, str]) -> dict[str, Any]:
    result_payload = _result_payloads_from_response(response)
    result_dois = {str(result["doi"]).lower() for result in result_payload if result["doi"]}
    result_titles = {_normalize_title(str(result["title"])) for result in result_payload if result["title"]}
    result_checksums = {checksum for result in result_payload if (checksum := article_checksums.get(str(result["article_id"])))}
    result_text = "\n".join(str(result["snippet"]) for result in result_payload).lower()
    missing_dois = [doi for doi in question.expected_article_dois if doi not in result_dois]
    missing_titles = [title for title in question.expected_article_titles if title not in result_titles]
    missing_checksums = [checksum for checksum in question.expected_article_checksums if checksum not in result_checksums]
    missing_keywords = [keyword for keyword in question.expected_keywords if keyword.lower() not in result_text]
    passed = not missing_dois and not missing_titles and not missing_checksums and not missing_keywords and bool(result_payload)
    rank_of_expected = _rank_of_expected_article(result_payload, question, article_checksums)
    top_1_passed = rank_of_expected == 1 and not missing_keywords
    top_result = result_payload[0] if result_payload else None
    candidate_count_before_grouping = response.metadata.get("candidate_count_before_grouping")
    group_count = response.metadata.get("group_count")
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
        "candidate_count_before_grouping": candidate_count_before_grouping,
        "group_count": group_count,
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
    filters: SearchFilters | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
) -> dict[str, Any]:
    normalized_method = normalize_retrieval_method(method)
    normalized_filters = filters or SearchFilters()
    questions = load_questions(questions_path)
    evaluated = []
    retrieval_metadata: dict[str, object] = {}
    for question in questions:
        response = search_chunks(
            session,
            question.query,
            collection,
            top_k,
            method=normalized_method,
            filters=normalized_filters,
            group_by=group_by,
            chunks_per_article=chunks_per_article,
            settings=settings,
        )
        if response.metadata:
            if retrieval_metadata and response.metadata != retrieval_metadata:
                raise ValueError("retrieval metadata changed during evaluation")
            retrieval_metadata = response.metadata
        result_payload = _result_payloads_from_response(response)
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
            "retrieval_method": concrete_retrieval_method(normalized_method),
            "filter_mode": "filtered" if normalized_filters.as_metadata() else "unfiltered",
            "filters": normalized_filters.as_metadata(),
            "group_by": group_by,
            "chunks_per_article": chunks_per_article,
            "default_top_k": settings.default_top_k,
            "retrieval_metadata": retrieval_metadata,
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
    settings = report.get("settings")
    method = settings.get("method") if isinstance(settings, dict) else None
    method_suffix = f"_{method}" if isinstance(method, str) and method else ""
    output_path = export_dir / f"retrieval_eval{method_suffix}_{timestamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def compare_retrieval_reports(exact_report: dict[str, Any], candidate_report: dict[str, Any]) -> dict[str, Any]:
    exact_settings = exact_report.get("settings")
    candidate_settings = candidate_report.get("settings")
    if not isinstance(exact_settings, dict) or exact_settings.get("method") != "exact":
        raise ValueError("exact report must use method=exact")
    if not isinstance(candidate_settings, dict) or candidate_settings.get("method") == "exact":
        raise ValueError("candidate report must use a non-exact method")
    for field in ("collection", "top_k"):
        if exact_settings.get(field) != candidate_settings.get(field):
            raise ValueError(f"report settings mismatch for {field}")

    exact_questions = exact_report.get("questions")
    candidate_questions = candidate_report.get("questions")
    if not isinstance(exact_questions, list) or not isinstance(candidate_questions, list):
        raise ValueError("reports must contain question lists")
    exact_by_id = {item.get("id"): item for item in exact_questions if isinstance(item, dict)}
    candidate_by_id = {item.get("id"): item for item in candidate_questions if isinstance(item, dict)}
    if set(exact_by_id) != set(candidate_by_id):
        raise ValueError("reports contain different evaluation question ids")

    regressions = []
    improvements = []
    top_1_regressions = []
    rank_changes = []
    for question_id in exact_by_id:
        exact_item = exact_by_id[question_id]
        candidate_item = candidate_by_id[question_id]
        if exact_item.get("query") != candidate_item.get("query"):
            raise ValueError(f"reports contain different query text for {question_id}")
        exact_rank = exact_item.get("rank_of_expected")
        candidate_rank = candidate_item.get("rank_of_expected")
        rank_changes.append(
            {
                "id": question_id,
                "exact_rank": exact_rank,
                "candidate_rank": candidate_rank,
                "delta": (exact_rank - candidate_rank) if isinstance(exact_rank, int) and isinstance(candidate_rank, int) else None,
            }
        )
        if exact_item.get("passed") is True and candidate_item.get("passed") is not True:
            regressions.append(question_id)
        if exact_item.get("top_1_passed") is True and candidate_item.get("top_1_passed") is not True:
            top_1_regressions.append(question_id)
        if exact_item.get("top_1_passed") is not True and candidate_item.get("top_1_passed") is True:
            improvements.append(question_id)

    exact_summary = exact_report.get("summary")
    candidate_summary = candidate_report.get("summary")
    if not isinstance(exact_summary, dict) or not isinstance(candidate_summary, dict):
        raise ValueError("reports must contain summaries")

    def numeric_delta(field: str) -> float | None:
        exact_value = exact_summary.get(field)
        candidate_value = candidate_summary.get(field)
        if isinstance(exact_value, (int, float)) and isinstance(candidate_value, (int, float)):
            return float(candidate_value) - float(exact_value)
        return None

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "exact_method": exact_settings["retrieval_method"],
        "candidate_method": candidate_settings["retrieval_method"],
        "settings": {"collection": exact_settings["collection"], "top_k": exact_settings["top_k"]},
        "summary": {
            "exact": exact_summary,
            "candidate": candidate_summary,
            "top_1_passed_delta": numeric_delta("top_1_passed"),
            "recall_at_k_delta": numeric_delta("recall_at_k"),
            "mean_rank_delta": numeric_delta("mean_rank"),
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
            "top_1_regression_count": len(top_1_regressions),
        },
        "regressions": regressions,
        "improvements": improvements,
        "top_1_regressions": top_1_regressions,
        "top_1_improvements": improvements,
        "rank_changes": rank_changes,
    }


def compare_retrieval_methods(
    exact_report: dict[str, Any],
    semantic_report: dict[str, Any],
    hybrid_report: dict[str, Any],
) -> dict[str, Any]:
    semantic_settings = semantic_report.get("settings")
    hybrid_settings = hybrid_report.get("settings")
    if not isinstance(semantic_settings, dict) or semantic_settings.get("method") != "semantic":
        raise ValueError("semantic report must use method=semantic")
    if not isinstance(hybrid_settings, dict) or hybrid_settings.get("method") != "hybrid":
        raise ValueError("hybrid report must use method=hybrid")

    exact_vs_semantic = compare_retrieval_reports(exact_report, semantic_report)
    exact_vs_hybrid = compare_retrieval_reports(exact_report, hybrid_report)
    semantic_summary = semantic_report.get("summary")
    hybrid_summary = hybrid_report.get("summary")
    if not isinstance(semantic_summary, dict) or not isinstance(hybrid_summary, dict):
        raise ValueError("reports must contain summaries")

    def deltas(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, float | None]:
        payload: dict[str, float | None] = {}
        for field in ("passed", "top_1_passed", "recall_at_k", "mean_rank", "empty_result_queries"):
            candidate_value = candidate.get(field)
            baseline_value = baseline.get(field)
            payload[field] = (
                float(candidate_value) - float(baseline_value)
                if isinstance(candidate_value, (int, float)) and isinstance(baseline_value, (int, float))
                else None
            )
        return payload

    exact_questions = {item["id"]: item for item in exact_report["questions"]}
    semantic_questions = {item["id"]: item for item in semantic_report["questions"]}
    hybrid_questions = {item["id"]: item for item in hybrid_report["questions"]}
    question_comparison = []
    for question_id in exact_questions:
        exact_item = exact_questions[question_id]
        semantic_item = semantic_questions[question_id]
        hybrid_item = hybrid_questions[question_id]
        question_comparison.append(
            {
                "id": question_id,
                "query": exact_item["query"],
                "exact_rank": exact_item["rank_of_expected"],
                "semantic_rank": semantic_item["rank_of_expected"],
                "hybrid_rank": hybrid_item["rank_of_expected"],
                "exact_passed": exact_item["passed"],
                "semantic_passed": semantic_item["passed"],
                "hybrid_passed": hybrid_item["passed"],
                "exact_top_1_passed": exact_item["top_1_passed"],
                "semantic_top_1_passed": semantic_item["top_1_passed"],
                "hybrid_top_1_passed": hybrid_item["top_1_passed"],
            }
        )

    exact_summary = exact_report["summary"]
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "settings": exact_vs_hybrid["settings"],
        "methods": {
            "exact_ilike": exact_summary,
            "semantic_cosine": semantic_summary,
            "hybrid_rrf": hybrid_summary,
        },
        "deltas": {
            "semantic_vs_exact": deltas(semantic_summary, exact_summary),
            "hybrid_vs_exact": deltas(hybrid_summary, exact_summary),
            "hybrid_vs_semantic": deltas(hybrid_summary, semantic_summary),
        },
        "hybrid_regressions_vs_exact": exact_vs_hybrid["regressions"],
        "hybrid_improvements_vs_exact": exact_vs_hybrid["improvements"],
        "hybrid_top_1_regressions_vs_exact": exact_vs_hybrid["top_1_regressions"],
        "hybrid_top_1_improvements_vs_exact": exact_vs_hybrid["top_1_improvements"],
        "semantic_regressions_vs_exact": exact_vs_semantic["regressions"],
        "semantic_improvements_vs_exact": exact_vs_semantic["improvements"],
        "semantic_top_1_regressions_vs_exact": exact_vs_semantic["top_1_regressions"],
        "semantic_top_1_improvements_vs_exact": exact_vs_semantic["top_1_improvements"],
        "questions": question_comparison,
    }


def load_evaluation_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evaluation report must contain an object: {path}")
    return payload


def write_comparison_report(report: dict[str, Any], data_root: Path) -> Path:
    export_dir = data_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = export_dir / f"retrieval_comparison_{timestamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
