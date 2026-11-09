from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.documents.service import build_pdf_url
from app.generation.answer_facts import prepare as prepare_answer_facts
from app.generation.answer_facts import resolve_selections as resolve_fact_selections
from app.generation.answer_fidelity import prepare as prepare_answer_fidelity
from app.generation.answer_fidelity import validate as validate_answer_fidelity
from app.generation.comparison_scope import conductivity_superlative, swelling_transition, transition_constraints
from app.generation.context_completion import complete_context
from app.generation.evidence_adequacy import LIGATURES, assess_evidence_adequacy
from app.generation.evidence_selection import select_answer_evidence
from app.generation.gigachat import GigaChatAnswerProvider
from app.generation.lithiation_overview import allowed_claims
from app.generation.lithiation_overview import prepare as prepare_lithiation_overview
from app.generation.lithiation_overview import validate_claims as validate_lithiation_claims
from app.generation.providers import (
    AnswerLanguage,
    AnswerProvider,
    AnswerStyle,
    Evidence,
    ExtractiveAnswerProvider,
    GeneratedClaim,
    GenerationOutputError,
)
from app.generation.query_assist import query_assistance_to_dict, suggest_query_corrections
from app.generation.reference_quotes import prepare as prepare_reference_quotes
from app.generation.reference_quotes import resolve_selections
from app.generation.reference_quotes import validate_complete as validate_reference_quotes
from app.generation.source_role_assembly import has_markers as has_assembly_markers
from app.generation.source_role_assembly import prepare as prepare_source_assembly
from app.retrieval.cross_lingual import detect_query_language, glossary_terms_for_concepts
from app.retrieval.search import SearchFilters, SearchResponse, SearchResult, make_snippet, search_chunks

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
    if provider == "gigachat":
        return GigaChatAnswerProvider(
            credentials=settings.gigachat_credentials,
            scope=settings.gigachat_scope,
            ca_bundle_file=settings.gigachat_ca_bundle_file,
            model=settings.rag_model,
            timeout_seconds=settings.rag_timeout_seconds,
            max_tokens=settings.rag_gigachat_max_tokens,
        )
    raise ValueError(f"Unsupported RAG provider: {settings.rag_provider}. Supported provider: gigachat")


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
    library_source_id: UUID | str | None = None,
    provider: AnswerProvider | None = None,
    trace_observer: Callable[[SearchResponse, list[Evidence], dict[str, object]], None] | None = None,
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
        filters=SearchFilters.normalize(library_source_id=library_source_id),
        settings=settings,
    )
    evidence_selection = select_answer_evidence(
        normalized_question,
        retrieval.results,
        additional_queries=_cross_lingual_selection_queries(retrieval.metadata),
    )
    context_results, context_metadata = complete_context(
        session, normalized_question, active_collection,
        SearchFilters.normalize(library_source_id=library_source_id), evidence_selection.results,
    )
    selected_retrieval = SearchResponse(query=retrieval.query, results=context_results, metadata=retrieval.metadata)
    evidence = _evidence_from_response(selected_retrieval, use_full_text=True)
    display_evidence = _evidence_from_response(selected_retrieval)
    evidence, display_evidence, derived_metadata = _augment_swelling_comparison_evidence(
        normalized_question,
        evidence,
        display_evidence,
    )
    evidence, display_evidence, deduplication_metadata = _deduplicate_parallel_evidence(evidence, display_evidence)
    raw_fact_sources = evidence
    adequacy_evidence = evidence
    transition_metadata = None
    if swelling_transition(normalized_question):
        evidence, display_evidence, transition_metadata = _bounded_swelling_transition(
            evidence, active_answer_language, normalized_question,
        )
    cross_lingual_concepts = _cross_lingual_matched_concepts(retrieval.metadata)
    adequacy = assess_evidence_adequacy(
        normalized_question,
        adequacy_evidence,
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
        "required_concepts": asdict(adequacy.required_concepts),
        "relation_requirements": adequacy.relation_requirements,
    }
    overview = prepare_lithiation_overview(normalized_question, evidence, answer_language=active_answer_language)
    actual_adequate = adequacy.adequate
    reference_quotes = prepare_reference_quotes(normalized_question, evidence, retrieval.metadata.get("explicit_source_reference"),
                                               answer_language=active_answer_language)
    if reference_quotes is not None:
        actual_adequate = (reference_quotes.eligible and not adequacy.required_concepts.missing
                           and not adequacy.relation_requirements["missing"])
        adequacy_metadata["lexical_baseline"] = deepcopy(adequacy_metadata)
        adequacy_metadata["adequate"] = actual_adequate
        adequacy_metadata["reason"] = reference_quotes.reason
        if actual_adequate:
            evidence, display_evidence = reference_quotes.evidence, reference_quotes.display
    if overview is not None:
        actual_adequate = overview.eligible and not adequacy.required_concepts.missing and not adequacy.relation_requirements["missing"]
        adequacy_metadata["lexical_baseline"] = deepcopy(adequacy_metadata)
        adequacy_metadata["adequate"] = actual_adequate
        adequacy_metadata["reason"] = overview.reason if actual_adequate or not overview.eligible else adequacy.reason
        if actual_adequate:
            evidence = overview.evidence
            display_evidence = overview.evidence
    optimum_scope = conductivity_superlative(normalized_question)
    if optimum_scope is not None:
        actual_adequate = False
        adequacy_metadata["lexical_baseline"] = deepcopy(adequacy_metadata)
        adequacy_metadata["adequate"] = False
        adequacy_metadata["reason"] = optimum_scope["reason"]
    if transition_metadata is not None:
        actual_adequate = (bool(transition_metadata["eligible"]) and not adequacy.required_concepts.missing
                           and not adequacy.relation_requirements["missing"])
        adequacy_metadata["lexical_baseline"] = deepcopy(adequacy_metadata)
        adequacy_metadata["adequate"] = actual_adequate
        adequacy_metadata["reason"] = (transition_metadata["reason"] if actual_adequate or not transition_metadata["eligible"]
                                        else adequacy.reason)
    fidelity = prepare_answer_fidelity(normalized_question, evidence)
    if fidelity is not None and not fidelity.eligible:
        adequacy_metadata["fidelity_baseline"] = deepcopy(adequacy_metadata)
        actual_adequate = False
        adequacy_metadata["adequate"] = False
        adequacy_metadata["reason"] = "answer_fidelity_source_pattern_unresolved"
    facts = prepare_answer_facts(normalized_question, raw_fact_sources, reference_quotes, fidelity,
                                answer_language=active_answer_language)
    facts_provider_supported = not isinstance(provider, ExtractiveAnswerProvider) and (
        provider is not None or settings.rag_provider == "gigachat")
    if (facts_provider_supported and (facts is None or not facts.eligible) and reference_quotes is not None
            and reference_quotes.diagnostics.get("family") == "composition_cycling" and has_assembly_markers(raw_fact_sources)
            and active_answer_language != "en"
            and (active_answer_language == "ru" or re.search(r"[а-яё]", normalized_question, re.I))):
        assembled = prepare_source_assembly(normalized_question, raw_fact_sources,
            retrieval.metadata.get("explicit_source_reference"), {r.chunk_id: r.text_layer for r in context_results},
            answer_language=active_answer_language)
        facts = assembled
        if assembled.eligible:
            actual_adequate = not adequacy.required_concepts.missing and not adequacy.relation_requirements["missing"]
            adequacy_metadata["assembly_baseline"] = deepcopy(adequacy_metadata)
            adequacy_metadata["adequate"] = actual_adequate
            adequacy_metadata["reason"] = assembled.reason if actual_adequate else adequacy.reason
    facts_active = facts is not None and facts.eligible and actual_adequate and facts_provider_supported
    if facts_active and facts is not None:
        evidence, display_evidence = facts.evidence, facts.display
    query_assistance = suggest_query_corrections(normalized_question, adequacy.distinctive_terms, adequacy.matched_terms)
    base_metadata = {
        "retrieval": retrieval.metadata,
        "retrieved_count": len(retrieval.results),
        "answer_evidence_selection": evidence_selection.metadata,
        "answer_evidence_deduplication": deduplication_metadata,
        "evidence_adequacy": adequacy_metadata,
        "answer_style": active_answer_style,
        "answer_language": active_answer_language,
        "citation_language_coverage": _citation_language_coverage(display_evidence),
    }
    if derived_metadata:
        base_metadata["derived_evidence"] = derived_metadata
    if context_metadata is not None:
        base_metadata["condition_context_completion"] = context_metadata
    if overview is not None:
        base_metadata["lithiation_overview"] = overview.metadata()
    if reference_quotes is not None:
        base_metadata["reference_quote_selection"] = reference_quotes.metadata()
    if fidelity is not None:
        base_metadata["answer_fidelity"] = fidelity.metadata()
    if facts is not None:
        base_metadata["source_facts"] = {**facts.metadata(), "active": facts_active,
                                         "provider_selection_supported": facts_provider_supported}
    if optimum_scope is not None:
        base_metadata["conductivity_best_scope"] = optimum_scope
    if transition_metadata is not None:
        base_metadata["swelling_transition"] = transition_metadata
    if query_assistance is not None:
        base_metadata["query_assistance"] = query_assistance_to_dict(query_assistance)
    if trace_observer is not None:
        trace_observer(deepcopy(retrieval), deepcopy(evidence), deepcopy(base_metadata))
    if not actual_adequate:
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
    generation_evidence = display_evidence if isinstance(active_provider, ExtractiveAnswerProvider) else evidence
    generated = active_provider.generate(
        normalized_question,
        generation_evidence,
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
    _validate_claims(generated.claims, generation_evidence)
    if facts_active:
        generated = replace(generated, claims=resolve_fact_selections(generated.claims, generation_evidence))
    if not facts_active:
        validate_answer_fidelity(generated.claims, fidelity)
    if reference_quotes is not None and not facts_active:
        generated = replace(generated, claims=resolve_selections(generated.claims, generation_evidence))
    quote_contract = allowed_claims(generation_evidence)
    validate_lithiation_claims(generated.claims, quote_contract)
    if reference_quotes is not None and not facts_active:
        validate_reference_quotes(generated.claims, reference_quotes)
    if quote_contract and active_answer_style == "mini_review" and reference_quotes is None and not facts_active:
        keys = [_claim_article_key(claim, {item.citation_id: item for item in generation_evidence}) for claim in generated.claims]
        if len(keys) != len(set(keys)):
            raise GenerationOutputError("Bounded mini-review must select at most one statement per work")
    claims = (
        _merge_mini_review_claims_by_article(generated.claims, generation_evidence)
        if active_answer_style == "mini_review" and not quote_contract
        else generated.claims
    )
    _validate_claims(claims, generation_evidence)
    used_ids = {citation_id for claim in claims for citation_id in claim.citation_ids}
    used_evidence = [item for item in display_evidence if item.citation_id in used_ids]
    answer = "\n\n".join(f"{claim.text} {' '.join(f'[{citation_id}]' for citation_id in claim.citation_ids)}" for claim in claims)
    return AnswerResponse(
        query=normalized_question,
        status="answered",
        answer=answer,
        claims=claims,
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
        "citations": [_citation_to_dict(citation) for citation in response.citations],
        "retrieval_method": response.retrieval_method,
        "generation_provider": response.generation_provider,
        "generation_model": response.generation_model,
        "metadata": response.metadata,
    }


def _citation_to_dict(citation: Evidence) -> dict[str, Any]:
    payload = asdict(citation)
    payload["pdf_url"] = build_pdf_url(citation.article_id, "original")
    payload["pdf_page_url"] = build_pdf_url(citation.article_id, "original", citation.page_start)
    payload["context_url"] = (
        f"/articles/{citation.article_id}/chunks/{citation.chunk_id}/context"
        "?before=1&after=1"
    )
    context_params: dict[str, object] = {"before": 1, "after": 1}
    if citation.text.strip():
        context_params["highlight_query"] = citation.text
        context_params["highlight_mode"] = "phrase"
    payload["ui_context_url"] = f"/ui/articles/{citation.article_id}/chunks/{citation.chunk_id}/context?{urlencode(context_params)}"
    return payload


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


def _merge_mini_review_claims_by_article(claims: list[GeneratedClaim], evidence: list[Evidence]) -> list[GeneratedClaim]:
    evidence_by_id = {item.citation_id: item for item in evidence}
    grouped: dict[tuple[str, ...], GeneratedClaim] = {}
    order: list[tuple[str, ...]] = []
    for claim in claims:
        key = _claim_article_key(claim, evidence_by_id)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = claim
            order.append(key)
            continue
        texts = [existing.text]
        if claim.text not in texts:
            texts.append(claim.text)
        citation_ids = list(existing.citation_ids)
        for citation_id in claim.citation_ids:
            if citation_id not in citation_ids:
                citation_ids.append(citation_id)
        grouped[key] = GeneratedClaim(text=" ".join(texts), citation_ids=citation_ids)
    return [grouped[key] for key in order]


def _claim_article_key(claim: GeneratedClaim, evidence_by_id: dict[str, Evidence]) -> tuple[str, ...]:
    article_ids: list[str] = []
    for citation_id in claim.citation_ids:
        evidence = evidence_by_id.get(citation_id)
        if evidence is None:
            continue
        if evidence.article_id not in article_ids:
            article_ids.append(evidence.article_id)
    return tuple(article_ids) if article_ids else tuple(claim.citation_ids)


def _deduplicate_parallel_evidence(
    evidence: list[Evidence],
    display_evidence: list[Evidence],
) -> tuple[list[Evidence], list[Evidence], dict[str, object]]:
    kept_generation: list[Evidence] = []
    kept_display: list[Evidence] = []
    dropped: list[dict[str, object]] = []
    for generation_item, display_item in zip(evidence, display_evidence, strict=False):
        duplicate_of = _find_duplicate_evidence_index(generation_item, kept_generation)
        if duplicate_of is None:
            kept_generation.append(generation_item)
            kept_display.append(display_item)
            continue
        dropped.append(
            {
                "chunk_id": generation_item.chunk_id,
                "duplicate_of_chunk_id": kept_generation[duplicate_of].chunk_id,
                "article_id": generation_item.article_id,
            }
        )
    renumbered_generation = _renumber_evidence(kept_generation)
    renumbered_display = _renumber_evidence(kept_display)
    return renumbered_generation, renumbered_display, {
        "input_count": len(evidence),
        "kept_count": len(renumbered_generation),
        "dropped_count": len(dropped),
        "dropped": dropped,
    }


def _find_duplicate_evidence_index(item: Evidence, kept: list[Evidence]) -> int | None:
    for index, candidate in enumerate(kept):
        if item.chunk_id == candidate.chunk_id:
            return index
        same_article = item.article_id == candidate.article_id
        same_title = item.title is not None and item.title == candidate.title
        if (same_article or same_title) and _text_similarity(item.text, candidate.text) >= 0.82:
            return index
    return None


def _text_similarity(left: str, right: str) -> float:
    left_tokens = _deduplication_tokens(left)
    right_tokens = _deduplication_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return overlap / min(len(left_tokens), len(right_tokens))


def _deduplication_tokens(text: str) -> set[str]:
    normalized = text.lower().translate(LIGATURES)
    return {term for term in re.findall(r"[\w-]+", normalized, flags=re.UNICODE) if len(term.strip("-")) >= 4}


def _augment_swelling_comparison_evidence(
    question: str,
    evidence: list[Evidence],
    display_evidence: list[Evidence],
) -> tuple[list[Evidence], list[Evidence], dict[str, object] | None]:
    if not _has_swelling_comparison_intent(question):
        return evidence, display_evidence, None
    if swelling_transition(question):
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


def _bounded_swelling_transition(
    evidence: list[Evidence], answer_language: str, question: str,
) -> tuple[list[Evidence], list[Evidence], dict[str, object]]:
    import json

    version = "nafion_swelling_transition_v0.1"
    unsupported = transition_constraints(question)
    if unsupported:
        return evidence, evidence, {"version": version, "eligible": False,
                                   "reason": "unsupported_swelling_transition_constraint", "unsupported_terms": unsupported}
    for source in evidence:
        rows = _extract_swelling_comparison_rows(source.text)
        table_heading = re.search(r"(?:таблица|table)\s*4\.5", source.text, re.I)
        if len(rows) != len(_SWELLING_TABLE_ROWS) or table_heading is None:
            continue
        first_row = re.search(r"ацетонитрил\s+\d", source.text[table_heading.end():], re.I)
        if first_row is None:
            continue
        heading = source.text[table_heading.start():table_heading.end() + first_row.start()].casefold()
        heading = re.sub(r"[-‑–]", "-", heading)
        if "h-nafion" not in heading or "li-nafion" not in heading:
            continue
        if not re.search(r"набухани|swelling", heading) or not 0 <= heading.find("αh") < heading.find("αli"):
            continue
        higher = sum(row.alpha_li > row.alpha_h for row in rows)
        lower = sum(row.alpha_li < row.alpha_h for row in rows)
        equal = sum(row.alpha_li == row.alpha_h for row in rows)
        english = answer_language == "en" or (answer_language == "auto" and not re.search(r"[а-яё]", question, re.I))
        if higher and lower:
            conclusion = ("The direction of change depends on solvent; these rows do not support a general increase upon lithiation."
                          if english else "Направление изменения зависит от растворителя; "
                          "общего увеличения при литировании эти строки не показывают.")
        elif equal == len(rows):
            conclusion = "All listed pairs are equal." if english else "Во всех перечисленных парах значения совпадают."
        elif higher:
            conclusion = ("In these rows Li-Nafion is higher or equal." if english else
                          "В перечисленных строках значения Li-Nafion выше или совпадают.")
        else:
            conclusion = ("In these rows Li-Nafion is lower or equal." if english else
                          "В перечисленных строках значения Li-Nafion ниже или совпадают.")
        names = {en: re.sub(r"^n(?:,n)?-", lambda m: m.group().upper(), ru) for ru, en in _SWELLING_TABLE_ROWS}
        lines = [f"{row.solvent if english else names[row.solvent]}: αH={row.alpha_h} → αLi={row.alpha_li}, "
                 f"Δα={row.alpha_li - row.alpha_h:+}" for row in rows]
        if english:
            text = ("System arithmetic from Table 4.5: " + conclusion
                    + f" Li-Nafion is higher in {higher}/9 rows, lower in {lower}/9, equal in {equal}/9. "
                    + "Nine paired equilibrium-swelling values: " + "; ".join(lines) + ". "
                    "This comparison covers the listed solvents, not the complete literature.")
        else:
            text = ("Арифметическое сравнение таблицы 4.5: " + conclusion
                    + f" Для Li-Nafion значения выше в {higher}/9 строк, ниже в {lower}/9, равны в {equal}/9. "
                    + "Девять пар равновесных степеней набухания: " + "; ".join(lines) + ". "
                    "Сравнение относится к перечисленным растворителям, а не ко всей литературе.")
        record = {"allowed_claim": text, "origin": "system_decimal_arithmetic_from_source_table",
                  "rows": [{"solvent": row.solvent, "alpha_h": str(row.alpha_h), "alpha_li": str(row.alpha_li),
                            "delta_alpha": str(row.alpha_li - row.alpha_h)} for row in rows]}
        derived = replace(source, source_type="comparison_derived", text=json.dumps({"version": version, "records": [record]},
                                                                                   ensure_ascii=False))
        return [derived], [derived], {"version": version, "eligible": True, "reason": "complete_supported_table_4_5",
                                     "source_article_id": source.article_id, "source_chunk_id": source.chunk_id,
                                     "records": [record], "units_or_temperature_added": False}
    return evidence, evidence, {"version": version, "eligible": False, "reason": "complete_paired_table_not_found"}


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
