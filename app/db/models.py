from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    articles: Mapped[list[Article]] = relationship(back_populates="collection")
    vector_index_states: Mapped[list[VectorIndexState]] = relationship(back_populates="collection", cascade="all, delete-orphan")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = uuid_pk()
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    authors: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    year: Mapped[int | None] = mapped_column(Integer)
    journal: Mapped[str | None] = mapped_column(Text)
    doi: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    publication_type: Mapped[str | None] = mapped_column(Text)
    pdf_original_path: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_ocr_path: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    access_source: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    zotero_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    collection: Mapped[Collection] = relationship(back_populates="articles")
    pages: Mapped[list[Page]] = relationship(back_populates="article", cascade="all, delete-orphan")
    chunks: Mapped[list[Chunk]] = relationship(back_populates="article", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text)
    has_text_layer: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selected_text_layer: Mapped[str] = mapped_column(Text, nullable=False, default="original")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article: Mapped[Article] = relationship(back_populates="pages")


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    normalized_name: Mapped[str | None] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    text_layer: Mapped[str] = mapped_column(Text, nullable=False, default="original")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article: Mapped[Article] = relationship(back_populates="chunks")


class PageTextLayer(Base):
    __tablename__ = "page_text_layers"
    __table_args__ = (UniqueConstraint("article_id", "page_number", "layer_type", name="uq_page_text_layers_article_page_layer"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    layer_type: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    has_usable_text: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    source_pdf_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArticleTag(Base):
    __tablename__ = "article_tags"

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    tag_type: Mapped[str] = mapped_column(Text, nullable=False)
    tag_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    input_path: Mapped[str] = mapped_column(Text, nullable=False)
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id"), nullable=False)
    article_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))
    original_filename: Mapped[str | None] = mapped_column(Text)
    checksum_sha256: Mapped[str | None] = mapped_column(Text)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    force_ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_id: Mapped[str | None] = mapped_column(Text)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VectorIndexState(Base):
    __tablename__ = "vector_index_states"
    __table_args__ = (
        UniqueConstraint("collection_id", "embedding_model", name="uq_vector_index_states_collection_model"),
        CheckConstraint("status IN ('ready', 'stale', 'rebuilding', 'failed')", name="ck_vector_index_states_status"),
        CheckConstraint("desired_revision >= 0", name="ck_vector_index_states_desired_revision"),
        CheckConstraint("active_revision IS NULL OR active_revision >= 0", name="ck_vector_index_states_active_revision"),
        CheckConstraint("building_revision IS NULL OR building_revision >= 0", name="ck_vector_index_states_building_revision"),
        CheckConstraint("attempt_count >= 0", name="ck_vector_index_states_attempt_count"),
        CheckConstraint(
            "status != 'ready' OR (active_revision IS NOT NULL "
            "AND active_generation_id IS NOT NULL AND active_manifest_sha256 IS NOT NULL)",
            name="ck_vector_index_states_ready_active_generation",
        ),
        Index("ix_vector_index_states_status_requested_at", "status", "requested_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="stale")
    desired_revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    active_revision: Mapped[int | None] = mapped_column(BigInteger)
    building_revision: Mapped[int | None] = mapped_column(BigInteger)
    active_generation_id: Mapped[str | None] = mapped_column(Text)
    active_manifest_sha256: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_type: Mapped[str | None] = mapped_column(Text)
    last_error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    collection: Mapped[Collection] = relationship(back_populates="vector_index_states")


class StructuredFact(Base):
    __tablename__ = "structured_facts"

    id: Mapped[uuid.UUID] = uuid_pk()
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    field_value_text: Mapped[str | None] = mapped_column(Text)
    field_value_numeric: Mapped[float | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(Text)
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    confidence: Mapped[float | None] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column(Text, nullable=False)
