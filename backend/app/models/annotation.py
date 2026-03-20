import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SignalType(str, PyEnum):
    rating = "rating"
    comparison = "comparison"
    correction = "correction"
    binary = "binary"


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("task_assignments.id"), nullable=False, unique=True)
    annotator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    task: Mapped["Task"] = relationship(back_populates="annotations")  # noqa: F821
    assignment: Mapped["TaskAssignment"] = relationship(back_populates="annotation")  # noqa: F821
    annotator: Mapped["User"] = relationship(back_populates="annotations")  # noqa: F821
    reward_signal: Mapped["RewardSignal | None"] = relationship(back_populates="annotation")


class RewardSignal(Base):
    __tablename__ = "reward_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("annotations.id"), nullable=False, unique=True)
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    annotation: Mapped["Annotation"] = relationship(back_populates="reward_signal")
