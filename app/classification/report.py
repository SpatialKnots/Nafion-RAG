from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, ArticleTag, Chunk, Collection, Page, Section


def _counter_payload(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def _article_payload(session: Session, article: Article) -> dict[str, Any]:
    tags = list(session.scalars(select(ArticleTag).where(ArticleTag.article_id == article.id).order_by(ArticleTag.tag_type, ArticleTag.tag_value)))
    sections = list(session.scalars(select(Section).where(Section.article_id == article.id).order_by(Section.page_start, Section.normalized_name)))
    chunks = list(session.scalars(select(Chunk).where(Chunk.article_id == article.id).order_by(Chunk.chunk_index)))
    pages = list(session.scalars(select(Page).where(Page.article_id == article.id).order_by(Page.page_number)))

    tags_by_type: dict[str, list[str]] = defaultdict(list)
    for tag in tags:
        tags_by_type[tag.tag_type].append(tag.tag_value)

    return {
        "article_id": str(article.id),
        "title": article.title,
        "doi": article.doi,
        "page_count": len(pages),
        "chunk_count": len(chunks),
        "section_count": len(sections),
        "tags_by_type": {tag_type: sorted(set(values)) for tag_type, values in sorted(tags_by_type.items())},
        "sections": [
            {
                "name": section.name,
                "normalized_name": section.normalized_name,
                "page_start": section.page_start,
                "page_end": section.page_end,
                "source_type": section.source_type,
            }
            for section in sections
        ],
        "chunks_by_source_type": _counter_payload(Counter(chunk.source_type for chunk in chunks)),
        "chunks_by_text_layer": _counter_payload(Counter(chunk.text_layer for chunk in chunks)),
        "pages_by_selected_text_layer": _counter_payload(Counter(page.selected_text_layer for page in pages)),
    }


def build_classification_report(session: Session, collection_name: str) -> dict[str, Any]:
    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")

    articles = list(session.scalars(select(Article).where(Article.collection_id == collection.id).order_by(Article.title)))
    article_payloads = [_article_payload(session, article) for article in articles]

    tag_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    text_layer_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    for article in article_payloads:
        for tag_type, values in article["tags_by_type"].items():
            tag_counts[tag_type] += len(values)
        source_type_counts.update(article["chunks_by_source_type"])
        text_layer_counts.update(article["chunks_by_text_layer"])
        section_counts.update(section["normalized_name"] or "unknown" for section in article["sections"])

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "collection": collection_name,
        "summary": {
            "article_count": len(article_payloads),
            "tag_counts_by_type": _counter_payload(tag_counts),
            "chunk_counts_by_source_type": _counter_payload(source_type_counts),
            "chunk_counts_by_text_layer": _counter_payload(text_layer_counts),
            "section_counts_by_name": _counter_payload(section_counts),
        },
        "articles": article_payloads,
    }


def write_classification_report(report: dict[str, Any], data_root: Path) -> Path:
    export_dir = data_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = export_dir / f"classification_report_{timestamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
