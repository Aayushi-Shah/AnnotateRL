import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TaskType(str, PyEnum):
    coding = "coding"
    reasoning = "reasoning"
    comparison = "comparison"
    correction = "correction"


class TaskStatus(str, PyEnum):
    draft = "draft"
    available = "available"
    completed = "completed"


class AssignmentStatus(str, PyEnum):
    in_progress = "in_progress"
    completed = "completed"
    expired = "expired"
    abandoned = "abandoned"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    annotations_required: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    creator: Mapped["User"] = relationship(back_populates="tasks", foreign_keys=[created_by])  # noqa: F821
    assignments: Mapped[list["TaskAssignment"]] = relationship(back_populates="task")
    annotations: Mapped[list["Annotation"]] = relationship(back_populates="task")  # noqa: F821


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    annotator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task: Mapped["Task"] = relationship(back_populates="assignments")
    annotator: Mapped["User"] = relationship(back_populates="assignments")  # noqa: F821
    annotation: Mapped["Annotation | None"] = relationship(back_populates="assignment")  # noqa: F821
