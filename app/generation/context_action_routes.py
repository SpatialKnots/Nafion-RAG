"""Explicit one-step read-only context completion; never inference or automatic continuation."""

from __future__ import annotations

import json
from html import escape
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.core.config import get_settings
from app.documents.service import DocumentAccessError, build_pdf_url
from app.evaluation.query_packet_run import collect_sources
from app.generation.answer_evidence_packet import serialize_packet
from app.generation.bounded_context_action import load_context_rows, run_context_action, validate_context_result
from app.generation.evidence_packet_routes import prepare_packet
from app.generation.preparation_routes import PreparationRequest, SessionDep, _form, prepare_page
from app.generation.requirements_routes import STATES
from app.ui import _layout

router = APIRouter()


def prepare_context_action(session: Any, request: PreparationRequest) -> dict[str, Any]:
    packet = prepare_packet(session, request)
    try:
        return run_context_action(packet, lambda scope: load_context_rows(session, scope),
            lambda source: collect_sources(session, get_settings(), [source]))
    except DocumentAccessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/answer/prepare/requirements/packet/context")
def context_action_api(session: SessionDep, request: PreparationRequest) -> Response:
    result = prepare_context_action(session, request)
    return Response(serialize_packet(result), media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="context-action-' + result["result_id"][:12] + '.json"'})


def _details(label: str, value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return "<details><summary>" + escape(label) + "</summary><pre>" + escape(text) + "</pre></details>"


def render_context_action(result: dict[str, Any]) -> str:
    validate_context_result(result, result["input_packet"], expected_result_id=result["result_id"])
    before = result["input_packet"]["content"]["parent"]["requirements"]
    after = result["after_requirements"]
    states = []
    for row in before["requirements"]:
        current = next((r for r in after["requirements"] if r["id"] == row["id"]), row) if after else row
        states.append("<tr><td>" + escape(row["label"]) + "</td><td>" + escape(STATES[row["state"]])
            + "</td><td>" + escape(STATES[current["state"]]) + "</td></tr>")
    added = result["added_evidence"]
    source = ""
    if added:
        source = ('<p><a href="' + escape(build_pdf_url(added["article_id"], "original", added["page_start"]), quote=True)
            + '">Добавленный исходный PDF-фрагмент</a></p>' + _details("Полный raw-текст без переписывания", added["text"]))
    consumed = result["consumed"]
    heading = "Один raw-контекст добавлен" if added else "Шаг остановлен без добавления контекста"
    return ('<section class="panel" data-context-action><h2>' + heading + "</h2>"
        "<p>Генерация отключена. Научная поддержка не оценена. Исходный пакет и запреты подготовки сохранены; "
        "новая карта относится только к диагностическому дополнению. Автоматического продолжения нет.</p>"
        "<p>Дополнительных поисков: " + str(consumed["additional_lookup_calls"]) + "; добавлено raw-чанков: "
        + str(consumed["accepted_raw_chunks"]) + "; просмотрено кандидатов: " + str(consumed["candidate_rows"]) + ".</p>"
        "<p>Лимиты: один поиск, один raw-чанк, окно двух страниц,12 кандидатов плюс sentinel; "
        "не более8000 символов добавленного текста. Связь принимается только по явному обозначению электролита.</p>"
        + "<table><thead><tr><th>Требование</th><th>До шага</th><th>После шага</th></tr></thead><tbody>"
        + "".join(states) + "</tbody></table>" + source
        + _details("Причина остановки, область и потреблённые лимиты", {k: result[k] for k in
                  ("stop_reason", "precondition", "plan", "budgets", "consumed")})
        + _details("Журнал одного шага", result["journal"])
        + _details("Полный результат, исходный пакет и непереписанные данные", result) + "</section>")


def _action_form(question: str = "", library_source_id: UUID | None = None, result: str = "", *,
                 collection: str = "literature", top_k: int = 5, method: str = "hybrid_cross_lingual") -> str:
    return _form(question, library_source_id, result, collection=collection, top_k=top_k, method=method).replace(
        'action="/ui/answer/prepare"', 'action="/ui/answer/prepare/requirements/packet/context"', 1).replace(
        "<h1>Подготовка ответа</h1>", "<h1>Один ограниченный шаг дополнения CE-контекста</h1>", 1).replace(
        "Проверить источники без генерации</button>", "Выполнить один ограниченный шаг</button>", 1)


@router.get("/ui/answer/prepare/requirements/packet/context", response_class=HTMLResponse)
def context_action_page(question: str = "", library_source_id: UUID | None = None,
                        ariadne_library_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    page = prepare_page(question, library_source_id, ariadne_library_id)
    return HTMLResponse(bytes(page.body).decode("utf-8").replace(
        'action="/ui/answer/prepare"', 'action="/ui/answer/prepare/requirements/packet/context"', 1).replace(
        "<h1>Подготовка ответа</h1>", "<h1>Один ограниченный шаг дополнения CE-контекста</h1>", 1).replace(
        "Проверить источники без генерации</button>", "Выполнить один ограниченный шаг</button>", 1))


@router.post("/ui/answer/prepare/requirements/packet/context", response_class=HTMLResponse)
def context_action_post(session: SessionDep, question: Annotated[str, Form()], collection: Annotated[str, Form()] = "literature",
                        top_k: Annotated[int, Form(ge=1)] = 5,
                        method: Annotated[Literal["exact", "semantic", "hybrid", "hybrid_cross_lingual"], Form()] = "hybrid_cross_lingual",
                        library_source_id: Annotated[UUID | None, Form()] = None) -> HTMLResponse:
    try:
        result = prepare_context_action(session, PreparationRequest(question=question, collection=collection, top_k=top_k,
            method=method, library_source_id=library_source_id))
        body = render_context_action(result)
    except HTTPException as exc:
        return HTMLResponse(_action_form(question, library_source_id, '<p class="warn">' + escape(str(exc.detail)) + "</p>",
            collection=collection, top_k=top_k, method=method), status_code=exc.status_code)
    return _layout("Один шаг контекста", _action_form(question, library_source_id, body,
        collection=collection, top_k=top_k, method=method))
