import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import AnnotatorDep, CurrentUser, DbDep, ResearcherDep
from app.models.annotation import Annotation, RewardSignal
from app.models.task import TaskAssignment, AssignmentStatus, Task, TaskStatus
from app.schemas.annotation import AnnotationCreate, AnnotationResponse
from app.schemas.common import PaginatedResponse
from sqlalchemy import func

router = APIRouter(prefix="/annotations", tags=["annotations"])


def _to_response(annotation: Annotation) -> AnnotationResponse:
    signal = annotation.reward_signal
    return AnnotationResponse(
        id=str(annotation.id),
        task_id=str(annotation.task_id),
        assignment_id=str(annotation.assignment_id),
        annotator_id=str(annotation.annotator_id),
        response=annotation.response,
        signal_type=signal.signal_type if signal else "",
        signal_value=signal.value if signal else {},
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


@router.post("", response_model=AnnotationResponse, status_code=201)
async def submit_annotation(payload: AnnotationCreate, db: DbDep, annotator: AnnotatorDep):
    """Submit response + reward signal atomically. Marks assignment as completed."""
    assignment_id = uuid.UUID(payload.assignment_id)
    assignment = await db.get(TaskAssignment, assignment_id)

    if not assignment or assignment.annotator_id != annotator.id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.status != AssignmentStatus.in_progress:
        raise HTTPException(status_code=400, detail="Assignment is not in progress")
    if assignment.expires_at < datetime.now(timezone.utc):
        assignment.status = AssignmentStatus.expired
        await db.commit()
        raise HTTPException(status_code=400, detail="Assignment has expired")

    # Check for duplicate submission
    existing = await db.scalar(
        select(func.count(Annotation.id)).where(Annotation.assignment_id == assignment_id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Annotation already submitted for this assignment")

    annotation = Annotation(
        task_id=assignment.task_id,
        assignment_id=assignment_id,
        annotator_id=annotator.id,
        response=payload.response,
        metadata_={},
    )
    db.add(annotation)
    await db.flush()  # get annotation.id before adding reward signal

    signal = RewardSignal(
        annotation_id=annotation.id,
        signal_type=payload.signal_type,
        value=payload.signal_value,
    )
    db.add(signal)

    assignment.status = AssignmentStatus.completed
    assignment.completed_at = datetime.now(timezone.utc)

    # Check if task is now fully annotated
    completed_count = await db.scalar(
        select(func.count(TaskAssignment.id)).where(
            TaskAssignment.task_id == assignment.task_id,
            TaskAssignment.status == AssignmentStatus.completed,
        )
    )
    task = await db.get(Task, assignment.task_id)
    # +1 because we haven't committed the current assignment yet
    if (completed_count + 1) >= task.annotations_required:
        task.status = TaskStatus.completed
        from app.core.redis import get_redis
        from app.services.queue import remove_task_from_queue
        await remove_task_from_queue(get_redis(), task.id)

    await db.commit()
    await db.refresh(annotation)
    await db.refresh(signal)
    annotation.reward_signal = signal

    return _to_response(annotation)


@router.get("", response_model=PaginatedResponse[AnnotationResponse])
async def list_annotations(
    db: DbDep,
    current_user: CurrentUser,
    task_id: str | None = Query(default=None),
    annotator_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    query = select(Annotation).options(selectinload(Annotation.reward_signal))

    if task_id:
        query = query.where(Annotation.task_id == uuid.UUID(task_id))
    if annotator_id:
        query = query.where(Annotation.annotator_id == uuid.UUID(annotator_id))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.offset((page - 1) * size).limit(size).order_by(Annotation.created_at.desc())
    )
    annotations = result.scalars().all()

    return PaginatedResponse(
        items=[_to_response(a) for a in annotations],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(annotation_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    result = await db.execute(
        select(Annotation)
        .options(selectinload(Annotation.reward_signal))
        .where(Annotation.id == annotation_id)
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return _to_response(annotation)
