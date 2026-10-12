"""Read existing page evidence without reselecting layers or modifying ingestion."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Page, PageTextLayer
from app.documents.service import PageEvidenceNotFoundError, PageLayer, PdfLayer, PdfStorageIntegrityError, resolve_article_pdf
from app.records.schema import SourceRegion, source_identity, text_hash


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_region_from_page(
    session: Session,
    settings: Settings,
    article_id: UUID,
    page_number: int,
    *,
    layer: PageLayer = "selected",
    start: int = 0,
    end: int | None = None,
    selection_basis: Literal["manual_development", "expert_oracle", "fixed_page", "retrieval"],
    selection_note: str,
) -> SourceRegion:
    if page_number < 1:
        raise ValueError("page_number must be positive")
    article = session.get(Article, article_id)
    if article is None:
        raise PageEvidenceNotFoundError(f"Unknown article {article_id}")
    original = resolve_article_pdf(article, settings, "original").path
    original_hash = file_hash(original)
    if original_hash != article.checksum_sha256:
        raise PdfStorageIntegrityError(f"Original PDF checksum mismatch: {article_id}")

    page = None
    resolved_layer: str = layer
    if layer == "selected":
        page = session.scalars(select(Page).where(Page.article_id == article_id, Page.page_number == page_number)).one_or_none()
        if page is None:
            raise PageEvidenceNotFoundError(f"Unknown selected page {page_number} for {article_id}")
        resolved_layer = page.selected_text_layer
    if resolved_layer not in ("original", "ocr"):
        raise PdfStorageIntegrityError(f"Unsupported recorded text layer: {resolved_layer}")
    text_layer = session.scalars(
        select(PageTextLayer).where(
            PageTextLayer.article_id == article_id,
            PageTextLayer.page_number == page_number,
            PageTextLayer.layer_type == resolved_layer,
        )
    ).one_or_none()
    if text_layer is None:
        raise PageEvidenceNotFoundError(f"Missing recorded {resolved_layer} layer for {article_id} page {page_number}")
    if page is not None and page.text != text_layer.text:
        raise PdfStorageIntegrityError("Selected page text differs from recorded text layer")
    layer_path = resolve_article_pdf(article, settings, cast(PdfLayer, resolved_layer)).path
    # Resolve PageTextLayer's registered path using the same document root guard.
    layer_article = Article(pdf_original_path=text_layer.source_pdf_path, pdf_ocr_path=text_layer.source_pdf_path)
    recorded_path = resolve_article_pdf(layer_article, settings, cast(PdfLayer, resolved_layer)).path
    if recorded_path != layer_path:
        raise PdfStorageIntegrityError("Text layer PDF differs from registered article PDF")
    layer_hash = original_hash if layer_path == original else file_hash(layer_path)
    final_end = len(text_layer.text) if end is None else end
    data: dict[str, object] = {
        "article_id": article_id,
        "original_pdf_path": str(original),
        "original_pdf_sha256": original_hash,
        "page_number": page_number,
        "text_layer_id": text_layer.id,
        "text_layer": resolved_layer,
        "layer_pdf_path": str(layer_path),
        "layer_pdf_sha256": layer_hash,
        "page_text": text_layer.text,
        "page_text_sha256": text_hash(text_layer.text),
        "start": start,
        "end": final_end,
        "quote": text_layer.text[start:final_end],
        "quote_sha256": text_hash(text_layer.text[start:final_end]),
        "selection_basis": selection_basis,
        "selection_note": selection_note,
    }
    data["region_id"] = source_identity(data)
    return SourceRegion.model_validate(data)


def verify_live_region(session: Session, settings: Settings, region: SourceRegion) -> None:
    """Fail if stored text, layer identity, PDF bytes, or resolved paths have changed."""
    current = source_region_from_page(
        session, settings, region.article_id, region.page_number,
        layer=region.text_layer, start=region.start, end=region.end,
        selection_basis=region.selection_basis, selection_note=region.selection_note,
    )
    if current != region:
        raise PdfStorageIntegrityError(f"Source region differs from live evidence: {region.region_id}")


def source_regions_from_pages(
    session: Session,
    settings: Settings,
    article_id: UUID,
    page_numbers: Sequence[int],
    *,
    layer: PageLayer = "selected",
    selection_basis: Literal["manual_development", "expert_oracle", "fixed_page", "retrieval"],
    selection_note: str,
) -> tuple[SourceRegion, ...]:
    """Export separate exact pages in declared order, without merging their text."""
    if not page_numbers or any(page < 1 for page in page_numbers):
        raise ValueError("Supply at least one positive page number")
    if len(set(page_numbers)) != len(page_numbers):
        raise ValueError("Duplicate page numbers are not allowed")
    return tuple(
        source_region_from_page(
            session, settings, article_id, page,
            layer=layer, selection_basis=selection_basis, selection_note=selection_note,
        )
        for page in page_numbers
    )
