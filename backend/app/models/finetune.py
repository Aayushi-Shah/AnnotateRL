import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FineTuneJobStatus(str, PyEnum):
    pending = "pending"
    preparing_data = "preparing_data"
    training = "training"
    completed = "completed"
    failed = "failed"


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_tag: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    base_model: Mapped[str] = mapped_column(String(100), nullable=False, default="claude-opus-4-6")
    finetuned_model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    training_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fine_tuning_jobs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    training_job: Mapped["FineTuningJob | None"] = relationship(
        back_populates="model_version", foreign_keys=[training_job_id]
    )


class FineTuningJob(Base):
    __tablename__ = "fine_tuning_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    trigger_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True
    )
    training_data_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    training_data_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_job_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trigger_task: Mapped["Task | None"] = relationship(foreign_keys=[trigger_task_id])  # noqa: F821
    model_version: Mapped["ModelVersion | None"] = relationship(
        back_populates="training_job", foreign_keys="ModelVersion.training_job_id"
    )
