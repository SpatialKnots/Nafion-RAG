"""Reuse the existing TAC metadata rules on registered front pages, retaining proposals."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, ArticleMetadataExtraction, Page
from app.documents.service import PdfStorageIntegrityError, resolve_article_pdf
from app.records.schema import text_hash
from app.records.sources import file_hash, source_region_from_page

# Explicit boundary to the unchanged legacy algorithms and their runtime validator.
tac_experiment = import_module('scripts.tac_experiment')
tac_metadata = import_module('scripts.tac_metadata')

VERSION = 'registered_tac_metadata_v0.1'
FIELDS = ('authors', 'year', 'journal')


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def implementation() -> dict[str, Any]:
    files = {'bibliography_bridge': file_hash(Path(__file__))}
    for name, module in (('tac_metadata', tac_metadata), ('tac_experiment', tac_experiment)):
        if module.__file__ is None:
            raise ValueError('TAC implementation has no inspectable source file')
        files[name] = file_hash(Path(module.__file__))
    return {'bridge': VERSION, 'algorithm': tac_metadata.VERSION, 'pymupdf': fitz.VersionBind,
            'files': files}


def front_sources(session: Session, settings: Settings, article: Article) -> dict[str, Any]:
    """Use physical pages 1–2, never a filename, reference list or new text layer."""
    original = resolve_article_pdf(article, settings).path
    if file_hash(original) != article.checksum_sha256:
        raise PdfStorageIntegrityError('Bibliographic original PDF checksum mismatch')
    pages = list(session.scalars(select(Page).where(Page.article_id == article.id, Page.page_number <= 2).order_by(Page.page_number)))
    regions, empty, diagnostics = [], [], []
    for page in pages:
        if not page.text:
            empty.append({'page': page.page_number, 'selected_text_layer': page.selected_text_layer,
                          'text_sha256': text_hash(page.text or '')})
            diagnostics.append(f'empty_registered_front_page:{page.page_number}')
            continue
        region = source_region_from_page(session, settings, article.id, page.page_number,
            selection_basis='fixed_page', selection_note=VERSION + ': physical front pages 1–2; proposals only.')
        with fitz.open(region.layer_pdf_path) as document:
            if document[region.page_number - 1].get_text('text') != region.page_text:
                raise PdfStorageIntegrityError('Bibliographic registered text differs from selected PDF extraction')
        regions.append(region.model_dump(mode='json'))
    if not pages or pages[0].page_number != 1:
        diagnostics.append('registered_first_page_missing')
    return {'article_id': str(article.id), 'original_pdf_path': str(original), 'original_pdf_sha256': article.checksum_sha256,
            'regions': regions, 'empty_pages': empty, 'diagnostics': diagnostics, 'profile_sections': []}


def extract_registered(sources: dict[str, Any]) -> dict[str, Any]:
    """Call the unchanged legacy extractor and its exact-span validator."""
    pages = [{'page': r['page_number'], 'text': r['page_text'], 'text_sha256': r['page_text_sha256'],
        'layer': r['text_layer'], 'layer_id': r['text_layer_id'], 'layer_pdf_path': r['layer_pdf_path']} for r in sources['regions']]
    article = {'article_id': sources['article_id'], 'original_pdf_sha256': sources['original_pdf_sha256'], 'pages': pages}
    snapshot = {'articles': [article]}
    snapshot_sha = text_hash(canonical(snapshot))
    extracted = tac_metadata.extract_article(article, {'sections': sources['profile_sections']})
    tac_metadata.validate_metadata(snapshot, {'schema': tac_metadata.VERSION, 'snapshot_sha256': snapshot_sha,
                                             'articles': [extracted]}, snapshot_sha)
    return {'version': VERSION, 'implementation': implementation(), 'sources': sources, 'extracted': extracted,
            'scientific_confirmation': False, 'input_sha256': text_hash(canonical(sources))}


def article_values(article: Article) -> dict[str, Any]:
    return {field: deepcopy(getattr(article, field)) for field in FIELDS}


def projection(current: dict[str, Any], extracted: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """Fill empty fields, refresh only values demonstrably managed by this bridge."""
    owned = previous['projection']['managed_values'] if previous else {}
    after, managed, actions = deepcopy(current), {}, {}
    for field in FIELDS:
        prior = current[field]
        if prior is not None and prior != [] and not (field in owned and prior == owned[field]):
            actions[field] = 'existing_value_preserved'
            continue
        value = deepcopy(extracted[field]) if extracted['fields'][field]['status'] == 'proposed' else None
        if field == 'authors' and value:
            value = [{'name': name, 'source': tac_metadata.VERSION} for name in value]
        after[field] = value
        managed[field] = value
        actions[field] = 'unchanged' if value == prior else 'filled_empty' if prior in (None, []) else 'refreshed_automatic_value'
    return {'previous_values': current, 'after_values': after, 'managed_values': managed, 'actions': actions,
            'basis': 'Algorithm proposals, not independent bibliographic confirmation.'}


def latest(session: Session, article_id: Any) -> ArticleMetadataExtraction | None:
    row = session.scalar(select(ArticleMetadataExtraction).where(ArticleMetadataExtraction.article_id == article_id)
        .order_by(ArticleMetadataExtraction.sequence_no.desc()).limit(1))
    if row is not None and text_hash(canonical(row.payload)) != row.payload_sha256:
        raise PdfStorageIntegrityError('Stored bibliographic payload checksum mismatch')
    return row


def preview(session: Session, settings: Settings, article: Article) -> dict[str, Any]:
    result = extract_registered(front_sources(session, settings, article))
    previous = latest(session, article.id)
    result['projection'] = projection(article_values(article), result['extracted'], previous.payload if previous else None)
    return result


def refresh(session: Session, settings: Settings, article: Article) -> ArticleMetadataExtraction:
    """Caller owns commit/rollback; row lock serializes same-article projections."""
    session.refresh(article, with_for_update=True)
    result = preview(session, settings, article)
    previous = latest(session, article.id)
    code_sha = text_hash(canonical(result['implementation']))
    if (previous and previous.input_sha256 == result['input_sha256'] and previous.code_sha256 == code_sha
            and previous.payload['projection']['managed_values'] == result['projection']['managed_values']
            and article_values(article) == result['projection']['after_values']):
        return previous
    for field, value in result['projection']['after_values'].items():
        setattr(article, field, deepcopy(value))
    row = ArticleMetadataExtraction(id=uuid4(), article_id=article.id, input_sha256=result['input_sha256'],
        code_sha256=code_sha, payload=result, payload_sha256=text_hash(canonical(result)))
    session.add(row)
    session.flush()
    return row


def recorded(session: Session, settings: Settings, article: Article) -> dict[str, Any]:
    row = latest(session, article.id)
    if row is None:
        return {'version': VERSION, 'state': 'not_extracted', 'article_id': str(article.id), 'current_values': article_values(article)}
    if text_hash(canonical(row.payload)) != row.payload_sha256:
        raise PdfStorageIntegrityError('Stored bibliographic payload checksum mismatch')
    current = front_sources(session, settings, article)
    if canonical(current) != canonical(row.payload['sources']):
        raise PdfStorageIntegrityError('Stored bibliographic evidence differs from current registered front pages; refresh required')
    return {'version': VERSION, 'state': 'proposed_not_confirmed', 'extraction_id': str(row.id),
        'article_id': str(article.id), 'payload': row.payload, 'current_values': article_values(article),
        'field_matches_projection': {f: f in row.payload['projection']['managed_values']
            and getattr(article, f) == row.payload['projection']['managed_values'][f] for f in FIELDS},
        'source_valid': True, 'scientific_confirmation': False}
