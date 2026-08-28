from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, cast

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.evidence_selection import select_answer_evidence
from app.generation.providers import (
    AnswerLanguage,
    AnswerProvider,
    AnswerStyle,
    DeepSeekAnswerProvider,
    Evidence,
    ExtractiveAnswerProvider,
    GeneratedClaim,
    GenerationOutputError,
    OllamaAnswerProvider,
    OpenAIAnswerProvider,
)
from app.generation.query_assist import query_assistance_to_dict, suggest_query_corrections
from app.retrieval.cross_lingual import detect_query_language, glossary_terms_for_concepts
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


def normalize_answer_style(answer_style: str) -> AnswerStyle:
    normalized = answer_style.strip().lower()
    if normalized in {"claims", "mini_review"}:
        return cast(AnswerStyle, normalized)
    raise ValueError("answer_style must be one of: claims, mini_review")


def normalize_answer_language(answer_language: str) -> AnswerLanguage:
    normalized = answer_language.strip().lower()
    if normalized in {"auto", "en", "ru"}:
        return cast(AnswerLanguage, normalized)
    raise ValueError("answer_language must be one of: auto, en, ru")


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


def _evidence_from_response(response: SearchResponse, *, use_full_text: bool = False) -> list[Evidence]:
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
            text=(result.full_text or result.snippet) if use_full_text else result.snippet,
            score=result.score,
            retrieval_method=result.retrieval_method,
            method_scores=result.method_scores,
            method_ranks=result.method_ranks,
            original_language=detect_query_language(result.full_text or result.snippet)[0],
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
    answer_style: str = "claims",
    answer_language: str = "auto",
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
    active_answer_style = normalize_answer_style(answer_style)
    active_answer_language = normalize_answer_language(answer_language)
    retrieval = search_chunks(
        session,
        normalized_question,
        active_collection,
        active_top_k,
        method=active_method,
        settings=settings,
    )
    evidence_selection = select_answer_evidence(
        normalized_question,
        retrieval.results,
        additional_queries=_cross_lingual_selection_queries(retrieval.metadata),
    )
    selected_retrieval = SearchResponse(query=retrieval.query, results=evidence_selection.results, metadata=retrieval.metadata)
    evidence = _evidence_from_response(selected_retrieval, use_full_text=True)
    display_evidence = _evidence_from_response(selected_retrieval)
    cross_lingual_concepts = _cross_lingual_matched_concepts(retrieval.metadata)
    adequacy = assess_evidence_adequacy(
        normalized_question,
        evidence,
        concept_terms=glossary_terms_for_concepts(cross_lingual_concepts),
    )
    adequacy_metadata = {
        "adequate": adequacy.adequate,
        "reason": adequacy.reason,
        "distinctive_terms": adequacy.distinctive_terms,
        "matched_terms": adequacy.matched_terms,
        "top_matched_terms": adequacy.top_matched_terms,
        "coverage": adequacy.coverage,
        "top_coverage": adequacy.top_coverage,
        "concept_coverage": adequacy.concept_coverage,
    }
    query_assistance = suggest_query_corrections(normalized_question, adequacy.distinctive_terms, adequacy.matched_terms)
    base_metadata = {
        "retrieval": retrieval.metadata,
        "retrieved_count": len(retrieval.results),
        "answer_evidence_selection": evidence_selection.metadata,
        "evidence_adequacy": adequacy_metadata,
        "answer_style": active_answer_style,
        "answer_language": active_answer_language,
        "citation_language_coverage": _citation_language_coverage(display_evidence),
    }
    if query_assistance is not None:
        base_metadata["query_assistance"] = query_assistance_to_dict(query_assistance)
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
            metadata=base_metadata,
        )
    active_provider = provider or build_answer_provider(settings)
    generated = active_provider.generate(
        normalized_question,
        evidence,
        answer_style=active_answer_style,
        answer_language=active_answer_language,
    )
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
            metadata=base_metadata,
        )
    _validate_claims(generated.claims, evidence)
    used_ids = {citation_id for claim in generated.claims for citation_id in claim.citation_ids}
    used_evidence = [item for item in display_evidence if item.citation_id in used_ids]
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
        metadata=base_metadata,
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


def _cross_lingual_selection_queries(metadata: dict[str, object]) -> list[str]:
    cross_lingual = metadata.get("cross_lingual")
    if not isinstance(cross_lingual, dict):
        return []
    variants = cross_lingual.get("variants")
    if not isinstance(variants, list):
        return []
    queries = []
    for variant in variants:
        if not isinstance(variant, dict) or variant.get("source") == "original":
            continue
        text = variant.get("text")
        if isinstance(text, str) and text.strip():
            queries.append(text)
    return queries


def _cross_lingual_matched_concepts(metadata: dict[str, object]) -> list[str]:
    cross_lingual = metadata.get("cross_lingual")
    if not isinstance(cross_lingual, dict):
        return []
    concepts = cross_lingual.get("matched_concepts")
    if isinstance(concepts, list):
        return [str(concept) for concept in concepts if isinstance(concept, str)]
    glossary = cross_lingual.get("glossary")
    if isinstance(glossary, dict):
        nested = glossary.get("matched_concepts")
        if isinstance(nested, list):
            return [str(concept) for concept in nested if isinstance(concept, str)]
    return []


def _citation_language_coverage(evidence: list[Evidence]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence:
        language = item.original_language or "unknown"
        counts[language] = counts.get(language, 0) + 1
    return counts
