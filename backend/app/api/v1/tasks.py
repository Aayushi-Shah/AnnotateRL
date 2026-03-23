import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, DbDep, ResearcherDep
from app.core.redis import get_redis
from app.models.annotation import Annotation
from app.models.task import Task, TaskStatus
from app.schemas.common import PaginatedResponse
from app.schemas.task import AssignmentResponse, TaskCreate, TaskResponse, TaskUpdate
from app.services.ai_agent import generate_for_task
from app.services.queue import publish_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_to_response(task: Task, annotation_count: int = 0) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        title=task.title,
        prompt=task.prompt,
        context=task.context,
        task_type=task.task_type,
        status=task.status,
        priority=task.priority,
        annotations_required=task.annotations_required,
        created_by=str(task.created_by),
        created_at=task.created_at,
        updated_at=task.updated_at,
        metadata=task.metadata_,
        annotation_count=annotation_count,
    )


@router.get("", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    db: DbDep,
    current_user: CurrentUser,
    status: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    query = select(Task)
    if status and status != "all":
        query = query.where(Task.status == status)
    if task_type and task_type != "all":
        query = query.where(Task.task_type == task_type)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset((page - 1) * size).limit(size).order_by(Task.created_at.desc()))
    tasks = result.scalars().all()

    # Batch annotation counts
    task_ids = [t.id for t in tasks]
    counts_result = await db.execute(
        select(Annotation.task_id, func.count(Annotation.id))
        .where(Annotation.task_id.in_(task_ids))
        .group_by(Annotation.task_id)
    )
    counts = {row[0]: row[1] for row in counts_result}

    return PaginatedResponse(
        items=[_task_to_response(t, counts.get(t.id, 0)) for t in tasks],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(payload: TaskCreate, db: DbDep, researcher: ResearcherDep):
    task = Task(
        title=payload.title,
        prompt=payload.prompt,
        context=payload.context,
        task_type=payload.task_type,
        priority=payload.priority,
        annotations_required=payload.annotations_required,
        created_by=researcher.id,
        metadata_=payload.metadata,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _task_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    count = await db.scalar(
        select(func.count(Annotation.id)).where(Annotation.task_id == task_id)
    )
    return _task_to_response(task, count)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: uuid.UUID, payload: TaskUpdate, db: DbDep, researcher: ResearcherDep):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft tasks can be edited")

    for field, value in payload.model_dump(exclude_none=True).items():
        if field == "metadata":
            task.metadata_ = value
        else:
            setattr(task, field, value)

    await db.commit()
    await db.refresh(task)
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, db: DbDep, researcher: ResearcherDep):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft tasks can be deleted")
    await db.delete(task)
    await db.commit()


@router.post("/{task_id}/publish", response_model=TaskResponse)
async def publish_task_endpoint(
    task_id: uuid.UUID,
    db: DbDep,
    researcher: ResearcherDep,
    background_tasks: BackgroundTasks,
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.draft:
        raise HTTPException(status_code=400, detail="Task is already published")

    task.status = TaskStatus.available
    await db.commit()
    await db.refresh(task)

    redis = get_redis()
    await publish_task(redis, task.id, task.priority)

    # Auto-generate AI responses in the background if key is configured
    from app.core.config import settings
    if settings.OPENROUTER_API_KEY or settings.ANTHROPIC_API_KEY:
        background_tasks.add_task(generate_for_task, task.id)

    return _task_to_response(task)
