from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chunking.simple import PageText, chunk_pages
from app.core.config import Settings
from app.db.models import Article, Chunk, Collection, IngestionJob, Page
from app.extraction.ocr import run_ocrmypdf
from app.extraction.text_quality import has_usable_text_layer, should_run_ocr
from app.ingestion.checksum import sha256_file
from app.ingestion.pdf_extract import extract_pages
from app.ingestion.pdf_store import copy_original_pdf, ocr_pdf_path
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


def ingest_pdf(session: Session, settings: Settings, input_path: Path, collection_name: str) -> IngestionResult:
    source_path = input_path.resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if source_path.suffix.lower() != ".pdf":
        raise ValueError(f"Only PDF files are supported: {source_path}")

    collection = get_collection(session, collection_name)
    checksum = sha256_file(source_path)
    duplicate = session.scalar(select(Article).where(Article.checksum_sha256 == checksum))
    if duplicate is not None:
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
        extracted_pages = extract_pages(stored_pdf)
        page_texts = [page.text for page in extracted_pages]
        ocr_required = should_run_ocr(page_texts, settings.ocr_enabled)
        ocr_used = False
        stored_ocr_pdf: Path | None = None
        if ocr_required:
            stored_ocr_pdf = run_ocrmypdf(
                stored_pdf,
                ocr_pdf_path(source_path, settings.data_root, checksum),
                languages=settings.ocr_languages,
                command=settings.ocr_command,
                timeout_seconds=settings.ocr_timeout_seconds,
            )
            extracted_pages = extract_pages(stored_ocr_pdf)
            page_texts = [page.text for page in extracted_pages]
            if not has_usable_text_layer(page_texts):
                raise RuntimeError(f"OCR completed but output still lacks a usable text layer: {stored_ocr_pdf}")
            ocr_used = True
        combined_first_pages = "\n".join(page_texts[:3])
        doi = extract_first_doi(combined_first_pages)

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

        for extracted in extracted_pages:
            has_text = bool(extracted.text.strip())
            session.add(
                Page(
                    article_id=article.id,
                    page_number=extracted.page_number,
                    text=extracted.text,
                    image_path=None,
                    has_text_layer=has_text,
                    ocr_used=ocr_used,
                )
            )

        chunks = chunk_pages(
            [PageText(page_number=page.page_number, text=page.text) for page in extracted_pages],
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
                    text=chunk.text,
                    token_count=chunk.token_count,
                    char_count=chunk.char_count,
                )
            )

        job.status = "indexed"
        job.finished_at = datetime.now(UTC)
        session.commit()
        return IngestionResult(
            article_id=str(article.id),
            status="indexed",
            checksum_sha256=checksum,
            page_count=len(extracted_pages),
            chunk_count=len(chunks),
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
