from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.providers import (
    AnswerProvider,
    DeepSeekAnswerProvider,
    Evidence,
    ExtractiveAnswerProvider,
    GeneratedClaim,
    GenerationOutputError,
    OllamaAnswerProvider,
    OpenAIAnswerProvider,
)
from app.retrieval.search import SearchResponse, search_chunks


@dataclass(frozen=True)
class AnswerResponse:
    query: str
    status: str
    answer: str | None
    claims: list[GeneratedClaim]
    citations: list[Evidence]
    retrieval_method: str
    generation_provider: str
    generation_model: str | None
    metadata: dict[str, object]


def build_answer_provider(settings: Settings) -> AnswerProvider:
    provider = settings.rag_provider.strip().lower()
    if provider == "extractive":
        return ExtractiveAnswerProvider(settings.rag_max_claims)
    if provider == "ollama":
        return OllamaAnswerProvider(
            base_url=settings.rag_ollama_url,
            model=settings.rag_model,
            timeout_seconds=settings.rag_timeout_seconds,
        )
    if provider == "openai":
        return OpenAIAnswerProvider(
            base_url=settings.rag_openai_base_url,
            api_key=settings.rag_openai_api_key,
            model=settings.rag_model or settings.rag_openai_model,
            timeout_seconds=settings.rag_timeout_seconds,
            max_tokens=settings.rag_openai_max_tokens,
        )
    if provider == "deepseek":
        return DeepSeekAnswerProvider(
            base_url=settings.rag_deepseek_url,
            api_key=settings.rag_deepseek_api_key,
            model=settings.rag_model or settings.rag_deepseek_model,
            timeout_seconds=settings.rag_timeout_seconds,
            max_tokens=settings.rag_deepseek_max_tokens,
        )
    raise ValueError(f"Unsupported RAG provider: {settings.rag_provider}. Supported providers: extractive, ollama, openai, deepseek")


def _evidence_from_response(response: SearchResponse) -> list[Evidence]:
    return [
        Evidence(
            citation_id=f"E{index}",
            article_id=result.article_id,
            chunk_id=result.chunk_id,
            title=result.title,
            doi=result.doi,
            page_start=result.page_start,
            page_end=result.page_end,
            source_type=result.source_type,
            text=result.snippet,
            score=result.score,
            retrieval_method=result.retrieval_method,
            method_scores=result.method_scores,
            method_ranks=result.method_ranks,
        )
        for index, result in enumerate(response.results, start=1)
        if result.snippet.strip()
    ]


def _validate_claims(claims: list[GeneratedClaim], evidence: list[Evidence]) -> None:
    if not claims:
        raise GenerationOutputError("answerable output must contain at least one claim")
    known_ids = {item.citation_id for item in evidence}
    for claim in claims:
        if not claim.text.strip():
            raise GenerationOutputError("generated claim text must not be empty")
        if not claim.citation_ids:
            raise GenerationOutputError("every generated claim must contain at least one citation")
        unknown_ids = set(claim.citation_ids) - known_ids
        if unknown_ids:
            raise GenerationOutputError(f"generated claim contains unknown citations: {sorted(unknown_ids)}")


def answer_question(
    session: Session,
    settings: Settings,
    question: str,
    *,
    collection: str | None = None,
    top_k: int | None = None,
    method: str | None = None,
    provider: AnswerProvider | None = None,
) -> AnswerResponse:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")
    active_collection = collection or settings.default_collection
    active_top_k = settings.rag_top_k if top_k is None else top_k
    if active_top_k <= 0:
        raise ValueError("top_k must be positive")
    active_method = method or settings.rag_retrieval_method
    retrieval = search_chunks(
        session,
        normalized_question,
        active_collection,
        active_top_k,
        method=active_method,
        settings=settings,
    )
    evidence = _evidence_from_response(retrieval)
    adequacy = assess_evidence_adequacy(normalized_question, evidence)
    adequacy_metadata = {
        "adequate": adequacy.adequate,
        "reason": adequacy.reason,
        "distinctive_terms": adequacy.distinctive_terms,
        "matched_terms": adequacy.matched_terms,
        "top_matched_terms": adequacy.top_matched_terms,
        "coverage": adequacy.coverage,
        "top_coverage": adequacy.top_coverage,
    }
    if not adequacy.adequate:
        return AnswerResponse(
            query=normalized_question,
            status="insufficient_evidence",
            answer=None,
            claims=[],
            citations=[],
            retrieval_method=active_method,
            generation_provider=settings.rag_provider,
            generation_model=settings.rag_model or None,
            metadata={"retrieval": retrieval.metadata, "retrieved_count": len(retrieval.results), "evidence_adequacy": adequacy_metadata},
        )
    active_provider = provider or build_answer_provider(settings)
    generated = active_provider.generate(normalized_question, evidence)
    if not evidence or not generated.answerable:
        return AnswerResponse(
            query=normalized_question,
            status="insufficient_evidence",
            answer=None,
            claims=[],
            citations=[],
            retrieval_method=active_method,
            generation_provider=generated.provider,
            generation_model=generated.model,
            metadata={"retrieval": retrieval.metadata, "retrieved_count": len(retrieval.results), "evidence_adequacy": adequacy_metadata},
        )
    _validate_claims(generated.claims, evidence)
    used_ids = {citation_id for claim in generated.claims for citation_id in claim.citation_ids}
    used_evidence = [item for item in evidence if item.citation_id in used_ids]
    answer = "\n\n".join(f"{claim.text} {' '.join(f'[{citation_id}]' for citation_id in claim.citation_ids)}" for claim in generated.claims)
    return AnswerResponse(
        query=normalized_question,
        status="answered",
        answer=answer,
        claims=generated.claims,
        citations=used_evidence,
        retrieval_method=active_method,
        generation_provider=generated.provider,
        generation_model=generated.model,
        metadata={"retrieval": retrieval.metadata, "retrieved_count": len(retrieval.results), "evidence_adequacy": adequacy_metadata},
    )


def answer_response_to_dict(response: AnswerResponse) -> dict[str, Any]:
    return {
        "query": response.query,
        "status": response.status,
        "answer": response.answer,
        "claims": [asdict(claim) for claim in response.claims],
        "citations": [asdict(citation) for citation in response.citations],
        "retrieval_method": response.retrieval_method,
        "generation_provider": response.generation_provider,
        "generation_model": response.generation_model,
        "metadata": response.metadata,
    }
