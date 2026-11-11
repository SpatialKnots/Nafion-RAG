"""Explicit read-only requirement preparation API/UI; old preparation unchanged."""

from __future__ import annotations

import json
from html import escape
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse

from app.documents.service import build_pdf_url
from app.generation.answer_requirements import build_requirements
from app.generation.preparation_routes import PreparationRequest, SessionDep, _form, prepare_api, prepare_page, render_preparation
from app.ui import _layout

VERSION = "answer_requirements_preparation_v0.1"
router = APIRouter()
STATES = {
    "recognized_source_pattern": "Шаблон факта распознан",
    "ambiguous_source_candidates": "Разные значения или области источников: варианты сохранены",
    "grammar_unrecognized": "Упоминание найдено; грамматика факта не распознана",
    "not_found_in_inspected_context": "В просмотренном выбранном контексте не найдено",
    "uninspected_selected_sources": "Часть выбранных источников не проверена",
    "textual_contract_available": "Доступен текстовый контракт связи",
    "conditional_policy_candidate": "Условный кандидат связи при явном правиле сопоставления списков",
    "identity_unresolved": "Связь ролей не установлена",
}
ACTIONS = {
    "compare_selected_source_candidates": "Сравнить сохранённые варианты и их области источников.",
    "inspect_unresolved_source_binding": "Проверить привязку выбранного фрагмента к исходному текстовому слою.",
    "inspect_selected_source_wording": "Посмотреть формулировку в выбранном фрагменте: парсер её не распознал.",
    "review_source_support": "Проверить смысл, образец, условия и оговорки по оригинальному PDF.",
    "review_identity_contract_assumptions": "Проверить основания и допущения текстовой связи в сохранённых источниках.",
    "inspect_selected_identity_definitions": "Посмотреть определения обозначений в уже выбранных фрагментах.",
}


@router.post("/answer/prepare/requirements")
def requirements_api(session: SessionDep, request: PreparationRequest) -> dict[str, Any]:
    baseline = prepare_api(session, request)
    try:
        requirements = build_requirements(baseline, request.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"version": VERSION, "preparation": baseline, "requirements": requirements,
            "generation_performed": False, "external_request_constructed": False, "network_ready": False}


def _details(label: str, value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return "<details><summary>" + escape(label) + "</summary><pre>" + escape(raw) + "</pre></details>"


def render_requirements(payload: dict[str, Any]) -> str:
    mapped = payload["requirements"]
    titles = {e["article_id"]: e.get("title") for e in payload["preparation"]["evidence"]}

    def anchor_html(anchor: dict[str, Any]) -> str:
        label = (titles.get(anchor["article_id"]) or "Название неизвестно") + " · PDF " + str(anchor["page_start"])
        if anchor["page_end"] != anchor["page_start"]:
            label += "–" + str(anchor["page_end"])
        return ("<p><a href=\"" + escape(build_pdf_url(anchor["article_id"], "original", anchor["page_start"]), quote=True)
                + "\">" + escape(label) + "</a></p>" + _details("Точный фрагмент", anchor["text"]))

    cards = []
    for row in mapped["requirements"]:
        content = []
        if row["id"] != "role_identity":
            for candidate in row["candidates"]:
                fields = [{"property": f["property"], "sample": f["sample"]["text"] if f["sample"] else None,
                    "value": f["value"]["text"] if f["value"] else None, "unit": f["unit"]["text"] if f["unit"] else None,
                    "conditions": {k: v["text"] for k, v in f["conditions"].items()},
                    "status": f["epistemic_status"], "unknown_fields": f["unknown_fields"]} for f in candidate["facts"]]
                content.append(_details("Распознанные поля; научная поддержка не оценена", fields))
                seen = set()
                for fact in candidate["facts"]:
                    a = fact["support"]
                    key = (a["chunk_id"], a["start"], a["end"])
                    if key not in seen:
                        content.append(anchor_html(a))
                        seen.add(key)
            if not row["candidates"]:
                content += [anchor_html(a) for a in row["cue_anchors"]]
            if not row["inspection_complete"]:
                content.append("<p>Выбранный контекст проверен не полностью; уникальность вариантов не установлена.</p>")
        else:
            content += [anchor_html(a) for a in row["anchors"]]
            content.append(_details("Текстовые контракты и их ограничения", row["contracts"]))
        cards.append('<article class="claim-card" data-answer-requirement="' + escape(row["id"], quote=True)
            + '"><h3>' + escape(row["label"]) + "</h3><p><strong>" + escape(STATES[row["state"]])
            + "</strong></p><p>Научная поддержка не оценена.</p>" + "".join(content)
            + "<p><strong>Что проверить дальше:</strong> " + escape(ACTIONS[row["next_action"]["kind"]])
            + " Действие предложено, не выполнено; новые источники не добавлены.</p>"
            + _details("Основание требования и полная диагностика", row) + "</article>")
    not_applicable = ("<p>Для этого вопроса карта требований пока не поддерживается. Дополнительные ограничения "
                      "вопроса не отброшены.</p>" if mapped["status"] == "not_applicable" else "")
    return ('<section class="panel" data-answer-requirements><h2>Требования и пробелы ответа</h2>'
        '<p>Генерация отключена. Карта описывает выбранный контекст; распознанный шаблон не подтверждает научный вывод. '
        'Исходные запреты подготовки сохранены.</p>' + not_applicable + "".join(cards)
        + _details("Область просмотра и версия", mapped)
        + '<details><summary>Исходная подготовка без изменений</summary>'
        + render_preparation(payload["preparation"]) + "</details></section>")


def _requirements_form(question: str = "", library_source_id: UUID | None = None, result: str = "", *,
                       collection: str = "literature", top_k: int = 5, method: str = "hybrid_cross_lingual") -> str:
    return _form(question, library_source_id, result, collection=collection, top_k=top_k, method=method).replace(
        'action="/ui/answer/prepare"', 'action="/ui/answer/prepare/requirements"', 1).replace(
        "<h1>Подготовка ответа</h1>", "<h1>Требования и пробелы ответа</h1>", 1)


@router.get("/ui/answer/prepare/requirements", response_class=HTMLResponse)
def requirements_page(question: str = "", library_source_id: UUID | None = None,
                      ariadne_library_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    page = prepare_page(question, library_source_id, ariadne_library_id)
    return HTMLResponse(bytes(page.body).decode("utf-8").replace(
        'action="/ui/answer/prepare"', 'action="/ui/answer/prepare/requirements"', 1).replace(
        "<h1>Подготовка ответа</h1>", "<h1>Требования и пробелы ответа</h1>", 1))


@router.post("/ui/answer/prepare/requirements", response_class=HTMLResponse)
def requirements_action(session: SessionDep, question: Annotated[str, Form()], collection: Annotated[str, Form()] = "literature",
                        top_k: Annotated[int, Form(ge=1)] = 5,
                        method: Annotated[Literal["exact", "semantic", "hybrid", "hybrid_cross_lingual"], Form()] = "hybrid_cross_lingual",
                        library_source_id: Annotated[UUID | None, Form()] = None) -> HTMLResponse:
    try:
        payload = requirements_api(session, PreparationRequest(question=question, collection=collection, top_k=top_k,
            method=method, library_source_id=library_source_id))
        result = render_requirements(payload)
    except HTTPException as exc:
        return HTMLResponse(_requirements_form(question, library_source_id, '<p class="warn">' + escape(str(exc.detail)) + "</p>",
            collection=collection, top_k=top_k, method=method), status_code=exc.status_code)
    return _layout("Требования к ответу", _requirements_form(question, library_source_id, result,
        collection=collection, top_k=top_k, method=method))
