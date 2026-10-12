from __future__ import annotations

import json
import secrets
from collections import Counter
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlencode
from uuid import UUID

import fitz  # type: ignore[import-untyped]
from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article, Chunk, PageTextLayer
from app.db.session import get_session
from app.facts.review_store import (
    ReviewConflict,
    code_hashes,
    decision_history,
    latest_decisions,
    load_snapshot,
    save_decision,
    sha,
)
from app.ui import _html, _layout

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]
STATUS = {'unreviewed': 'Без решения', 'acceptable': 'Допустимо', 'blocker': 'Ошибка', 'ambiguous': 'Неоднозначно'}
CUES = {'scale_bar_cue': 'Масштабная линейка', 'approximation_cue': 'Приблизительность',
        'inequality_cue': 'Граница', 'isolated_numeric_line': 'Роль не определена'}
DECISIONS = {'accepted': 'Выбрано', 'rejected': 'Отклонено', 'duplicate': 'Лексический дубликат',
             'cap_omitted': 'Пропущено лимитом', 'not_recognized': 'Нет точного совпадения в текущем распознавателе'}


def review_root() -> Path:
    return get_settings().data_root / 'reviews' / 'numeric'


def snapshot_or_error(snapshot: str | None) -> tuple[str, dict[str, Any]]:
    try:
        return load_snapshot(review_root(), snapshot)
    except FileNotFoundError as exc:
        raise HTTPException(404, 'Снимок проверки ещё не создан') from exc
    except (ValueError, ReviewConflict) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/ui/numeric-review', response_class=HTMLResponse)
def review_page(
    snapshot: str | None = None, item: str | None = None, status: str = 'unreviewed', q: str = '',
    cue: str = '', direction: str = '', offset: int = Query(0, ge=0), pdf_page: int | None = Query(None, ge=1),
    saved: bool = False, review_csrf: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    try:
        sid, data = snapshot_or_error(snapshot)
    except HTTPException as exc:
        if exc.status_code != 404 or snapshot is not None:
            raise
        return _layout('Проверка фактов', '<h1>Проверка численных фактов</h1><p>Снимок проверки ещё не создан.</p>')
    latest = latest_decisions(review_root(), sid)
    counts = Counter(latest.get(r['id'], {}).get('verdict', 'unreviewed') for r in data['records'])
    stale = data['code_hashes'] != code_hashes()
    filtered = [r for r in data['records'] if
                (not status or latest.get(r['id'], {}).get('verdict', 'unreviewed') == status)
                and (not q or q.casefold() in str(data['sources'][r['chunk_id']]['title']).casefold())
                and (not direction or r['direction'] == direction)
                and (not cue or any(c['kind'] == cue for o in r['occurrences'] for c in o['context_cues']))]
    selected = next((r for r in data['records'] if r['id'] == item), None) if item else None
    if item and selected is None:
        raise HTTPException(404, 'Изменение не найдено')
    if selected is None and filtered:
        selected = filtered[min(offset, len(filtered) - 1)]
    token = review_csrf or secrets.token_urlsafe(32)

    def url(**extra: object) -> str:
        return '/ui/numeric-review?' + urlencode(dict(snapshot=sid, status=status, q=q, cue=cue,
                                                       direction=direction, offset=offset) | extra)

    def options(values: dict[str, str], chosen: str, all_label: str) -> str:
        return ''.join(f'<option value="{_html(k)}" {"selected" if k == chosen else ""}>{_html(v)}</option>'
                       for k, v in ({'': all_label} | values).items())

    body = '<h1>Проверка численных фактов</h1><p>Решения сохраняются отдельно. Факты в базе не обновляются.</p>'
    body += '<p>' + ' · '.join(f'{_html(label)}: <strong>{counts[key]}</strong>' for key, label in STATUS.items()) + '</p>'
    body += f'<p><small>Снимок {_html(sid[:12])} · {_html(data["created_at"])} · '
    body += f'<a href="/ui/numeric-review/export?snapshot={sid}">Экспорт решений и истории</a></small></p>'
    prior_count = sum(bool(r['historical_annotations']) for r in data['records'])
    if prior_count:
        body += f'<p>Для {prior_count} изменений доступна прежняя разметка. Решения нового снимка учитываются отдельно.</p>'
    if stale:
        body += '<p role="alert"><strong>Версия извлечения изменилась. Снимок доступен для чтения; сохранение заблокировано.</strong></p>'
    if saved:
        body += '<p role="status"><strong>Решение сохранено. Предыдущие версии остаются в истории.</strong></p>'
    body += f'''<form method="get" class="review-filters"><input type="hidden" name="snapshot" value="{sid}">
      <label>Статья<input name="q" value="{_html(q)}" placeholder="Название статьи"></label>
      <label>Статус<select name="status">{options(STATUS, status, 'Все статусы')}</select></label>
      <label>Признак<select name="cue">{options(CUES, cue, 'Все признаки')}</select></label>
      <label>Изменение<select name="direction">
      {options({'added': 'Добавлено', 'removed': 'Удалено'}, direction, 'Все изменения')}</select></label>
      <button type="submit">Показать</button></form>
      <p>Найдено: {len(filtered)}. Порядок: статья → страница.</p><div class="review-grid"><section>'''
    for row in filtered[offset:offset + 20]:
        source = data['sources'][row['chunk_id']]
        active = ' aria-current="true"' if selected and row['id'] == selected['id'] else ''
        body += f'''<a class="review-card"{active} href="{_html(url(item=row['id']))}">
        <strong>{_html(row['candidate']['field_value_text'])}</strong> — {'добавлено' if row['direction'] == 'added' else 'удалено'}<br>
        {_html(source['title'])} · стр. {source['page_start']}–{source['page_end']}<br>
        <small>{STATUS[latest.get(row['id'], {}).get('verdict', 'unreviewed')]}</small></a>'''
    if offset:
        body += f'<a href="{_html(url(offset=max(0, offset-20)))}">← Предыдущие</a> '
    if offset + 20 < len(filtered):
        body += f'<a href="{_html(url(offset=offset+20))}">Следующие →</a>'
    body += '</section><section>'
    if selected:
        source = data['sources'][selected['chunk_id']]
        value = selected['candidate']['field_value_text']
        decision = latest.get(selected['id'], {})
        page = pdf_page or decision.get('page') or source['page_start']
        if not source['page_start'] <= page <= source['page_end']:
            raise HTTPException(400, 'Страница вне диапазона чанка')
        pdf_url = f'/articles/{source["article_id"]}/pdf?layer=original#page={page}'
        image_url = '/ui/numeric-review/page-image?' + urlencode(dict(snapshot=sid, item=selected['id'], page=page))
        body += f'<h2>{_html(value)} · {_html(source["title"])}</h2>'
        body += f'<p>{_html(selected["candidate"]["field_name"])} · слой {_html(source["text_layer"])} · '
        body += f'тип {_html(source["source_type"])}</p>'
        body += f'<p><a target="_blank" rel="noopener" href="{_html(pdf_url)}">Открыть оригинальный PDF, стр. {page}</a></p>'
        body += f'''<form method="get"><input type="hidden" name="snapshot" value="{sid}">
        <input type="hidden" name="item" value="{selected['id']}"><input type="hidden" name="status" value="{_html(status)}">
        <label>Страница PDF <input type="number" name="pdf_page" value="{page}" min="{source['page_start']}"
        max="{source['page_end']}"></label><button>Открыть страницу</button></form>
        <div class="review-pdf"><a href="{_html(image_url)}" target="_blank" rel="noopener">
        <img src="{_html(image_url)}" alt="Страница {page} оригинального PDF" style="width:100%;display:block"></a></div>'''
        if source['page_start'] != source['page_end']:
            body += ('<p>Чанк содержит несколько страниц. Укажите проверенную страницу; '
                     'точная страница вхождения не определена автоматически.</p>')
        body += '<h3>Вхождения в исходном тексте</h3>'
        for occurrence in selected['occurrences']:
            a, b = occurrence['start'], occurrence['end']
            context = (_html(source['text'][occurrence['context_start']:a]) + '<mark>' +
                       _html(source['text'][a:b]) + '</mark>' + _html(source['text'][b:occurrence['context_end']]))
            flags = ', '.join(CUES[c['kind']] + ': ' + c['text'] for c in occurrence['context_cues']) or 'Явных признаков нет'
            body += f'<details open><summary>Позиция {a}: {DECISIONS[occurrence["decision"]]}</summary>'
            body += f'<p>{_html(flags)}</p><pre>{context}</pre><small>Причина: {_html(occurrence["reason"])}</small></details>'
        body += ('<p><small>Позиции относятся к тексту чанка. Дубликат означает совпадение записи числа, '
                 'а не тождество экспериментов.</small></p>')
        for prior in selected['historical_annotations']:
            body += f'<details><summary>Предыдущая разметка — не решение текущего снимка</summary><p>{_html(prior["verdict"])}: '
            body += f'{_html(prior["rationale"])}</p></details>'
        if not stale:
            reviewed_page = decision.get('page', source['page_start'] if source['page_start'] == source['page_end'] else '')
            verdict_options = options({k: v for k, v in STATUS.items() if k != 'unreviewed'},
                                      decision.get('verdict', ''), 'Выберите решение')
            choices = ''.join(f'<option value="{o["start"]}" '
                              f'{"selected" if o["start"] == decision.get("occurrence_start") else ""}>'
                              f'{o["start"]}: {DECISIONS[o["decision"]]}</option>' for o in selected['occurrences'])
            body += f'''<h3>Решение по изменению</h3><form method="post" action="/ui/numeric-review/decision">
            <input type="hidden" name="snapshot" value="{sid}"><input type="hidden" name="item" value="{selected['id']}">
            <input type="hidden" name="csrf" value="{_html(token)}">
            <input type="hidden" name="revision" value="{decision.get('revision', 0)}">
            <label>Проверенное вхождение<select name="occurrence_start" required>{choices}</select></label>
            <label>Проверенная страница PDF<input name="page" type="number" min="{source['page_start']}"
            max="{source['page_end']}" value="{reviewed_page}" required></label>
            <label>Результат<select name="verdict" required>{verdict_options}</select></label>
            <label>Кто проверил<input name="reviewer" maxlength="100" value="{_html(decision.get('reviewer', ''))}" required></label>
            <label>Комментарий: смысл числа, единицы, материал, условия
            <textarea name="comment" maxlength="5000" required>{_html(decision.get('comment', ''))}</textarea></label>
            <button type="submit">Сохранить решение</button></form>'''
        history = [r for r in decision_history(review_root(), sid) if r['item'] == selected['id']]
        if history:
            body += '<h3>История решений</h3>'
            for event in reversed(history):
                body += f'<p>#{event["revision"]} · {_html(event["reviewer"])} · {_html(event["created_at"])}<br>'
                body += f'{STATUS[event["verdict"]]} · стр. {event["page"]}<br>{_html(event["comment"])}</p>'
    else:
        body += '<p>Изменений с такими фильтрами нет.</p>'
    body += '</section></div><style>.review-grid{display:grid;grid-template-columns:280px minmax(0,1fr);gap:24px}'
    body += '.review-card{display:block;padding:12px;margin-bottom:8px;border:1px solid #ccd6d8;border-radius:8px;text-decoration:none}'
    body += '.review-card[aria-current]{background:#dff4f1;border-color:#137c75}'
    body += '.review-pdf{width:100%;height:600px;overflow:auto;border:1px solid #ccd6d8;background:white}'
    body += '.review-grid>section:first-child{max-height:1100px;overflow:auto}'
    body += '.review-filters{display:flex;gap:12px;flex-wrap:wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
    body += 'label{display:block;margin:8px 0}textarea{display:block;width:100%;min-height:100px}'
    body += '@media(max-width:900px){.review-grid{grid-template-columns:1fr}.review-pdf{height:450px}}</style>'
    response = _layout('Проверка фактов', body)
    response.set_cookie('review_csrf', token, httponly=True, samesite='strict', path='/ui/numeric-review')
    return response


@router.get('/ui/numeric-review/page-image')
def page_image(session: SessionDep, snapshot: str, item: str, page: int = Query(ge=1)) -> Response:
    _, data = snapshot_or_error(snapshot)
    record = next((r for r in data['records'] if r['id'] == item), None)
    if record is None:
        raise HTTPException(404, 'Изменение не найдено')
    source = data['sources'][record['chunk_id']]
    if not source['page_start'] <= page <= source['page_end']:
        raise HTTPException(400, 'Страница вне диапазона чанка')
    article = session.get(Article, UUID(source['article_id']))
    if article is None or article.checksum_sha256 != source['pdf_sha256']:
        raise HTTPException(409, 'Источник изменился')
    try:
        raw = Path(article.pdf_original_path).read_bytes()
    except FileNotFoundError as exc:
        raise HTTPException(409, 'Оригинальный PDF отсутствует') from exc
    if sha(raw) != source['pdf_sha256']:
        raise HTTPException(409, 'Оригинальный PDF изменился')
    try:
        with fitz.open(stream=raw, filetype='pdf') as document:
            if page > len(document):
                raise HTTPException(400, 'Страница отсутствует в PDF')
            pdf_page = document[page - 1]
            scale = 1600 / max(pdf_page.rect.width, pdf_page.rect.height)
            png = pdf_page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes('png')
    except fitz.FileDataError as exc:
        raise HTTPException(422, 'PDF не удалось прочитать') from exc
    return Response(png, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'})


@router.post('/ui/numeric-review/decision')
def record_decision(
    session: SessionDep, snapshot: Annotated[str, Form()], item: Annotated[str, Form()],
    csrf: Annotated[str, Form()], revision: Annotated[int, Form(ge=0)],
    verdict: Annotated[str, Form()], comment: Annotated[str, Form(min_length=1, max_length=5000)],
    reviewer: Annotated[str, Form(min_length=1, max_length=100)], page: Annotated[int, Form(ge=1)],
    occurrence_start: Annotated[int, Form(ge=0)], review_csrf: Annotated[str | None, Cookie()] = None,
) -> RedirectResponse:
    if not review_csrf or not secrets.compare_digest(csrf, review_csrf):
        raise HTTPException(403, 'Откройте страницу проверки заново')
    sid, data = snapshot_or_error(snapshot)
    if data['code_hashes'] != code_hashes():
        raise HTTPException(409, 'Версия извлечения изменилась; требуется новый снимок')
    record = next((r for r in data['records'] if r['id'] == item), None)
    if record is None:
        raise HTTPException(404, 'Изменение не найдено')
    source = data['sources'][record['chunk_id']]
    chunk = session.get(Chunk, UUID(record['chunk_id']))
    article = session.get(Article, UUID(source['article_id']))
    if (chunk is None or article is None or sha(chunk.text.encode()) != source['chunk_sha256']
            or str(chunk.article_id) != source['article_id'] or chunk.text_layer != source['text_layer']
            or chunk.source_type != source['source_type']
            or chunk.page_start != source['page_start'] or chunk.page_end != source['page_end']
            or article.checksum_sha256 != source['pdf_sha256']):
        raise HTTPException(409, 'Источник изменился; требуется новый снимок')
    try:
        pdf_hash = sha(Path(article.pdf_original_path).read_bytes())
    except FileNotFoundError as exc:
        raise HTTPException(409, 'Оригинальный PDF отсутствует') from exc
    if pdf_hash != source['pdf_sha256']:
        raise HTTPException(409, 'Оригинальный PDF изменился')
    occurrence = next((o for o in record['occurrences'] if o['start'] == occurrence_start), None)
    if occurrence is None or not source['page_start'] <= page <= source['page_end']:
        raise HTTPException(400, 'Неверное вхождение или страница')
    layer = session.scalar(select(PageTextLayer).where(PageTextLayer.article_id == article.id,
                           PageTextLayer.page_number == page, PageTextLayer.layer_type == source['text_layer']))
    left = chunk.text.rfind('\n', 0, occurrence_start) + 1
    right = chunk.text.find('\n', occurrence['end'])
    line = chunk.text[left:len(chunk.text) if right < 0 else right].rstrip('\r')
    if (layer is None or sha(layer.text.encode()) != source['page_hashes'].get(str(page)) or line not in layer.text):
        raise HTTPException(409, 'Выбранная страница не содержит исходную строку вхождения')
    try:
        save_decision(review_root(), snapshot_id=sid, item_id=item, expected_revision=revision,
                      verdict=verdict, comment=comment, reviewer=reviewer, page=page, occurrence_start=occurrence_start)
    except ReviewConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse('/ui/numeric-review?' + urlencode(dict(snapshot=sid, item=item, status='', saved='true')), status_code=303)


@router.get('/ui/numeric-review/export')
def export_decisions(snapshot: str) -> Response:
    sid, data = snapshot_or_error(snapshot)
    history = decision_history(review_root(), sid)
    payload = dict(schema_version=1, snapshot_id=sid, diff_sha256=data['diff_sha256'], applied=False,
                   code_is_current=data['code_hashes'] == code_hashes(), history=history)
    return Response(json.dumps(payload, ensure_ascii=False, indent=2), media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="numeric-review-{sid[:12]}.json"'})
