"""
Closed-loop fine-tuning service.
Triggered automatically when a task reaches its annotation quota,
or manually by a researcher via the API.

Uses a stub training provider by default (simulates training for learning/dev).
Swap to a real provider by changing FINETUNE_PROVIDER in config.
"""
import asyncio
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select, func

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.s3 import get_s3
from app.models.annotation import Annotation, RewardSignal
from app.models.finetune import FineTuningJob, FineTuneJobStatus, ModelVersion
from app.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)

DEFAULT_BASE_MODEL = "claude-opus-4-6"


# ── Training provider abstraction ────────────────────────────────────────────


class TrainingProvider(Protocol):
    async def start_training(self, s3_key: str, config: dict) -> str:
        """Start a training job. Returns an external job ID."""
        ...


class StubProvider:
    """Simulates training for development/learning. No GPU needed."""

    async def start_training(self, s3_key: str, config: dict) -> str:
        logger.info("StubProvider: simulating training on %s", s3_key)
        await asyncio.sleep(2)
        return f"stub-ft-{uuid.uuid4().hex[:8]}"


def _get_provider() -> TrainingProvider:
    if settings.FINETUNE_PROVIDER == "stub":
        return StubProvider()
    raise ValueError(f"Unknown FINETUNE_PROVIDER: {settings.FINETUNE_PROVIDER}")


# ── Data preparation (reuses export.py pattern) ─────────────────────────────


def _extract_scalar_reward(signal: RewardSignal) -> float | None:
    v = signal.value
    if signal.signal_type == "rating":
        return float(v.get("score", 0))
    if signal.signal_type == "binary":
        return 1.0 if v.get("accept") else 0.0
    if signal.signal_type == "comparison":
        return 1.0 if v.get("chosen") == "A" else 0.0
    return None


async def _build_training_rows(db) -> list[dict]:
    """Query all completed annotations with reward signals for training."""
    query = (
        select(Annotation, RewardSignal, Task)
        .join(RewardSignal, RewardSignal.annotation_id == Annotation.id)
        .join(Task, Task.id == Annotation.task_id)
        .where(Task.status == TaskStatus.completed)
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


# ── Core fine-tuning job runner ──────────────────────────────────────────────


async def run_finetuning_job(job_id: uuid.UUID) -> None:
    """
    Background task: prepare training data, upload to S3, run training provider.
    Opens its own DB session (same pattern as ai_agent.py and export.py).
    """
    async with AsyncSessionLocal() as db:
        job = await db.get(FineTuningJob, job_id)
        if not job:
            return

        try:
            # Phase 1: Prepare data
            job.status = FineTuneJobStatus.preparing_data
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            rows = await _build_training_rows(db)

            min_rows = job.config.get("min_rows", settings.FINETUNE_MIN_ROWS)
            if len(rows) < min_rows:
                job.status = FineTuneJobStatus.failed
                job.error_message = f"Insufficient training data: {len(rows)} rows (need {min_rows})"
                await db.commit()
                return

            # Upload JSONL to S3
            buf = io.BytesIO()
            for row in rows:
                buf.write((json.dumps(row) + "\n").encode())
            buf.seek(0)

            s3_key = f"finetune/{job_id}/training_data.jsonl"
            get_s3().upload_fileobj(buf, settings.S3_BUCKET, s3_key)

            job.training_data_s3_key = s3_key
            job.training_data_rows = len(rows)

            # Phase 2: Train
            job.status = FineTuneJobStatus.training
            await db.commit()

            provider = _get_provider()
            external_id = await provider.start_training(s3_key, job.config)
            job.external_job_id = external_id

            # Phase 3: Create model version
            # Determine next version tag
            max_tag = await db.scalar(
                select(func.count(ModelVersion.id))
            )
            version_tag = f"v{(max_tag or 0) + 1}"

            base_model = job.config.get("base_model", DEFAULT_BASE_MODEL)
            version = ModelVersion(
                version_tag=version_tag,
                base_model=base_model,
                finetuned_model_id=external_id,
                is_active=True,
                training_job_id=job.id,
            )

            # Deactivate all other versions
            existing = await db.execute(
                select(ModelVersion).where(ModelVersion.is_active == True)  # noqa: E712
            )
            for v in existing.scalars().all():
                v.is_active = False

            db.add(version)
            await db.flush()

            job.status = FineTuneJobStatus.completed
            job.completed_at = datetime.now(timezone.utc)

            logger.info(
                "Fine-tuning job %s completed: %d rows, model version %s (%s)",
                job_id, len(rows), version_tag, external_id,
            )

        except Exception as e:
            logger.exception("Fine-tuning job %s failed", job_id)
            job.status = FineTuneJobStatus.failed
            job.error_message = f"{type(e).__name__}: {str(e)}"

        await db.commit()


# ── Trigger gating ───────────────────────────────────────────────────────────


async def maybe_trigger_finetune(task_id: uuid.UUID) -> None:
    """
    Called as a BackgroundTask after a task completes.
    Checks gating conditions and kicks off a fine-tuning job if appropriate.
    """
    if not settings.FINETUNE_ENABLED:
        return

    async with AsyncSessionLocal() as db:
        # Don't start a new job if one is already running
        active_count = await db.scalar(
            select(func.count(FineTuningJob.id)).where(
                FineTuningJob.status.in_([
                    FineTuneJobStatus.pending,
                    FineTuneJobStatus.preparing_data,
                    FineTuneJobStatus.training,
                ])
            )
        )
        if active_count and active_count > 0:
            logger.info("Skipping fine-tune trigger: job already in progress")
            return

        job = FineTuningJob(
            trigger_task_id=task_id,
            config={
                "provider": settings.FINETUNE_PROVIDER,
                "base_model": DEFAULT_BASE_MODEL,
                "min_rows": settings.FINETUNE_MIN_ROWS,
            },
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info("Triggered fine-tuning job %s for task %s", job.id, task_id)

    # Run the job (uses its own session internally)
    await run_finetuning_job(job.id)
