from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.chunking.simple import PageText, chunk_pages
from app.classification.rules import classify_article
from app.core.config import Settings
from app.db.models import Article, Chunk, Collection, IngestionJob, Page
from app.extraction.ocr import run_ocrmypdf
from app.extraction.text_quality import has_usable_text_layer, should_run_ocr
from app.ingestion.checksum import sha256_file
from app.ingestion.pdf_extract import ExtractedPage, extract_pages
from app.ingestion.pdf_store import copy_original_pdf, ocr_pdf_path
from app.ingestion.text_layers import OCR_LAYER, ORIGINAL_LAYER, SelectedPageText, build_layer_inputs, replace_text_layers, select_best_pages
from app.metadata.doi import extract_first_doi


@dataclass(frozen=True)
class IngestionResult:
    article_id: str
    status: str
    checksum_sha256: str
    page_count: int
    chunk_count: int
    ocr_required: bool


def get_collection(session: Session, name: str) -> Collection:
    collection = session.scalar(select(Collection).where(Collection.name == name))
    if collection is None:
        raise ValueError(f"Unknown collection: {name}")
    return collection


def _selected_pages_to_page_texts(pages: list[SelectedPageText]) -> list[PageText]:
    return [PageText(page_number=page.page_number, text=page.text) for page in pages]


def _chunk_text_layer(chunk: object, selected_pages: list[SelectedPageText]) -> str:
    layers = {
        page.selected_text_layer
        for page in selected_pages
        if page.page_number >= chunk.page_start and page.page_number <= chunk.page_end
    }
    if len(layers) == 1:
        return next(iter(layers))
    if len(layers) > 1:
        return "mixed"
    return ORIGINAL_LAYER


def _replace_article_content(session: Session, settings: Settings, article: Article, pages: list[SelectedPageText]) -> int:
    session.execute(delete(Chunk).where(Chunk.article_id == article.id))
    session.execute(delete(Page).where(Page.article_id == article.id))
    session.flush()

    for page in pages:
        session.add(
            Page(
                article_id=article.id,
                page_number=page.page_number,
                text=page.text,
                image_path=None,
                has_text_layer=page.has_text_layer,
                ocr_used=page.ocr_used,
                selected_text_layer=page.selected_text_layer,
            )
        )

    chunks = chunk_pages(
        _selected_pages_to_page_texts(pages),
        target_chars=settings.chunk_target_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )
    for chunk in chunks:
        session.add(
            Chunk(
                article_id=article.id,
                section_id=None,
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                source_type=chunk.source_type,
                text_layer=_chunk_text_layer(chunk, pages),
                text=chunk.text,
                token_count=chunk.token_count,
                char_count=chunk.char_count,
            )
        )
    return len(chunks)


def _first_nonempty_text(page_sets: list[list[ExtractedPage] | list[SelectedPageText]]) -> str:
    for pages in page_sets:
        text = "\n".join(page.text for page in pages[:3])
        if text.strip():
            return text
    return ""


def reselect_article_text(session: Session, settings: Settings, article: Article) -> int:
    original_pdf = Path(article.pdf_original_path)
    if original_pdf.exists():
        original_pages = extract_pages(original_pdf)
        replace_text_layers(
            session,
            article,
            build_layer_inputs(original_pages, layer_type=ORIGINAL_LAYER, source_pdf_path=original_pdf),
        )
    if article.pdf_ocr_path:
        ocr_pdf = Path(article.pdf_ocr_path)
        if ocr_pdf.exists():
            ocr_pages = extract_pages(ocr_pdf)
            replace_text_layers(session, article, build_layer_inputs(ocr_pages, layer_type=OCR_LAYER, source_pdf_path=ocr_pdf))
    session.flush()
    selected_pages = select_best_pages(session, article)
    chunk_count = _replace_article_content(session, settings, article, selected_pages)
    classify_article(session, article)
    return chunk_count


def ingest_pdf(
    session: Session,
    settings: Settings,
    input_path: Path,
    collection_name: str,
    *,
    force_ocr: bool = False,
) -> IngestionResult:
    source_path = input_path.resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if source_path.suffix.lower() != ".pdf":
        raise ValueError(f"Only PDF files are supported: {source_path}")

    collection = get_collection(session, collection_name)
    checksum = sha256_file(source_path)
    duplicate = session.scalar(select(Article).where(Article.checksum_sha256 == checksum))
    if duplicate is not None and not force_ocr:
        return IngestionResult(
            article_id=str(duplicate.id),
            status="duplicate",
            checksum_sha256=checksum,
            page_count=len(duplicate.pages),
            chunk_count=len(duplicate.chunks),
            ocr_required=False,
        )

    job = IngestionJob(
        input_path=str(source_path),
        collection_id=collection.id,
        status="processing",
        started_at=datetime.now(UTC),
    )
    session.add(job)
    session.flush()

    try:
        stored_pdf = copy_original_pdf(source_path, settings.data_root, checksum)
        original_pages = extract_pages(stored_pdf)
        page_texts = [page.text for page in original_pages]
        ocr_required = force_ocr or should_run_ocr(page_texts, settings.ocr_enabled)
        stored_ocr_pdf: Path | None = None
        ocr_pages: list[ExtractedPage] = []
        if ocr_required:
            stored_ocr_pdf = run_ocrmypdf(
                stored_pdf,
                ocr_pdf_path(source_path, settings.data_root, checksum),
                languages=settings.ocr_languages,
                command=settings.ocr_command,
                timeout_seconds=settings.ocr_timeout_seconds,
                force=force_ocr,
            )
            ocr_pages = extract_pages(stored_ocr_pdf)
            ocr_page_texts = [page.text for page in ocr_pages]
            if not has_usable_text_layer(ocr_page_texts):
                raise RuntimeError(f"OCR completed but output still lacks a usable text layer: {stored_ocr_pdf}")

        doi = extract_first_doi(_first_nonempty_text([original_pages, ocr_pages]))
        if duplicate is None:
            article = Article(
                collection_id=collection.id,
                title=source_path.stem,
                authors=None,
                year=None,
                journal=None,
                doi=doi,
                abstract=None,
                language=None,
                publication_type=None,
                pdf_original_path=str(stored_pdf),
                pdf_ocr_path=str(stored_ocr_pdf) if stored_ocr_pdf is not None else None,
                source_url=None,
                access_source="manual",
                license=None,
                checksum_sha256=checksum,
                zotero_key=None,
                status="indexed",
                indexed_at=datetime.now(UTC),
            )
            session.add(article)
            session.flush()
        else:
            article = duplicate
            article.collection_id = collection.id
            article.doi = article.doi or doi
            article.pdf_original_path = str(stored_pdf)
            article.pdf_ocr_path = str(stored_ocr_pdf) if stored_ocr_pdf is not None else article.pdf_ocr_path
            article.status = "indexed"
            article.indexed_at = datetime.now(UTC)

        replace_text_layers(session, article, build_layer_inputs(original_pages, layer_type=ORIGINAL_LAYER, source_pdf_path=stored_pdf))
        if stored_ocr_pdf is not None:
            replace_text_layers(session, article, build_layer_inputs(ocr_pages, layer_type=OCR_LAYER, source_pdf_path=stored_ocr_pdf))
        session.flush()
        selected_pages = select_best_pages(session, article)
        if not selected_pages:
            article.status = "needs_review"
        chunk_count = _replace_article_content(session, settings, article, selected_pages)
        session.flush()
        classify_article(session, article)

        job.status = "indexed"
        job.finished_at = datetime.now(UTC)
        session.commit()
        return IngestionResult(
            article_id=str(article.id),
            status="indexed",
            checksum_sha256=checksum,
            page_count=len(selected_pages),
            chunk_count=chunk_count,
            ocr_required=ocr_required,
        )
    except Exception as exc:
        session.rollback()
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(UTC)
        session.add(job)
        session.commit()
        raise
