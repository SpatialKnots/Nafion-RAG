from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    Article,
    ArticleTag,
    Chunk,
    Collection,
    IngestionJob,
    LibrarySource,
    LibrarySourceFile,
    Page,
    PageTextLayer,
    Section,
    StructuredFact,
)
from app.db.session import get_session
from app.documents.context import ContextNotFoundError, get_chunk_context, get_page_range_context
from app.documents.service import PageEvidenceNotFoundError, build_pdf_url
from app.facts.service import list_structured_facts, structured_fact_summary, structured_fact_to_response
from app.generation.providers import GenerationOutputError, GenerationUnavailableError
from app.generation.service import answer_question, answer_response_to_dict
from app.ingestion.queue import job_to_response
from app.library.service import (
    DuplicateLibrarySourceError,
    create_library_source,
    delete_library_source,
    list_library_source_files,
    list_library_sources,
    scan_and_queue_library_source,
    update_library_source,
)
from app.retrieval.index_lifecycle import list_vector_index_states, request_vector_rebuild, vector_index_state_to_response
from app.retrieval.search import SearchFilters, search_chunks
from app.retrieval.vector_index import VectorIndexUnavailableError

SessionDep = Annotated[Session, Depends(get_session)]
router = APIRouter()
BRAND_ASSET_DIR = Path(__file__).resolve().parent / "static" / "brand"
BRAND_ASSETS = {
    "ariadne-logo-horizontal.png": "ariadne-logo-horizontal.png",
    "ariadne-logo-vertical.png": "ariadne-logo-vertical.png",
    "ariadne-logo-mark.png": "ariadne-logo-mark.png",
}


def _html(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def _brand_asset_url(name: str) -> str:
    return f"/ui/assets/brand/{_html(name)}"


def _optional_int_filter(name: str, value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{name} must be an integer") from exc


def _cookie_uuid(value: str | None) -> UUID | None:
    if value is None or not value.strip():
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _truncate(text: str | None, limit: int = 500) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _counter_rows(counter: Counter[str]) -> str:
    if not counter:
        return "<tr><td colspan='2'>No data</td></tr>"
    return "".join(f"<tr><td>{_html(key)}</td><td class='num'>{value}</td></tr>" for key, value in sorted(counter.items()))


def _dashboard_counter_rows(counter: Counter[str]) -> str:
    if not counter:
        return "<tr><td colspan='2'>No data</td></tr>"
    return "".join(
        f"<tr><td>{_html(_dashboard_label(key))}</td><td class='num'>{value}</td></tr>" for key, value in sorted(counter.items())
    )


def _dashboard_label(value: str) -> str:
    labels = {
        "figure_caption": "Figure caption",
        "main_text": "Main text",
        "method": "Method",
        "table": "Table",
        "original": "Original",
        "ocr": "OCR",
    }
    return labels.get(value, value.replace("_", " ").strip().capitalize())


def _counter_from_rows(rows: object) -> Counter[str]:
    pairs = cast(list[tuple[object, int]], rows)
    return Counter({str(key): value for key, value in pairs})


def _command_hint(command: str) -> str:
    return f"<p class='path'>{_html(command)}</p>"


def _page_range(start: int | None, end: int | None) -> str:
    if start is None:
        return ""
    if end is None or end == start:
        return str(start)
    return f"{start}-{end}"


def _pdf_link(article_id: UUID | str, page_number: int | None = None, label: str = "Open PDF") -> str:
    return f"<a href='{_html(build_pdf_url(article_id, 'original', page_number))}' target='_blank' rel='noopener'>{_html(label)}</a>"


def _ocr_pdf_link(article_id: UUID | str, label: str = "Open OCR PDF") -> str:
    return f"<a href='{_html(build_pdf_url(article_id, 'ocr'))}' target='_blank' rel='noopener'>{_html(label)}</a>"


def _group_metadata(doi: str | None, year: int | None, journal: str | None) -> str:
    return " ".join(_html(value) for value in (doi, year, journal) if value)


def _context_url(article_id: UUID | str, chunk_id: UUID | str, highlight_query: str = "", highlight_mode: str = "terms") -> str:
    params: dict[str, object] = {"before": 1, "after": 1}
    if highlight_query.strip():
        params["highlight_query"] = highlight_query
        if highlight_mode != "terms":
            params["highlight_mode"] = highlight_mode
    return f"/ui/articles/{article_id}/chunks/{chunk_id}/context?{urlencode(params)}"


def _context_link(article_id: UUID | str, chunk_id: UUID | str, query: str, label: str = "Context", highlight_mode: str = "terms") -> str:
    return f"<a href='{_html(_context_url(article_id, chunk_id, query, highlight_mode))}'>{_html(label)}</a>"


def _citation_href(citation: dict[str, object]) -> str | None:
    pdf_page_url = citation.get("pdf_page_url")
    if isinstance(pdf_page_url, str) and pdf_page_url.strip():
        return pdf_page_url
    article_id = citation.get("article_id")
    chunk_id = citation.get("chunk_id")
    if article_id and chunk_id:
        evidence_text = str(citation.get("text") or "")
        return _context_url(str(article_id), str(chunk_id), evidence_text, "phrase")
    return None


def _linked_answer_text(answer: str, citations: list[dict[str, object]]) -> str:
    by_id: dict[str, str] = {}
    for citation in citations:
        citation_id = citation.get("citation_id")
        href = _citation_href(citation)
        if citation_id and href:
            by_id[str(citation_id)] = href
    if not by_id:
        return _html(answer)

    parts: list[str] = []
    cursor = 0
    for match in re.finditer(r"\[([A-Za-z]\d+)\]", answer):
        citation_id = match.group(1)
        href = by_id.get(citation_id)
        if href is None:
            continue
        parts.append(_html(answer[cursor : match.start()]))
        parts.append(f"<a href='{_html(href)}' target='_blank' rel='noopener'>{_html(match.group(0))}</a>")
        cursor = match.end()
    parts.append(_html(answer[cursor:]))
    return "".join(parts)


def _highlighted_text(text: str, highlights: object) -> str:
    if not isinstance(highlights, list):
        return _html(text)
    spans = []
    for item in highlights:
        start = getattr(item, "start", None)
        end = getattr(item, "end", None)
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
            spans.append((start, end))
    if not spans:
        return _html(text)
    parts: list[str] = []
    cursor = 0
    for start, end in sorted(spans):
        if start < cursor:
            continue
        parts.append(_html(text[cursor:start]))
        parts.append(f"<mark>{_html(text[start:end])}</mark>")
        cursor = end
    parts.append(_html(text[cursor:]))
    return "".join(parts)


def _layout(title: str, body: str) -> HTMLResponse:
    css = """
    :root {
      color-scheme: light;
      --graphite:#2B3843;
      --slate:#5D7285;
      --aqua:#91DEDB;
      --coral:#E5664A;
      --paper:#FDFEFF;
      --line:#DCE3E8;
      --muted:#5D7285;
      --bg:#F4F7F9;
      --ink:#1F2A33;
      --accent:#247A82;
      --ok:#126B36;
      --warn:#8A4B16;
      --radius:12px;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; color: var(--ink); background: var(--bg); font-size: 14px; }
    .app-shell {
      min-height:100vh; display:grid; grid-template-columns:210px minmax(0, 1fr); gap:18px;
      padding:12px; border:1px solid #C9DAE3; background:#F7FAFB;
    }
    .sidebar {
      min-height:calc(100vh - 24px); padding:20px 14px; border-radius:14px; background:#203B4A; color:#F7FBFC;
      display:flex; flex-direction:column; gap:22px;
    }
    .brand-lockup {
      display:block; border-radius:8px; padding:8px; text-decoration:none;
    }
    .brand-lockup:hover, .brand-lockup:focus { outline:2px solid var(--aqua); outline-offset:2px; }
    .sidebar-logo { display:block; width:150px; max-width:100%; height:auto; }
    .ariadne-mark {
      position:relative; width:58px; height:74px; flex:0 0 auto;
    }
    .ariadne-mark::before {
      content:""; position:absolute; left:27px; top:10px; width:3px; height:52px; border-radius:999px;
      background:#91DEDB; box-shadow:0 -8px 0 #E5664A;
    }
    .thread-line {
      position:absolute; left:9px; width:38px; height:12px; border:5px solid #91DEDB; border-left-color:transparent;
      border-right-color:transparent; border-radius:50%; transform:rotate(-24deg);
    }
    .thread-line:nth-child(1) { top:15px; opacity:.35; }
    .thread-line:nth-child(2) { top:30px; transform:rotate(24deg); opacity:.65; }
    .thread-line:nth-child(3) { top:45px; opacity:1; }
    nav { display:grid; gap:8px; }
    nav a {
      color:#B8CBD5; text-decoration:none; min-height:34px; display:flex; gap:10px; align-items:center;
      padding:8px 10px; border-radius:8px; font-weight:600;
    }
    nav a::before {
      content:""; width:9px; height:9px; border:1px solid #91DEDB; border-radius:50%; flex:0 0 auto;
    }
    nav a.active { background:#365B6D; color:#fff; }
    nav a.active::before { background:#5BD4D3; border-color:#5BD4D3; }
    .sidebar-card {
      margin-top:auto; border:1px solid rgba(145,222,219,.28); border-radius:8px; padding:8px; background:#173341;
    }
    .sidebar-card small { display:block; color:#5DE1DF; font-size:10px; font-weight:700; text-transform:uppercase; margin-bottom:8px; }
    .sidebar-card strong { display:block; font-size:15px; font-weight:500; }
    .library-switch { position:relative; }
    .library-switch button {
      width:100%; display:grid; grid-template-columns:24px minmax(0, 1fr); gap:8px; align-items:center;
      background:transparent; border:0; color:#fff; padding:4px; text-align:left;
    }
    .library-plus { width:22px; height:22px; display:grid; place-items:center; border:1px solid #5DE1DF; border-radius:50%; }
    .library-menu {
      display:none; position:absolute; left:0; right:0; bottom:calc(100% + 8px); z-index:5;
      border:1px solid rgba(145,222,219,.38); border-radius:8px; background:#102C39; padding:6px;
      box-shadow:0 10px 24px rgba(16,44,57,.24);
    }
    .library-switch.open .library-menu { display:grid; gap:4px; }
    .library-menu a { color:#EAFBFC; text-decoration:none; padding:7px 8px; border-radius:6px; overflow-wrap:anywhere; }
    .library-menu a:hover, .library-menu a:focus { background:#365B6D; }
    main { min-width:0; padding:16px 12px 40px; max-width: none; margin: 0; }
    h1 { font-size: 28px; line-height:1.1; margin: 0 0 6px; color:#213846; }
    h2 { font-size: 17px; margin: 22px 0 8px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
    .workbench-grid { display:grid; grid-template-columns:minmax(320px, 0.9fr) minmax(420px, 1.4fr); gap:14px; align-items:start; }
    .evidence-grid { display:grid; grid-template-columns:minmax(320px, 0.9fr) minmax(420px, 1.2fr); gap:14px; align-items:start; }
    .panel { background:var(--paper); border:1px solid var(--line); border-radius:var(--radius); padding:18px; }
    .panel.compact h2 { margin-top:0; }
    .workspace-band {
      background:var(--paper); border:1px solid var(--line); border-radius:var(--radius);
      padding:18px; margin-bottom:14px;
    }
    .status-strip { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:8px 0 0; }
    .status-pill, .citation-chip {
      display:inline-flex; align-items:center; gap:6px; min-height:24px; padding:3px 8px; border:1px solid var(--line);
      border-radius:999px; background:#F8FBFC; color:var(--graphite); text-decoration:none; font-size:12px;
    }
    .status-pill.ok { border-color:#B8DCC7; color:var(--ok); background:#F4FBF7; }
    .status-pill.warn { border-color:#E5C6B1; color:var(--warn); background:#FFF8F3; }
    .citation-chip { border-color:#B9DADC; background:#F2FBFB; color:#155E63; font-weight:600; }
    .claim-card {
      position:relative; border:0; border-radius:0; padding:0 0 18px 34px; background:transparent; margin:0;
    }
    .claim-card::before {
      content:""; position:absolute; left:8px; top:5px; width:12px; height:12px; border-radius:50%; background:#5BD4D3;
      box-shadow:0 0 0 3px rgba(91,212,211,.18);
    }
    .claim-card::after {
      content:""; position:absolute; left:13px; top:20px; bottom:-5px; width:3px; border-radius:999px; background:#5BD4D3;
    }
    .claim-card:last-child::after { display:none; }
    .claim-card.low-evidence { border-left-color:var(--coral); }
    .claim-text { font-size:14px; line-height:1.45; margin:0 0 8px; }
    .source-card { border:1px solid var(--line); border-radius:8px; padding:16px; background:var(--paper); margin-bottom:10px; }
    .source-card.table-derived { border-left:4px solid var(--coral); }
    .source-head { display:flex; justify-content:space-between; gap:12px; align-items:start; margin-bottom:6px; }
    .source-title { font-weight:600; color:var(--graphite); }
    .source-fragment {
      border-left:6px solid var(--aqua); padding:14px 0 14px 18px; margin:14px 0;
      color:#24313A; background:#fff; border-radius:8px;
    }
    .empty-state { border:1px dashed var(--line); border-radius:var(--radius); padding:12px; background:#FBFCFD; }
    .muted { color: var(--muted); }
    .path { font-family: Consolas, monospace; font-size: 12px; word-break: break-all; }
    table { width:100%; border-collapse: collapse; background:var(--paper); border:1px solid var(--line); }
    th, td { border-bottom:1px solid var(--line); padding:7px 8px; vertical-align: top; text-align:left; }
    th { background:#EEF4F6; font-weight:600; color:var(--graphite); }
    tr:hover td { background:#FAFDFD; }
    .num { text-align:right; font-variant-numeric: tabular-nums; }
    .tag { display:inline-block; border:1px solid var(--line); border-radius:8px; padding:2px 5px; margin:1px; background:#F9FBFD; }
    .actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .actions a { display:inline-flex; min-height:26px; align-items:center; }
    .ok { color:var(--ok); font-weight:600; }
    .warn { color:var(--warn); font-weight:600; }
    .progress-steps { display:grid; gap:8px; margin:0; padding:0; list-style:none; }
    .progress-step { display:flex; gap:9px; align-items:center; color:var(--muted); }
    .progress-step .marker { width:18px; height:18px; border:1px solid #b9c4d2; border-radius:50%; display:inline-grid;
      place-items:center; flex:0 0 auto; font-size:12px; line-height:1; }
    .progress-step.running { color:var(--ink); font-weight:600; }
    .progress-step.done { color:#126b36; }
    .progress-step.done .marker { background:#126b36; border-color:#126b36; color:#fff; }
    .progress-step.error { color:#9b5a00; font-weight:600; }
    .progress-step.error .marker { background:#9b5a00; border-color:#9b5a00; color:#fff; }
    .progress-step.running .marker { border:2px solid #c7d0dd; border-top-color:var(--accent);
      animation: spin .8s linear infinite; }
    .pipeline-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:10px; margin:10px 0 14px; }
    .pipeline-meter { border:1px solid var(--line); border-radius:8px; padding:10px; background:#FBFCFD; }
    .pipeline-meter strong { display:block; margin-bottom:6px; color:var(--graphite); }
    .bar { height:9px; border-radius:999px; background:#E8EEF2; overflow:hidden; }
    .bar span { display:block; height:100%; background:#247A82; }
    .stage-line { display:flex; flex-wrap:wrap; gap:4px; margin-top:5px; }
    .stage-dot { min-width:22px; min-height:18px; display:inline-grid; place-items:center; border:1px solid var(--line);
      border-radius:999px; color:var(--muted); background:#F8FBFC; font-size:11px; }
    .stage-dot.done { border-color:#B8DCC7; color:var(--ok); background:#F4FBF7; }
    .stage-dot.running { border-color:#B9DADC; color:#155E63; background:#F2FBFB; font-weight:700; }
    .stage-dot.error { border-color:#E5C6B1; color:var(--warn); background:#FFF8F3; font-weight:700; }
    .stage-spinner { width:11px; height:11px; border:2px solid #B9DADC; border-top-color:#155E63; border-radius:50%;
      animation:spin .8s linear infinite; }
    .stage-check { font-weight:800; color:var(--ok); }
    button[disabled] { opacity:.65; cursor:wait; }
    @keyframes spin { to { transform: rotate(360deg); } }
    mark { background:#fff1a8; padding:0 1px; }
    pre.context { white-space: pre-wrap; font-family: Consolas, monospace; font-size: 13px; margin: 6px 0 0; }
    input, select, button {
      max-width:100%; font: inherit; padding:6px 8px; border:1px solid var(--line); border-radius:8px; background:var(--paper);
    }
    textarea { font: inherit; padding:7px 8px; border:1px solid var(--line); border-radius:8px; background:var(--paper);
      min-width: min(720px, 100%); }
    button { background:#203B4A; color:#fff; border-color:#203B4A; font-weight:700; }
    form { display:flex; gap:8px; flex-wrap:wrap; align-items:end; margin-bottom:14px; }
    form[data-async-result] { display:block; }
    form label { max-width:100%; min-width:0; }
    form.stack { display:block; }
    form.stack label { display:block; margin:0 0 10px; }
    form.stack .actions { margin-top:8px; }
    .page-kicker { color:#668091; margin:0 0 16px; font-size:15px; }
    .answer-search {
      display:grid; grid-template-columns:minmax(0, 1fr) auto; gap:10px; align-items:center;
      width:100%; padding:14px; border:1px solid var(--line); border-radius:14px; background:#fff; margin-bottom:14px;
    }
    .answer-search label { margin:0; }
    .answer-search textarea {
      min-height:42px; height:42px; resize:vertical; border:0; padding:10px 12px; font-size:15px; background:#fff;
    }
    .answer-search button { min-width:116px; min-height:42px; border-radius:9px; }
    .answer-controls {
      width:100%; display:grid; grid-template-columns:repeat(5, minmax(120px, 1fr)); gap:10px; margin:0 0 22px;
    }
    .answer-controls label { display:block; margin:0; color:#213846; }
    .answer-controls input, .answer-controls select { width:100%; min-height:40px; background:#fff; }
    .answer-surface {
      display:grid; grid-template-columns:minmax(0, 1.85fr) minmax(300px, .75fr); gap:20px; align-items:start;
    }
    .answer-card, .evidence-card {
      min-width:0; border:1px solid #D1E0E7; border-radius:14px; background:#fff; padding:24px;
    }
    .answer-card > h2, .evidence-card > h2 { margin-top:0; }
    .section-kicker { color:#486F88; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.02em; margin:0 0 12px; }
    .answer-lede {
      font-size:16px; line-height:1.55; font-weight:600; margin:0 0 24px; color:#213846;
      white-space:pre-wrap; overflow-wrap:break-word;
    }
    .citation-chip { border-radius:7px; }
    .start-page {
      min-height:calc(100vh - 68px); display:grid; align-content:start; gap:28px;
      padding:7vh 0 0;
    }
    .start-hero {
      width:min(820px, 100%); margin:0 auto; text-align:center;
    }
    .start-logo {
      width:min(420px, 78vw); height:auto; display:block; margin:0 auto 18px;
    }
    .start-hero h1 { font-size:36px; margin:0 0 8px; color:var(--graphite); }
    .start-hero .page-kicker { max-width:620px; margin:0 auto 22px; color:var(--slate); }
    .start-search {
      width:100%; display:block; margin:0;
    }
    .start-search-row {
      display:grid; grid-template-columns:minmax(0, 1fr) 48px 118px; gap:8px; align-items:center;
      padding:8px; border:1px solid var(--line); border-radius:12px; background:var(--paper);
    }
    .start-search-row input[name="question"] {
      width:100%; min-height:46px; border:0; padding:0 12px; background:transparent; font-size:16px;
    }
    .start-search-row input[name="question"]:focus { outline:2px solid var(--aqua); outline-offset:2px; border-radius:8px; }
    .advanced-toggle { position:absolute; opacity:0; pointer-events:none; }
    .icon-button {
      width:46px; min-width:46px; min-height:46px; display:inline-grid; place-items:center;
      padding:0; border-radius:8px; background:var(--paper); color:var(--graphite); border:1px solid var(--line);
      cursor:pointer;
    }
    .icon-button:hover, .icon-button:focus, .advanced-toggle:focus + .icon-button {
      border-color:var(--aqua); outline:0;
    }
    .advanced-toggle:checked + .icon-button { box-shadow:inset 0 0 0 2px var(--aqua); }
    .start-search-row button[type="submit"] { min-height:46px; border-radius:8px; }
    .advanced-panel {
      display:none; grid-column:1 / -1; text-align:left; border:1px solid var(--line); border-radius:12px;
      background:#F8FBFC; padding:12px; border-left:4px solid var(--aqua);
    }
    .advanced-toggle:checked ~ .advanced-panel { display:block; }
    .advanced-grid {
      display:grid; grid-template-columns:repeat(4, minmax(120px, 1fr)); gap:10px;
    }
    .advanced-grid label { display:block; color:var(--graphite); font-size:12px; font-weight:700; }
    .advanced-grid input, .advanced-grid select { width:100%; min-height:38px; margin-top:4px; background:var(--paper); }
    .start-result {
      width:min(1320px, 100%); margin:18px auto 0; text-align:left;
    }
    .start-result:empty { display:none; }
    .start-thread {
      width:min(620px, 100%); margin:16px auto 0; display:grid; grid-template-columns:repeat(4, minmax(0, 1fr));
      gap:0; align-items:center; color:var(--slate); font-size:12px; font-weight:700; text-transform:uppercase;
    }
    .start-thread span {
      position:relative; display:grid; place-items:center; min-height:34px; border:1px solid var(--line);
      background:var(--paper);
    }
    .start-thread span + span { border-left:0; }
    .start-thread span + span::before {
      content:""; position:absolute; left:-14px; top:50%; width:28px; height:3px; background:var(--aqua);
      transform:translateY(-50%);
    }
    .start-thread span:last-child::after {
      content:""; position:absolute; right:-6px; top:50%; width:12px; height:12px; border-radius:50%;
      background:var(--coral); transform:translateY(-50%);
    }
    .dashboard-section { width:min(1180px, 100%); margin:0 auto; }
    .dashboard-section > h2 { color:var(--graphite); }
    a { color: var(--accent); }
    @media (max-width: 900px) {
      .app-shell { grid-template-columns:1fr; padding:8px; }
      .sidebar { min-height:auto; padding:12px; gap:10px; border-radius:10px; }
      .sidebar-card { display:none; }
      .brand-lockup { min-height:28px; padding:0; }
      .sidebar-logo { width:118px; }
      nav { grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); }
      .workbench-grid, .evidence-grid, .answer-surface { grid-template-columns:1fr; }
      .answer-controls { grid-template-columns:1fr 1fr; }
      .answer-search { grid-template-columns:1fr; }
      main { padding:12px 0 32px; }
      .start-page { min-height:auto; padding-top:18px; }
      .start-logo { width:min(270px, 72vw); margin-bottom:14px; }
      .start-hero h1 { font-size:32px; }
      .start-search-row { grid-template-columns:1fr 46px; }
      .start-search-row button[type="submit"] { grid-column:1 / -1; }
      .advanced-grid { grid-template-columns:1fr 1fr; }
      .start-thread { grid-template-columns:1fr; }
      .start-thread span + span { border-left:1px solid var(--line); border-top:0; }
      .start-thread span + span::before { display:none; }
      .start-thread span:last-child::after { right:12px; }
    }
    """
    nav_items = (
        ("Home", "/", {"Dashboard", "Articles", "Article", "Text Layers", "Answer"}),
        ("Facts", "/ui/facts", {"Structured Facts"}),
        (
            "Evidence",
            "/ui/reports/retrieval",
            {"Retrieval Evaluation Report", "Extended Retrieval Evaluation Report", "Text Quality Report", "Classification Report"},
        ),
        ("Sessions", "/ui/ingestion", {"Ingestion"}),
        ("Libraries", "/ui/libraries", {"Libraries"}),
        ("Settings", "/ui/vector-indexes", {"Vector Indexes"}),
    )
    nav = "".join(
        f"<a class='{'active' if title in active_titles else ''}' href='{href}'>{label}</a>"
        for label, href, active_titles in nav_items
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html(title)}</title>
<style>{css}</style>
</head>
<body>
<div class="app-shell">
<aside class="sidebar">
  <a class="brand-lockup" href="/" aria-label="ARIADNE home">
    <img class="sidebar-logo" src="{_brand_asset_url('ariadne-logo-horizontal.png')}" alt="ARIADNE">
  </a>
  <nav>{nav}</nav>
  <div class="sidebar-card library-switch" data-library-switch>
    <button type="button" data-library-toggle aria-expanded="false">
      <span class="library-plus">+</span><strong data-current-library>Evidence library</strong>
    </button>
    <div class="library-menu" data-library-menu></div>
  </div>
</aside>
<main>{body}</main>
</div>
{_library_switch_script()}
</body></html>"""
    return HTMLResponse(html)


def _library_switch_script() -> str:
    return """
    <script>
    (() => {
      const key = 'ariadne:selectedLibraries';
      const currentKey = 'ariadne:currentLibrary';
      const switcher = document.querySelector('[data-library-switch]');
      if (!switcher) return;
      const label = switcher.querySelector('[data-current-library]');
      const menu = switcher.querySelector('[data-library-menu]');
      const toggle = switcher.querySelector('[data-library-toggle]');
      const read = (name) => {
        const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : '';
      };
      const write = (name, value) => {
        document.cookie = name + '=' + encodeURIComponent(value) + '; path=/; samesite=lax';
      };
      const loadList = () => {
        try { return JSON.parse(sessionStorage.getItem(key) || '[]'); } catch (_) { return []; }
      };
      const esc = (value) => String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      })[char]);
      const saveList = (items) => sessionStorage.setItem(key, JSON.stringify(items.slice(-12)));
      const current = (() => {
        try { return JSON.parse(sessionStorage.getItem(currentKey) || 'null'); } catch (_) { return null; }
      })();
      const cookieId = read('ariadne_library_id');
      let items = loadList();
      if (current && current.id) {
        items = [...items.filter((item) => item.id !== current.id), current];
        saveList(items);
      }
      const active = current || items.find((item) => item.id === cookieId) || items[items.length - 1];
      if (active && active.name) label.textContent = active.name;
      const render = () => {
        const latest = loadList();
        menu.innerHTML = latest.length
          ? latest.map((item) => '<a href="/ui/libraries?library_id=' + encodeURIComponent(item.id) +
              '" data-library-id="' + esc(item.id) + '">' + esc(item.name) + '</a>').join('')
          : '<a href="/ui/libraries">Add Library</a>';
      };
      render();
      toggle.addEventListener('click', () => {
        switcher.classList.toggle('open');
        toggle.setAttribute('aria-expanded', switcher.classList.contains('open') ? 'true' : 'false');
        render();
      });
      menu.addEventListener('click', (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement) || !target.dataset.libraryId) return;
        const item = loadList().find((value) => value.id === target.dataset.libraryId);
        if (item) {
          sessionStorage.setItem(currentKey, JSON.stringify(item));
          write('ariadne_library_id', item.id);
        }
      });
      document.querySelectorAll('form[data-library-scoped]').forEach((form) => {
        form.addEventListener('submit', () => {
          const activeItem = (() => {
            try { return JSON.parse(sessionStorage.getItem(currentKey) || 'null'); } catch (_) { return null; }
          })();
          const id = (activeItem && activeItem.id) || read('ariadne_library_id');
          if (!id) return;
          let input = form.querySelector('input[name="library_source_id"]');
          if (!input) {
            input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'library_source_id';
            form.appendChild(input);
          }
          input.value = id;
        });
      });
    })();
    </script>
    """


@router.get("/ui/assets/brand/{asset_name}")
def brand_asset(asset_name: str) -> FileResponse:
    filename = BRAND_ASSETS.get(asset_name)
    if filename is None:
        raise HTTPException(status_code=404, detail="Unknown brand asset")
    return FileResponse(BRAND_ASSET_DIR / filename)


@router.get("/ui/", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def dashboard(session: SessionDep) -> HTMLResponse:
    settings = get_settings()
    retrieval_report = _latest_standard_retrieval_report(settings.data_root)
    extended_retrieval_report = _latest_extended_retrieval_report(settings.data_root)
    text_quality_report = _latest_report(settings.data_root, "text_quality_report_*.json")
    retrieval_report_link = (
        f"<a href='/ui/reports/retrieval'>Latest retrieval evaluation</a><div class='path'>{_html(retrieval_report)}</div>"
        if retrieval_report is not None
        else "<span class='warn'>No retrieval evaluation report generated yet.</span>"
    )
    text_quality_report_link = (
        f"<a href='/ui/reports/text-quality'>Latest text quality audit</a><div class='path'>{_html(text_quality_report)}</div>"
        if text_quality_report is not None
        else "<span class='warn'>No text quality report generated yet.</span>"
    )
    extended_retrieval_report_link = (
        f"<a href='/ui/reports/retrieval-extended'>Latest extended retrieval evaluation</a>"
        f"<div class='path'>{_html(extended_retrieval_report)}</div>"
        if extended_retrieval_report is not None
        else "<span class='warn'>No extended retrieval evaluation report generated yet.</span>"
    )
    article_count = session.scalar(select(func.count()).select_from(Article)) or 0
    page_count = session.scalar(select(func.count()).select_from(Page)) or 0
    chunk_count = session.scalar(select(func.count()).select_from(Chunk)) or 0
    layer_count = session.scalar(select(func.count()).select_from(PageTextLayer)) or 0
    selected_layers = _counter_from_rows(
        session.execute(select(Page.selected_text_layer, func.count()).group_by(Page.selected_text_layer)).all()
    )
    source_types = _counter_from_rows(session.execute(select(Chunk.source_type, func.count()).group_by(Chunk.source_type)).all())
    text_layers = _counter_from_rows(session.execute(select(Chunk.text_layer, func.count()).group_by(Chunk.text_layer)).all())
    corpus_rows = (
        f'<tr><td>Articles</td><td class="num">{article_count}</td></tr>'
        f'<tr><td>Pages</td><td class="num">{page_count}</td></tr>'
        f'<tr><td>Chunks</td><td class="num">{chunk_count}</td></tr>'
        f'<tr><td>Text layers</td><td class="num">{layer_count}</td></tr>'
    )
    selected_rows = _dashboard_counter_rows(selected_layers)
    source_rows = _dashboard_counter_rows(source_types)
    text_layer_rows = _dashboard_counter_rows(text_layers)
    eval_command = "python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10"
    extended_eval_command = (
        "python -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --top-k 10 --method exact"
    )
    text_quality_command = "python -m app.ingestion.cli text-quality-report"
    selected_panel = (
        '<section class="panel"><h2>Selected Page Layers</h2>'
        f'<table><tr><th>Layer</th><th class="num">Pages</th></tr>{selected_rows}</table></section>'
    )
    source_panel = (
        '<section class="panel"><h2>Chunk Source Types</h2>'
        f'<table><tr><th>Type</th><th class="num">Chunks</th></tr>{source_rows}</table></section>'
    )
    text_layer_panel = (
        '<section class="panel"><h2>Chunk Text Layers</h2>'
        f'<table><tr><th>Layer</th><th class="num">Chunks</th></tr>{text_layer_rows}</table></section>'
    )
    body = f"""
    <div class="start-page">
      <section class="start-hero" aria-labelledby="start-title">
        <img class="start-logo" src="{_brand_asset_url('ariadne-logo-horizontal.png')}" alt="ARIADNE">
        <h1 id="start-title">ARIADNE Research Workbench</h1>
        <p class="page-kicker">Ask a literature question and trace the answer to source fragments and the original PDF.</p>
        <form class="start-search" method="post" action="/ui/answer" data-async-result="/ui/answer/result" data-library-scoped>
          <div class="start-search-row">
            <input name="question" value="" placeholder="Ask for a literature review" aria-label="Question" autofocus>
            <input class="advanced-toggle" id="start-answer-options" type="checkbox" aria-label="Show answer parameters">
            <label class="icon-button" for="start-answer-options" aria-label="Answer parameters" title="Answer parameters">&#9881;</label>
            <button type="submit">Answer</button>
            <div class="advanced-panel">
              <div class="advanced-grid">
                <label>Collection<input name="collection" value="literature"></label>
                <label>Method<select name="method">
                  <option value="hybrid_cross_lingual">hybrid_cross_lingual</option>
                  <option value="hybrid">hybrid</option>
                  <option value="semantic">semantic</option>
                  <option value="exact">exact</option>
                </select></label>
                <label>Answer style<select name="answer_style">
                  <option value="mini_review">mini_review</option>
                  <option value="claims">claims</option>
                </select></label>
                <label>Answer language<select name="answer_language">
                  <option value="auto">auto</option>
                  <option value="ru">ru</option>
                  <option value="en">en</option>
                </select></label>
                <label>Top K<input name="top_k" type="number" value="10" min="1"></label>
              </div>
            </div>
          </div>
        </form>
        <div class="start-result" id="home-answer-result" aria-live="polite"></div>
        <div class="start-thread" aria-label="Evidence path">
          <span>Question</span><span>Retrieve</span><span>Review</span><span>Original PDF</span>
        </div>
        {_answer_progress_script("home-answer-result")}
      </section>
      <section class="dashboard-section" aria-labelledby="corpus-dashboard">
        <h2 id="corpus-dashboard">Corpus Dashboard</h2>
        <div class="grid">
          {_project_analysis_progress_panel(session)}
          <section class="panel"><h2>Corpus</h2><table>{corpus_rows}</table></section>
          {selected_panel}
          {source_panel}
          {text_layer_panel}
          <section class="panel"><h2>Retrieval Evaluation</h2>{retrieval_report_link}{_command_hint(eval_command)}</section>
          <section class="panel"><h2>Extended Retrieval Evaluation</h2>
          {extended_retrieval_report_link}{_command_hint(extended_eval_command)}</section>
          <section class="panel"><h2>Tables / Facts diagnostics</h2>
          {text_quality_report_link}{_command_hint(text_quality_command)}</section>
        </div>
      </section>
    </div>
    """
    return _layout("Dashboard", body)


def _answer_payload_panel(payload: dict[str, Any], question: str) -> str:
    status_class = "ok" if payload.get("status") == "answered" else "warn"
    answer = payload.get("answer")
    metadata = payload.get("metadata", {})
    adequacy = metadata.get("evidence_adequacy") if isinstance(metadata, dict) else None
    adequacy_row = ""
    if isinstance(adequacy, dict):
        distinctive_terms = (
            [str(term) for term in adequacy.get("distinctive_terms", [])]
            if isinstance(adequacy.get("distinctive_terms"), list)
            else []
        )
        matched_terms = (
            [str(term) for term in adequacy.get("matched_terms", [])]
            if isinstance(adequacy.get("matched_terms"), list)
            else []
        )
        missing_terms = [term for term in distinctive_terms if term not in set(matched_terms)]
        term_diagnostics = ""
        if distinctive_terms:
            term_diagnostics = (
                f"<br><span class='muted'>matched={_html(', '.join(matched_terms) or 'none')}; "
                f"missing={_html(', '.join(missing_terms) or 'none')}</span>"
            )
        adequacy_row = (
            f"<p><strong>Evidence:</strong> {_html(adequacy.get('reason'))} "
            f"<span class='muted'>coverage={_html(adequacy.get('coverage'))}, top={_html(adequacy.get('top_coverage'))}</span>"
            f"{term_diagnostics}</p>"
        )
    query_assistance = metadata.get("query_assistance") if isinstance(metadata, dict) else None
    query_assistance_row = ""
    if isinstance(query_assistance, dict):
        corrected_query = str(query_assistance.get("corrected_query") or "")
        corrections = query_assistance.get("corrections")
        correction_text = ""
        if isinstance(corrections, list):
            correction_text = ", ".join(
                f"{item.get('original')} -> {item.get('suggestion')}"
                for item in corrections
                if isinstance(item, dict) and item.get("original") and item.get("suggestion")
            )
        if corrected_query:
            query_assistance_row = (
                "<section class='panel'>"
                f"<p><strong>Possible query typo:</strong> {_html(correction_text or corrected_query)}</p>"
                f"<p><strong>Suggested query:</strong> {_html(corrected_query)}</p>"
                f"<button type='button' data-suggested-query='{_html(corrected_query)}'>Use suggested query</button>"
                "</section>"
            )
    derived_evidence = metadata.get("derived_evidence") if isinstance(metadata, dict) else None
    derived_evidence_row = ""
    if isinstance(derived_evidence, dict):
        source_pages = derived_evidence.get("source_pages")
        source_page_text = ""
        if isinstance(source_pages, list) and source_pages:
            source_page_text = _page_range(
                source_pages[0] if isinstance(source_pages[0], int) else None,
                source_pages[1] if len(source_pages) > 1 and isinstance(source_pages[1], int) else None,
            )
        derived_evidence_row = (
            "<section class='panel'>"
            "<p class='section-kicker'>Derived evidence</p>"
            f"<p><strong>Type:</strong> {_html(derived_evidence.get('type'))} &nbsp; "
            f"<strong>Pages:</strong> {_html(source_page_text or 'unknown')} &nbsp; "
            f"<strong>Matching rows:</strong> {_html(derived_evidence.get('matching_row_count'))} &nbsp; "
            f"<strong>Nonmatching rows:</strong> {_html(derived_evidence.get('nonmatching_row_count'))}</p>"
            f"<p><strong>Source article:</strong> {_html(derived_evidence.get('source_article_id'))}<br>"
            f"<strong>Source chunk:</strong> {_html(derived_evidence.get('source_chunk_id'))}</p>"
            "</section>"
        )
    citation_by_id: dict[str, dict[str, object]] = {}
    citation_dicts: list[dict[str, object]] = []
    citations = payload.get("citations", [])
    if isinstance(citations, list):
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            citation_dicts.append(citation)
            citation_id = citation.get("citation_id")
            if citation_id:
                citation_by_id[str(citation_id)] = citation

    claim_cards = []
    claims = payload.get("claims", [])
    if isinstance(claims, list):
        for index, claim in enumerate(claims, start=1):
            if not isinstance(claim, dict):
                continue
            citation_ids = [str(item) for item in claim.get("citation_ids", [])]
            chips = []
            for citation_id in citation_ids:
                citation = citation_by_id.get(citation_id)
                href = _citation_href(citation) if citation else None
                if href:
                    chips.append(
                        f"<a class='citation-chip' href='{_html(href)}' target='_blank' rel='noopener'>"
                        f"{_html(citation_id)}</a>"
                    )
                else:
                    chips.append(f"<span class='citation-chip'>{_html(citation_id)}</span>")
            citation_chips_html = "".join(chips) or "<span class='muted'>No citation links</span>"
            claim_cards.append(
                "<article class='claim-card'>"
                f"<p class='section-kicker'>Claim {index:02d}</p>"
                f"<p class='claim-text'>{_html(claim.get('text'))}</p>"
                f"<div class='actions'>{citation_chips_html}</div>"
                "</article>"
            )

    source_cards = []
    citation_rows = []
    for citation in citation_dicts:
        article_id = citation.get("article_id")
        chunk_id = citation.get("chunk_id")
        raw_page_start = citation.get("page_start")
        raw_page_end = citation.get("page_end")
        page_start = raw_page_start if isinstance(raw_page_start, int) else None
        page_end = raw_page_end if isinstance(raw_page_end, int) else None
        evidence_text = str(citation.get("text") or "")
        links = []
        if article_id and chunk_id:
            links.append(_context_link(str(article_id), str(chunk_id), evidence_text, "Evidence", "phrase"))
            links.append(_context_link(str(article_id), str(chunk_id), question))
        if article_id:
            links.append(_pdf_link(str(article_id), page_start))
        title = _html(citation.get("title"))
        article_cell = f"<a href='/ui/articles/{_html(article_id)}'>{title}</a>" if article_id else title
        page_range = _page_range(page_start, page_end)
        source_type = str(citation.get("source_type") or "")
        source_class = "source-card table-derived" if source_type == "table_derived" else "source-card"
        source_cards.append(
            f"<article class='{source_class}'>"
            "<div class='source-head'>"
            f"<div><span class='citation-chip'>{_html(citation.get('citation_id'))}</span> "
            f"<span class='source-title'>{article_cell}</span><div class='muted'>{_html(citation.get('doi'))}</div></div>"
            f"<div class='num muted'>p. {_html(page_range or 'unknown')}</div>"
            "</div>"
            f"<div class='source-fragment'>{_html(_truncate(evidence_text, 520))}</div>"
            f"<div class='status-strip'><span class='status-pill'>{_html(source_type or 'source')}</span>"
            f"<span class='status-pill'>language={_html(citation.get('original_language') or 'unknown')}</span>"
            f"<span class='status-pill'>translation={_html(citation.get('translation_status') or 'not_requested')}</span></div>"
            f"<p class='actions'>{' '.join(links)}</p>"
            "</article>"
        )
        citation_rows.append(
            "<tr>"
            f"<td>{_html(citation.get('citation_id'))}</td>"
            f"<td>{article_cell}"
            f"<div class='muted'>{_html(citation.get('doi'))}</div></td>"
            f"<td class='num'>{_html(_page_range(page_start, page_end))}</td>"
            f"<td>{_html(citation.get('original_language') or 'unknown')}</td>"
            f"<td class='num'>{_html(citation.get('score'))}</td>"
            f"<td>{_html(_truncate(str(citation.get('text') or ''), 360))}"
            f"<div class='muted'>translation={_html(citation.get('translation_status') or 'not_requested')}</div></td>"
            f"<td class='actions'>{' '.join(links)}</td>"
            "</tr>"
        )
    answer_block = (
        f"<div class='answer-lede'>{_linked_answer_text(str(answer), citation_dicts)}</div>"
        if answer
        else "<p class='warn'>No answer: evidence was insufficient or generation failed validation.</p>"
    )
    claim_cards_html = (
        "".join(claim_cards) or "<div class='empty-state warn'>No claims. The available evidence did not support an answer.</div>"
    )
    citation_rows_html = "".join(citation_rows) or "<tr><td colspan='7'>No citations</td></tr>"
    source_cards_html = "".join(source_cards) or "<div class='empty-state warn'>No source fragments selected.</div>"
    retrieved_count = metadata.get("retrieved_count") if isinstance(metadata, dict) else ""
    return (
        "<section class='workspace-band'>"
        f"<p><strong>Query:</strong> {_html(payload.get('query') or question)}</p>"
        "<div class='status-strip'>"
        f"<span class='status-pill {status_class}'><strong>Status:</strong> {_html(payload.get('status'))}</span>"
        f"<span class='status-pill'><strong>Retrieval:</strong> {_html(payload.get('retrieval_method'))}</span>"
        f"<span class='status-pill'><strong>Provider:</strong> {_html(payload.get('generation_provider'))}</span>"
        f"<span class='status-pill'><strong>Retrieved:</strong> {_html(retrieved_count)}</span>"
        "</div>"
        f"{adequacy_row}"
        "</section>"
        f"{query_assistance_row}"
        f"{derived_evidence_row}"
        "<div class='answer-surface'>"
        "<section class='answer-card'>"
        "<p class='section-kicker'>Evidence-based answer</p>"
        f"{answer_block}"
        f"<div class='claims-thread'>{claim_cards_html}</div></section>"
        "<section class='evidence-card'>"
        "<p class='section-kicker'>Source fragment</p>"
        f"{source_cards_html}</section>"
        "</div>"
        "<h2>Citations</h2><table><tr><th>ID</th><th>Article</th><th class='num'>Pages</th>"
        f"<th>Language</th><th class='num'>Score</th><th>Evidence text</th><th>Links</th></tr>{citation_rows_html}</table>"
    )


def _answer_error_panel(exc: Exception) -> str:
    if isinstance(exc, GenerationUnavailableError):
        title = "Generation provider unavailable"
        hint = (
            "Retrieval may have succeeded, but answer generation could not reach the configured provider. "
            "Check RAG_PROVIDER=openai, OpenAI API key, OpenAI base URL, and local network permissions."
        )
    elif isinstance(exc, GenerationOutputError):
        title = "Generation output rejected"
        hint = "The provider returned an answer that failed validation; claims and citations were not rendered."
    elif isinstance(exc, VectorIndexUnavailableError):
        title = "Vector index unavailable"
        hint = "The selected retrieval method needs a ready vector index. Rebuild it or choose an exact retrieval method."
    else:
        title = "Answer request failed"
        hint = "The request parameters or local service state need attention before an answer can be generated."
    return (
        "<section class='workspace-band' data-result-status='error'>"
        "<div class='status-strip'>"
        f"<span class='status-pill warn'><strong>Status:</strong> error</span>"
        f"<span class='status-pill'><strong>Type:</strong> {_html(type(exc).__name__)}</span>"
        "</div>"
        f"<p><strong>{_html(title)}</strong></p>"
        f"<p>{_html(hint)}</p>"
        f"<p class='path'>{_html(exc)}</p>"
        "</section>"
    )


def _answer_progress_script(result_id: str) -> str:
    return f"""
    <script>
    (() => {{
      const result = document.getElementById('{_html(result_id)}');
      const form = result ? result.closest('main').querySelector('form[data-async-result]') : null;
      if (!form || !result || !window.fetch) return;
      const steps = [
        ['prepare', 'Prepare request parameters'],
        ['send', 'Send request to backend'],
        ['wait', 'Wait for retrieval, evidence check, and generation'],
        ['receive', 'Receive answer payload'],
        ['render', 'Render answer and citations']
      ];
      const progressHtml = () => '<section class="panel"><ol class="progress-steps">' +
        steps.map(([key, label]) =>
          '<li class="progress-step" data-step="' + key + '">' +
          '<span class="marker"></span><span>' + label + '</span></li>'
        ).join('') +
        '</ol></section>';
      const setStep = (activeKey, doneKeys = [], errorKey = null) => {{
        for (const item of result.querySelectorAll('.progress-step')) {{
          const marker = item.querySelector('.marker');
          const key = item.dataset.step;
          item.classList.remove('running', 'done', 'error');
          if (doneKeys.includes(key)) {{
            item.classList.add('done');
            if (marker) marker.textContent = '✓';
          }} else if (errorKey === key) {{
            item.classList.add('error');
            if (marker) marker.textContent = '!';
          }} else if (activeKey === key) {{
            item.classList.add('running');
            if (marker) marker.textContent = '';
          }} else if (marker) {{
            marker.textContent = '';
          }}
        }}
      }};
      form.addEventListener('submit', async (event) => {{
        event.preventDefault();
        const button = form.querySelector('button[type="submit"]');
        const originalText = button ? button.textContent : '';
        if (button) {{
          button.disabled = true;
          button.textContent = 'Loading...';
        }}
        result.innerHTML = progressHtml();
        setStep('prepare');
        try {{
          setStep('send', ['prepare']);
          const data = new FormData(form);
          const readCookie = (name) => {{
            const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
            return match ? decodeURIComponent(match[1]) : '';
          }};
          const activeLibrary = (() => {{
            try {{ return JSON.parse(sessionStorage.getItem('ariadne:currentLibrary') || 'null'); }} catch (_) {{ return null; }}
          }})();
          const activeLibraryId = (activeLibrary && activeLibrary.id) || readCookie('ariadne_library_id');
          if (activeLibraryId && !data.get('library_source_id')) {{
            data.set('library_source_id', activeLibraryId);
          }}
          const responsePromise = fetch(form.dataset.asyncResult, {{
            method: 'POST',
            body: data,
            headers: {{'X-Requested-With': 'fetch'}}
          }});
          setStep('wait', ['prepare', 'send']);
          const response = await responsePromise;
          setStep('wait', ['prepare', 'send']);
          const body = await response.text();
          setStep('receive', ['prepare', 'send', 'wait']);
          if (!response.ok) {{
            setStep(null, ['prepare', 'send', 'wait'], 'receive');
            result.insertAdjacentHTML('beforeend', '<section class="panel"><p class="warn">' + body + '</p></section>');
            return;
          }}
          setStep('render', ['prepare', 'send', 'wait', 'receive']);
          result.insertAdjacentHTML('beforeend', body);
          if (result.querySelector('[data-result-status="error"]')) {{
            setStep(null, ['prepare', 'send', 'wait', 'receive'], 'render');
          }} else {{
            setStep(null, ['prepare', 'send', 'wait', 'receive', 'render']);
          }}
        }} catch (error) {{
          setStep(null, ['prepare'], 'send');
          result.insertAdjacentHTML(
            'beforeend',
            '<section class="panel"><p class="warn">Request failed before the answer was returned.</p></section>'
          );
        }} finally {{
          if (button) {{
            button.disabled = false;
            button.textContent = originalText;
          }}
        }}
      }});
      result.addEventListener('click', (event) => {{
        const target = event.target;
        if (!(target instanceof HTMLElement) || !target.dataset.suggestedQuery) return;
        const question = form.querySelector('[name="question"]');
        if (question) {{
          question.value = target.dataset.suggestedQuery;
          form.requestSubmit();
        }}
      }});
    }})();
    </script>
    """


def _answer_body(
    question: str = "",
    collection: str = "literature",
    top_k: int = 5,
    method: str = "hybrid_cross_lingual",
    answer_style: str = "claims",
    answer_language: str = "auto",
    result: str = "",
    library_source_id: UUID | str | None = None,
) -> str:
    method_options = "".join(
        f"<option value='{value}' {'selected' if method == value else ''}>{value}</option>"
        for value in ("exact", "semantic", "hybrid", "hybrid_cross_lingual")
    )
    style_options = "".join(
        f"<option value='{value}' {'selected' if answer_style == value else ''}>{label}</option>"
        for value, label in (("claims", "Claims"), ("mini_review", "Mini-review by article"))
    )
    language_options = "".join(
        f"<option value='{value}' {'selected' if answer_language == value else ''}>{label}</option>"
        for value, label in (("auto", "Auto"), ("en", "English"), ("ru", "Russian"))
    )
    return f"""
    <h1>Search the literature</h1>
    <p class="page-kicker">Every claim should lead back to a source fragment.</p>
    <form method="post" action="/ui/answer" data-async-result="/ui/answer/result" data-library-scoped>
      <input type="hidden" name="library_source_id" value="{_html(library_source_id or '')}">
      <div class="answer-search">
        <label><span class="section-kicker">Question</span><br><textarea name="question" rows="1">{_html(question)}</textarea></label>
        <button type="submit">Search</button>
      </div>
      <div class="answer-controls">
        <label>Collection<br><input name="collection" value="{_html(collection)}"></label>
        <label>Top K<br><input name="top_k" type="number" value="{top_k}" min="1"></label>
        <label>Method<br><select name="method">{method_options}</select></label>
        <label>Style<br><select name="answer_style">{style_options}</select></label>
        <label>Answer language<br><select name="answer_language">{language_options}</select></label>
      </div>
    </form>
    <div id="answer-result" aria-live="polite">{result}</div>
    {_answer_progress_script("answer-result")}
    """


@router.get("/ui/answer", response_class=HTMLResponse)
def answer_page(
    question: str = "",
    collection: str = "literature",
    library_source_id: UUID | None = None,
    ariadne_library_id: Annotated[str | None, Cookie()] = None,
    top_k: int = Query(default=5, ge=1),
    method: str = "hybrid_cross_lingual",
    answer_style: str = "claims",
    answer_language: str = "auto",
) -> HTMLResponse:
    active_library_id = library_source_id or _cookie_uuid(ariadne_library_id)
    return _layout(
        "Answer",
        _answer_body(question, collection, top_k, method, answer_style, answer_language, library_source_id=active_library_id),
    )


def _answer_result_fragment(
    session: Session,
    question: str,
    collection: str,
    top_k: int,
    method: str,
    answer_style: str,
    answer_language: str,
    library_source_id: UUID | None = None,
) -> str:
    if top_k <= 0:
        return "<section class='panel'><p class='warn'>top_k must be positive.</p></section>"
    try:
        response = answer_question(
            session,
            get_settings(),
            question,
            collection=collection,
            top_k=top_k,
            method=method,
            answer_style=answer_style,
            answer_language=answer_language,
            library_source_id=library_source_id,
        )
        payload = answer_response_to_dict(response)
        return _answer_payload_panel(payload, question)
    except (GenerationUnavailableError, GenerationOutputError, VectorIndexUnavailableError, ValueError) as exc:
        return _answer_error_panel(exc)


@router.post("/ui/answer", response_class=HTMLResponse)
def answer_action(
    session: SessionDep,
    question: Annotated[str, Form()],
    collection: Annotated[str, Form()] = "literature",
    top_k: Annotated[int, Form()] = 5,
    method: Annotated[str, Form()] = "hybrid_cross_lingual",
    answer_style: Annotated[str, Form()] = "claims",
    answer_language: Annotated[str, Form()] = "auto",
    library_source_id: Annotated[UUID | None, Form()] = None,
) -> HTMLResponse:
    result = _answer_result_fragment(session, question, collection, top_k, method, answer_style, answer_language, library_source_id)
    return _layout(
        "Answer",
        _answer_body(question, collection, top_k, method, answer_style, answer_language, result, library_source_id),
    )


@router.post("/ui/answer/result", response_class=HTMLResponse)
def answer_result_action(
    session: SessionDep,
    question: Annotated[str, Form()],
    collection: Annotated[str, Form()] = "literature",
    top_k: Annotated[int, Form()] = 5,
    method: Annotated[str, Form()] = "hybrid_cross_lingual",
    answer_style: Annotated[str, Form()] = "claims",
    answer_language: Annotated[str, Form()] = "auto",
    library_source_id: Annotated[UUID | None, Form()] = None,
) -> HTMLResponse:
    return HTMLResponse(
        _answer_result_fragment(session, question, collection, top_k, method, answer_style, answer_language, library_source_id)
    )


@router.get("/ui/vector-indexes", response_class=HTMLResponse)
def vector_indexes_page(session: SessionDep) -> HTMLResponse:
    states = [vector_index_state_to_response(state) for state in list_vector_index_states(session)]
    rows = []
    for state in states:
        collection = str(state.get("collection") or state.get("collection_id"))
        model = str(state["embedding_model"])
        error = ""
        if state.get("last_error_type") or state.get("last_error_message"):
            error = f"<div class='warn'>{_html(state.get('last_error_type'))}: {_html(state.get('last_error_message'))}</div>"
        rows.append(
            "<tr>"
            f"<td>{_html(collection)}</td>"
            f"<td class='path'>{_html(model)}</td>"
            f"<td>{_html(state['status'])}{error}</td>"
            f"<td class='num'>{_html(state['desired_revision'])}</td>"
            f"<td class='num'>{_html(state['active_revision'])}</td>"
            f"<td class='num'>{_html(state['building_revision'])}</td>"
            f"<td>{_html(state['requested_at'])}</td>"
            f"<td>{_html(state['finished_at'])}</td>"
            "<td>"
            f"<form method='post' action='/ui/vector-indexes/{_html(collection)}/rebuild'>"
            f"<input type='hidden' name='embedding_model' value='{_html(model)}'>"
            "<button type='submit'>Rebuild</button></form>"
            "</td>"
            "</tr>"
        )
    table_rows = "".join(rows) or "<tr><td colspan='9'>No vector index states</td></tr>"
    body = (
        "<h1>Vector Indexes</h1>"
        "<table><tr><th>Collection</th><th>Embedding model</th><th>Status</th>"
        "<th class='num'>Desired</th><th class='num'>Active</th><th class='num'>Building</th>"
        f"<th>Requested</th><th>Finished</th><th>Action</th></tr>{table_rows}</table>"
        "<p class='muted'>Exact search is independent. Semantic and hybrid require a ready vector index generation.</p>"
    )
    return _layout("Vector Indexes", body)


@router.post("/ui/vector-indexes/{collection}/rebuild", response_class=HTMLResponse)
def vector_index_rebuild_action(session: SessionDep, collection: str, embedding_model: Annotated[str, Form()]) -> HTMLResponse:
    try:
        request_vector_rebuild(session, collection_name=collection, embedding_model=embedding_model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return vector_indexes_page(session)


def search_page(
    session: SessionDep,
    q: str = "",
    collection: str = "literature",
    library_source_id: UUID | None = None,
    ariadne_library_id: Annotated[str | None, Cookie()] = None,
    top_k: int = Query(default=10, ge=1),
    article_id: UUID | None = None,
    doi: str = "",
    year: str | int | None = "",
    year_from: str | int | None = "",
    year_to: str | int | None = "",
    journal: str = "",
    source_type: str = "",
    text_layer: str = "",
    tag_type: str = "",
    tag_value: str = "",
    method: str = "exact",
    group_by: str = "none",
    chunks_per_article: str | int | None = "",
) -> HTMLResponse:
    rows = ""
    year_filter = _optional_int_filter("year", year)
    year_from_filter = _optional_int_filter("year_from", year_from)
    year_to_filter = _optional_int_filter("year_to", year_to)
    chunks_per_article_filter = _optional_int_filter("chunks_per_article", chunks_per_article)
    active_library_id = library_source_id or _cookie_uuid(ariadne_library_id)
    if chunks_per_article_filter is not None and chunks_per_article_filter <= 0:
        raise HTTPException(status_code=400, detail="chunks_per_article must be positive")
    filters = SearchFilters.normalize(
        article_id=article_id,
        library_source_id=active_library_id,
        doi=doi,
        year=year_filter,
        year_from=year_from_filter,
        year_to=year_to_filter,
        journal=journal,
        source_type=source_type,
        text_layer=text_layer,
        tag_type=tag_type,
        tag_value=tag_value,
    )
    if q.strip():
        try:
            response = search_chunks(
                session,
                q,
                collection,
                top_k,
                method=method,
                filters=filters,
                group_by=group_by,
                chunks_per_article=chunks_per_article_filter,
                settings=get_settings(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        response_groups = getattr(response, "groups", [])
        if response_groups:
            rows = "".join(
                "<tr>"
                f"<td><a href='/ui/articles/{_html(group.article_id)}'>{_html(group.title)}</a>"
                f"<div class='muted'>{_group_metadata(group.doi, group.year, group.journal)}</div></td>"
                f"<td class='num'>{_html(_page_range(group.best_page_start, group.best_page_end))}</td>"
                f"<td class='num'>{group.best_score:.4g}</td>"
                f"<td class='num'>{group.result_count}/{group.total_result_count}</td>"
                f"<td>{_html(group.results[0].retrieval_method)}</td>"
                f"<td>{_html(group.results[0].snippet)}</td>"
                f"<td class='actions'>{_context_link(group.article_id, group.results[0].chunk_id, q)}"
                f"{_pdf_link(group.article_id, group.best_page_start)}</td>"
                "</tr>"
                for group in response_groups
            )
        elif response.results:
            rows = "".join(
                "<tr>"
                f"<td><a href='/ui/articles/{_html(result.article_id)}'>{_html(result.title)}</a>"
                f"<div class='muted'>{_html(result.doi)}</div></td>"
                f"<td class='num'>{_html(_page_range(result.page_start, result.page_end))}</td>"
                f"<td>{_html(result.source_type)}<div class='muted'>{_html(result.text_layer)}</div></td>"
                f"<td>{_html(result.retrieval_method)}</td>"
                f"<td class='num'>{result.score:.4g}</td>"
                f"<td>{_html(result.snippet)}</td>"
                f"<td class='actions'>{_context_link(result.article_id, result.chunk_id, q)}"
                f"{_pdf_link(result.article_id, result.page_start)}</td>"
                "</tr>"
                for result in response.results
            )
        else:
            rows = "<tr><td colspan='7'>No results</td></tr>"
    empty_rows = "<tr><td colspan='7'>Enter a query.</td></tr>"
    source_options = "".join(
        f"<option value='{_html(value)}' {'selected' if source_type == value else ''}>{_html(label)}</option>"
        for value, label in [
            ("", "all"),
            ("method", "method"),
            ("main_text", "main_text"),
            ("table", "table"),
            ("figure_caption", "figure_caption"),
        ]
    )
    method_options = "".join(
        f"<option value='{value}' {'selected' if method == value else ''}>{value}</option>" for value in ("exact", "semantic", "hybrid")
    )
    text_layer_options = "".join(
        f"<option value='{_html(value)}' {'selected' if text_layer == value else ''}>{_html(label)}</option>"
        for value, label in [("", "all"), ("original", "original"), ("ocr", "ocr")]
    )
    group_options = "".join(
        f"<option value='{value}' {'selected' if group_by == value else ''}>{value}</option>" for value in ("none", "article")
    )
    year_value = "" if year_filter is None else str(year_filter)
    year_from_value = "" if year_from_filter is None else str(year_from_filter)
    year_to_value = "" if year_to_filter is None else str(year_to_filter)
    chunks_value = "" if chunks_per_article_filter is None else str(chunks_per_article_filter)
    table_header = (
        '<tr><th>Article</th><th class="num">Best pages</th><th class="num">Best score</th>'
        '<th class="num">Chunks</th><th>Method</th><th>Best snippet</th><th>PDF</th></tr>'
        if group_by == "article"
        else '<tr><th>Article</th><th class="num">Pages</th><th>Type / layer</th><th>Method</th>'
        '<th class="num">Score</th><th>Snippet</th><th>PDF</th></tr>'
    )
    body = f"""
    <h1>Search</h1>
    <form method="get" action="/ui/search" data-library-scoped>
      <input type="hidden" name="library_source_id" value="{_html(active_library_id or '')}">
      <label>Query<br><input name="q" size="52" value="{_html(q)}"></label>
      <label>Collection<br><input name="collection" value="{_html(collection)}"></label>
      <label>Source type<br><select name="source_type">{source_options}</select></label>
      <label>Text layer<br><select name="text_layer">{text_layer_options}</select></label>
      <label>Method<br><select name="method">{method_options}</select></label>
      <label>Top K<br><input name="top_k" type="number" value="{top_k}" min="1"></label>
      <label>DOI<br><input name="doi" value="{_html(doi)}"></label>
      <label>Year<br><input name="year" type="number" value="{_html(year_value)}"></label>
      <label>Year from<br><input name="year_from" type="number" value="{_html(year_from_value)}"></label>
      <label>Year to<br><input name="year_to" type="number" value="{_html(year_to_value)}"></label>
      <label>Journal<br><input name="journal" value="{_html(journal)}"></label>
      <label>Tag type<br><input name="tag_type" value="{_html(tag_type)}"></label>
      <label>Tag value<br><input name="tag_value" value="{_html(tag_value)}"></label>
      <label>Group by<br><select name="group_by">{group_options}</select></label>
      <label>Chunks/article<br><input name="chunks_per_article" type="number" value="{_html(chunks_value)}" min="1"></label>
      <button type="submit">Search</button>
    </form>
    <table>{table_header}
    {rows or empty_rows}</table>
    """
    return _layout("Search", body)


@router.get("/ui/articles/{article_id}/chunks/{chunk_id}/context", response_class=HTMLResponse)
def chunk_context_page(
    session: SessionDep,
    article_id: UUID,
    chunk_id: UUID,
    before: int = Query(default=1, ge=0),
    after: int = Query(default=1, ge=0),
    highlight_query: str = "",
    highlight_mode: str = "terms",
    max_chars: int | None = Query(default=None, ge=1),
) -> HTMLResponse:
    article = _get_article_or_404(session, article_id)
    if highlight_mode not in {"terms", "phrase"}:
        raise HTTPException(status_code=400, detail="highlight_mode must be one of: terms, phrase")
    try:
        context = get_chunk_context(
            session,
            get_settings(),
            article,
            chunk_id,
            before=before,
            after=after,
            highlight_query=highlight_query,
            highlight_mode=cast(Any, highlight_mode),
            max_chars=max_chars,
        )
    except ContextNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows = []
    for chunk in context.chunks:
        page_params: dict[str, object] = {"page_start": chunk.page_start, "page_end": chunk.page_end, "layer": "selected"}
        if highlight_query.strip():
            page_params["highlight_query"] = highlight_query
            if highlight_mode != "terms":
                page_params["highlight_mode"] = highlight_mode
        page_context = f"/ui/articles/{context.article_id}/pages/context?{urlencode(page_params)}"
        rows.append(
            "<section class='panel'>"
            f"<p><strong>{_html(chunk.role)}</strong> chunk {chunk.chunk_index} &nbsp; "
            f"pages {_html(_page_range(chunk.page_start, chunk.page_end))} &nbsp; "
            f"{_html(chunk.source_type)} / {_html(chunk.text_layer)} &nbsp; "
            f"<a href='{_html(page_context)}'>Page text</a> {_pdf_link(context.article_id, chunk.page_start)}</p>"
            f"<pre class='context'>{_highlighted_text(chunk.text, chunk.highlights)}</pre>"
            "</section>"
        )
    body = f"""
    <h1>{_html(context.title)}</h1>
    <section class="panel">
      <p><strong>DOI:</strong> {_html(context.doi)} &nbsp; <strong>Requested chunk:</strong> {context.requested_chunk_index}</p>
      <p class="actions"><a href="/ui/articles/{_html(context.article_id)}">Article</a>
      <a href="{_html(context.pdf_page_url)}" target="_blank" rel="noopener">PDF page</a></p>
      {"<p class='warn'>Truncated by context limit.</p>" if context.truncated else ""}
    </section>
    {"".join(rows) or "<p class='warn'>No context chunks.</p>"}
    """
    return _layout("Chunk Context", body)


@router.get("/ui/articles/{article_id}/pages/context", response_class=HTMLResponse)
def page_context_page(
    session: SessionDep,
    article_id: UUID,
    page_start: int = Query(..., ge=1),
    page_end: int = Query(..., ge=1),
    layer: str = "selected",
    highlight_query: str = "",
    highlight_mode: str = "terms",
    max_chars: int | None = Query(default=None, ge=1),
) -> HTMLResponse:
    article = _get_article_or_404(session, article_id)
    if layer not in {"selected", "original", "ocr"}:
        raise HTTPException(status_code=400, detail="layer must be one of: selected, original, ocr")
    if highlight_mode not in {"terms", "phrase"}:
        raise HTTPException(status_code=400, detail="highlight_mode must be one of: terms, phrase")
    try:
        context = get_page_range_context(
            session,
            get_settings(),
            article,
            page_start=page_start,
            page_end=page_end,
            layer=cast(Any, layer),
            highlight_query=highlight_query,
            highlight_mode=cast(Any, highlight_mode),
            max_chars=max_chars,
        )
    except PageEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    page_range = _page_range(context.page_start, context.page_end)
    rows = "".join(
        "<section class='panel'>"
        f"<p><strong>Page {page.page_number}</strong> &nbsp; {_html(page.resolved_layer)} &nbsp; "
        f"{'usable' if page.has_usable_text else 'not usable'}</p>"
        f"<pre class='context'>{_highlighted_text(page.text, page.highlights)}</pre>"
        "</section>"
        for page in context.pages
    )
    body = f"""
    <h1>{_html(context.title)}</h1>
    <section class="panel">
      <p><strong>Layer:</strong> {_html(context.layer)} &nbsp; <strong>Pages:</strong> {_html(page_range)}</p>
      <p class="actions"><a href="/ui/articles/{_html(context.article_id)}">Article</a>
      <a href="{_html(context.pdf_page_url)}" target="_blank" rel="noopener">PDF page</a></p>
      {"<p class='warn'>Truncated by context limit.</p>" if context.truncated else ""}
    </section>
    {rows or "<p class='warn'>No page text.</p>"}
    """
    return _layout("Page Context", body)


def _library_status_class(status: str) -> str:
    if status in {"active", "ready", "text_ready", "duplicate"}:
        return "ok"
    if status in {"missing", "failed", "error"}:
        return "warn"
    return ""


def _progress_percent(done: int, total: int) -> int:
    if total <= 0:
        return 0
    return round(done / total * 100)


def _pipeline_meter(label: str, done: int, total: int) -> str:
    percent = _progress_percent(done, total)
    return (
        "<div class='pipeline-meter'>"
        f"<strong>{_html(label)}</strong>"
        f"<div class='bar' aria-label='{_html(label)} {percent} percent'><span style='width:{percent}%'></span></div>"
        f"<div class='muted'>{done} / {total}</div>"
        "</div>"
    )


def _stage_line(status: str) -> str:
    stages = (
        ("discovered", "Discovered"),
        ("queued", "Queued"),
        ("ingesting", "Text/OCR"),
        ("text_ready", "Ready"),
    )
    order = [stage for stage, _title in stages]
    if status == "missing":
        active_index = 0
    elif status == "failed":
        active_index = min(order.index("ingesting"), len(stages) - 1)
    elif status == "duplicate":
        active_index = len(stages) - 1
    elif status in order:
        active_index = order.index(status)
    elif status == "ready":
        active_index = len(stages) - 1
    else:
        active_index = 0
    dots = []
    for index, (_stage, title) in enumerate(stages):
        css_class = "done" if index < active_index or status in {"duplicate", "ready"} else ""
        if index == active_index and status not in {"duplicate", "ready"}:
            css_class = "error" if status in {"failed", "missing"} else "running"
        if css_class == "done":
            label = "<span class='stage-check' aria-label='done'>✓</span>"
        elif css_class == "running":
            label = "<span class='stage-spinner' aria-label='processing'></span>"
        else:
            label = ""
        dots.append(f"<span class='stage-dot {css_class}' title='{_html(title)}'>{label}</span>")
    return "<div class='stage-line'>" + "".join(dots) + "</div>"


def _library_progress_panel(files: list[LibrarySourceFile]) -> str:
    total = len(files)
    counts = Counter(row.status for row in files)
    discovered = total
    queued_or_later = sum(counts.get(status, 0) for status in ("queued", "ingesting", "text_ready", "ready", "duplicate"))
    text_ready = counts.get("text_ready", 0) + counts.get("ready", 0) + counts.get("duplicate", 0)
    failed = counts.get("failed", 0) + counts.get("missing", 0)
    meters = "".join(
        (
            _pipeline_meter("Discovered", discovered, total),
            _pipeline_meter("Queued", queued_or_later, total),
            _pipeline_meter("Text/OCR ready", text_ready, total),
            _pipeline_meter("Needs attention", failed, total),
        )
    )
    return f"<section class='panel'><h2>Analysis Progress</h2><div class='pipeline-grid'>{meters}</div></section>"


def _job_progress_panel(jobs: list[IngestionJob]) -> str:
    total = len(jobs)
    counts = Counter(job.status for job in jobs)
    active = counts.get("queued", 0) + counts.get("processing", 0)
    done = counts.get("indexed", 0) + counts.get("duplicate", 0)
    failed = counts.get("failed", 0)
    meters = "".join(
        (
            _pipeline_meter("Waiting or processing", active, total),
            _pipeline_meter("Text/OCR indexed", done, total),
            _pipeline_meter("Failed", failed, total),
        )
    )
    return f"<section class='panel'><h2>Recognition And Text Analysis</h2><div class='pipeline-grid'>{meters}</div></section>"


def _project_analysis_progress_panel(session: Session) -> str:
    library_files = list(session.scalars(select(LibrarySourceFile)))
    if library_files:
        return _library_progress_panel(library_files)
    jobs = list(session.scalars(select(IngestionJob)))
    return _job_progress_panel(jobs)


def _library_source_counts(files: list[LibrarySourceFile]) -> Counter[str]:
    return Counter(row.status for row in files)


def _library_source_rows(session: Session, sources: list[LibrarySource]) -> str:
    rows = []
    for source in sources:
        files = list_library_source_files(session, source.id)
        counts = _library_source_counts(files)
        status_class = _library_status_class(source.status)
        error = f"<div class='warn'>{_html(_truncate(source.last_error, 140))}</div>" if source.last_error else ""
        toggle_action = "disable" if source.enabled else "enable"
        toggle_label = "Disable" if source.enabled else "Enable"
        rows.append(
            "<tr>"
            f"<td><a href='/ui/libraries?library_id={_html(source.id)}'>{_html(source.name)}</a>"
            f"<div class='path'>{_html(source.path)}</div></td>"
            f"<td>{_html(source.collection.name if source.collection is not None else source.collection_id)}</td>"
            f"<td><span class='{status_class}'>{_html(source.status)}</span>{error}</td>"
            f"<td>{_html('yes' if source.watch_enabled else 'no')}</td>"
            f"<td>{_html('yes' if source.recursive else 'no')}</td>"
            f"<td class='num'>{sum(counts.values())}</td>"
            f"<td class='num'>{counts.get('ready', 0) + counts.get('text_ready', 0) + counts.get('duplicate', 0)}</td>"
            f"<td class='num'>{counts.get('queued', 0)}</td>"
            f"<td class='num'>{counts.get('failed', 0)}</td>"
            f"<td>{_html(source.last_scan_at)}</td>"
            "<td class='actions'>"
            f"<a href='/ui/articles?library_source_id={_html(source.id)}'>Open Articles</a> "
            f"<a href='/ui/libraries?library_id={_html(source.id)}&file_status=failed'>Open Failed Files</a> "
            f"<form method='post' action='/ui/libraries/{_html(source.id)}/scan'>"
            "<button type='submit'>Scan Now</button></form>"
            f"<form method='post' action='/ui/libraries/{_html(source.id)}/{toggle_action}'>"
            f"<button type='submit'>{toggle_label}</button></form>"
            f"<form method='post' action='/ui/libraries/{_html(source.id)}/delete'>"
            "<button type='submit'>Delete Source</button></form>"
            "</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='11'>No library sources</td></tr>"


def _library_file_rows(files: list[LibrarySourceFile]) -> str:
    rows = []
    for row in files[:200]:
        status_class = _library_status_class(row.status)
        article_link = f"<a href='/ui/articles/{_html(row.article_id)}'>Article</a>" if row.article_id else ""
        job_link = f"<a href='/ingestion/jobs/{_html(row.ingestion_job_id)}'>Job</a>" if row.ingestion_job_id else ""
        links = " ".join(value for value in (article_link, job_link) if value)
        error = f"<div class='warn'>{_html(_truncate(row.last_error, 160))}</div>" if row.last_error else ""
        rows.append(
            "<tr>"
            f"<td>{_html(row.filename)}<div class='path'>{_html(row.relative_path)}</div>{_stage_line(row.status)}</td>"
            f"<td><span class='{status_class}'>{_html(row.status)}</span>{error}</td>"
            f"<td class='num'>{_html(row.file_size_bytes)}</td>"
            f"<td class='path'>{_html(row.content_hash_sha256)}</td>"
            f"<td>{_html(row.last_seen_at)}</td>"
            f"<td>{_html(row.last_ingested_at)}</td>"
            f"<td class='actions'>{links}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='7'>No discovered files</td></tr>"


def _fact_rows(session: Session, facts: list[StructuredFact]) -> str:
    rows = []
    for fact in facts:
        payload = structured_fact_to_response(session, fact)
        article_id = payload.get("article_id")
        source_chunk_id = payload.get("source_chunk_id")
        raw_page_start = payload.get("page_start")
        raw_page_end = payload.get("page_end")
        page_start = raw_page_start if isinstance(raw_page_start, int) else None
        page_end = raw_page_end if isinstance(raw_page_end, int) else None
        value_text = str(payload.get("field_value_text") or "")
        context_query = value_text or str(payload.get("field_name") or "")
        links = []
        if article_id:
            links.append(f"<a href='/ui/articles/{_html(article_id)}'>Article</a>")
        if article_id and source_chunk_id:
            links.append(_context_link(str(article_id), str(source_chunk_id), context_query, "Context"))
        if article_id:
            links.append(_pdf_link(str(article_id), page_start))
        rows.append(
            "<tr>"
            f"<td>{_html(payload.get('field_name'))}<div class='muted'>{_html(payload.get('entity_type'))}</div></td>"
            f"<td>{_html(payload.get('field_value_text'))}</td>"
            f"<td class='num'>{_html(payload.get('field_value_numeric'))}</td>"
            f"<td>{_html(payload.get('unit'))}</td>"
            f"<td>{_html(payload.get('title'))}<div class='muted'>{_html(payload.get('doi'))}</div></td>"
            f"<td class='num'>{_html(_page_range(page_start, page_end))}</td>"
            f"<td>{_html(payload.get('source'))}<div class='muted'>confidence={_html(payload.get('confidence'))}</div></td>"
            f"<td class='actions'>{' '.join(links)}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='8'>No structured facts</td></tr>"


@router.get("/ui/facts", response_class=HTMLResponse)
def structured_facts_page(
    session: SessionDep,
    collection: str = "literature",
    article_id: UUID | None = None,
    field_name: str = "",
    unit: str = "",
    source: str = "",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> HTMLResponse:
    facts = list_structured_facts(
        session,
        collection_name=collection,
        article_id=article_id,
        field_name=field_name,
        unit=unit,
        source=source,
        limit=limit,
    )
    summary = structured_fact_summary(facts)
    collections = list(session.scalars(select(Collection).order_by(Collection.name)))
    collection_options = "".join(
        f"<option value='{_html(row.name)}' {'selected' if row.name == collection else ''}>{_html(row.name)}</option>"
        for row in collections
    )
    by_field_rows = _counter_rows(Counter(cast(dict[str, int], summary.get("by_field", {}))))
    by_unit_rows = _counter_rows(Counter(cast(dict[str, int], summary.get("by_unit", {}))))
    by_source_rows = _counter_rows(Counter(cast(dict[str, int], summary.get("by_source", {}))))
    body = f"""
    <h1>Structured Facts</h1>
    <p class="page-kicker">Derived numeric evidence candidates linked back to chunks and original PDFs.</p>
    <section class="panel">
      <form method="get" action="/ui/facts">
        <label>Collection<br><select name="collection">{collection_options}</select></label>
        <label>Article ID<br><input name="article_id" value="{_html(article_id or '')}" size="36"></label>
        <label>Field<br><input name="field_name" value="{_html(field_name)}" placeholder="conductivity"></label>
        <label>Unit<br><input name="unit" value="{_html(unit)}" placeholder="S cm-1"></label>
        <label>Source<br><input name="source" value="{_html(source)}" placeholder="rule_based_numeric_v1"></label>
        <label>Limit<br><input name="limit" value="{_html(limit)}" size="5"></label>
        <button type="submit">Filter</button>
      </form>
      <p><strong>Rows shown:</strong> {_html(summary.get("count"))}</p>
      {_command_hint('python -m app.ingestion.cli extract-facts --apply')}
    </section>
    <div class="grid">
      <section class="panel"><h2>By Field</h2><table><tr><th>Field</th><th class="num">Facts</th></tr>{by_field_rows}</table></section>
      <section class="panel"><h2>By Unit</h2><table><tr><th>Unit</th><th class="num">Facts</th></tr>{by_unit_rows}</table></section>
      <section class="panel"><h2>By Source</h2><table><tr><th>Source</th><th class="num">Facts</th></tr>{by_source_rows}</table></section>
    </div>
    <h2>Facts</h2>
    <table><tr><th>Field</th><th>Text value</th><th class="num">Numeric</th><th>Unit</th>
    <th>Article</th><th class="num">Pages</th><th>Source</th><th>Links</th></tr>{_fact_rows(session, facts)}</table>
    """
    return _layout("Structured Facts", body)


@router.get("/ui/libraries", response_class=HTMLResponse)
def libraries_page(session: SessionDep, library_id: UUID | None = None, file_status: str = "") -> HTMLResponse:
    sources = list_library_sources(session)
    selected = next((source for source in sources if source.id == library_id), sources[0] if sources else None)
    selected_files = list_library_source_files(session, selected.id, status=file_status or None) if selected is not None else []
    collections = list(session.scalars(select(Collection).order_by(Collection.name)))
    collection_options = "".join(
        f"<option value='{_html(collection.name)}'>{_html(collection.name)}</option>" for collection in collections
    )
    edit_panel = ""
    if selected is not None:
        selected_collection = selected.collection.name if selected.collection is not None else ""
        edit_options = "".join(
            f"<option value='{_html(collection.name)}' {'selected' if collection.name == selected_collection else ''}>"
            f"{_html(collection.name)}</option>"
            for collection in collections
        )
        edit_panel = f"""
        <section class="panel">
          <h2>Edit Selected Library</h2>
          <form method="post" action="/ui/libraries/{_html(selected.id)}">
            <label>Name<br><input name="name" required value="{_html(selected.name)}"></label>
            <label>Folder path<br><input name="path" required class="path" size="48" value="{_html(selected.path)}"></label>
            <button type="button" data-folder-picker>Browse Folder</button>
            <label>Collection<br><select name="collection">{edit_options}</select></label>
            <label>Enabled<br><select name="enabled">
              <option value="true" {'selected' if selected.enabled else ''}>yes</option>
              <option value="false" {'selected' if not selected.enabled else ''}>no</option>
            </select></label>
            <label>Watch<br><select name="watch_enabled">
              <option value="true" {'selected' if selected.watch_enabled else ''}>yes</option>
              <option value="false" {'selected' if not selected.watch_enabled else ''}>no</option>
            </select></label>
            <label>Recursive<br><select name="recursive">
              <option value="true" {'selected' if selected.recursive else ''}>yes</option>
              <option value="false" {'selected' if not selected.recursive else ''}>no</option>
            </select></label>
            <button type="submit">Save Library</button>
          </form>
        </section>
        """
    selection_script = _remember_library_script(selected) if selected is not None else ""
    body = f"""
    <h1>Libraries</h1>
    <p class="page-kicker">Persistent local PDF folders, discovered files, and ingestion queue status.</p>
    {_library_progress_panel(selected_files)}
    <section class="panel">
      <form method="post" action="/ui/libraries">
        <label>Name<br><input name="name" required></label>
        <label>Folder path<br><input name="path" required class="path" size="48"></label>
        <button type="button" data-folder-picker>Browse Folder</button>
        <label>Collection<br><select name="collection">{collection_options}</select></label>
        <label>Recursive<br><select name="recursive">
          <option value="true" selected>yes</option>
          <option value="false">no</option>
        </select></label>
        <button type="submit">Add Library</button>
      </form>
    </section>
    {edit_panel}
    <h2>Library Sources</h2>
    <table><tr><th>Library</th><th>Collection</th><th>Status</th><th>Watch</th><th>Recursive</th>
    <th class="num">PDFs</th><th class="num">Ready</th><th class="num">Queued</th><th class="num">Failed</th>
    <th>Last scan</th><th>Actions</th></tr>{_library_source_rows(session, sources)}</table>
    <h2>Files{f': {_html(selected.name)}' if selected is not None else ''}{f' / {_html(file_status)}' if file_status else ''}</h2>
    <table><tr><th>File</th><th>Status</th><th class="num">Bytes</th><th>SHA-256</th>
    <th>Last seen</th><th>Last ingested</th><th>Links</th></tr>{_library_file_rows(selected_files)}</table>
    {selection_script}
    {_folder_picker_script()}
    {_library_auto_refresh_script(selected_files)}
    """
    response = _layout("Libraries", body)
    if selected is not None:
        response.set_cookie("ariadne_library_id", str(selected.id), httponly=False, samesite="lax")
    return response


def _remember_library_script(source: LibrarySource) -> str:
    item_json = json.dumps({"id": str(source.id), "name": source.name}, ensure_ascii=False)
    return f"""
    <script>
    (() => {{
      const item = {item_json};
      const key = 'ariadne:selectedLibraries';
      const currentKey = 'ariadne:currentLibrary';
      let items = [];
      try {{ items = JSON.parse(sessionStorage.getItem(key) || '[]'); }} catch (_) {{ items = []; }}
      items = [...items.filter((value) => value.id !== item.id), item].slice(-12);
      sessionStorage.setItem(key, JSON.stringify(items));
      sessionStorage.setItem(currentKey, JSON.stringify(item));
      document.cookie = 'ariadne_library_id=' + encodeURIComponent(item.id) + '; path=/; samesite=lax';
      const label = document.querySelector('[data-current-library]');
      if (label) label.textContent = item.name;
    }})();
    </script>
    """


def _folder_picker_script() -> str:
    return """
    <script>
    (() => {
      document.querySelectorAll('[data-folder-picker]').forEach((button) => {
        button.addEventListener('click', async () => {
          const form = button.closest('form');
          const input = form ? form.querySelector('input[name="path"]') : null;
          if (!input) return;
          button.disabled = true;
          try {
            const body = new URLSearchParams();
            body.set('initial_path', input.value || '');
            const response = await fetch('/ui/pick-folder', {
              method: 'POST',
              headers: {'Content-Type': 'application/x-www-form-urlencoded'},
              body
            });
            if (!response.ok) return;
            const payload = await response.json();
            if (payload.path) input.value = payload.path;
          } finally {
            button.disabled = false;
          }
        });
      });
    })();
    </script>
    """


def _library_auto_refresh_script(files: list[LibrarySourceFile]) -> str:
    if not any(row.status in {"discovered", "queued", "ingesting", "embedding"} for row in files):
        return ""
    return """
    <script>
    window.setTimeout(() => {
      window.location.reload();
    }, 3000);
    </script>
    """


def _pick_local_directory(initial_path: str = "") -> str | None:
    import tkinter as tk
    from tkinter import TclError, filedialog

    initial = initial_path.strip()
    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            initialdir=initial or None,
            mustexist=True,
            title="Select Library Folder",
        )
    except TclError as exc:
        raise RuntimeError("Local folder picker is unavailable") from exc
    finally:
        root.destroy()
    return selected or None


@router.post("/ui/pick-folder")
def pick_folder_action(initial_path: Annotated[str, Form()] = "") -> dict[str, object]:
    try:
        return {"path": _pick_local_directory(initial_path)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ui/libraries")
def create_library_action(
    session: SessionDep,
    name: Annotated[str, Form()],
    path: Annotated[str, Form()],
    collection: Annotated[str, Form()] = "literature",
    recursive: Annotated[bool, Form()] = True,
) -> RedirectResponse:
    try:
        source = create_library_source(
            session,
            get_settings(),
            name=name,
            path=path,
            collection_name=collection,
            recursive=recursive,
        )
    except DuplicateLibrarySourceError as exc:
        response = RedirectResponse(f"/ui/libraries?library_id={exc.source.id}", status_code=303)
        response.set_cookie("ariadne_library_id", str(exc.source.id), httponly=False, samesite="lax")
        return response
    except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    response = RedirectResponse(f"/ui/libraries?library_id={source.id}", status_code=303)
    response.set_cookie("ariadne_library_id", str(source.id), httponly=False, samesite="lax")
    return response


@router.post("/ui/libraries/{library_id}")
def update_library_action(
    session: SessionDep,
    library_id: UUID,
    name: Annotated[str, Form()],
    path: Annotated[str, Form()],
    collection: Annotated[str, Form()],
    enabled: Annotated[bool, Form()],
    watch_enabled: Annotated[bool, Form()],
    recursive: Annotated[bool, Form()],
) -> RedirectResponse:
    try:
        update_library_source(
            session,
            get_settings(),
            library_id,
            name=name,
            path=path,
            collection_name=collection,
            enabled=enabled,
            watch_enabled=watch_enabled,
            recursive=recursive,
        )
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Unknown library source") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    response = RedirectResponse(f"/ui/libraries?library_id={library_id}", status_code=303)
    response.set_cookie("ariadne_library_id", str(library_id), httponly=False, samesite="lax")
    return response


@router.post("/ui/libraries/{library_id}/enable")
def enable_library_action(session: SessionDep, library_id: UUID) -> RedirectResponse:
    return _set_library_enabled(session, library_id, enabled=True)


@router.post("/ui/libraries/{library_id}/disable")
def disable_library_action(session: SessionDep, library_id: UUID) -> RedirectResponse:
    return _set_library_enabled(session, library_id, enabled=False)


def _set_library_enabled(session: Session, library_id: UUID, *, enabled: bool) -> RedirectResponse:
    try:
        update_library_source(session, get_settings(), library_id, enabled=enabled)
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Unknown library source") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    response = RedirectResponse(f"/ui/libraries?library_id={library_id}", status_code=303)
    response.set_cookie("ariadne_library_id", str(library_id), httponly=False, samesite="lax")
    return response


@router.post("/ui/libraries/{library_id}/delete")
def delete_library_action(session: SessionDep, library_id: UUID) -> RedirectResponse:
    try:
        delete_library_source(session, library_id)
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Unknown library source") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    session.commit()
    return RedirectResponse("/ui/libraries", status_code=303)


@router.post("/ui/libraries/{library_id}/scan")
def scan_library_action(session: SessionDep, library_id: UUID) -> RedirectResponse:
    try:
        scan_and_queue_library_source(session, get_settings(), library_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    response = RedirectResponse(f"/ui/libraries?library_id={library_id}", status_code=303)
    response.set_cookie("ariadne_library_id", str(library_id), httponly=False, samesite="lax")
    return response


@router.get("/ui/ingestion", response_class=HTMLResponse)
def ingestion_page(session: SessionDep, show: str = "uploads") -> HTMLResponse:
    settings = get_settings()
    collections = list(session.scalars(select(Collection).order_by(Collection.name)))
    collection_options = "".join(
        f"<option value='{_html(collection.name)}'>{_html(collection.name)}</option>" for collection in collections
    )
    statement = select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(50)
    if show == "uploads":
        statement = statement.where(IngestionJob.original_filename.is_not(None))
    elif show == "failed":
        statement = statement.where(IngestionJob.status == "failed")
    elif show != "all":
        show = "uploads"
        statement = statement.where(IngestionJob.original_filename.is_not(None))
    jobs = list(session.scalars(statement))
    progress_panel = _job_progress_panel(jobs)
    rows = []
    for job in jobs:
        payload = job_to_response(job)
        article_id = payload.get("article_id")
        links = ""
        if isinstance(article_id, str):
            links = (
                f"<a href='/ui/articles/{_html(article_id)}'>Article</a> "
                f"<a href='{_html(build_pdf_url(article_id, 'original'))}' target='_blank' rel='noopener'>PDF</a>"
            )
        error = ""
        if payload.get("error_type") or payload.get("error_message"):
            error_prefix = f"{_html(payload.get('error_type'))}: " if payload.get("error_type") else ""
            error = (
                f"<div class='warn'>{error_prefix}{_html(_truncate(str(payload.get('error_message') or ''), 160))}</div>"
            )
        filename = job.original_filename or "(legacy CLI job)"
        rows.append(
            "<tr>"
            f"<td>{_html(filename)}</td>"
            f"<td>{_html(job.status)}</td>"
            f"<td class='num'>{job.attempt_count}</td>"
            f"<td>{_html(job.created_at)}</td>"
            f"<td>{links}{error}</td>"
            "</tr>"
        )
    table_rows = "".join(rows) or "<tr><td colspan='5'>No jobs for this filter</td></tr>"
    filters = " ".join(
        [
            f"<strong>{_html(label)}</strong>" if show == value else f"<a href='/ui/ingestion?show={value}'>{_html(label)}</a>"
            for value, label in (("uploads", "Upload jobs"), ("failed", "Failed"), ("all", "All legacy jobs"))
        ]
    )
    body = f"""
    <h1>Ingestion</h1>
    {progress_panel}
    <section class="panel">
      <form method="post" action="/ingestion/uploads" enctype="multipart/form-data">
        <label>Collection<br><select name="collection">{collection_options}</select></label>
        <label>PDF files<br><input name="files" type="file" accept="application/pdf,.pdf" multiple></label>
        <button type="submit">Upload</button>
      </form>
      <p class="muted">Limits: up to {settings.upload_max_files_per_request} files per request,
      {settings.upload_max_file_size_mb} MB per file. Indexed means PostgreSQL is updated; rebuild semantic/vector index manually.</p>
    </section>
    <h2>Recent Jobs</h2>
    <p class="actions">{filters}</p>
    <table><tr><th>Filename</th><th>Status</th><th class="num">Attempts</th><th>Created</th><th>Result</th></tr>{table_rows}</table>
    """
    return _layout("Ingestion", body)


def _article_tag_summary(tags: list[ArticleTag]) -> str:
    grouped: dict[str, list[str]] = defaultdict(list)
    for tag in tags:
        grouped[tag.tag_type].append(tag.tag_value)
    return " ".join(
        f"<span class='tag'>{_html(tag_type)}: {_html(', '.join(sorted(set(values))[:6]))}</span>"
        for tag_type, values in sorted(grouped.items())
    )


@router.get("/ui/articles", response_class=HTMLResponse)
def article_list(session: SessionDep, library_source_id: UUID | None = None) -> HTMLResponse:
    statement = select(Article)
    if library_source_id is not None:
        statement = statement.where(
            Article.id.in_(
                select(LibrarySourceFile.article_id)
                .where(LibrarySourceFile.library_source_id == library_source_id)
                .where(LibrarySourceFile.article_id.is_not(None))
            )
        )
    articles = list(session.scalars(statement.order_by(Article.title)))
    rows = []
    for article in articles:
        tags = list(
            session.scalars(
                select(ArticleTag).where(ArticleTag.article_id == article.id).order_by(ArticleTag.tag_type, ArticleTag.tag_value)
            )
        )
        page_layers = _counter_from_rows(
            session.execute(
                select(Page.selected_text_layer, func.count()).where(Page.article_id == article.id).group_by(Page.selected_text_layer)
            ).all()
        )
        page_count = session.scalar(select(func.count()).select_from(Page).where(Page.article_id == article.id)) or 0
        chunk_count = session.scalar(select(func.count()).select_from(Chunk).where(Chunk.article_id == article.id)) or 0
        rows.append(
            "<tr>"
            f"<td><a href='/ui/articles/{article.id}'>{_html(article.title)}</a><div class='muted'>{_html(article.doi)}</div></td>"
            f"<td class='num'>{page_count}</td><td class='num'>{chunk_count}</td>"
            f"<td>{_html(dict(page_layers))}</td>"
            f"<td>{_article_tag_summary(tags)}</td>"
            "</tr>"
        )
    table_rows = "".join(rows) or "<tr><td colspan=5>No articles</td></tr>"
    body = (
        "<h1>Articles</h1><table><tr><th>Article</th><th class='num'>Pages</th>"
        f"<th class='num'>Chunks</th><th>Selected layers</th><th>Tags</th></tr>{table_rows}</table>"
    )
    return _layout("Articles", body)


def _get_article_or_404(session: Session, article_id: UUID) -> Article:
    article = session.scalar(select(Article).where(Article.id == article_id))
    if article is None:
        raise HTTPException(status_code=404, detail=f"Unknown article: {article_id}")
    return article


@router.get("/ui/articles/{article_id}", response_class=HTMLResponse)
def article_detail(session: SessionDep, article_id: UUID) -> HTMLResponse:
    article = _get_article_or_404(session, article_id)
    tags = list(
        session.scalars(select(ArticleTag).where(ArticleTag.article_id == article.id).order_by(ArticleTag.tag_type, ArticleTag.tag_value))
    )
    sections = list(
        session.scalars(select(Section).where(Section.article_id == article.id).order_by(Section.page_start, Section.normalized_name))
    )
    chunks = list(session.scalars(select(Chunk).where(Chunk.article_id == article.id).order_by(Chunk.chunk_index)))
    page_layers = _counter_from_rows(
        session.execute(
            select(Page.selected_text_layer, func.count()).where(Page.article_id == article.id).group_by(Page.selected_text_layer)
        ).all()
    )
    section_rows = "".join(
        f"<tr><td>{_html(section.normalized_name)}</td><td>{_html(section.name)}</td>"
        f"<td class='num'>{_html(section.page_start)}-{_html(section.page_end)}</td>"
        f"<td>{_html(section.source_type)}</td></tr>"
        for section in sections
    )
    chunk_rows = "".join(
        f"<tr><td class='num'>{chunk.chunk_index}</td>"
        f"<td class='num'>{_pdf_link(article.id, chunk.page_start, _page_range(chunk.page_start, chunk.page_end))}</td>"
        f"<td>{_html(chunk.source_type)}</td><td>{_html(chunk.text_layer)}</td>"
        f"<td>{_html(_truncate(chunk.text))}</td></tr>"
        for chunk in chunks
    )
    selected_layer_text = _html(dict(page_layers))
    empty_sections = "<tr><td colspan=4>No sections</td></tr>"
    empty_chunks = "<tr><td colspan=5>No chunks</td></tr>"
    metadata_row = (
        f"<p><strong>DOI:</strong> {_html(article.doi)} &nbsp; "
        f"<strong>Status:</strong> {_html(article.status)} &nbsp; "
        f"<strong>Selected layers:</strong> {selected_layer_text}</p>"
    )
    pdf_actions = (
        f"<p class='actions'>{_pdf_link(article.id, label='Open original PDF')}"
        f"{' ' + _ocr_pdf_link(article.id) if article.pdf_ocr_path else ''}</p>"
    )
    sections_table = (
        "<h2>Sections</h2><table><tr><th>Normalized</th><th>Name</th>"
        f'<th class="num">Pages</th><th>Type</th></tr>{section_rows or empty_sections}</table>'
    )
    chunks_table = (
        '<h2>Chunks</h2><table><tr><th class="num">#</th><th class="num">Pages</th>'
        f"<th>Source type</th><th>Text layer</th><th>Snippet</th></tr>{chunk_rows or empty_chunks}</table>"
    )
    body = f"""
    <h1>{_html(article.title)}</h1>
    <section class="panel">
      {metadata_row}
      {pdf_actions}
      <p><strong>Original PDF:</strong> <span class="path">{_html(article.pdf_original_path)}</span></p>
      <p><strong>OCR PDF:</strong> <span class="path">{_html(article.pdf_ocr_path)}</span></p>
      <p><a href="/ui/articles/{article.id}/text-layers">Inspect page text layers</a></p>
    </section>
    <h2>Tags</h2><div class="panel">{_article_tag_summary(tags) or '<span class="muted">No tags</span>'}</div>
    {sections_table}
    {chunks_table}
    """
    return _layout("Article", body)


@router.get("/ui/articles/{article_id}/text-layers", response_class=HTMLResponse)
def article_text_layers(session: SessionDep, article_id: UUID) -> HTMLResponse:
    article = _get_article_or_404(session, article_id)
    selected = dict(
        cast(
            list[tuple[int, str]],
            session.execute(select(Page.page_number, Page.selected_text_layer).where(Page.article_id == article.id)).all(),
        )
    )
    layers = list(
        session.scalars(
            select(PageTextLayer)
            .where(PageTextLayer.article_id == article.id)
            .order_by(PageTextLayer.page_number, PageTextLayer.layer_type)
        )
    )
    layer_rows = []
    for layer in layers:
        usable = "<span class=ok>yes</span>" if layer.has_usable_text else "<span class=warn>no</span>"
        selected_marker = "<span class=ok>selected</span>" if selected.get(layer.page_number) == layer.layer_type else ""
        layer_rows.append(
            f"<tr><td class='num'>{layer.page_number}</td><td>{_html(layer.layer_type)}</td>"
            f"<td>{usable}</td><td class='num'>{float(layer.quality_score):.3f}</td>"
            f"<td>{selected_marker}</td><td class='path'>{_html(layer.source_pdf_path)}</td></tr>"
        )
    rows = "".join(layer_rows) or "<tr><td colspan=6>No text layers</td></tr>"
    body = (
        f"<h1>Text Layers: {_html(article.title)}</h1><p><a href='/ui/articles/{article.id}'>Back to article</a></p>"
        "<table><tr><th class='num'>Page</th><th>Layer</th><th>Usable</th>"
        f"<th class='num'>Quality</th><th>Selected</th><th>Source PDF</th></tr>{rows}</table>"
    )
    return _layout("Text Layers", body)


def _latest_report(data_root: Path, pattern: str) -> Path | None:
    export_dir = data_root / "exports"
    if not export_dir.exists():
        return None
    reports = sorted(export_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def _latest_standard_retrieval_report(data_root: Path) -> Path | None:
    export_dir = data_root / "exports"
    if not export_dir.exists():
        return None
    reports = [
        path
        for path in export_dir.glob("retrieval_eval_*.json")
        if not path.name.startswith("retrieval_eval_extended_")
    ]
    return sorted(reports, key=lambda path: path.stat().st_mtime, reverse=True)[0] if reports else None


def _latest_extended_retrieval_report(data_root: Path) -> Path | None:
    return _latest_report(data_root, "retrieval_eval_extended_*.json")


def _result_rows(results: list[object]) -> str:
    rows = []
    for result in results:
        if not isinstance(result, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{_html(result.get('title'))}<div class='muted'>{_html(result.get('doi'))}</div></td>"
            f"<td class='num'>{_html(result.get('page_start'))}-{_html(result.get('page_end'))}</td>"
            f"<td class='num'>{_html(result.get('score'))}</td>"
            f"<td>{_html(result.get('retrieval_method'))}</td>"
            f"<td>{_html(_truncate(str(result.get('snippet') or ''), 320))}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='5'>No results</td></tr>"


def _counter_rows_from_mapping(value: object) -> str:
    if not isinstance(value, dict):
        return _counter_rows(Counter())
    return _counter_rows(Counter({str(key): int(count) for key, count in value.items() if isinstance(count, int)}))


def _mapping_rows(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return "<tr><td colspan='2'>No data</td></tr>"
    return "".join(f"<tr><td>{_html(key)}</td><td>{_html(item)}</td></tr>" for key, item in sorted(value.items()))


def _text_quality_page_rows(pages: object, query: str = "") -> str:
    if not isinstance(pages, list):
        return "<tr><td colspan='6'>No data</td></tr>"
    rows = []
    for page in pages[:100]:
        if not isinstance(page, dict):
            continue
        article_id = page.get("article_id")
        page_number = page.get("page_number")
        page_int = page_number if isinstance(page_number, int) else None
        reasons = page.get("reasons", [])
        reason_text = ", ".join(str(reason) for reason in reasons) if isinstance(reasons, list) else ""
        links = []
        if article_id and page_int is not None:
            highlight = f"&highlight_query={_html(query)}" if query else ""
            links.append(
                f"<a href='/ui/articles/{_html(article_id)}/pages/context?page_start={page_int}&page_end={page_int}&layer=selected"
                f"{highlight}'>Page text</a>"
            )
            links.append(_pdf_link(str(article_id), page_int))
        title = _html(page.get("title"))
        article_cell = f"<a href='/ui/articles/{_html(article_id)}'>{title}</a>" if article_id else title
        rows.append(
            "<tr>"
            f"<td>{article_cell}"
            f"<div class='muted'>{_html(page.get('doi'))}</div></td>"
            f"<td class='num'>{_html(page_number)}</td>"
            f"<td>{_html(reason_text)}</td>"
            f"<td>{_html(page.get('selected_text_layer'))}</td>"
            f"<td class='num'>{_html(page.get('selected_char_count'))}</td>"
            f"<td class='actions'>{' '.join(links)}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='6'>No pages</td></tr>"


def _bool_label(value: object) -> str:
    if value is None:
        return "unknown"
    return "yes" if bool(value) else "no"


def _extended_breakdown_rows(groups: object) -> str:
    if not isinstance(groups, dict) or not groups:
        return "<tr><td colspan='7'>No breakdown data</td></tr>"
    rows = []
    for key, payload in sorted(groups.items()):
        if not isinstance(payload, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{_html(key)}</td>"
            f"<td class='num'>{_html(payload.get('total'))}</td>"
            f"<td class='num'>{_html(payload.get('passed'))}</td>"
            f"<td class='num'>{_html(payload.get('article_recall_at_k'))}</td>"
            f"<td class='num'>{_html(payload.get('mrr'))}</td>"
            f"<td class='num'>{_html(payload.get('top_1_passed'))}</td>"
            f"<td class='num'>{_html(payload.get('mean_rank'))}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='7'>No breakdown data</td></tr>"


def _missing_expected_count(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


@router.get("/ui/reports/retrieval", response_class=HTMLResponse)
def retrieval_report_page() -> HTMLResponse:
    settings = get_settings()
    report_path = _latest_standard_retrieval_report(settings.data_root)
    if report_path is None:
        command = "python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10"
        body = (
            f"<h1>Retrieval Evaluation Report</h1><p class='warn'>No retrieval evaluation report generated yet.</p>{_command_hint(command)}"
        )
        return _layout("Retrieval Evaluation Report", body)

    payload: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    settings_payload = payload.get("settings", {})
    questions = payload.get("questions", [])
    question_sections = []
    if isinstance(questions, list):
        for question in questions:
            if not isinstance(question, dict):
                continue
            status_class = "ok" if question.get("passed") else "warn"
            missing_dois = ", ".join(str(item) for item in question.get("missing_article_dois", []))
            missing_titles = ", ".join(str(item) for item in question.get("missing_article_titles", []))
            missing_checksums = ", ".join(str(item) for item in question.get("missing_article_checksums", []))
            missing_keywords = ", ".join(str(item) for item in question.get("missing_keywords", []))
            trace_complete = question.get("evidence_trace_complete")
            trace_label = "unknown" if trace_complete is None else ("yes" if trace_complete else "no")
            rank = question.get("rank_of_expected", question.get("rank_of_first_relevant"))
            results = question.get("results", [])
            result_rows = _result_rows(results if isinstance(results, list) else [])
            question_sections.append(
                f"<h2>{_html(question.get('id'))}: {_html(question.get('query'))}</h2>"
                "<section class='panel'>"
                f"<p><strong>Status:</strong> <span class='{status_class}'>"
                f"{_html('PASS' if question.get('passed') else 'FAIL')}</span> "
                f"<strong>Results:</strong> {_html(question.get('result_count'))} &nbsp; "
                f"<strong>Rank:</strong> {_html(rank if rank is not None else 'none')} &nbsp; "
                f"<strong>Top-1:</strong> {_html('yes' if question.get('top_1_passed') else 'no')} &nbsp; "
                f"<strong>Recall@k:</strong> {_html(question.get('recall_at_k', question.get('article_recall_at_k')))} &nbsp; "
                f"<strong>Trace complete:</strong> {_html(trace_label)}</p>"
                f"<p><strong>Missing DOI:</strong> {_html(missing_dois or 'none')} &nbsp; "
                f"<strong>Missing title:</strong> {_html(missing_titles or 'none')} &nbsp; "
                f"<strong>Missing checksum:</strong> {_html(missing_checksums or 'none')} &nbsp; "
                f"<strong>Missing keywords:</strong> {_html(missing_keywords or 'none')}</p>"
                "</section>"
                "<table><tr><th>Article</th><th class='num'>Pages</th>"
                "<th class='num'>Score</th><th>Method</th><th>Snippet</th></tr>"
                f"{result_rows}</table>"
            )
    summary_rows = (
        f'<td class="num">{_html(summary.get("total"))}</td>'
        f'<td class="num">{_html(summary.get("passed"))}</td>'
        f'<td class="num">{_html(summary.get("top_1_passed"))}</td>'
        f'<td class="num">{_html(summary.get("failed"))}</td>'
        f'<td class="num">{_html(summary.get("recall_at_k", summary.get("article_recall_at_k")))}</td>'
        f'<td class="num">{_html(summary.get("mean_rank"))}</td>'
        f'<td class="num">{_html(summary.get("empty_result_queries"))}</td>'
    )
    method = _html(settings_payload.get("retrieval_method"))
    body = f"""
    <h1>Retrieval Evaluation Report</h1>
    <section class="panel">
      <p><strong>Path:</strong> <span class="path">{_html(report_path)}</span></p>
      <p><strong>Created:</strong> {_html(payload.get("created_at"))} &nbsp; <strong>Method:</strong> {method}</p>
      <table><tr><th>Total</th><th>Passed</th><th>Top-1 passed</th><th>Failed</th>
      <th>Recall@k</th><th>Mean rank</th><th>Empty result queries</th></tr><tr>{summary_rows}</tr></table>
    </section>
    {"".join(question_sections) or '<p class="warn">Report has no readable questions.</p>'}
    """
    return _layout("Retrieval Evaluation Report", body)


@router.get("/ui/reports/retrieval-extended", response_class=HTMLResponse)
def extended_retrieval_report_page() -> HTMLResponse:
    settings = get_settings()
    report_path = _latest_extended_retrieval_report(settings.data_root)
    if report_path is None:
        command = "python -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --top-k 10 --method exact"
        body = (
            "<h1>Extended Retrieval Evaluation Report</h1>"
            "<p class='warn'>No extended retrieval evaluation report generated yet.</p>"
            f"{_command_hint(command)}"
        )
        return _layout("Extended Retrieval Evaluation Report", body)

    payload: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    settings_payload = payload.get("settings", {})
    summary_rows = (
        f'<tr><td>Total</td><td class="num">{_html(summary.get("total"))}</td></tr>'
        f'<tr><td>Answerable</td><td class="num">{_html(summary.get("answerable"))}</td></tr>'
        f'<tr><td>Unanswerable</td><td class="num">{_html(summary.get("unanswerable"))}</td></tr>'
        f'<tr><td>Passed</td><td class="num">{_html(summary.get("passed"))}</td></tr>'
        f'<tr><td>Failed</td><td class="num">{_html(summary.get("failed"))}</td></tr>'
        f'<tr><td>Article recall@k</td><td class="num">{_html(summary.get("article_recall_at_k"))}</td></tr>'
        f'<tr><td>Chunk recall@k</td><td class="num">{_html(summary.get("chunk_recall_at_k"))}</td></tr>'
        f'<tr><td>MRR</td><td class="num">{_html(summary.get("mrr"))}</td></tr>'
        f'<tr><td>NDCG@k</td><td class="num">{_html(summary.get("ndcg_at_k"))}</td></tr>'
        f'<tr><td>Top-1 passed</td><td class="num">{_html(summary.get("top_1_passed"))}</td></tr>'
        f'<tr><td>Mean rank</td><td class="num">{_html(summary.get("mean_rank"))}</td></tr>'
        f'<tr><td>False answerable</td><td class="num">{_html(summary.get("false_answerable"))}</td></tr>'
        f'<tr><td>Evidence trace complete</td><td class="num">{_html(_bool_label(summary.get("evidence_trace_complete")))}</td></tr>'
        f'<tr><td>P95 latency ms</td><td class="num">{_html(summary.get("p95_latency_ms"))}</td></tr>'
    )
    breakdown_header = (
        "<tr><th>Group</th><th class='num'>Total</th><th class='num'>Passed</th>"
        "<th class='num'>Article recall@k</th><th class='num'>MRR</th>"
        "<th class='num'>Top-1</th><th class='num'>Mean rank</th></tr>"
    )
    question_rows = []
    questions = payload.get("questions", [])
    if isinstance(questions, list):
        for question in questions:
            if not isinstance(question, dict):
                continue
            status_class = "ok" if question.get("passed") else "warn"
            question_rows.append(
                "<tr>"
                f"<td>{_html(question.get('id'))}<div class='muted'>{_html(question.get('query'))}</div></td>"
                f"<td>{_html(question.get('language') or 'unspecified')}</td>"
                f"<td>{_html(question.get('category') or 'unspecified')}</td>"
                f"<td><span class='{status_class}'>{_html('PASS' if question.get('passed') else 'FAIL')}</span></td>"
                f"<td class='num'>{_html(question.get('rank_of_first_relevant'))}</td>"
                f"<td class='num'>{_html(question.get('article_recall_at_k'))}</td>"
                f"<td class='num'>{_html(question.get('mrr'))}</td>"
                f"<td class='num'>{_html(question.get('ndcg_at_k'))}</td>"
                f"<td class='num'>{_html(_missing_expected_count(question.get('missing_expected_articles')))}</td>"
                f"<td class='num'>{_html(_missing_expected_count(question.get('missing_expected_chunks')))}</td>"
                f"<td>{_html(_bool_label(question.get('evidence_trace_complete')))}</td>"
                "</tr>"
            )
    question_rows_html = "".join(question_rows) or "<tr><td colspan='11'>No readable questions</td></tr>"
    method = _html(settings_payload.get("retrieval_method") or settings_payload.get("method"))
    body = f"""
    <h1>Extended Retrieval Evaluation Report</h1>
    <section class="panel">
      <p><strong>Path:</strong> <span class="path">{_html(report_path)}</span></p>
      <p><strong>Created:</strong> {_html(payload.get("created_at"))} &nbsp; <strong>Method:</strong> {method}</p>
      <table><tr><th>Metric</th><th class="num">Value</th></tr>{summary_rows}</table>
    </section>
    <div class="grid">
      <section class="panel"><h2>By Language</h2>
      <table>{breakdown_header}{_extended_breakdown_rows(summary.get("by_language"))}</table></section>
      <section class="panel"><h2>By Category</h2>
      <table>{breakdown_header}{_extended_breakdown_rows(summary.get("by_category"))}</table></section>
    </div>
    <h2>Questions</h2>
    <table><tr><th>Question</th><th>Language</th><th>Category</th><th>Status</th>
    <th class="num">Rank</th><th class="num">Article recall@k</th><th class="num">MRR</th>
    <th class="num">NDCG@k</th><th class="num">Missing articles</th><th class="num">Missing chunks</th>
    <th>Trace</th></tr>{question_rows_html}</table>
    """
    return _layout("Extended Retrieval Evaluation Report", body)


@router.get("/ui/reports/text-quality", response_class=HTMLResponse)
def text_quality_report_page() -> HTMLResponse:
    settings = get_settings()
    report_path = _latest_report(settings.data_root, "text_quality_report_*.json")
    if report_path is None:
        body = (
            "<h1>Text Quality Report</h1><p class='warn'>No text quality report generated yet.</p>"
            f"{_command_hint('python -m app.ingestion.cli text-quality-report')}"
        )
        return _layout("Text Quality Report", body)

    payload: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    suspicious_pages = payload.get("suspicious_pages", [])
    reason_counter = Counter[str]()
    if isinstance(suspicious_pages, list):
        for page in suspicious_pages:
            if isinstance(page, dict) and isinstance(page.get("reasons"), list):
                reason_counter.update(str(reason) for reason in page["reasons"])
    ocr = payload.get("ocr_diagnostics", {})
    ocr_rows = _mapping_rows(ocr)
    summary_rows = (
        f"<tr><td>Articles</td><td class='num'>{_html(payload.get('article_count'))}</td></tr>"
        f"<tr><td>Pages</td><td class='num'>{_html(payload.get('page_count'))}</td></tr>"
        f"<tr><td>Empty original pages</td><td class='num'>{_html(payload.get('empty_original_page_count'))}</td></tr>"
        f"<tr><td>Short original pages</td><td class='num'>{_html(payload.get('short_original_page_count'))}</td></tr>"
        f"<tr><td>Suspicious pages</td><td class='num'>{_html(payload.get('suspicious_page_count'))}</td></tr>"
        f"<tr><td>OCR used pages</td><td class='num'>{_html(payload.get('ocr_used_pages'))}</td></tr>"
        f"<tr><td>OCR available pages</td><td class='num'>{_html(payload.get('ocr_available_pages'))}</td></tr>"
    )
    reasons_panel = (
        '<section class="panel"><h2>Suspicious Reasons</h2><table>'
        '<tr><th>Reason</th><th class="num">Pages</th></tr>'
        f"{_counter_rows(reason_counter)}</table></section>"
    )
    source_panel = (
        '<section class="panel"><h2>Chunk Source Types</h2><table>'
        '<tr><th>Type</th><th class="num">Chunks</th></tr>'
        f"{_counter_rows_from_mapping(payload.get('source_type_distribution'))}</table></section>"
    )
    text_layer_panel = (
        '<section class="panel"><h2>Chunk Text Layers</h2><table>'
        '<tr><th>Layer</th><th class="num">Chunks</th></tr>'
        f"{_counter_rows_from_mapping(payload.get('text_layer_distribution'))}</table></section>"
    )
    selected_layer_panel = (
        '<section class="panel"><h2>Selected Page Layers</h2><table>'
        '<tr><th>Layer</th><th class="num">Pages</th></tr>'
        f"{_counter_rows_from_mapping(payload.get('selected_text_layer_distribution'))}</table></section>"
    )
    ocr_panel = (
        '<section class="panel"><h2>OCR Diagnostics</h2><table>'
        f"<tr><th>Field</th><th>Value</th></tr>{ocr_rows}</table></section>"
    )
    suspicious_rows = _text_quality_page_rows(suspicious_pages)
    body = f"""
    <h1>Text Quality Report</h1>
    <section class="panel">
      <p><strong>Path:</strong> <span class="path">{_html(report_path)}</span></p>
      <p><strong>Created:</strong> {_html(payload.get("created_at"))} &nbsp;
      <strong>Collection:</strong> {_html(payload.get("collection"))}</p>
      <table><tr><th>Metric</th><th class="num">Value</th></tr>{summary_rows}</table>
    </section>
    <div class="grid">
      {reasons_panel}
      {source_panel}
      {text_layer_panel}
      {selected_layer_panel}
      {ocr_panel}
    </div>
    <h2>Suspicious Pages</h2>
    <table><tr><th>Article</th><th class="num">Page</th><th>Reasons</th><th>Selected layer</th>
    <th class="num">Chars</th><th>Links</th></tr>{suspicious_rows}</table>
    """
    return _layout("Text Quality Report", body)


@router.get("/ui/reports/classification", response_class=HTMLResponse)
def classification_report_page() -> HTMLResponse:
    settings = get_settings()
    report_path = _latest_report(settings.data_root, "classification_report_*.json")
    if report_path is None:
        body = (
            "<h1>Classification Report</h1><p class='warn'>No classification report generated yet.</p>"
            f"{_command_hint('python -m app.classification.cli report --collection literature')}"
        )
        return _layout("Classification Report", body)
    payload: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    tables = "".join(
        f"<section class='panel'><h2>{_html(key)}</h2><table>"
        f"<tr><th>Value</th><th class='num'>Count</th></tr>"
        f"{_counter_rows(Counter(value)) if isinstance(value, dict) else f'<tr><td>{_html(value)}</td><td></td></tr>'}"
        "</table></section>"
        for key, value in summary.items()
        if key != "article_count"
    )
    body = (
        f"<h1>Classification Report</h1><p><strong>Path:</strong> <span class='path'>{_html(report_path)}</span></p>"
        f"<p><strong>Articles:</strong> {_html(summary.get('article_count'))}</p><div class='grid'>{tables}</div>"
    )
    return _layout("Classification Report", body)
