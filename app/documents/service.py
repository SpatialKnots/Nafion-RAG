from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Page, PageTextLayer

PdfLayer = Literal["original", "ocr"]
PageLayer = Literal["selected", "original", "ocr"]


class DocumentAccessError(Exception):
    """Base class for expected document access failures."""


class PdfLayerUnavailableError(DocumentAccessError):
    pass


class PdfNotFoundError(DocumentAccessError):
    pass


class PdfStorageIntegrityError(DocumentAccessError):
    pass


class PageEvidenceNotFoundError(DocumentAccessError):
    pass


@dataclass(frozen=True)
class ResolvedPdf:
    path: Path
    layer: PdfLayer
    media_type: str
    download_name: str


@dataclass(frozen=True)
class PageEvidence:
    article_id: str
    title: str | None
    page_number: int
    requested_layer: PageLayer
    resolved_layer: str
    has_usable_text: bool
    text: str
    pdf_url: str
    pdf_page_url: str
    layer_pdf_url: str | None = None


def build_pdf_url(article_id: uuid.UUID | str, layer: PdfLayer = "original", page_number: int | None = None) -> str:
    url = f"/articles/{article_id}/pdf?layer={layer}"
    if page_number is not None:
        url = f"{url}#page={page_number}"
    return url


def resolve_article_pdf(article: Article, settings: Settings, layer: PdfLayer = "original") -> ResolvedPdf:
    stored_path = article.pdf_original_path if layer == "original" else article.pdf_ocr_path
    if not stored_path:
        raise PdfLayerUnavailableError("PDF layer is unavailable")

    data_root = settings.data_root.resolve()
    allowed_root = _allowed_root(data_root, layer).resolve()
    candidate = _candidate_path(Path(stored_path), data_root).resolve()
    _assert_inside(candidate, allowed_root)

    if candidate.suffix.lower() != ".pdf":
        raise PdfStorageIntegrityError("Stored PDF path does not point to a PDF file")
    if not candidate.is_file():
        raise PdfNotFoundError("PDF file is unavailable")

    return ResolvedPdf(
        path=candidate,
        layer=layer,
        media_type="application/pdf",
        download_name=_safe_download_name(article, layer, candidate),
    )


def get_article_page(
    session: Session,
    settings: Settings,
    article: Article,
    page_number: int,
    layer: PageLayer = "selected",
) -> PageEvidence:
    if page_number < 1:
        raise ValueError("page_number must be positive")

    if layer == "selected":
        page = session.scalar(select(Page).where(Page.article_id == article.id).where(Page.page_number == page_number))
        if page is None:
            raise PageEvidenceNotFoundError(f"Unknown page {page_number} for article {article.id}")
        text = page.text or ""
        resolved_layer = page.selected_text_layer
        has_usable_text = bool(text.strip())
    else:
        text_layer = session.scalar(
            select(PageTextLayer)
            .where(PageTextLayer.article_id == article.id)
            .where(PageTextLayer.page_number == page_number)
            .where(PageTextLayer.layer_type == layer)
        )
        if text_layer is None:
            raise PageEvidenceNotFoundError(f"Unknown {layer} text layer for article {article.id} page {page_number}")
        text = text_layer.text
        resolved_layer = text_layer.layer_type
        has_usable_text = bool(text_layer.has_usable_text)

    layer_pdf_url = _available_layer_pdf_url(article, settings, resolved_layer)
    return PageEvidence(
        article_id=str(article.id),
        title=article.title,
        page_number=page_number,
        requested_layer=layer,
        resolved_layer=resolved_layer,
        has_usable_text=has_usable_text,
        text=text,
        pdf_url=build_pdf_url(article.id, "original"),
        pdf_page_url=build_pdf_url(article.id, "original", page_number),
        layer_pdf_url=layer_pdf_url,
    )


def page_evidence_to_dict(evidence: PageEvidence) -> dict[str, object]:
    payload: dict[str, object] = {
        "article_id": evidence.article_id,
        "title": evidence.title,
        "page_number": evidence.page_number,
        "requested_layer": evidence.requested_layer,
        "resolved_layer": evidence.resolved_layer,
        "has_usable_text": evidence.has_usable_text,
        "text": evidence.text,
        "pdf_url": evidence.pdf_url,
        "pdf_page_url": evidence.pdf_page_url,
    }
    if evidence.layer_pdf_url is not None:
        payload["layer_pdf_url"] = evidence.layer_pdf_url
    return payload


def _allowed_root(data_root: Path, layer: PdfLayer) -> Path:
    if layer == "original":
        return data_root / "pdf"
    return data_root / "processed" / "ocr"


def _candidate_path(stored_path: Path, data_root: Path) -> Path:
    if stored_path.is_absolute():
        return stored_path
    parts = stored_path.parts
    if parts and parts[0] == data_root.name:
        return data_root.parent.joinpath(stored_path)
    return data_root / stored_path


def _assert_inside(path: Path, allowed_root: Path) -> None:
    try:
        path.relative_to(allowed_root)
    except ValueError as exc:
        raise PdfStorageIntegrityError("Stored PDF path is outside the allowed document root") from exc


def _safe_download_name(article: Article, layer: PdfLayer, path: Path) -> str:
    raw_title = (article.title or path.stem or str(article.id)).strip()
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_title).strip("._-")
    stem = (normalized or str(article.id))[:80]
    return f"{stem}_{layer}.pdf"


def _available_layer_pdf_url(article: Article, settings: Settings, layer: str) -> str | None:
    if layer not in ("original", "ocr") or layer == "original":
        return None
    try:
        resolve_article_pdf(article, settings, cast(PdfLayer, layer))
    except (PdfLayerUnavailableError, PdfNotFoundError, PdfStorageIntegrityError):
        return None
    return build_pdf_url(article.id, cast(PdfLayer, layer))
