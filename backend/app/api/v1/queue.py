import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.deps import AnnotatorDep, DbDep
from app.core.redis import get_redis
from app.models.task import Task, TaskAssignment, TaskStatus, AssignmentStatus
from app.schemas.task import AssignmentResponse, TaskResponse
from app.services.queue import claim_specific

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("", response_model=list[TaskResponse])
async def list_available(
    db: DbDep,
    annotator: AnnotatorDep,
    task_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Tasks available for this annotator to claim (not already taken by them)."""
    subq = (
        select(TaskAssignment.task_id)
        .where(
            TaskAssignment.annotator_id == annotator.id,
        )
    )
    query = select(Task).where(
        Task.status == TaskStatus.available,
        Task.id.not_in(subq),
    )
    if task_type:
        query = query.where(Task.task_type == task_type)

    result = await db.execute(query.order_by(Task.priority.desc(), Task.created_at).limit(limit))
    tasks = result.scalars().all()

    return [
        TaskResponse(
            id=str(t.id),
            title=t.title,
            prompt=t.prompt,
            context=t.context,
            task_type=t.task_type,
            status=t.status,
            priority=t.priority,
            annotations_required=t.annotations_required,
            created_by=str(t.created_by),
            created_at=t.created_at,
            updated_at=t.updated_at,
            metadata=t.metadata_,
        )
        for t in tasks
    ]


@router.post("/{task_id}/claim", response_model=AssignmentResponse, status_code=201)
async def claim_task(task_id: uuid.UUID, db: DbDep, annotator: AnnotatorDep):
    """Atomically claim a specific task. Uses SELECT FOR UPDATE SKIP LOCKED."""
    redis = get_redis()
    assignment = await claim_specific(db, redis, annotator.id, task_id)
    if not assignment:
        raise HTTPException(status_code=409, detail="Task already claimed or no longer available")

    return AssignmentResponse(
        id=str(assignment.id),
        task_id=str(assignment.task_id),
        annotator_id=str(assignment.annotator_id),
        status=assignment.status,
        claimed_at=assignment.claimed_at,
        expires_at=assignment.expires_at,
        completed_at=assignment.completed_at,
    )


@router.get("/mine", response_model=list[AssignmentResponse])
async def my_assignments(db: DbDep, annotator: AnnotatorDep):
    result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.annotator_id == annotator.id,
            TaskAssignment.status == AssignmentStatus.in_progress,
        ).order_by(TaskAssignment.expires_at)
    )
    assignments = result.scalars().all()
    return [
        AssignmentResponse(
            id=str(a.id),
            task_id=str(a.task_id),
            annotator_id=str(a.annotator_id),
            status=a.status,
            claimed_at=a.claimed_at,
            expires_at=a.expires_at,
            completed_at=a.completed_at,
        )
        for a in assignments
    ]


@router.post("/{assignment_id}/abandon", response_model=AssignmentResponse)
async def abandon(assignment_id: uuid.UUID, db: DbDep, annotator: AnnotatorDep):
    assignment = await db.get(TaskAssignment, assignment_id)
    if not assignment or assignment.annotator_id != annotator.id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.status != AssignmentStatus.in_progress:
        raise HTTPException(status_code=400, detail="Assignment is not in progress")

    assignment.status = AssignmentStatus.abandoned
    await db.commit()
    await db.refresh(assignment)

    return AssignmentResponse(
        id=str(assignment.id),
        task_id=str(assignment.task_id),
        annotator_id=str(assignment.annotator_id),
        status=assignment.status,
        claimed_at=assignment.claimed_at,
        expires_at=assignment.expires_at,
        completed_at=assignment.completed_at,
    )
