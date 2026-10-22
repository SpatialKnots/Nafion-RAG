"""Persist source-bound metadata proposals without changing article column types."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '0006_metadata_extractions'
down_revision = '0005_library_sources'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('article_metadata_extractions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('sequence_no', sa.BigInteger(), sa.Identity(always=True), nullable=False, unique=True),
        sa.Column('article_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('input_sha256', sa.Text(), nullable=False),
        sa.Column('code_sha256', sa.Text(), nullable=False),
        sa.Column('payload_sha256', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_article_metadata_extractions_article_created', 'article_metadata_extractions', ['article_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_article_metadata_extractions_article_created', table_name='article_metadata_extractions')
    op.drop_table('article_metadata_extractions')
