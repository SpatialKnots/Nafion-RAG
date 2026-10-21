"""Dedicated local full-record editor; declared reviews remain separate from candidates."""

from __future__ import annotations

import hashlib
import html
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.records.review import observations_for_review
from app.records.revision_store import (
    RevisionConflict,
    RevisionRequest,
    export_review,
    load_state,
    locate_evidence,
    review_csv,
    save_revision,
)
from app.records.schema import CandidateBundle, ContractModel, NonEmpty


class EvidenceRequest(ContractModel):
    case_id: NonEmpty
    region_id: NonEmpty
    quote: NonEmpty
    occurrence: int = Field(ge=1)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _json_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _layout(body: str, token: str) -> HTMLResponse:
    response = HTMLResponse(
        '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>ARIADNE — полные записи</title><style>'
        'body{font:15px system-ui;background:#f4f7fb;color:#182537;margin:24px;line-height:1.45}'
        'a{color:#2056a3}section,article{background:white;padding:18px;border:1px solid #ccd5e1;border-radius:8px;margin:12px 0}'
        '.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'textarea{box-sizing:border-box;width:100%;min-height:90px}input,select,button,textarea{font:inherit;padding:7px;margin:4px 0}'
        'label{display:block;margin-top:10px}[hidden]{display:none!important}'
        'iframe{width:100%;height:520px;border:1px solid #ccd5e1}'
        '.notice{padding:12px;background:#fff1d0;border-left:4px solid #a36b00}.error{color:#9c1e1e;white-space:pre-wrap}'
        'button{cursor:pointer}small{color:#53647a}details{margin:8px 0}table{width:100%;border-collapse:collapse}'
        'td,th{text-align:left;border:1px solid #ccd5e1;padding:8px;vertical-align:top}'
        '@media(max-width:1000px){.grid{grid-template-columns:1fr}}'
        '</style><h1>ARIADNE: полные записи</h1><p><a href="/">Все входы</a> · '
        '<a href="/export/review.json">JSON: версии и evidence</a> · <a href="/export/review.csv">CSV</a></p>'
        '<p class="notice">Решение reviewer хранится отдельно. Candidate остаётся needs_review; '
        'scientific admission — not_evaluated. Имя и роль reviewer заявляются пользователем; независимость не подтверждена.</p>'
        + body + '</html>'
    )
    response.set_cookie("record_csrf", token, httponly=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _dashboard(state: dict[str, Any]) -> str:
    body = f'<p>Снимок: <code>{esc(state["snapshot_id"])}</code></p>'
    if state["stale_code"]:
        body += '<p class="notice">Код изменился. Сохранение и экспорт решений заблокированы.</p>'
    for case in state["baseline"]["cases"]:
        records = [item for item in state["records"] if item["case_id"] == case["case_id"]]
        body += f'<section><h2>{esc(case["case_id"])}</h2><p>{esc(case["input"]["path"])}</p>'
        if not records:
            body += '<p>Предложенных записей нет. Это не подтверждённый отрицательный результат.</p>'
        for item in records:
            record = item["candidate"]
            url = "/record?" + urlencode({"key": item["record_key"]})
            label = record["sample_label"]["raw_text"] or "Образец не установлен"
            value = record["value"]["raw_value"]["raw_text"] or "Значение не установлено"
            body += (f'<p><a href="{esc(url)}">{esc(label)} · {esc(value)}</a><br>'
                     f'Ревизия {item["revision"]} · {esc(item["declared_review_status"])} · '
                     f'{esc(item["checks"]["technical_outcome"])}</p>')
        body += '</section>'
    return body


def _editor(state: dict[str, Any], key: str, token: str) -> str:
    item = next((item for item in state["records"] if item["record_key"] == key), None)
    if item is None:
        raise HTTPException(404, "Unknown record key")
    case = next(case for case in state["baseline"]["cases"] if case["case_id"] == item["case_id"])
    bundle = CandidateBundle.model_validate(case["candidate_bundle"])
    current = next(record for record in bundle.records if str(record.record_id) == item["candidate"]["record_id"])
    observations = [name for name, _ in observations_for_review(current)]
    regions = [region for region in bundle.regions if str(region.article_id) == item["candidate"]["article_id"]]
    source_html = ""
    for index, region in enumerate(regions):
        pdf = f"/pdf/{case['case_id']}/{region.region_id}/original#page={region.page_number}"
        layer_pdf = f"/pdf/{case['case_id']}/{region.region_id}/selected#page={region.page_number}"
        source_html += (
            f'<details {"open" if index == 0 else ""}><summary>PDF p.{region.page_number}, {esc(region.text_layer)}</summary>'
            f'<p><a href="{esc(pdf)}" target="_blank" rel="noopener">Оригинал</a> · '
            f'<a href="{esc(layer_pdf)}" target="_blank" rel="noopener">Выбранный слой</a></p>'
            f'<pre>{esc(region.quote)}</pre><details><summary>Полный текст страницы и provenance</summary>'
            f'<pre>{esc(region.page_text)}</pre><pre>{esc(region.model_dump_json(indent=2))}</pre></details></details>'
        )
        if index == 0:
            source_html += f'<iframe title="Оригинальный PDF" src="{esc(pdf)}"></iframe>'
    options = "".join(f'<option value="field:{esc(name)}">{esc(name)}</option>' for name in observations)
    options += "".join(f'<option value="link:{role}">Связь: {role}</option>'
                       for role in ("sample_value", "property_value", "conditions_measurement"))
    region_options = "".join(f'<option value="{region.region_id}">Источник {i + 1}: PDF p.{region.page_number}, '
                              f'{esc(region.text_layer)}</option>' for i, region in enumerate(regions))
    history = "".join(
        f'<details><summary>#{event["revision"]} · {esc(event["action"])} · {esc(event["actor"])} '
        f'({esc(event["actor_kind"])}) · {esc(event["created_at"])}</summary>'
        f'<pre>{esc(json.dumps(event, ensure_ascii=False, indent=2))}</pre></details>' for event in item["history"]
    ) or '<p>Изменений пока нет. Ревизия 0 — исходный кандидат.</p>'
    init = {"snapshot_id": state["snapshot_id"], "item": item, "csrf": token, "case_id": item["case_id"],
            "regions": [region.model_dump(mode="json") for region in regions], "stale": state["stale_code"]}
    return (
        f'<p>Ревизия <strong>{item["revision"]}</strong> · решение: {esc(item["declared_review_status"])} · '
        f'технический результат: {esc(item["checks"]["technical_outcome"])}</p>'
        + ('<p class="notice">Код изменился. Сохранение заблокировано.</p>' if state["stale_code"] else '')
        + '<div class="grid"><section><h2>Источники</h2>' + source_html + '</section><section>'
        '<h2>Исправление записи</h2><p>Сохраняется новая ревизия. Прежнее решение сбрасывается в unreviewed.</p>'
        '<label>Кто вносит изменение<input id="actor" autocomplete="name"></label>'
        '<label>Роль<select id="actor-kind"><option value="human">Человек</option>'
        '<option value="assistant">Assistant</option></select></label>'
        '<label>Основание<textarea id="reason"></textarea></label>'
        f'<label>Поле или связь<select id="target">{options}</select></label>'
        '<div id="observation"><label>Status<select id="status"><option>present</option><option>not_found_in_context</option>'
        '<option>ambiguous</option><option>unsupported</option></select></label>'
        '<label>Точный raw text<textarea id="raw"></textarea></label></div>'
        '<label id="link-label" hidden><input id="link-enabled" type="checkbox"> Предложение связи присутствует</label>'
        '<p id="link-notice" hidden>Сохранение заменяет все предложения выбранной роли; остальные роли сохраняются.</p>'
        '<label>Примечание к полю / связи<textarea id="note"></textarea></label>'
        '<h3>Evidence выбранного поля / связи</h3><div id="spans"></div>'
        '<details><summary>Добавить точный фрагмент</summary>'
        f'<label>Источник<select id="region">{region_options}</select></label>'
        '<label>Точная цитата из frozen-текста<textarea id="quote"></textarea></label>'
        '<label>Номер совпадения, начиная с 1<input id="occurrence" type="number" min="1" value="1"></label>'
        '<button id="add-span" type="button">Добавить evidence</button></details>'
        '<button id="save-field" type="button">Сохранить исправление</button>'
        '<h3>Представление значения</h3><select id="representation"><option>scalar</option><option>range</option>'
        '<option>bound</option><option>unparsed</option></select>'
        '<button id="save-representation" type="button">Сохранить представление</button>'
        '<h3>Отдельное решение reviewer</h3><select id="decision"><option>needs_changes</option><option>rejected</option>'
        '<option>unreviewed</option><option>confirmed</option></select>'
        '<label><input id="source-reviewed" type="checkbox"> Проверены исходные PDF, поля и связи образец–значение–условия</label>'
        '<button id="save-decision" type="button">Записать решение</button>'
        '<h3>Восстановить содержимое</h3><label>Номер прежней ревизии, 0 = исходная запись'
        f'<input id="restore" type="number" min="0" max="{item["revision"]}" value="0"></label>'
        '<button id="save-restore" type="button">Создать ревизию из прежней версии</button>'
        '<p id="error" class="error" role="alert"></p></section></div><section><h2>Проверки</h2><pre>'
        + esc(json.dumps(item["checks"], ensure_ascii=False, indent=2)) + '</pre></section>'
        + '<section><h2>История</h2>' + history
        + '<details><summary>Исходная запись, ревизия 0</summary><pre>'
        + esc(json.dumps(item["original_candidate"], ensure_ascii=False, indent=2)) + '</pre></details></section>'
        + f'<script type="application/json" id="initial">{_json_script(init)}</script><script>{_EDITOR_JS}</script>'
    )


_EDITOR_JS = r"""
const initial=JSON.parse(document.getElementById('initial').textContent), $=id=>document.getElementById(id);
const original=initial.item.candidate; let spans=[];
const get=(object,name)=>name.split('.').reduce((v,k)=>v[k],object);
function replaceField(object,name,value){const keys=name.split('.');let parent=object;
  for(const key of keys.slice(0,-1))parent=parent[key];parent[keys.at(-1)]=value;}
function renderSpans(){const box=$('spans');box.replaceChildren();
  spans.forEach((span,index)=>{const card=document.createElement('article');
    const label=document.createElement('p'),pre=document.createElement('pre');
    const region=initial.regions.find(r=>r.region_id===span.region_id);
    label.textContent='PDF p.'+(region?.page_number??'?');pre.textContent=span.quote;
    const remove=document.createElement('button');remove.type='button';remove.textContent='Убрать evidence';
    remove.addEventListener('click',()=>{spans.splice(index,1);renderSpans();});card.append(label,pre,remove);box.append(card);});}
function choose(){const [mode,name]=$('target').value.split(':');const link=mode==='link';
  $('observation').hidden=link;$('link-label').hidden=!link;$('link-notice').hidden=!link;
  const data=link?original.linkage.find(l=>l.role===name):get(original,name);
  $('note').value=data?.note??'';$('link-enabled').checked=Boolean(data);
  if(!link){$('status').value=data.status;$('raw').value=data.raw_text??'';}
  spans=structuredClone(data?.evidence??[]);renderSpans();}
async function post(url,data){const response=await fetch(url,{method:'POST',
  headers:{'Content-Type':'application/json','X-Record-CSRF':initial.csrf},body:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw new Error(JSON.stringify(result.detail??result));return result;}
function request(action,extra){return {snapshot_id:initial.snapshot_id,record_key:initial.item.record_key,
  expected_revision:initial.item.revision,actor:$('actor').value,actor_kind:$('actor-kind').value,reason:$('reason').value,action,...extra};}
async function save(action,extra){if(initial.stale)throw new Error('Код изменился; сохранение заблокировано.');
  await post('/api/revisions',request(action,extra));location.reload();}
function run(fn){return async()=>{$('error').textContent='';try{await fn();}catch(error){$('error').textContent=String(error);}};}
function preserved(value,previous){return typeof previous==='string'&&value===previous.replace(/\r\n?/g,'\n')?previous:value;}
$('add-span').addEventListener('click',run(async()=>{const span=await post('/api/evidence',{case_id:initial.case_id,
  region_id:$('region').value,quote:$('quote').value,occurrence:Number($('occurrence').value)});spans.push(span);renderSpans();}));
$('save-field').addEventListener('click',run(async()=>{const candidate=structuredClone(original),[mode,name]=$('target').value.split(':');
  if(mode==='link'){candidate.linkage=candidate.linkage.filter(l=>l.role!==name);
    if($('link-enabled').checked)candidate.linkage.push({role:name,evidence:spans,note:$('note').value});}
  else{const prior=get(original,name);replaceField(candidate,name,{status:$('status').value,
    raw_text:$('status').value==='present'?preserved($('raw').value,prior.raw_text):null,evidence:spans,note:$('note').value||null});}
  await save('edit',{candidate});}));
$('save-representation').addEventListener('click',run(async()=>{const candidate=structuredClone(original);
  candidate.value.representation=$('representation').value;await save('edit',{candidate});}));
$('save-decision').addEventListener('click',run(()=>save('decide',{decision:$('decision').value,source_reviewed:$('source-reviewed').checked})));
$('save-restore').addEventListener('click',run(()=>save('restore',{restore_revision:Number($('restore').value)})));
$('target').addEventListener('change',choose);$('representation').value=original.value.representation;choose();
if(initial.stale)document.querySelectorAll('button').forEach(button=>button.disabled=true);
"""


def create_app(root: Path) -> FastAPI:
    root = root.resolve()
    app = FastAPI(title="ARIADNE full-record revisions")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    token = secrets.token_urlsafe(32)

    @app.exception_handler(RevisionConflict)
    async def revision_error(request: Request, exc: RevisionConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def validation_error(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(FileNotFoundError)
    async def missing_error(request: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(sqlite3.DatabaseError)
    async def database_error(request: Request, exc: sqlite3.DatabaseError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": f"Record revision database error: {exc}"})

    def csrf(request: Request) -> None:
        supplied = request.headers.get("X-Record-CSRF", "")
        cookie = request.cookies.get("record_csrf", "")
        origin = request.headers.get("origin")
        if (not secrets.compare_digest(supplied, token) or not secrets.compare_digest(cookie, token)
                or (origin is not None and origin != str(request.base_url).rstrip("/"))):
            raise HTTPException(403, "Invalid record CSRF token or Origin")

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        return _layout(_dashboard(load_state(root)), token)

    @app.get("/record", response_class=HTMLResponse)
    def editor(key: str) -> HTMLResponse:
        return _layout(_editor(load_state(root), key, token), token)

    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return load_state(root)

    @app.post("/api/revisions")
    def revise(payload: RevisionRequest, request: Request) -> dict[str, Any]:
        csrf(request)
        return save_revision(root, payload)

    @app.post("/api/evidence")
    def evidence(payload: EvidenceRequest, request: Request) -> dict[str, Any]:
        csrf(request)
        data = load_state(root)
        case = next((case for case in data["baseline"]["cases"] if case["case_id"] == payload.case_id), None)
        if case is None:
            raise HTTPException(404, "Unknown case")
        span = locate_evidence(CandidateBundle.model_validate(case["candidate_bundle"]), payload.region_id,
                               payload.quote, payload.occurrence)
        return span.model_dump(mode="json")

    @app.get("/pdf/{case_id}/{region_id}/{kind}")
    def pdf(case_id: str, region_id: str, kind: str) -> Response:
        if kind not in {"original", "selected"}:
            raise HTTPException(404, "Unknown PDF layer")
        data = load_state(root)
        case = next((case for case in data["baseline"]["cases"] if case["case_id"] == case_id), None)
        if case is None:
            raise HTTPException(404, "Unknown case")
        region = next((region for region in case["candidate_bundle"]["regions"] if region["region_id"] == region_id), None)
        if region is None:
            raise HTTPException(404, "Unknown frozen source region")
        path = Path(region["original_pdf_path"] if kind == "original" else region["layer_pdf_path"])
        expected = region["original_pdf_sha256"] if kind == "original" else region["layer_pdf_sha256"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RevisionConflict("Source PDF changed before response")
        return Response(raw, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="source.pdf"'})

    @app.get("/export/review.json")
    def json_export() -> dict[str, Any]:
        return export_review(root)

    @app.get("/export/review.csv")
    def csv_export() -> Response:
        return Response(review_csv(export_review(root)), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="records_review.csv"'})

    return app
