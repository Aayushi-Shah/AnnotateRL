"""Add training_stats column to fine_tuning_jobs

Revision ID: 003
Revises: 002
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fine_tuning_jobs", sa.Column("training_stats", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("fine_tuning_jobs", "training_stats")
