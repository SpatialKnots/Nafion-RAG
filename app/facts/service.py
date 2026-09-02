from __future__ import annotations

from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection, StructuredFact
from app.documents.service import build_pdf_url


def list_structured_facts(
    session: Session,
    *,
    collection_name: str = "literature",
    article_id: UUID | None = None,
    field_name: str | None = None,
    unit: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> list[StructuredFact]:
    statement = select(StructuredFact).join(Article, StructuredFact.article_id == Article.id)
    statement = statement.join(Collection, Article.collection_id == Collection.id).where(Collection.name == collection_name)
    if article_id is not None:
        statement = statement.where(StructuredFact.article_id == article_id)
    if field_name is not None and field_name.strip():
        statement = statement.where(StructuredFact.field_name == field_name.strip())
    if unit is not None and unit.strip():
        statement = statement.where(StructuredFact.unit == unit.strip())
    if source is not None and source.strip():
        statement = statement.where(StructuredFact.source == source.strip())
    statement = statement.order_by(StructuredFact.field_name, StructuredFact.unit, StructuredFact.id).limit(limit)
    return list(session.scalars(statement))


def structured_fact_summary(facts: list[StructuredFact]) -> dict[str, object]:
    return {
        "count": len(facts),
        "by_field": dict(sorted(Counter(fact.field_name for fact in facts).items())),
        "by_unit": dict(sorted(Counter(str(fact.unit) for fact in facts if fact.unit is not None).items())),
        "by_source": dict(sorted(Counter(fact.source for fact in facts).items())),
    }


def structured_fact_to_response(session: Session, fact: StructuredFact) -> dict[str, object]:
    article = session.get(Article, fact.article_id)
    chunk = session.get(Chunk, fact.source_chunk_id) if fact.source_chunk_id is not None else None
    page_start = chunk.page_start if chunk is not None else None
    page_end = chunk.page_end if chunk is not None else None
    context_url = f"/ui/articles/{fact.article_id}/chunks/{fact.source_chunk_id}/context" if fact.source_chunk_id else None
    pdf_page_url = build_pdf_url(fact.article_id, "original", page_start) if page_start is not None else None
    return {
        "id": str(fact.id),
        "article_id": str(fact.article_id),
        "title": article.title if article is not None else None,
        "doi": article.doi if article is not None else None,
        "source_chunk_id": str(fact.source_chunk_id) if fact.source_chunk_id is not None else None,
        "page_start": page_start,
        "page_end": page_end,
        "entity_type": fact.entity_type,
        "field_name": fact.field_name,
        "field_value_text": fact.field_value_text,
        "field_value_numeric": str(fact.field_value_numeric) if fact.field_value_numeric is not None else None,
        "unit": fact.unit,
        "confidence": str(fact.confidence) if fact.confidence is not None else None,
        "source": fact.source,
        "article_url": f"/ui/articles/{fact.article_id}",
        "context_url": context_url,
        "pdf_page_url": pdf_page_url,
    }
