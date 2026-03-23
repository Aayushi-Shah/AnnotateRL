"""Add fine-tuning tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fine_tuning_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("trigger_task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("training_data_s3_key", sa.String(500), nullable=True),
        sa.Column("training_data_rows", sa.Integer, nullable=True),
        sa.Column("external_job_id", sa.String(200), nullable=True),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "model_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version_tag", sa.String(50), nullable=False, unique=True),
        sa.Column("base_model", sa.String(100), nullable=False, server_default="claude-opus-4-6"),
        sa.Column("finetuned_model_id", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("training_job_id", UUID(as_uuid=True), sa.ForeignKey("fine_tuning_jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Track which model version generated each task's AI response
    op.add_column("tasks", sa.Column("model_version_id", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "model_version_id")
    op.drop_table("model_versions")
    op.drop_table("fine_tuning_jobs")
