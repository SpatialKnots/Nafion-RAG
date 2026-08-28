from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article, ArticleTag, Chunk, Collection, IngestionJob, Page, PageTextLayer, Section
from app.db.session import get_session
from app.documents.context import ContextNotFoundError, get_chunk_context, get_page_range_context
from app.documents.service import PageEvidenceNotFoundError, build_pdf_url
from app.generation.providers import GenerationOutputError, GenerationUnavailableError
from app.generation.service import answer_question, answer_response_to_dict
from app.ingestion.queue import job_to_response
from app.retrieval.index_lifecycle import list_vector_index_states, request_vector_rebuild, vector_index_state_to_response
from app.retrieval.search import SearchFilters, search_chunks
from app.retrieval.vector_index import VectorIndexUnavailableError

SessionDep = Annotated[Session, Depends(get_session)]
router = APIRouter()


def _html(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def _truncate(text: str | None, limit: int = 500) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _counter_rows(counter: Counter[str]) -> str:
    if not counter:
        return "<tr><td colspan='2'>No data</td></tr>"
    return "".join(f"<tr><td>{_html(key)}</td><td class='num'>{value}</td></tr>" for key, value in sorted(counter.items()))


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


def _linked_answer_text(answer: str, citations: list[dict[str, object]]) -> str:
    by_id: dict[str, str] = {}
    for citation in citations:
        citation_id = citation.get("citation_id")
        article_id = citation.get("article_id")
        chunk_id = citation.get("chunk_id")
        evidence_text = str(citation.get("text") or "")
        if citation_id and article_id and chunk_id:
            by_id[str(citation_id)] = _context_url(str(article_id), str(chunk_id), evidence_text, "phrase")
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
        parts.append(f"<a href='{_html(href)}'>{_html(match.group(0))}</a>")
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
    header {
      background: var(--paper); border-bottom: 1px solid var(--line); padding: 12px 20px;
      display:flex; gap:18px; align-items:center;
    }
    header strong { font-size: 16px; color:var(--graphite); letter-spacing:0; }
    header strong .domain { color:var(--slate); font-weight:500; }
    nav { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    nav a { color: var(--accent); text-decoration: none; }
    main { padding: 18px 20px 40px; max-width: 1500px; margin: 0 auto; }
    h1 { font-size: 22px; margin: 0 0 14px; }
    h2 { font-size: 17px; margin: 22px 0 8px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
    .workbench-grid { display:grid; grid-template-columns:minmax(320px, 0.9fr) minmax(420px, 1.4fr); gap:14px; align-items:start; }
    .evidence-grid { display:grid; grid-template-columns:minmax(320px, 0.9fr) minmax(420px, 1.2fr); gap:14px; align-items:start; }
    .panel { background:var(--paper); border:1px solid var(--line); border-radius:var(--radius); padding:12px; }
    .panel.compact h2 { margin-top:0; }
    .workspace-band {
      background:var(--paper); border:1px solid var(--line); border-radius:var(--radius);
      padding:14px; margin-bottom:14px;
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
      border:1px solid var(--line); border-left:4px solid var(--aqua); border-radius:var(--radius);
      padding:12px; background:var(--paper); margin-bottom:10px;
    }
    .claim-card.low-evidence { border-left-color:var(--coral); }
    .claim-text { font-size:15px; line-height:1.45; margin:0 0 10px; }
    .source-card { border:1px solid var(--line); border-radius:var(--radius); padding:10px; background:var(--paper); margin-bottom:10px; }
    .source-card.table-derived { border-left:4px solid var(--coral); }
    .source-head { display:flex; justify-content:space-between; gap:12px; align-items:start; margin-bottom:6px; }
    .source-title { font-weight:600; color:var(--graphite); }
    .source-fragment { border-left:3px solid var(--aqua); padding-left:10px; margin:8px 0; color:#24313A; }
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
    button[disabled] { opacity:.65; cursor:wait; }
    @keyframes spin { to { transform: rotate(360deg); } }
    mark { background:#fff1a8; padding:0 1px; }
    pre.context { white-space: pre-wrap; font-family: Consolas, monospace; font-size: 13px; margin: 6px 0 0; }
    input, select, button { font: inherit; padding:6px 8px; border:1px solid var(--line); border-radius:8px; background:var(--paper); }
    textarea { font: inherit; padding:7px 8px; border:1px solid var(--line); border-radius:8px; background:var(--paper);
      min-width: min(720px, 100%); }
    button { background:var(--graphite); color:#fff; border-color:var(--graphite); }
    form { display:flex; gap:8px; flex-wrap:wrap; align-items:end; margin-bottom:14px; }
    form.stack { display:block; }
    form.stack label { display:block; margin:0 0 10px; }
    form.stack .actions { margin-top:8px; }
    a { color: var(--accent); }
    @media (max-width: 900px) {
      .workbench-grid, .evidence-grid { grid-template-columns:1fr; }
      header { align-items:flex-start; flex-direction:column; gap:8px; }
    }
    """
    nav = (
        '<a href="/">Library</a>'
        '<a href="/ui/search">Search</a>'
        '<a href="/ui/answer">Answer</a>'
        '<a href="/ui/articles">Documents</a>'
        '<a href="/ui/ingestion">Ingestion</a>'
        '<a href="/ui/vector-indexes">Settings</a>'
        '<a href="/ui/reports/retrieval">Retrieval report</a>'
        '<a href="/ui/reports/text-quality">Text quality</a>'
        '<a href="/ui/reports/classification">Classification report</a>'
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
<header><strong>ARIADNE <span class="domain">/ Nafion profile</span></strong><nav>{nav}</nav></header>
<main>{body}</main>
</body></html>"""
    return HTMLResponse(html)


@router.get("/", response_class=HTMLResponse)
def dashboard(session: SessionDep) -> HTMLResponse:
    settings = get_settings()
    retrieval_report = _latest_report(settings.data_root, "retrieval_eval_*.json")
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
    selected_rows = _counter_rows(selected_layers)
    source_rows = _counter_rows(source_types)
    text_layer_rows = _counter_rows(text_layers)
    eval_command = "python -m app.evaluation.cli retrieval docs/evaluation_questions.yaml --top-k 10"
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
    <h1>ARIADNE Research Workbench</h1>
    <section class="workspace-band">
      <form method="get" action="/ui/answer">
        <label>Question<br><input name="question" size="56" value="Li-Nafion conductivity"></label>
        <label>Collection<br><input name="collection" value="literature"></label>
        <label>Method<br><select name="method">
          <option value="hybrid_cross_lingual">hybrid_cross_lingual</option>
          <option value="hybrid">hybrid</option>
          <option value="exact">exact</option>
        </select></label>
        <button type="submit">Answer</button>
      </form>
      <div class="status-strip">
        <a class="status-pill" href="/ui/search">Search</a>
        <a class="status-pill" href="/ui/answer">Claims</a>
        <a class="status-pill" href="/ui/answer">Evidence</a>
        <a class="status-pill" href="/ui/articles">Documents</a>
        <a class="status-pill" href="/ui/reports/text-quality">Tables / Facts diagnostics</a>
      </div>
    </section>
    <h2>Corpus Dashboard</h2>
    <div class="grid">
      <section class="panel"><h2>Corpus</h2><table>{corpus_rows}</table></section>
      {selected_panel}
      {source_panel}
      {text_layer_panel}
      <section class="panel"><h2>Retrieval Evaluation</h2>{retrieval_report_link}{_command_hint(eval_command)}</section>
      <section class="panel"><h2>Text Quality</h2>{text_quality_report_link}{_command_hint(text_quality_command)}</section>
    </div>
    <h2>Quick Search</h2>
    <form method="get" action="/ui/search">
      <input name="q" size="42" value="Li-Nafion conductivity">
      <input name="collection" value="literature">
      <input name="top_k" type="number" value="10" min="1">
      <select name="method">
        <option value="exact">exact</option>
        <option value="semantic">semantic</option>
        <option value="hybrid">hybrid</option>
      </select>
      <button type="submit">Search</button>
    </form>
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
                article_id = citation.get("article_id") if citation else None
                chunk_id = citation.get("chunk_id") if citation else None
                evidence_text = str(citation.get("text") or "") if citation else ""
                if article_id and chunk_id:
                    chips.append(
                        f"<a class='citation-chip' href='{_html(_context_url(str(article_id), str(chunk_id), evidence_text, 'phrase'))}'>"
                        f"{_html(citation_id)}</a>"
                    )
                else:
                    chips.append(f"<span class='citation-chip'>{_html(citation_id)}</span>")
            citation_chips_html = "".join(chips) or "<span class='muted'>No citation links</span>"
            claim_cards.append(
                "<article class='claim-card'>"
                f"<p class='claim-text'><strong>Claim {index}.</strong> {_html(claim.get('text'))}</p>"
                f"<div class='actions'>{citation_chips_html}</div>"
                "</article>"
            )

    source_cards = []
    citation_rows = []
    for citation in citation_dicts:
        article_id = citation.get("article_id")
        chunk_id = citation.get("chunk_id")
        page_start = citation.get("page_start") if isinstance(citation.get("page_start"), int) else None
        page_end = citation.get("page_end") if isinstance(citation.get("page_end"), int) else None
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
        f"<pre class='context'>{_linked_answer_text(str(answer), citation_dicts)}</pre>"
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
        "<div class='evidence-grid'>"
        "<section><h2>Answer</h2>"
        f"<section class='panel compact'>{answer_block}</section>"
        "<h2>Claims</h2>"
        f"{claim_cards_html}</section>"
        "<section><h2>Evidence</h2>"
        f"{source_cards_html}</section>"
        "</div>"
        "<h2>Citations</h2><table><tr><th>ID</th><th>Article</th><th class='num'>Pages</th>"
        f"<th>Language</th><th class='num'>Score</th><th>Evidence text</th><th>Links</th></tr>{citation_rows_html}</table>"
    )


def _answer_body(
    question: str = "",
    collection: str = "literature",
    top_k: int = 5,
    method: str = "hybrid_cross_lingual",
    answer_style: str = "claims",
    answer_language: str = "auto",
    result: str = "",
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
    <h1>Answer</h1>
    <form class="stack" method="post" action="/ui/answer" data-async-result="/ui/answer/result">
      <label>Question<br><textarea name="question" rows="4">{_html(question)}</textarea></label>
      <div class="actions">
        <label>Collection<br><input name="collection" value="{_html(collection)}"></label>
        <label>Top K<br><input name="top_k" type="number" value="{top_k}" min="1"></label>
        <label>Method<br><select name="method">{method_options}</select></label>
        <label>Style<br><select name="answer_style">{style_options}</select></label>
        <label>Answer language<br><select name="answer_language">{language_options}</select></label>
        <button type="submit">Answer</button>
      </div>
    </form>
    <div id="answer-result" aria-live="polite">{result}</div>
    <script>
    (() => {{
      const form = document.querySelector('form[data-async-result]');
      const result = document.getElementById('answer-result');
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
          const responsePromise = fetch(form.dataset.asyncResult, {{
            method: 'POST',
            body: new FormData(form),
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
          setStep(null, ['prepare', 'send', 'wait', 'receive', 'render']);
          result.insertAdjacentHTML('beforeend', body);
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
        const question = form.querySelector('textarea[name="question"]');
        if (question) {{
          question.value = target.dataset.suggestedQuery;
          form.requestSubmit();
        }}
      }});
    }})();
    </script>
    """


@router.get("/ui/answer", response_class=HTMLResponse)
def answer_page(
    question: str = "",
    collection: str = "literature",
    top_k: int = Query(default=5, ge=1),
    method: str = "hybrid_cross_lingual",
    answer_style: str = "claims",
    answer_language: str = "auto",
) -> HTMLResponse:
    return _layout("Answer", _answer_body(question, collection, top_k, method, answer_style, answer_language))


def _answer_result_fragment(
    session: Session,
    question: str,
    collection: str,
    top_k: int,
    method: str,
    answer_style: str,
    answer_language: str,
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
        )
        payload = answer_response_to_dict(response)
        return _answer_payload_panel(payload, question)
    except (GenerationUnavailableError, GenerationOutputError, VectorIndexUnavailableError, ValueError) as exc:
        return f"<section class='panel'><p class='warn'>{_html(exc)}</p></section>"


@router.post("/ui/answer", response_class=HTMLResponse)
def answer_action(
    session: SessionDep,
    question: Annotated[str, Form()],
    collection: Annotated[str, Form()] = "literature",
    top_k: Annotated[int, Form()] = 5,
    method: Annotated[str, Form()] = "hybrid_cross_lingual",
    answer_style: Annotated[str, Form()] = "claims",
    answer_language: Annotated[str, Form()] = "auto",
) -> HTMLResponse:
    result = _answer_result_fragment(session, question, collection, top_k, method, answer_style, answer_language)
    return _layout("Answer", _answer_body(question, collection, top_k, method, answer_style, answer_language, result))


@router.post("/ui/answer/result", response_class=HTMLResponse)
def answer_result_action(
    session: SessionDep,
    question: Annotated[str, Form()],
    collection: Annotated[str, Form()] = "literature",
    top_k: Annotated[int, Form()] = 5,
    method: Annotated[str, Form()] = "hybrid_cross_lingual",
    answer_style: Annotated[str, Form()] = "claims",
    answer_language: Annotated[str, Form()] = "auto",
) -> HTMLResponse:
    return HTMLResponse(_answer_result_fragment(session, question, collection, top_k, method, answer_style, answer_language))


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


@router.get("/ui/search", response_class=HTMLResponse)
def search_page(
    session: SessionDep,
    q: str = "",
    collection: str = "literature",
    top_k: int = Query(default=10, ge=1),
    article_id: UUID | None = None,
    doi: str = "",
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str = "",
    source_type: str = "",
    text_layer: str = "",
    tag_type: str = "",
    tag_value: str = "",
    method: str = "exact",
    group_by: str = "none",
    chunks_per_article: int | None = None,
) -> HTMLResponse:
    rows = ""
    if chunks_per_article is not None and chunks_per_article <= 0:
        raise HTTPException(status_code=400, detail="chunks_per_article must be positive")
    filters = SearchFilters.normalize(
        article_id=article_id,
        doi=doi,
        year=year,
        year_from=year_from,
        year_to=year_to,
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
                chunks_per_article=chunks_per_article,
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
    chunks_value = "" if chunks_per_article is None else str(chunks_per_article)
    table_header = (
        '<tr><th>Article</th><th class="num">Best pages</th><th class="num">Best score</th>'
        '<th class="num">Chunks</th><th>Method</th><th>Best snippet</th><th>PDF</th></tr>'
        if group_by == "article"
        else '<tr><th>Article</th><th class="num">Pages</th><th>Type / layer</th><th>Method</th>'
        '<th class="num">Score</th><th>Snippet</th><th>PDF</th></tr>'
    )
    body = f"""
    <h1>Search</h1>
    <form method="get" action="/ui/search">
      <label>Query<br><input name="q" size="52" value="{_html(q)}"></label>
      <label>Collection<br><input name="collection" value="{_html(collection)}"></label>
      <label>Source type<br><select name="source_type">{source_options}</select></label>
      <label>Text layer<br><select name="text_layer">{text_layer_options}</select></label>
      <label>Method<br><select name="method">{method_options}</select></label>
      <label>Top K<br><input name="top_k" type="number" value="{top_k}" min="1"></label>
      <label>DOI<br><input name="doi" value="{_html(doi)}"></label>
      <label>Year<br><input name="year" type="number" value="{_html(year)}"></label>
      <label>Year from<br><input name="year_from" type="number" value="{_html(year_from)}"></label>
      <label>Year to<br><input name="year_to" type="number" value="{_html(year_to)}"></label>
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
def article_list(session: SessionDep) -> HTMLResponse:
    articles = list(session.scalars(select(Article).order_by(Article.title)))
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


@router.get("/ui/reports/retrieval", response_class=HTMLResponse)
def retrieval_report_page() -> HTMLResponse:
    settings = get_settings()
    report_path = _latest_report(settings.data_root, "retrieval_eval_*.json")
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
            missing_keywords = ", ".join(str(item) for item in question.get("missing_keywords", []))
            results = question.get("results", [])
            result_rows = _result_rows(results if isinstance(results, list) else [])
            question_sections.append(
                f"<h2>{_html(question.get('id'))}: {_html(question.get('query'))}</h2>"
                "<section class='panel'>"
                f"<p><strong>Status:</strong> <span class='{status_class}'>"
                f"{_html('PASS' if question.get('passed') else 'FAIL')}</span> "
                f"<strong>Results:</strong> {_html(question.get('result_count'))}</p>"
                f"<p><strong>Missing DOI:</strong> {_html(missing_dois or 'none')} &nbsp; "
                f"<strong>Missing keywords:</strong> {_html(missing_keywords or 'none')}</p>"
                "</section>"
                "<table><tr><th>Article</th><th class='num'>Pages</th>"
                "<th class='num'>Score</th><th>Method</th><th>Snippet</th></tr>"
                f"{result_rows}</table>"
            )
    summary_rows = (
        f'<td class="num">{_html(summary.get("total"))}</td>'
        f'<td class="num">{_html(summary.get("passed"))}</td>'
        f'<td class="num">{_html(summary.get("failed"))}</td>'
        f'<td class="num">{_html(summary.get("empty_result_queries"))}</td>'
    )
    method = _html(settings_payload.get("retrieval_method"))
    body = f"""
    <h1>Retrieval Evaluation Report</h1>
    <section class="panel">
      <p><strong>Path:</strong> <span class="path">{_html(report_path)}</span></p>
      <p><strong>Created:</strong> {_html(payload.get("created_at"))} &nbsp; <strong>Method:</strong> {method}</p>
      <table><tr><th>Total</th><th>Passed</th><th>Failed</th><th>Empty result queries</th></tr><tr>{summary_rows}</tr></table>
    </section>
    {"".join(question_sections) or '<p class="warn">Report has no readable questions.</p>'}
    """
    return _layout("Retrieval Evaluation Report", body)


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
