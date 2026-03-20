import io
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.s3 import get_s3
from app.models.annotation import Annotation, RewardSignal
from app.models.dataset import Dataset, DatasetExport
from app.models.task import Task


async def run_export(export_id: uuid.UUID) -> None:
    """
    Background task: build JSONL in HuggingFace datasets format and upload to S3.
    Each record: {id, prompt, context, task_type, response, signal_type, reward, metadata}
    """
    from app.core.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        export = await db.get(DatasetExport, export_id)
        if not export:
            return

        export.status = "running"
        await db.commit()

        try:
            dataset = await db.get(Dataset, export.dataset_id)
            rows = await _build_rows(db, dataset)

            buf = io.BytesIO()
            for row in rows:
                buf.write((json.dumps(row) + "\n").encode())
            buf.seek(0)

            s3_key = f"exports/{dataset.id}/{export_id}.jsonl"
            get_s3().upload_fileobj(buf, settings.S3_BUCKET, s3_key)

            export.status = "done"
            export.s3_key = s3_key
            export.row_count = len(rows)
            export.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            export.status = "failed"
            export.error_message = str(e)

        await db.commit()


async def _build_rows(db: AsyncSession, dataset: Dataset) -> list[dict]:
    cfg = dataset.filter_config

    query = (
        select(Annotation, RewardSignal, Task)
        .join(RewardSignal, RewardSignal.annotation_id == Annotation.id)
        .join(Task, Task.id == Annotation.task_id)
    )

    if cfg.get("task_type"):
        query = query.where(Task.task_type == cfg["task_type"])
    if cfg.get("date_from"):
        query = query.where(Annotation.created_at >= cfg["date_from"])
    if cfg.get("date_to"):
        query = query.where(Annotation.created_at <= cfg["date_to"])
    if cfg.get("annotator_ids"):
        query = query.where(Annotation.annotator_id.in_(cfg["annotator_ids"]))
    if cfg.get("min_rating") is not None:
        query = query.where(
            RewardSignal.signal_type == "rating",
            RewardSignal.value["score"].as_integer() >= cfg["min_rating"],
        )

    result = await db.execute(query)
    rows = []
    for annotation, signal, task in result.all():
        reward = _extract_scalar_reward(signal)
        rows.append({
            "id": str(annotation.id),
            "prompt": task.prompt,
            "context": task.context,
            "task_type": task.task_type,
            "response": annotation.response,
            "signal_type": signal.signal_type,
            "reward": reward,
            "signal_value": signal.value,
            "metadata": {
                "task_id": str(task.id),
                "annotator_id": str(annotation.annotator_id),
                "created_at": annotation.created_at.isoformat(),
            },
        })
    return rows


def _extract_scalar_reward(signal: RewardSignal) -> float | None:
    """Normalize all signal types to a scalar for fine-tuning pipelines."""
    v = signal.value
    if signal.signal_type == "rating":
        return float(v.get("score", 0))
    if signal.signal_type == "binary":
        return 1.0 if v.get("accept") else 0.0
    if signal.signal_type == "comparison":
        return 1.0 if v.get("chosen") == "A" else 0.0
    return None
