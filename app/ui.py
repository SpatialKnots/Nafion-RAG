from __future__ import annotations

import json
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article, ArticleTag, Chunk, Collection, Page, PageTextLayer, Section
from app.db.session import get_session
from app.retrieval.search import exact_search

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
    .ok { color:#126b36; font-weight:600; }
    .warn { color:#9b5a00; font-weight:600; }
    input, select, button { font: inherit; padding:6px 8px; border:1px solid var(--line); border-radius:4px; background:#fff; }
    button { background:#2454a6; color:#fff; border-color:#2454a6; }
    form { display:flex; gap:8px; flex-wrap:wrap; align-items:end; margin-bottom:14px; }
    a { color: var(--accent); }
    """
    html = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{_html(title)}</title><style>{css}</style></head>
<body>
<header><strong>Nafion RAG</strong><nav><a href="/">Dashboard</a><a href="/ui/search">Search</a><a href="/ui/articles">Articles</a><a href="/ui/reports/classification">Classification report</a></nav></header>
<main>{body}</main>
</body></html>"""
    return HTMLResponse(html)


@router.get("/", response_class=HTMLResponse)
def dashboard(session: SessionDep) -> HTMLResponse:
    article_count = session.scalar(select(func.count()).select_from(Article)) or 0
    page_count = session.scalar(select(func.count()).select_from(Page)) or 0
    chunk_count = session.scalar(select(func.count()).select_from(Chunk)) or 0
    layer_count = session.scalar(select(func.count()).select_from(PageTextLayer)) or 0
    selected_layers = Counter(dict(session.execute(select(Page.selected_text_layer, func.count()).group_by(Page.selected_text_layer)).all()))
    source_types = Counter(dict(session.execute(select(Chunk.source_type, func.count()).group_by(Chunk.source_type)).all()))
    text_layers = Counter(dict(session.execute(select(Chunk.text_layer, func.count()).group_by(Chunk.text_layer)).all()))
    body = f"""
    <h1>Corpus Dashboard</h1>
    <div class="grid">
      <section class="panel"><h2>Corpus</h2><table><tr><td>Articles</td><td class="num">{article_count}</td></tr><tr><td>Pages</td><td class="num">{page_count}</td></tr><tr><td>Chunks</td><td class="num">{chunk_count}</td></tr><tr><td>Text layers</td><td class="num">{layer_count}</td></tr></table></section>
      <section class="panel"><h2>Selected Page Layers</h2><table><tr><th>Layer</th><th class="num">Pages</th></tr>{_counter_rows(selected_layers)}</table></section>
      <section class="panel"><h2>Chunk Source Types</h2><table><tr><th>Type</th><th class="num">Chunks</th></tr>{_counter_rows(source_types)}</table></section>
      <section class="panel"><h2>Chunk Text Layers</h2><table><tr><th>Layer</th><th class="num">Chunks</th></tr>{_counter_rows(text_layers)}</table></section>
    </div>
    <h2>Quick Search</h2>
    <form method="get" action="/ui/search"><input name="q" size="42" value="Li-Nafion conductivity"><input name="collection" value="literature"><input name="top_k" type="number" value="10" min="1"><button type="submit">Search</button></form>
    """
    return _layout("Dashboard", body)


@router.get("/ui/search", response_class=HTMLResponse)
def search_page(session: SessionDep, q: str = "", collection: str = "literature", top_k: int = Query(default=10, ge=1)) -> HTMLResponse:
    rows = ""
    if q.strip():
        response = exact_search(session, q, collection, top_k)
        if response.results:
            rows = "".join(
                "<tr>"
                f"<td><a href='/ui/articles/{_html(result.article_id)}'>{_html(result.title)}</a><div class='muted'>{_html(result.doi)}</div></td>"
                f"<td class='num'>{result.page_start}-{result.page_end}</td>"
                f"<td class='num'>{result.score:.1f}</td>"
                f"<td>{_html(result.snippet)}</td>"
                "</tr>"
                for result in response.results
            )
        else:
            rows = "<tr><td colspan='4'>No results</td></tr>"
    body = f"""
    <h1>Search</h1>
    <form method="get" action="/ui/search">
      <label>Query<br><input name="q" size="52" value="{_html(q)}"></label>
      <label>Collection<br><input name="collection" value="{_html(collection)}"></label>
      <label>Top K<br><input name="top_k" type="number" value="{top_k}" min="1"></label>
      <button type="submit">Search</button>
    </form>
    <table><tr><th>Article</th><th class="num">Pages</th><th class="num">Score</th><th>Snippet</th></tr>{rows or "<tr><td colspan='4'>Enter a query.</td></tr>"}</table>
    """
    return _layout("Search", body)


def _article_tag_summary(tags: list[ArticleTag]) -> str:
    grouped: dict[str, list[str]] = defaultdict(list)
    for tag in tags:
        grouped[tag.tag_type].append(tag.tag_value)
    return " ".join(
        f"<span class='tag'>{_html(tag_type)}: {_html(', '.join(sorted(set(values))[:6]))}</span>" for tag_type, values in sorted(grouped.items())
    )


@router.get("/ui/articles", response_class=HTMLResponse)
def article_list(session: SessionDep) -> HTMLResponse:
    articles = list(session.scalars(select(Article).order_by(Article.title)))
    rows = []
    for article in articles:
        tags = list(session.scalars(select(ArticleTag).where(ArticleTag.article_id == article.id).order_by(ArticleTag.tag_type, ArticleTag.tag_value)))
        page_layers = Counter(dict(session.execute(select(Page.selected_text_layer, func.count()).where(Page.article_id == article.id).group_by(Page.selected_text_layer)).all()))
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
    body = f"<h1>Articles</h1><table><tr><th>Article</th><th class='num'>Pages</th><th class='num'>Chunks</th><th>Selected layers</th><th>Tags</th></tr>{''.join(rows) or '<tr><td colspan=5>No articles</td></tr>'}</table>"
    return _layout("Articles", body)


def _get_article_or_404(session: Session, article_id: UUID) -> Article:
    article = session.scalar(select(Article).where(Article.id == article_id))
    if article is None:
        raise HTTPException(status_code=404, detail=f"Unknown article: {article_id}")
    return article


@router.get("/ui/articles/{article_id}", response_class=HTMLResponse)
def article_detail(session: SessionDep, article_id: UUID) -> HTMLResponse:
    article = _get_article_or_404(session, article_id)
    tags = list(session.scalars(select(ArticleTag).where(ArticleTag.article_id == article.id).order_by(ArticleTag.tag_type, ArticleTag.tag_value)))
    sections = list(session.scalars(select(Section).where(Section.article_id == article.id).order_by(Section.page_start, Section.normalized_name)))
    chunks = list(session.scalars(select(Chunk).where(Chunk.article_id == article.id).order_by(Chunk.chunk_index)))
    page_layers = Counter(dict(session.execute(select(Page.selected_text_layer, func.count()).where(Page.article_id == article.id).group_by(Page.selected_text_layer)).all()))
    section_rows = "".join(
        f"<tr><td>{_html(section.normalized_name)}</td><td>{_html(section.name)}</td><td class='num'>{_html(section.page_start)}-{_html(section.page_end)}</td><td>{_html(section.source_type)}</td></tr>"
        for section in sections
    )
    chunk_rows = "".join(
        f"<tr><td class='num'>{chunk.chunk_index}</td><td class='num'>{chunk.page_start}-{chunk.page_end}</td><td>{_html(chunk.source_type)}</td><td>{_html(chunk.text_layer)}</td><td>{_html(_truncate(chunk.text))}</td></tr>"
        for chunk in chunks
    )
    body = f"""
    <h1>{_html(article.title)}</h1>
    <section class="panel">
      <p><strong>DOI:</strong> {_html(article.doi)} &nbsp; <strong>Status:</strong> {_html(article.status)} &nbsp; <strong>Selected layers:</strong> {_html(dict(page_layers))}</p>
      <p><strong>Original PDF:</strong> <span class="path">{_html(article.pdf_original_path)}</span></p>
      <p><strong>OCR PDF:</strong> <span class="path">{_html(article.pdf_ocr_path)}</span></p>
      <p><a href="/ui/articles/{article.id}/text-layers">Inspect page text layers</a></p>
    </section>
    <h2>Tags</h2><div class="panel">{_article_tag_summary(tags) or '<span class="muted">No tags</span>'}</div>
    <h2>Sections</h2><table><tr><th>Normalized</th><th>Name</th><th class="num">Pages</th><th>Type</th></tr>{section_rows or '<tr><td colspan=4>No sections</td></tr>'}</table>
    <h2>Chunks</h2><table><tr><th class="num">#</th><th class="num">Pages</th><th>Source type</th><th>Text layer</th><th>Snippet</th></tr>{chunk_rows or '<tr><td colspan=5>No chunks</td></tr>'}</table>
    """
    return _layout("Article", body)


@router.get("/ui/articles/{article_id}/text-layers", response_class=HTMLResponse)
def article_text_layers(session: SessionDep, article_id: UUID) -> HTMLResponse:
    article = _get_article_or_404(session, article_id)
    selected = dict(session.execute(select(Page.page_number, Page.selected_text_layer).where(Page.article_id == article.id)).all())
    layers = list(
        session.scalars(
            select(PageTextLayer).where(PageTextLayer.article_id == article.id).order_by(PageTextLayer.page_number, PageTextLayer.layer_type)
        )
    )
    rows = "".join(
        f"<tr><td class='num'>{layer.page_number}</td><td>{_html(layer.layer_type)}</td><td>{'<span class=ok>yes</span>' if layer.has_usable_text else '<span class=warn>no</span>'}</td><td class='num'>{float(layer.quality_score):.3f}</td><td>{'<span class=ok>selected</span>' if selected.get(layer.page_number) == layer.layer_type else ''}</td><td class='path'>{_html(layer.source_pdf_path)}</td></tr>"
        for layer in layers
    )
    body = f"<h1>Text Layers: {_html(article.title)}</h1><p><a href='/ui/articles/{article.id}'>Back to article</a></p><table><tr><th class='num'>Page</th><th>Layer</th><th>Usable</th><th class='num'>Quality</th><th>Selected</th><th>Source PDF</th></tr>{rows or '<tr><td colspan=6>No text layers</td></tr>'}</table>"
    return _layout("Text Layers", body)


def _latest_classification_report(data_root: Path) -> Path | None:
    export_dir = data_root / "exports"
    if not export_dir.exists():
        return None
    reports = sorted(export_dir.glob("classification_report_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


@router.get("/ui/reports/classification", response_class=HTMLResponse)
def classification_report_page() -> HTMLResponse:
    settings = get_settings()
    report_path = _latest_classification_report(settings.data_root)
    if report_path is None:
        body = "<h1>Classification Report</h1><p class='warn'>No classification report generated yet.</p><p class='path'>python -m app.classification.cli report --collection literature</p>"
        return _layout("Classification Report", body)
    payload: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    tables = "".join(
        f"<section class='panel'><h2>{_html(key)}</h2><table><tr><th>Value</th><th class='num'>Count</th></tr>{_counter_rows(Counter(value)) if isinstance(value, dict) else f'<tr><td>{_html(value)}</td><td></td></tr>'}</table></section>"
        for key, value in summary.items()
        if key != "article_count"
    )
    body = f"<h1>Classification Report</h1><p><strong>Path:</strong> <span class='path'>{_html(report_path)}</span></p><p><strong>Articles:</strong> {_html(summary.get('article_count'))}</p><div class='grid'>{tables}</div>"
    return _layout("Classification Report", body)
