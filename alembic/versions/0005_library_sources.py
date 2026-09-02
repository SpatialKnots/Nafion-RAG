"""add library source registry

Revision ID: 0005_library_sources
Revises: 0004_vector_index_lifecycle
Create Date: 2026-09-01
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_library_sources"
down_revision = "0004_vector_index_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "library_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("watch_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("recursive", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], name="fk_library_sources_collection_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id", "path", name="uq_library_sources_collection_path"),
        sa.CheckConstraint("status IN ('active', 'disabled', 'missing', 'error')", name="ck_library_sources_status"),
    )
    op.create_index("ix_library_sources_collection_status", "library_sources", ["collection_id", "status"])

    op.create_table(
        "library_source_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("library_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_path", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_hash_sha256", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("mtime_ns", sa.BigInteger(), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ingestion_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="discovered"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], name="fk_library_source_files_article_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id"],
            ["ingestion_jobs.id"],
            name="fk_library_source_files_ingestion_job_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["library_source_id"],
            ["library_sources.id"],
            name="fk_library_source_files_library_source_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("library_source_id", "external_path", name="uq_library_source_files_source_external_path"),
        sa.CheckConstraint(
            "status IN ('discovered', 'queued', 'ingesting', 'text_ready', 'embedding', 'ready', 'duplicate', 'missing', 'failed')",
            name="ck_library_source_files_status",
        ),
    )
    op.create_index("ix_library_source_files_source_status", "library_source_files", ["library_source_id", "status"])
    op.create_index("ix_library_source_files_hash", "library_source_files", ["content_hash_sha256"])
    op.create_index("ix_library_source_files_ingestion_job", "library_source_files", ["ingestion_job_id"])


def downgrade() -> None:
    op.drop_index("ix_library_source_files_ingestion_job", table_name="library_source_files")
    op.drop_index("ix_library_source_files_hash", table_name="library_source_files")
    op.drop_index("ix_library_source_files_source_status", table_name="library_source_files")
    op.drop_table("library_source_files")
    op.drop_index("ix_library_sources_collection_status", table_name="library_sources")
    op.drop_table("library_sources")
