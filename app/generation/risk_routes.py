"""Explicit preparation UI/API for diagnostic risks; no inference admission changes."""

from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse

from app.documents.service import DocumentAccessError, build_pdf_url
from app.evaluation.context_risks import audit_context_risks
from app.generation.block_routes import block_api, render_blocks
from app.generation.preparation_routes import PreparationRequest, SessionDep, _form, prepare_page
from app.ui import _layout

VERSION = 'answer_preparation_risks_v0.1'
router = APIRouter()
RELATIONS = {
    'intersects_selected_or_protected_geometry': 'Пересекает выбранные блоки или защищённое окружение',
    'outside_selected_geometry_relevance_unknown': 'Вне выбранной геометрии; значимость неизвестна',
    'unknown_geometry': 'Геометрия не подтверждена',
    'intersects_selected_text': 'Признак риска внутри выбранного текста',
    'outside_selected_text_extent_unknown': 'Признак вне текста; смысловые границы неизвестны',
}


@router.post('/answer/prepare/blocks/risks')
def risk_api(session: SessionDep, request: PreparationRequest) -> dict[str, Any]:
    preparation = block_api(session, request)
    try:
        audit = audit_context_risks(preparation)
    except DocumentAccessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'version': VERSION, 'preparation': preparation, 'audit': audit,
            'generation_performed': False, 'external_request_constructed': False, 'network_ready': False}


def render_risks(payload: dict[str, Any], *, local_pdf_links: bool = False) -> str:
    """Display every page/window, including empty and deferred states, without repair."""
    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + escape(label) + '</summary><pre>' + escape(raw) + '</pre></details>'

    def counts(relations: list[dict[str, Any]]) -> str:
        return '<br>'.join(escape(RELATIONS.get(k, k)) + ': ' + str(n)
                          for k, n in sorted(Counter(r['relation'] for r in relations).items())) or 'Нет записей'

    audit = payload['audit']
    titles = {e['article_id']: e['title'] for e in payload['preparation']['baseline']['evidence']}
    pages = []
    for page in audit['pages']:
        source = page['source']
        link = (Path(source['original_pdf_path']).resolve().as_uri() + '#page=' + str(source['page_number'])
                if local_pdf_links else build_pdf_url(source['article_id'], 'original', source['page_number']))
        rows = []
        for w in page['windows']:
            flags = []
            if w['complete_page_coverage']:
                flags.append('Окно покрывает полную страницу')
            if w['exceeds_existing_character_ceiling']:
                flags.append('Превышен существующий предел символов; текст сохранён')
            rows.append('<tr data-risk-window><td>' + escape(str(w['block_numbers'])) + '<br>'
                + str(w['start']) + ':' + str(w['end']) + '</td><td>' + counts(w['asset_relations'])
                + '</td><td>' + counts(w['trigger_relations']) + '</td><td>' + escape('; '.join(flags))
                + detail('Полный текст окружения', w['quote']) + detail('Точная привязка и все отношения', w) + '</td></tr>')
        empty = ('<p>Окружение не построено: точная геометрия блоков не подтверждена.</p>' if page['mapping_unproven']
                 else '<p>Нет удерживаемого окружения с поддерживаемым уточнением запроса. Страница сохранена в исходной подготовке.</p>')
        pages.append('<section data-risk-page><h3>' + escape(titles.get(source['article_id']) or 'Название неизвестно')
            + ' · <a href="' + escape(link, quote=True) + '">Оригинальный PDF, страница ' + str(source['page_number'])
            + '</a></h3><p>' + ('Совокупность диагностических окон покрывает полную страницу. Отправка отключена.'
                if page['diagnostic_windows_assemble_complete_page'] else
                'Полное покрытие страницы этими окнами не обнаружено; допуск не меняется.')
            + '</p>' + detail('Прежняя и нелокализованная диагностика', {'parent_diagnostics': page['parent_diagnostics'],
                'unlocalized_page_diagnostics': page['unlocalized_page_diagnostics']})
            + detail('Точный источник, графика и признаки риска', {k: v for k, v in page.items() if k != 'windows'})
            + ('<div style="overflow-x:auto"><table><thead><tr><th>Блоки и offsets</th><th>Графика</th>'
               '<th>Текстовые признаки</th><th>Окружение</th></tr></thead><tbody>' + ''.join(rows)
               + '</tbody></table></div>' if rows else empty)
            + '</section>')
    return ('<section class="panel risk-result" data-risk-result><h2>Риски выбранного окружения</h2>'
        '<p>Генерация отключена. Выбор источников и прежние запреты сохранены. Диагностические окна не являются пакетом для модели.</p>'
        '<p>Удалённая графика не признана несущественной. Место текстового признака не устанавливает его смысловые границы.</p>'
        '<p>Страниц-вхождений: ' + str(len(audit['pages'])) + '; диагностических окон: '
        + str(sum(len(p['windows']) for p in audit['pages'])) + '. Повторения между источниками сохранены.</p>'
        '<label>Поиск по аудиту <input type="search" data-risk-search></label><p data-risk-search-status aria-live="polite"></p>'
        + ''.join(pages) + '<details><summary>Исходная подготовка и все прежние запреты</summary>'
        + render_blocks(payload['preparation'], metadata_links=not local_pdf_links) + '</details>'
        + detail('Версии и связь с исходной подготовкой', {'version': payload['version'], 'audit_version': audit['version'],
            'parent_sha256': audit['parent_sha256'], 'selection_changed': audit['selection_changed'],
            'admission_changed': audit['admission_changed'], 'scientific_exclusion_proven': audit['scientific_exclusion_proven']})
        + '<script>(()=>{const root=document.currentScript.parentElement;const input=root.querySelector("[data-risk-search]");'
        'input.addEventListener("input",()=>{const q=input.value.toLocaleLowerCase();let shown=0;'
        'for(const page of root.querySelectorAll("[data-risk-page]")){page.hidden=!page.textContent.toLocaleLowerCase().includes(q);'
        'if(!page.hidden)shown++;for(const row of page.querySelectorAll("[data-risk-window]"))'
        'row.hidden=!row.textContent.toLocaleLowerCase().includes(q)}'
        'root.querySelector("[data-risk-search-status]").textContent="Страниц-вхождений показано: "+shown})})();</script></section>')


def _risk_form(content: str) -> str:
    return content.replace('action="/ui/answer/prepare"', 'action="/ui/answer/prepare/blocks/risks"', 1).replace(
        '<h1>Подготовка ответа</h1>', '<h1>Риски контекста перед анализом</h1>', 1)


@router.get('/ui/answer/prepare/blocks/risks', response_class=HTMLResponse)
def risk_page(question: str = '', library_source_id: UUID | None = None,
              ariadne_library_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    page = prepare_page(question, library_source_id, ariadne_library_id)
    return HTMLResponse(_risk_form(bytes(page.body).decode('utf-8')))


@router.post('/ui/answer/prepare/blocks/risks', response_class=HTMLResponse)
def risk_action(session: SessionDep, question: Annotated[str, Form()], collection: Annotated[str, Form()] = 'literature',
                top_k: Annotated[int, Form(ge=1)] = 5,
                method: Annotated[Literal['exact', 'semantic', 'hybrid', 'hybrid_cross_lingual'], Form()] = 'hybrid_cross_lingual',
                library_source_id: Annotated[UUID | None, Form()] = None) -> HTMLResponse:
    try:
        payload = risk_api(session, PreparationRequest(question=question, collection=collection, top_k=top_k,
                           method=method, library_source_id=library_source_id))
        result = render_risks(payload)
        status = 200
    except HTTPException as exc:
        result = '<p class="warn">' + escape(str(exc.detail)) + '</p>'
        status = exc.status_code
    page = _layout('Риски контекста', _risk_form(_form(question, library_source_id, result,
        collection=collection, top_k=top_k, method=method)))
    page.status_code = status
    return page
