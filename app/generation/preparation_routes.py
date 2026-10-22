"""Separate API/UI for read-only answer preparation; existing answer routes unchanged."""

from __future__ import annotations

import json
from html import escape
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.documents.service import DocumentAccessError
from app.generation.preparation import prepare_answer
from app.retrieval.vector_index import VectorIndexUnavailableError
from app.ui import _layout

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


class PreparationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1)
    collection: str = 'literature'
    top_k: int = Field(default=5, ge=1)
    method: Literal['exact', 'semantic', 'hybrid', 'hybrid_cross_lingual'] = 'hybrid_cross_lingual'
    answer_style: Literal['claims', 'mini_review'] = 'claims'
    answer_language: Literal['auto', 'en', 'ru'] = 'auto'
    library_source_id: UUID | None = None


@router.post('/answer/prepare')
def prepare_api(session: SessionDep, request: PreparationRequest) -> dict[str, Any]:
    try:
        return prepare_answer(session, get_settings(), **request.model_dump())
    except VectorIndexUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DocumentAccessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


REASONS = {
    'baseline_insufficient_evidence': 'Исходная проверка: недостаточно доказательств.',
    'query_qualifier_check_failed': 'Обязательные уточнения запроса не подтверждены в одной статье.',
    'source_registry_unproven': 'Точная привязка выбранных фрагментов к страницам не установлена.',
    'complete_source_pages_retained': 'Контекст содержит полные страницы источника.',
    'evidence_bundle_over_budget': 'Объём выбранных доказательств превышает установленный предел.',
}
STATES = {'mentioned': 'Упоминание найдено', 'not_found': 'В выбранном контексте не найдено',
          'unknown_metadata': 'Метаданные неизвестны'}


def render_preparation(payload: dict[str, Any]) -> str:
    reasons = ''.join('<li>' + escape(REASONS.get(r, r)) + '</li>' for r in payload['blocking_reasons'])
    qualifier_rows = []
    for article in payload['query_qualifiers']['articles']:
        for check in article['checks']:
            qualifier_rows.append('<tr><td>' + escape(article['article_id']) + '</td><td>'
                + escape(check['qualifier']['text']) + '</td><td>' + escape(STATES.get(check['state'], check['state'])) + '</td></tr>')
    evidence = []
    links = {r['citation_id']: r for r in payload['source_links']}
    for item in payload['evidence']:
        link = links[item['citation_id']]
        context = (' · <a href="' + escape(link['context_url'], quote=True) + '">Контекст</a>') if link['context_url'] else ''
        evidence.append('<details><summary>' + escape(item['citation_id'] + ' · ' + (item['title'] or 'Без названия'))
            + '</summary><p><a href="' + escape(link['pdf_url'], quote=True) + '">Оригинальный PDF</a> · <a href="/ui/articles/'
            + escape(item['article_id'], quote=True) + '/bibliography">Происхождение авторов/года</a>'
            + context + '</p><pre>' + escape(item['text']) + '</pre></details>')
    return ('<section class="panel" id="preparation-result"><h2>Проверка контекста</h2>'
        '<p>Генерация отключена. Запрос к внешней модели не создан. Наличие упоминаний не подтверждает научный вывод.</p>'
        + ('<ul>' + reasons + '</ul>' if reasons else '<p>Необходимые проверки пройдены; научная корректность не оценена.</p>')
        + '<table><tr><th>Статья</th><th>Уточнение</th><th>Состояние</th></tr>' + ''.join(qualifier_rows) + '</table>'
        + ''.join(evidence) + '<details><summary>Полная диагностика и источники</summary><pre>'
        + escape(json.dumps(payload, ensure_ascii=False, indent=2)) + '</pre></details></section>')


def _form(question: str = '', library_source_id: UUID | None = None, result: str = '', *,
          collection: str = 'literature', top_k: int = 5, method: str = 'hybrid_cross_lingual') -> str:
    risk_url = '/ui/answer/prepare/blocks/risks'
    if library_source_id is not None:
        risk_url += '?library_source_id=' + str(library_source_id)
    options = ''.join('<option' + (' selected' if method == m else '') + '>' + m + '</option>'
                      for m in ('hybrid_cross_lingual', 'hybrid', 'semantic', 'exact'))
    return ('<h1>Подготовка ответа</h1><p>Поиск источников и проверка обязательных уточнений без генерации ответа.</p>'
        '<p><a href="/ui/answer/prepare/blocks">Контекст из исходных PDF-блоков</a></p>'
        '<p><a href="' + escape(risk_url, quote=True) + '">Риски выбранного окружения</a></p>'
        '<form method="post" action="/ui/answer/prepare"><label>Вопрос<br><textarea name="question" required>'
        + escape(question) + '</textarea></label><input type="hidden" name="library_source_id" value="'
        + escape(str(library_source_id or ''), quote=True) + '"><p><label>Коллекция <input name="collection" value="'
        + escape(collection, quote=True) + '"></label><label>Top K <input type="number" name="top_k" value="'
        + str(top_k) + '" min="1"></label><label>Поиск <select name="method">' + options + '</select></label></p>'
        '<button type="submit">Проверить источники без генерации</button></form>' + result)


@router.get('/ui/answer/prepare', response_class=HTMLResponse)
def prepare_page(question: str = '', library_source_id: UUID | None = None,
                 ariadne_library_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    if library_source_id is None and ariadne_library_id:
        try:
            library_source_id = UUID(ariadne_library_id)
        except ValueError:
            pass  # Malformed preference cookie is not source evidence or a preparation result.
    return _layout('Подготовка ответа', _form(question, library_source_id))


@router.post('/ui/answer/prepare', response_class=HTMLResponse)
def prepare_action(session: SessionDep, question: Annotated[str, Form()], collection: Annotated[str, Form()] = 'literature',
                   top_k: Annotated[int, Form(ge=1)] = 5,
                   method: Annotated[Literal['exact', 'semantic', 'hybrid', 'hybrid_cross_lingual'], Form()] = 'hybrid_cross_lingual',
                   library_source_id: Annotated[UUID | None, Form()] = None) -> HTMLResponse:
    request = PreparationRequest(question=question, collection=collection, top_k=top_k, method=method,
                                 library_source_id=library_source_id)
    try:
        result = render_preparation(prepare_api(session, request))
    except HTTPException as exc:
        return HTMLResponse(_form(question, library_source_id, '<p class="warn">' + escape(str(exc.detail)) + '</p>',
                            collection=collection, top_k=top_k, method=method), status_code=exc.status_code)
    return _layout('Подготовка ответа', _form(question, library_source_id, result, collection=collection, top_k=top_k, method=method))
