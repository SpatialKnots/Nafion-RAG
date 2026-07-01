"""add dual text layers

Revision ID: 0002_dual_text_layers
Revises: 0001_initial_phase1
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_dual_text_layers"
down_revision = "0001_initial_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("selected_text_layer", sa.Text(), nullable=False, server_default="original"))
    op.add_column("chunks", sa.Column("text_layer", sa.Text(), nullable=False, server_default="original"))

    op.create_table(
        "page_text_layers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("layer_type", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("has_usable_text", sa.Boolean(), nullable=False),
        sa.Column("quality_score", sa.Numeric(), nullable=False),
        sa.Column("source_pdf_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("article_id", "page_number", "layer_type", name="uq_page_text_layers_article_page_layer"),
    )
    op.create_index("ix_page_text_layers_article_id", "page_text_layers", ["article_id"])
    op.create_index("ix_page_text_layers_layer_type", "page_text_layers", ["layer_type"])


def downgrade() -> None:
    op.drop_index("ix_page_text_layers_layer_type", table_name="page_text_layers")
    op.drop_index("ix_page_text_layers_article_id", table_name="page_text_layers")
    op.drop_table("page_text_layers")
    op.drop_column("chunks", "text_layer")
    op.drop_column("pages", "selected_text_layer")
