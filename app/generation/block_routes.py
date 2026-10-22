"""Explicit block-context preparation; never an endpoint for generation or client PDF paths."""

from __future__ import annotations

import json
from html import escape
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse

from app.documents.service import DocumentAccessError, build_pdf_url
from app.generation.block_context import build_block_context
from app.generation.preparation_routes import REASONS, PreparationRequest, SessionDep, _form, prepare_api, prepare_page
from app.ui import _layout

router = APIRouter()
BLOCK_REASONS = {**REASONS,
    'no_supported_block_context': 'Подходящий контекст из целых блоков не установлен.',
    'no_supported_query_anchor': 'Уточнения вопроса не входят в поддерживаемый каталог поиска блоков.',
    'unresolved_source_pages': 'Часть исходных страниц имеет неразрешённую структуру или нетекстовые данные.',
    'deferred_block_contexts': 'Некоторые контексты оставлены отложенными: границы или объём не прошли проверку.',
    'complete_source_page_or_assembled_coverage': 'Выбранные окна по отдельности или вместе раскрывают полную страницу.',
    'candidate_query_qualifier_check_failed': 'Уточнения вопроса не подтверждены в новом контексте.',
    'candidate_over_byte_budget': 'Новый контекст превышает установленный предел объёма.'}


@router.post('/answer/prepare/blocks')
def block_api(session: SessionDep, request: PreparationRequest) -> dict[str, Any]:
    baseline = prepare_api(session, request)
    try:
        return build_block_context(baseline)
    except DocumentAccessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def render_blocks(payload: dict[str, Any], *, metadata_links: bool = True) -> str:
    reasons = ''.join('<li>' + escape(BLOCK_REASONS.get(r, r)) + '</li>' for r in payload['blocking_reasons'])
    contexts = []
    for proposal, item in zip(payload['proposals'], payload['wire']['evidence'], strict=True):
        source = proposal['source']
        metadata_link = (' · <a href="/ui/articles/' + escape(source['article_id'], quote=True)
                         + '/bibliography">Происхождение авторов/года</a>') if metadata_links else ''
        contexts.append('<details><summary>' + escape(item['citation_id']) + ' · страница '
            + str(source['page_number']) + '</summary><p><a href="'
            + escape(build_pdf_url(source['article_id'], 'original', source['page_number']), quote=True)
            + '">Оригинальный PDF</a>' + metadata_link + '. Полные PDF-блоки; смысловые связи не подтверждены.</p><pre>'
            + escape(item['text']) + '</pre></details>')
    return ('<section class="panel" id="block-result"><h2>Контекст из исходных блоков</h2>'
        '<p>Генерация отключена. Полный исходный контекст сохранён в диагностике; невыбранные блоки не объявляются несущественными.</p>'
        + ('<ul>' + reasons + '</ul>' if reasons else '<p>Необходимые технические проверки пройдены. Отправка модели отключена.</p>')
        + ''.join(contexts) + '<details><summary>Исходный контекст, отложенные блоки и полная диагностика</summary><pre>'
        + escape(json.dumps(payload, ensure_ascii=False, indent=2)) + '</pre></details></section>')


def _block_form(question: str = '', library_source_id: UUID | None = None, result: str = '', *,
                collection: str = 'literature', top_k: int = 5, method: str = 'hybrid_cross_lingual') -> str:
    return _form(question, library_source_id, result, collection=collection, top_k=top_k, method=method).replace(
        'action="/ui/answer/prepare"', 'action="/ui/answer/prepare/blocks"', 1).replace(
        '<h1>Подготовка ответа</h1>', '<h1>Контекст из исходных PDF-блоков</h1>', 1)


@router.get('/ui/answer/prepare/blocks', response_class=HTMLResponse)
def block_page(question: str = '', library_source_id: UUID | None = None,
               ariadne_library_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    # Preserve the existing cookie validation and escaped form verbatim.
    page = prepare_page(question, library_source_id, ariadne_library_id)
    return HTMLResponse(bytes(page.body).decode('utf-8').replace('action="/ui/answer/prepare"',
                        'action="/ui/answer/prepare/blocks"', 1).replace('<h1>Подготовка ответа</h1>',
                        '<h1>Контекст из исходных PDF-блоков</h1>', 1))


@router.post('/ui/answer/prepare/blocks', response_class=HTMLResponse)
def block_action(session: SessionDep, question: Annotated[str, Form()], collection: Annotated[str, Form()] = 'literature',
                 top_k: Annotated[int, Form(ge=1)] = 5,
                 method: Annotated[Literal['exact', 'semantic', 'hybrid', 'hybrid_cross_lingual'], Form()] = 'hybrid_cross_lingual',
                 library_source_id: Annotated[UUID | None, Form()] = None) -> HTMLResponse:
    try:
        payload = block_api(session, PreparationRequest(question=question, collection=collection, top_k=top_k,
                            method=method, library_source_id=library_source_id))
        result = render_blocks(payload)
    except HTTPException as exc:
        return HTMLResponse(_block_form(question, library_source_id, '<p class="warn">' + escape(str(exc.detail)) + '</p>',
                            collection=collection, top_k=top_k, method=method), status_code=exc.status_code)
    return _layout('Подготовка блоков', _block_form(question, library_source_id, result,
                                                  collection=collection, top_k=top_k, method=method))
