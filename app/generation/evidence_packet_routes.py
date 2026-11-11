"""Explicit canonical JSON export and read-only UI for diagnostic answer packets."""

from __future__ import annotations

import json
from html import escape
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.documents.service import build_pdf_url
from app.generation.answer_evidence_packet import build_packet, serialize_packet, validate_packet
from app.generation.preparation_routes import PreparationRequest, SessionDep, _form, prepare_page
from app.generation.requirements_routes import STATES, requirements_api
from app.ui import _layout

router = APIRouter()
KINDS = {"preparation_observed": "Сохранена исходная подготовка", "requirements_reconstructed": "Воспроизведена карта требований",
         "requirement_state_observed": "Зафиксировано состояние требования", "read_only_stop_observed": "Read-only остановка"}


def prepare_packet(session: Any, request: PreparationRequest) -> dict[str, Any]:
    parent = requirements_api(session, request)
    try:
        if parent["requirements"]["request_scope"] != request.model_dump(mode="json"):
            raise ValueError("Packet request scope differs from returned requirement preparation")
        return build_packet(parent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/answer/prepare/requirements/packet")
def packet_api(session: SessionDep, request: PreparationRequest) -> Response:
    packet = prepare_packet(session, request)
    return Response(serialize_packet(packet), media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="answer-evidence-' + packet["packet_id"][:12] + '.json"'})


def _details(label: str, value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return "<details><summary>" + escape(label) + "</summary><pre>" + escape(text) + "</pre></details>"


def render_packet(packet: dict[str, Any]) -> str:
    validate_packet(packet, packet["content"]["parent"], expected_packet_id=packet["packet_id"])
    content = packet["content"]
    labels: dict[str, str] = {r["id"]: r["label"] for r in content["parent"]["requirements"]["requirements"]}
    events: list[str] = []
    for event in packet["journal"]["events"]:
        requirement = event["details"].get("requirement_ref")
        reason = str(event["reason"])
        meaning = labels.get(requirement, "") + (": " if requirement else "") + STATES.get(reason, reason)
        events.append('<tr data-packet-event="' + str(event["sequence"]) + '"><td>' + str(event["sequence"]) + "</td><td>"
            + escape(KINDS[event["kind"]]) + "</td><td>" + escape(meaning) + "</td><td>"
            + _details("Точные основания и ссылки", event) + "</td></tr>")
    sources: list[str] = []
    for source in content["sources"]:
        pages = str(source["page_start"]) + ("–" + str(source["page_end"]) if source["page_end"] != source["page_start"] else "")
        sources.append(_details(source["citation_id"] + " · raw text · PDF " + pages, source["raw_text"])
            + '<p><a href="' + escape(build_pdf_url(source["article_id"], "original", source["page_start"]), quote=True)
            + '">Оригинальный PDF, диапазон ' + escape(pages) + "</a></p>")
    return ('<section class="panel" data-evidence-packet><h2>Пакет доказательств</h2>'
        '<p>Пакет и журнал — диагностические наблюдения системы, не человеческое подтверждение. '
        'Генерация отключена; действия сбора контекста не выполнены. Научная поддержка не оценена.</p>'
        '<p>Снимок: <code>' + escape(str(packet["packet_id"])) + "</code></p><p>Источников: " + str(len(content["sources"]))
        + "; точных raw anchors: " + str(len(content["anchors"])) + "; фактов-кандидатов: " + str(len(content["facts"]))
        + "; преобразований: " + str(len(content["transformations"])) + ".</p>"
        + "<p>PDF identities сохранены из исходного registry; файлы при сборке пакета не перечитываются. "
          "Неподтверждённые привязки к конкретной странице остаются явными.</p>"
        + _details("Исходные запреты и условие остановки", content["stop"])
        + "<h3>Журнал диагностических наблюдений</h3><div style='overflow-x:auto'><table><thead><tr>"
          "<th>№</th><th>Наблюдение</th><th>Основание</th><th>Подробности</th></tr></thead><tbody>"
        + "".join(events) + "</tbody></table></div><h3>Исходные фрагменты</h3>" + "".join(sources)
        + _details("Версии и declared code bindings", content["versions"])
        + _details("Anchors, факты, преобразования и непроверенные области", {k: content[k] for k in
                  ("anchors", "facts", "transformations", "inspection")})
        + _details("Полный JSON-пакет для воспроизведения", packet) + "</section>")


def _packet_form(question: str = "", library_source_id: UUID | None = None, result: str = "", *,
                 collection: str = "literature", top_k: int = 5, method: str = "hybrid_cross_lingual") -> str:
    return _form(question, library_source_id, result, collection=collection, top_k=top_k, method=method).replace(
        'action="/ui/answer/prepare"', 'action="/ui/answer/prepare/requirements/packet"', 1).replace(
        "<h1>Подготовка ответа</h1>", "<h1>Пакет доказательств и журнал</h1>", 1)


@router.get("/ui/answer/prepare/requirements/packet", response_class=HTMLResponse)
def packet_page(question: str = "", library_source_id: UUID | None = None,
                ariadne_library_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    page = prepare_page(question, library_source_id, ariadne_library_id)
    return HTMLResponse(bytes(page.body).decode("utf-8").replace(
        'action="/ui/answer/prepare"', 'action="/ui/answer/prepare/requirements/packet"', 1).replace(
        "<h1>Подготовка ответа</h1>", "<h1>Пакет доказательств и журнал</h1>", 1))


@router.post("/ui/answer/prepare/requirements/packet", response_class=HTMLResponse)
def packet_action(session: SessionDep, question: Annotated[str, Form()], collection: Annotated[str, Form()] = "literature",
                  top_k: Annotated[int, Form(ge=1)] = 5,
                  method: Annotated[Literal["exact", "semantic", "hybrid", "hybrid_cross_lingual"], Form()] = "hybrid_cross_lingual",
                  library_source_id: Annotated[UUID | None, Form()] = None) -> HTMLResponse:
    try:
        packet = prepare_packet(session, PreparationRequest(question=question, collection=collection, top_k=top_k,
            method=method, library_source_id=library_source_id))
        result = render_packet(packet)
    except HTTPException as exc:
        return HTMLResponse(_packet_form(question, library_source_id, '<p class="warn">' + escape(str(exc.detail)) + "</p>",
            collection=collection, top_k=top_k, method=method), status_code=exc.status_code)
    return _layout("Пакет доказательств", _packet_form(question, library_source_id, result,
        collection=collection, top_k=top_k, method=method))
