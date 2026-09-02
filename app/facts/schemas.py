from __future__ import annotations

from pydantic import BaseModel


class StructuredFactResponse(BaseModel):
    id: str
    article_id: str
    title: str | None
    doi: str | None
    source_chunk_id: str | None
    page_start: int | None
    page_end: int | None
    entity_type: str
    field_name: str
    field_value_text: str | None
    field_value_numeric: str | None
    unit: str | None
    confidence: str | None
    source: str
    article_url: str
    context_url: str | None
    pdf_page_url: str | None


class StructuredFactsResponse(BaseModel):
    items: list[StructuredFactResponse]
    summary: dict[str, object]
