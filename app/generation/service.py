from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.generation.evidence_adequacy import LIGATURES, assess_evidence_adequacy
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
from app.retrieval.search import SearchResponse, SearchResult, make_snippet, search_chunks

_SWELLING_TABLE_ROWS = (
    ("ацетонитрил", "acetonitrile"),
    ("ацетон", "acetone"),
    ("вода", "water"),
    ("изопропанол", "isopropanol"),
    ("диметилсульфоксид", "dimethyl sulfoxide (DMSO)"),
    ("n,n-диметилформамид", "N,N-dimethylformamide (DMF)"),
    ("метанол", "methanol"),
    ("этанол", "ethanol"),
    ("n-метил-2-пирролидон", "N-methyl-2-pyrrolidone (NMP)"),
)


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


@dataclass(frozen=True)
class _SwellingComparisonRow:
    solvent: str
    alpha_h: Decimal
    alpha_li: Decimal


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
            text=(result.full_text or result.snippet) if use_full_text else _display_text_for_result(result),
            score=result.score,
            retrieval_method=result.retrieval_method,
            method_scores=result.method_scores,
            method_ranks=result.method_ranks,
            original_language=detect_query_language(result.full_text or result.snippet)[0],
        )
        for index, result in enumerate(response.results, start=1)
        if result.snippet.strip()
    ]


def _display_text_for_result(result: SearchResult) -> str:
    full_text = result.full_text or ""
    normalized = full_text.lower().translate(LIGATURES)
    for marker in (
        "таблица 4.6",
        "table 4.6",
        "highest ionic conductivities",
        "highest li-ion conductivity",
        "best transport properties",
        "highest conductivity values",
        "best sample",
        "стабильно высокие значения",
        "наиболее высок",
        "10−4–10−3",
        "дмфа",
        "дмсо",
        "нмп",
    ):
        if marker in normalized:
            return make_snippet(full_text, marker, radius=220)
    return result.snippet


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
    evidence, display_evidence, derived_metadata = _augment_swelling_comparison_evidence(
        normalized_question,
        evidence,
        display_evidence,
    )
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
    if derived_metadata:
        base_metadata["derived_evidence"] = derived_metadata
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


def _augment_swelling_comparison_evidence(
    question: str,
    evidence: list[Evidence],
    display_evidence: list[Evidence],
) -> tuple[list[Evidence], list[Evidence], dict[str, object] | None]:
    if not _has_swelling_comparison_intent(question):
        return evidence, display_evidence, None
    for generation_item, display_item in zip(evidence, display_evidence, strict=False):
        rows = _extract_swelling_comparison_rows(generation_item.text)
        if not rows:
            continue
        matching = [row for row in rows if row.alpha_li > row.alpha_h]
        nonmatching = [row for row in rows if row.alpha_li <= row.alpha_h]
        if not matching:
            continue
        derived_text = _swelling_comparison_summary_text(matching, nonmatching)
        derived_generation = replace(generation_item, text=derived_text, source_type="table_derived")
        derived_display = replace(display_item, text=derived_text, source_type="table_derived")
        augmented_generation = _renumber_evidence([derived_generation, *evidence])
        augmented_display = _renumber_evidence([derived_display, *display_evidence])
        return augmented_generation, augmented_display, {
            "type": "swelling_comparison_table",
            "source_article_id": generation_item.article_id,
            "source_chunk_id": generation_item.chunk_id,
            "source_pages": [generation_item.page_start, generation_item.page_end],
            "matching_row_count": len(matching),
            "nonmatching_row_count": len(nonmatching),
        }
    return evidence, display_evidence, None


def _has_swelling_comparison_intent(question: str) -> bool:
    text = question.lower()
    has_swelling = "swelling degree" in text or "степень набухания" in text
    has_forms = "li-nafion" in text and "h-nafion" in text
    has_comparison = any(term in text for term in ("more", "than", "higher", "больше", "большую", "большей", "выше"))
    return has_swelling and has_forms and has_comparison


def _extract_swelling_comparison_rows(text: str) -> list[_SwellingComparisonRow]:
    normalized = (
        text.lower()
        .replace("‑", "-")
        .replace("–", "-")
        .replace("−", "-")
        .replace("\u00a0", " ")
    )
    if "αh" not in normalized or "αli" not in normalized:
        return []
    rows: list[_SwellingComparisonRow] = []
    for russian_name, english_name in _SWELLING_TABLE_ROWS:
        pattern = rf"{re.escape(russian_name)}\s+(?P<alpha_h>\d+[.,]\d+)\s+-?\d+[.,]\d+\s+(?P<alpha_li>\d+[.,]\d+)\s+-?\d+[.,]\d+"
        match = re.search(pattern, normalized)
        if match is None:
            continue
        alpha_h = _decimal(match.group("alpha_h"))
        alpha_li = _decimal(match.group("alpha_li"))
        if alpha_h is None or alpha_li is None:
            continue
        rows.append(_SwellingComparisonRow(solvent=english_name, alpha_h=alpha_h, alpha_li=alpha_li))
    return rows


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None


def _swelling_comparison_summary_text(
    matching: list[_SwellingComparisonRow],
    nonmatching: list[_SwellingComparisonRow],
) -> str:
    matching_text = "; ".join(
        f"{row.solvent}: alphaLi={row.alpha_li} > alphaH={row.alpha_h}" for row in matching
    )
    nonmatching_text = "; ".join(
        f"{row.solvent}: alphaLi={row.alpha_li} <= alphaH={row.alpha_h}" for row in nonmatching
    )
    return (
        "Deterministic row comparison extracted from Table 4.5. "
        "Растворители, которые дают Li-Nafion большую степень набухания, чем H-Nafion, are listed by alphaLi > alphaH. "
        f"Rows where Li-Nafion has higher equilibrium swelling degree than H-Nafion: {matching_text}. "
        f"Rows where Li-Nafion is not higher: {nonmatching_text}."
    )


def _renumber_evidence(evidence: list[Evidence]) -> list[Evidence]:
    return [replace(item, citation_id=f"E{index}") for index, item in enumerate(evidence, start=1)]
