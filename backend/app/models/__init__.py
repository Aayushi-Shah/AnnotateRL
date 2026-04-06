# Import all models here so Alembic can detect them
from app.models.base import Base
from app.models.user import User, RefreshToken
from app.models.task import Task, TaskAssignment
from app.models.annotation import Annotation, RewardSignal
from app.models.dataset import Dataset, DatasetExport
from app.models.finetune import FineTuningJob, ModelVersion
from app.models.eval import EvalSet, EvalResult

__all__ = [
    "Base",
    "User",
    "RefreshToken",
    "Task",
    "TaskAssignment",
    "Annotation",
    "RewardSignal",
    "Dataset",
    "DatasetExport",
    "FineTuningJob",
    "ModelVersion",
    "EvalSet",
    "EvalResult",
]
