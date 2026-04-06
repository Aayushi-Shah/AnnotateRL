import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import DbDep, ResearcherDep
from app.models.eval import EvalResult, EvalSet
from app.models.finetune import FineTuningJob, ModelVersion
from app.schemas.finetune import (
    EvalResultResponse,
    FineTuningJobResponse,
    FineTuningTriggerRequest,
    ModelVersionResponse,
    ScoreRequest,
    ScoreResponse,
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
        training_stats=job.training_stats,
        external_job_id=job.external_job_id,
        config=job.config,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _eval_response(er: EvalResult) -> EvalResultResponse:
    return EvalResultResponse(
        id=str(er.id),
        model_version_id=str(er.model_version_id),
        eval_set_id=str(er.eval_set_id),
        status=er.status,
        win_rate=er.win_rate,
        error_message=er.error_message,
        created_at=er.created_at,
        completed_at=er.completed_at,
    )


def _version_response(v: ModelVersion) -> ModelVersionResponse:
    # Pick the most recent eval result (by created_at)
    latest_eval = None
    if v.eval_results:
        latest = max(v.eval_results, key=lambda e: e.created_at)
        latest_eval = _eval_response(latest)
    return ModelVersionResponse(
        id=str(v.id),
        version_tag=v.version_tag,
        base_model=v.base_model,
        finetuned_model_id=v.finetuned_model_id,
        is_active=v.is_active,
        training_job_id=str(v.training_job_id) if v.training_job_id else None,
        created_at=v.created_at,
        latest_eval=latest_eval,
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
    result = await db.execute(
        select(ModelVersion)
        .options(selectinload(ModelVersion.eval_results))
        .order_by(ModelVersion.created_at.desc())
    )
    return [_version_response(v) for v in result.scalars().all()]


@router.post("/models/{version_id}/eval", response_model=EvalResultResponse, status_code=202)
async def trigger_eval(
    version_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbDep,
    researcher: ResearcherDep,
):
    """
    Trigger an eval run for a candidate model version.
    Auto-builds an eval set from recent completed tasks if none exists.
    """
    version = await db.get(ModelVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    # Build eval set from recent tasks
    from app.services.eval import _build_default_eval_set, run_eval
    eval_set = await _build_default_eval_set(db)

    eval_result = EvalResult(
        model_version_id=version_id,
        eval_set_id=eval_set.id,
        status="pending",
    )
    db.add(eval_result)
    await db.commit()
    await db.refresh(eval_result)

    background_tasks.add_task(run_eval, eval_result.id)

    return _eval_response(eval_result)


@router.post("/models/{version_id}/activate", response_model=ModelVersionResponse)
async def activate_model_version(
    version_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbDep,
    researcher: ResearcherDep,
):
    """
    Activate a candidate model version.
    Triggers background re-generation of all previously rejected tasks using the new model.
    """
    result = await db.execute(
        select(ModelVersion)
        .options(selectinload(ModelVersion.eval_results))
        .where(ModelVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    # Deactivate all others
    others = await db.execute(
        select(ModelVersion).where(ModelVersion.is_active == True)  # noqa: E712
    )
    for v in others.scalars().all():
        v.is_active = False

    version.is_active = True
    await db.commit()
    await db.refresh(version)

    # Re-generate rejected tasks with the newly activated model
    from app.services.ai_agent import regenerate_rejected_tasks
    background_tasks.add_task(regenerate_rejected_tasks, version.id)

    return _version_response(version)


@router.post("/models/active/score", response_model=ScoreResponse)
async def score_response(
    payload: ScoreRequest,
    db: DbDep,
    researcher: ResearcherDep,
):
    """
    Score a prompt+response pair using the active model as a reward model.

    For stub/no-model: uses DB similarity (difflib) against existing rating annotations.
    For real fine-tuned models: calls Claude with a scoring prompt.
    Returns predicted quality score (1.0–5.0) and confidence (0.0–1.0).
    """
    from difflib import SequenceMatcher
    from app.models.annotation import Annotation, RewardSignal
    from app.models.task import Task
    from app.services.ai_agent import _get_api_key, _get_active_model

    # Check if we have a real (non-stub) active model
    active_q = await db.execute(
        select(ModelVersion)
        .options(selectinload(ModelVersion.eval_results))
        .where(ModelVersion.is_active == True)  # noqa: E712
    )
    active_version = active_q.scalar_one_or_none()
    model_id = active_version.finetuned_model_id if active_version else None
    is_real_model = model_id and not model_id.startswith("stub-")

    api_key = _get_api_key()

    if is_real_model and api_key:
        # Call the fine-tuned model as a judge
        from openai import AsyncOpenAI
        from app.services.ai_agent import _chat, _SYSTEM
        client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        judge_prompt = (
            f"Question: {payload.prompt}\n\n"
            f"Response: {payload.response}\n\n"
            "Rate the quality, accuracy, and helpfulness of this response on a scale of 1 to 5.\n"
            "5 = excellent, 4 = good, 3 = adequate, 2 = poor, 1 = very poor.\n"
            "Reply with ONLY a single digit (1, 2, 3, 4, or 5)."
        )
        import re
        raw = await _chat(client, model_id, _SYSTEM["reasoning"], judge_prompt, max_tokens=10)
        m = re.search(r"[1-5]", raw)
        score = float(m.group()) if m else 3.0
        return ScoreResponse(score=score, confidence=0.9, source="model")

    # DB similarity fallback: find rating annotations on similar prompts
    ann_result = await db.execute(
        select(Task.prompt, RewardSignal.value)
        .join(Annotation, Annotation.task_id == Task.id)
        .join(RewardSignal, RewardSignal.annotation_id == Annotation.id)
        .where(RewardSignal.signal_type == "rating")
        .limit(200)
    )
    rows = ann_result.all()

    if not rows:
        return ScoreResponse(score=3.0, confidence=0.0, source="db_similarity")

    # Weight each annotation by prompt similarity
    weighted_scores: list[tuple[float, float]] = []
    for task_prompt, signal_value in rows:
        sim = SequenceMatcher(None, payload.prompt.lower(), task_prompt.lower()).ratio()
        if sim > 0.1:
            score_val = float(signal_value.get("score", 3))
            weighted_scores.append((sim, score_val))

    if not weighted_scores:
        return ScoreResponse(score=3.0, confidence=0.0, source="db_similarity")

    total_weight = sum(w for w, _ in weighted_scores)
    weighted_avg = sum(w * s for w, s in weighted_scores) / total_weight
    confidence = min(1.0, len(weighted_scores) / 10)  # saturates at 10 matches

    return ScoreResponse(
        score=round(weighted_avg, 2),
        confidence=round(confidence, 2),
        source="db_similarity",
    )
