"""Drop unique constraint on task_assignments(task_id, annotator_id)

Revision ID: 004
Revises: 003
Create Date: 2026-03-23

Allows an annotator to be assigned the same task multiple times across
different generation rounds (each round creates a new assignment row).
The in_progress status check prevents double-claiming within a single round.
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_assignment_task_annotator", "task_assignments", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_assignment_task_annotator", "task_assignments", ["task_id", "annotator_id"]
    )
