from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AnnotationCreate(BaseModel):
    assignment_id: str
    response: str = Field(default="")
    signal_type: str = Field(pattern="^(rating|comparison|correction|binary)$")
    signal_value: dict[str, Any]
    # signal_value shapes by type:
    #   rating:     {"score": 4}               — int 1-5
    #   comparison: {"chosen": "A", "rationale": "..."}
    #   correction: {"edited": "..."}
    #   binary:     {"accept": true}


class AnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    assignment_id: str
    annotator_id: str
    response: str
    signal_type: str
    signal_value: dict[str, Any]
    source: str  # "human" | "ai"
    created_at: datetime
    updated_at: datetime | None
