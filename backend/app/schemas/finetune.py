from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FineTuningJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    trigger_task_id: str | None
    training_data_s3_key: str | None
    training_data_rows: int | None
    training_stats: dict[str, Any] | None = None
    external_job_id: str | None
    config: dict[str, Any]
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class EvalResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_version_id: str
    eval_set_id: str
    status: str  # "pending" | "running" | "completed" | "failed"
    win_rate: float | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class ModelVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_tag: str
    base_model: str
    finetuned_model_id: str | None
    is_active: bool
    training_job_id: str | None
    created_at: datetime
    latest_eval: EvalResultResponse | None = None


class FineTuningTriggerRequest(BaseModel):
    """Optional overrides when manually triggering a fine-tuning run."""
    base_model: str | None = None
    min_rows: int | None = None


class ScoreRequest(BaseModel):
    prompt: str
    response: str


class ScoreResponse(BaseModel):
    score: float       # 1.0–5.0 predicted quality
    confidence: float  # 0.0–1.0 (how many similar examples support this estimate)
    source: str        # "model" | "db_similarity"
