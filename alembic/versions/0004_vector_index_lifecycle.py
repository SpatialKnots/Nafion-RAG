"""add vector index lifecycle state

Revision ID: 0004_vector_index_lifecycle
Revises: 0003_ingestion_queue
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_vector_index_lifecycle"
down_revision = "0003_ingestion_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vector_index_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="stale"),
        sa.Column("desired_revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("active_revision", sa.BigInteger(), nullable=True),
        sa.Column("building_revision", sa.BigInteger(), nullable=True),
        sa.Column("active_generation_id", sa.Text(), nullable=True),
        sa.Column("active_manifest_sha256", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_type", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], name="fk_vector_index_states_collection_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id", "embedding_model", name="uq_vector_index_states_collection_model"),
        sa.CheckConstraint("status IN ('ready', 'stale', 'rebuilding', 'failed')", name="ck_vector_index_states_status"),
        sa.CheckConstraint("desired_revision >= 0", name="ck_vector_index_states_desired_revision"),
        sa.CheckConstraint("active_revision IS NULL OR active_revision >= 0", name="ck_vector_index_states_active_revision"),
        sa.CheckConstraint("building_revision IS NULL OR building_revision >= 0", name="ck_vector_index_states_building_revision"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_vector_index_states_attempt_count"),
        sa.CheckConstraint(
            "status != 'ready' OR (active_revision IS NOT NULL "
            "AND active_generation_id IS NOT NULL AND active_manifest_sha256 IS NOT NULL)",
            name="ck_vector_index_states_ready_active_generation",
        ),
    )
    op.create_index("ix_vector_index_states_status_requested_at", "vector_index_states", ["status", "requested_at"])


def downgrade() -> None:
    op.drop_index("ix_vector_index_states_status_requested_at", table_name="vector_index_states")
    op.drop_table("vector_index_states")
