"""Explicit experimental generation route/UI; normal answer endpoint is unchanged."""

from __future__ import annotations

import json
from html import escape
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.documents.service import DocumentAccessError
from app.generation import service
from app.generation.preparation_routes import PreparationRequest, SessionDep
from app.generation.providers import AnswerProvider, GenerationOutputError, GenerationUnavailableError
from app.generation.required_answer_fields import RequirementGuidedAnswerProvider
from app.generation.required_fields_guard import RequiredFieldsGuardProvider
from app.retrieval.vector_index import VectorIndexUnavailableError
from app.ui import _layout, _prepared_statement_text

router = APIRouter()


class GuardRequest(PreparationRequest):
    question: str = Field(min_length=1, max_length=4000)


def make_provider(settings: Settings) -> AnswerProvider:
    if settings.rag_provider != 'gigachat':
        raise ValueError('Experimental required-fields delivery supports the configured GigaChat provider only')
    return RequirementGuidedAnswerProvider(credentials=settings.gigachat_credentials, scope=settings.gigachat_scope,
        model=settings.rag_model, max_tokens=settings.rag_gigachat_max_tokens, timeout_seconds=settings.rag_timeout_seconds,
        ca_bundle_file=settings.gigachat_ca_bundle_file)


@router.post('/answer/experimental/required-fields')
def guarded_answer(session: SessionDep, request: GuardRequest,
                   settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, Any]:
    reviews: list[dict[str, Any]] = []
    try:
        provider = RequiredFieldsGuardProvider(make_provider(settings), on_review=reviews.append)
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        result = service.answer_question(session, settings, **request.model_dump(), provider=provider)
    except GenerationUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GenerationOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except VectorIndexUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DocumentAccessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.rollback()
    reviewed = reviews[0] if reviews else None
    return {'version': 'required_fields_experimental_answer_v0.1', 'answer': service.answer_response_to_dict(result),
        'delivery_status': reviewed['decision'] if reviewed else 'baseline_preprovider_refusal',
        'review': reviewed, 'default_changed': False, 'server_persistence': False}


LABELS = {'insufficient_confirmation': 'Недостаточно подтверждений', 'provider_abstained': 'Модель отказалась от ответа',
    'not_evaluated': 'Этот тип вопроса не проверен картой обязательных полей',
    'required_literal_fields_present': 'Необходимые поля найдены; научная корректность не установлена',
    'baseline_preprovider_refusal': 'Исходная проверка источников не допустила генерацию'}


def render(payload: dict[str, Any]) -> str:
    status = LABELS[payload['delivery_status']]
    body = '<section><h2>' + escape(status) + '</h2>'
    answer = payload['answer']['answer']
    if answer is not None:
        body += '<pre>' + escape(answer) + '</pre>'
        records = payload['answer'].get('metadata', {}).get('source_facts', {}).get('records', [])
        if any(isinstance(r.get('source_grammar'), dict) and isinstance(r['source_grammar'].get('glyph_decoding'), dict)
               for r in records if isinstance(r, dict)):
            prepared = _prepared_statement_text(json.dumps({'records': records}, ensure_ascii=False), 'source_fact_derived')
            body += ('<details><summary>Расшифровка символов PDF и исходные цитаты</summary><pre>'
                     + escape(prepared) + '</pre></details>')
    reviewed = payload['review']
    if reviewed is not None:
        body += '<p>Это конечная проверка полей; нераспознанная формулировка не считается научной ошибкой.</p>'
        body += '<details><summary>Причины и неустановленные связи</summary><pre>' + escape(json.dumps(
            reviewed['reasons'], ensure_ascii=False, indent=2)) + '</pre></details>'
        body += '<details><summary>Исходный ответ модели — отдельно от решения о выдаче'
        body += ' (не допущен)' if reviewed['withheld'] else ' (не является научной приёмкой)'
        body += '</summary><pre>' + escape(json.dumps(reviewed['native_result'], ensure_ascii=False, indent=2)) + '</pre></details>'
        body += '<details><summary>Карта и исходные доказательства</summary><pre>' + escape(json.dumps(
            reviewed['check'], ensure_ascii=False, indent=2)) + '</pre></details>'
    return body + '</section>'


def form(result: str = '', question: str = '') -> str:
    return ('<h1>Эксперимент: ответ с проверкой обязательных полей</h1><p>Нажатие кнопки запускает один запрос '
        'к модели при допуске исходной проверкой источников. Автоматических повторов нет. Основной режим не изменён.</p>'
        '<form method="post" action="/ui/answer/experimental/required-fields"><label>Вопрос<textarea name="question" '
        'required maxlength="4000">' + escape(question) + '</textarea></label>'
        '<button type="submit">Получить экспериментальный ответ</button></form>' + result)


@router.get('/ui/answer/experimental/required-fields', response_class=HTMLResponse)
def page() -> HTMLResponse:
    return _layout('Экспериментальная проверка ответа', form())


@router.post('/ui/answer/experimental/required-fields', response_class=HTMLResponse)
def action(session: SessionDep, question: Annotated[str, Form(min_length=1, max_length=4000)],
           settings: Annotated[Settings, Depends(get_settings)]) -> HTMLResponse:
    try:
        payload = guarded_answer(session, GuardRequest(question=question), settings)
    except HTTPException as exc:
        return HTMLResponse(form('<p>' + escape(str(exc.detail)) + '</p>', question), status_code=exc.status_code)
    return _layout('Экспериментальная проверка ответа', form(render(payload), question))
