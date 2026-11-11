"""Explicit fresh-packet claim inspection API/UI; never imports client evidence."""

from __future__ import annotations

import json
from html import escape
from typing import Annotated, Any
from urllib.parse import parse_qsl
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import Field, ValidationError, field_validator

from app.generation.answer_evidence_packet import serialize_packet
from app.generation.claim_checks import CLAIMS, MAX_CLAIMS, MAX_INPUT_BYTES, Claim
from app.generation.claim_review import build_review, render_catalog, render_review
from app.generation.evidence_packet_routes import prepare_packet
from app.generation.preparation_routes import PreparationRequest, SessionDep
from app.ui import _layout

router = APIRouter()
PATH = "/answer/prepare/requirements/packet/checks"
UI_PATH = "/ui" + PATH
MAX_REQUEST_BYTES = 300000


def _claims(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list) or len(data) > MAX_CLAIMS:
        raise ValueError("Expected a list of at most 64 structured assertions")
    if len(serialize_packet({"claims": data})) > MAX_INPUT_BYTES:
        raise ValueError("Claim input exceeds canonical byte budget")
    parsed = CLAIMS.validate_python(data)
    if len({c.id for c in parsed}) != len(parsed):
        raise ValueError("Claim IDs must be unique")
    return [c.model_dump() for c in parsed]


class ClaimReviewRequest(PreparationRequest):
    expected_packet_id: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    claims: list[Claim] = Field(max_length=MAX_CLAIMS)

    @field_validator("claims")
    @classmethod
    def bounded_claims(cls, value: list[Claim]) -> list[Claim]:
        _claims([v.model_dump() for v in value])
        return value


def _json(text: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(value: str) -> Any:
        raise ValueError("Nonfinite JSON number: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


async def _bounded_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="Claim review request exceeds 300000 bytes")
    return bytes(body)


async def _api_request(request: Request) -> ClaimReviewRequest:
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(status_code=415, detail="Expected application/json")
    raw = await _bounded_body(request)
    try:
        return ClaimReviewRequest.model_validate(_json(raw.decode("utf-8")))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False)) from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def prepare_review(session: Any, request: ClaimReviewRequest) -> dict[str, Any]:
    base = PreparationRequest.model_validate(request.model_dump(exclude={"claims", "expected_packet_id"}))
    packet = prepare_packet(session, base)
    if packet["packet_id"] != request.expected_packet_id:
        raise HTTPException(status_code=409, detail="Evidence packet changed; prepare a new snapshot before checking assertions")
    try:
        if packet["content"]["request_scope"] != base.model_dump(mode="json"):
            raise ValueError("Review request scope differs from fresh packet scope")
        return build_review(packet, [c.model_dump() for c in request.claims], expected_packet_id=request.expected_packet_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _download(review: dict[str, Any]) -> Response:
    return Response(serialize_packet(review), media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="claim-review-' + review["review_id"][:12] + '.json"'})


@router.post(PATH)
def review_api(session: SessionDep, request: Annotated[ClaimReviewRequest, Depends(_api_request)]) -> Response:
    return _download(prepare_review(session, request))


def _form(values: dict[str, Any] | None = None, *, result: str = "", claims_json: str = "[]", packet_id: str = "", error: str = "") -> str:
    data: dict[str, Any] = {"question": "", "collection": "literature", "top_k": 5, "method": "hybrid_cross_lingual",
        "answer_style": "claims", "answer_language": "auto", "library_source_id": ""}
    data.update(values or {})
    controls = []
    for name, label in (("collection", "Коллекция"), ("top_k", "Top K"), ("library_source_id", "Библиотека (ID)")):
        controls.append("<label>" + label + ' <input name="' + name + '" value="'
                        + escape(str(data[name] or ""), quote=True) + '"></label>')
    for name, label, options in (("method", "Поиск", ("hybrid_cross_lingual", "hybrid", "semantic", "exact")),
        ("answer_style", "Форма исходного запроса", ("claims", "mini_review")), ("answer_language", "Язык", ("auto", "ru", "en"))):
        controls.append("<label>" + label + ' <select name="' + name + '">' + "".join('<option value="' + option + '"'
            + (" selected" if data[name] == option else "") + ">" + option + "</option>" for option in options) + "</select></label>")
    return ('<style>.claim-input-form{display:block}.claim-input-form label{display:block;margin:10px 0}'
        '.claim-input-form textarea,.claim-input-form input{box-sizing:border-box;width:100%}'
        '.claim-input-form textarea{min-height:100px}.claim-input-form details{display:block;margin:12px 0}'
        '.claim-scope{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}</style>'
        '<h1>Утверждения и источники</h1><p>Явный просмотр без генерации ответа. Сначала подготовьте снимок источников; '
        'затем передайте структурированные утверждения для сравнения. При изменении вопроса или настроек подготовьте новый снимок.</p>'
        + ('<p class="warn" role="alert">' + escape(error) + "</p>" if error else "")
        + '<form class="claim-input-form" method="post" action="' + UI_PATH + '"><label>Вопрос<br>'
        '<textarea name="question" rows="3" required>'
        + escape(str(data["question"])) + "</textarea></label><details><summary>Область поиска и настройки</summary>"
        + '<div class="claim-scope">' + " ".join(controls)
        + '</div></details><p><button name="intent" value="prepare">Подготовить снимок без генерации</button></p>'
        + '<details' + (" open" if packet_id else "") + '><summary>Явная проверка структурированных утверждений</summary>'
        '<p>Проверяющий слой принимает exact quotations, полные fact tuples и суммы. Он не извлекает утверждения из свободного текста. '
        'Записи источника ниже служат справочником; автоматической проверки их копий нет.</p>'
        '<label>Идентификатор подготовленного снимка <input name="expected_packet_id" readonly value="'
        + escape(packet_id, quote=True) + '"></label><label>Утверждения (JSON-массив)<br>'
        '<textarea name="claims_json" rows="10" spellcheck="false" maxlength="256000">' + escape(claims_json) + '</textarea></label>'
        '<p><button name="intent" value="check">Проверить явные утверждения</button> '
        '<button name="intent" value="download">Скачать проверяемый JSON-снимок</button></p></details></form>' + result)


@router.get(UI_PATH, response_class=HTMLResponse)
def review_page(question: str = "", library_source_id: UUID | None = None,
                ariadne_library_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    if library_source_id is None and ariadne_library_id:
        try:
            library_source_id = UUID(ariadne_library_id)
        except ValueError:
            pass  # Malformed preference cookie is not evidence or a selected library.
    return _layout("Утверждения и источники", _form({"question": question, "library_source_id": library_source_id}))


@router.post(UI_PATH, response_class=HTMLResponse)
async def review_action(session: SessionDep, request: Request) -> Response:
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Expected URL-encoded form; file uploads are not supported")
    raw = await _bounded_body(request)
    values: dict[str, Any] = {}
    claims_json, packet_id = "[]", ""
    try:
        pairs = parse_qsl(raw.decode("utf-8"), keep_blank_values=True, strict_parsing=True, errors="strict", max_num_fields=20)
        if len({k for k, _ in pairs}) != len(pairs):
            raise ValueError("Duplicate form keys are not supported")
        values = dict(pairs)
        claims_json, packet_id = str(values.pop("claims_json", "[]")), str(values.pop("expected_packet_id", ""))
        intent = values.pop("intent", "prepare")
        if intent not in {"prepare", "check", "download"}:
            raise ValueError("Unknown claim review action")
        if not values.get("library_source_id"):
            values["library_source_id"] = None
        base = PreparationRequest.model_validate(values)
        if intent == "prepare":
            packet = prepare_packet(session, base)
            if packet["content"]["request_scope"] != base.model_dump(mode="json"):
                raise ValueError("Review preparation scope differs from fresh packet scope")
            result = render_catalog(packet)
            packet_id = packet["packet_id"]
        else:
            claims = _claims(_json(claims_json))
            check = ClaimReviewRequest.model_validate({**base.model_dump(), "expected_packet_id": packet_id, "claims": claims})
            review = prepare_review(session, check)
            if intent == "download":
                return _download(review)
            result = render_review(review, review["packet"], expected_review_id=review["review_id"])
    except HTTPException as exc:
        response = _layout("Утверждения и источники", _form(values, claims_json=claims_json, packet_id=packet_id, error=str(exc.detail)))
        response.status_code = exc.status_code
        return response
    except ValueError as exc:
        response = _layout("Утверждения и источники", _form(values, claims_json=claims_json, packet_id=packet_id, error=str(exc)))
        response.status_code = 400
        return response
    return _layout("Утверждения и источники", _form(base.model_dump(), result=result, claims_json=claims_json, packet_id=packet_id))
