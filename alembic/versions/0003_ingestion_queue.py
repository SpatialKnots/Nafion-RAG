"""add ingestion upload queue fields

Revision ID: 0003_ingestion_queue
Revises: 0002_dual_text_layers
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_ingestion_queue"
down_revision = "0002_dual_text_layers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("original_filename", sa.Text(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("checksum_sha256", sa.Text(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("force_ocr", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("ingestion_jobs", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ingestion_jobs", sa.Column("worker_id", sa.Text(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("error_type", sa.Text(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_foreign_key(
        "fk_ingestion_jobs_article_id_articles",
        "ingestion_jobs",
        "articles",
        ["article_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_status",
        "ingestion_jobs",
        "status IN ('queued', 'processing', 'indexed', 'duplicate', 'failed')",
    )
    op.create_check_constraint("ck_ingestion_jobs_attempt_count", "ingestion_jobs", "attempt_count >= 0")
    op.create_check_constraint(
        "ck_ingestion_jobs_file_size_bytes",
        "ingestion_jobs",
        "file_size_bytes IS NULL OR file_size_bytes >= 0",
    )
    op.create_index("ix_ingestion_jobs_status_created_at", "ingestion_jobs", ["status", "created_at"])
    op.create_index("ix_ingestion_jobs_checksum_sha256", "ingestion_jobs", ["checksum_sha256"])
    op.create_index(
        "uq_ingestion_jobs_active_checksum",
        "ingestion_jobs",
        ["checksum_sha256"],
        unique=True,
        postgresql_where=sa.text("checksum_sha256 IS NOT NULL AND status IN ('queued', 'processing') AND force_ocr = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_ingestion_jobs_active_checksum", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_checksum_sha256", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_status_created_at", table_name="ingestion_jobs")
    op.drop_constraint("ck_ingestion_jobs_file_size_bytes", "ingestion_jobs", type_="check")
    op.drop_constraint("ck_ingestion_jobs_attempt_count", "ingestion_jobs", type_="check")
    op.drop_constraint("ck_ingestion_jobs_status", "ingestion_jobs", type_="check")
    op.drop_constraint("fk_ingestion_jobs_article_id_articles", "ingestion_jobs", type_="foreignkey")
    op.drop_column("ingestion_jobs", "updated_at")
    op.drop_column("ingestion_jobs", "error_type")
    op.drop_column("ingestion_jobs", "heartbeat_at")
    op.drop_column("ingestion_jobs", "worker_id")
    op.drop_column("ingestion_jobs", "attempt_count")
    op.drop_column("ingestion_jobs", "force_ocr")
    op.drop_column("ingestion_jobs", "file_size_bytes")
    op.drop_column("ingestion_jobs", "checksum_sha256")
    op.drop_column("ingestion_jobs", "original_filename")
    op.drop_column("ingestion_jobs", "article_id")
