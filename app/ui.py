from __future__ import annotations

import json
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article, ArticleTag, Chunk, Collection, IngestionJob, Page, PageTextLayer, Section
from app.db.session import get_session
from app.documents.service import build_pdf_url
from app.ingestion.queue import job_to_response
from app.retrieval.search import search_chunks

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


def _layout(title: str, body: str) -> HTMLResponse:
    css = """
    :root { color-scheme: light; --line:#d7dde5; --muted:#5c6675; --bg:#f6f8fb; --ink:#1d2430; --accent:#2454a6; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Segoe UI, Arial, sans-serif; color: var(--ink); background: var(--bg); font-size: 14px; }
    header { background: #ffffff; border-bottom: 1px solid var(--line); padding: 12px 20px; display:flex; gap:18px; align-items:center; }
    header strong { font-size: 16px; }
    nav a { margin-right: 12px; color: var(--accent); text-decoration: none; }
    main { padding: 18px 20px 40px; max-width: 1500px; margin: 0 auto; }
    h1 { font-size: 22px; margin: 0 0 14px; }
    h2 { font-size: 17px; margin: 22px 0 8px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
    .panel { background:#fff; border:1px solid var(--line); border-radius:6px; padding:12px; }
    .muted { color: var(--muted); }
    .path { font-family: Consolas, monospace; font-size: 12px; word-break: break-all; }
    table { width:100%; border-collapse: collapse; background:#fff; border:1px solid var(--line); }
    th, td { border-bottom:1px solid var(--line); padding:7px 8px; vertical-align: top; text-align:left; }
    th { background:#eef2f7; font-weight:600; }
    tr:hover td { background:#fafcff; }
    .num { text-align:right; font-variant-numeric: tabular-nums; }
    .tag { display:inline-block; border:1px solid var(--line); border-radius:4px; padding:2px 5px; margin:1px; background:#f9fbfd; }
    .actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .ok { color:#126b36; font-weight:600; }
    .warn { color:#9b5a00; font-weight:600; }
    input, select, button { font: inherit; padding:6px 8px; border:1px solid var(--line); border-radius:4px; background:#fff; }
    button { background:#2454a6; color:#fff; border-color:#2454a6; }
    form { display:flex; gap:8px; flex-wrap:wrap; align-items:end; margin-bottom:14px; }
    a { color: var(--accent); }
    """
    nav = (
        '<a href="/">Dashboard</a>'
        '<a href="/ui/search">Search</a>'
        '<a href="/ui/articles">Articles</a>'
        '<a href="/ui/ingestion">Ingestion</a>'
        '<a href="/ui/reports/retrieval">Retrieval report</a>'
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
<header><strong>Nafion RAG</strong><nav>{nav}</nav></header>
<main>{body}</main>
</body></html>"""
    return HTMLResponse(html)


@router.get("/", response_class=HTMLResponse)
def dashboard(session: SessionDep) -> HTMLResponse:
    settings = get_settings()
    retrieval_report = _latest_report(settings.data_root, "retrieval_eval_*.json")
    retrieval_report_link = (
        f"<a href='/ui/reports/retrieval'>Latest retrieval evaluation</a><div class='path'>{_html(retrieval_report)}</div>"
        if retrieval_report is not None
        else "<span class='warn'>No retrieval evaluation report generated yet.</span>"
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
    <h1>Corpus Dashboard</h1>
    <div class="grid">
      <section class="panel"><h2>Corpus</h2><table>{corpus_rows}</table></section>
      {selected_panel}
      {source_panel}
      {text_layer_panel}
      <section class="panel"><h2>Retrieval Evaluation</h2>{retrieval_report_link}{_command_hint(eval_command)}</section>
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


@router.get("/ui/search", response_class=HTMLResponse)
def search_page(
    session: SessionDep,
    q: str = "",
    collection: str = "literature",
    top_k: int = Query(default=10, ge=1),
    source_type: str = "",
    method: str = "exact",
) -> HTMLResponse:
    rows = ""
    normalized_source_type = source_type.strip() or None
    if q.strip():
        try:
            response = search_chunks(
                session,
                q,
                collection,
                top_k,
                method=method,
                source_type=normalized_source_type,
                settings=get_settings(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if response.results:
            rows = "".join(
                "<tr>"
                f"<td><a href='/ui/articles/{_html(result.article_id)}'>{_html(result.title)}</a>"
                f"<div class='muted'>{_html(result.doi)}</div></td>"
                f"<td class='num'>{_html(_page_range(result.page_start, result.page_end))}</td>"
                f"<td>{_html(result.source_type)}<div class='muted'>{_html(result.text_layer)}</div></td>"
                f"<td>{_html(result.retrieval_method)}</td>"
                f"<td class='num'>{result.score:.4g}</td>"
                f"<td>{_html(result.snippet)}</td>"
                f"<td class='actions'>{_pdf_link(result.article_id, result.page_start)}</td>"
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
    body = f"""
    <h1>Search</h1>
    <form method="get" action="/ui/search">
      <label>Query<br><input name="q" size="52" value="{_html(q)}"></label>
      <label>Collection<br><input name="collection" value="{_html(collection)}"></label>
      <label>Source type<br><select name="source_type">{source_options}</select></label>
      <label>Method<br><select name="method">{method_options}</select></label>
      <label>Top K<br><input name="top_k" type="number" value="{top_k}" min="1"></label>
      <button type="submit">Search</button>
    </form>
    <table><tr><th>Article</th><th class="num">Pages</th><th>Type / layer</th><th>Method</th>
    <th class="num">Score</th><th>Snippet</th><th>PDF</th></tr>
    {rows or empty_rows}</table>
    """
    return _layout("Search", body)


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
