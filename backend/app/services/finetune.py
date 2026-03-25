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
from app.models.task import Task, TaskAssignment, AssignmentStatus

logger = logging.getLogger(__name__)

DEFAULT_BASE_MODEL = "claude-opus-4-6"

# Quality thresholds (must match annotations.py)
IAA_KAPPA_MIN = 0.2  # below this = skip entire task (poor annotator agreement)


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


# ── Data preparation ─────────────────────────────────────────────────────────


def _extract_scalar_reward(signal: RewardSignal) -> float | None:
    v = signal.value
    if signal.signal_type == "rating":
        return float(v.get("score", 0))
    if signal.signal_type == "binary":
        return 1.0 if v.get("accept") else 0.0
    if signal.signal_type == "comparison":
        return 1.0 if v.get("chosen") == "A" else 0.0
    return None


def _kappa_gate(signal_type: str, values: list[dict]) -> float | None:
    """Returns Cohen's kappa for binary/comparison signals, None for others."""
    if signal_type not in ("binary", "comparison"):
        return None
    labels = (
        ["accept" if v.get("accept") else "reject" for v in values]
        if signal_type == "binary"
        else [v.get("chosen", "?") for v in values]
    )
    n = len(labels)
    if n < 2:
        return None
    pairs = [(labels[i], labels[j]) for i in range(n) for j in range(i + 1, n)]
    Po = sum(1 for a, b in pairs if a == b) / len(pairs)
    Pe = sum((labels.count(c) / n) ** 2 for c in set(labels))
    return (Po - Pe) / (1 - Pe) if Pe < 1 else 1.0


async def _build_training_rows(db) -> tuple[list[dict], dict]:
    """
    Build quality-filtered training rows with DPO pairs.
    Returns (rows, stats) where rows include accepted (SFT), negative (SFT),
    and DPO pairs for tasks that improved across generations.
    Only includes current-round annotations (respects round_completed_offset).
    """
    query = (
        select(Annotation, RewardSignal, Task, TaskAssignment)
        .join(RewardSignal, RewardSignal.annotation_id == Annotation.id)
        .join(Task, Task.id == Annotation.task_id)
        .join(TaskAssignment, TaskAssignment.id == Annotation.assignment_id)
        .where(TaskAssignment.status == AssignmentStatus.completed)
    )
    result = await db.execute(query)
    all_data = result.all()

    # Group by task
    by_task: dict[str, list] = {}
    task_map: dict[str, Task] = {}
    for annotation, signal, task, assignment in all_data:
        tid = str(task.id)
        by_task.setdefault(tid, []).append((annotation, signal, assignment))
        task_map[tid] = task

    rows: list[dict] = []
    stats: dict[str, int] = {
        "total_annotations": 0,  # counted after round filter
        "accepted": 0,
        "negative_examples": 0,
        "dpo_pairs": 0,
        "skipped_low_iaa": 0,
        "skipped_ambiguous": 0,
        "skipped_correction": 0,
    }

    for tid, entries in by_task.items():
        task = task_map[tid]

        # Filter to current-round annotations only
        offset = (task.metadata_ or {}).get("round_completed_offset", 0)
        if offset > 0:
            entries = sorted(entries, key=lambda e: e[2].completed_at)[offset:]
        if not entries:
            continue

        stats["total_annotations"] += len(entries)
        quality_status = (task.metadata_ or {}).get("quality_status")

        if quality_status not in ("accepted", "rejected"):
            stats["skipped_ambiguous"] += len(entries)
            continue

        # IAA gate: skip tasks with poor annotator agreement
        if len(entries) >= 2:
            stype = entries[0][1].signal_type
            kappa = _kappa_gate(stype, [s.value for _, s, _ in entries])
            if kappa is not None and kappa < IAA_KAPPA_MIN:
                stats["skipped_low_iaa"] += len(entries)
                continue

        label = "accepted" if quality_status == "accepted" else "negative"

        for annotation, signal, _ in entries:
            if signal.signal_type == "correction":
                stats["skipped_correction"] += 1
                continue

            reward = _extract_scalar_reward(signal)
            rows.append({
                "format": "sft",
                "label": label,
                "id": str(annotation.id),
                "prompt": task.prompt,
                "context": task.context,
                "task_type": task.task_type,
                "response": annotation.response,
                "signal_type": signal.signal_type,
                "reward": reward,
                "signal_value": signal.value,
                "metadata": {
                    "task_id": tid,
                    "annotator_id": str(annotation.annotator_id),
                    "created_at": annotation.created_at.isoformat(),
                    "quality_status": quality_status,
                },
            })
            if label == "accepted":
                stats["accepted"] += 1
            else:
                stats["negative_examples"] += 1

        # DPO pair: task was rejected in a prior round, then accepted in a later round
        if (
            quality_status == "accepted"
            and (task.metadata_ or {}).get("generation_round", 1) >= 2
        ):
            history = (task.metadata_ or {}).get("round_history", [])
            old_response = history[-1].get("old_response", "") if history else ""
            current_response = (task.metadata_ or {}).get("model_response", "")
            if current_response and old_response:
                rows.append({
                    "format": "dpo",
                    "prompt": task.prompt,
                    "chosen": current_response,
                    "rejected": old_response,
                    "task_id": tid,
                })
                stats["dpo_pairs"] += 1

    return rows, stats


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

            rows, stats = await _build_training_rows(db)
            job.training_stats = stats

            min_rows = job.config.get("min_rows", settings.FINETUNE_MIN_ROWS)
            total_rows = stats.get("accepted", 0) + stats.get("negative_examples", 0)
            if total_rows < min_rows:
                job.status = FineTuneJobStatus.failed
                job.error_message = (
                    f"Insufficient training data: {total_rows} rows (need {min_rows})"
                )
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

            # Phase 3: Create candidate model version (NOT auto-activated)
            # Researcher reviews stats and manually activates via the fine-tuning page
            max_tag = await db.scalar(select(func.count(ModelVersion.id)))
            version_tag = f"v{(max_tag or 0) + 1}"

            base_model = job.config.get("base_model", DEFAULT_BASE_MODEL)
            version = ModelVersion(
                version_tag=version_tag,
                base_model=base_model,
                finetuned_model_id=external_id,
                is_active=False,  # candidate — researcher activates manually
                training_job_id=job.id,
            )

            db.add(version)
            await db.flush()

            job.status = FineTuneJobStatus.completed
            job.completed_at = datetime.now(timezone.utc)

            logger.info(
                "Fine-tuning job %s completed: %d rows (%d accepted, %d DPO pairs), candidate %s",
                job_id, len(rows), stats.get("accepted", 0), stats.get("dpo_pairs", 0), version_tag,
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
