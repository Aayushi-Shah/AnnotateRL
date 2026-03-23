import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import DbDep, ResearcherDep
from app.models.finetune import FineTuningJob, ModelVersion
from app.schemas.finetune import (
    FineTuningJobResponse,
    FineTuningTriggerRequest,
    ModelVersionResponse,
)
from app.services.finetune import run_finetuning_job, DEFAULT_BASE_MODEL

router = APIRouter(prefix="/finetune", tags=["finetune"])


def _job_response(job: FineTuningJob) -> FineTuningJobResponse:
    return FineTuningJobResponse(
        id=str(job.id),
        status=job.status,
        trigger_task_id=str(job.trigger_task_id) if job.trigger_task_id else None,
        training_data_s3_key=job.training_data_s3_key,
        training_data_rows=job.training_data_rows,
        external_job_id=job.external_job_id,
        config=job.config,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _version_response(v: ModelVersion) -> ModelVersionResponse:
    return ModelVersionResponse(
        id=str(v.id),
        version_tag=v.version_tag,
        base_model=v.base_model,
        finetuned_model_id=v.finetuned_model_id,
        is_active=v.is_active,
        training_job_id=str(v.training_job_id) if v.training_job_id else None,
        created_at=v.created_at,
    )


@router.get("/jobs", response_model=list[FineTuningJobResponse])
async def list_jobs(db: DbDep, researcher: ResearcherDep):
    result = await db.execute(select(FineTuningJob).order_by(FineTuningJob.created_at.desc()))
    return [_job_response(j) for j in result.scalars().all()]


@router.get("/jobs/{job_id}", response_model=FineTuningJobResponse)
async def get_job(job_id: uuid.UUID, db: DbDep, researcher: ResearcherDep):
    job = await db.get(FineTuningJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Fine-tuning job not found")
    return _job_response(job)


@router.post("/jobs", response_model=FineTuningJobResponse, status_code=202)
async def trigger_finetune(
    background_tasks: BackgroundTasks,
    db: DbDep,
    researcher: ResearcherDep,
    payload: FineTuningTriggerRequest | None = None,
):
    """Manually trigger a fine-tuning run."""
    config = {
        "provider": settings.FINETUNE_PROVIDER,
        "base_model": (payload.base_model if payload and payload.base_model else DEFAULT_BASE_MODEL),
        "min_rows": (payload.min_rows if payload and payload.min_rows else settings.FINETUNE_MIN_ROWS),
        "manual": True,
    }

    job = FineTuningJob(config=config)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(run_finetuning_job, job.id)

    return _job_response(job)


@router.get("/models", response_model=list[ModelVersionResponse])
async def list_model_versions(db: DbDep, researcher: ResearcherDep):
    result = await db.execute(select(ModelVersion).order_by(ModelVersion.created_at.desc()))
    return [_version_response(v) for v in result.scalars().all()]


@router.post("/models/{version_id}/activate", response_model=ModelVersionResponse)
async def activate_model_version(version_id: uuid.UUID, db: DbDep, researcher: ResearcherDep):
    """Switch the active model version used for AI generation."""
    version = await db.get(ModelVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    # Deactivate all others
    result = await db.execute(
        select(ModelVersion).where(ModelVersion.is_active == True)  # noqa: E712
    )
    for v in result.scalars().all():
        v.is_active = False

    version.is_active = True
    await db.commit()
    await db.refresh(version)
    return _version_response(version)
