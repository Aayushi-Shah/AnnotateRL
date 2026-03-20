from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    filter_config: dict[str, Any] = Field(default_factory=dict)
    # filter_config keys: task_type, date_from, date_to, annotator_ids, min_rating


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    filter_config: dict[str, Any]
    created_by: str
    created_at: datetime


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    format: str
    status: str
    s3_key: str | None
    row_count: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    download_url: str | None = None
