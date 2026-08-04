from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article
from app.evaluation.retrieval import EvaluationQuestion, load_questions
from app.generation.providers import AnswerProvider
from app.generation.service import AnswerResponse, answer_question, answer_response_to_dict


def _normalize_title(value: str) -> str:
    return " ".join(value.lower().split())


def _citation_checksums(session: Session, response: AnswerResponse) -> dict[str, str]:
    article_ids = [UUID(citation.article_id) for citation in response.citations]
    if not article_ids:
        return {}
    rows = session.execute(select(Article.id, Article.checksum_sha256).where(Article.id.in_(article_ids))).all()
    return {str(article_id): checksum.lower() for article_id, checksum in rows}


def _evaluate_answer(question: EvaluationQuestion, response: AnswerResponse, checksums: dict[str, str]) -> dict[str, Any]:
    citation_dois = {citation.doi.lower() for citation in response.citations if citation.doi}
    citation_titles = {_normalize_title(citation.title) for citation in response.citations if citation.title}
    citation_checksums = {checksum for citation in response.citations if (checksum := checksums.get(citation.article_id))}
    missing_dois = [doi for doi in question.expected_article_dois if doi not in citation_dois]
    missing_titles = [title for title in question.expected_article_titles if title not in citation_titles]
    missing_checksums = [checksum for checksum in question.expected_article_checksums if checksum not in citation_checksums]
    answer_text = (response.answer or "").lower()
    missing_keywords = [keyword for keyword in question.expected_keywords if keyword.lower() not in answer_text]
    known_citation_ids = {citation.citation_id for citation in response.citations}
    claims_with_valid_citations = sum(
        1 for claim in response.claims if claim.citation_ids and set(claim.citation_ids).issubset(known_citation_ids)
    )
    exact_extractive_claims = sum(
        1
        for claim in response.claims
        if any(claim.text == citation.text for citation in response.citations if citation.citation_id in claim.citation_ids)
    )
    passed = (
        response.status == "answered"
        and not missing_dois
        and not missing_titles
        and not missing_checksums
        and not missing_keywords
        and claims_with_valid_citations == len(response.claims)
        and bool(response.claims)
    )
    return {
        "id": question.id,
        "query": question.query,
        "passed": passed,
        "status": response.status,
        "claim_count": len(response.claims),
        "citation_count": len(response.citations),
        "claims_with_valid_citations": claims_with_valid_citations,
        "citation_coverage": claims_with_valid_citations / len(response.claims) if response.claims else 0.0,
        "exact_extractive_claims": exact_extractive_claims,
        "missing_article_dois": missing_dois,
        "missing_article_titles": missing_titles,
        "missing_article_checksums": missing_checksums,
        "missing_keywords": missing_keywords,
        "response": answer_response_to_dict(response),
    }


def run_answer_evaluation(
    session: Session,
    settings: Settings,
    questions_path: Path,
    *,
    collection: str,
    top_k: int,
    method: str,
    provider: AnswerProvider | None = None,
) -> dict[str, Any]:
    evaluated = []
    for question in load_questions(questions_path):
        response = answer_question(
            session,
            settings,
            question.query,
            collection=collection,
            top_k=top_k,
            method=method,
            provider=provider,
        )
        evaluated.append(_evaluate_answer(question, response, _citation_checksums(session, response)))
    failures = [item for item in evaluated if not item["passed"]]
    total_claims = sum(int(item["claim_count"]) for item in evaluated)
    valid_claims = sum(int(item["claims_with_valid_citations"]) for item in evaluated)
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "questions_path": str(questions_path),
        "settings": {
            "collection": collection,
            "top_k": top_k,
            "retrieval_method": method,
            "generation_provider": settings.rag_provider,
            "generation_model": settings.rag_model or None,
        },
        "summary": {
            "total": len(evaluated),
            "passed": len(evaluated) - len(failures),
            "failed": len(failures),
            "answered": sum(1 for item in evaluated if item["status"] == "answered"),
            "refused": sum(1 for item in evaluated if item["status"] == "insufficient_evidence"),
            "claim_count": total_claims,
            "citation_coverage": valid_claims / total_claims if total_claims else 0.0,
            "exact_extractive_claims": sum(int(item["exact_extractive_claims"]) for item in evaluated),
        },
        "questions": evaluated,
        "failures": failures,
    }


def write_answer_evaluation_report(report: dict[str, Any], data_root: Path) -> Path:
    export_dir = data_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = export_dir / f"answer_eval_{timestamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
