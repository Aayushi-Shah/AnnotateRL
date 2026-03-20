from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    prompt: str = Field(min_length=1)
    context: str | None = None
    task_type: str = Field(pattern="^(coding|reasoning|comparison|correction)$")
    priority: int = Field(default=0, ge=0, le=100)
    annotations_required: int = Field(default=1, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    prompt: str | None = None
    context: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    metadata: dict[str, Any] | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    prompt: str
    context: str | None
    task_type: str
    status: str
    priority: int
    annotations_required: int
    created_by: str
    created_at: datetime
    updated_at: datetime | None
    metadata: dict[str, Any]
    annotation_count: int = 0


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    annotator_id: str
    status: str
    claimed_at: datetime
    expires_at: datetime
    completed_at: datetime | None
