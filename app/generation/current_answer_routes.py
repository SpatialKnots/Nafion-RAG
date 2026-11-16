"""Explicit current pipeline API/UI, with shared source and diagnostic rendering."""

from __future__ import annotations

from html import escape
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Form, Request
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy import text

from app.core.config import get_settings
from app.generation.current_answer import diagnostic_json, run
from app.generation.preparation_routes import PreparationRequest, SessionDep
from app.ui import _answer_body, _answer_payload_panel, _cookie_uuid, _layout

router = APIRouter()


class CurrentRequest(PreparationRequest):
    question: str = Field(min_length=1, max_length=4000)
    method: Literal["hybrid_cross_lingual"] = "hybrid_cross_lingual"
    answer_language: Literal["auto", "en", "ru"] = "ru"


def execute(session: Any, options: CurrentRequest) -> tuple[int, dict[str, Any], dict[str, Any]]:
    try:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        return run(session, get_settings(), options.model_dump())
    finally:
        session.rollback()


@router.post("/answer/current")
def api(session: SessionDep, options: CurrentRequest) -> Any:
    from fastapi.responses import JSONResponse

    code, payload, _ = execute(session, options)
    return JSONResponse(payload, status_code=code)


def form(question: str = "", collection: str = "literature", top_k: int = 5, answer_style: str = "claims",
         answer_language: str = "ru", library_source_id: UUID | None = None, result: str = "") -> str:
    body = _answer_body(question, collection, top_k, "hybrid_cross_lingual", answer_style,
                        answer_language, result, library_source_id)
    body = body.replace('action="/ui/answer"', 'action="/ui/answer/current"').replace(
        'data-async-result="/ui/answer/result"', 'data-async-result="/ui/answer/current/result"')
    # Only this versioned profile is offered here; the baseline page keeps all methods.
    start = body.index('<label>Method<br>')
    end = body.index('</label>', start) + len('</label>')
    body = body[:start] + '<input type="hidden" name="method" value="hybrid_cross_lingual">' + body[end:]
    return ('<section class="panel"><strong>Текущий путь ответа · 16 ноября 2026</strong>'
        '<p>Вопрос → rewriting → поиск источников → ответ GigaChat → проверка обязательных полей.</p>'
        '<p>Отправка запускает до двух запросов к модели: один для rewriting, один для ответа. '
        'Повторов нет. Вопрос для ответа сохраняется в исходном виде. Rewriting проверяется автоматически; '
        'ручная проверка смысла из испытаний здесь не выполняется. Научная корректность не установлена.</p>'
        '<p>Для вопроса по одной работе укажите автора и год, например: «По статье Author (2020): …».</p>'
        '<p><a href="/ui/answer">Исходный режим без экспериментального rewriting</a></p></section>' + body)


@router.get("/ui/answer/current", response_class=HTMLResponse)
def page(question: str = "", collection: str = "literature", library_source_id: UUID | None = None,
         ariadne_library_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    return _layout("Current answer", form(question=question, collection=collection,
                   library_source_id=library_source_id or _cookie_uuid(ariadne_library_id)))


def result_panel(payload: dict[str, Any], sources: dict[str, Any]) -> str:
    body = '<section class="panel"><h2>Ход обработки вопроса</h2>'
    plan = payload["rewriting"]["plan"]
    if plan is not None:
        body += '<p><strong>Поисковая формулировка:</strong> ' + escape(plan["english_question"]) + '</p>'
        if plan["keywords"]:
            body += '<p><strong>Поисковые фразы:</strong> ' + escape('; '.join(plan["keywords"])) + '</p>'
    body += '<p><strong>Состояние:</strong> ' + escape(payload["status"]) + '</p>'
    if payload.get("error"):
        body += '<p class="warn" data-result-status="error">' + escape(payload["error"]) + '</p>'
    if payload["delivery_status"] == "insufficient_confirmation":
        body += '<p class="warn">Выдача удержана проверкой обязательных полей; это не установленная научная ошибка.</p>'
    body += '</section>'
    if payload["answer"] is not None:
        body += _answer_payload_panel(payload["answer"], payload["question"], sources)
    # Refusals still expose the selected source context without presenting it as
    # a delivered answer. Values/wording remain exact strings from this request.
    if payload.get("preparation") and payload["status"] != "answered":
        body += '<section class="panel"><details><summary>Выбранные фрагменты источников</summary>'
        from app.documents.service import build_pdf_url

        for item in payload["preparation"]["evidence"]:
            url = build_pdf_url(item["article_id"], "original", item["page_start"])
            label = str(item["title"] or "Название неизвестно") + f' · PDF {item["page_start"]}–{item["page_end"]}'
            body += ('<p><a href="' + escape(url, quote=True) + '">' + escape(label) + '</a></p><pre>'
                     + escape(item["text"]) + '</pre>')
        body += '</details></section>'
    body += ('<section class="panel"><details><summary>Диагностика: rewriting, источники, исходный ответ и проверка</summary>'
             '<p>Исходный результат модели показан отдельно от решения о выдаче. Наличие цитаты и прохождение '
             'конечных проверок не устанавливают научную корректность.</p><pre>'
             + escape(diagnostic_json(payload)) + '</pre></details></section>')
    return str(body)


@router.post("/ui/answer/current", response_class=HTMLResponse)
@router.post("/ui/answer/current/result", response_class=HTMLResponse)
def action(request: Request, session: SessionDep,
           question: Annotated[str, Form(min_length=1, max_length=4000)],
           collection: Annotated[str, Form()] = "literature",
           top_k: Annotated[int, Form(ge=1)] = 5,
           method: Annotated[Literal["hybrid_cross_lingual"], Form()] = "hybrid_cross_lingual",
           answer_style: Annotated[Literal["claims", "mini_review"], Form()] = "claims",
           answer_language: Annotated[Literal["auto", "en", "ru"], Form()] = "ru",
           library_source_id: Annotated[UUID | None, Form()] = None) -> HTMLResponse:
    options = CurrentRequest(question=question, collection=collection, top_k=top_k, method=method,
        answer_style=answer_style, answer_language=answer_language, library_source_id=library_source_id)
    code, payload, sources = execute(session, options)
    panel = result_panel(payload, sources)
    if request.url.path.endswith("/result"):
        return HTMLResponse(panel, status_code=code)
    return _layout("Current answer", form(question, collection, top_k, answer_style, answer_language, library_source_id, panel))
