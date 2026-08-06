from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Chunk
from app.generation.evidence_adequacy import assess_evidence_adequacy
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


@dataclass(frozen=True)
class ExtendedExpectedArticle:
    doi: str | None = None
    title: str | None = None
    title_contains: str | None = None
    checksum: str | None = None
    article_id: str | None = None
    relevance: int = 1


@dataclass(frozen=True)
class ExtendedExpectedChunk:
    article_doi: str | None = None
    article_title: str | None = None
    article_title_contains: str | None = None
    article_checksum: str | None = None
    article_id: str | None = None
    chunk_id: str | None = None
    text_contains: list[str] | None = None
    relevance: int = 1


@dataclass(frozen=True)
class ExtendedEvaluationQuestion:
    id: str
    query: str
    expected_articles: list[ExtendedExpectedArticle]
    expected_chunks: list[ExtendedExpectedChunk]
    answerable: bool = True
    language: str | None = None
    filters: dict[str, object] | None = None
    notes: str | None = None


@dataclass(frozen=True)
class _EvidenceSnippet:
    text: str


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


def _optional_bool(value: object, field_name: str, question_id: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{question_id}.{field_name} must be a boolean")
    return value


def _optional_string(value: object, field_name: str, question_id: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{question_id}.{field_name} must be a string")
    stripped = value.strip()
    return stripped or None


def _optional_lower_string(value: object, field_name: str, question_id: str) -> str | None:
    normalized = _optional_string(value, field_name, question_id)
    return normalized.lower() if normalized is not None else None


def _optional_int(value: object, field_name: str, question_id: str, *, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{question_id}.{field_name} must be a non-negative integer")
    return value


def _extended_article_from_old_question(question: EvaluationQuestion) -> list[ExtendedExpectedArticle]:
    articles: list[ExtendedExpectedArticle] = []
    articles.extend(ExtendedExpectedArticle(doi=doi, relevance=1) for doi in question.expected_article_dois)
    articles.extend(ExtendedExpectedArticle(title=title, relevance=1) for title in question.expected_article_titles)
    articles.extend(ExtendedExpectedArticle(checksum=checksum, relevance=1) for checksum in question.expected_article_checksums)
    return articles


def load_extended_questions(path: Path) -> list[ExtendedEvaluationQuestion]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("extended evaluation questions file must contain a list")
    questions: list[ExtendedEvaluationQuestion] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"question at index {index} must be a mapping")
        question_id = item.get("id")
        query = item.get("query")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"question at index {index} has invalid id")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{question_id}.query must be a non-empty string")
        notes = _optional_string(item.get("notes"), "notes", question_id)
        language = _optional_string(item.get("language"), "language", question_id)
        filters = item.get("filters")
        if filters is not None and not isinstance(filters, dict):
            raise ValueError(f"{question_id}.filters must be a mapping when provided")
        answerable = _optional_bool(item.get("answerable"), "answerable", question_id, default=True)
        expected = item.get("expected")
        if expected is None:
            old_question = EvaluationQuestion(
                id=question_id,
                query=query,
                expected_article_dois=[
                    doi.lower()
                    for doi in _optional_string_list(item.get("expected_article_dois"), "expected_article_dois", question_id)
                ],
                expected_article_titles=[
                    _normalize_title(title)
                    for title in _optional_string_list(item.get("expected_article_titles"), "expected_article_titles", question_id)
                ],
                expected_article_checksums=[
                    checksum.lower()
                    for checksum in _optional_string_list(
                        item.get("expected_article_checksums"), "expected_article_checksums", question_id
                    )
                ],
                expected_keywords=_optional_string_list(item.get("expected_keywords"), "expected_keywords", question_id),
                notes=notes,
            )
            questions.append(
                ExtendedEvaluationQuestion(
                    id=old_question.id,
                    query=old_question.query,
                    expected_articles=_extended_article_from_old_question(old_question),
                    expected_chunks=[
                        ExtendedExpectedChunk(text_contains=old_question.expected_keywords, relevance=1)
                    ]
                    if old_question.expected_keywords
                    else [],
                    answerable=answerable,
                    language=language,
                    filters=cast(dict[str, object] | None, filters),
                    notes=old_question.notes,
                )
            )
        else:
            if not isinstance(expected, dict):
                raise ValueError(f"{question_id}.expected must be a mapping")
            questions.append(
                ExtendedEvaluationQuestion(
                    id=question_id,
                    query=query,
                    expected_articles=_load_extended_expected_articles(expected.get("articles"), question_id),
                    expected_chunks=_load_extended_expected_chunks(expected.get("chunks"), question_id),
                    answerable=answerable,
                    language=language,
                    filters=cast(dict[str, object] | None, filters),
                    notes=notes,
                )
            )
        latest = questions[-1]
        if latest.answerable and not latest.expected_articles and not latest.expected_chunks:
            raise ValueError(f"{question_id} must define expected articles or chunks when answerable=true")
        if not latest.answerable and (latest.expected_articles or latest.expected_chunks):
            raise ValueError(f"{question_id} must not define expected articles or chunks when answerable=false")
    return questions


def _load_extended_expected_articles(value: object, question_id: str) -> list[ExtendedExpectedArticle]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{question_id}.expected.articles must be a list")
    articles: list[ExtendedExpectedArticle] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{question_id}.expected.articles[{index}] must be a mapping")
        relevance = _optional_int(item.get("relevance"), f"expected.articles[{index}].relevance", question_id, default=1)
        title = _optional_string(item.get("title"), f"expected.articles[{index}].title", question_id)
        title_contains = _optional_string(item.get("title_contains"), f"expected.articles[{index}].title_contains", question_id)
        article = ExtendedExpectedArticle(
            doi=_optional_lower_string(item.get("doi"), f"expected.articles[{index}].doi", question_id),
            title=_normalize_title(title) if title else None,
            title_contains=_normalize_title(title_contains) if title_contains else None,
            checksum=_optional_lower_string(item.get("checksum"), f"expected.articles[{index}].checksum", question_id),
            article_id=_optional_string(item.get("article_id"), f"expected.articles[{index}].article_id", question_id),
            relevance=relevance,
        )
        if not (article.doi or article.title or article.title_contains or article.checksum or article.article_id):
            raise ValueError(f"{question_id}.expected.articles[{index}] must define a stable article target")
        articles.append(article)
    return articles


def _load_extended_expected_chunks(value: object, question_id: str) -> list[ExtendedExpectedChunk]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{question_id}.expected.chunks must be a list")
    chunks: list[ExtendedExpectedChunk] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{question_id}.expected.chunks[{index}] must be a mapping")
        text_contains = _optional_string_list(item.get("text_contains"), f"expected.chunks[{index}].text_contains", question_id)
        article_title = _optional_string(item.get("article_title"), f"expected.chunks[{index}].article_title", question_id)
        article_title_contains = _optional_string(
            item.get("article_title_contains"), f"expected.chunks[{index}].article_title_contains", question_id
        )
        chunk = ExtendedExpectedChunk(
            article_doi=_optional_lower_string(item.get("article_doi"), f"expected.chunks[{index}].article_doi", question_id),
            article_title=_normalize_title(article_title) if article_title else None,
            article_title_contains=_normalize_title(article_title_contains) if article_title_contains else None,
            article_checksum=_optional_lower_string(
                item.get("article_checksum"), f"expected.chunks[{index}].article_checksum", question_id
            ),
            article_id=_optional_string(item.get("article_id"), f"expected.chunks[{index}].article_id", question_id),
            chunk_id=_optional_string(item.get("chunk_id"), f"expected.chunks[{index}].chunk_id", question_id),
            text_contains=text_contains,
            relevance=_optional_int(item.get("relevance"), f"expected.chunks[{index}].relevance", question_id, default=1),
        )
        if not (
            chunk.article_doi
            or chunk.article_title
            or chunk.article_title_contains
            or chunk.article_checksum
            or chunk.article_id
            or chunk.chunk_id
            or chunk.text_contains
        ):
            raise ValueError(f"{question_id}.expected.chunks[{index}] must define a stable chunk target")
        chunks.append(chunk)
    return chunks


def _article_checksums_for_results(session: Session, result_payload: list[dict[str, object]]) -> dict[str, str]:
    article_ids = [UUID(str(result["article_id"])) for result in result_payload if result.get("article_id")]
    if not article_ids:
        return {}
    rows = session.execute(select(Article.id, Article.checksum_sha256).where(Article.id.in_(article_ids))).all()
    return {str(article_id): checksum.lower() for article_id, checksum in rows}


def _chunk_texts_for_results(session: Session, result_payload: list[dict[str, object]]) -> dict[str, str]:
    chunk_ids = [UUID(str(result["chunk_id"])) for result in result_payload if result.get("chunk_id")]
    if not chunk_ids:
        return {}
    rows = session.execute(select(Chunk.id, Chunk.text).where(Chunk.id.in_(chunk_ids))).all()
    return {str(chunk_id): text for chunk_id, text in rows}


def _evaluation_text_for_result(result: dict[str, object], chunk_texts: dict[str, str] | None = None) -> str:
    parts = [str(result.get("snippet", ""))]
    if chunk_texts is not None:
        chunk_text = chunk_texts.get(str(result.get("chunk_id")))
        if chunk_text:
            parts.append(chunk_text)
    return "\n".join(parts).lower()


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


def _result_matches_extended_article(
    result: dict[str, object],
    expected: ExtendedExpectedArticle,
    article_checksums: dict[str, str],
) -> bool:
    doi = result.get("doi")
    title = result.get("title")
    article_id = str(result.get("article_id"))
    checksum = article_checksums.get(article_id)
    normalized_title = _normalize_title(str(title)) if title else None
    return (
        (bool(expected.doi) and bool(doi) and str(doi).lower() == expected.doi)
        or (bool(expected.title) and normalized_title == expected.title)
        or (
            expected.title_contains is not None
            and normalized_title is not None
            and expected.title_contains in normalized_title
        )
        or (bool(expected.checksum) and checksum == expected.checksum)
        or (bool(expected.article_id) and article_id == expected.article_id)
    )


def _result_matches_extended_chunk(
    result: dict[str, object],
    expected: ExtendedExpectedChunk,
    article_checksums: dict[str, str],
    chunk_texts: dict[str, str] | None = None,
) -> bool:
    article_target = ExtendedExpectedArticle(
        doi=expected.article_doi,
        title=expected.article_title,
        title_contains=expected.article_title_contains,
        checksum=expected.article_checksum,
        article_id=expected.article_id,
        relevance=expected.relevance,
    )
    has_article_target = any(
        (
            article_target.doi,
            article_target.title,
            article_target.title_contains,
            article_target.checksum,
            article_target.article_id,
        )
    )
    if has_article_target and not _result_matches_extended_article(result, article_target, article_checksums):
        return False
    if expected.chunk_id and str(result.get("chunk_id")) != expected.chunk_id:
        return False
    if expected.text_contains:
        text = _evaluation_text_for_result(result, chunk_texts)
        if not all(fragment.lower() in text for fragment in expected.text_contains):
            return False
    return True


def _relevance_for_result(
    result: dict[str, object],
    question: ExtendedEvaluationQuestion,
    article_checksums: dict[str, str],
    chunk_texts: dict[str, str] | None = None,
) -> int:
    relevance = 0
    for expected_article in question.expected_articles:
        if _result_matches_extended_article(result, expected_article, article_checksums):
            relevance = max(relevance, expected_article.relevance)
    for expected_chunk in question.expected_chunks:
        if _result_matches_extended_chunk(result, expected_chunk, article_checksums, chunk_texts):
            relevance = max(relevance, expected_chunk.relevance)
    return relevance


def _unique_expected_relevances_for_results(
    result_payload: list[dict[str, object]],
    question: ExtendedEvaluationQuestion,
    article_checksums: dict[str, str],
    chunk_texts: dict[str, str] | None = None,
) -> list[int]:
    used_articles: set[int] = set()
    used_chunks: set[int] = set()
    relevances: list[int] = []
    for result in result_payload:
        relevance = 0
        for index, expected_article in enumerate(question.expected_articles):
            if index not in used_articles and _result_matches_extended_article(result, expected_article, article_checksums):
                relevance = max(relevance, expected_article.relevance)
                used_articles.add(index)
        for index, expected_chunk in enumerate(question.expected_chunks):
            if index not in used_chunks and _result_matches_extended_chunk(result, expected_chunk, article_checksums, chunk_texts):
                relevance = max(relevance, expected_chunk.relevance)
                used_chunks.add(index)
        relevances.append(relevance)
    return relevances


def _first_relevant_rank(relevances: list[int]) -> int | None:
    for index, relevance in enumerate(relevances, start=1):
        if relevance > 0:
            return index
    return None


def _dcg(relevances: list[int]) -> float:
    return float(sum(((2**relevance) - 1) / math.log2(index + 1) for index, relevance in enumerate(relevances, start=1)))


def _ndcg_at_k(result_relevances: list[int], expected_relevances: list[int], top_k: int) -> float:
    ideal = sorted(expected_relevances, reverse=True)[:top_k]
    ideal_dcg = _dcg(ideal)
    if ideal_dcg == 0:
        return 0.0
    return _dcg(result_relevances[:top_k]) / ideal_dcg


def _result_has_trace(result: dict[str, object]) -> bool:
    required = ("article_id", "chunk_id", "page_start", "page_end", "source_type", "text_layer", "snippet")
    return all(result.get(field) not in (None, "") for field in required)


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


def _evaluate_question(
    question: EvaluationQuestion,
    response: SearchResponse,
    article_checksums: dict[str, str],
    chunk_texts: dict[str, str] | None = None,
) -> dict[str, Any]:
    result_payload = _result_payloads_from_response(response)
    result_dois = {str(result["doi"]).lower() for result in result_payload if result["doi"]}
    result_titles = {_normalize_title(str(result["title"])) for result in result_payload if result["title"]}
    result_checksums = {checksum for result in result_payload if (checksum := article_checksums.get(str(result["article_id"])))}
    result_text = "\n".join(_evaluation_text_for_result(result, chunk_texts) for result in result_payload)
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
        evaluated.append(
            _evaluate_question(
                question,
                response,
                _article_checksums_for_results(session, result_payload),
                _chunk_texts_for_results(session, result_payload),
            )
        )
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


def _corpus_manifest_sha256() -> str | None:
    manifest_path = Path("docs/corpus_manifest.json")
    if not manifest_path.exists():
        return None
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def _evaluate_extended_question(
    question: ExtendedEvaluationQuestion,
    response: SearchResponse,
    article_checksums: dict[str, str],
    chunk_texts: dict[str, str] | None = None,
    *,
    elapsed_ms: float,
    top_k: int,
) -> dict[str, Any]:
    result_payload = _result_payloads_from_response(response)
    evidence_for_adequacy = [_EvidenceSnippet(str(result.get("snippet", ""))) for result in result_payload]
    adequacy = assess_evidence_adequacy(question.query, evidence_for_adequacy)
    adequacy_payload = {
        "adequate": adequacy.adequate,
        "reason": adequacy.reason,
        "distinctive_terms": adequacy.distinctive_terms,
        "matched_terms": adequacy.matched_terms,
        "top_matched_terms": adequacy.top_matched_terms,
        "coverage": adequacy.coverage,
        "top_coverage": adequacy.top_coverage,
    }
    relevances = [_relevance_for_result(result, question, article_checksums, chunk_texts) for result in result_payload]
    unique_relevances = _unique_expected_relevances_for_results(result_payload, question, article_checksums, chunk_texts)
    first_rank = _first_relevant_rank(relevances)
    relevant_result_count = sum(1 for relevance in relevances if relevance > 0)
    expected_article_hits = [
        any(_result_matches_extended_article(result, expected, article_checksums) for result in result_payload)
        for expected in question.expected_articles
    ]
    expected_chunk_hits = [
        any(_result_matches_extended_chunk(result, expected, article_checksums, chunk_texts) for result in result_payload)
        for expected in question.expected_chunks
    ]
    expected_relevances = [expected.relevance for expected in question.expected_articles]
    expected_relevances.extend(expected.relevance for expected in question.expected_chunks)
    article_recall = (
        sum(1 for hit in expected_article_hits if hit) / len(expected_article_hits) if expected_article_hits else None
    )
    chunk_recall = sum(1 for hit in expected_chunk_hits if hit) / len(expected_chunk_hits) if expected_chunk_hits else None
    precision = relevant_result_count / len(result_payload) if result_payload else 0.0
    mrr = 1.0 / first_rank if first_rank is not None else 0.0
    ndcg = _ndcg_at_k(unique_relevances, expected_relevances, top_k) if question.answerable else None
    trace_complete = all(_result_has_trace(result) for result in result_payload)
    if question.answerable:
        passed = (article_recall in (None, 1.0)) and (chunk_recall in (None, 1.0)) and bool(result_payload)
    else:
        passed = not adequacy.adequate
    return {
        "id": question.id,
        "query": question.query,
        "language": question.language,
        "answerable": question.answerable,
        "passed": passed,
        "rank_of_first_relevant": first_rank,
        "top_1_passed": first_rank == 1 if question.answerable else False,
        "article_recall_at_k": article_recall,
        "chunk_recall_at_k": chunk_recall,
        "article_precision_at_k": precision if question.answerable else None,
        "mrr": mrr if question.answerable else None,
        "ndcg_at_k": ndcg,
        "unanswerable_passed": passed if not question.answerable else None,
        "evidence_adequacy": adequacy_payload,
        "result_relevances": relevances,
        "unique_expected_relevances": unique_relevances,
        "result_count": len(result_payload),
        "elapsed_ms": elapsed_ms,
        "evidence_trace_complete": trace_complete,
        "missing_expected_articles": [
            expected for expected, hit in zip(question.expected_articles, expected_article_hits, strict=True) if not hit
        ],
        "missing_expected_chunks": [
            expected for expected, hit in zip(question.expected_chunks, expected_chunk_hits, strict=True) if not hit
        ],
        "top_result": result_payload[0] if result_payload else None,
        "results": result_payload,
    }


def run_extended_retrieval_evaluation(
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
    questions = load_extended_questions(questions_path)
    evaluated = []
    retrieval_metadata: dict[str, object] = {}
    for question in questions:
        started = time.perf_counter()
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
        elapsed_ms = (time.perf_counter() - started) * 1000
        if response.metadata:
            if retrieval_metadata and response.metadata != retrieval_metadata:
                raise ValueError("retrieval metadata changed during evaluation")
            retrieval_metadata = response.metadata
        result_payload = _result_payloads_from_response(response)
        evaluated.append(
            _evaluate_extended_question(
                question,
                response,
                _article_checksums_for_results(session, result_payload),
                _chunk_texts_for_results(session, result_payload),
                elapsed_ms=elapsed_ms,
                top_k=top_k,
            )
        )
    answerable = [item for item in evaluated if item["answerable"]]
    unanswerable = [item for item in evaluated if not item["answerable"]]
    failures = [item for item in evaluated if not item["passed"]]
    ranks = [item["rank_of_first_relevant"] for item in answerable if isinstance(item["rank_of_first_relevant"], int)]
    latencies = sorted(float(item["elapsed_ms"]) for item in evaluated)
    summary = {
        "total": len(evaluated),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "passed": len(evaluated) - len(failures),
        "failed": len(failures),
        "article_recall_at_k": _mean_optional(answerable, "article_recall_at_k"),
        "chunk_recall_at_k": _mean_optional(answerable, "chunk_recall_at_k"),
        "article_precision_at_k": _mean_optional(answerable, "article_precision_at_k"),
        "mrr": _mean_optional(answerable, "mrr"),
        "ndcg_at_k": _mean_optional(answerable, "ndcg_at_k"),
        "top_1_passed": sum(1 for item in answerable if item["top_1_passed"]),
        "mean_rank": (sum(ranks) / len(ranks)) if ranks else None,
        "empty_result_queries": sum(1 for item in evaluated if item["result_count"] == 0),
        "unanswerable_passed": sum(1 for item in unanswerable if item["unanswerable_passed"] is True),
        "unanswerable_pass_rate": (
            sum(1 for item in unanswerable if item["unanswerable_passed"] is True) / len(unanswerable) if unanswerable else None
        ),
        "false_answerable": sum(1 for item in unanswerable if item["unanswerable_passed"] is not True),
        "evidence_trace_complete": all(bool(item["evidence_trace_complete"]) for item in evaluated),
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
    }
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "schema": "retrieval_eval_extended_v1",
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
        "provenance": {
            "corpus_manifest_path": "docs/corpus_manifest.json",
            "corpus_manifest_sha256": _corpus_manifest_sha256(),
            "git_commit": _git_commit(),
        },
        "summary": summary,
        "questions": evaluated,
        "failures": failures,
    }


def _mean_optional(items: list[dict[str, Any]], field: str) -> float | None:
    values = [float(item[field]) for item in items if isinstance(item.get(field), (int, float))]
    return sum(values) / len(values) if values else None


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    index = round((len(values) - 1) * percentile / 100)
    return values[index]


def write_extended_evaluation_report(report: dict[str, Any], data_root: Path) -> Path:
    export_dir = data_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    settings = report.get("settings")
    method = settings.get("method") if isinstance(settings, dict) else None
    method_suffix = f"_{method}" if isinstance(method, str) and method else ""
    output_path = export_dir / f"retrieval_eval_extended{method_suffix}_{timestamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return output_path


def _json_default(value: object) -> object:
    if isinstance(value, ExtendedExpectedArticle | ExtendedExpectedChunk):
        return value.__dict__
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def load_evaluation_thresholds(path: Path, method: str) -> dict[str, float]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evaluation thresholds file must contain a mapping")
    method_thresholds = raw.get(method)
    if method_thresholds is None:
        return {}
    if not isinstance(method_thresholds, dict):
        raise ValueError(f"{method} thresholds must be a mapping")
    thresholds: dict[str, float] = {}
    for key, value in method_thresholds.items():
        if not isinstance(key, str) or not isinstance(value, (int, float)):
            raise ValueError(f"{method} threshold values must be numeric")
        thresholds[key] = float(value)
    return thresholds


def check_extended_evaluation_thresholds(report: dict[str, Any], thresholds: dict[str, float]) -> list[dict[str, object]]:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("extended evaluation report must contain summary")
    failures: list[dict[str, object]] = []
    for threshold, expected in thresholds.items():
        if threshold.startswith("min_"):
            metric = threshold.removeprefix("min_")
            actual = summary.get(metric)
            if not isinstance(actual, (int, float)) or float(actual) < expected:
                failures.append({"threshold": threshold, "metric": metric, "expected": expected, "actual": actual})
        elif threshold.startswith("max_"):
            metric = threshold.removeprefix("max_")
            actual = summary.get(metric)
            if not isinstance(actual, (int, float)) or float(actual) > expected:
                failures.append({"threshold": threshold, "metric": metric, "expected": expected, "actual": actual})
        else:
            raise ValueError(f"unsupported threshold name: {threshold}")
    return failures


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
