"""Read-only answer preparation: actual retrieval, explicit diagnostics, no generation."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article
from app.documents.service import build_pdf_url
from app.evaluation.context_compaction import SourcePage, complete_pages_in_request
from app.evaluation.query_packet import MAX_BYTES, aligned_pages
from app.evaluation.query_packet_run import collect_sources
from app.generation.providers import AnswerLanguage, AnswerStyle, Evidence, ProviderResult
from app.generation.query_qualifiers import assess_query_qualifiers
from app.generation.service import answer_question
from app.records.schema import SourceRegion, text_hash
from app.retrieval.search import SearchResponse

VERSION = 'answer_preparation_v0.1'


class _BeforeGeneration(Exception):
    """Explicit local boundary, not a model refusal or transport failure."""


class _NoGenerationProvider:
    def generate(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = 'claims',
                 answer_language: AnswerLanguage = 'auto') -> ProviderResult:
        raise _BeforeGeneration()


def _article_metadata(session: Session, evidence: list[Evidence]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata: dict[str, Any] = {}
    diagnostics = []
    for article_id in sorted({e.article_id for e in evidence}):
        article = session.get(Article, UUID(article_id))
        if article is None:
            raise ValueError(f'Preparation evidence article missing: {article_id}')
        authors: list[str] = []
        fields: list[dict[str, Any]] = []
        unknown = article.authors is None or not article.authors
        for index, author in enumerate(article.authors or []):
            if not isinstance(author, dict):
                unknown = True
                continue
            found = [(key, author[key]) for key in ('name', 'family', 'last_name', 'lastName')
                     if isinstance(author.get(key), str) and author[key].strip()]
            if not found:
                unknown = True
            for key, value in found:
                authors.append(value)
                fields.append({'author_index': index, 'field': key, 'text': value})
        metadata[article_id] = {'authors': None if unknown else authors, 'year': article.year,
            'source_authors': article.authors, 'author_field_mapping': fields, 'title': article.title, 'doi': article.doi,
            'basis': 'Recorded article metadata; not independently validated bibliographic identity.'}
        if unknown or article.year is None:
            diagnostics.append({'article_id': article_id, 'state': 'incomplete_bibliographic_metadata',
                                'authors_unresolved': unknown, 'year_missing': article.year is None})
    return metadata, diagnostics


def prepare_answer(session: Session, settings: Settings, question: str, *, collection: str = 'literature',
                   top_k: int = 5, method: str = 'hybrid_cross_lingual', answer_style: str = 'claims',
                   answer_language: str = 'auto', library_source_id: UUID | None = None) -> dict[str, Any]:
    """Requires a fresh PostgreSQL session; read-only transaction errors propagate.

    This endpoint constructs no external API request and loads no generation
    provider. Passing necessary checks is not scientific or network acceptance.
    """
    session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
    trace: dict[str, Any] = {}

    def observe(retrieval: SearchResponse, evidence: list[Evidence], metadata: dict[str, object]) -> None:
        trace.update(evidence=deepcopy(evidence), metadata=deepcopy(metadata))

    baseline_allowed = True
    with session.no_autoflush:
        try:
            response = answer_question(session, settings, question, collection=collection, top_k=top_k, method=method,
                answer_style=answer_style, answer_language=answer_language, library_source_id=library_source_id,
                provider=_NoGenerationProvider(), trace_observer=observe)
            if response.status != 'insufficient_evidence':
                raise ValueError('Unexpected answer preparation return before generation')
            baseline_allowed = False
        except _BeforeGeneration:
            pass
        if not trace:
            raise ValueError('Answer preparation did not observe the actual evidence selection')
        evidence = trace['evidence']
        sources = collect_sources(session, settings, evidence)
        metadata, metadata_diagnostics = _article_metadata(session, evidence)
    qualifiers = assess_query_qualifiers(question.strip(), evidence, baseline_allowed=baseline_allowed, article_metadata=metadata)
    regions = [SourceRegion.model_validate(r) for r in sources['pages'].values()]
    mappings = {e.chunk_id: aligned_pages(e, [r for r in regions if str(r.article_id) == e.article_id
        and e.page_start <= r.page_number <= e.page_end and r.text_layer == sources['chunk_layers'].get(e.chunk_id)],
        sources['chunk_layers'].get(e.chunk_id)) for e in evidence}
    registry_proven = bool(evidence) and not sources['diagnostics'] and all(mappings.values())
    pages = [SourcePage(str(r.article_id), r.region_id, r.page_number, r.text_layer, str(r.text_layer_id),
                        r.page_text, r.layer_pdf_path, r.layer_pdf_sha256) for r in regions]
    raw_text = '\n'.join(e.text for e in evidence)
    complete_pages = complete_pages_in_request(raw_text, pages)
    bundle = {'question': question.strip(), 'evidence': [asdict(e) for e in evidence]}
    serialized = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    size = len(serialized.encode('utf-8'))
    blockers = []
    if not baseline_allowed:
        blockers.append('baseline_insufficient_evidence')
    if not qualifiers['candidate_allowed']:
        blockers.append('query_qualifier_check_failed')
    if not registry_proven:
        blockers.append('source_registry_unproven')
    if complete_pages:
        blockers.append('complete_source_pages_retained')
    if size > MAX_BYTES:
        blockers.append('evidence_bundle_over_budget')
    # Keep the full local evidence and registry even on failure; no clipping.
    return {'version': VERSION, 'question': question.strip(), 'status': 'blocked' if blockers else 'checks_passed',
        'generation_performed': False, 'external_request_constructed': False, 'network_ready': False,
        'blocking_reasons': blockers, 'baseline_allowed': baseline_allowed, 'baseline_metadata': trace['metadata'],
        'query_qualifiers': qualifiers, 'article_metadata': metadata, 'metadata_diagnostics': metadata_diagnostics,
        'evidence': bundle['evidence'], 'sources': sources,
        'source_links': [{'citation_id': e.citation_id, 'pdf_url': build_pdf_url(e.article_id, 'original', e.page_start),
                         'context_url': (f'/ui/articles/{e.article_id}/chunks/{e.chunk_id}/context?before=1&after=1'
                                         if e.source_type != 'table_derived' else None)} for e in evidence],
        'scope': {'page_registry_proven': registry_proven, 'complete_pages_in_evidence': complete_pages,
                  'evidence_bundle_bytes': size, 'byte_ceiling': MAX_BYTES, 'evidence_bundle_sha256': text_hash(serialized),
                  'basis': 'Raw selected evidence only; no external API request has been built or authorized.'},
        'scientific_admission': 'not_evaluated',
        'limitations': ['necessary_mention_checks_only', 'query_grammar_is_finite', 'metadata_not_independently_validated',
                        'no_measurement_or_relation_entailment', 'no_generation_or_api_request']}
